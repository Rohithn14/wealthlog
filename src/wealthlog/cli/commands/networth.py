"""`wealthlog-cli networth` commands."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

import typer

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import console, fmt_inr, make_table
from wealthlog.services.networth import NetWorthService

app = typer.Typer(help="Net-worth dashboard.", no_args_is_help=True)


@app.command("show")
def show(
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD")] = None,
) -> None:
    """Show net worth with asset-class breakdown."""
    with session_scope() as session:
        svc = NetWorthService(session)
        nw = svc.calculate_net_worth(dt.date.fromisoformat(as_of) if as_of else None)
        table = make_table(f"Net worth as of {nw.as_of}", ["Asset class", "Value", "Share"])
        for c in nw.by_asset_class:
            table.add_row(c.asset_type.value, fmt_inr(c.market_value_inr), f"{c.pct_of_total:.1f}%")
        console.print(table)
        console.print(f"[bold]Total assets:[/bold] {fmt_inr(nw.total_assets_inr)}")
        console.print(f"[bold]Net worth:[/bold]   {fmt_inr(nw.net_worth_inr)}")


@app.command("history")
def history(
    start: Annotated[str, typer.Option("--start", help="YYYY-MM-DD")],
    end: Annotated[str, typer.Option("--end", help="YYYY-MM-DD")],
) -> None:
    """Show cumulative invested capital month-by-month."""
    with session_scope() as session:
        svc = NetWorthService(session)
        points = svc.historical_net_worth(
            dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        )
        table = make_table("Invested capital (month-end)", ["Month", "Invested"])
        for p in points:
            table.add_row(f"{p.year}-{p.month:02d}", fmt_inr(p.invested_inr))
        console.print(table)
