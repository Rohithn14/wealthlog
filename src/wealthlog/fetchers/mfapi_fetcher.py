"""Indian mutual-fund NAV fetcher backed by the free mfapi.in REST API."""

from __future__ import annotations

import datetime as dt

import httpx

from wealthlog.config import get_config
from wealthlog.constants import MFAPI_BASE_URL
from wealthlog.fetchers.base import FetchError, NavQuote
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_price

logger = get_logger(__name__)


class MfApiFetcher:
    """Fetch latest NAV for a scheme code from ``api.mfapi.in/mf/{code}``.

    Args:
        client: Optional pre-configured ``httpx.Client`` (injected in tests).
        base_url: Override the API base URL.
    """

    def __init__(
        self, client: httpx.Client | None = None, base_url: str = MFAPI_BASE_URL
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    def get_nav(self, scheme_code: str) -> NavQuote:
        """Return the latest NAV for a mutual-fund scheme code.

        Args:
            scheme_code: The mfapi.in scheme code (e.g. ``"120503"``).

        Returns:
            A :class:`NavQuote` with the latest NAV and its publication date.

        Raises:
            FetchError: On network errors, missing data, or unparseable NAV.
        """
        url = f"{self._base_url}/{scheme_code}"
        try:
            client = self._client or httpx.Client(timeout=get_config().http_timeout_seconds)
            close = self._client is None
            try:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()
            finally:
                if close:
                    client.close()
        except (httpx.HTTPError, ValueError) as exc:
            raise FetchError(f"mfapi request failed for {scheme_code}: {exc}") from exc

        data = payload.get("data") or []
        if not data:
            raise FetchError(f"mfapi returned no NAV data for {scheme_code}")
        latest = data[0]
        try:
            nav = to_price(latest["nav"])
            nav_date = dt.datetime.strptime(latest["date"], "%d-%m-%Y").date()
        except (KeyError, ValueError) as exc:
            raise FetchError(f"mfapi NAV parse error for {scheme_code}: {exc}") from exc

        scheme_name = (payload.get("meta") or {}).get("scheme_name")
        logger.debug("Fetched NAV %s for scheme %s (%s)", nav, scheme_code, nav_date)
        return NavQuote(
            scheme_code=scheme_code, nav=nav, nav_date=nav_date, scheme_name=scheme_name
        )
