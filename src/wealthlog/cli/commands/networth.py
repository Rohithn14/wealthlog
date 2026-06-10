"""`wealthlog-cli networth` commands."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

import typer

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import OutputFormat, console, emit, fmt_inr, make_table
from wealthlog.services.networth import NetWorthService

app = typer.Typer(help="Net-worth dashboard.", no_args_is_help=True)


@app.command("show")
def show(
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD")] = None,
    fmt: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Show net worth with asset-class breakdown."""
    with session_scope() as session:
        svc = NetWorthService(session)
        nw = svc.calculate_net_worth(dt.date.fromisoformat(as_of) if as_of else None)
        if fmt is not OutputFormat.table:
            emit(nw, fmt)
            return
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
    mode: Annotated[
        str, typer.Option("--mode", help="cost (net invested) or market (from snapshots)")
    ] = "cost",
    fmt: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.table,
) -> None:
    """Show net worth month-by-month (cost basis, or market value from snapshots)."""
    with session_scope() as session:
        svc = NetWorthService(session)
        try:
            points = svc.historical_net_worth(
                dt.date.fromisoformat(start), dt.date.fromisoformat(end), mode=mode
            )
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from None
        if fmt is not OutputFormat.table:
            emit(points, fmt)
            return
        if mode == "market":
            table = make_table("Net worth (month-end)", ["Month", "Invested", "Value", "Source"])
            for p in points:
                table.add_row(
                    f"{p.year}-{p.month:02d}", fmt_inr(p.invested_inr),
                    fmt_inr(p.market_value_inr),
                    "snapshots" if p.is_market_value else "cost (no snapshots)",
                )
            console.print(table)
        else:
            table = make_table("Invested capital (month-end)", ["Month", "Invested"])
            for p in points:
                table.add_row(f"{p.year}-{p.month:02d}", fmt_inr(p.invested_inr))
            console.print(table)
            console.print(
                "[dim]Note: cost-basis series (cumulative net invested capital), "
                "not market value. Use --mode market once price snapshots exist.[/dim]"
            )
