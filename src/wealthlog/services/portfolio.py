"""Portfolio tracking: transactions, holdings, P&L, and XIRR.

Prices are read from the ``prices_cache`` table (populated by the fetcher layer in
Milestone 7). When no cached price exists, the holding falls back to its average cost
(so P&L reads zero) and is flagged ``price_is_stale``. FD positions are valued
analytically via :func:`wealthlog.finance.fd.calculate_fd_value`.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.config import get_config
from wealthlog.constants import (
    INFLOW_TRANSACTION_TYPES,
    AssetType,
    TransactionType,
)
from wealthlog.db.models import FdDetails, Investment, PriceCache, Transaction
from wealthlog.finance.fd import calculate_fd_value
from wealthlog.finance.xirr import calculate_xirr
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_money, to_price, to_units
from wealthlog.services.results import Holding, PnL

logger = get_logger(__name__)

_ZERO = Decimal("0.00")


class PortfolioService:
    """Manage investments, transactions, and portfolio analytics.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    # ----------------------------------------------------------------- writes

    def add_investment(
        self,
        symbol: str,
        name: str,
        asset_type: AssetType,
        currency_native: str = "INR",
        exchange: str | None = None,
    ) -> Investment:
        """Create an investment record and return it."""
        inv = Investment(
            symbol=symbol,
            name=name,
            asset_type=asset_type,
            currency_native=currency_native,
            exchange=exchange,
        )
        self.session.add(inv)
        self.session.commit()
        self.session.refresh(inv)
        return inv

    def add_fd(
        self,
        name: str,
        principal: Decimal | int | str,
        interest_rate: Decimal | int | str,
        start_date: dt.date,
        maturity_date: dt.date,
        compounding=None,
        symbol: str | None = None,
    ) -> Investment:
        """Create an FD investment plus its :class:`FdDetails` row.

        Returns:
            The created FD :class:`Investment`.
        """
        from wealthlog.constants import CompoundingFrequency

        inv = self.add_investment(
            symbol=symbol or name,
            name=name,
            asset_type=AssetType.FD,
            currency_native="INR",
        )
        details = FdDetails(
            investment_id=inv.id,
            principal=to_money(principal),
            interest_rate=to_price(interest_rate),
            start_date=start_date,
            maturity_date=maturity_date,
            compounding=compounding or CompoundingFrequency.QUARTERLY,
        )
        self.session.add(details)
        self.session.commit()
        return inv

    def add_transaction(
        self,
        investment_id: int,
        date: dt.date,
        type: TransactionType,
        units: Decimal | int | str,
        price_per_unit: Decimal | int | str,
        amount_inr: Decimal | int | str | None = None,
        fx_rate_used: Decimal | int | str | None = None,
        notes: str | None = None,
    ) -> Transaction:
        """Record a buy/sell/dividend/SIP transaction.

        Args:
            investment_id: Target investment.
            date: Transaction date.
            type: Transaction type.
            units: Units transacted (>= 0).
            price_per_unit: Native-currency price per unit.
            amount_inr: Total INR cash flow. If omitted, it is computed as
                ``units * price_per_unit * fx_rate`` (fx defaults to 1).
            fx_rate_used: FX rate applied for non-INR assets (audit).
            notes: Optional free text.

        Returns:
            The persisted :class:`Transaction`.

        Raises:
            ValueError: If the investment does not exist or units/price are negative.
        """
        inv = self.session.get(Investment, investment_id)
        if inv is None:
            raise ValueError(f"Investment {investment_id} does not exist")

        u = to_units(units)
        ppu = to_price(price_per_unit)
        if u < 0 or ppu < 0:
            raise ValueError("units and price_per_unit must be non-negative")

        fx = Decimal(fx_rate_used) if fx_rate_used is not None else None
        if amount_inr is not None:
            amount = to_money(amount_inr)
        else:
            rate = fx if fx is not None else Decimal(1)
            amount = to_money(u * ppu * rate)

        txn = Transaction(
            investment_id=investment_id,
            date=date,
            type=type,
            units=u,
            price_per_unit=ppu,
            amount_inr=amount,
            fx_rate_used=(None if fx is None else fx),
            notes=notes,
        )
        self.session.add(txn)
        self.session.commit()
        self.session.refresh(txn)
        logger.info("Added %s txn for investment %s: %s units @ %s", type, investment_id, u, ppu)
        return txn

    # ------------------------------------------------------------- price reads

    def _latest_price(self, investment_id: int) -> PriceCache | None:
        return self.session.exec(
            select(PriceCache)
            .where(PriceCache.investment_id == investment_id)
            .order_by(PriceCache.fetched_at.desc())
        ).first()

    def _is_stale(self, asset_type: AssetType, fetched_at: dt.datetime | None) -> bool:
        if fetched_at is None:
            return True
        ttl = get_config().cache_ttl.for_asset(asset_type)
        return (dt.datetime.now() - fetched_at) > ttl

    # ------------------------------------------------------------------ reads

    def get_holdings(self, as_of: dt.date | None = None) -> list[Holding]:
        """Compute current holdings across all investments.

        Args:
            as_of: Valuation date (defaults to today), used for FD accrual.

        Returns:
            One :class:`Holding` per investment that has a non-zero position
            (or any FD). Sells reduce units; average cost is gross-buy weighted.
        """
        as_of = as_of or dt.date.today()
        holdings: list[Holding] = []
        investments = self.session.exec(select(Investment)).all()
        for inv in investments:
            if inv.asset_type == AssetType.FD:
                holding = self._fd_holding(inv, as_of)
            else:
                holding = self._market_holding(inv, as_of)
            if holding is not None:
                holdings.append(holding)
        return holdings

    def _fd_holding(self, inv: Investment, as_of: dt.date) -> Holding | None:
        details = self.session.exec(
            select(FdDetails).where(FdDetails.investment_id == inv.id)
        ).first()
        if details is None:
            return None
        value = calculate_fd_value(
            details.principal,
            details.interest_rate,
            details.start_date,
            as_of,
            compounding=details.compounding,
            maturity_date=details.maturity_date,
        )
        invested = to_money(details.principal)
        pnl_abs = to_money(value - invested)
        pnl_pct = to_money(pnl_abs / invested * Decimal(100)) if invested > 0 else None
        return Holding(
            investment_id=inv.id,
            symbol=inv.symbol,
            name=inv.name,
            asset_type=inv.asset_type,
            units=Decimal("1.0000"),
            invested_inr=invested,
            avg_cost_inr=invested,
            current_price_inr=value,
            market_value_inr=value,
            pnl_abs_inr=pnl_abs,
            pnl_pct=pnl_pct,
            price_as_of=None,
            price_is_stale=False,
        )

    def _market_holding(self, inv: Investment, as_of: dt.date) -> Holding | None:
        txns = self.session.exec(
            select(Transaction).where(Transaction.investment_id == inv.id)
        ).all()
        if not txns:
            return None

        bought_units = Decimal(0)
        bought_amt = Decimal(0)
        sold_units = Decimal(0)
        for t in txns:
            if t.type in INFLOW_TRANSACTION_TYPES:
                bought_units += t.units
                bought_amt += t.amount_inr
            elif t.type == TransactionType.SELL:
                sold_units += t.units
            # DIVIDEND does not affect units or cost basis here.

        units = to_units(bought_units - sold_units)
        if units <= 0:
            return None

        avg_cost = to_price(bought_amt / bought_units) if bought_units > 0 else None
        invested = to_money((avg_cost or Decimal(0)) * units)

        price_row = self._latest_price(inv.id)
        if price_row is not None:
            current_price = price_row.price_inr
            price_as_of = price_row.fetched_at
            stale = self._is_stale(inv.asset_type, price_as_of)
        else:
            current_price = avg_cost  # fallback -> zero P&L
            price_as_of = None
            stale = True

        market_value = to_money((current_price or Decimal(0)) * units)
        pnl_abs = to_money(market_value - invested)
        pnl_pct = to_money(pnl_abs / invested * Decimal(100)) if invested > 0 else None

        return Holding(
            investment_id=inv.id,
            symbol=inv.symbol,
            name=inv.name,
            asset_type=inv.asset_type,
            units=units,
            invested_inr=invested,
            avg_cost_inr=avg_cost,
            current_price_inr=current_price,
            market_value_inr=market_value,
            pnl_abs_inr=pnl_abs,
            pnl_pct=pnl_pct,
            price_as_of=price_as_of,
            price_is_stale=stale,
        )

    def get_pnl(self, investment_id: int | None = None, as_of: dt.date | None = None) -> PnL:
        """Aggregate P&L for one investment or the whole portfolio.

        Args:
            investment_id: If given, restrict to that investment; else portfolio-wide.
            as_of: Valuation date for FD accrual (defaults to today).

        Returns:
            A :class:`PnL` summary in INR.
        """
        holdings = self.get_holdings(as_of=as_of)
        if investment_id is not None:
            holdings = [h for h in holdings if h.investment_id == investment_id]

        invested = to_money(sum((h.invested_inr for h in holdings), _ZERO))
        market = to_money(sum((h.market_value_inr for h in holdings), _ZERO))
        pnl_abs = to_money(market - invested)
        pnl_pct = to_money(pnl_abs / invested * Decimal(100)) if invested > 0 else None
        return PnL(
            invested_inr=invested,
            market_value_inr=market,
            pnl_abs_inr=pnl_abs,
            pnl_pct=pnl_pct,
        )

    # ------------------------------------------------------------------- xirr

    def _investment_cashflows(
        self, inv: Investment, as_of: dt.date
    ) -> list[tuple[dt.date, Decimal]]:
        """Build dated cash flows for XIRR (buys negative, inflows positive)."""
        flows: list[tuple[dt.date, Decimal]] = []
        if inv.asset_type == AssetType.FD:
            details = self.session.exec(
                select(FdDetails).where(FdDetails.investment_id == inv.id)
            ).first()
            if details is None:
                return flows
            flows.append((details.start_date, -to_money(details.principal)))
            value = calculate_fd_value(
                details.principal,
                details.interest_rate,
                details.start_date,
                as_of,
                compounding=details.compounding,
                maturity_date=details.maturity_date,
            )
            flows.append((as_of, to_money(value)))
            return flows

        txns = self.session.exec(
            select(Transaction).where(Transaction.investment_id == inv.id)
        ).all()
        for t in txns:
            if t.type in INFLOW_TRANSACTION_TYPES:
                flows.append((t.date, -t.amount_inr))
            else:  # SELL, DIVIDEND are inflows
                flows.append((t.date, t.amount_inr))

        holding = self._market_holding(inv, as_of)
        if holding is not None and holding.market_value_inr > 0:
            flows.append((as_of, holding.market_value_inr))
        return flows

    def calculate_xirr(
        self, investment_id: int | None = None, as_of: dt.date | None = None
    ) -> Decimal | None:
        """Compute XIRR for one investment or the entire portfolio.

        Args:
            investment_id: If given, restrict to that investment; else portfolio-wide.
            as_of: Valuation date for the terminal cash flow (defaults to today).

        Returns:
            The annualised XIRR as a Decimal, or ``None`` when undefined (e.g. only
            buys so far, or fewer than two cash flows).
        """
        as_of = as_of or dt.date.today()
        if investment_id is not None:
            inv = self.session.get(Investment, investment_id)
            if inv is None:
                return None
            investments = [inv]
        else:
            investments = list(self.session.exec(select(Investment)).all())

        flows: list[tuple[dt.date, Decimal]] = []
        for inv in investments:
            flows.extend(self._investment_cashflows(inv, as_of))
        return calculate_xirr(flows)
