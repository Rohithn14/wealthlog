"""Tests for the headless dashboard data layer and UI pure helpers."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from wealthlog.api.dashboard import asset_allocation_series, build_dashboard_data
from wealthlog.constants import AssetType, TransactionType
from wealthlog.db.models import PriceCache
from wealthlog.services.budget import BudgetService
from wealthlog.services.expense import ExpenseService
from wealthlog.services.portfolio import PortfolioService


def _price(session, inv_id, value):
    session.add(
        PriceCache(investment_id=inv_id, price_native=Decimal(value),
                   price_inr=Decimal(value), fetched_at=dt.datetime.now())
    )
    session.commit()


class TestBuildDashboardData:
    def test_empty(self, db_session):
        data = build_dashboard_data(db_session, as_of=dt.date(2026, 6, 1))
        assert data.net_worth.net_worth_inr == Decimal("0.00")
        assert data.holdings == []
        assert data.month_total_inr == Decimal("0.00")
        assert data.overages == []

    def test_populated(self, db_session):
        p = PortfolioService(db_session)
        inv = p.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        p.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "1000")
        _price(db_session, inv.id, "1500")
        ExpenseService(db_session).add_expense(dt.date(2026, 6, 5), "250")
        data = build_dashboard_data(db_session, as_of=dt.date(2026, 6, 10))
        assert data.net_worth.net_worth_inr == Decimal("15000.00")
        assert len(data.holdings) == 1
        assert data.pnl.pnl_abs_inr == Decimal("5000.00")
        assert data.month_total_inr == Decimal("250.00")
        assert data.portfolio_xirr is not None

    def test_overages_detected(self, db_session):
        ExpenseService(db_session)  # ensure import path
        from wealthlog.db.models import Category

        cat = Category(name="Food")
        db_session.add(cat)
        db_session.commit()
        BudgetService(db_session).set_budget(cat.id, 6, 2026, "100")
        ExpenseService(db_session).add_expense(dt.date(2026, 6, 1), "500", category_id=cat.id)
        data = build_dashboard_data(db_session, as_of=dt.date(2026, 6, 15))
        assert len(data.overages) == 1
        assert data.overages[0].category_name == "Food"

    def test_default_as_of_is_today(self, db_session):
        data = build_dashboard_data(db_session)
        assert data.as_of == dt.date.today()


class TestAllocationSeries:
    def test_empty(self, db_session):
        data = build_dashboard_data(db_session)
        labels, values = asset_allocation_series(data)
        assert labels == [] and values == []

    def test_multi_class(self, db_session):
        p = PortfolioService(db_session)
        stock = p.add_investment("A.NS", "A", AssetType.STOCK_IN)
        p.add_transaction(stock.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        _price(db_session, stock.id, "100")
        p.add_fd("FD", "5000", "7", dt.date(2026, 1, 1), dt.date(2027, 1, 1))
        data = build_dashboard_data(db_session, as_of=dt.date(2026, 1, 1))
        labels, values = asset_allocation_series(data)
        assert set(labels) == {"STOCK_IN", "FD"}
        assert all(isinstance(v, float) for v in values)


class TestUiHelpers:
    def test_fmt_inr(self):
        from wealthlog.api.server import _fmt_inr

        assert _fmt_inr(Decimal("1234.5")) == "₹1,234.50"
        assert _fmt_inr(None) == "—"

    def test_allocation_chart_options(self):
        from wealthlog.api.server import _allocation_chart_options

        opts = _allocation_chart_options(["STOCK_IN", "FD"], [1000.0, 5000.0])
        assert opts["series"][0]["type"] == "pie"
        data = opts["series"][0]["data"]
        assert data[0] == {"value": 1000.0, "name": "STOCK_IN"}

    def test_index_and_main_importable(self):
        from wealthlog.api.server import index, main

        assert callable(index)
        assert callable(main)
