"""`wealthlog-cli income` commands."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

import typer
from sqlmodel import select

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import console, fmt_inr, make_table
from wealthlog.constants import CategoryType
from wealthlog.db.models import Category
from wealthlog.services.income import IncomeService

app = typer.Typer(help="Log and review income.", no_args_is_help=True)


def _parse_date(value: str | None) -> dt.date:
    return dt.date.fromisoformat(value) if value else dt.date.today()


def _resolve_income_category(session, name: str) -> int:
    cat = session.exec(
        select(Category).where(Category.name == name, Category.type == CategoryType.INCOME)
    ).first()
    if cat is None:
        console.print(f"[red]Unknown income category '{name}'. Use 'category list'.[/red]")
        raise typer.Exit(code=1)
    return cat.id


@app.command("add")
def add_income(
    amount: Annotated[str, typer.Argument(help="Amount in INR, e.g. 85000")],
    category: Annotated[
        str | None, typer.Option("--category", "-c", help="Income category name")
    ] = None,
    date: Annotated[str | None, typer.Option("--date", "-d", help="YYYY-MM-DD")] = None,
    source: Annotated[str | None, typer.Option("--source", help="Employer/broker/bank")] = None,
    description: Annotated[str | None, typer.Option("--desc")] = None,
) -> None:
    """Add an income entry (date defaults to today)."""
    with session_scope() as session:
        category_id = _resolve_income_category(session, category) if category else None
        svc = IncomeService(session)
        row = svc.add_income(
            _parse_date(date), amount, category_id=category_id,
            source=source, description=description,
        )
        console.print(
            f"[green]Added income #{row.id}:[/green] {fmt_inr(row.amount_inr)} on {row.date}"
        )


@app.command("list")
def list_income(
    start: Annotated[str | None, typer.Option("--start", help="YYYY-MM-DD")] = None,
    end: Annotated[str | None, typer.Option("--end", help="YYYY-MM-DD")] = None,
) -> None:
    """List income entries, optionally filtered by date range."""
    with session_scope() as session:
        svc = IncomeService(session)
        rows = svc.list_income(
            start=dt.date.fromisoformat(start) if start else None,
            end=dt.date.fromisoformat(end) if end else None,
        )
        table = make_table("Income", ["Date", "Amount", "Category", "Source", "Description"])
        for row in rows:
            cat = session.get(Category, row.category_id) if row.category_id else None
            table.add_row(
                str(row.date), fmt_inr(row.amount_inr),
                cat.name if cat else "—", row.source or "—", row.description or "—",
            )
        console.print(table)
        console.print(f"[dim]{len(rows)} income entr{'y' if len(rows) == 1 else 'ies'}.[/dim]")


@app.command("summary")
def summary(
    year: Annotated[int, typer.Argument(help="Year, e.g. 2026")],
    month: Annotated[int, typer.Argument(help="Month 1-12")],
) -> None:
    """Show monthly income by category plus net cashflow (income − expenses)."""
    with session_scope() as session:
        svc = IncomeService(session)
        by_category = svc.monthly_income_summary(year, month)
        table = make_table(f"Income {year}-{month:02d}", ["Category", "Received"])
        for name, amount in sorted(by_category.items(), key=lambda kv: kv[1], reverse=True):
            table.add_row(name, fmt_inr(amount))
        console.print(table)
        flow = svc.net_cashflow(year, month)
        color = "green" if flow.net_inr >= 0 else "red"
        console.print(f"[bold]Income:[/bold]   {fmt_inr(flow.income_inr)}")
        console.print(f"[bold]Expenses:[/bold] {fmt_inr(flow.expenses_inr)}")
        console.print(f"[bold]Net cashflow:[/bold] [{color}]{fmt_inr(flow.net_inr)}[/{color}]")


@app.command("delete")
def delete_income(income_id: Annotated[int, typer.Argument(help="Income id")]) -> None:
    """Delete an income entry by id."""
    with session_scope() as session:
        if IncomeService(session).delete_income(income_id):
            console.print(f"[green]Deleted income #{income_id}.[/green]")
        else:
            console.print(f"[red]No income #{income_id}.[/red]")
            raise typer.Exit(code=1)
