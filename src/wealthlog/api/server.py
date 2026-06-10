"""wealthlog web/desktop UI (NiceGUI) — full CLI parity.

Exposed as the ``wealthlog`` console script. All features available in the
CLI/TUI are accessible here: expenses, income, budgets, investments, net
worth, liabilities, import/export, alerts, and categories.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import tempfile
from decimal import Decimal
from pathlib import Path

from nicegui import ui
from sqlmodel import select

from wealthlog.api.dashboard import asset_allocation_series, build_dashboard_data
from wealthlog.bootstrap import session_scope
from wealthlog.constants import (
    AlertKind,
    AssetType,
    CategoryType,
    CompoundingFrequency,
    LiabilityCategory,
    RecurrenceFrequency,
    TransactionType,
)
from wealthlog.db.models import Category, Investment
from wealthlog.logging_conf import get_logger
from wealthlog.services.alerts import AlertService
from wealthlog.services.benchmark import BenchmarkService
from wealthlog.services.budget import BudgetService
from wealthlog.services.concentration import ConcentrationService
from wealthlog.services.dividends import DividendService
from wealthlog.services.expense import ExpenseService
from wealthlog.services.export import CSV_KINDS, ExportService
from wealthlog.services.fetcher import FetcherService
from wealthlog.services.importer import ImportService
from wealthlog.services.income import IncomeService
from wealthlog.services.liability import LiabilityService
from wealthlog.services.networth import NetWorthService
from wealthlog.services.portfolio import PortfolioService
from wealthlog.services.recurring import RecurringExpenseService
from wealthlog.services.sip import SIPService
from wealthlog.services.tax import TaxService

logger = get_logger(__name__)

_TODAY = dt.date.today


def _fmt_inr(amount: Decimal | None) -> str:
    return "—" if amount is None else f"₹{amount:,.2f}"


def _fmt_pct(value: Decimal | None) -> str:
    return "—" if value is None else f"{value:+.2f}%"


def _allocation_chart_options(labels: list[str], values: list[float]) -> dict:
    return {
        "tooltip": {"trigger": "item"},
        "legend": {"top": "bottom"},
        "series": [
            {
                "name": "Allocation",
                "type": "pie",
                "radius": ["40%", "70%"],
                "data": [{"value": v, "name": n} for n, v in zip(labels, values, strict=True)],
            }
        ],
    }


def _history_chart_options(labels: list[str], invested: list[float], market: list[float]) -> dict:
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["Invested", "Market Value"]},
        "xAxis": {"type": "category", "data": labels},
        "yAxis": {"type": "value"},
        "series": [
            {"name": "Invested", "type": "line", "data": invested},
            {"name": "Market Value", "type": "line", "data": market, "areaStyle": {}},
        ],
    }


def _summary_card(title: str, value: str, color: str) -> None:
    with ui.card().classes(f"min-w-[180px] border-l-4 border-{color}"):
        ui.label(title).classes("text-xs uppercase text-gray-500")
        ui.label(value).classes("text-xl font-bold")


def _get_expense_categories() -> list[tuple[int, str]]:
    with session_scope() as session:
        cats = session.exec(
            select(Category).where(Category.type == CategoryType.EXPENSE).order_by(Category.name)
        ).all()
        return [(c.id, c.name) for c in cats]


def _get_income_categories() -> list[tuple[int, str]]:
    with session_scope() as session:
        cats = session.exec(
            select(Category).where(Category.type == CategoryType.INCOME).order_by(Category.name)
        ).all()
        return [(c.id, c.name) for c in cats]


def _get_investments() -> list[tuple[int, str, str]]:
    with session_scope() as session:
        invs = session.exec(
            select(Investment).order_by(Investment.symbol)
        ).all()
        return [(i.id, i.symbol, i.asset_type) for i in invs]


def _do_refresh() -> object:
    with session_scope() as session:
        return FetcherService(session).refresh_prices()


async def _refresh_prices() -> None:
    note = ui.notification("Refreshing prices…", spinner=True, timeout=None)
    try:
        result = await asyncio.to_thread(_do_refresh)
    finally:
        note.dismiss()
    if result.failed:
        ui.notify(f"Refreshed {len(result.updated)}, {len(result.failed)} failed", type="warning")
    else:
        ui.notify(f"Refreshed {len(result.updated)} price(s)", type="positive")


# ---------------------------------------------------------------------------
# Dashboard tab
# ---------------------------------------------------------------------------

def _render_dashboard() -> None:
    with session_scope() as session:
        data = build_dashboard_data(session)

    ui.label(f"As of {data.as_of:%d %b %Y}").classes("text-sm text-gray-500 mb-2")

    with ui.row().classes("w-full gap-4 flex-wrap"):
        _summary_card("Net worth", _fmt_inr(data.net_worth.net_worth_inr), "primary")
        _summary_card("Assets", _fmt_inr(data.net_worth.total_assets_inr), "secondary")
        _summary_card("Liabilities", _fmt_inr(data.net_worth.total_liabilities_inr), "warning")
        pnl_color = "positive" if data.pnl.pnl_abs_inr >= 0 else "negative"
        _summary_card("Unrealised P&L", _fmt_inr(data.pnl.pnl_abs_inr), pnl_color)
        xirr = (
            f"{data.portfolio_xirr * Decimal(100):+.2f}%"
            if data.portfolio_xirr is not None else "—"
        )
        _summary_card("Portfolio XIRR", xirr, "accent")
        _summary_card("Spent this month", _fmt_inr(data.month_total_inr), "orange")

    with ui.row().classes("w-full gap-4 flex-wrap items-start mt-4"):
        with ui.card().classes("flex-1 min-w-[320px]"):
            ui.label("Asset allocation").classes("text-lg font-semibold")
            labels, values = asset_allocation_series(data)
            if values:
                ui.echart(_allocation_chart_options(labels, values)).classes("h-64 w-full")
            else:
                ui.label("No holdings yet.").classes("text-gray-500")

        with ui.card().classes("flex-1 min-w-[320px]"):
            ui.label("Budget alerts").classes("text-lg font-semibold")
            if data.overages:
                for s in data.overages:
                    ui.label(
                        f"⚠ {s.category_name}: {_fmt_inr(s.spent_inr)} / "
                        f"{_fmt_inr(s.limit_inr)} ({s.pct_used:.0f}%)"
                    ).classes("text-red-600")
            else:
                ui.label("All budgets within limits 🎉").classes("text-green-600")


# ---------------------------------------------------------------------------
# Expenses tab
# ---------------------------------------------------------------------------

def _render_expenses() -> None:
    with ui.tabs().classes("w-full") as sub_tabs:
        t_list = ui.tab("List")
        t_add = ui.tab("Add")
        t_summary = ui.tab("Summary")
        t_recurring = ui.tab("Recurring")

    with ui.tab_panels(sub_tabs, value=t_list).classes("w-full"):
        with ui.tab_panel(t_list):
            _expense_list_panel()
        with ui.tab_panel(t_add):
            _expense_add_panel()
        with ui.tab_panel(t_summary):
            _expense_summary_panel()
        with ui.tab_panel(t_recurring):
            _recurring_panel()


@ui.refreshable
def _expense_list_panel() -> None:
    start_in = ui.input("Start date (YYYY-MM-DD)").classes("w-40")
    end_in = ui.input("End date (YYYY-MM-DD)").classes("w-40")

    cats = _get_expense_categories()
    cat_options = {"": "All categories"} | {str(cid): name for cid, name in cats}
    cat_sel = ui.select(cat_options, value="", label="Category").classes("w-48")

    @ui.refreshable
    def expense_table() -> None:
        with session_scope() as session:
            svc = ExpenseService(session)
            cat_id = int(cat_sel.value) if cat_sel.value else None
            try:
                start = dt.date.fromisoformat(start_in.value) if start_in.value else None
                end = dt.date.fromisoformat(end_in.value) if end_in.value else None
            except ValueError:
                ui.notify("Invalid date format", type="negative")
                return
            rows = svc.list_expenses(start=start, end=end, category_id=cat_id)
            cat_map = {c.id: c.name for c in session.exec(select(Category)).all()}

        if not rows:
            ui.label("No expenses found.").classes("text-gray-500")
            return

        columns = [
            {"name": "id", "label": "#", "field": "id", "sortable": True},
            {"name": "date", "label": "Date", "field": "date", "sortable": True},
            {"name": "amount", "label": "Amount", "field": "amount"},
            {"name": "category", "label": "Category", "field": "category"},
            {"name": "description", "label": "Description", "field": "description"},
            {"name": "tags", "label": "Tags", "field": "tags"},
            {"name": "actions", "label": "", "field": "actions"},
        ]
        table_rows = [
            {
                "id": e.id,
                "date": str(e.date),
                "amount": _fmt_inr(e.amount_inr),
                "category": cat_map.get(e.category_id, "—") if e.category_id else "—",
                "description": e.description or "—",
                "tags": ", ".join(e.tags) if e.tags else "—",
            }
            for e in rows
        ]
        tbl = ui.table(columns=columns, rows=table_rows, row_key="id").classes("w-full")
        tbl.add_slot("body-cell-actions", """
            <q-td :props="props">
                <q-btn size="sm" flat icon="delete" color="negative"
                    @click="$emit('delete', props.row.id)" />
            </q-td>
        """)
        tbl.on("delete", lambda e: _delete_expense(e.args, expense_table.refresh))
        ui.label(f"{len(rows)} expense(s)").classes("text-sm text-gray-500 mt-2")

    ui.button("Search", on_click=expense_table.refresh).props("color=primary outline size=sm")
    expense_table()


def _delete_expense(expense_id: int, refresh_fn) -> None:
    with session_scope() as session:
        ok = ExpenseService(session).delete_expense(expense_id)
    if ok:
        ui.notify(f"Deleted expense #{expense_id}", type="positive")
        refresh_fn()
    else:
        ui.notify(f"No expense #{expense_id}", type="negative")


def _expense_add_panel() -> None:
    ui.label("Add expense").classes("text-lg font-semibold mb-2")
    cats = _get_expense_categories()
    cat_options = {"": "No category"} | {str(cid): name for cid, name in cats}

    amount = ui.number("Amount (INR)", value=0, format="%.2f").classes("w-40")
    cat_sel = ui.select(cat_options, value="", label="Category").classes("w-48")
    date_in = ui.input("Date", value=_TODAY().isoformat()).classes("w-40")
    desc = ui.input("Description").classes("w-64")
    tags_in = ui.input("Tags (comma-separated)").classes("w-64")

    def submit() -> None:
        try:
            with session_scope() as session:
                cat_id = int(cat_sel.value) if cat_sel.value else None
                tag_list = [t.strip() for t in tags_in.value.split(",")] if tags_in.value else []
                ExpenseService(session).add_expense(
                    dt.date.fromisoformat(date_in.value),
                    str(amount.value),
                    category_id=cat_id,
                    description=desc.value or None,
                    tags=tag_list,
                )
            ui.notify("Expense added", type="positive")
            amount.value = 0
            desc.value = ""
            tags_in.value = ""
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Add expense", on_click=submit).props("color=primary")


def _expense_summary_panel() -> None:
    ui.label("Monthly expense summary").classes("text-lg font-semibold mb-2")
    today = _TODAY()
    year_in = ui.number("Year", value=today.year, format="%d").classes("w-28")
    month_in = ui.number("Month", value=today.month, min=1, max=12, format="%d").classes("w-20")

    @ui.refreshable
    def summary_view() -> None:
        with session_scope() as session:
            result = ExpenseService(session).monthly_summary(
                int(year_in.value), int(month_in.value)
            )

        if not result.by_category:
            ui.label("No expenses for this period.").classes("text-gray-500")
            return

        rows = sorted(result.by_category.items(), key=lambda kv: kv[1], reverse=True)
        columns = [
            {"name": "category", "label": "Category", "field": "category"},
            {"name": "spent", "label": "Spent", "field": "spent"},
        ]
        tbl_rows = [{"category": name, "spent": _fmt_inr(amt)} for name, amt in rows]
        ui.table(columns=columns, rows=tbl_rows).classes("w-full max-w-md")
        ui.label(f"Total: {_fmt_inr(result.total_inr)} across {result.count} expense(s)").classes(
            "font-bold mt-2"
        )

    ui.button("Show", on_click=summary_view.refresh).props("color=primary outline size=sm")
    summary_view()


def _recurring_panel() -> None:
    with ui.tabs().classes("w-full") as rec_tabs:
        t_rules = ui.tab("Rules")
        t_add = ui.tab("Add rule")
        t_generate = ui.tab("Generate")

    with ui.tab_panels(rec_tabs, value=t_rules).classes("w-full"):
        with ui.tab_panel(t_rules):
            _recurring_rules_view()
        with ui.tab_panel(t_add):
            _recurring_add_view()
        with ui.tab_panel(t_generate):
            _recurring_generate_view()


@ui.refreshable
def _recurring_rules_view() -> None:
    with session_scope() as session:
        rules = RecurringExpenseService(session).list_rules(include_inactive=True)
        cat_map = {c.id: c.name for c in session.exec(select(Category)).all()}

    if not rules:
        ui.label("No recurring rules.").classes("text-gray-500")
        return

    columns = [
        {"name": "id", "label": "#", "field": "id"},
        {"name": "amount", "label": "Amount", "field": "amount"},
        {"name": "frequency", "label": "Frequency", "field": "frequency"},
        {"name": "category", "label": "Category", "field": "category"},
        {"name": "active", "label": "Active", "field": "active"},
        {"name": "last_gen", "label": "Last generated", "field": "last_gen"},
        {"name": "actions", "label": "", "field": "actions"},
    ]
    rows = [
        {
            "id": r.id,
            "amount": _fmt_inr(r.amount_inr),
            "frequency": r.frequency,
            "category": cat_map.get(r.category_id, "—") if r.category_id else "—",
            "active": "yes" if r.active else "no",
            "last_gen": str(r.last_generated) if r.last_generated else "—",
        }
        for r in rules
    ]
    tbl = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")
    tbl.add_slot("body-cell-actions", """
        <q-td :props="props">
            <q-btn v-if="props.row.active === 'yes'" size="sm" flat label="Deactivate"
                color="warning" @click="$emit('deactivate', props.row.id)" />
        </q-td>
    """)
    tbl.on("deactivate", lambda e: _deactivate_recurring(e.args, _recurring_rules_view.refresh))


def _deactivate_recurring(rule_id: int, refresh_fn) -> None:
    with session_scope() as session:
        ok = RecurringExpenseService(session).deactivate(rule_id)
    if ok:
        ui.notify(f"Deactivated rule #{rule_id}", type="positive")
        refresh_fn()
    else:
        ui.notify(f"No rule #{rule_id}", type="negative")


def _recurring_add_view() -> None:
    cats = _get_expense_categories()
    cat_options = {"": "No category"} | {str(cid): name for cid, name in cats}

    amount = ui.number("Amount (INR)", format="%.2f").classes("w-40")
    freq_sel = ui.select(
        {f.value: f.value for f in RecurrenceFrequency}, value="MONTHLY", label="Frequency"
    ).classes("w-36")
    cat_sel = ui.select(cat_options, value="", label="Category").classes("w-48")
    day_in = ui.number("Day of month (MONTHLY)", min=1, max=31, format="%d").classes("w-48")
    desc = ui.input("Description").classes("w-64")
    start_in = ui.input("Start from (YYYY-MM-DD, optional)").classes("w-48")

    def submit() -> None:
        try:
            with session_scope() as session:
                cat_id = int(cat_sel.value) if cat_sel.value else None
                RecurringExpenseService(session).add_rule(
                    str(amount.value),
                    RecurrenceFrequency(freq_sel.value),
                    category_id=cat_id,
                    day_of_month=int(day_in.value) if day_in.value else None,
                    description=desc.value or None,
                    start_from=dt.date.fromisoformat(start_in.value) if start_in.value else None,
                )
            ui.notify("Recurring rule created", type="positive")
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Create rule", on_click=submit).props("color=primary")


def _recurring_generate_view() -> None:
    ui.label("Generate due recurring expenses").classes("text-lg font-semibold mb-2")
    as_of_in = ui.input("As-of date (default: today)", value=_TODAY().isoformat()).classes("w-48")

    state: dict = {"created": None}

    @ui.refreshable
    def result_view() -> None:
        created = state["created"]
        if created is None:
            return
        if not created:
            ui.label("Nothing due.").classes("text-gray-500")
            return
        columns = [
            {"name": "date", "label": "Date", "field": "date"},
            {"name": "amount", "label": "Amount", "field": "amount"},
            {"name": "description", "label": "Description", "field": "description"},
        ]
        tbl_rows = [
            {
                "date": str(e.date),
                "amount": _fmt_inr(e.amount_inr),
                "description": e.description or "—",
            }
            for e in created
        ]
        ui.table(columns=columns, rows=tbl_rows).classes("w-full")

    def generate() -> None:
        try:
            with session_scope() as session:
                state["created"] = RecurringExpenseService(session).generate_due_instances(
                    as_of=dt.date.fromisoformat(as_of_in.value) if as_of_in.value else None
                )
            result_view.refresh()
            if state["created"]:
                ui.notify(f"Generated {len(state['created'])} expense(s)", type="positive")
            else:
                ui.notify("Nothing due", type="info")
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Generate", on_click=generate).props("color=primary")
    result_view()


# ---------------------------------------------------------------------------
# Income tab
# ---------------------------------------------------------------------------

def _render_income() -> None:
    with ui.tabs().classes("w-full") as sub_tabs:
        t_list = ui.tab("List")
        t_add = ui.tab("Add")
        t_summary = ui.tab("Summary")

    with ui.tab_panels(sub_tabs, value=t_list).classes("w-full"):
        with ui.tab_panel(t_list):
            _income_list_panel()
        with ui.tab_panel(t_add):
            _income_add_panel()
        with ui.tab_panel(t_summary):
            _income_summary_panel()


@ui.refreshable
def _income_list_panel() -> None:
    start_in = ui.input("Start date (YYYY-MM-DD)").classes("w-40")
    end_in = ui.input("End date (YYYY-MM-DD)").classes("w-40")

    @ui.refreshable
    def income_table() -> None:
        with session_scope() as session:
            try:
                start = dt.date.fromisoformat(start_in.value) if start_in.value else None
                end = dt.date.fromisoformat(end_in.value) if end_in.value else None
            except ValueError:
                ui.notify("Invalid date format", type="negative")
                return
            rows = IncomeService(session).list_income(start=start, end=end)
            cat_map = {c.id: c.name for c in session.exec(select(Category)).all()}

        if not rows:
            ui.label("No income entries found.").classes("text-gray-500")
            return

        columns = [
            {"name": "id", "label": "#", "field": "id"},
            {"name": "date", "label": "Date", "field": "date", "sortable": True},
            {"name": "amount", "label": "Amount", "field": "amount"},
            {"name": "category", "label": "Category", "field": "category"},
            {"name": "source", "label": "Source", "field": "source"},
            {"name": "description", "label": "Description", "field": "description"},
            {"name": "actions", "label": "", "field": "actions"},
        ]
        tbl_rows = [
            {
                "id": r.id,
                "date": str(r.date),
                "amount": _fmt_inr(r.amount_inr),
                "category": cat_map.get(r.category_id, "—") if r.category_id else "—",
                "source": r.source or "—",
                "description": r.description or "—",
            }
            for r in rows
        ]
        tbl = ui.table(columns=columns, rows=tbl_rows, row_key="id").classes("w-full")
        tbl.add_slot("body-cell-actions", """
            <q-td :props="props">
                <q-btn size="sm" flat icon="delete" color="negative"
                    @click="$emit('delete', props.row.id)" />
            </q-td>
        """)
        tbl.on("delete", lambda e: _delete_income(e.args, income_table.refresh))
        ui.label(f"{len(rows)} income entr{'y' if len(rows) == 1 else 'ies'}").classes(
            "text-sm text-gray-500 mt-2"
        )

    ui.button("Search", on_click=income_table.refresh).props("color=primary outline size=sm")
    income_table()


def _delete_income(income_id: int, refresh_fn) -> None:
    with session_scope() as session:
        ok = IncomeService(session).delete_income(income_id)
    if ok:
        ui.notify(f"Deleted income #{income_id}", type="positive")
        refresh_fn()
    else:
        ui.notify(f"No income #{income_id}", type="negative")


def _income_add_panel() -> None:
    ui.label("Add income").classes("text-lg font-semibold mb-2")
    cats = _get_income_categories()
    cat_options = {"": "No category"} | {str(cid): name for cid, name in cats}

    amount = ui.number("Amount (INR)", value=0, format="%.2f").classes("w-40")
    cat_sel = ui.select(cat_options, value="", label="Category").classes("w-48")
    date_in = ui.input("Date", value=_TODAY().isoformat()).classes("w-40")
    source = ui.input("Source (employer/broker/bank)").classes("w-64")
    desc = ui.input("Description").classes("w-64")

    def submit() -> None:
        try:
            with session_scope() as session:
                cat_id = int(cat_sel.value) if cat_sel.value else None
                IncomeService(session).add_income(
                    dt.date.fromisoformat(date_in.value),
                    str(amount.value),
                    category_id=cat_id,
                    source=source.value or None,
                    description=desc.value or None,
                )
            ui.notify("Income added", type="positive")
            amount.value = 0
            source.value = ""
            desc.value = ""
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Add income", on_click=submit).props("color=primary")


def _income_summary_panel() -> None:
    ui.label("Monthly income summary").classes("text-lg font-semibold mb-2")
    today = _TODAY()
    year_in = ui.number("Year", value=today.year, format="%d").classes("w-28")
    month_in = ui.number("Month", value=today.month, min=1, max=12, format="%d").classes("w-20")

    @ui.refreshable
    def summary_view() -> None:
        with session_scope() as session:
            svc = IncomeService(session)
            by_cat = svc.monthly_income_summary(int(year_in.value), int(month_in.value))
            cashflow = svc.net_cashflow(int(year_in.value), int(month_in.value))

        if not by_cat:
            ui.label("No income for this period.").classes("text-gray-500")
        else:
            rows = sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)
            columns = [
                {"name": "category", "label": "Category", "field": "category"},
                {"name": "received", "label": "Received", "field": "received"},
            ]
            tbl_rows = [{"category": name, "received": _fmt_inr(amt)} for name, amt in rows]
            ui.table(columns=columns, rows=tbl_rows).classes("w-full max-w-md")

        net_color = "text-green-600" if cashflow.net_inr >= 0 else "text-red-600"
        ui.label(f"Income: {_fmt_inr(cashflow.income_inr)}").classes("font-bold mt-2")
        ui.label(f"Expenses: {_fmt_inr(cashflow.expenses_inr)}").classes("font-bold")
        ui.label(f"Net cashflow: {_fmt_inr(cashflow.net_inr)}").classes(f"font-bold {net_color}")

    ui.button("Show", on_click=summary_view.refresh).props("color=primary outline size=sm")
    summary_view()


# ---------------------------------------------------------------------------
# Budget tab
# ---------------------------------------------------------------------------

def _render_budget() -> None:
    with ui.tabs().classes("w-full") as sub_tabs:
        t_status = ui.tab("Status")
        t_set = ui.tab("Set budget")

    with ui.tab_panels(sub_tabs, value=t_status).classes("w-full"):
        with ui.tab_panel(t_status):
            _budget_status_panel()
        with ui.tab_panel(t_set):
            _budget_set_panel()


def _budget_status_panel() -> None:
    today = _TODAY()
    year_in = ui.number("Year", value=today.year, format="%d").classes("w-28")
    month_in = ui.number("Month", value=today.month, min=1, max=12, format="%d").classes("w-20")

    @ui.refreshable
    def status_view() -> None:
        with session_scope() as session:
            rows = BudgetService(session).get_budget_status(int(year_in.value), int(month_in.value))

        if not rows:
            ui.label("No budgets set for this month.").classes("text-gray-500")
            return

        columns = [
            {"name": "category", "label": "Category", "field": "category"},
            {"name": "limit", "label": "Limit", "field": "limit"},
            {"name": "spent", "label": "Spent", "field": "spent"},
            {"name": "remaining", "label": "Remaining", "field": "remaining"},
            {"name": "used_pct", "label": "Used %", "field": "used_pct"},
            {"name": "status", "label": "Status", "field": "status"},
        ]
        tbl_rows = [
            {
                "category": s.category_name,
                "limit": _fmt_inr(s.limit_inr),
                "spent": _fmt_inr(s.spent_inr),
                "remaining": _fmt_inr(s.remaining_inr),
                "used_pct": f"{s.pct_used:.0f}%",
                "status": "OVER" if s.is_over else "ok",
            }
            for s in rows
        ]
        tbl = ui.table(columns=columns, rows=tbl_rows).classes("w-full")
        tbl.add_slot("body-cell-status", """
            <q-td :props="props">
                <q-badge :color="props.row.status === 'OVER' ? 'negative' : 'positive'">
                    {{ props.row.status }}
                </q-badge>
            </q-td>
        """)

    ui.button("Show", on_click=status_view.refresh).props("color=primary outline size=sm")
    status_view()


def _budget_set_panel() -> None:
    ui.label("Set monthly budget").classes("text-lg font-semibold mb-2")
    cats = _get_expense_categories()
    if not cats:
        ui.label("No expense categories found. Add categories first.").classes("text-gray-500")
        return

    cat_options = {str(cid): name for cid, name in cats}
    today = _TODAY()

    cat_sel = ui.select(cat_options, value=str(cats[0][0]), label="Category").classes("w-48")
    limit = ui.number("Monthly limit (INR)", value=0, format="%.2f").classes("w-40")
    year_in = ui.number("Year", value=today.year, format="%d").classes("w-28")
    month_in = ui.number("Month", value=today.month, min=1, max=12, format="%d").classes("w-20")

    def submit() -> None:
        try:
            with session_scope() as session:
                BudgetService(session).set_budget(
                    int(cat_sel.value), int(month_in.value), int(year_in.value), str(limit.value)
                )
            ui.notify("Budget set", type="positive")
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Set budget", on_click=submit).props("color=primary")


# ---------------------------------------------------------------------------
# Investments tab
# ---------------------------------------------------------------------------

def _render_investments() -> None:
    with ui.tabs().classes("w-full") as sub_tabs:
        t_holdings = ui.tab("Holdings")
        t_transact = ui.tab("Trade")
        t_add = ui.tab("Add investment")
        t_pnl = ui.tab("P&L / XIRR")
        t_sip = ui.tab("SIP schedules")
        t_analysis = ui.tab("Analysis")

    with ui.tab_panels(sub_tabs, value=t_holdings).classes("w-full"):
        with ui.tab_panel(t_holdings):
            _holdings_panel()
        with ui.tab_panel(t_transact):
            _trade_panel()
        with ui.tab_panel(t_add):
            _add_investment_panel()
        with ui.tab_panel(t_pnl):
            _pnl_xirr_panel()
        with ui.tab_panel(t_sip):
            _sip_panel()
        with ui.tab_panel(t_analysis):
            _analysis_panel()


@ui.refreshable
def _holdings_panel() -> None:
    with ui.row().classes("items-center gap-2 mb-2"):
        ui.label("Holdings").classes("text-lg font-semibold")
        ui.button(
            "Refresh prices",
            on_click=lambda: asyncio.ensure_future(_refresh_prices()),
        ).props("outline size=sm")
        ui.button("Reload", on_click=_holdings_panel.refresh).props("outline size=sm")

    with session_scope() as session:
        rows = PortfolioService(session).get_holdings()

    if not rows:
        ui.label("No holdings yet.").classes("text-gray-500")
        return

    columns = [
        {"name": "symbol", "label": "Symbol", "field": "symbol", "sortable": True},
        {"name": "type", "label": "Type", "field": "type"},
        {"name": "units", "label": "Units", "field": "units"},
        {"name": "invested", "label": "Invested", "field": "invested"},
        {"name": "value", "label": "Value", "field": "value"},
        {"name": "pnl", "label": "P&L", "field": "pnl"},
        {"name": "pnl_pct", "label": "P&L %", "field": "pnl_pct"},
        {"name": "price", "label": "Price", "field": "price"},
    ]
    tbl_rows = [
        {
            "symbol": h.symbol,
            "type": h.asset_type.value,
            "units": f"{h.units:g}",
            "invested": _fmt_inr(h.invested_inr),
            "value": _fmt_inr(h.market_value_inr),
            "pnl": _fmt_inr(h.pnl_abs_inr),
            "pnl_pct": _fmt_pct(h.pnl_pct),
            "price": _fmt_inr(h.current_price_inr) + (" (stale)" if h.price_is_stale else ""),
        }
        for h in rows
    ]
    ui.table(columns=columns, rows=tbl_rows, row_key="symbol").classes("w-full")


def _trade_panel() -> None:
    with ui.tabs().classes("w-full") as trade_tabs:
        t_buy = ui.tab("Buy")
        t_sell = ui.tab("Sell")
        t_sip = ui.tab("SIP")
        t_div = ui.tab("Dividend")
        t_price = ui.tab("Set price")

    with ui.tab_panels(trade_tabs, value=t_buy).classes("w-full"):
        with ui.tab_panel(t_buy):
            _txn_form(TransactionType.BUY)
        with ui.tab_panel(t_sell):
            _txn_form(TransactionType.SELL)
        with ui.tab_panel(t_sip):
            _txn_form(TransactionType.SIP)
        with ui.tab_panel(t_div):
            _txn_form(TransactionType.DIVIDEND)
        with ui.tab_panel(t_price):
            _set_price_form()


def _txn_form(txn_type: TransactionType) -> None:
    invs = _get_investments()
    non_fd = [(iid, sym, at) for iid, sym, at in invs if at != AssetType.FD]
    if not non_fd:
        ui.label("No investments found. Add one first.").classes("text-gray-500")
        return

    inv_options = {str(iid): sym for iid, sym, _ in non_fd}
    inv_sel = ui.select(inv_options, value=str(non_fd[0][0]), label="Investment").classes("w-56")
    units = ui.number("Units", value=0, format="%.4f").classes("w-36")
    price = ui.number("Price (native currency)", value=0, format="%.4f").classes("w-40")
    date_in = ui.input("Date", value=_TODAY().isoformat()).classes("w-40")
    fx = ui.number("FX rate (USD assets)", value=0, format="%.6f").classes("w-40")
    amount_override = ui.number("INR amount override", value=0, format="%.2f").classes("w-40")
    notes = ui.input("Notes").classes("w-64")

    def submit() -> None:
        try:
            with session_scope() as session:
                PortfolioService(session).add_transaction(
                    int(inv_sel.value),
                    dt.date.fromisoformat(date_in.value),
                    txn_type,
                    str(units.value),
                    str(price.value),
                    fx_rate_used=str(fx.value) if fx.value else None,
                    amount_inr=str(amount_override.value) if amount_override.value else None,
                    notes=notes.value or None,
                )
            ui.notify(f"{txn_type.value} recorded", type="positive")
            units.value = 0
            price.value = 0
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button(f"Record {txn_type.value}", on_click=submit).props("color=primary")


def _set_price_form() -> None:
    ui.label("Manually set INR price for a holding").classes("text-lg font-semibold mb-2")
    invs = _get_investments()
    if not invs:
        ui.label("No investments found.").classes("text-gray-500")
        return

    inv_options = {str(iid): sym for iid, sym, _ in invs}
    inv_sel = ui.select(inv_options, value=str(invs[0][0]), label="Investment").classes("w-56")
    price = ui.number("Price (INR)", value=0, format="%.4f").classes("w-40")

    def submit() -> None:
        try:
            with session_scope() as session:
                FetcherService(session).set_manual_price(int(inv_sel.value), str(price.value))
            ui.notify("Price set", type="positive")
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Set price", on_click=submit).props("color=primary")


def _add_investment_panel() -> None:
    with ui.tabs().classes("w-full") as add_tabs:
        t_stock = ui.tab("Stock / MF / ETF")
        t_fd = ui.tab("Fixed Deposit")

    with ui.tab_panels(add_tabs, value=t_stock).classes("w-full"):
        with ui.tab_panel(t_stock):
            _add_stock_form()
        with ui.tab_panel(t_fd):
            _add_fd_form()


def _add_stock_form() -> None:
    ui.label("Register investment").classes("text-lg font-semibold mb-2")
    non_fd_types = [t for t in AssetType if t not in (AssetType.FD, AssetType.BENCHMARK)]
    type_options = {t.value: t.value for t in non_fd_types}

    symbol = ui.input("Symbol (e.g. INFY.NS, AAPL, 120503)").classes("w-56")
    name = ui.input("Display name").classes("w-64")
    type_sel = ui.select(type_options, value="STOCK_IN", label="Asset type").classes("w-40")
    currency = ui.input("Currency", value="INR").classes("w-24")
    exchange = ui.input("Exchange (optional)").classes("w-40")
    sector = ui.input("Sector (optional, e.g. IT, Banking)").classes("w-40")

    def submit() -> None:
        try:
            with session_scope() as session:
                inv = PortfolioService(session).add_investment(
                    symbol.value, name.value, AssetType(type_sel.value),
                    currency_native=currency.value, exchange=exchange.value or None,
                )
                if sector.value:
                    PortfolioService(session).set_sector(inv.id, sector.value)
            ui.notify(f"Added {symbol.value}", type="positive")
            symbol.value = ""
            name.value = ""
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Add investment", on_click=submit).props("color=primary")


def _add_fd_form() -> None:
    ui.label("Register fixed deposit").classes("text-lg font-semibold mb-2")
    comp_options = {f.value: f.value for f in CompoundingFrequency}

    name = ui.input("FD name/label").classes("w-64")
    principal = ui.number("Principal (INR)", value=0, format="%.2f").classes("w-40")
    rate = ui.number("Annual rate (%)", value=7.0, format="%.2f").classes("w-32")
    start_in = ui.input("Start date (YYYY-MM-DD)").classes("w-40")
    maturity_in = ui.input("Maturity date (YYYY-MM-DD)").classes("w-40")
    comp_sel = ui.select(comp_options, value="QUARTERLY", label="Compounding").classes("w-40")

    def submit() -> None:
        try:
            with session_scope() as session:
                PortfolioService(session).add_fd(
                    name.value, str(principal.value), str(rate.value),
                    dt.date.fromisoformat(start_in.value),
                    dt.date.fromisoformat(maturity_in.value),
                    compounding=CompoundingFrequency(comp_sel.value),
                )
            ui.notify(f"Added FD: {name.value}", type="positive")
            name.value = ""
            principal.value = 0
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Add FD", on_click=submit).props("color=primary")


def _pnl_xirr_panel() -> None:
    invs = _get_investments()
    inv_options = {"": "Portfolio (all)"} | {str(iid): sym for iid, sym, _ in invs}

    inv_sel = ui.select(
        inv_options, value="", label="Investment (blank = portfolio)"
    ).classes("w-56")

    @ui.refreshable
    def pnl_view() -> None:
        with session_scope() as session:
            svc = PortfolioService(session)
            inv_id = int(inv_sel.value) if inv_sel.value else None
            pnl = svc.get_pnl(investment_id=inv_id)
            xirr = svc.calculate_xirr(investment_id=inv_id)
            label = inv_options.get(inv_sel.value, "Portfolio") if inv_sel.value else "Portfolio"

            # check if FD for annotation
            is_fd = False
            if inv_id:
                inv = session.get(Investment, inv_id)
                is_fd = inv is not None and inv.asset_type == AssetType.FD

        ui.label(f"P&L — {label}").classes("text-lg font-semibold mt-2")
        with ui.row().classes("gap-4 flex-wrap"):
            _summary_card("Invested", _fmt_inr(pnl.invested_inr), "secondary")
            _summary_card("Market value", _fmt_inr(pnl.market_value_inr), "primary")
            pnl_color = "positive" if pnl.pnl_abs_inr >= 0 else "negative"
            _summary_card("P&L", _fmt_inr(pnl.pnl_abs_inr), pnl_color)
            _summary_card("P&L %", _fmt_pct(pnl.pnl_pct), pnl_color)

        if xirr is not None:
            xi_color = "positive" if xirr >= 0 else "negative"
            ui.label(f"XIRR: {xirr * Decimal(100):+.2f}%").classes(
                f"text-xl font-bold mt-2 text-{'green' if xi_color == 'positive' else 'red'}-600"
            )
        else:
            ui.label("XIRR: — (insufficient data)").classes("text-gray-500 mt-2")

        if is_fd:
            ui.label("FD XIRR is analytical (from rate/compounding), not market-derived.").classes(
                "text-xs text-gray-400"
            )

    ui.button("Calculate", on_click=pnl_view.refresh).props("color=primary outline size=sm")
    pnl_view()


def _sip_panel() -> None:
    with ui.tabs().classes("w-full") as sip_tabs:
        t_pending = ui.tab("Pending SIPs")
        t_schedules = ui.tab("Schedules")
        t_add = ui.tab("Add schedule")

    with ui.tab_panels(sip_tabs, value=t_pending).classes("w-full"):
        with ui.tab_panel(t_pending):
            _sip_pending_view()
        with ui.tab_panel(t_schedules):
            _sip_schedules_view()
        with ui.tab_panel(t_add):
            _sip_add_schedule_view()


@ui.refreshable
def _sip_pending_view() -> None:
    with session_scope() as session:
        pending = SIPService(session).get_pending_sips()

    if not pending:
        ui.label("No pending SIP instalments. 🎉").classes("text-green-600")
        return

    columns = [
        {"name": "due_date", "label": "Due", "field": "due_date"},
        {"name": "symbol", "label": "Symbol", "field": "symbol"},
        {"name": "amount", "label": "Amount", "field": "amount"},
    ]
    tbl_rows = [
        {"due_date": str(p.due_date), "symbol": p.symbol, "amount": _fmt_inr(p.amount_inr)}
        for p in pending
    ]
    ui.table(columns=columns, rows=tbl_rows).classes("w-full max-w-md")
    ui.label(f"{len(pending)} instalment(s) pending").classes("text-yellow-600 font-semibold mt-2")


@ui.refreshable
def _sip_schedules_view() -> None:
    with session_scope() as session:
        schedules = SIPService(session).list_schedules(include_inactive=True)
        inv_map = {
            i.id: i.symbol
            for i in session.exec(select(Investment)).all()
        }

    if not schedules:
        ui.label("No SIP schedules.").classes("text-gray-500")
        return

    columns = [
        {"name": "id", "label": "#", "field": "id"},
        {"name": "symbol", "label": "Symbol", "field": "symbol"},
        {"name": "amount", "label": "Amount", "field": "amount"},
        {"name": "day", "label": "Day", "field": "day"},
        {"name": "start", "label": "Start", "field": "start"},
        {"name": "end", "label": "End", "field": "end"},
        {"name": "active", "label": "Active", "field": "active"},
        {"name": "actions", "label": "", "field": "actions"},
    ]
    tbl_rows = [
        {
            "id": s.id,
            "symbol": inv_map.get(s.investment_id, str(s.investment_id)),
            "amount": _fmt_inr(s.amount_inr),
            "day": s.day_of_month,
            "start": str(s.start_date),
            "end": str(s.end_date) if s.end_date else "—",
            "active": "yes" if s.active else "no",
        }
        for s in schedules
    ]
    tbl = ui.table(columns=columns, rows=tbl_rows, row_key="id").classes("w-full")
    tbl.add_slot("body-cell-actions", """
        <q-td :props="props">
            <q-btn v-if="props.row.active === 'yes'" size="sm" flat label="Deactivate"
                color="warning" @click="$emit('deactivate', props.row.id)" />
        </q-td>
    """)
    tbl.on("deactivate", lambda e: _deactivate_sip(e.args, _sip_schedules_view.refresh))


def _deactivate_sip(schedule_id: int, refresh_fn) -> None:
    with session_scope() as session:
        ok = SIPService(session).deactivate(schedule_id)
    if ok:
        ui.notify(f"Deactivated schedule #{schedule_id}", type="positive")
        refresh_fn()
    else:
        ui.notify(f"No schedule #{schedule_id}", type="negative")


def _sip_add_schedule_view() -> None:
    invs = [(iid, sym) for iid, sym, at in _get_investments() if at == AssetType.MF]
    if not invs:
        ui.label("No mutual fund investments found. Add one first.").classes("text-gray-500")
        return

    inv_options = {str(iid): sym for iid, sym in invs}
    inv_sel = ui.select(inv_options, value=str(invs[0][0]), label="Investment (MF)").classes("w-56")
    amount = ui.number("Monthly amount (INR)", value=0, format="%.2f").classes("w-40")
    day = ui.number("Day of month (1-31)", value=1, min=1, max=31, format="%d").classes("w-36")
    start_in = ui.input("Start month (YYYY-MM-DD)").classes("w-40")
    end_in = ui.input("End month (YYYY-MM-DD, optional)").classes("w-40")

    def submit() -> None:
        try:
            with session_scope() as session:
                SIPService(session).add_schedule(
                    int(inv_sel.value), str(amount.value), int(day.value),
                    dt.date.fromisoformat(start_in.value),
                    end_date=dt.date.fromisoformat(end_in.value) if end_in.value else None,
                )
            ui.notify("SIP schedule created", type="positive")
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Add schedule", on_click=submit).props("color=primary")


def _analysis_panel() -> None:
    with ui.tabs().classes("w-full") as analysis_tabs:
        t_concentration = ui.tab("Concentration")
        t_dividends = ui.tab("Dividends")
        t_tax = ui.tab("Tax report")
        t_benchmark = ui.tab("Benchmark")

    with ui.tab_panels(analysis_tabs, value=t_concentration).classes("w-full"):
        with ui.tab_panel(t_concentration):
            _concentration_view()
        with ui.tab_panel(t_dividends):
            _dividends_view()
        with ui.tab_panel(t_tax):
            _tax_report_view()
        with ui.tab_panel(t_benchmark):
            _benchmark_view()


@ui.refreshable
def _concentration_view() -> None:
    top_n = ui.number("Top N holdings", value=10, min=1, max=50, format="%d").classes("w-28")
    threshold = ui.number("Concentration threshold %", value=10.0, format="%.1f").classes("w-40")

    @ui.refreshable
    def conc_result() -> None:
        with session_scope() as session:
            report = ConcentrationService(session).concentration_report(
                top_n=int(top_n.value), threshold_pct=str(threshold.value)
            )

        if report.total_value_inr <= 0:
            ui.label("No holdings to analyse.").classes("text-gray-500")
            return

        ui.label(f"Total portfolio: {_fmt_inr(report.total_value_inr)}").classes("font-semibold")

        cols = [
            {"name": "symbol", "label": "Symbol", "field": "symbol"},
            {"name": "name", "label": "Name", "field": "name"},
            {"name": "value", "label": "Value", "field": "value"},
            {"name": "weight", "label": "Weight", "field": "weight"},
            {"name": "flag", "label": "", "field": "flag"},
        ]
        rows = [
            {
                "symbol": r.symbol, "name": r.name,
                "value": _fmt_inr(r.market_value_inr),
                "weight": f"{r.pct_of_total:.2f}%",
                "flag": "⚠ HIGH" if r.is_concentrated else "",
            }
            for r in report.top_holdings
        ]
        ui.label(f"Top {int(top_n.value)} holdings").classes("text-lg font-semibold mt-2")
        ui.table(columns=cols, rows=rows, row_key="symbol").classes("w-full")

        for title, weight_rows in (
            ("By sector", report.by_sector),
            ("By asset class", report.by_asset_class),
        ):
            if weight_rows:
                ui.label(title).classes("text-lg font-semibold mt-4")
                w_cols = [
                    {"name": "label", "label": "Category", "field": "label"},
                    {"name": "value", "label": "Value", "field": "value"},
                    {"name": "weight", "label": "Weight", "field": "weight"},
                ]
                w_rows = [
                    {
                        "label": w.label,
                        "value": _fmt_inr(w.market_value_inr),
                        "weight": f"{w.pct_of_total:.2f}%",
                    }
                    for w in weight_rows
                ]
                ui.table(columns=w_cols, rows=w_rows).classes("w-full max-w-md")

    ui.button("Analyse", on_click=conc_result.refresh).props("color=primary outline size=sm")
    conc_result()


@ui.refreshable
def _dividends_view() -> None:
    year_filter = ui.number("Year (blank = all time)", value=0, format="%d").classes("w-36")

    @ui.refreshable
    def div_result() -> None:
        with session_scope() as session:
            svc = DividendService(session)
            year = int(year_filter.value) if year_filter.value else None
            rows = svc.total_by_holding(year=year)
            by_year = svc.total_by_year() if not year else {}

        if not rows:
            ui.label("No dividends recorded.").classes("text-gray-500")
            return

        cols = [
            {"name": "symbol", "label": "Symbol", "field": "symbol"},
            {"name": "name", "label": "Name", "field": "name"},
            {"name": "total", "label": "Total", "field": "total"},
            {"name": "yield", "label": "TTM Yield", "field": "yield"},
        ]
        tbl_rows = [
            {
                "symbol": r.symbol, "name": r.name,
                "total": _fmt_inr(r.total_inr),
                "yield": (
                    f"{r.trailing_yield_pct:.2f}%"
                    if r.trailing_yield_pct is not None else "—"
                ),
            }
            for r in rows
        ]
        ui.table(columns=cols, rows=tbl_rows, row_key="symbol").classes("w-full")

        if by_year:
            ui.label("By year").classes("text-lg font-semibold mt-4")
            y_cols = [
                {"name": "year", "label": "Year", "field": "year"},
                {"name": "total", "label": "Received", "field": "total"},
            ]
            y_rows = [{"year": y, "total": _fmt_inr(amt)} for y, amt in sorted(by_year.items())]
            ui.table(columns=y_cols, rows=y_rows).classes("w-full max-w-xs")

    ui.button("Show", on_click=div_result.refresh).props("color=primary outline size=sm")
    div_result()


def _tax_report_view() -> None:
    ui.label("FIFO capital-gains report").classes("text-lg font-semibold mb-2")
    current_year = _TODAY().year
    fy_in = ui.input(
        "Financial year (e.g. 2025-26)",
        value=f"{current_year - 1}-{str(current_year)[2:]}",
    ).classes("w-40")

    state: dict = {"report": None}

    @ui.refreshable
    def tax_result() -> None:
        report = state["report"]
        if report is None:
            return
        cols = [
            {"name": "symbol", "label": "Symbol", "field": "symbol"},
            {"name": "buy", "label": "Buy date", "field": "buy"},
            {"name": "sell", "label": "Sell date", "field": "sell"},
            {"name": "units", "label": "Units", "field": "units"},
            {"name": "cost", "label": "Cost", "field": "cost"},
            {"name": "proceeds", "label": "Proceeds", "field": "proceeds"},
            {"name": "gain", "label": "Gain", "field": "gain"},
            {"name": "term", "label": "Term", "field": "term"},
        ]
        rows = [
            {
                "symbol": r.symbol,
                "buy": str(r.buy_date), "sell": str(r.sell_date),
                "units": f"{r.units:g}",
                "cost": _fmt_inr(r.cost_basis_inr),
                "proceeds": _fmt_inr(r.proceeds_inr),
                "gain": _fmt_inr(r.gain_inr),
                "term": "LTCG" if r.is_long_term else "STCG",
            }
            for r in report.rows
        ]
        if rows:
            ui.table(columns=cols, rows=rows).classes("w-full")
        else:
            ui.label("No realised gains for this FY.").classes("text-gray-500")

        with ui.row().classes("gap-4 flex-wrap mt-2"):
            _summary_card("STCG", _fmt_inr(report.short_term_gain_inr), "warning")
            _summary_card("LTCG", _fmt_inr(report.long_term_gain_inr), "primary")
            _summary_card("Taxable LTCG", _fmt_inr(report.taxable_ltcg_inr), "negative")
            _summary_card("Est. STCG tax", _fmt_inr(report.estimated_stcg_tax_inr), "negative")
            _summary_card("Est. LTCG tax", _fmt_inr(report.estimated_ltcg_tax_inr), "negative")

        ui.label(
            "Informational only — not tax advice. Post-Jul-2024 equity rates; "
            "gold/debt and grandfathering excluded. Verify with a CA."
        ).classes("text-xs text-gray-400 mt-2")

    def run_report() -> None:
        try:
            with session_scope() as session:
                state["report"] = TaxService(session).capital_gains_report(fy_in.value)
            tax_result.refresh()
        except ValueError as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Run report", on_click=run_report).props("color=primary")
    tax_result()


def _benchmark_view() -> None:
    with ui.tabs().classes("w-full") as bench_tabs:
        t_compare = ui.tab("Compare")
        t_record = ui.tab("Record price")

    with ui.tab_panels(bench_tabs, value=t_compare).classes("w-full"):
        with ui.tab_panel(t_compare):
            _benchmark_compare_view()
        with ui.tab_panel(t_record):
            _benchmark_record_view()


def _benchmark_compare_view() -> None:
    start_in = ui.input("Start date (YYYY-MM-DD)").classes("w-40")
    end_in = ui.input("End date (YYYY-MM-DD, default today)").classes("w-40")

    state: dict = {"result": None}

    @ui.refreshable
    def bench_result() -> None:
        result = state["result"]
        if result is None:
            return
        xirr_str = (
            f"{result.portfolio_xirr_pct:.2f}%" if result.portfolio_xirr_pct is not None else "—"
        )
        ui.label(
            f"Portfolio XIRR ({result.start_date} → {result.end_date}): {xirr_str}"
        ).classes("font-semibold mt-2")
        if not result.benchmarks:
            ui.label("No benchmark snapshots in range.").classes("text-gray-500")
            return
        cols = [
            {"name": "index", "label": "Index", "field": "index"},
            {"name": "from_d", "label": "From", "field": "from_d"},
            {"name": "to_d", "label": "To", "field": "to_d"},
            {"name": "total", "label": "Total return", "field": "total"},
            {"name": "cagr", "label": "CAGR", "field": "cagr"},
        ]
        rows = [
            {
                "index": b.display_name,
                "from_d": str(b.start_date), "to_d": str(b.end_date),
                "total": f"{b.total_return_pct:.2f}%",
                "cagr": f"{b.cagr_pct:.2f}%" if b.cagr_pct is not None else "—",
            }
            for b in result.benchmarks
        ]
        ui.table(columns=cols, rows=rows).classes("w-full")

    def run() -> None:
        try:
            with session_scope() as session:
                state["result"] = BenchmarkService(session).compare(
                    dt.date.fromisoformat(start_in.value),
                    dt.date.fromisoformat(end_in.value) if end_in.value else _TODAY(),
                )
            bench_result.refresh()
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Compare", on_click=run).props("color=primary")
    bench_result()


def _benchmark_record_view() -> None:
    ui.label("Record benchmark price snapshot").classes("text-lg font-semibold mb-2")
    from wealthlog.constants import BENCHMARKS
    bench_options = {name: f"{name} — {info[0]}" for name, info in BENCHMARKS.items()}

    bench_sel = ui.select(bench_options, value="NIFTY50", label="Benchmark").classes("w-56")
    price = ui.number("Index level / price (INR)", value=0, format="%.2f").classes("w-40")
    date_in = ui.input("Date", value=_TODAY().isoformat()).classes("w-40")

    def submit() -> None:
        try:
            with session_scope() as session:
                BenchmarkService(session).record_price(
                    bench_sel.value, dt.date.fromisoformat(date_in.value), str(price.value)
                )
            ui.notify(f"Recorded {bench_sel.value} = {price.value}", type="positive")
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Record", on_click=submit).props("color=primary")


# ---------------------------------------------------------------------------
# Net worth tab
# ---------------------------------------------------------------------------

def _render_networth() -> None:
    with ui.tabs().classes("w-full") as sub_tabs:
        t_now = ui.tab("Current")
        t_history = ui.tab("History")

    with ui.tab_panels(sub_tabs, value=t_now).classes("w-full"):
        with ui.tab_panel(t_now):
            _networth_current_view()
        with ui.tab_panel(t_history):
            _networth_history_view()


@ui.refreshable
def _networth_current_view() -> None:
    with session_scope() as session:
        nw = NetWorthService(session).calculate_net_worth()

    with ui.row().classes("gap-4 flex-wrap"):
        _summary_card("Total assets", _fmt_inr(nw.total_assets_inr), "primary")
        _summary_card("Total liabilities", _fmt_inr(nw.total_liabilities_inr), "warning")
        _summary_card("Net worth", _fmt_inr(nw.net_worth_inr), "positive")

    ui.label(f"As of {nw.as_of}").classes("text-sm text-gray-500 mt-2")

    if nw.by_asset_class:
        ui.label("By asset class").classes("text-lg font-semibold mt-4")
        cols = [
            {"name": "type", "label": "Asset class", "field": "type"},
            {"name": "value", "label": "Value", "field": "value"},
            {"name": "share", "label": "Share", "field": "share"},
        ]
        rows = [
            {
                "type": c.asset_type.value,
                "value": _fmt_inr(c.market_value_inr),
                "share": f"{c.pct_of_total:.1f}%",
            }
            for c in nw.by_asset_class
        ]
        ui.table(columns=cols, rows=rows).classes("w-full max-w-lg")


def _networth_history_view() -> None:
    start_in = ui.input("Start date (YYYY-MM-DD)").classes("w-40")
    end_in = ui.input("End date (YYYY-MM-DD)").classes("w-40")
    mode_sel = ui.select({"cost": "Cost basis", "market": "Market value"}, value="cost",
                         label="Mode").classes("w-40")

    @ui.refreshable
    def history_view() -> None:
        try:
            start = dt.date.fromisoformat(start_in.value)
            end = dt.date.fromisoformat(end_in.value) if end_in.value else _TODAY()
        except ValueError:
            ui.notify("Invalid date format", type="negative")
            return

        with session_scope() as session:
            try:
                points = NetWorthService(session).historical_net_worth(
                    start, end, mode=mode_sel.value
                )
            except ValueError as exc:
                ui.notify(str(exc), type="negative")
                return

        if not points:
            ui.label("No data for this range.").classes("text-gray-500")
            return

        labels = [f"{p.year}-{p.month:02d}" for p in points]
        invested = [float(p.invested_inr) for p in points]
        market = [
            float(p.market_value_inr) if p.market_value_inr is not None else float(p.invested_inr)
            for p in points
        ]

        ui.echart(_history_chart_options(labels, invested, market)).classes("h-72 w-full")

        cols = [
            {"name": "month", "label": "Month", "field": "month"},
            {"name": "invested", "label": "Invested", "field": "invested"},
            {"name": "value", "label": "Market value", "field": "value"},
        ]
        rows = [
            {
                "month": f"{p.year}-{p.month:02d}",
                "invested": _fmt_inr(p.invested_inr),
                "value": _fmt_inr(p.market_value_inr) if p.market_value_inr else "—",
            }
            for p in points
        ]
        ui.table(columns=cols, rows=rows).classes("w-full")
        if mode_sel.value == "cost":
            ui.label(
                "Cost-basis series (net cash deployed), not market value. "
                "Use 'market' mode once price snapshots exist."
            ).classes("text-xs text-gray-400 mt-1")

    ui.button("Show history", on_click=history_view.refresh).props("color=primary outline size=sm")
    history_view()


# ---------------------------------------------------------------------------
# Liabilities tab
# ---------------------------------------------------------------------------

def _render_liabilities() -> None:
    with ui.tabs().classes("w-full") as sub_tabs:
        t_list = ui.tab("List")
        t_add = ui.tab("Add")

    with ui.tab_panels(sub_tabs, value=t_list).classes("w-full"):
        with ui.tab_panel(t_list):
            _liabilities_list_panel()
        with ui.tab_panel(t_add):
            _liability_add_panel()


@ui.refreshable
def _liabilities_list_panel() -> None:
    with session_scope() as session:
        svc = LiabilityService(session)
        rows = svc.list_liabilities()
        total = svc.total_liabilities()

    if not rows:
        ui.label("No liabilities recorded.").classes("text-gray-500")
    else:
        cols = [
            {"name": "id", "label": "#", "field": "id"},
            {"name": "name", "label": "Name", "field": "name"},
            {"name": "amount", "label": "Amount", "field": "amount"},
            {"name": "category", "label": "Category", "field": "category"},
            {"name": "due", "label": "Due", "field": "due"},
            {"name": "notes", "label": "Notes", "field": "notes"},
            {"name": "actions", "label": "", "field": "actions"},
        ]
        tbl_rows = [
            {
                "id": r.id, "name": r.name,
                "amount": _fmt_inr(r.amount_inr),
                "category": str(r.category),
                "due": str(r.due_date) if r.due_date else "—",
                "notes": r.notes or "—",
            }
            for r in rows
        ]
        tbl = ui.table(columns=cols, rows=tbl_rows, row_key="id").classes("w-full")
        tbl.add_slot("body-cell-actions", """
            <q-td :props="props">
                <q-btn size="sm" flat icon="edit" color="primary"
                    @click="$emit('edit', props.row)" />
                <q-btn size="sm" flat icon="delete" color="negative"
                    @click="$emit('delete', props.row.id)" />
            </q-td>
        """)
        tbl.on("delete", lambda e: _delete_liability(e.args, _liabilities_list_panel.refresh))
        tbl.on("edit", lambda e: _edit_liability_dialog(e.args, _liabilities_list_panel.refresh))

        ui.label(f"Total liabilities: {_fmt_inr(total)}").classes("font-bold mt-2")


def _delete_liability(liability_id: int, refresh_fn) -> None:
    with session_scope() as session:
        ok = LiabilityService(session).delete_liability(liability_id)
    if ok:
        ui.notify(f"Deleted liability #{liability_id}", type="positive")
        refresh_fn()
    else:
        ui.notify(f"No liability #{liability_id}", type="negative")


def _edit_liability_dialog(row: dict, refresh_fn) -> None:
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Update liability: {row['name']}").classes("text-lg font-semibold")
        new_amount = ui.number("New amount (INR)", value=0, format="%.2f").classes("w-40")

        def save() -> None:
            try:
                with session_scope() as session:
                    LiabilityService(session).update_amount(row["id"], str(new_amount.value))
                ui.notify("Updated", type="positive")
                dialog.close()
                refresh_fn()
            except (ValueError, TypeError) as exc:
                ui.notify(f"Error: {exc}", type="negative")

        with ui.row():
            ui.button("Save", on_click=save).props("color=primary")
            ui.button("Cancel", on_click=dialog.close).props("flat")

    dialog.open()


def _liability_add_panel() -> None:
    ui.label("Add liability").classes("text-lg font-semibold mb-2")
    cat_options = {c.value: c.value for c in LiabilityCategory}

    name = ui.input("Name (e.g. Home loan)").classes("w-64")
    amount = ui.number("Outstanding amount (INR)", value=0, format="%.2f").classes("w-40")
    cat_sel = ui.select(cat_options, value="OTHER", label="Category").classes("w-36")
    due_in = ui.input("Due date (YYYY-MM-DD, optional)").classes("w-40")
    notes = ui.input("Notes").classes("w-64")

    def submit() -> None:
        try:
            with session_scope() as session:
                LiabilityService(session).add_liability(
                    name.value, str(amount.value),
                    category=LiabilityCategory(cat_sel.value),
                    due_date=dt.date.fromisoformat(due_in.value) if due_in.value else None,
                    notes=notes.value or None,
                )
            ui.notify("Liability added", type="positive")
            name.value = ""
            amount.value = 0
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Add liability", on_click=submit).props("color=primary")


# ---------------------------------------------------------------------------
# Import / Export tab
# ---------------------------------------------------------------------------

def _render_data() -> None:
    with ui.tabs().classes("w-full") as sub_tabs:
        t_export = ui.tab("Export")
        t_import = ui.tab("Import")

    with ui.tab_panels(sub_tabs, value=t_export).classes("w-full"):
        with ui.tab_panel(t_export):
            _export_panel()
        with ui.tab_panel(t_import):
            _import_panel()


def _export_panel() -> None:
    ui.label("Export data").classes("text-lg font-semibold mb-2")

    with ui.card().classes("w-full max-w-lg mb-4"):
        ui.label("CSV export").classes("font-semibold")
        kind_sel = ui.select(
            {k: k for k in CSV_KINDS}, value="expenses", label="Export type"
        ).classes("w-40")
        out_path = ui.input("Output path", value=str(Path.home() / "wealthlog_export.csv")).classes(
            "w-full"
        )

        def do_csv() -> None:
            try:
                with session_scope() as session:
                    out = ExportService(session).export_csv(kind_sel.value, out_path.value)
                ui.notify(f"Exported to {out}", type="positive")
            except (ValueError, OSError) as exc:
                ui.notify(f"Error: {exc}", type="negative")

        ui.button("Export CSV", on_click=do_csv).props("color=primary")

    with ui.card().classes("w-full max-w-lg"):
        ui.label("PDF report").classes("font-semibold")
        pdf_path = ui.input("Output path", value=str(Path.home() / "wealthlog_report.pdf")).classes(
            "w-full"
        )

        def do_pdf() -> None:
            try:
                with session_scope() as session:
                    out = ExportService(session).export_pdf_report(pdf_path.value)
                ui.notify(f"PDF written to {out}", type="positive")
            except (ValueError, OSError) as exc:
                ui.notify(f"Error: {exc}", type="negative")

        ui.button("Export PDF", on_click=do_pdf).props("color=primary")


def _import_panel() -> None:
    ui.label("Import broker statement").classes("text-lg font-semibold mb-2")
    ui.label(
        "Upload a CSV/XLSX broker statement. Use dry run first to preview."
    ).classes("text-sm text-gray-500 mb-2")

    broker_sel = ui.select({"zerodha": "Zerodha", "generic": "Generic CSV"}, value="zerodha",
                           label="Broker").classes("w-40")
    commit_toggle = ui.checkbox("Commit (write to database)", value=False)

    import_state: dict = {"preview": None, "committed": None}

    @ui.refreshable
    def import_result() -> None:
        preview = import_state["preview"]
        committed = import_state["committed"]
        if preview is not None:
            cols = [
                {"name": "date", "label": "Date", "field": "date"},
                {"name": "symbol", "label": "Symbol", "field": "symbol"},
                {"name": "type", "label": "Type", "field": "type"},
                {"name": "units", "label": "Units", "field": "units"},
                {"name": "price", "label": "Price", "field": "price"},
                {"name": "status", "label": "Status", "field": "status"},
            ]
            rows = [
                {
                    "date": str(r.txn.date), "symbol": r.txn.symbol,
                    "type": str(r.txn.type), "units": f"{r.txn.units:g}",
                    "price": _fmt_inr(r.txn.price),
                    "status": (
                        "duplicate" if r.is_duplicate
                        else ("new +inv" if r.creates_investment else "new")
                    ),
                }
                for r in preview.rows
            ]
            ui.table(columns=cols, rows=rows).classes("w-full")
            ui.label(
                f"{preview.new_count} new, {preview.duplicate_count} duplicate. "
                "Check 'Commit' and re-upload to import."
            ).classes("font-semibold mt-2")
        elif committed is not None:
            ui.label(
                f"Imported {committed.imported}, "
                f"skipped {committed.skipped_duplicates} duplicate(s)."
            ).classes("text-green-600 font-semibold")
            if committed.created_investments:
                ui.label(
                    f"Created investments: {', '.join(committed.created_investments)}"
                ).classes("text-sm text-gray-500")

    async def handle_upload(e) -> None:
        import_state["preview"] = None
        import_state["committed"] = None
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(e.name).suffix) as tmp:
            tmp.write(e.content.read())
            tmp_path = tmp.name
        try:
            with session_scope() as session:
                svc = ImportService(session)
                if not commit_toggle.value:
                    import_state["preview"] = svc.preview(tmp_path, broker_sel.value)
                else:
                    import_state["committed"] = svc.commit(tmp_path, broker_sel.value)
            import_result.refresh()
            if import_state["committed"]:
                ui.notify(
                    f"Imported {import_state['committed'].imported} transaction(s)",
                    type="positive",
                )
        except (ValueError, KeyError, FileNotFoundError) as exc:
            ui.notify(f"Import failed: {exc}", type="negative")
        finally:
            os.unlink(tmp_path)

    ui.upload(on_upload=handle_upload, label="Drop file here").props(
        "accept='.csv,.xlsx'"
    ).classes("w-full")
    import_result()


# ---------------------------------------------------------------------------
# Alerts tab
# ---------------------------------------------------------------------------

def _render_alerts() -> None:
    with ui.tabs().classes("w-full") as sub_tabs:
        t_rules = ui.tab("Rules")
        t_add = ui.tab("Add rule")
        t_check = ui.tab("Check now")

    with ui.tab_panels(sub_tabs, value=t_rules).classes("w-full"):
        with ui.tab_panel(t_rules):
            _alert_rules_view()
        with ui.tab_panel(t_add):
            _alert_add_view()
        with ui.tab_panel(t_check):
            _alert_check_view()


@ui.refreshable
def _alert_rules_view() -> None:
    with session_scope() as session:
        svc = AlertService(session)
        rules = svc.list_rules(include_inactive=True)
        descriptions = {r.id: svc.describe_rule(r) for r in rules}

    if not rules:
        ui.label("No alert rules.").classes("text-gray-500")
        return

    cols = [
        {"name": "id", "label": "#", "field": "id"},
        {"name": "kind", "label": "Kind", "field": "kind"},
        {"name": "threshold", "label": "Threshold", "field": "threshold"},
        {"name": "target", "label": "Target", "field": "target"},
        {"name": "active", "label": "Active", "field": "active"},
        {"name": "actions", "label": "", "field": "actions"},
    ]
    rows = [
        {
            "id": r.id,
            "kind": r.kind,
            "threshold": str(r.threshold) if r.threshold else "—",
            "target": descriptions[r.id],
            "active": "yes" if r.active else "no",
        }
        for r in rules
    ]
    tbl = ui.table(columns=cols, rows=rows, row_key="id").classes("w-full")
    tbl.add_slot("body-cell-actions", """
        <q-td :props="props">
            <q-btn v-if="props.row.active === 'yes'" size="sm" flat label="Deactivate"
                color="warning" @click="$emit('deactivate', props.row.id)" />
        </q-td>
    """)
    tbl.on("deactivate", lambda e: _deactivate_alert(e.args, _alert_rules_view.refresh))


def _deactivate_alert(rule_id: int, refresh_fn) -> None:
    with session_scope() as session:
        ok = AlertService(session).deactivate(rule_id)
    if ok:
        ui.notify(f"Deactivated rule #{rule_id}", type="positive")
        refresh_fn()
    else:
        ui.notify(f"No rule #{rule_id}", type="negative")


def _alert_add_view() -> None:
    kind_options = {k.value: k.value for k in AlertKind}
    invs = _get_investments()
    inv_options = {"": "Any"} | {str(iid): sym for iid, sym, _ in invs}
    cats = _get_expense_categories()
    cat_options = {"": "Any"} | {str(cid): name for cid, name in cats}

    kind_sel = ui.select(kind_options, value="PRICE_DROP", label="Kind").classes("w-40")
    threshold = ui.number("Threshold %", value=10.0, format="%.1f").classes("w-32")
    inv_sel = ui.select(inv_options, value="", label="Investment (optional)").classes("w-48")
    cat_sel = ui.select(cat_options, value="", label="Category (optional)").classes("w-48")

    def submit() -> None:
        try:
            with session_scope() as session:
                AlertService(session).add_rule(
                    AlertKind(kind_sel.value),
                    threshold=str(threshold.value) if threshold.value else None,
                    investment_id=int(inv_sel.value) if inv_sel.value else None,
                    category_id=int(cat_sel.value) if cat_sel.value else None,
                )
            ui.notify("Alert rule created", type="positive")
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Create rule", on_click=submit).props("color=primary")


def _alert_check_view() -> None:
    state: dict = {"fired": None}

    @ui.refreshable
    def check_result() -> None:
        fired = state["fired"]
        if fired is None:
            return
        if not fired:
            ui.label("No alerts fired. 🎉").classes("text-green-600")
            return
        for alert in fired:
            ui.label(f"[{alert.kind}] {alert.message}").classes("text-yellow-600 font-semibold")

    def run_check() -> None:
        with session_scope() as session:
            state["fired"] = AlertService(session).evaluate()
        check_result.refresh()

    ui.button("Check alerts now", on_click=run_check).props("color=primary")
    check_result()


# ---------------------------------------------------------------------------
# Categories tab
# ---------------------------------------------------------------------------

def _render_categories() -> None:
    with ui.tabs().classes("w-full") as sub_tabs:
        t_list = ui.tab("List")
        t_add = ui.tab("Add")

    with ui.tab_panels(sub_tabs, value=t_list).classes("w-full"):
        with ui.tab_panel(t_list):
            _categories_list_view()
        with ui.tab_panel(t_add):
            _category_add_view()


@ui.refreshable
def _categories_list_view() -> None:
    with session_scope() as session:
        cats = session.exec(select(Category).order_by(Category.type, Category.name)).all()

    if not cats:
        ui.label("No categories.").classes("text-gray-500")
        return

    cols = [
        {"name": "name", "label": "Name", "field": "name"},
        {"name": "type", "label": "Type", "field": "type"},
        {"name": "color", "label": "Color", "field": "color"},
    ]
    rows = [
        {"name": c.name, "type": c.type.value, "color": c.color or "—"}
        for c in cats
    ]
    ui.table(columns=cols, rows=rows, row_key="name").classes("w-full max-w-lg")


def _category_add_view() -> None:
    type_options = {"expense": "Expense", "income": "Income"}

    name = ui.input("Category name").classes("w-48")
    type_sel = ui.select(type_options, value="expense", label="Type").classes("w-36")
    color = ui.input("Color (optional, e.g. #3B82F6)").classes("w-40")

    def submit() -> None:
        try:
            ctype = CategoryType.INCOME if type_sel.value == "income" else CategoryType.EXPENSE
            with session_scope() as session:
                existing = session.exec(
                    select(Category).where(
                        Category.name == name.value, Category.type == ctype
                    )
                ).first()
                if existing:
                    ui.notify(f"Category '{name.value}' already exists", type="warning")
                    return
                session.add(Category(name=name.value, type=ctype, color=color.value or None))
                session.commit()
            ui.notify(f"Added category '{name.value}'", type="positive")
            name.value = ""
        except (ValueError, TypeError) as exc:
            ui.notify(f"Error: {exc}", type="negative")

    ui.button("Add category", on_click=submit).props("color=primary")


# ---------------------------------------------------------------------------
# Main page layout
# ---------------------------------------------------------------------------

@ui.page("/")
def index() -> None:
    """Single-page app with top-level tab navigation."""
    ui.add_head_html("""
        <style>
        .q-tab { font-size: 0.8rem; min-height: 40px; }
        body { font-family: 'Inter', sans-serif; }
        </style>
    """)

    with ui.header().classes("bg-gray-900 text-white px-4 py-2"):
        with ui.row().classes("items-center gap-2"):
            ui.label("wealthlog").classes("text-xl font-bold")
            ui.label("personal finance & investments").classes("text-sm text-gray-400")

    with ui.tabs().classes("w-full sticky top-0 bg-white z-10 shadow-sm px-2") as tabs:
        t_dash = ui.tab("Dashboard")
        t_exp = ui.tab("Expenses")
        t_inc = ui.tab("Income")
        t_bud = ui.tab("Budget")
        t_inv = ui.tab("Investments")
        t_nw = ui.tab("Net Worth")
        t_lib = ui.tab("Liabilities")
        t_data = ui.tab("Import/Export")
        t_alrt = ui.tab("Alerts")
        t_cat = ui.tab("Categories")

    with ui.tab_panels(tabs, value=t_dash).classes("w-full px-4 py-2"):
        with ui.tab_panel(t_dash):
            _render_dashboard()
        with ui.tab_panel(t_exp):
            _render_expenses()
        with ui.tab_panel(t_inc):
            _render_income()
        with ui.tab_panel(t_bud):
            _render_budget()
        with ui.tab_panel(t_inv):
            _render_investments()
        with ui.tab_panel(t_nw):
            _render_networth()
        with ui.tab_panel(t_lib):
            _render_liabilities()
        with ui.tab_panel(t_data):
            _render_data()
        with ui.tab_panel(t_alrt):
            _render_alerts()
        with ui.tab_panel(t_cat):
            _render_categories()


def main() -> None:
    """Launch the wealthlog web/desktop UI on localhost."""
    logger.info("Starting wealthlog web UI on http://127.0.0.1:8080")
    ui.run(title="wealthlog", port=8080, reload=False, show=False, native=False)


if __name__ in {"__main__", "__mp_main__"}:  # pragma: no cover
    main()
