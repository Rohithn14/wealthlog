"""Portfolio concentration analysis (Milestone B4).

Reports the most concentrated single holdings and weights by sector and asset
class, flagging positions above a configurable threshold (default 10%). Built on
top of :class:`PortfolioService` market values, so FDs and priced holdings are
included at their current valuation.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlmodel import Session

from wealthlog.db.models import Investment
from wealthlog.money import to_money
from wealthlog.services.portfolio import PortfolioService
from wealthlog.services.results import ConcentrationReport, ConcentrationRow, WeightRow

_ZERO = Decimal("0.00")
_DEFAULT_THRESHOLD = Decimal("10")


class ConcentrationService:
    """Compute single-name, sector, and asset-class concentration.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def concentration_report(
        self,
        top_n: int = 10,
        threshold_pct: Decimal | int | str = _DEFAULT_THRESHOLD,
        as_of: dt.date | None = None,
    ) -> ConcentrationReport:
        """Build a concentration report from current holdings.

        Args:
            top_n: Number of largest holdings to return.
            threshold_pct: Single-holding weight above which to flag concentration.
            as_of: Valuation date (defaults to today).

        Returns:
            A :class:`ConcentrationReport`. With no holdings, totals are zero and
            all lists are empty.
        """
        threshold = Decimal(str(threshold_pct))
        holdings = PortfolioService(self.session).get_holdings(as_of=as_of)
        total = to_money(sum((h.market_value_inr for h in holdings), _ZERO))
        if total <= 0:
            return ConcentrationReport(
                total_value_inr=_ZERO, threshold_pct=threshold,
                top_holdings=[], by_sector=[], by_asset_class=[],
            )

        def pct(value: Decimal) -> Decimal:
            return to_money(value / total * Decimal(100))

        ranked = sorted(holdings, key=lambda h: h.market_value_inr, reverse=True)
        top_holdings = [
            ConcentrationRow(
                symbol=h.symbol,
                name=h.name,
                market_value_inr=h.market_value_inr,
                pct_of_total=pct(h.market_value_inr),
                is_concentrated=pct(h.market_value_inr) > threshold,
            )
            for h in ranked[:top_n]
        ]

        sector_totals: dict[str, Decimal] = defaultdict(lambda: _ZERO)
        class_totals: dict[str, Decimal] = defaultdict(lambda: _ZERO)
        for h in holdings:
            inv = self.session.get(Investment, h.investment_id)
            sector = (inv.sector if inv and inv.sector else "Unclassified")
            sector_totals[sector] += h.market_value_inr
            class_totals[h.asset_type.value] += h.market_value_inr

        by_sector = self._weight_rows(sector_totals, pct)
        by_asset_class = self._weight_rows(class_totals, pct)
        return ConcentrationReport(
            total_value_inr=total,
            threshold_pct=threshold,
            top_holdings=top_holdings,
            by_sector=by_sector,
            by_asset_class=by_asset_class,
        )

    @staticmethod
    def _weight_rows(totals: dict[str, Decimal], pct) -> list[WeightRow]:
        rows = [
            WeightRow(label=label, market_value_inr=to_money(value), pct_of_total=pct(value))
            for label, value in totals.items()
        ]
        rows.sort(key=lambda r: r.market_value_inr, reverse=True)
        return rows
