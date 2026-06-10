"""Tests for NetWorthService: asset-class breakdown and historical series."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import AssetType, CompoundingFrequency, TransactionType
from wealthlog.db.models import PriceCache, PriceSnapshot
from wealthlog.services.networth import NetWorthService
from wealthlog.services.portfolio import PortfolioService


@pytest.fixture
def portfolio(db_session):
    return PortfolioService(db_session)


@pytest.fixture
def svc(db_session):
    return NetWorthService(db_session)


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


class TestNetWorth:
    def test_empty_is_zero(self, svc):
        nw = svc.calculate_net_worth()
        assert nw.total_assets_inr == Decimal("0.00")
        assert nw.net_worth_inr == Decimal("0.00")
        assert nw.by_asset_class == []

    def test_single_asset_class(self, svc, portfolio, db_session):
        inv = portfolio.add_investment("A.NS", "A", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        _add_price(db_session, inv.id, "150")
        nw = svc.calculate_net_worth()
        assert nw.total_assets_inr == Decimal("1500.00")
        assert nw.by_asset_class[0].asset_type == AssetType.STOCK_IN
        assert nw.by_asset_class[0].pct_of_total == Decimal("100.00")

    def test_multi_class_breakdown_sorted(self, svc, portfolio, db_session):
        stock = portfolio.add_investment("A.NS", "A", AssetType.STOCK_IN)
        portfolio.add_transaction(stock.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        _add_price(db_session, stock.id, "100")  # value 1000
        portfolio.add_fd(
            "FD", "3000", "10", dt.date(2026, 1, 1),
            dt.date(2027, 1, 1), compounding=CompoundingFrequency.SIMPLE,
        )
        nw = svc.calculate_net_worth(as_of=dt.date(2026, 1, 1))
        # FD at start == principal 3000 > stock 1000, so FD ranks first.
        assert nw.by_asset_class[0].asset_type == AssetType.FD
        assert nw.total_assets_inr == Decimal("4000.00")

    def test_pct_sums_to_100(self, svc, portfolio, db_session):
        a = portfolio.add_investment("A.NS", "A", AssetType.STOCK_IN)
        b = portfolio.add_investment("AAPL", "Apple", AssetType.STOCK_US, currency_native="USD")
        portfolio.add_transaction(a.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        portfolio.add_transaction(
            b.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100", fx_rate_used="1"
        )
        _add_price(db_session, a.id, "100")
        _add_price(db_session, b.id, "100")
        nw = svc.calculate_net_worth()
        total_pct = sum(c.pct_of_total for c in nw.by_asset_class)
        assert total_pct == Decimal("100.00")

    def test_liabilities_zero_v1(self, svc):
        nw = svc.calculate_net_worth()
        assert nw.total_liabilities_inr == Decimal("0.00")


class TestHistorical:
    def test_cumulative_invested_grows(self, svc, portfolio):
        inv = portfolio.add_investment("A.NS", "A", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 15), TransactionType.BUY, "10", "100")
        portfolio.add_transaction(inv.id, dt.date(2026, 3, 15), TransactionType.BUY, "10", "100")
        points = svc.historical_net_worth(dt.date(2026, 1, 1), dt.date(2026, 3, 31))
        assert len(points) == 3
        assert points[0].invested_inr == Decimal("1000.00")  # Jan
        assert points[1].invested_inr == Decimal("1000.00")  # Feb (no new)
        assert points[2].invested_inr == Decimal("2000.00")  # Mar

    def test_sell_reduces_invested(self, svc, portfolio):
        inv = portfolio.add_investment("A.NS", "A", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 10), TransactionType.BUY, "10", "100")
        portfolio.add_transaction(inv.id, dt.date(2026, 2, 10), TransactionType.SELL, "5", "100")
        points = svc.historical_net_worth(dt.date(2026, 1, 1), dt.date(2026, 2, 28))
        assert points[0].invested_inr == Decimal("1000.00")
        assert points[1].invested_inr == Decimal("500.00")

    def test_fd_counts_from_start(self, svc, portfolio):
        portfolio.add_fd(
            "FD", "5000", "10", dt.date(2026, 2, 1),
            dt.date(2027, 2, 1), compounding=CompoundingFrequency.SIMPLE,
        )
        points = svc.historical_net_worth(dt.date(2026, 1, 1), dt.date(2026, 2, 28))
        assert points[0].invested_inr == Decimal("0.00")  # Jan, before FD
        assert points[1].invested_inr == Decimal("5000.00")  # Feb

    def test_end_before_start_raises(self, svc):
        with pytest.raises(ValueError):
            svc.historical_net_worth(dt.date(2026, 3, 1), dt.date(2026, 1, 1))

    def test_single_month_range(self, svc, portfolio):
        points = svc.historical_net_worth(dt.date(2026, 5, 1), dt.date(2026, 5, 31))
        assert len(points) == 1


def _add_snapshot(session, investment_id, date, price_inr, source="manual"):
    session.add(
        PriceSnapshot(
            investment_id=investment_id, date=date,
            price_inr=Decimal(price_inr), source=source,
        )
    )
    session.commit()


class TestHistoricalSellCostBasis:
    """Bug #4b: a SELL releases the average cost of sold units, not the proceeds."""

    def test_profitable_full_exit_returns_to_zero(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        # Sell all 10 at a large profit (proceeds 3000 >> cost 1000).
        portfolio.add_transaction(inv.id, dt.date(2026, 3, 1), TransactionType.SELL, "10", "300")
        points = svc.historical_net_worth(dt.date(2026, 1, 1), dt.date(2026, 4, 1))
        by_month = {(p.year, p.month): p.invested_inr for p in points}
        assert by_month[(2026, 1)] == Decimal("1000.00")
        assert by_month[(2026, 2)] == Decimal("1000.00")
        # Released avg cost (1000), not proceeds (3000): series rests at 0, not -2000.
        assert by_month[(2026, 3)] == Decimal("0.00")
        assert by_month[(2026, 4)] == Decimal("0.00")

    def test_partial_sell_releases_average_cost(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        portfolio.add_transaction(inv.id, dt.date(2026, 2, 1), TransactionType.SELL, "4", "500")
        points = svc.historical_net_worth(dt.date(2026, 1, 1), dt.date(2026, 2, 1))
        by_month = {(p.year, p.month): p.invested_inr for p in points}
        # 6 units remain at avg cost 100 -> 600 (not 1000 - 2000 proceeds).
        assert by_month[(2026, 2)] == Decimal("600.00")


class TestMarketModeHistory:
    """A3: market mode values holdings from snapshots, falling back to cost."""

    def test_snapshot_used_when_available(self, svc, portfolio, db_session):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        _add_snapshot(db_session, inv.id, dt.date(2026, 2, 15), "150")
        points = svc.historical_net_worth(
            dt.date(2026, 1, 1), dt.date(2026, 3, 1), mode="market"
        )
        by_month = {(p.year, p.month): p for p in points}
        # January: no snapshot on/before month-end -> falls back to cost.
        jan = by_month[(2026, 1)]
        assert jan.invested_inr == Decimal("1000.00")
        assert jan.market_value_inr == Decimal("1000.00")
        assert jan.is_market_value is False
        # February: snapshot (150) applies -> 10 * 150 = 1500.
        feb = by_month[(2026, 2)]
        assert feb.market_value_inr == Decimal("1500.00")
        assert feb.is_market_value is True
        # March: latest snapshot on/before cutoff still 150.
        assert by_month[(2026, 3)].market_value_inr == Decimal("1500.00")

    def test_cost_mode_has_no_market_value(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        points = svc.historical_net_worth(dt.date(2026, 1, 1), dt.date(2026, 1, 31))
        assert points[0].market_value_inr is None
        assert points[0].is_market_value is False
