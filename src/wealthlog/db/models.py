"""SQLModel table definitions for wealthlog.

All monetary values are stored in INR as exact Decimals (via
:class:`wealthlog.db.types.DecimalText`). Investment transactions additionally
record the native-currency price and the FX rate used, for auditability. Dates are
stored as ISO ``YYYY-MM-DD`` (SQLAlchemy ``Date``); cache timestamps as datetimes.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from wealthlog.constants import (
    FX_QUANTET,
    MONEY_QUANTET,
    PRICE_QUANTET,
    UNITS_QUANTET,
    AssetType,
    CategoryType,
    CompoundingFrequency,
    TransactionType,
)
from wealthlog.db.types import DecimalText


class Account(SQLModel, table=True):
    """A bank or demat account used to group expenses and holdings."""

    __tablename__ = "accounts"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    type: str | None = None  # e.g. "bank", "demat", "wallet"
    institution: str | None = None
    notes: str | None = None


class Category(SQLModel, table=True):
    """An expense or income category."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", "type", name="uq_category_name_type"),)

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    type: CategoryType = Field(default=CategoryType.EXPENSE)
    color: str | None = None
    icon: str | None = None


class Expense(SQLModel, table=True):
    """A single dated expense in INR."""

    __tablename__ = "expenses"

    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    amount_inr: Decimal = Field(sa_column=Column(DecimalText(MONEY_QUANTET), nullable=False))
    category_id: int | None = Field(default=None, foreign_key="categories.id", index=True)
    subcategory: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    account_id: int | None = Field(default=None, foreign_key="accounts.id", index=True)


class Budget(SQLModel, table=True):
    """A per-category monthly spending limit (INR)."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("category_id", "month", "year", name="uq_budget_category_month_year"),
    )

    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="categories.id", index=True)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=1900)
    limit_amount_inr: Decimal = Field(
        sa_column=Column(DecimalText(MONEY_QUANTET), nullable=False)
    )


class Investment(SQLModel, table=True):
    """An investment holding (stock, MF, gold ETF, or FD)."""

    __tablename__ = "investments"

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)  # ticker, MF scheme code, or FD label
    name: str
    asset_type: AssetType = Field(index=True)
    currency_native: str = "INR"
    exchange: str | None = None  # e.g. "NSE", "NASDAQ"


class Transaction(SQLModel, table=True):
    """A buy/sell/dividend/SIP event against an investment.

    ``amount_inr`` is the total INR cash flow; ``price_per_unit`` and
    ``fx_rate_used`` are stored in native currency for audit.
    """

    __tablename__ = "transactions"

    id: int | None = Field(default=None, primary_key=True)
    investment_id: int = Field(foreign_key="investments.id", index=True)
    date: dt.date = Field(index=True)
    type: TransactionType = Field(index=True)
    units: Decimal = Field(sa_column=Column(DecimalText(UNITS_QUANTET), nullable=False))
    price_per_unit: Decimal = Field(
        sa_column=Column(DecimalText(PRICE_QUANTET), nullable=False)
    )
    amount_inr: Decimal = Field(sa_column=Column(DecimalText(MONEY_QUANTET), nullable=False))
    fx_rate_used: Decimal | None = Field(
        default=None, sa_column=Column(DecimalText(FX_QUANTET), nullable=True)
    )
    notes: str | None = None


class PriceCache(SQLModel, table=True):
    """A cached latest price for an investment, in native currency and INR."""

    __tablename__ = "prices_cache"

    id: int | None = Field(default=None, primary_key=True)
    investment_id: int = Field(foreign_key="investments.id", index=True)
    price_native: Decimal = Field(
        sa_column=Column(DecimalText(PRICE_QUANTET), nullable=False)
    )
    price_inr: Decimal = Field(sa_column=Column(DecimalText(PRICE_QUANTET), nullable=False))
    fx_rate_used: Decimal | None = Field(
        default=None, sa_column=Column(DecimalText(FX_QUANTET), nullable=True)
    )
    fetched_at: dt.datetime = Field(index=True)


class FxRate(SQLModel, table=True):
    """A cached FX rate for a currency pair (e.g. USD_INR)."""

    __tablename__ = "fx_rates"

    id: int | None = Field(default=None, primary_key=True)
    currency_pair: str = Field(index=True)
    rate: Decimal = Field(sa_column=Column(DecimalText(FX_QUANTET), nullable=False))
    fetched_at: dt.datetime = Field(index=True)


class FdDetails(SQLModel, table=True):
    """Fixed-deposit parameters for an FD-type investment (value is computed, not fetched)."""

    __tablename__ = "fd_details"

    id: int | None = Field(default=None, primary_key=True)
    investment_id: int = Field(foreign_key="investments.id", unique=True, index=True)
    principal: Decimal = Field(sa_column=Column(DecimalText(MONEY_QUANTET), nullable=False))
    interest_rate: Decimal = Field(
        sa_column=Column(DecimalText(PRICE_QUANTET), nullable=False)
    )  # annual %, e.g. 7.1000
    start_date: dt.date
    maturity_date: dt.date
    compounding: CompoundingFrequency = Field(default=CompoundingFrequency.QUARTERLY)
