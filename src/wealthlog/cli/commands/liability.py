"""`wealthlog-cli liability` commands."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

import typer

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import console, fmt_inr, make_table
from wealthlog.constants import LiabilityCategory
from wealthlog.services.liability import LiabilityService

app = typer.Typer(help="Track liabilities (loans, credit cards) against net worth.",
                  no_args_is_help=True)


@app.command("add")
def add_liability(
    name: Annotated[str, typer.Argument(help="Liability name, e.g. 'Home loan'")],
    amount: Annotated[str, typer.Argument(help="Outstanding amount in INR")],
    category: Annotated[
        LiabilityCategory, typer.Option("--category", "-c")
    ] = LiabilityCategory.OTHER,
    due: Annotated[str | None, typer.Option("--due", help="Due date YYYY-MM-DD")] = None,
    notes: Annotated[str | None, typer.Option("--notes")] = None,
) -> None:
    """Add a liability."""
    with session_scope() as session:
        row = LiabilityService(session).add_liability(
            name, amount, category=category,
            due_date=dt.date.fromisoformat(due) if due else None, notes=notes,
        )
        console.print(
            f"[green]Added liability #{row.id}:[/green] {fmt_inr(row.amount_inr)} ({row.category})"
        )


@app.command("list")
def list_liabilities() -> None:
    """List liabilities and their total."""
    with session_scope() as session:
        svc = LiabilityService(session)
        rows = svc.list_liabilities()
        table = make_table("Liabilities", ["#", "Name", "Amount", "Category", "Due", "Notes"])
        for r in rows:
            table.add_row(
                str(r.id), r.name, fmt_inr(r.amount_inr), str(r.category),
                str(r.due_date) if r.due_date else "—", r.notes or "—",
            )
        console.print(table)
        console.print(f"[bold]Total liabilities:[/bold] {fmt_inr(svc.total_liabilities())}")


@app.command("update")
def update_liability(
    liability_id: Annotated[int, typer.Argument(help="Liability id")],
    amount: Annotated[str, typer.Argument(help="New outstanding amount in INR")],
) -> None:
    """Update a liability's outstanding amount."""
    with session_scope() as session:
        if not LiabilityService(session).update_amount(liability_id, amount):
            console.print(f"[red]No liability #{liability_id}.[/red]")
            raise typer.Exit(code=1)
        console.print(f"[green]Updated liability #{liability_id}.[/green]")


@app.command("delete")
def delete_liability(
    liability_id: Annotated[int, typer.Argument(help="Liability id")],
) -> None:
    """Delete a liability."""
    with session_scope() as session:
        if not LiabilityService(session).delete_liability(liability_id):
            console.print(f"[red]No liability #{liability_id}.[/red]")
            raise typer.Exit(code=1)
        console.print(f"[green]Deleted liability #{liability_id}.[/green]")
