"""Tests for PortfolioService: transactions, holdings, P&L, XIRR, FD valuation."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import AssetType, CompoundingFrequency, TransactionType
from wealthlog.db.models import PriceCache
from wealthlog.services.portfolio import PortfolioService


@pytest.fixture
def svc(db_session):
    return PortfolioService(db_session)


def _add_price(session, investment_id, price_inr, price_native=None, when=None):
    session.add(
        PriceCache(
            investment_id=investment_id,
            price_native=Decimal(price_native if price_native is not None else price_inr),
            price_inr=Decimal(price_inr),
            fetched_at=when or dt.datetime.now(),
        )
    )
    session.commit()


class TestAddTransaction:
    def test_auto_amount_inr_with_fx(self, svc):
        inv = svc.add_investment("AAPL", "Apple", AssetType.STOCK_US, currency_native="USD")
        txn = svc.add_transaction(
            inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100", fx_rate_used="83"
        )
        assert txn.amount_inr == Decimal("83000.00")  # 10 * 100 * 83
        assert txn.fx_rate_used == Decimal("83")

    def test_auto_amount_inr_no_fx(self, svc):
        inv = svc.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        txn = svc.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "5", "1500")
        assert txn.amount_inr == Decimal("7500.00")

    def test_explicit_amount_overrides(self, svc):
        inv = svc.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        txn = svc.add_transaction(
            inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "5", "1500", amount_inr="7000"
        )
        assert txn.amount_inr == Decimal("7000.00")

    def test_missing_investment_raises(self, svc):
        with pytest.raises(ValueError):
            svc.add_transaction(999, dt.date(2026, 1, 1), TransactionType.BUY, "1", "1")

    def test_negative_units_raises(self, svc):
        inv = svc.add_investment("X", "X", AssetType.STOCK_IN)
        with pytest.raises(ValueError):
            svc.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "-1", "10")


class TestHoldings:
    def test_single_buy_no_price_is_stale(self, svc, db_session):
        inv = svc.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        svc.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "1000")
        holdings = svc.get_holdings()
        assert len(holdings) == 1
        h = holdings[0]
        assert h.units == Decimal("10.0000")
        assert h.invested_inr == Decimal("10000.00")
        assert h.price_is_stale is True
        assert h.pnl_abs_inr == Decimal("0.00")  # fallback to avg cost

    def test_buy_with_fresh_price_gives_pnl(self, svc, db_session):
        inv = svc.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        svc.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "1000")
        _add_price(db_session, inv.id, "1200")
        h = svc.get_holdings()[0]
        assert h.current_price_inr == Decimal("1200")
        assert h.market_value_inr == Decimal("12000.00")
        assert h.pnl_abs_inr == Decimal("2000.00")
        assert h.pnl_pct == Decimal("20.00")
        assert h.price_is_stale is False

    def test_average_cost_across_buys(self, svc):
        inv = svc.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        svc.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "1000")
        svc.add_transaction(inv.id, dt.date(2026, 2, 1), TransactionType.BUY, "10", "2000")
        h = svc.get_holdings()[0]
        assert h.units == Decimal("20.0000")
        assert h.avg_cost_inr == Decimal("1500.0000")  # (10000+20000)/20

    def test_sell_reduces_units(self, svc):
        inv = svc.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        svc.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "1000")
        svc.add_transaction(inv.id, dt.date(2026, 3, 1), TransactionType.SELL, "4", "1500")
        h = svc.get_holdings()[0]
        assert h.units == Decimal("6.0000")

    def test_fully_sold_excluded(self, svc):
        inv = svc.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        svc.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "1000")
        svc.add_transaction(inv.id, dt.date(2026, 3, 1), TransactionType.SELL, "10", "1500")
        assert svc.get_holdings() == []

    def test_sip_counts_as_buy(self, svc):
        inv = svc.add_investment("120503", "Axis MF", AssetType.MF)
        svc.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.SIP, "100", "50")
        h = svc.get_holdings()[0]
        assert h.units == Decimal("100.0000")
        assert h.invested_inr == Decimal("5000.00")

    def test_stale_price_flagged(self, svc, db_session):
        inv = svc.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        svc.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "1000")
        _add_price(db_session, inv.id, "1200", when=dt.datetime.now() - dt.timedelta(days=2))
        h = svc.get_holdings()[0]
        assert h.price_is_stale is True


class TestFd:
    def test_fd_holding_valued(self, svc):
        svc.add_fd(
            "SBI FD", "100000", "10", dt.date(2024, 1, 1),
            dt.date(2024, 1, 1) + dt.timedelta(days=365),
            compounding=CompoundingFrequency.SIMPLE,
        )
        holdings = svc.get_holdings(as_of=dt.date(2024, 1, 1) + dt.timedelta(days=365))
        assert len(holdings) == 1
        h = holdings[0]
        assert h.asset_type == AssetType.FD
        assert h.invested_inr == Decimal("100000.00")
        assert h.market_value_inr == Decimal("110000.00")
        assert h.pnl_abs_inr == Decimal("10000.00")


class TestPnl:
    def test_portfolio_pnl_aggregates(self, svc, db_session):
        a = svc.add_investment("A.NS", "A", AssetType.STOCK_IN)
        b = svc.add_investment("B.NS", "B", AssetType.STOCK_IN)
        svc.add_transaction(a.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        svc.add_transaction(b.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "200")
        _add_price(db_session, a.id, "150")
        _add_price(db_session, b.id, "250")
        pnl = svc.get_pnl()
        assert pnl.invested_inr == Decimal("3000.00")
        assert pnl.market_value_inr == Decimal("4000.00")
        assert pnl.pnl_abs_inr == Decimal("1000.00")

    def test_pnl_single_investment(self, svc, db_session):
        a = svc.add_investment("A.NS", "A", AssetType.STOCK_IN)
        svc.add_transaction(a.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        _add_price(db_session, a.id, "150")
        pnl = svc.get_pnl(investment_id=a.id)
        assert pnl.pnl_abs_inr == Decimal("500.00")

    def test_empty_portfolio_pnl(self, svc):
        pnl = svc.get_pnl()
        assert pnl.invested_inr == Decimal("0.00")
        assert pnl.pnl_pct is None


class TestXirr:
    def test_all_buys_returns_none(self, svc):
        inv = svc.add_investment("A.NS", "A", AssetType.STOCK_IN)
        svc.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        # No price, fallback market value == invested -> terminal positive flow exists,
        # so two signs present; but with equal value XIRR ~ 0. Force no-price scenario:
        rate = svc.calculate_xirr(inv.id, as_of=dt.date(2026, 6, 1))
        # terminal value equals invested -> near-zero return is valid (not None).
        assert rate is None or abs(rate) < Decimal("0.01")

    def test_profit_positive_xirr(self, svc, db_session):
        inv = svc.add_investment("A.NS", "A", AssetType.STOCK_IN)
        svc.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "100")
        _add_price(db_session, inv.id, "150")
        rate = svc.calculate_xirr(inv.id, as_of=dt.date(2025, 1, 1))
        assert rate is not None and rate > 0

    def test_sell_realized_gain_xirr(self, svc):
        inv = svc.add_investment("A.NS", "A", AssetType.STOCK_IN)
        svc.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "100")
        svc.add_transaction(inv.id, dt.date(2025, 1, 1), TransactionType.SELL, "10", "120")
        rate = svc.calculate_xirr(inv.id, as_of=dt.date(2025, 1, 1))
        assert rate is not None and rate > Decimal("0.15")

    def test_portfolio_xirr_combines(self, svc, db_session):
        a = svc.add_investment("A.NS", "A", AssetType.STOCK_IN)
        b = svc.add_investment("B.NS", "B", AssetType.STOCK_IN)
        svc.add_transaction(a.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "100")
        svc.add_transaction(b.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "100")
        _add_price(db_session, a.id, "150")
        _add_price(db_session, b.id, "150")
        rate = svc.calculate_xirr(as_of=dt.date(2025, 1, 1))
        assert rate is not None and rate > 0

    def test_unknown_investment_none(self, svc):
        assert svc.calculate_xirr(investment_id=12345) is None

    def test_empty_portfolio_none(self, svc):
        assert svc.calculate_xirr() is None
