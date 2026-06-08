"""Equity / ETF price fetcher backed by yfinance (Yahoo Finance).

Covers NSE/BSE stocks (``SYMBOL.NS`` / ``SYMBOL.BO``), US stocks (bare ticker), and
NSE-listed gold ETFs (``GOLDBEES.NS``). yfinance is an unofficial scraper, so callers
must treat :class:`FetchError` as expected and fall back to manual prices.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from wealthlog.fetchers.base import FetchError, PriceQuote
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_price

logger = get_logger(__name__)


class YFinanceFetcher:
    """Fetch the latest price for an exchange-listed symbol via yfinance."""

    def _raw_quote(self, symbol: str) -> tuple[float, str]:
        """Return ``(last_price, currency)`` from yfinance (isolated for testing)."""
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        has_get = hasattr(info, "get")
        price = info.get("last_price") if has_get else getattr(info, "last_price", None)
        currency = info.get("currency") if has_get else getattr(info, "currency", None)
        if price is None:
            hist = ticker.history(period="1d")
            if hist.empty:
                raise FetchError(f"yfinance returned no data for {symbol}")
            price = float(hist["Close"].iloc[-1])
        return float(price), (currency or "INR")

    def get_price(self, symbol: str) -> PriceQuote:
        """Return the latest price quote for a symbol.

        Args:
            symbol: yfinance symbol (e.g. ``"INFY.NS"``, ``"AAPL"``, ``"GOLDBEES.NS"``).

        Returns:
            A :class:`PriceQuote` in the symbol's native currency.

        Raises:
            FetchError: If yfinance fails or returns no/zero price.
        """
        try:
            price, currency = self._raw_quote(symbol)
        except FetchError:
            raise
        except Exception as exc:  # noqa: BLE001 - yfinance raises many error types
            raise FetchError(f"yfinance request failed for {symbol}: {exc}") from exc

        quote = to_price(str(price))
        if quote <= Decimal(0):
            raise FetchError(f"yfinance returned non-positive price for {symbol}")
        return PriceQuote(symbol=symbol, price=quote, currency=currency, as_of=dt.datetime.now())
