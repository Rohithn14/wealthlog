"""`wealthlog-cli budget` commands."""

from __future__ import annotations

from typing import Annotated

import typer
from sqlmodel import select

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import console, fmt_inr, make_table
from wealthlog.db.models import Category
from wealthlog.services.budget import BudgetService

app = typer.Typer(help="Set and check monthly budgets.", no_args_is_help=True)


def _resolve_category(session, name: str) -> int:
    cat = session.exec(select(Category).where(Category.name == name)).first()
    if cat is None:
        console.print(f"[red]Unknown category '{name}'.[/red]")
        raise typer.Exit(code=1)
    return cat.id


@app.command("set")
def set_budget(
    category: Annotated[str, typer.Argument(help="Category name")],
    limit: Annotated[str, typer.Argument(help="Monthly limit in INR")],
    year: Annotated[int, typer.Option("--year", "-y")],
    month: Annotated[int, typer.Option("--month", "-m")],
) -> None:
    """Set (or update) a category's monthly budget."""
    with session_scope() as session:
        category_id = _resolve_category(session, category)
        svc = BudgetService(session)
        b = svc.set_budget(category_id, month, year, limit)
        console.print(
            f"[green]Budget set:[/green] {category} {year}-{month:02d} = "
            f"{fmt_inr(b.limit_amount_inr)}"
        )


@app.command("status")
def status(
    year: Annotated[int, typer.Argument()],
    month: Annotated[int, typer.Argument()],
) -> None:
    """Show budget vs spending for a month."""
    with session_scope() as session:
        svc = BudgetService(session)
        rows = svc.get_budget_status(year, month)
        table = make_table(
            f"Budget status {year}-{month:02d}",
            ["Category", "Limit", "Spent", "Remaining", "Used", "Status"],
        )
        for s in rows:
            state = "[red]OVER[/red]" if s.is_over else "[green]ok[/green]"
            table.add_row(
                s.category_name, fmt_inr(s.limit_inr), fmt_inr(s.spent_inr),
                fmt_inr(s.remaining_inr), f"{s.pct_used:.0f}%", state,
            )
        console.print(table)


@app.command("alerts")
def alerts(
    year: Annotated[int, typer.Argument()],
    month: Annotated[int, typer.Argument()],
) -> None:
    """List categories that are over budget for a month."""
    with session_scope() as session:
        svc = BudgetService(session)
        overages = svc.alert_overages(year, month)
        if not overages:
            console.print("[green]No budgets exceeded. 🎉[/green]")
            return
        for s in overages:
            console.print(
                f"[red]⚠ {s.category_name}: spent {fmt_inr(s.spent_inr)} "
                f"of {fmt_inr(s.limit_inr)} ({s.pct_used:.0f}%)[/red]"
            )
