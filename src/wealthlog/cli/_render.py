"""Shared CLI rendering helpers (rich tables, INR/percent formatting)."""

from __future__ import annotations

from decimal import Decimal

from rich.console import Console
from rich.table import Table

console = Console()


def fmt_inr(amount: Decimal | None) -> str:
    """Format a Decimal as an INR string with thousands separators."""
    if amount is None:
        return "—"
    return f"₹{amount:,.2f}"


def fmt_pct(value: Decimal | None) -> str:
    """Format a Decimal percentage (already in percent units) with a sign."""
    if value is None:
        return "—"
    return f"{value:+.2f}%"


def fmt_ratio_as_pct(rate: Decimal | None) -> str:
    """Format a ratio (e.g. 0.0997) as a percentage string (9.97%)."""
    if rate is None:
        return "—"
    return f"{rate * Decimal(100):+.2f}%"


def make_table(title: str, columns: list[str]) -> Table:
    """Create a rich table with a title and right-aligned numeric look."""
    table = Table(title=title, header_style="bold cyan")
    for col in columns:
        justify = "right" if col != columns[0] else "left"
        table.add_column(col, justify=justify)
    return table
