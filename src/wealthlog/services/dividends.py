"""Dividend analytics over DIVIDEND transactions (Milestone B5).

DIVIDEND rows already exist in the transaction log (recorded as cash inflows with
zero units); this service aggregates them and derives trailing yield. No schema
change is required.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.constants import AssetType, TransactionType
from wealthlog.db.models import Investment, Transaction
from wealthlog.money import to_money
from wealthlog.services.portfolio import PortfolioService
from wealthlog.services.results import DividendRow

_ZERO = Decimal("0.00")


class DividendService:
    """Aggregate dividends by year/holding and compute trailing yield.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def _dividend_txns(self) -> list[Transaction]:
        return list(
            self.session.exec(
                select(Transaction).where(Transaction.type == TransactionType.DIVIDEND)
            ).all()
        )

    def total_by_year(self) -> dict[int, Decimal]:
        """Total dividends received per calendar year (INR), newest first."""
        totals: dict[int, Decimal] = defaultdict(lambda: _ZERO)
        for t in self._dividend_txns():
            totals[t.date.year] += t.amount_inr
        return {year: to_money(amt) for year, amt in sorted(totals.items(), reverse=True)}

    def total_by_holding(self, year: int | None = None) -> list[DividendRow]:
        """Per-investment dividend totals, optionally filtered to one year.

        Returns:
            One :class:`DividendRow` per investment that paid a dividend, sorted
            by amount descending.
        """
        by_inv: dict[int, Decimal] = defaultdict(lambda: _ZERO)
        for t in self._dividend_txns():
            if year is not None and t.date.year != year:
                continue
            by_inv[t.investment_id] += t.amount_inr
        rows: list[DividendRow] = []
        for inv_id, amount in by_inv.items():
            inv = self.session.get(Investment, inv_id)
            if inv is None:
                continue
            rows.append(
                DividendRow(
                    investment_id=inv_id,
                    symbol=inv.symbol,
                    name=inv.name,
                    total_inr=to_money(amount),
                    trailing_yield_pct=self.trailing_yield(inv_id),
                )
            )
        rows.sort(key=lambda r: r.total_inr, reverse=True)
        return rows

    def trailing_yield(
        self, investment_id: int, as_of: dt.date | None = None
    ) -> Decimal | None:
        """Trailing-12-month dividends as a percentage of current market value.

        Returns ``None`` when the holding has no current market value (e.g. fully
        exited or unpriced), since yield is then undefined.
        """
        as_of = as_of or dt.date.today()
        one_year_ago = as_of.replace(year=as_of.year - 1)
        ttm = sum(
            (
                t.amount_inr
                for t in self._dividend_txns()
                if t.investment_id == investment_id and one_year_ago < t.date <= as_of
            ),
            _ZERO,
        )
        if ttm == 0:
            return _ZERO
        inv = self.session.get(Investment, investment_id)
        if inv is None or inv.asset_type == AssetType.FD:
            return None
        holding = next(
            (
                h
                for h in PortfolioService(self.session).get_holdings(as_of=as_of)
                if h.investment_id == investment_id
            ),
            None,
        )
        if holding is None or holding.market_value_inr <= 0:
            return None
        return to_money(ttm / holding.market_value_inr * Decimal(100))
