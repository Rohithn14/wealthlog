"""Net-worth aggregation across asset classes.

Net worth = gross investment assets (valued in INR) minus total liabilities (loans,
credit-card balances) tracked by :class:`LiabilityService`.
``historical_net_worth`` returns a cost-basis series
(cumulative net invested per month), since true historical market values would require
historical price data that wealthlog does not store in v1.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.constants import INFLOW_TRANSACTION_TYPES, AssetType, TransactionType
from wealthlog.db.models import FdDetails, Investment, PriceSnapshot, Transaction
from wealthlog.finance.fd import calculate_fd_value
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_money
from wealthlog.services.liability import LiabilityService
from wealthlog.services.portfolio import PortfolioService
from wealthlog.services.results import AssetClassValue, NetWorth, NetWorthPoint

logger = get_logger(__name__)

_ZERO = Decimal("0.00")


class NetWorthService:
    """Compute net worth and historical invested-capital series.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.portfolio = PortfolioService(session)

    def calculate_net_worth(self, as_of: dt.date | None = None) -> NetWorth:
        """Compute net worth as of a date, broken down by asset class.

        Args:
            as_of: Valuation date (defaults to today).

        Returns:
            A :class:`NetWorth` snapshot. Asset classes are sorted by value desc.
        """
        as_of = as_of or dt.date.today()
        holdings = self.portfolio.get_holdings(as_of=as_of)

        by_class: dict[AssetType, Decimal] = defaultdict(lambda: _ZERO)
        for h in holdings:
            by_class[h.asset_type] = to_money(by_class[h.asset_type] + h.market_value_inr)

        total_assets = to_money(sum(by_class.values(), _ZERO))
        breakdown = [
            AssetClassValue(
                asset_type=asset_type,
                market_value_inr=value,
                pct_of_total=(
                    to_money(value / total_assets * Decimal(100)) if total_assets > 0 else _ZERO
                ),
            )
            for asset_type, value in by_class.items()
        ]
        breakdown.sort(key=lambda a: a.market_value_inr, reverse=True)

        liabilities = LiabilityService(self.session).total_liabilities()
        return NetWorth(
            as_of=as_of,
            total_assets_inr=total_assets,
            total_liabilities_inr=liabilities,
            net_worth_inr=to_money(total_assets - liabilities),
            by_asset_class=breakdown,
        )

    def historical_net_worth(
        self, start: dt.date, end: dt.date, mode: str = "cost"
    ) -> list[NetWorthPoint]:
        """Return a month-end net-worth series over a range.

        In ``"cost"`` mode each point is cumulative net-invested capital: FD
        principal counts from its start date; buys add their INR amounts, and sells
        subtract the average cost of the units sold (not the sale proceeds, which
        would let realised profits push the series negative).

        In ``"market"`` mode each point additionally carries ``market_value_inr``:
        units held at month-end valued at the latest :class:`PriceSnapshot` on or
        before that date (FDs valued analytically). Holdings without a snapshot fall
        back to their cost; ``is_market_value`` is True when at least one snapshot
        was used.

        Args:
            start: Range start (inclusive month).
            end: Range end (inclusive month).
            mode: ``"cost"`` (default) or ``"market"``.

        Returns:
            One :class:`NetWorthPoint` per month from ``start`` to ``end``.

        Raises:
            ValueError: If ``end`` precedes ``start`` or ``mode`` is unknown.
        """
        if end < start:
            raise ValueError("end must not precede start")
        if mode not in ("cost", "market"):
            raise ValueError("mode must be 'cost' or 'market'")

        by_investment: dict[int, list[Transaction]] = defaultdict(list)
        for t in self.session.exec(select(Transaction)).all():
            by_investment[t.investment_id].append(t)
        for txns in by_investment.values():
            txns.sort(key=lambda t: (t.date, t.id))

        fd_rows: list[FdDetails] = []
        for inv in self.session.exec(
            select(Investment).where(Investment.asset_type == AssetType.FD)
        ).all():
            details = self.session.exec(
                select(FdDetails).where(FdDetails.investment_id == inv.id)
            ).first()
            if details is not None:
                fd_rows.append(details)

        snapshots: dict[int, list[PriceSnapshot]] = defaultdict(list)
        if mode == "market":
            for snap in self.session.exec(
                select(PriceSnapshot).order_by(PriceSnapshot.date)
            ).all():
                snapshots[snap.investment_id].append(snap)

        points: list[NetWorthPoint] = []
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            cutoff = _month_end(year, month)

            invested = _ZERO
            market = _ZERO
            used_snapshot = False
            for inv_id, txns in by_investment.items():
                held_units, held_cost = _position_at(txns, cutoff)
                invested += held_cost
                if mode == "market" and held_units > 0:
                    snap_price = _latest_snapshot_price(snapshots.get(inv_id, []), cutoff)
                    if snap_price is not None:
                        market += held_units * snap_price
                        used_snapshot = True
                    else:
                        market += held_cost
            for details in fd_rows:
                if details.start_date <= cutoff:
                    invested += details.principal
                    if mode == "market":
                        market += calculate_fd_value(
                            details.principal,
                            details.interest_rate,
                            details.start_date,
                            cutoff,
                            compounding=details.compounding,
                            maturity_date=details.maturity_date,
                        )

            points.append(
                NetWorthPoint(
                    year=year,
                    month=month,
                    invested_inr=to_money(invested),
                    market_value_inr=to_money(market) if mode == "market" else None,
                    is_market_value=used_snapshot,
                )
            )
            month += 1
            if month > 12:
                month = 1
                year += 1
        return points


def _position_at(txns: list[Transaction], cutoff: dt.date) -> tuple[Decimal, Decimal]:
    """Fold date-sorted transactions up to ``cutoff`` into (units, cost) held.

    SELLs release the average cost of the sold units; oversells (legacy data)
    release no further cost.
    """
    held_units = Decimal(0)
    held_cost = Decimal(0)
    for t in txns:
        if t.date > cutoff:
            break
        if t.type in INFLOW_TRANSACTION_TYPES:
            held_units += t.units
            held_cost += t.amount_inr
        elif t.type == TransactionType.SELL and held_units > 0:
            sold = min(t.units, held_units)
            held_cost -= held_cost * sold / held_units
            held_units -= sold
    return held_units, held_cost


def _latest_snapshot_price(snaps: list[PriceSnapshot], cutoff: dt.date) -> Decimal | None:
    """Latest snapshot price on or before ``cutoff`` (snaps are date-sorted)."""
    price: Decimal | None = None
    for snap in snaps:
        if snap.date > cutoff:
            break
        price = snap.price_inr
    return price


def _month_end(year: int, month: int) -> dt.date:
    import calendar

    return dt.date(year, month, calendar.monthrange(year, month)[1])
