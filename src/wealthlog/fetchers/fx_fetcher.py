"""USD→INR (and general) FX fetcher backed by the free frankfurter.app API."""

from __future__ import annotations

import datetime as dt

import httpx

from wealthlog.config import get_config
from wealthlog.constants import FRANKFURTER_BASE_URL
from wealthlog.fetchers.base import FetchError, FxQuote
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_fx

logger = get_logger(__name__)


class FrankfurterFetcher:
    """Fetch a latest FX rate from ``api.frankfurter.app/latest``.

    Args:
        client: Optional pre-configured ``httpx.Client`` (injected in tests).
        base_url: Override the API base URL.
    """

    def __init__(
        self, client: httpx.Client | None = None, base_url: str = FRANKFURTER_BASE_URL
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    def get_rate(self, base: str, quote: str) -> FxQuote:
        """Return the latest exchange rate for ``base`` → ``quote``.

        Args:
            base: Base currency code (e.g. ``"USD"``).
            quote: Quote currency code (e.g. ``"INR"``).

        Returns:
            An :class:`FxQuote` with the rate and fetch timestamp.

        Raises:
            FetchError: On network errors or a missing/invalid rate.
        """
        url = f"{self._base_url}/latest"
        params = {"from": base, "to": quote}
        try:
            client = self._client or httpx.Client(timeout=get_config().http_timeout_seconds)
            close = self._client is None
            try:
                response = client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
            finally:
                if close:
                    client.close()
        except (httpx.HTTPError, ValueError) as exc:
            raise FetchError(f"frankfurter request failed for {base}->{quote}: {exc}") from exc

        rates = payload.get("rates") or {}
        if quote not in rates:
            raise FetchError(f"frankfurter returned no rate for {base}->{quote}")
        rate = to_fx(str(rates[quote]))
        logger.debug("Fetched FX %s->%s = %s", base, quote, rate)
        return FxQuote(pair=f"{base}_{quote}", rate=rate, as_of=dt.datetime.now())
