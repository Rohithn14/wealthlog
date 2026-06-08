"""Fetcher protocols and shared types.

Fetchers are thin wrappers over external data sources that return Decimal-precise
quotes. They never touch the database; caching and persistence live in
:class:`wealthlog.services.fetcher.FetcherService`. Any network/parse failure raises
:class:`FetchError` so callers can fall back to manual prices.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class FetchError(Exception):
    """Raised when a market-data source fails or returns unusable data."""


@dataclass(frozen=True)
class PriceQuote:
    """A native-currency price quote for a symbol."""

    symbol: str
    price: Decimal
    currency: str
    as_of: dt.datetime


@dataclass(frozen=True)
class NavQuote:
    """An Indian mutual-fund NAV quote (published end-of-day)."""

    scheme_code: str
    nav: Decimal
    nav_date: dt.date
    scheme_name: str | None = None


@dataclass(frozen=True)
class FxQuote:
    """A foreign-exchange rate quote for a currency pair."""

    pair: str
    rate: Decimal
    as_of: dt.datetime


class PriceFetcher(Protocol):
    """Fetches a latest price for an exchange-listed symbol."""

    def get_price(self, symbol: str) -> PriceQuote: ...


class NavFetcher(Protocol):
    """Fetches the latest NAV for an Indian mutual-fund scheme code."""

    def get_nav(self, scheme_code: str) -> NavQuote: ...


class FxFetcher(Protocol):
    """Fetches a latest FX rate for a currency pair."""

    def get_rate(self, base: str, quote: str) -> FxQuote: ...
