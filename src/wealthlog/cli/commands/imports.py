"""`wealthlog-cli import` commands — broker statement import (B3)."""

from __future__ import annotations

from typing import Annotated

import typer

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import console, fmt_inr, make_table
from wealthlog.services.importer import ImportService

app = typer.Typer(help="Import transactions from broker statements.", no_args_is_help=True)


def _run(broker: str, path: str, commit: bool) -> None:
    with session_scope() as session:
        svc = ImportService(session)
        try:
            if not commit:
                preview = svc.preview(path, broker)
                table = make_table(
                    f"{broker} import (dry run)",
                    ["Date", "Symbol", "Type", "Units", "Price", "Status"],
                )
                for r in preview.rows:
                    if r.is_duplicate:
                        status = "duplicate"
                    else:
                        status = "new +inv" if r.creates_investment else "new"
                    color = "yellow" if r.is_duplicate else "green"
                    table.add_row(
                        str(r.txn.date), r.txn.symbol, r.txn.type, f"{r.txn.units:g}",
                        fmt_inr(r.txn.price), f"[{color}]{status}[/{color}]",
                    )
                console.print(table)
                console.print(
                    f"[bold]{preview.new_count}[/bold] new, "
                    f"{preview.duplicate_count} duplicate. "
                    "Re-run with --commit to import."
                )
            else:
                result = svc.commit(path, broker)
                console.print(
                    f"[green]Imported {result.imported}[/green], "
                    f"skipped {result.skipped_duplicates} duplicate(s)."
                )
                if result.created_investments:
                    console.print(
                        f"[dim]Created investments: {', '.join(result.created_investments)}[/dim]"
                    )
        except (ValueError, KeyError, FileNotFoundError) as exc:
            console.print(f"[red]Import failed: {exc}[/red]")
            raise typer.Exit(code=1) from exc


@app.command("zerodha")
def zerodha(
    path: Annotated[str, typer.Argument(help="Path to tradebook CSV/XLSX")],
    commit: Annotated[bool, typer.Option("--commit", help="Write transactions")] = False,
) -> None:
    """Import a Zerodha tradebook (dry run by default)."""
    _run("zerodha", path, commit)


@app.command("generic")
def generic(
    path: Annotated[str, typer.Argument(help="Path to CSV in the generic schema")],
    commit: Annotated[bool, typer.Option("--commit", help="Write transactions")] = False,
) -> None:
    """Import a CSV in the documented generic schema (dry run by default).

    Columns: symbol,name,asset_type,date,type,units,price[,amount_inr,fx_rate].
    """
    _run("generic", path, commit)
