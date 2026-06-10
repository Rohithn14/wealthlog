"""SQLModel table definitions for wealthlog.

All monetary values are stored in INR as exact Decimals (via
:class:`wealthlog.db.types.DecimalText`). Investment transactions additionally
record the native-currency price and the FX rate used, for auditability. Dates are
stored as ISO ``YYYY-MM-DD`` (SQLAlchemy ``Date``); cache timestamps as datetimes.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from wealthlog.constants import (
    FX_QUANTET,
    MONEY_QUANTET,
    PRICE_QUANTET,
    UNITS_QUANTET,
    AlertKind,
    AssetType,
    CategoryType,
    CompoundingFrequency,
    RecurrenceFrequency,
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
    # Composite serves BudgetService._spent (filters on category_id + date range).
    # DecimalText stores TEXT, so sign checks cast to REAL (precision irrelevant here).
    __table_args__ = (
        Index("ix_expenses_category_date", "category_id", "date"),
        CheckConstraint("CAST(amount_inr AS REAL) > 0", name="ck_expense_amount_pos"),
    )

    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    amount_inr: Decimal = Field(sa_column=Column(DecimalText(MONEY_QUANTET), nullable=False))
    category_id: int | None = Field(default=None, foreign_key="categories.id", index=True)
    subcategory: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    account_id: int | None = Field(default=None, foreign_key="accounts.id", index=True)


class Income(SQLModel, table=True):
    """A single dated income entry in INR (salary, dividend payout, interest…)."""

    __tablename__ = "incomes"

    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    amount_inr: Decimal = Field(sa_column=Column(DecimalText(MONEY_QUANTET), nullable=False))
    category_id: int | None = Field(default=None, foreign_key="categories.id", index=True)
    source: str | None = None  # e.g. employer, broker, bank
    description: str | None = None
    account_id: int | None = Field(default=None, foreign_key="accounts.id", index=True)


class RecurringExpense(SQLModel, table=True):
    """A rule that materialises an :class:`Expense` on a fixed cadence."""

    __tablename__ = "recurring_expenses"

    id: int | None = Field(default=None, primary_key=True)
    amount_inr: Decimal = Field(sa_column=Column(DecimalText(MONEY_QUANTET), nullable=False))
    category_id: int | None = Field(default=None, foreign_key="categories.id", index=True)
    frequency: RecurrenceFrequency = Field(default=RecurrenceFrequency.MONTHLY)
    day_of_month: int | None = None  # MONTHLY only; clamped to month length
    description: str | None = None
    active: bool = Field(default=True)
    #: Watermark: expenses up to and including this date have been generated.
    last_generated: dt.date | None = None


class Budget(SQLModel, table=True):
    """A per-category monthly spending limit (INR)."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("category_id", "month", "year", name="uq_budget_category_month_year"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_budget_month_range"),
        CheckConstraint(
            "CAST(limit_amount_inr AS REAL) > 0", name="ck_budget_limit_pos"
        ),
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
    sector: str | None = None  # e.g. "IT", "Banking" — for concentration analysis


class Transaction(SQLModel, table=True):
    """A buy/sell/dividend/SIP event against an investment.

    ``amount_inr`` is the total INR cash flow; ``price_per_unit`` and
    ``fx_rate_used`` are stored in native currency for audit.
    """

    __tablename__ = "transactions"
    # Serves _market_holding and per-investment date-ranged queries.
    __table_args__ = (
        Index("ix_transactions_inv_date", "investment_id", "date"),
        CheckConstraint("CAST(units AS REAL) >= 0", name="ck_transaction_units_nonneg"),
        CheckConstraint(
            "CAST(price_per_unit AS REAL) >= 0", name="ck_transaction_price_nonneg"
        ),
    )

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
    # Makes the latest-price lookup (WHERE investment_id ORDER BY fetched_at) an
    # index scan with no sort step.
    __table_args__ = (Index("ix_prices_cache_inv_fetched", "investment_id", "fetched_at"),)

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


class PriceSnapshot(SQLModel, table=True):
    """One closing INR price per investment per day, for historical valuation."""

    __tablename__ = "price_snapshots"
    __table_args__ = (
        UniqueConstraint("investment_id", "date", name="uq_price_snapshot_investment_date"),
    )

    id: int | None = Field(default=None, primary_key=True)
    investment_id: int = Field(foreign_key="investments.id", index=True)
    date: dt.date = Field(index=True)
    price_inr: Decimal = Field(sa_column=Column(DecimalText(PRICE_QUANTET), nullable=False))
    source: str = "fetch"  # "yfinance" | "mfapi" | "manual"


class SIPSchedule(SQLModel, table=True):
    """An expected monthly SIP instalment against an investment."""

    __tablename__ = "sip_schedules"

    id: int | None = Field(default=None, primary_key=True)
    investment_id: int = Field(foreign_key="investments.id", index=True)
    amount_inr: Decimal = Field(sa_column=Column(DecimalText(MONEY_QUANTET), nullable=False))
    day_of_month: int = Field(ge=1, le=31)
    start_date: dt.date
    end_date: dt.date | None = None
    active: bool = Field(default=True)


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
    __table_args__ = (
        CheckConstraint("CAST(principal AS REAL) > 0", name="ck_fd_principal_pos"),
        CheckConstraint("maturity_date >= start_date", name="ck_fd_maturity_after_start"),
    )

    id: int | None = Field(default=None, primary_key=True)
    investment_id: int = Field(foreign_key="investments.id", unique=True, index=True)
    principal: Decimal = Field(sa_column=Column(DecimalText(MONEY_QUANTET), nullable=False))
    interest_rate: Decimal = Field(
        sa_column=Column(DecimalText(PRICE_QUANTET), nullable=False)
    )  # annual %, e.g. 7.1000
    start_date: dt.date
    maturity_date: dt.date
    compounding: CompoundingFrequency = Field(default=CompoundingFrequency.QUARTERLY)


class AlertRule(SQLModel, table=True):
    """A user-defined condition evaluated by the alerts watcher (C3)."""

    __tablename__ = "alert_rules"

    id: int | None = Field(default=None, primary_key=True)
    kind: AlertKind = Field(index=True)
    threshold: Decimal | None = Field(
        default=None, sa_column=Column(DecimalText(PRICE_QUANTET), nullable=True)
    )
    investment_id: int | None = Field(default=None, foreign_key="investments.id", index=True)
    category_id: int | None = Field(default=None, foreign_key="categories.id", index=True)
    active: bool = Field(default=True)


class AlertEvent(SQLModel, table=True):
    """A fired alert, kept for same-day de-duplication and history."""

    __tablename__ = "alert_events"

    id: int | None = Field(default=None, primary_key=True)
    rule_id: int = Field(foreign_key="alert_rules.id", index=True)
    fired_on: dt.date = Field(index=True)
    message: str
