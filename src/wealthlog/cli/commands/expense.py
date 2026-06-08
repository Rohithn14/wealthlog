"""`wealthlog-cli expense` commands."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

import typer
from sqlmodel import select

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import console, fmt_inr, make_table
from wealthlog.db.models import Category
from wealthlog.services.expense import ExpenseService

app = typer.Typer(help="Log and review expenses.", no_args_is_help=True)


def _parse_date(value: str | None) -> dt.date:
    return dt.date.fromisoformat(value) if value else dt.date.today()


@app.command("add")
def add_expense(
    amount: Annotated[str, typer.Argument(help="Amount in INR, e.g. 250.50")],
    category: Annotated[str | None, typer.Option("--category", "-c", help="Category name")] = None,
    date: Annotated[str | None, typer.Option("--date", "-d", help="YYYY-MM-DD")] = None,
    description: Annotated[str | None, typer.Option("--desc")] = None,
    subcategory: Annotated[str | None, typer.Option("--sub")] = None,
    tags: Annotated[str | None, typer.Option("--tags", help="Comma-separated tags")] = None,
) -> None:
    """Add an expense (date defaults to today)."""
    with session_scope() as session:
        category_id = None
        if category:
            cat = session.exec(select(Category).where(Category.name == category)).first()
            if cat is None:
                console.print(f"[red]Unknown category '{category}'. Use 'category list'.[/red]")
                raise typer.Exit(code=1)
            category_id = cat.id
        tag_list = [t.strip() for t in tags.split(",")] if tags else []
        svc = ExpenseService(session)
        exp = svc.add_expense(
            _parse_date(date), amount, category_id=category_id,
            subcategory=subcategory, description=description, tags=tag_list,
        )
        console.print(
            f"[green]Added expense #{exp.id}:[/green] {fmt_inr(exp.amount_inr)} on {exp.date}"
        )


@app.command("list")
def list_expenses(
    start: Annotated[str | None, typer.Option("--start", help="YYYY-MM-DD")] = None,
    end: Annotated[str | None, typer.Option("--end", help="YYYY-MM-DD")] = None,
    category: Annotated[str | None, typer.Option("--category", "-c")] = None,
    tags: Annotated[str | None, typer.Option("--tags")] = None,
) -> None:
    """List expenses, optionally filtered by date range, category, or tags."""
    with session_scope() as session:
        category_id = None
        if category:
            cat = session.exec(select(Category).where(Category.name == category)).first()
            category_id = cat.id if cat else -1
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        svc = ExpenseService(session)
        rows = svc.list_expenses(
            start=dt.date.fromisoformat(start) if start else None,
            end=dt.date.fromisoformat(end) if end else None,
            category_id=category_id,
            tags=tag_list,
        )
        table = make_table("Expenses", ["Date", "Amount", "Category", "Description", "Tags"])
        for e in rows:
            cat = session.get(Category, e.category_id) if e.category_id else None
            table.add_row(
                str(e.date), fmt_inr(e.amount_inr),
                cat.name if cat else "—", e.description or "—", ", ".join(e.tags) or "—",
            )
        console.print(table)
        console.print(f"[dim]{len(rows)} expense(s).[/dim]")


@app.command("summary")
def summary(
    year: Annotated[int, typer.Argument(help="Year, e.g. 2026")],
    month: Annotated[int, typer.Argument(help="Month 1-12")],
) -> None:
    """Show a monthly expense summary with per-category breakdown."""
    with session_scope() as session:
        svc = ExpenseService(session)
        result = svc.monthly_summary(year, month)
        table = make_table(f"Summary {year}-{month:02d}", ["Category", "Spent"])
        for name, amount in sorted(result.by_category.items(), key=lambda kv: kv[1], reverse=True):
            table.add_row(name, fmt_inr(amount))
        console.print(table)
        console.print(
            f"[bold]Total:[/bold] {fmt_inr(result.total_inr)} across {result.count} expense(s)"
        )


@app.command("delete")
def delete_expense(expense_id: Annotated[int, typer.Argument(help="Expense id")]) -> None:
    """Delete an expense by id."""
    with session_scope() as session:
        svc = ExpenseService(session)
        if svc.delete_expense(expense_id):
            console.print(f"[green]Deleted expense #{expense_id}.[/green]")
        else:
            console.print(f"[red]No expense #{expense_id}.[/red]")
            raise typer.Exit(code=1)
