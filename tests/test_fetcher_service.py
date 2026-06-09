"""Tests for FetcherService: caching, INR conversion, fallback, manual override."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlmodel import select

from wealthlog.constants import AssetType, TransactionType
from wealthlog.db.models import FxRate, PriceCache, PriceSnapshot
from wealthlog.fetchers.base import FetchError, FxQuote, NavQuote, PriceQuote
from wealthlog.services.fetcher import FetcherService
from wealthlog.services.portfolio import PortfolioService


class FakePriceFetcher:
    def __init__(self, prices: dict[str, tuple[str, str]], fail: set[str] | None = None):
        self.prices = prices
        self.fail = fail or set()
        self.calls = 0

    def get_price(self, symbol: str) -> PriceQuote:
        self.calls += 1
        if symbol in self.fail:
            raise FetchError(f"fail {symbol}")
        price, currency = self.prices[symbol]
        return PriceQuote(symbol, Decimal(price), currency, dt.datetime.now())


class FakeNavFetcher:
    def __init__(self, navs: dict[str, str]):
        self.navs = navs
        self.calls = 0

    def get_nav(self, scheme_code: str) -> NavQuote:
        self.calls += 1
        return NavQuote(scheme_code, Decimal(self.navs[scheme_code]), dt.date(2026, 6, 7))


class FakeFxFetcher:
    def __init__(self, rate: str = "83", fail: bool = False):
        self.rate = rate
        self.fail = fail
        self.calls = 0

    def get_rate(self, base: str, quote: str) -> FxQuote:
        self.calls += 1
        if self.fail:
            raise FetchError("fx down")
        return FxQuote(f"{base}_{quote}", Decimal(self.rate), dt.datetime.now())


@pytest.fixture
def portfolio(db_session):
    return PortfolioService(db_session)


class TestRefreshPrices:
    def test_inr_stock_stored_as_native(self, db_session, portfolio):
        portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        svc = FetcherService(
            db_session, price_fetcher=FakePriceFetcher({"INFY.NS": ("1500", "INR")})
        )
        result = svc.refresh_prices()
        assert "INFY.NS" in result.updated
        row = db_session.get(PriceCache, 1)
        assert row.price_inr == Decimal("1500.0000")
        assert row.fx_rate_used is None

    def test_us_stock_converted_to_inr(self, db_session, portfolio):
        inv = portfolio.add_investment("AAPL", "Apple", AssetType.STOCK_US, currency_native="USD")
        svc = FetcherService(
            db_session,
            price_fetcher=FakePriceFetcher({"AAPL": ("190", "USD")}),
            fx_fetcher=FakeFxFetcher("83"),
        )
        svc.refresh_prices()
        row = svc._latest_price_row(inv.id)
        assert row.price_native == Decimal("190.0000")
        assert row.price_inr == Decimal("15770.0000")  # 190 * 83
        assert row.fx_rate_used == Decimal("83.000000")

    def test_mf_uses_nav(self, db_session, portfolio):
        inv = portfolio.add_investment("120503", "Axis MF", AssetType.MF)
        svc = FetcherService(db_session, nav_fetcher=FakeNavFetcher({"120503": "65.43"}))
        svc.refresh_prices()
        row = svc._latest_price_row(inv.id)
        assert row.price_inr == Decimal("65.4300")

    def test_fd_skipped(self, db_session, portfolio):
        portfolio.add_fd("FD", "1000", "7", dt.date(2024, 1, 1), dt.date(2025, 1, 1))
        svc = FetcherService(db_session, price_fetcher=FakePriceFetcher({}))
        result = svc.refresh_prices()
        assert result.updated == []

    def test_fresh_skipped(self, db_session, portfolio):
        portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        fetcher = FakePriceFetcher({"INFY.NS": ("1500", "INR")})
        svc = FetcherService(db_session, price_fetcher=fetcher)
        svc.refresh_prices()
        result = svc.refresh_prices()  # second run within TTL
        assert "INFY.NS" in result.skipped_fresh
        assert fetcher.calls == 1

    def test_force_refetches(self, db_session, portfolio):
        portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        fetcher = FakePriceFetcher({"INFY.NS": ("1500", "INR")})
        svc = FetcherService(db_session, price_fetcher=fetcher)
        svc.refresh_prices()
        svc.refresh_prices(force=True)
        assert fetcher.calls == 2

    def test_failure_collected(self, db_session, portfolio):
        portfolio.add_investment("BAD.NS", "Bad", AssetType.STOCK_IN)
        svc = FetcherService(
            db_session, price_fetcher=FakePriceFetcher({}, fail={"BAD.NS"})
        )
        result = svc.refresh_prices()
        assert result.updated == []
        assert result.failed and result.failed[0][0] == "BAD.NS"

    def test_stale_refetched(self, db_session, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        # Seed a stale price (2 days old).
        db_session.add(
            PriceCache(
                investment_id=inv.id, price_native=Decimal("1000"), price_inr=Decimal("1000"),
                fetched_at=dt.datetime.now() - dt.timedelta(days=2),
            )
        )
        db_session.commit()
        fetcher = FakePriceFetcher({"INFY.NS": ("1500", "INR")})
        svc = FetcherService(db_session, price_fetcher=fetcher)
        result = svc.refresh_prices()
        assert "INFY.NS" in result.updated
        assert fetcher.calls == 1


class TestFxCaching:
    def test_first_call_fetches_and_stores(self, db_session):
        fx = FakeFxFetcher("83.5")
        svc = FetcherService(db_session, fx_fetcher=fx)
        rate, _ = svc.get_fx_rate()
        assert rate == Decimal("83.500000")
        assert fx.calls == 1
        assert db_session.exec(select(FxRate)).first() is not None

    def test_second_call_uses_cache(self, db_session):
        fx = FakeFxFetcher("83.5")
        svc = FetcherService(db_session, fx_fetcher=fx)
        svc.get_fx_rate()
        svc.get_fx_rate()
        assert fx.calls == 1

    def test_force_refetches(self, db_session):
        fx = FakeFxFetcher("83.5")
        svc = FetcherService(db_session, fx_fetcher=fx)
        svc.get_fx_rate()
        svc.get_fx_rate(force=True)
        assert fx.calls == 2

    def test_fallback_to_cache_on_failure(self, db_session):
        # Seed a stale cached rate, then fail the live fetch -> should reuse cache.
        db_session.add(
            FxRate(currency_pair="USD_INR", rate=Decimal("80"),
                   fetched_at=dt.datetime.now() - dt.timedelta(days=2))
        )
        db_session.commit()
        svc = FetcherService(db_session, fx_fetcher=FakeFxFetcher(fail=True))
        rate, _ = svc.get_fx_rate()
        assert rate == Decimal("80.000000")

    def test_failure_no_cache_raises(self, db_session):
        svc = FetcherService(db_session, fx_fetcher=FakeFxFetcher(fail=True))
        with pytest.raises(FetchError):
            svc.get_fx_rate()


class TestNavAndManual:
    def test_get_mf_nav_caches(self, db_session, portfolio):
        portfolio.add_investment("120503", "Axis MF", AssetType.MF)
        nav = FakeNavFetcher({"120503": "65.43"})
        svc = FetcherService(db_session, nav_fetcher=nav)
        assert svc.get_mf_nav("120503") == Decimal("65.4300")
        svc.get_mf_nav("120503")  # cached
        assert nav.calls == 1

    def test_set_manual_price(self, db_session, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        svc = FetcherService(db_session)
        row = svc.set_manual_price(inv.id, "1234.56")
        assert row.price_inr == Decimal("1234.5600")
        assert svc._latest_price_row(inv.id).price_inr == Decimal("1234.5600")

    def test_manual_price_feeds_holdings(self, db_session, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(
            inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "1000",
        )
        FetcherService(db_session).set_manual_price(inv.id, "1500")
        holding = portfolio.get_holdings()[0]
        assert holding.market_value_inr == Decimal("15000.00")
        assert holding.price_is_stale is False


class TestPriceSnapshots:
    """A3: every stored price also upserts one PriceSnapshot per investment per day."""

    def _snaps(self, session, investment_id):
        return list(
            session.exec(
                select(PriceSnapshot).where(PriceSnapshot.investment_id == investment_id)
            ).all()
        )

    def test_refresh_creates_snapshot(self, db_session, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        svc = FetcherService(
            db_session, price_fetcher=FakePriceFetcher({"INFY.NS": ("1500", "INR")})
        )
        svc.refresh_prices()
        snaps = self._snaps(db_session, inv.id)
        assert len(snaps) == 1
        assert snaps[0].date == dt.date.today()
        assert snaps[0].price_inr == Decimal("1500.0000")

    def test_us_stock_snapshot_in_inr(self, db_session, portfolio):
        inv = portfolio.add_investment("AAPL", "Apple", AssetType.STOCK_US, currency_native="USD")
        svc = FetcherService(
            db_session,
            price_fetcher=FakePriceFetcher({"AAPL": ("190", "USD")}),
            fx_fetcher=FakeFxFetcher("83"),
        )
        svc.refresh_prices()
        snaps = self._snaps(db_session, inv.id)
        assert len(snaps) == 1
        assert snaps[0].price_inr == Decimal("15770.0000")  # 190 * 83

    def test_same_day_upsert_no_duplicate(self, db_session, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        svc = FetcherService(
            db_session, price_fetcher=FakePriceFetcher({"INFY.NS": ("1500", "INR")})
        )
        svc.refresh_prices()
        svc.refresh_prices(force=True)  # second store same day
        snaps = self._snaps(db_session, inv.id)
        assert len(snaps) == 1  # upserted, not appended

    def test_manual_price_creates_snapshot(self, db_session, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        FetcherService(db_session).set_manual_price(inv.id, "1234.56")
        snaps = self._snaps(db_session, inv.id)
        assert len(snaps) == 1
        assert snaps[0].price_inr == Decimal("1234.5600")
