"""Plain result objects returned by the service layer.

These are read-only value objects (not ORM rows) so the CLI/TUI/UI layers can render
computed summaries without re-querying or knowing the DB schema.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from wealthlog.constants import AssetType


@dataclass(frozen=True)
class MonthlySummary:
    """Aggregated expenses for a single month."""

    year: int
    month: int
    total_inr: Decimal
    count: int
    by_category: dict[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class BudgetStatus:
    """Spending status for one category against its monthly budget."""

    category_id: int
    category_name: str
    month: int
    year: int
    limit_inr: Decimal
    spent_inr: Decimal
    remaining_inr: Decimal
    pct_used: Decimal
    is_over: bool


@dataclass(frozen=True)
class Holding:
    """Current position in a single investment, valued in INR."""

    investment_id: int
    symbol: str
    name: str
    asset_type: AssetType
    units: Decimal
    invested_inr: Decimal
    avg_cost_inr: Decimal | None
    current_price_inr: Decimal | None
    market_value_inr: Decimal
    pnl_abs_inr: Decimal
    pnl_pct: Decimal | None
    price_as_of: dt.datetime | None
    price_is_stale: bool


@dataclass(frozen=True)
class PnL:
    """Profit-and-loss summary for one investment or the whole portfolio."""

    invested_inr: Decimal
    market_value_inr: Decimal
    pnl_abs_inr: Decimal
    pnl_pct: Decimal | None


@dataclass(frozen=True)
class AssetClassValue:
    """Market value of one asset class and its share of the portfolio."""

    asset_type: AssetType
    market_value_inr: Decimal
    pct_of_total: Decimal


@dataclass(frozen=True)
class NetWorth:
    """Net-worth snapshot: assets by class minus liabilities, all in INR."""

    as_of: dt.date
    total_assets_inr: Decimal
    total_liabilities_inr: Decimal
    net_worth_inr: Decimal
    by_asset_class: list[AssetClassValue] = field(default_factory=list)


@dataclass(frozen=True)
class NetWorthPoint:
    """A single point in a historical net-worth (cost-basis) series."""

    year: int
    month: int
    invested_inr: Decimal
