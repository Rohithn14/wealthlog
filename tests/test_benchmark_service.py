"""Tests for BenchmarkService: snapshot-based returns and portfolio comparison."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import AssetType, TransactionType
from wealthlog.db.models import PriceCache
from wealthlog.services.benchmark import BenchmarkService
from wealthlog.services.portfolio import PortfolioService


@pytest.fixture
def svc(db_session):
    return BenchmarkService(db_session)


@pytest.fixture
def portfolio(db_session):
    return PortfolioService(db_session)


class TestBenchmarkSetup:
    def test_get_or_create_idempotent(self, svc):
        a = svc.get_or_create("NIFTY50")
        b = svc.get_or_create("nifty50")
        assert a.id == b.id
        assert a.asset_type == AssetType.BENCHMARK
        assert a.symbol == "^NSEI"

    def test_unknown_benchmark_raises(self, svc):
        with pytest.raises(ValueError):
            svc.get_or_create("DOWJONES")

    def test_record_price_upserts(self, svc):
        svc.record_price("NIFTY50", dt.date(2025, 1, 1), "20000")
        svc.record_price("NIFTY50", dt.date(2025, 1, 1), "20500")  # same day
        ret = svc.benchmark_return("NIFTY50", dt.date(2025, 1, 1), dt.date(2025, 12, 31))
        # Only one snapshot that day -> need a second date for a window.
        assert ret is None

    def test_benchmark_excluded_from_holdings(self, svc, portfolio):
        svc.get_or_create("NIFTY50")
        # Benchmark has no transactions, so it never appears as a holding.
        assert portfolio.get_holdings() == []


class TestBenchmarkReturn:
    def test_total_and_cagr(self, svc):
        svc.record_price("NIFTY50", dt.date(2024, 1, 1), "20000")
        svc.record_price("NIFTY50", dt.date(2025, 1, 1), "24000")  # +20% over ~1yr
        ret = svc.benchmark_return("NIFTY50", dt.date(2024, 1, 1), dt.date(2025, 1, 1))
        assert ret is not None
        assert ret.total_return_pct == Decimal("20.00")
        # 366 days (2024 leap) -> CAGR very close to 20%.
        assert abs(ret.cagr_pct - Decimal("20")) < Decimal("0.5")

    def test_uses_window_bounds(self, svc):
        svc.record_price("NIFTY50", dt.date(2023, 1, 1), "10000")  # before window
        svc.record_price("NIFTY50", dt.date(2024, 6, 1), "20000")
        svc.record_price("NIFTY50", dt.date(2024, 12, 1), "22000")
        svc.record_price("NIFTY50", dt.date(2025, 6, 1), "30000")  # after window
        ret = svc.benchmark_return("NIFTY50", dt.date(2024, 1, 1), dt.date(2025, 1, 1))
        assert ret.start_price == Decimal("20000.0000")
        assert ret.end_price == Decimal("22000.0000")
        assert ret.total_return_pct == Decimal("10.00")

    def test_single_snapshot_returns_none(self, svc):
        svc.record_price("NIFTY50", dt.date(2024, 6, 1), "20000")
        assert svc.benchmark_return("NIFTY50", dt.date(2024, 1, 1), dt.date(2025, 1, 1)) is None

    def test_end_before_start_raises(self, svc):
        with pytest.raises(ValueError):
            svc.benchmark_return("NIFTY50", dt.date(2025, 1, 1), dt.date(2024, 1, 1))


class TestCompare:
    def test_compare_includes_portfolio_and_benchmarks(self, svc, portfolio, db_session):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "100")
        db_session.add(
            PriceCache(
                investment_id=inv.id, price_native=Decimal("150"),
                price_inr=Decimal("150"), fetched_at=dt.datetime.now(),
            )
        )
        db_session.commit()
        svc.record_price("NIFTY50", dt.date(2024, 1, 1), "20000")
        svc.record_price("NIFTY50", dt.date(2025, 1, 1), "24000")
        result = svc.compare(dt.date(2024, 1, 1), dt.date(2025, 1, 1))
        assert result.portfolio_xirr_pct is not None
        names = {b.name for b in result.benchmarks}
        assert "NIFTY50" in names

    def test_compare_no_snapshots(self, svc):
        result = svc.compare(dt.date(2024, 1, 1), dt.date(2025, 1, 1))
        assert result.benchmarks == []
        assert result.portfolio_xirr_pct is None
