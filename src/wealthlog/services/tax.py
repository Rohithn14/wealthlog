"""Indian capital-gains report via FIFO lot matching (Milestone B2).

Average-cost holdings stay as-is for display; this engine re-derives FIFO lots
from the transaction log so each SELL is matched against the oldest open buy
lots. Gains are classified long/short-term by holding period and summarised per
financial year (April–March).

INFORMATIONAL ONLY — not tax advice. Post-July-2024 equity rates are applied;
gold/debt and grandfathering (pre-2018 equity) are out of scope. Verify with a CA.
"""

from __future__ import annotations

import datetime as dt
from collections import deque
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.constants import (
    EQUITY_LONG_TERM_DAYS,
    INFLOW_TRANSACTION_TYPES,
    LTCG_EXEMPTION_INR,
    LTCG_RATE,
    STCG_RATE,
    AssetType,
    TransactionType,
)
from wealthlog.db.models import Investment, Transaction
from wealthlog.money import to_money
from wealthlog.services.results import CapitalGainsReport, GainRow

_ZERO = Decimal("0.00")


def financial_year_bounds(fy: str) -> tuple[dt.date, dt.date]:
    """Return (start, end) dates for an Indian FY string like ``"2025-26"``.

    Raises:
        ValueError: If the string is malformed.
    """
    try:
        start_year_s, end_part = fy.split("-")
        start_year = int(start_year_s)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Bad financial year '{fy}'; expected e.g. '2025-26'") from exc
    if len(end_part) == 2:
        end_year = start_year - (start_year % 100) + int(end_part)
    else:
        end_year = int(end_part)
    if end_year != start_year + 1:
        raise ValueError(f"Financial year '{fy}' must span consecutive years")
    return dt.date(start_year, 4, 1), dt.date(end_year, 3, 31)


class _Lot:
    """An open buy lot: remaining units carry a per-unit INR cost."""

    __slots__ = ("date", "units", "cost_per_unit")

    def __init__(self, date: dt.date, units: Decimal, cost_per_unit: Decimal) -> None:
        self.date = date
        self.units = units
        self.cost_per_unit = cost_per_unit


class TaxService:
    """Compute realised capital gains by FIFO lot matching.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def _matched_gains(self) -> list[GainRow]:
        """FIFO-match every SELL against prior buy lots, across all investments."""
        rows: list[GainRow] = []
        investments = self.session.exec(
            select(Investment).where(Investment.asset_type != AssetType.FD)
        ).all()
        for inv in investments:
            txns = self.session.exec(
                select(Transaction).where(Transaction.investment_id == inv.id)
            ).all()
            # Chronological; buys before sells on the same day so a same-day sell matches.
            ordered = sorted(
                txns, key=lambda t: (t.date, 0 if t.type in INFLOW_TRANSACTION_TYPES else 1)
            )
            lots: deque[_Lot] = deque()
            for t in ordered:
                if t.type in INFLOW_TRANSACTION_TYPES:
                    if t.units > 0:
                        lots.append(_Lot(t.date, t.units, t.amount_inr / t.units))
                elif t.type == TransactionType.SELL:
                    rows.extend(self._match_sell(inv, t, lots))
            # DIVIDEND ignored — not a disposal.
        return rows

    def _match_sell(
        self, inv: Investment, sell: Transaction, lots: deque[_Lot]
    ) -> list[GainRow]:
        rows: list[GainRow] = []
        remaining = sell.units
        proceeds_per_unit = sell.amount_inr / sell.units if sell.units > 0 else _ZERO
        while remaining > 0 and lots:
            lot = lots[0]
            take = min(remaining, lot.units)
            cost = take * lot.cost_per_unit
            proceeds = take * proceeds_per_unit
            holding_days = (sell.date - lot.date).days
            is_long = holding_days >= EQUITY_LONG_TERM_DAYS
            rows.append(
                GainRow(
                    symbol=inv.symbol,
                    asset_type=inv.asset_type,
                    buy_date=lot.date,
                    sell_date=sell.date,
                    units=take,
                    cost_basis_inr=to_money(cost),
                    proceeds_inr=to_money(proceeds),
                    gain_inr=to_money(proceeds - cost),
                    holding_days=holding_days,
                    is_long_term=is_long,
                )
            )
            lot.units -= take
            remaining -= take
            if lot.units <= 0:
                lots.popleft()
        return rows

    def capital_gains_report(self, fy: str) -> CapitalGainsReport:
        """Build a FIFO capital-gains report for an Indian financial year.

        Args:
            fy: Financial year string, e.g. ``"2025-26"`` (1 Apr 2025 – 31 Mar 2026).

        Returns:
            A :class:`CapitalGainsReport` covering disposals settled within the FY.
        """
        start, end = financial_year_bounds(fy)
        rows = [r for r in self._matched_gains() if start <= r.sell_date <= end]
        rows.sort(key=lambda r: (r.sell_date, r.symbol))

        stcg = to_money(sum((r.gain_inr for r in rows if not r.is_long_term), _ZERO))
        ltcg = to_money(sum((r.gain_inr for r in rows if r.is_long_term), _ZERO))
        taxable_ltcg = max(_ZERO, ltcg - LTCG_EXEMPTION_INR)
        est_stcg_tax = to_money(max(_ZERO, stcg) * STCG_RATE)
        est_ltcg_tax = to_money(taxable_ltcg * LTCG_RATE)
        return CapitalGainsReport(
            financial_year=fy,
            rows=rows,
            short_term_gain_inr=stcg,
            long_term_gain_inr=ltcg,
            ltcg_exemption_inr=LTCG_EXEMPTION_INR,
            taxable_ltcg_inr=to_money(taxable_ltcg),
            estimated_stcg_tax_inr=est_stcg_tax,
            estimated_ltcg_tax_inr=est_ltcg_tax,
        )
