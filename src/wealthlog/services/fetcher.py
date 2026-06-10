"""Cache-aware market-data service.

Wraps the raw fetchers with TTL caching (``prices_cache`` / ``fx_rates`` tables),
INR conversion for USD assets, and manual-fallback semantics. Fetchers are injected,
so the whole service is testable without network access.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.config import get_config
from wealthlog.constants import INR, USD, AssetType
from wealthlog.db.models import FxRate, Investment, PriceCache, PriceSnapshot
from wealthlog.fetchers.base import (
    FetchError,
    FxFetcher,
    NavFetcher,
    PriceFetcher,
)
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_money, to_price

logger = get_logger(__name__)


@dataclass
class RefreshResult:
    """Outcome of a :meth:`FetcherService.refresh_prices` run."""

    updated: list[str] = field(default_factory=list)
    skipped_fresh: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


class FetcherService:
    """Fetch and cache prices, NAVs, and FX rates.

    Args:
        session: An open database session.
        price_fetcher: Equity/ETF price source (defaults to yfinance).
        nav_fetcher: Mutual-fund NAV source (defaults to mfapi.in).
        fx_fetcher: FX source (defaults to frankfurter.app).
    """

    def __init__(
        self,
        session: Session,
        price_fetcher: PriceFetcher | None = None,
        nav_fetcher: NavFetcher | None = None,
        fx_fetcher: FxFetcher | None = None,
    ) -> None:
        self.session = session
        self._price_fetcher = price_fetcher
        self._nav_fetcher = nav_fetcher
        self._fx_fetcher = fx_fetcher
        self._ttl = get_config().cache_ttl

    # ------------------------------------------------------------ lazy fetchers

    @property
    def price_fetcher(self) -> PriceFetcher:
        if self._price_fetcher is None:
            from wealthlog.fetchers.yfinance_fetcher import YFinanceFetcher

            self._price_fetcher = YFinanceFetcher()
        return self._price_fetcher

    @property
    def nav_fetcher(self) -> NavFetcher:
        if self._nav_fetcher is None:
            from wealthlog.fetchers.mfapi_fetcher import MfApiFetcher

            self._nav_fetcher = MfApiFetcher()
        return self._nav_fetcher

    @property
    def fx_fetcher(self) -> FxFetcher:
        if self._fx_fetcher is None:
            from wealthlog.fetchers.fx_fetcher import FrankfurterFetcher

            self._fx_fetcher = FrankfurterFetcher()
        return self._fx_fetcher

    # --------------------------------------------------------------------- FX

    def _latest_fx_row(self, pair: str) -> FxRate | None:
        return self.session.exec(
            select(FxRate).where(FxRate.currency_pair == pair).order_by(FxRate.fetched_at.desc())
        ).first()

    def get_fx_rate(
        self, base: str = USD, quote: str = INR, force: bool = False
    ) -> tuple[Decimal, dt.datetime]:
        """Return ``(rate, fetched_at)`` for a currency pair, using the cache.

        Fresh cached rates (within the FX TTL) are returned directly. Otherwise a new
        rate is fetched and cached; if the fetch fails, the most recent cached rate is
        used as a fallback.

        Args:
            base: Base currency (default USD).
            quote: Quote currency (default INR).
            force: If ``True``, bypass the freshness check and fetch.

        Returns:
            A tuple of the Decimal rate and the timestamp it was fetched.

        Raises:
            FetchError: If no cached rate exists and the live fetch fails.
        """
        pair = f"{base}_{quote}"
        cached = self._latest_fx_row(pair)
        if not force and cached is not None and not self._is_stale(
            cached.fetched_at, self._ttl.fx_rate
        ):
            return cached.rate, cached.fetched_at

        try:
            quote_data = self.fx_fetcher.get_rate(base, quote)
        except FetchError:
            if cached is not None:
                logger.warning(
                    "FX fetch failed for %s; using cached rate from %s", pair, cached.fetched_at
                )
                return cached.rate, cached.fetched_at
            raise
        row = FxRate(currency_pair=pair, rate=quote_data.rate, fetched_at=quote_data.as_of)
        self.session.add(row)
        self.session.commit()
        return quote_data.rate, quote_data.as_of

    # -------------------------------------------------------------------- NAV

    def get_mf_nav(self, scheme_code: str, force: bool = False) -> Decimal:
        """Return the latest NAV for a scheme code (INR), using cached price rows.

        Args:
            scheme_code: mfapi.in scheme code.
            force: Bypass freshness check.

        Returns:
            The NAV as a Decimal (INR per unit).

        Raises:
            FetchError: If the scheme is unknown locally and the live fetch fails.
        """
        inv = self.session.exec(
            select(Investment).where(
                Investment.symbol == scheme_code, Investment.asset_type == AssetType.MF
            )
        ).first()
        if inv is not None:
            cached = self._latest_price_row(inv.id)
            if not force and cached is not None and not self._is_stale(
                cached.fetched_at, self._ttl.mf_nav
            ):
                return cached.price_inr
        nav = self.nav_fetcher.get_nav(scheme_code)
        if inv is not None:
            self._store_price(inv.id, nav.nav, nav.nav, None)
        return nav.nav

    # ----------------------------------------------------------------- prices

    def _latest_price_row(self, investment_id: int) -> PriceCache | None:
        return self.session.exec(
            select(PriceCache)
            .where(PriceCache.investment_id == investment_id)
            .order_by(PriceCache.fetched_at.desc())
        ).first()

    def _store_price(
        self,
        investment_id: int,
        price_native: Decimal,
        price_inr: Decimal,
        fx_rate_used: Decimal | None,
        source: str = "fetch",
    ) -> PriceCache:
        row = PriceCache(
            investment_id=investment_id,
            price_native=to_price(price_native),
            price_inr=to_price(price_inr),
            fx_rate_used=fx_rate_used,
            fetched_at=dt.datetime.now(),
        )
        self.session.add(row)
        self._upsert_snapshot(investment_id, to_price(price_inr), source)
        self.session.commit()
        return row

    def _upsert_snapshot(self, investment_id: int, price_inr: Decimal, source: str) -> None:
        """Record today's closing price (one snapshot per investment per day)."""
        today = dt.date.today()
        existing = self.session.exec(
            select(PriceSnapshot).where(
                PriceSnapshot.investment_id == investment_id,
                PriceSnapshot.date == today,
            )
        ).first()
        if existing is not None:
            existing.price_inr = price_inr
            existing.source = source
            self.session.add(existing)
        else:
            self.session.add(
                PriceSnapshot(
                    investment_id=investment_id, date=today, price_inr=price_inr, source=source
                )
            )

    def refresh_prices(self, force: bool = False) -> RefreshResult:
        """Refresh cached prices for every non-FD investment.

        For USD assets the native price is converted to INR via the cached/live FX
        rate, and the rate used is stored for audit. Fresh prices (within the asset's
        TTL) are skipped unless ``force`` is set. Per-symbol failures are collected and
        do not abort the run.

        Args:
            force: Refresh even if a cached price is still fresh.

        Returns:
            A :class:`RefreshResult` summarising updated / skipped / failed symbols.
        """
        result = RefreshResult()
        investments = self.session.exec(
            select(Investment).where(Investment.asset_type != AssetType.FD)
        ).all()
        for inv in investments:
            cached = self._latest_price_row(inv.id)
            ttl = self._ttl.for_asset(inv.asset_type)
            if not force and cached is not None and not self._is_stale(cached.fetched_at, ttl):
                result.skipped_fresh.append(inv.symbol)
                continue
            try:
                self._refresh_one(inv)
                result.updated.append(inv.symbol)
            except FetchError as exc:
                logger.warning("Price refresh failed for %s: %s", inv.symbol, exc)
                result.failed.append((inv.symbol, str(exc)))
        return result

    def _refresh_one(self, inv: Investment) -> PriceCache:
        if inv.asset_type == AssetType.MF:
            nav = self.nav_fetcher.get_nav(inv.symbol)
            return self._store_price(inv.id, nav.nav, nav.nav, None)

        quote = self.price_fetcher.get_price(inv.symbol)
        if inv.currency_native == USD or quote.currency == USD:
            fx_rate, _ = self.get_fx_rate(USD, INR)
            price_inr = to_price(quote.price * fx_rate)
            return self._store_price(inv.id, quote.price, price_inr, fx_rate)
        return self._store_price(inv.id, quote.price, quote.price, None)

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _is_stale(fetched_at: dt.datetime, ttl: dt.timedelta) -> bool:
        return (dt.datetime.now() - fetched_at) > ttl

    def set_manual_price(
        self, investment_id: int, price_inr: Decimal | int | str
    ) -> PriceCache:
        """Manually record an INR price for an investment (override / fallback).

        Args:
            investment_id: Target investment.
            price_inr: The price in INR to store as the latest cached price.

        Returns:
            The stored :class:`PriceCache` row.
        """
        money = to_money(price_inr)
        return self._store_price(investment_id, money, money, None)
