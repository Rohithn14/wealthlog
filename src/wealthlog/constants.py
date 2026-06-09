"""Project-wide constants: enums, decimal precision, currencies, and API endpoints.

No magic numbers should live outside this module (or :mod:`wealthlog.config`).
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class AssetType(StrEnum):
    """Supported investment asset classes."""

    STOCK_IN = "STOCK_IN"  # Indian equity (NSE/BSE)
    STOCK_US = "STOCK_US"  # US equity (NYSE/NASDAQ)
    MF = "MF"  # Indian mutual fund
    GOLD_ETF = "GOLD_ETF"  # NSE-listed gold ETF
    FD = "FD"  # Fixed deposit / debt instrument (no live price)


class TransactionType(StrEnum):
    """Investment transaction kinds."""

    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    SIP = "SIP"  # systematic investment plan instalment (treated as a buy)


class CategoryType(StrEnum):
    """Expense/income category classification."""

    EXPENSE = "EXPENSE"
    INCOME = "INCOME"


class CompoundingFrequency(StrEnum):
    """Interest compounding frequency for fixed deposits."""

    SIMPLE = "SIMPLE"
    ANNUAL = "ANNUAL"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"


#: Number of compounding periods per year for each frequency (None == simple interest).
COMPOUNDING_PERIODS_PER_YEAR: dict[CompoundingFrequency, int | None] = {
    CompoundingFrequency.SIMPLE: None,
    CompoundingFrequency.ANNUAL: 1,
    CompoundingFrequency.SEMI_ANNUAL: 2,
    CompoundingFrequency.QUARTERLY: 4,
    CompoundingFrequency.MONTHLY: 12,
}

#: Transaction types that represent capital inflows into a holding (units increase).
INFLOW_TRANSACTION_TYPES: frozenset[TransactionType] = frozenset(
    {TransactionType.BUY, TransactionType.SIP}
)

#: Asset types priced via yfinance.
YFINANCE_ASSET_TYPES: frozenset[AssetType] = frozenset(
    {AssetType.STOCK_IN, AssetType.STOCK_US, AssetType.GOLD_ETF}
)

# --------------------------------------------------------------------------- #
# Currencies
# --------------------------------------------------------------------------- #

INR: str = "INR"
USD: str = "USD"
DEFAULT_DISPLAY_CURRENCY: str = INR
USD_INR_PAIR: str = "USD_INR"

# --------------------------------------------------------------------------- #
# Decimal precision (quantization targets)
# --------------------------------------------------------------------------- #

#: Monetary amounts in INR are rounded to 2 decimal places.
MONEY_QUANTET: Decimal = Decimal("0.01")
#: Per-unit prices (stock price, NAV) carry 4 decimal places.
PRICE_QUANTET: Decimal = Decimal("0.0001")
#: FX rates carry 6 decimal places.
FX_QUANTET: Decimal = Decimal("0.000001")
#: Fractional units (MF units, fractional shares) carry 4 decimal places.
UNITS_QUANTET: Decimal = Decimal("0.0001")

MONEY_DECIMAL_PLACES: int = 2
PRICE_DECIMAL_PLACES: int = 4
FX_DECIMAL_PLACES: int = 6
UNITS_DECIMAL_PLACES: int = 4

# --------------------------------------------------------------------------- #
# yfinance exchange suffixes
# --------------------------------------------------------------------------- #

NSE_SUFFIX: str = ".NS"
BSE_SUFFIX: str = ".BO"

# --------------------------------------------------------------------------- #
# External API endpoints (all free / keyless)
# --------------------------------------------------------------------------- #

MFAPI_BASE_URL: str = "https://api.mfapi.in/mf"
FRANKFURTER_BASE_URL: str = "https://api.frankfurter.dev/v1"

# ISO date format used for all stored dates (YYYY-MM-DD), never unix timestamps.
ISO_DATE_FORMAT: str = "%Y-%m-%d"

#: Days per year used in XIRR / accrual day-count (Actual/365 fixed).
DAYS_PER_YEAR: int = 365
