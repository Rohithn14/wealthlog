"""Net-worth aggregation across asset classes.

v1 has no liabilities model, so total liabilities are zero and net worth equals total
investment assets (valued in INR). ``historical_net_worth`` returns a cost-basis series
(cumulative net invested per month), since true historical market values would require
historical price data that wealthlog does not store in v1.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.constants import INFLOW_TRANSACTION_TYPES, AssetType, TransactionType
from wealthlog.db.models import FdDetails, Investment, Transaction
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_money
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

        liabilities = _ZERO
        return NetWorth(
            as_of=as_of,
            total_assets_inr=total_assets,
            total_liabilities_inr=liabilities,
            net_worth_inr=to_money(total_assets - liabilities),
            by_asset_class=breakdown,
        )

    def historical_net_worth(
        self, start: dt.date, end: dt.date
    ) -> list[NetWorthPoint]:
        """Return cumulative net-invested capital at each month-end in a range.

        This is a cost-basis proxy for net worth over time (market history is not
        stored in v1). FD principal counts from its start date; investment buys add
        and sells subtract their INR amounts.

        Args:
            start: Range start (inclusive month).
            end: Range end (inclusive month).

        Returns:
            One :class:`NetWorthPoint` per month from ``start`` to ``end``.

        Raises:
            ValueError: If ``end`` precedes ``start``.
        """
        if end < start:
            raise ValueError("end must not precede start")

        # Gather dated capital movements.
        movements: list[tuple[dt.date, Decimal]] = []
        for t in self.session.exec(select(Transaction)).all():
            if t.type in INFLOW_TRANSACTION_TYPES:
                movements.append((t.date, t.amount_inr))
            elif t.type == TransactionType.SELL:
                movements.append((t.date, -t.amount_inr))
        for inv in self.session.exec(
            select(Investment).where(Investment.asset_type == AssetType.FD)
        ).all():
            details = self.session.exec(
                select(FdDetails).where(FdDetails.investment_id == inv.id)
            ).first()
            if details is not None:
                movements.append((details.start_date, details.principal))

        points: list[NetWorthPoint] = []
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            cutoff = _month_end(year, month)
            invested = to_money(
                sum((amt for d, amt in movements if d <= cutoff), _ZERO)
            )
            points.append(NetWorthPoint(year=year, month=month, invested_inr=invested))
            month += 1
            if month > 12:
                month = 1
                year += 1
        return points


def _month_end(year: int, month: int) -> dt.date:
    import calendar

    return dt.date(year, month, calendar.monthrange(year, month)[1])
