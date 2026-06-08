"""`wealthlog-cli invest` commands."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated

import typer
from sqlmodel import select

from wealthlog.cli._db import session_scope
from wealthlog.cli._render import console, fmt_inr, fmt_ratio_as_pct, make_table
from wealthlog.constants import AssetType, CompoundingFrequency, TransactionType
from wealthlog.db.models import Investment
from wealthlog.services.portfolio import PortfolioService

app = typer.Typer(help="Track investments, holdings, P&L, and XIRR.", no_args_is_help=True)


def _parse_date(value: str | None) -> dt.date:
    return dt.date.fromisoformat(value) if value else dt.date.today()


def _resolve_investment(session, symbol: str) -> Investment:
    inv = session.exec(select(Investment).where(Investment.symbol == symbol)).first()
    if inv is None:
        console.print(f"[red]Unknown investment '{symbol}'. Add it first.[/red]")
        raise typer.Exit(code=1)
    return inv


@app.command("add")
def add_investment(
    symbol: Annotated[str, typer.Argument(help="Ticker/scheme code, e.g. INFY.NS, AAPL, 120503")],
    name: Annotated[str, typer.Argument(help="Display name")],
    asset_type: Annotated[
        str, typer.Option("--type", "-t", help="STOCK_IN|STOCK_US|MF|GOLD_ETF")
    ],
    currency: Annotated[str, typer.Option("--currency", help="Native currency")] = "INR",
    exchange: Annotated[str | None, typer.Option("--exchange")] = None,
) -> None:
    """Register a tradable investment (non-FD)."""
    try:
        atype = AssetType(asset_type.upper())
    except ValueError:
        console.print(f"[red]Invalid asset type '{asset_type}'.[/red]")
        raise typer.Exit(code=1) from None
    if atype == AssetType.FD:
        console.print("[red]Use 'invest add-fd' for fixed deposits.[/red]")
        raise typer.Exit(code=1)
    with session_scope() as session:
        svc = PortfolioService(session)
        inv = svc.add_investment(symbol, name, atype, currency_native=currency, exchange=exchange)
        console.print(f"[green]Added investment #{inv.id}: {symbol} ({atype.value}).[/green]")


@app.command("add-fd")
def add_fd(
    name: Annotated[str, typer.Argument(help="FD name/label")],
    principal: Annotated[str, typer.Argument(help="Principal in INR")],
    rate: Annotated[str, typer.Argument(help="Annual interest rate %, e.g. 7.1")],
    start: Annotated[str, typer.Option("--start", help="YYYY-MM-DD")],
    maturity: Annotated[str, typer.Option("--maturity", help="YYYY-MM-DD")],
    compounding: Annotated[
        str, typer.Option("--compounding", help="SIMPLE|ANNUAL|SEMI_ANNUAL|QUARTERLY|MONTHLY")
    ] = "QUARTERLY",
) -> None:
    """Register a fixed deposit."""
    with session_scope() as session:
        svc = PortfolioService(session)
        inv = svc.add_fd(
            name, principal, rate, _parse_date(start), _parse_date(maturity),
            compounding=CompoundingFrequency(compounding.upper()),
        )
        console.print(
            f"[green]Added FD #{inv.id}: {name} ({fmt_inr(Decimal(principal))}).[/green]"
        )


def _txn(symbol: str, ttype: TransactionType, units: str, price: str,
         date: str | None, fx: str | None, amount: str | None, notes: str | None) -> None:
    with session_scope() as session:
        inv = _resolve_investment(session, symbol)
        svc = PortfolioService(session)
        txn = svc.add_transaction(
            inv.id, _parse_date(date), ttype, units, price,
            amount_inr=amount, fx_rate_used=fx, notes=notes,
        )
        console.print(
            f"[green]{ttype.value}[/green] {units} {symbol} @ {price} "
            f"= {fmt_inr(txn.amount_inr)} on {txn.date}"
        )


@app.command("buy")
def buy(
    symbol: Annotated[str, typer.Argument()],
    units: Annotated[str, typer.Argument()],
    price: Annotated[str, typer.Argument(help="Native price per unit")],
    date: Annotated[str | None, typer.Option("--date", "-d")] = None,
    fx: Annotated[str | None, typer.Option("--fx", help="FX rate for USD assets")] = None,
    amount: Annotated[str | None, typer.Option("--amount", help="Override INR amount")] = None,
    notes: Annotated[str | None, typer.Option("--notes")] = None,
) -> None:
    """Record a BUY transaction."""
    _txn(symbol, TransactionType.BUY, units, price, date, fx, amount, notes)


@app.command("sell")
def sell(
    symbol: Annotated[str, typer.Argument()],
    units: Annotated[str, typer.Argument()],
    price: Annotated[str, typer.Argument()],
    date: Annotated[str | None, typer.Option("--date", "-d")] = None,
    fx: Annotated[str | None, typer.Option("--fx")] = None,
    amount: Annotated[str | None, typer.Option("--amount")] = None,
    notes: Annotated[str | None, typer.Option("--notes")] = None,
) -> None:
    """Record a SELL transaction."""
    _txn(symbol, TransactionType.SELL, units, price, date, fx, amount, notes)


@app.command("sip")
def sip(
    symbol: Annotated[str, typer.Argument()],
    units: Annotated[str, typer.Argument()],
    price: Annotated[str, typer.Argument(help="NAV per unit")],
    date: Annotated[str | None, typer.Option("--date", "-d")] = None,
    notes: Annotated[str | None, typer.Option("--notes")] = None,
) -> None:
    """Record a mutual-fund SIP instalment."""
    _txn(symbol, TransactionType.SIP, units, price, date, None, None, notes)


@app.command("holdings")
def holdings() -> None:
    """Show current holdings with P&L."""
    with session_scope() as session:
        svc = PortfolioService(session)
        rows = svc.get_holdings()
        table = make_table(
            "Holdings",
            ["Symbol", "Type", "Units", "Invested", "Value", "P&L", "P&L %", "Price"],
        )
        for h in rows:
            stale = " [yellow](stale)[/yellow]" if h.price_is_stale else ""
            pnl_color = "green" if h.pnl_abs_inr >= 0 else "red"
            table.add_row(
                h.symbol, h.asset_type.value, f"{h.units:g}",
                fmt_inr(h.invested_inr), fmt_inr(h.market_value_inr),
                f"[{pnl_color}]{fmt_inr(h.pnl_abs_inr)}[/{pnl_color}]",
                f"[{pnl_color}]{h.pnl_pct:+.2f}%[/{pnl_color}]" if h.pnl_pct is not None else "—",
                (fmt_inr(h.current_price_inr) + stale),
            )
        console.print(table)


@app.command("pnl")
def pnl(
    symbol: Annotated[str | None, typer.Option("--symbol", "-s")] = None,
) -> None:
    """Show portfolio (or single-investment) P&L."""
    with session_scope() as session:
        svc = PortfolioService(session)
        inv_id = _resolve_investment(session, symbol).id if symbol else None
        result = svc.get_pnl(investment_id=inv_id)
        console.print(f"Invested: {fmt_inr(result.invested_inr)}")
        console.print(f"Value:    {fmt_inr(result.market_value_inr)}")
        color = "green" if result.pnl_abs_inr >= 0 else "red"
        pct = f"{result.pnl_pct:+.2f}%" if result.pnl_pct is not None else "—"
        console.print(f"P&L:      [{color}]{fmt_inr(result.pnl_abs_inr)} ({pct})[/{color}]")


@app.command("xirr")
def xirr(
    symbol: Annotated[str | None, typer.Option("--symbol", "-s")] = None,
) -> None:
    """Show XIRR for the portfolio or a single investment."""
    with session_scope() as session:
        svc = PortfolioService(session)
        inv_id = _resolve_investment(session, symbol).id if symbol else None
        rate = svc.calculate_xirr(investment_id=inv_id)
        label = symbol or "Portfolio"
        if rate is None:
            console.print(
                f"{label} XIRR: [dim]undefined (need at least one realised/valued flow)[/dim]"
            )
        else:
            color = "green" if rate >= 0 else "red"
            console.print(f"{label} XIRR: [{color}]{fmt_ratio_as_pct(rate)}[/{color}]")
