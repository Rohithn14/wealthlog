"""`wealthlog-cli alert` commands — manage and test portfolio alerts (C3)."""

from __future__ import annotations

from typing import Annotated

import typer
from sqlmodel import select

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import console, make_table
from wealthlog.constants import AlertKind
from wealthlog.db.models import Category, Investment
from wealthlog.services.alerts import AlertService

app = typer.Typer(help="Manage portfolio alert rules.", no_args_is_help=True)


@app.command("add")
def add_rule(
    kind: Annotated[AlertKind, typer.Argument(help="PRICE_DROP, BUDGET_PCT, or SIP_DUE")],
    threshold: Annotated[
        float | None, typer.Option("--threshold", "-t", help="Percent threshold")
    ] = None,
    symbol: Annotated[
        str | None, typer.Option("--symbol", "-s", help="Limit to an investment")
    ] = None,
    category: Annotated[
        str | None, typer.Option("--category", "-c", help="Limit to a category")
    ] = None,
) -> None:
    """Create an alert rule."""
    with session_scope() as session:
        investment_id = None
        if symbol:
            inv = session.exec(select(Investment).where(Investment.symbol == symbol)).first()
            if inv is None:
                console.print(f"[red]Unknown investment '{symbol}'.[/red]")
                raise typer.Exit(code=1)
            investment_id = inv.id
        category_id = None
        if category:
            cat = session.exec(select(Category).where(Category.name == category)).first()
            if cat is None:
                console.print(f"[red]Unknown category '{category}'.[/red]")
                raise typer.Exit(code=1)
            category_id = cat.id
        try:
            rule = AlertService(session).add_rule(
                kind, threshold=str(threshold) if threshold is not None else None,
                investment_id=investment_id, category_id=category_id,
            )
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        console.print(f"[green]Added alert rule #{rule.id}:[/green] {rule.kind}")


@app.command("list")
def list_rules(
    all_rules: Annotated[bool, typer.Option("--all", help="Include inactive")] = False,
) -> None:
    """List alert rules."""
    with session_scope() as session:
        svc = AlertService(session)
        rules = svc.list_rules(include_inactive=all_rules)
        table = make_table("Alert rules", ["#", "Kind", "Threshold", "Target", "Active"])
        for r in rules:
            table.add_row(
                str(r.id), r.kind, str(r.threshold or "—"),
                svc.describe_rule(r), "yes" if r.active else "no",
            )
        console.print(table)


@app.command("deactivate")
def deactivate(rule_id: Annotated[int, typer.Argument(help="Rule id")]) -> None:
    """Deactivate an alert rule."""
    with session_scope() as session:
        if AlertService(session).deactivate(rule_id):
            console.print(f"[green]Deactivated rule #{rule_id}.[/green]")
        else:
            console.print(f"[red]No rule #{rule_id}.[/red]")
            raise typer.Exit(code=1)


@app.command("check")
def check() -> None:
    """Evaluate alert rules now and print any that fire."""
    with session_scope() as session:
        fired = AlertService(session).evaluate()
        if not fired:
            console.print("[green]No alerts.[/green]")
            return
        for alert in fired:
            console.print(f"[yellow][{alert.kind}][/yellow] {alert.message}")
