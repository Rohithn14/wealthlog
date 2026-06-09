"""Unit tests for the raw market-data fetchers (HTTP mocked, yfinance patched)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import httpx
import pytest
import respx

from wealthlog.constants import FRANKFURTER_BASE_URL, MFAPI_BASE_URL
from wealthlog.fetchers.base import FetchError
from wealthlog.fetchers.fx_fetcher import FrankfurterFetcher
from wealthlog.fetchers.mfapi_fetcher import MfApiFetcher
from wealthlog.fetchers.yfinance_fetcher import YFinanceFetcher


class TestMfApiFetcher:
    @respx.mock
    def test_parses_latest_nav(self):
        respx.get(f"{MFAPI_BASE_URL}/120503").mock(
            return_value=httpx.Response(
                200,
                json={
                    "meta": {"scheme_name": "Axis Bluechip"},
                    "data": [
                        {"date": "07-06-2026", "nav": "65.4321"},
                        {"date": "06-06-2026", "nav": "65.0000"},
                    ],
                },
            )
        )
        quote = MfApiFetcher().get_nav("120503")
        assert quote.nav == Decimal("65.4321")
        assert quote.nav_date == dt.date(2026, 6, 7)
        assert quote.scheme_name == "Axis Bluechip"

    @respx.mock
    def test_empty_data_raises(self):
        respx.get(f"{MFAPI_BASE_URL}/999").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        with pytest.raises(FetchError):
            MfApiFetcher().get_nav("999")

    @respx.mock
    def test_http_error_raises(self):
        respx.get(f"{MFAPI_BASE_URL}/500").mock(return_value=httpx.Response(500))
        with pytest.raises(FetchError):
            MfApiFetcher().get_nav("500")

    @respx.mock
    def test_malformed_nav_raises(self):
        respx.get(f"{MFAPI_BASE_URL}/1").mock(
            return_value=httpx.Response(200, json={"data": [{"date": "bad", "nav": "x"}]})
        )
        with pytest.raises(FetchError):
            MfApiFetcher().get_nav("1")


class TestFrankfurterFetcher:
    @respx.mock
    def test_parses_rate(self):
        respx.get(f"{FRANKFURTER_BASE_URL}/latest").mock(
            return_value=httpx.Response(200, json={"rates": {"INR": 83.25}})
        )
        quote = FrankfurterFetcher().get_rate("USD", "INR")
        assert quote.rate == Decimal("83.250000")
        assert quote.pair == "USD_INR"

    @respx.mock
    def test_missing_rate_raises(self):
        respx.get(f"{FRANKFURTER_BASE_URL}/latest").mock(
            return_value=httpx.Response(200, json={"rates": {}})
        )
        with pytest.raises(FetchError):
            FrankfurterFetcher().get_rate("USD", "INR")

    @respx.mock
    def test_network_error_raises(self):
        respx.get(f"{FRANKFURTER_BASE_URL}/latest").mock(
            side_effect=httpx.ConnectError("boom")
        )
        with pytest.raises(FetchError):
            FrankfurterFetcher().get_rate("USD", "INR")

    @respx.mock
    def test_follows_redirect(self):
        # Guards against the api.frankfurter.app -> .dev 301 migration breaking fetches.
        respx.get(f"{FRANKFURTER_BASE_URL}/latest").mock(
            return_value=httpx.Response(301, headers={"Location": "https://redirected/final"})
        )
        respx.get("https://redirected/final").mock(
            return_value=httpx.Response(200, json={"rates": {"INR": 84.0}})
        )
        quote = FrankfurterFetcher().get_rate("USD", "INR")
        assert quote.rate == Decimal("84.000000")


class TestYFinanceFetcher:
    def test_get_price_inr(self, monkeypatch):
        f = YFinanceFetcher()
        monkeypatch.setattr(f, "_raw_quote", lambda s: (1523.45, "INR"))
        quote = f.get_price("INFY.NS")
        assert quote.price == Decimal("1523.4500")
        assert quote.currency == "INR"

    def test_get_price_usd(self, monkeypatch):
        f = YFinanceFetcher()
        monkeypatch.setattr(f, "_raw_quote", lambda s: (190.25, "USD"))
        quote = f.get_price("AAPL")
        assert quote.currency == "USD"

    def test_zero_price_raises(self, monkeypatch):
        f = YFinanceFetcher()
        monkeypatch.setattr(f, "_raw_quote", lambda s: (0.0, "INR"))
        with pytest.raises(FetchError):
            f.get_price("DEAD.NS")

    def test_exception_wrapped(self, monkeypatch):
        f = YFinanceFetcher()

        def boom(_):
            raise RuntimeError("yahoo down")

        monkeypatch.setattr(f, "_raw_quote", boom)
        with pytest.raises(FetchError):
            f.get_price("X")

    def test_nan_price_raises_fetch_error(self, monkeypatch):
        # Bug #7b: yfinance can return NaN; it must be rejected before Decimal
        # conversion (Decimal("NaN") <= 0 raises InvalidOperation, not FetchError).
        f = YFinanceFetcher()
        monkeypatch.setattr(f, "_raw_quote", lambda s: (float("nan"), "INR"))
        with pytest.raises(FetchError):
            f.get_price("BROKEN.NS")

    def test_inf_price_raises_fetch_error(self, monkeypatch):
        f = YFinanceFetcher()
        monkeypatch.setattr(f, "_raw_quote", lambda s: (float("inf"), "INR"))
        with pytest.raises(FetchError):
            f.get_price("BROKEN.NS")

    def test_attribute_only_fast_info(self, monkeypatch):
        # Bug #7a: attribute-style fast_info uses snake_case `last_price`.
        import yfinance as yf

        class AttrFastInfo:  # attribute access only, no .get
            last_price = 1234.5
            currency = "INR"

        class FakeTicker:
            def __init__(self, symbol):
                self.fast_info = AttrFastInfo()

        monkeypatch.setattr(yf, "Ticker", FakeTicker)
        quote = YFinanceFetcher().get_price("INFY.NS")
        assert quote.price == Decimal("1234.5000")
        assert quote.currency == "INR"

    def test_dict_style_camelcase_fast_info(self, monkeypatch):
        # Bug #7a: dict-style fast_info exposes camelCase `lastPrice`, not snake_case.
        import yfinance as yf

        fast_info = {"lastPrice": 999.0, "currency": "USD"}

        class FakeTicker:
            def __init__(self, symbol):
                self.fast_info = fast_info

        monkeypatch.setattr(yf, "Ticker", FakeTicker)
        quote = YFinanceFetcher().get_price("AAPL")
        assert quote.price == Decimal("999.0000")
        assert quote.currency == "USD"
