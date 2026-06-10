"""Benchmark index comparison (Milestone B1).

Each benchmark is a pseudo-:class:`Investment` of type ``BENCHMARK`` that carries
no transactions — so it is naturally excluded from holdings, net worth, and tax
(all transaction-driven) while still accruing :class:`PriceSnapshot` rows through
the normal price-refresh path. Benchmark returns are computed from those snapshots
and compared against the portfolio's XIRR over the same window.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.constants import BENCHMARKS, AssetType
from wealthlog.db.models import Investment, PriceSnapshot
from wealthlog.money import to_money, to_price
from wealthlog.services.portfolio import PortfolioService
from wealthlog.services.results import BenchmarkComparison, BenchmarkReturn

_ZERO = Decimal("0.00")
_DAYS_PER_YEAR = Decimal("365")


class BenchmarkService:
    """Manage benchmark pseudo-investments and compute index returns.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, name: str) -> Investment:
        """Return (creating if needed) the pseudo-investment for a benchmark name.

        Raises:
            ValueError: If ``name`` is not a known benchmark.
        """
        key = name.upper()
        if key not in BENCHMARKS:
            raise ValueError(f"Unknown benchmark '{name}'; known: {', '.join(BENCHMARKS)}")
        display, symbol, currency = BENCHMARKS[key]
        existing = self.session.exec(
            select(Investment).where(
                Investment.symbol == symbol, Investment.asset_type == AssetType.BENCHMARK
            )
        ).first()
        if existing is not None:
            return existing
        inv = Investment(
            symbol=symbol, name=display, asset_type=AssetType.BENCHMARK,
            currency_native=currency,
        )
        self.session.add(inv)
        self.session.commit()
        self.session.refresh(inv)
        return inv

    def record_price(
        self, name: str, date: dt.date, price_inr: Decimal | int | str
    ) -> PriceSnapshot:
        """Upsert a benchmark price snapshot (one per benchmark per day)."""
        inv = self.get_or_create(name)
        price = to_price(price_inr)
        existing = self.session.exec(
            select(PriceSnapshot).where(
                PriceSnapshot.investment_id == inv.id, PriceSnapshot.date == date
            )
        ).first()
        if existing is not None:
            existing.price_inr = price
            existing.source = "benchmark"
            self.session.add(existing)
            snap = existing
        else:
            snap = PriceSnapshot(
                investment_id=inv.id, date=date, price_inr=price, source="benchmark"
            )
            self.session.add(snap)
        self.session.commit()
        self.session.refresh(snap)
        return snap

    def benchmark_return(
        self, name: str, start: dt.date, end: dt.date
    ) -> BenchmarkReturn | None:
        """Return a benchmark's growth between the snapshots bounding [start, end].

        Uses the earliest snapshot on/after ``start`` and the latest on/before
        ``end``. Returns ``None`` if fewer than two snapshots fall in the window.
        """
        if end < start:
            raise ValueError("end must not precede start")
        key = name.upper()
        display = BENCHMARKS.get(key, (name, name, "INR"))[0]
        inv = self.get_or_create(name)
        snaps = self.session.exec(
            select(PriceSnapshot)
            .where(PriceSnapshot.investment_id == inv.id)
            .order_by(PriceSnapshot.date)
        ).all()
        in_window = [s for s in snaps if start <= s.date <= end]
        if len(in_window) < 2:
            return None
        first, last = in_window[0], in_window[-1]
        if first.price_inr <= 0:
            return None
        total = (last.price_inr - first.price_inr) / first.price_inr * Decimal(100)
        days = (last.date - first.date).days
        cagr = None
        if days >= 1:
            ratio = last.price_inr / first.price_inr
            years = Decimal(days) / _DAYS_PER_YEAR
            cagr = (_pow(ratio, Decimal(1) / years) - Decimal(1)) * Decimal(100)
        return BenchmarkReturn(
            name=key,
            display_name=display,
            start_date=first.date,
            end_date=last.date,
            start_price=first.price_inr,
            end_price=last.price_inr,
            total_return_pct=to_money(total),
            cagr_pct=to_money(cagr) if cagr is not None else None,
        )

    def compare(
        self, start: dt.date, end: dt.date, names: list[str] | None = None
    ) -> BenchmarkComparison:
        """Compare portfolio XIRR against each benchmark's CAGR over a window."""
        xirr = PortfolioService(self.session).calculate_xirr(as_of=end)
        results: list[BenchmarkReturn] = []
        for name in names or list(BENCHMARKS):
            br = self.benchmark_return(name, start, end)
            if br is not None:
                results.append(br)
        return BenchmarkComparison(
            start_date=start,
            end_date=end,
            portfolio_xirr_pct=to_money(xirr * Decimal(100)) if xirr is not None else None,
            benchmarks=results,
        )


def _pow(base: Decimal, exp: Decimal) -> Decimal:
    """Decimal ``base ** exp`` via float (precision is ample for CAGR display)."""
    return Decimal(str(float(base) ** float(exp)))
