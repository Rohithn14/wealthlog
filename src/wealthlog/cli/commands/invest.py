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
from wealthlog.services.concentration import ConcentrationService
from wealthlog.services.dividends import DividendService
from wealthlog.services.portfolio import PortfolioService
from wealthlog.services.sip import SIPService
from wealthlog.services.tax import TaxService

app = typer.Typer(help="Track investments, holdings, P&L, and XIRR.", no_args_is_help=True)
sip_schedule_app = typer.Typer(help="Manage SIP schedules.", no_args_is_help=True)
app.add_typer(sip_schedule_app, name="sip-schedule")


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


@app.command("refresh")
def refresh(
    force: Annotated[bool, typer.Option("--force", help="Ignore cache freshness")] = False,
) -> None:
    """Fetch live prices for all holdings (yfinance / mfapi / FX), with caching."""
    from wealthlog.services.fetcher import FetcherService

    with session_scope() as session:
        svc = FetcherService(session)
        result = svc.refresh_prices(force=force)
        console.print(f"[green]Updated:[/green] {', '.join(result.updated) or '—'}")
        if result.skipped_fresh:
            console.print(f"[dim]Fresh (skipped): {', '.join(result.skipped_fresh)}[/dim]")
        for symbol, err in result.failed:
            console.print(f"[red]Failed {symbol}:[/red] {err}")


@app.command("set-price")
def set_price(
    symbol: Annotated[str, typer.Argument()],
    price_inr: Annotated[str, typer.Argument(help="Manual INR price per unit")],
) -> None:
    """Manually set an INR price for a holding (override / offline fallback)."""
    from wealthlog.services.fetcher import FetcherService

    with session_scope() as session:
        inv = _resolve_investment(session, symbol)
        svc = FetcherService(session)
        svc.set_manual_price(inv.id, price_inr)
        console.print(
            f"[green]Set manual price for {symbol}:[/green] {fmt_inr(Decimal(price_inr))}"
        )


@sip_schedule_app.command("add")
def add_sip_schedule(
    symbol: Annotated[str, typer.Argument(help="Investment symbol/scheme code")],
    amount: Annotated[str, typer.Argument(help="Monthly instalment in INR")],
    day: Annotated[int, typer.Argument(help="Day of month (1-31)")],
    start: Annotated[str, typer.Option("--start", help="First instalment month (YYYY-MM-DD)")],
    end: Annotated[
        str | None, typer.Option("--end", help="Last instalment month (YYYY-MM-DD)")
    ] = None,
) -> None:
    """Create a monthly SIP schedule for an investment."""
    with session_scope() as session:
        inv = _resolve_investment(session, symbol)
        try:
            schedule = SIPService(session).add_schedule(
                inv.id, amount, day, _parse_date(start),
                end_date=dt.date.fromisoformat(end) if end else None,
            )
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        console.print(
            f"[green]Added SIP schedule #{schedule.id}:[/green] "
            f"{fmt_inr(schedule.amount_inr)} {symbol} on day {schedule.day_of_month}"
        )


@sip_schedule_app.command("list")
def list_sip_schedules(
    all_schedules: Annotated[bool, typer.Option("--all", help="Include inactive")] = False,
) -> None:
    """List SIP schedules (active only by default)."""
    with session_scope() as session:
        schedules = SIPService(session).list_schedules(include_inactive=all_schedules)
        table = make_table(
            "SIP schedules", ["#", "Symbol", "Amount", "Day", "Start", "End", "Active"]
        )
        for s in schedules:
            inv = session.get(Investment, s.investment_id)
            table.add_row(
                str(s.id), inv.symbol if inv else str(s.investment_id),
                fmt_inr(s.amount_inr), str(s.day_of_month), str(s.start_date),
                str(s.end_date or "—"), "yes" if s.active else "no",
            )
        console.print(table)


@sip_schedule_app.command("deactivate")
def deactivate_sip_schedule(
    schedule_id: Annotated[int, typer.Argument(help="Schedule id")],
) -> None:
    """Deactivate a SIP schedule."""
    with session_scope() as session:
        if SIPService(session).deactivate(schedule_id):
            console.print(f"[green]Deactivated SIP schedule #{schedule_id}.[/green]")
        else:
            console.print(f"[red]No SIP schedule #{schedule_id}.[/red]")
            raise typer.Exit(code=1)


@app.command("sip-due")
def sip_due(
    as_of: Annotated[
        str | None, typer.Option("--as-of", help="Check due as of (YYYY-MM-DD)")
    ] = None,
) -> None:
    """List SIP instalments that are due but have no recorded transaction."""
    with session_scope() as session:
        pending = SIPService(session).get_pending_sips(
            as_of=dt.date.fromisoformat(as_of) if as_of else None
        )
        if not pending:
            console.print("[green]No pending SIP instalments.[/green]")
            return
        table = make_table("Pending SIPs", ["Due", "Symbol", "Amount"])
        for p in pending:
            table.add_row(str(p.due_date), p.symbol, fmt_inr(p.amount_inr))
        console.print(table)
        console.print(f"[yellow]{len(pending)} instalment(s) pending.[/yellow]")


@app.command("tax-report")
def tax_report(
    fy: Annotated[str, typer.Option("--fy", help="Financial year, e.g. 2025-26")],
) -> None:
    """FIFO capital-gains report for a financial year (informational only)."""
    with session_scope() as session:
        try:
            report = TaxService(session).capital_gains_report(fy)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        table = make_table(
            f"Capital gains FY {report.financial_year}",
            ["Symbol", "Buy", "Sell", "Units", "Cost", "Proceeds", "Gain", "Term"],
        )
        for r in report.rows:
            color = "green" if r.gain_inr >= 0 else "red"
            table.add_row(
                r.symbol, str(r.buy_date), str(r.sell_date), f"{r.units:g}",
                fmt_inr(r.cost_basis_inr), fmt_inr(r.proceeds_inr),
                f"[{color}]{fmt_inr(r.gain_inr)}[/{color}]",
                "LTCG" if r.is_long_term else "STCG",
            )
        console.print(table)
        console.print(f"[bold]Short-term gain:[/bold] {fmt_inr(report.short_term_gain_inr)}")
        console.print(f"[bold]Long-term gain:[/bold]  {fmt_inr(report.long_term_gain_inr)}")
        console.print(
            f"[dim]LTCG exemption {fmt_inr(report.ltcg_exemption_inr)} -> "
            f"taxable LTCG {fmt_inr(report.taxable_ltcg_inr)}[/dim]"
        )
        console.print(
            f"[bold]Est. tax:[/bold] STCG {fmt_inr(report.estimated_stcg_tax_inr)} + "
            f"LTCG {fmt_inr(report.estimated_ltcg_tax_inr)}"
        )
        console.print(
            "[yellow]Informational only — not tax advice. Post-Jul-2024 equity rates; "
            "gold/debt and grandfathering excluded. Verify with a CA.[/yellow]"
        )


@app.command("concentration")
def concentration(
    top: Annotated[int, typer.Option("--top", help="Number of largest holdings")] = 10,
    threshold: Annotated[
        float, typer.Option("--threshold", help="High-concentration weight %")
    ] = 10.0,
) -> None:
    """Show single-name, sector, and asset-class concentration."""
    with session_scope() as session:
        report = ConcentrationService(session).concentration_report(
            top_n=top, threshold_pct=str(threshold)
        )
        if report.total_value_inr <= 0:
            console.print("[dim]No holdings to analyse.[/dim]")
            return
        console.print(f"Total portfolio value: {fmt_inr(report.total_value_inr)}")
        holdings = make_table(
            f"Top {top} holdings", ["Symbol", "Name", "Value", "Weight"]
        )
        for r in report.top_holdings:
            weight = f"{r.pct_of_total:.2f}%"
            if r.is_concentrated:
                weight = f"[red]{weight} ⚠[/red]"
            holdings.add_row(r.symbol, r.name, fmt_inr(r.market_value_inr), weight)
        console.print(holdings)
        for title, rows in (
            ("By sector", report.by_sector),
            ("By asset class", report.by_asset_class),
        ):
            table = make_table(title, ["Category", "Value", "Weight"])
            for w in rows:
                table.add_row(w.label, fmt_inr(w.market_value_inr), f"{w.pct_of_total:.2f}%")
            console.print(table)


@app.command("set-sector")
def set_sector(
    symbol: Annotated[str, typer.Argument(help="Investment symbol")],
    sector: Annotated[str, typer.Argument(help="Sector label, e.g. IT, Banking")],
) -> None:
    """Tag an investment with a sector (used by concentration analysis)."""
    with session_scope() as session:
        inv = _resolve_investment(session, symbol)
        PortfolioService(session).set_sector(inv.id, sector)
        console.print(f"[green]Set sector for {symbol}:[/green] {sector}")


@app.command("dividends")
def dividends(
    year: Annotated[
        int | None, typer.Option("--year", "-y", help="Filter to one calendar year")
    ] = None,
) -> None:
    """Show dividends by holding (and yearly totals) with trailing yield."""
    with session_scope() as session:
        svc = DividendService(session)
        rows = svc.total_by_holding(year=year)
        title = f"Dividends {year}" if year else "Dividends (all time)"
        table = make_table(title, ["Symbol", "Name", "Total", "TTM Yield"])
        for r in rows:
            yld = f"{r.trailing_yield_pct:.2f}%" if r.trailing_yield_pct is not None else "—"
            table.add_row(r.symbol, r.name, fmt_inr(r.total_inr), yld)
        console.print(table)
        if year is None:
            by_year = svc.total_by_year()
            if by_year:
                yt = make_table("By year", ["Year", "Received"])
                for y, amount in by_year.items():
                    yt.add_row(str(y), fmt_inr(amount))
                console.print(yt)


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
