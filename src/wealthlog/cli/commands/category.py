"""`wealthlog-cli category` commands."""

from __future__ import annotations

from typing import Annotated

import typer
from sqlmodel import select

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import console, make_table
from wealthlog.constants import CategoryType
from wealthlog.db.models import Category

app = typer.Typer(help="Manage expense/income categories.", no_args_is_help=True)


@app.command("list")
def list_categories() -> None:
    """List all categories."""
    with session_scope() as session:
        rows = session.exec(select(Category).order_by(Category.type, Category.name)).all()
        table = make_table("Categories", ["Name", "Type", "Color"])
        for c in rows:
            table.add_row(c.name, c.type.value, c.color or "—")
        console.print(table)


@app.command("add")
def add_category(
    name: Annotated[str, typer.Argument(help="Category name")],
    type: Annotated[str, typer.Option("--type", help="expense|income")] = "expense",
    color: Annotated[str | None, typer.Option("--color")] = None,
    icon: Annotated[str | None, typer.Option("--icon")] = None,
) -> None:
    """Add a new category."""
    ctype = CategoryType.INCOME if type.lower() == "income" else CategoryType.EXPENSE
    with session_scope() as session:
        existing = session.exec(
            select(Category).where(Category.name == name, Category.type == ctype)
        ).first()
        if existing:
            console.print(f"[yellow]Category '{name}' ({ctype.value}) already exists.[/yellow]")
            raise typer.Exit(code=1)
        cat = Category(name=name, type=ctype, color=color, icon=icon)
        session.add(cat)
        session.commit()
        console.print(f"[green]Added category '{name}' ({ctype.value}).[/green]")
