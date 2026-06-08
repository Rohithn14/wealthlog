"""Export service: CSV (raw data) and PDF (formatted report)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from sqlmodel import Session, select

from wealthlog.db.models import Category, Investment, Transaction
from wealthlog.exporters.csv_exporter import write_csv
from wealthlog.exporters.pdf_exporter import build_pdf_report
from wealthlog.logging_conf import get_logger
from wealthlog.services.expense import ExpenseService
from wealthlog.services.networth import NetWorthService
from wealthlog.services.portfolio import PortfolioService

logger = get_logger(__name__)

CSV_KINDS = ("expenses", "transactions", "holdings")


class ExportService:
    """Produce CSV extracts and PDF reports from stored data.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def export_csv(self, kind: str, path: str | Path) -> Path:
        """Export a dataset to CSV.

        Args:
            kind: One of ``"expenses"``, ``"transactions"``, ``"holdings"``.
            path: Destination CSV path.

        Returns:
            The path written to.

        Raises:
            ValueError: If ``kind`` is not recognised.
        """
        if kind == "expenses":
            return self._export_expenses(path)
        if kind == "transactions":
            return self._export_transactions(path)
        if kind == "holdings":
            return self._export_holdings(path)
        raise ValueError(f"Unknown export kind '{kind}'. Choose from {CSV_KINDS}.")

    def _export_expenses(self, path: str | Path) -> Path:
        rows = []
        for e in ExpenseService(self.session).list_expenses():
            cat = self.session.get(Category, e.category_id) if e.category_id else None
            rows.append(
                [
                    e.id, e.date.isoformat(), e.amount_inr,
                    cat.name if cat else "", e.subcategory or "",
                    e.description or "", ";".join(e.tags),
                ]
            )
        return write_csv(
            path,
            ["id", "date", "amount_inr", "category", "subcategory", "description", "tags"],
            rows,
        )

    def _export_transactions(self, path: str | Path) -> Path:
        rows = []
        statement = select(Transaction, Investment).join(
            Investment, Transaction.investment_id == Investment.id
        ).order_by(Transaction.date)
        for txn, inv in self.session.exec(statement).all():
            rows.append(
                [
                    txn.id, txn.date.isoformat(), inv.symbol, inv.asset_type.value,
                    txn.type.value, txn.units, txn.price_per_unit, txn.amount_inr,
                    txn.fx_rate_used if txn.fx_rate_used is not None else "",
                    txn.notes or "",
                ]
            )
        return write_csv(
            path,
            [
                "id", "date", "symbol", "asset_type", "type", "units",
                "price_per_unit", "amount_inr", "fx_rate_used", "notes",
            ],
            rows,
        )

    def _export_holdings(self, path: str | Path, as_of: dt.date | None = None) -> Path:
        rows = []
        for h in PortfolioService(self.session).get_holdings(as_of=as_of):
            rows.append(
                [
                    h.symbol, h.asset_type.value, h.units, h.invested_inr,
                    h.current_price_inr, h.market_value_inr, h.pnl_abs_inr,
                    h.pnl_pct if h.pnl_pct is not None else "",
                    "stale" if h.price_is_stale else "live",
                ]
            )
        return write_csv(
            path,
            [
                "symbol", "asset_type", "units", "invested_inr", "current_price_inr",
                "market_value_inr", "pnl_abs_inr", "pnl_pct", "price_status",
            ],
            rows,
        )

    def export_pdf_report(self, path: str | Path, as_of: dt.date | None = None) -> Path:
        """Export a formatted PDF report (net worth + portfolio summary).

        Args:
            path: Destination ``.pdf`` path.
            as_of: Valuation date (defaults to today).

        Returns:
            The path written to.
        """
        portfolio = PortfolioService(self.session)
        net_worth = NetWorthService(self.session).calculate_net_worth(as_of)
        holdings = portfolio.get_holdings(as_of=as_of)
        pnl = portfolio.get_pnl(as_of=as_of)
        xirr = portfolio.calculate_xirr(as_of=as_of)
        out = build_pdf_report(
            path,
            net_worth=net_worth,
            holdings=holdings,
            pnl=pnl,
            portfolio_xirr=xirr,
        )
        logger.info("Wrote PDF report to %s", out)
        return out
