"""Shared CLI rendering helpers (rich tables, INR/percent formatting, machine output)."""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from enum import Enum, StrEnum

from rich.console import Console
from rich.table import Table

console = Console()


class OutputFormat(StrEnum):
    """Output format for read commands (``--format``)."""

    table = "table"
    json = "json"
    csv = "csv"


def _jsonable(value: object) -> object:
    """Recursively coerce a value to JSON/CSV-friendly primitives."""
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)  # Decimal-safe: never lose precision to float
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dt.date | dt.datetime):
        return value.isoformat()
    return value


def _to_records(obj: object) -> object:
    """Normalise dataclasses / SQLModel rows (and lists of them) to plain dicts."""
    def one(o: object) -> object:
        if is_dataclass(o) and not isinstance(o, type):
            return asdict(o)
        if hasattr(o, "model_dump"):  # pydantic / SQLModel rows
            return o.model_dump()
        return o

    if isinstance(obj, list | tuple):
        return [_jsonable(one(o)) for o in obj]
    return _jsonable(one(obj))


def emit(obj: object, fmt: OutputFormat) -> None:
    """Print ``obj`` as JSON or CSV (pipe-friendly, no rich markup).

    JSON preserves structure; CSV flattens each record's top-level fields (nested
    lists/dicts are JSON-encoded in their cell). Used by read commands when
    ``--format`` is not ``table``.
    """
    payload = _to_records(obj)
    if fmt is OutputFormat.json:
        print(json.dumps(payload, indent=2))
        return
    # CSV
    rows = payload if isinstance(payload, list) else [payload]
    if not rows:
        return
    fieldnames = list(rows[0].keys()) if isinstance(rows[0], dict) else ["value"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        if not isinstance(row, dict):
            row = {"value": row}
        writer.writerow(
            {k: (json.dumps(v) if isinstance(v, list | dict) else v) for k, v in row.items()}
        )
    print(buf.getvalue(), end="")


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
