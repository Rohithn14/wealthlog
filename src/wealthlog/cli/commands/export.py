"""`wealthlog-cli export` commands."""

from __future__ import annotations

from typing import Annotated

import typer

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import console
from wealthlog.services.export import CSV_KINDS, ExportService

app = typer.Typer(help="Export data to CSV / PDF.", no_args_is_help=True)


@app.command("csv")
def export_csv(
    kind: Annotated[str, typer.Argument(help=f"One of: {', '.join(CSV_KINDS)}")],
    path: Annotated[str, typer.Option("--out", "-o", help="Output .csv path")],
) -> None:
    """Export expenses, transactions, or holdings to CSV."""
    with session_scope() as session:
        try:
            out = ExportService(session).export_csv(kind, path)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from None
        console.print(f"[green]Wrote {kind} CSV:[/green] {out}")


@app.command("pdf")
def export_pdf(
    path: Annotated[str, typer.Option("--out", "-o", help="Output .pdf path")],
) -> None:
    """Export a formatted PDF report (net worth + portfolio summary)."""
    with session_scope() as session:
        out = ExportService(session).export_pdf_report(path)
        console.print(f"[green]Wrote PDF report:[/green] {out}")
