"""wealthlog web/desktop UI (NiceGUI).

Exposed as the ``wealthlog`` console script. Serves a localhost dashboard (net worth,
allocation chart, holdings, expense entry, budget status) and can also run as a native
desktop window. The heavy lifting lives in :mod:`wealthlog.api.dashboard`; this module
is the presentation layer.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from nicegui import ui

from wealthlog.api.dashboard import asset_allocation_series, build_dashboard_data
from wealthlog.bootstrap import session_scope
from wealthlog.logging_conf import get_logger
from wealthlog.services.expense import ExpenseService
from wealthlog.services.fetcher import FetcherService

logger = get_logger(__name__)


def _fmt_inr(amount: Decimal | None) -> str:
    return "—" if amount is None else f"₹{amount:,.2f}"


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


def _render_dashboard() -> None:
    """Build the dashboard page contents (called within a NiceGUI page context)."""
    with session_scope() as session:
        data = build_dashboard_data(session)

    ui.label("wealthlog").classes("text-3xl font-bold")
    ui.label(f"As of {data.as_of:%d %b %Y}").classes("text-sm text-gray-500")

    # Summary cards.
    with ui.row().classes("w-full gap-4 flex-wrap"):
        _summary_card("Net worth", _fmt_inr(data.net_worth.net_worth_inr), "primary")
        _summary_card("Invested", _fmt_inr(data.pnl.invested_inr), "secondary")
        pnl_color = "positive" if data.pnl.pnl_abs_inr >= 0 else "negative"
        _summary_card("Unrealised P&L", _fmt_inr(data.pnl.pnl_abs_inr), pnl_color)
        xirr = (
            f"{data.portfolio_xirr * Decimal(100):+.2f}%"
            if data.portfolio_xirr is not None
            else "—"
        )
        _summary_card("Portfolio XIRR", xirr, "accent")
        _summary_card("Spent this month", _fmt_inr(data.month_total_inr), "warning")

    with ui.row().classes("w-full gap-4 flex-wrap items-start"):
        # Allocation chart.
        with ui.card().classes("flex-1 min-w-[320px]"):
            ui.label("Asset allocation").classes("text-lg font-semibold")
            labels, values = asset_allocation_series(data)
            if values:
                ui.echart(_allocation_chart_options(labels, values)).classes("h-64 w-full")
            else:
                ui.label("No holdings yet.").classes("text-gray-500")

        # Budget overages.
        with ui.card().classes("flex-1 min-w-[320px]"):
            ui.label("Budget alerts").classes("text-lg font-semibold")
            if data.overages:
                for s in data.overages:
                    ui.label(
                        f"⚠ {s.category_name}: {_fmt_inr(s.spent_inr)} / {_fmt_inr(s.limit_inr)} "
                        f"({s.pct_used:.0f}%)"
                    ).classes("text-red-600")
            else:
                ui.label("All budgets within limits 🎉").classes("text-green-600")

    # Holdings table.
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Holdings").classes("text-lg font-semibold")
            ui.button("Refresh prices", on_click=_refresh_prices).props("outline size=sm")
        columns = [
            {"name": "symbol", "label": "Symbol", "field": "symbol", "align": "left"},
            {"name": "type", "label": "Type", "field": "type"},
            {"name": "units", "label": "Units", "field": "units"},
            {"name": "invested", "label": "Invested", "field": "invested"},
            {"name": "value", "label": "Value", "field": "value"},
            {"name": "pnl", "label": "P&L", "field": "pnl"},
            {"name": "price", "label": "Price", "field": "price"},
        ]
        rows = [
            {
                "symbol": h.symbol,
                "type": h.asset_type.value,
                "units": f"{h.units:g}",
                "invested": _fmt_inr(h.invested_inr),
                "value": _fmt_inr(h.market_value_inr),
                "pnl": _fmt_inr(h.pnl_abs_inr),
                "price": _fmt_inr(h.current_price_inr) + (" (stale)" if h.price_is_stale else ""),
            }
            for h in data.holdings
        ]
        ui.table(columns=columns, rows=rows).classes("w-full")

    # Expense entry.
    with ui.card().classes("w-full"):
        ui.label("Add expense").classes("text-lg font-semibold")
        _expense_form()


def _summary_card(title: str, value: str, color: str) -> None:
    with ui.card().classes(f"min-w-[180px] border-l-4 border-{color}"):
        ui.label(title).classes("text-xs uppercase text-gray-500")
        ui.label(value).classes("text-xl font-bold")


def _expense_form() -> None:
    amount = ui.number("Amount (INR)", value=0, format="%.2f").classes("w-40")
    description = ui.input("Description").classes("w-64")
    date_in = ui.input("Date", value=dt.date.today().isoformat()).classes("w-40")

    def submit() -> None:
        try:
            with session_scope() as session:
                ExpenseService(session).add_expense(
                    dt.date.fromisoformat(date_in.value),
                    str(amount.value),
                    description=description.value or None,
                )
            ui.notify("Expense added", type="positive")
        except (ValueError, TypeError) as exc:
            ui.notify(f"Invalid input: {exc}", type="negative")

    ui.button("Add", on_click=submit).props("color=primary")


def _refresh_prices() -> None:
    with session_scope() as session:
        result = FetcherService(session).refresh_prices()
    if result.failed:
        ui.notify(f"Refreshed {len(result.updated)}, {len(result.failed)} failed", type="warning")
    else:
        ui.notify(f"Refreshed {len(result.updated)} price(s)", type="positive")


@ui.page("/")
def index() -> None:
    """Render the dashboard at the site root."""
    _render_dashboard()


def main() -> None:
    """Launch the wealthlog web/desktop UI on localhost."""
    logger.info("Starting wealthlog web UI on http://127.0.0.1:8080")
    ui.run(title="wealthlog", port=8080, reload=False, show=False, native=False)


if __name__ in {"__main__", "__mp_main__"}:  # pragma: no cover
    main()
