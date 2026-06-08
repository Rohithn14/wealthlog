"""CSV export helpers (stdlib ``csv``)."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path


def write_csv(path: str | Path, header: Sequence[str], rows: Iterable[Sequence[object]]) -> Path:
    """Write a CSV file with a header row and data rows.

    Args:
        path: Destination file path.
        header: Column names.
        rows: Iterable of row sequences. Values are stringified by the csv writer;
            Decimals are written in their exact canonical form.

    Returns:
        The path written to.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for row in rows:
            writer.writerow(["" if v is None else v for v in row])
    return out
