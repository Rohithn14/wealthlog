"""Headless data aggregation for the web/TUI dashboards.

Pure read functions that compose the service layer into render-ready structures.
Kept UI-framework-agnostic so they can be unit-tested without a running server.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from sqlmodel import Session

from wealthlog.services.budget import BudgetService
from wealthlog.services.expense import ExpenseService
from wealthlog.services.networth import NetWorth, NetWorthService
from wealthlog.services.portfolio import PortfolioService
from wealthlog.services.results import BudgetStatus, Holding, PnL


@dataclass(frozen=True)
class DashboardData:
    """Everything the dashboard needs for a single render."""

    as_of: dt.date
    net_worth: NetWorth
    holdings: list[Holding]
    pnl: PnL
    portfolio_xirr: Decimal | None
    month_total_inr: Decimal
    budget_statuses: list[BudgetStatus] = field(default_factory=list)
    overages: list[BudgetStatus] = field(default_factory=list)


def build_dashboard_data(session: Session, as_of: dt.date | None = None) -> DashboardData:
    """Assemble a :class:`DashboardData` snapshot from the services.

    Args:
        session: An open database session.
        as_of: Valuation date (defaults to today).

    Returns:
        A fully-populated dashboard snapshot.
    """
    as_of = as_of or dt.date.today()
    portfolio = PortfolioService(session)
    networth = NetWorthService(session)
    budgets = BudgetService(session)
    expenses = ExpenseService(session)

    net_worth = networth.calculate_net_worth(as_of)
    holdings = portfolio.get_holdings(as_of=as_of)
    pnl = portfolio.get_pnl(as_of=as_of)
    xirr = portfolio.calculate_xirr(as_of=as_of)
    month_summary = expenses.monthly_summary(as_of.year, as_of.month)
    statuses = budgets.get_budget_status(as_of.year, as_of.month)

    return DashboardData(
        as_of=as_of,
        net_worth=net_worth,
        holdings=holdings,
        pnl=pnl,
        portfolio_xirr=xirr,
        month_total_inr=month_summary.total_inr,
        budget_statuses=statuses,
        overages=[s for s in statuses if s.is_over],
    )


def asset_allocation_series(data: DashboardData) -> tuple[list[str], list[float]]:
    """Return ``(labels, values)`` for an asset-allocation pie chart."""
    labels = [c.asset_type.value for c in data.net_worth.by_asset_class]
    values = [float(c.market_value_inr) for c in data.net_worth.by_asset_class]
    return labels, values
