"""Tests for the Textual TUI, driven through the async test pilot.

We wrap each scenario in ``asyncio.run`` so no extra pytest-asyncio plugin is needed.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from decimal import Decimal

from textual.widgets import DataTable, Static

from wealthlog.constants import AssetType, TransactionType
from wealthlog.db.models import Category, PriceCache
from wealthlog.services.budget import BudgetService
from wealthlog.services.expense import ExpenseService
from wealthlog.services.portfolio import PortfolioService
from wealthlog.tui.app import WealthlogApp, _fmt_inr


def _run(coro):
    return asyncio.run(coro)


class TestFormatting:
    def test_fmt_inr(self):
        from decimal import Decimal

        assert _fmt_inr(Decimal("1234.5")) == "Rs 1,234.50"
        assert _fmt_inr(None) == "-"


class TestAppMounts:
    def test_mounts_with_empty_db(self, db_session):
        async def scenario():
            app = WealthlogApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                assert isinstance(app.query_one("#holdings", DataTable), DataTable)
                assert isinstance(app.query_one("#summary", Static), Static)

        _run(scenario())

    def test_summary_shows_net_worth(self, db_session):
        p = PortfolioService(db_session)
        inv = p.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        p.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "1000")
        db_session.add(
            PriceCache(investment_id=inv.id, price_native=Decimal("1500"),
                       price_inr=Decimal("1500"), fetched_at=dt.datetime.now())
        )
        db_session.commit()

        async def scenario():
            app = WealthlogApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                assert "Net worth" in app.summary_text
                assert "15,000" in app.summary_text

        _run(scenario())

    def test_holdings_table_populated(self, db_session):
        p = PortfolioService(db_session)
        inv = p.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        p.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "1000")

        async def scenario():
            app = WealthlogApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                table = app.query_one("#holdings", DataTable)
                assert table.row_count == 1

        _run(scenario())

    def test_expenses_tab_lists_expense(self, db_session):
        ExpenseService(db_session).add_expense(dt.date(2026, 6, 1), "250")

        async def scenario():
            app = WealthlogApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                table = app.query_one("#expenses_table", DataTable)
                assert table.row_count == 1

        _run(scenario())

    def test_budgets_tab_populated(self, db_session):
        cat = Category(name="Food")
        db_session.add(cat)
        db_session.commit()
        BudgetService(db_session).set_budget(cat.id, dt.date.today().month, dt.date.today().year,
                                             "1000")

        async def scenario():
            app = WealthlogApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                table = app.query_one("#budgets_table", DataTable)
                assert table.row_count == 1

        _run(scenario())

    def test_refresh_action(self, db_session):
        async def scenario():
            app = WealthlogApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("r")
                await pilot.pause()
                assert isinstance(app.query_one("#holdings", DataTable), DataTable)

        _run(scenario())
