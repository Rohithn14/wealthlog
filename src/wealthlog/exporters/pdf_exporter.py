"""PDF report generation using fpdf2 (pure-Python, no system libraries).

Core fonts are latin-1 only, so INR amounts are prefixed with ``Rs`` rather than the
``₹`` glyph to avoid font embedding.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

from wealthlog.services.results import Holding, NetWorth, PnL


def _rs(amount: Decimal | None) -> str:
    if amount is None:
        return "-"
    return f"Rs {amount:,.2f}"


class _ReportPdf(FPDF):
    def header(self) -> None:  # pragma: no cover - layout glue
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "wealthlog - Portfolio & Net Worth Report", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(180, 180, 180)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)

    def footer(self) -> None:  # pragma: no cover - layout glue
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _table(
    pdf: FPDF, header: Sequence[str], rows: Sequence[Sequence[str]], widths: Sequence[int]
) -> None:
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for label, width in zip(header, widths, strict=True):
        pdf.cell(width, 7, label, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for row in rows:
        for value, width in zip(row, widths, strict=True):
            pdf.cell(width, 6, str(value), border=1)
        pdf.ln()


def build_pdf_report(
    path: str | Path,
    *,
    net_worth: NetWorth,
    holdings: Sequence[Holding],
    pnl: PnL,
    portfolio_xirr: Decimal | None,
    generated_at: dt.datetime | None = None,
) -> Path:
    """Render a formatted PDF report with net-worth and portfolio summaries.

    Args:
        path: Destination ``.pdf`` path.
        net_worth: Net-worth snapshot to summarise.
        holdings: Current holdings to list.
        pnl: Portfolio-wide P&L.
        portfolio_xirr: Portfolio XIRR ratio (or ``None`` if undefined).
        generated_at: Report timestamp (defaults to now).

    Returns:
        The path written to.
    """
    generated_at = generated_at or dt.datetime.now()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    pdf = _ReportPdf()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Generated: {generated_at:%Y-%m-%d %H:%M}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"As of: {net_worth.as_of}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Net worth summary.
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Net Worth", new_x="LMARGIN", new_y="NEXT")
    nw_rows = [
        (c.asset_type.value, _rs(c.market_value_inr), f"{c.pct_of_total:.1f}%")
        for c in net_worth.by_asset_class
    ]
    nw_rows.append(("TOTAL", _rs(net_worth.net_worth_inr), "100.0%"))
    _table(pdf, ["Asset class", "Value", "Share"], nw_rows, [70, 60, 40])
    pdf.ln(4)

    # Portfolio P&L.
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Portfolio Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pct = f"{pnl.pnl_pct:+.2f}%" if pnl.pnl_pct is not None else "-"
    xirr_txt = f"{portfolio_xirr * Decimal(100):+.2f}%" if portfolio_xirr is not None else "-"
    pdf.cell(0, 6, f"Invested: {_rs(pnl.invested_inr)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Market value: {_rs(pnl.market_value_inr)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"P&L: {_rs(pnl.pnl_abs_inr)} ({pct})", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Portfolio XIRR: {xirr_txt}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Holdings.
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Holdings", new_x="LMARGIN", new_y="NEXT")
    h_rows = [
        (
            h.symbol,
            h.asset_type.value,
            f"{h.units:g}",
            _rs(h.invested_inr),
            _rs(h.market_value_inr),
            _rs(h.pnl_abs_inr),
        )
        for h in holdings
    ]
    _table(
        pdf,
        ["Symbol", "Type", "Units", "Invested", "Value", "P&L"],
        h_rows or [("-", "-", "-", "-", "-", "-")],
        [32, 26, 22, 32, 32, 32],
    )

    pdf.output(str(out))
    return out
