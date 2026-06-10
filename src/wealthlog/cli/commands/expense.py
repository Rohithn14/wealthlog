"""`wealthlog-cli expense` commands."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

import typer
from sqlmodel import select

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import OutputFormat, console, emit, fmt_inr, make_table
from wealthlog.constants import RecurrenceFrequency
from wealthlog.db.models import Category
from wealthlog.services.expense import ExpenseService
from wealthlog.services.recurring import RecurringExpenseService

app = typer.Typer(help="Log and review expenses.", no_args_is_help=True)
recurring_app = typer.Typer(help="Manage recurring-expense rules.", no_args_is_help=True)
app.add_typer(recurring_app, name="recurring")


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
    fmt: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """List expenses, optionally filtered by date range, category, or tags."""
    with session_scope() as session:
        category_id = None
        if category:
            cat = session.exec(select(Category).where(Category.name == category)).first()
            if cat is None:
                console.print(f"[red]Unknown category '{category}'. Use 'category list'.[/red]")
                raise typer.Exit(code=1)
            category_id = cat.id
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        svc = ExpenseService(session)
        rows = svc.list_expenses(
            start=dt.date.fromisoformat(start) if start else None,
            end=dt.date.fromisoformat(end) if end else None,
            category_id=category_id,
            tags=tag_list,
        )
        if fmt is not OutputFormat.table:
            emit(rows, fmt)
            return
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
    fmt: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Show a monthly expense summary with per-category breakdown."""
    with session_scope() as session:
        svc = ExpenseService(session)
        result = svc.monthly_summary(year, month)
        if fmt is not OutputFormat.table:
            emit(result, fmt)
            return
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


@recurring_app.command("add")
def add_recurring(
    amount: Annotated[str, typer.Argument(help="Amount in INR, e.g. 1500")],
    frequency: Annotated[
        RecurrenceFrequency, typer.Argument(help="DAILY, WEEKLY, or MONTHLY")
    ],
    category: Annotated[str | None, typer.Option("--category", "-c")] = None,
    day_of_month: Annotated[
        int | None, typer.Option("--day", help="Day of month (MONTHLY, 1-31)")
    ] = None,
    description: Annotated[str | None, typer.Option("--desc")] = None,
    start_from: Annotated[
        str | None, typer.Option("--start", help="Generate after this date (YYYY-MM-DD)")
    ] = None,
) -> None:
    """Create a recurring-expense rule (generation starts after today by default)."""
    with session_scope() as session:
        category_id = None
        if category:
            cat = session.exec(select(Category).where(Category.name == category)).first()
            if cat is None:
                console.print(f"[red]Unknown category '{category}'. Use 'category list'.[/red]")
                raise typer.Exit(code=1)
            category_id = cat.id
        try:
            rule = RecurringExpenseService(session).add_rule(
                amount, frequency, category_id=category_id,
                day_of_month=day_of_month, description=description,
                start_from=dt.date.fromisoformat(start_from) if start_from else None,
            )
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        console.print(
            f"[green]Added recurring rule #{rule.id}:[/green] "
            f"{fmt_inr(rule.amount_inr)} {rule.frequency}"
        )


@recurring_app.command("list")
def list_recurring(
    all_rules: Annotated[
        bool, typer.Option("--all", help="Include inactive rules")
    ] = False,
) -> None:
    """List recurring-expense rules (active only by default)."""
    with session_scope() as session:
        rules = RecurringExpenseService(session).list_rules(include_inactive=all_rules)
        table = make_table(
            "Recurring rules", ["#", "Amount", "Frequency", "Day", "Active", "Last generated"]
        )
        for r in rules:
            table.add_row(
                str(r.id), fmt_inr(r.amount_inr), r.frequency,
                str(r.day_of_month or "—"), "yes" if r.active else "no",
                str(r.last_generated or "—"),
            )
        console.print(table)


@recurring_app.command("deactivate")
def deactivate_recurring(rule_id: Annotated[int, typer.Argument(help="Rule id")]) -> None:
    """Deactivate a recurring-expense rule."""
    with session_scope() as session:
        if RecurringExpenseService(session).deactivate(rule_id):
            console.print(f"[green]Deactivated rule #{rule_id}.[/green]")
        else:
            console.print(f"[red]No rule #{rule_id}.[/red]")
            raise typer.Exit(code=1)


@app.command("generate-recurring")
def generate_recurring(
    as_of: Annotated[
        str | None, typer.Option("--as-of", help="Generate due instances up to (YYYY-MM-DD)")
    ] = None,
) -> None:
    """Materialise due recurring expenses (idempotent)."""
    with session_scope() as session:
        created = RecurringExpenseService(session).generate_due_instances(
            as_of=dt.date.fromisoformat(as_of) if as_of else None
        )
        if not created:
            console.print("[dim]Nothing due.[/dim]")
            return
        table = make_table("Generated expenses", ["Date", "Amount", "Description"])
        for e in created:
            table.add_row(str(e.date), fmt_inr(e.amount_inr), e.description or "—")
        console.print(table)
        console.print(f"[green]Generated {len(created)} expense(s).[/green]")
