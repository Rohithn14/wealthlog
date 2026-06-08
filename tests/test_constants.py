"""Tests for enums and constant invariants."""

from __future__ import annotations

from decimal import Decimal

from wealthlog.constants import (
    COMPOUNDING_PERIODS_PER_YEAR,
    FX_QUANTET,
    INFLOW_TRANSACTION_TYPES,
    MONEY_QUANTET,
    PRICE_QUANTET,
    YFINANCE_ASSET_TYPES,
    AssetType,
    CategoryType,
    CompoundingFrequency,
    TransactionType,
)


class TestEnums:
    def test_asset_types_are_strings(self):
        assert AssetType.STOCK_IN.value == "STOCK_IN"
        assert isinstance(AssetType.MF, str)

    def test_all_asset_types_present(self):
        assert {a.value for a in AssetType} == {
            "STOCK_IN",
            "STOCK_US",
            "MF",
            "GOLD_ETF",
            "FD",
        }

    def test_transaction_types(self):
        assert {t.value for t in TransactionType} == {"BUY", "SELL", "DIVIDEND", "SIP"}

    def test_category_types(self):
        assert {c.value for c in CategoryType} == {"EXPENSE", "INCOME"}


class TestInflowTypes:
    def test_buy_and_sip_are_inflows(self):
        assert TransactionType.BUY in INFLOW_TRANSACTION_TYPES
        assert TransactionType.SIP in INFLOW_TRANSACTION_TYPES

    def test_sell_and_dividend_not_inflows(self):
        assert TransactionType.SELL not in INFLOW_TRANSACTION_TYPES
        assert TransactionType.DIVIDEND not in INFLOW_TRANSACTION_TYPES


class TestYfinanceAssetTypes:
    def test_equities_and_gold_use_yfinance(self):
        assert AssetType.STOCK_IN in YFINANCE_ASSET_TYPES
        assert AssetType.STOCK_US in YFINANCE_ASSET_TYPES
        assert AssetType.GOLD_ETF in YFINANCE_ASSET_TYPES

    def test_mf_and_fd_excluded(self):
        assert AssetType.MF not in YFINANCE_ASSET_TYPES
        assert AssetType.FD not in YFINANCE_ASSET_TYPES


class TestCompounding:
    def test_every_frequency_mapped(self):
        for freq in CompoundingFrequency:
            assert freq in COMPOUNDING_PERIODS_PER_YEAR

    def test_simple_is_none(self):
        assert COMPOUNDING_PERIODS_PER_YEAR[CompoundingFrequency.SIMPLE] is None

    def test_periods_values(self):
        assert COMPOUNDING_PERIODS_PER_YEAR[CompoundingFrequency.ANNUAL] == 1
        assert COMPOUNDING_PERIODS_PER_YEAR[CompoundingFrequency.QUARTERLY] == 4
        assert COMPOUNDING_PERIODS_PER_YEAR[CompoundingFrequency.MONTHLY] == 12


class TestQuantizers:
    def test_decimal_places(self):
        assert MONEY_QUANTET == Decimal("0.01")
        assert PRICE_QUANTET == Decimal("0.0001")
        assert FX_QUANTET == Decimal("0.000001")
