"""Tests for DividendService: yearly/holding aggregation and trailing yield."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import AssetType, TransactionType
from wealthlog.db.models import PriceCache
from wealthlog.services.dividends import DividendService
from wealthlog.services.portfolio import PortfolioService


@pytest.fixture
def portfolio(db_session):
    return PortfolioService(db_session)


@pytest.fixture
def svc(db_session):
    return DividendService(db_session)


def _add_price(session, investment_id, price_inr):
    session.add(
        PriceCache(
            investment_id=investment_id,
            price_native=Decimal(price_inr),
            price_inr=Decimal(price_inr),
            fetched_at=dt.datetime.now(),
        )
    )
    session.commit()


def _dividend(portfolio, inv_id, date, amount):
    portfolio.add_transaction(
        inv_id, date, TransactionType.DIVIDEND, "0", "0", amount_inr=amount
    )


class TestAggregation:
    def test_total_by_year(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        _dividend(portfolio, inv.id, dt.date(2025, 6, 1), "300")
        _dividend(portfolio, inv.id, dt.date(2026, 6, 1), "500")
        _dividend(portfolio, inv.id, dt.date(2026, 12, 1), "200")
        by_year = svc.total_by_year()
        assert list(by_year.keys()) == [2026, 2025]  # newest first
        assert by_year[2026] == Decimal("700.00")
        assert by_year[2025] == Decimal("300.00")

    def test_total_by_holding_sorted(self, svc, portfolio):
        a = portfolio.add_investment("A.NS", "A", AssetType.STOCK_IN)
        b = portfolio.add_investment("B.NS", "B", AssetType.STOCK_IN)
        _dividend(portfolio, a.id, dt.date(2026, 1, 1), "100")
        _dividend(portfolio, b.id, dt.date(2026, 1, 1), "400")
        rows = svc.total_by_holding()
        assert [r.symbol for r in rows] == ["B.NS", "A.NS"]
        assert rows[0].total_inr == Decimal("400.00")

    def test_total_by_holding_filters_year(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        _dividend(portfolio, inv.id, dt.date(2025, 6, 1), "300")
        _dividend(portfolio, inv.id, dt.date(2026, 6, 1), "500")
        rows = svc.total_by_holding(year=2026)
        assert len(rows) == 1
        assert rows[0].total_inr == Decimal("500.00")

    def test_no_dividends_empty(self, svc, portfolio):
        portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        assert svc.total_by_year() == {}
        assert svc.total_by_holding() == []


class TestTrailingYield:
    def test_yield_from_market_value(self, svc, portfolio, db_session):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "100", "100")
        _add_price(db_session, inv.id, "100")  # market value 10000
        _dividend(portfolio, inv.id, dt.date(2026, 3, 1), "500")
        # 500 / 10000 = 5%
        y = svc.trailing_yield(inv.id, as_of=dt.date(2026, 6, 1))
        assert y == Decimal("5.00")

    def test_yield_excludes_old_dividends(self, svc, portfolio, db_session):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "100", "100")
        _add_price(db_session, inv.id, "100")
        _dividend(portfolio, inv.id, dt.date(2024, 3, 1), "999")  # >12mo ago
        assert svc.trailing_yield(inv.id, as_of=dt.date(2026, 6, 1)) == Decimal("0.00")

    def test_yield_none_when_no_value(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        # Dividend but no holding/price -> fully exited, value undefined.
        _dividend(portfolio, inv.id, dt.date(2026, 3, 1), "500")
        assert svc.trailing_yield(inv.id, as_of=dt.date(2026, 6, 1)) is None
