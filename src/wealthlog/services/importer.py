"""Broker statement import (Milestone B3).

Per-broker parsers normalise rows into :class:`ParsedTxn`; the service previews
(dry-run, default) and commits them. Unknown symbols auto-create investments;
rows matching an existing transaction on (investment, date, type, units, amount)
are skipped as duplicates.

Supported parsers: ``generic`` (our documented CSV schema) and ``zerodha``
(tradebook CSV/XLSX). ``.xlsx`` is read via openpyxl; ``.csv`` via stdlib csv.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlmodel import Session, select

from wealthlog.constants import AssetType, TransactionType
from wealthlog.db.models import Investment, Transaction
from wealthlog.money import to_money, to_price, to_units
from wealthlog.services.portfolio import PortfolioService


@dataclass(frozen=True)
class ParsedTxn:
    """A normalised transaction parsed from a broker statement."""

    symbol: str
    name: str
    asset_type: AssetType
    date: dt.date
    type: TransactionType
    units: Decimal
    price: Decimal
    amount_inr: Decimal | None = None
    fx_rate: Decimal | None = None


@dataclass(frozen=True)
class PreviewRow:
    """A parsed row tagged with whether it is new or a duplicate."""

    txn: ParsedTxn
    is_duplicate: bool
    creates_investment: bool


@dataclass(frozen=True)
class ImportPreview:
    """Dry-run result: every parsed row tagged new/duplicate."""

    broker: str
    rows: list[PreviewRow]

    @property
    def new_count(self) -> int:
        return sum(1 for r in self.rows if not r.is_duplicate)

    @property
    def duplicate_count(self) -> int:
        return sum(1 for r in self.rows if r.is_duplicate)


@dataclass(frozen=True)
class ImportResult:
    """Commit result: counts of imported, skipped, and created investments."""

    imported: int
    skipped_duplicates: int
    created_investments: list[str]


# --------------------------------------------------------------------------- #
# Row reading
# --------------------------------------------------------------------------- #

def _read_rows(path: Path) -> list[dict[str, str]]:
    """Read a CSV or XLSX file into a list of header-keyed string dicts."""
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        return _read_xlsx(path)
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _read_xlsx(path: Path) -> list[dict[str, str]]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = [str(c).strip() if c is not None else "" for c in next(rows_iter)]
    except StopIteration:
        return []
    out: list[dict[str, str]] = []
    for raw in rows_iter:
        if raw is None or all(c is None for c in raw):
            continue
        out.append({h: ("" if v is None else str(v)) for h, v in zip(header, raw, strict=False)})
    wb.close()
    return out


def _dec(value: str) -> Decimal:
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"Bad number '{value}'") from exc


def _parse_date(value: str) -> dt.date:
    value = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date '{value}'")


# --------------------------------------------------------------------------- #
# Parsers
# --------------------------------------------------------------------------- #

def parse_generic(rows: Iterable[dict[str, str]]) -> list[ParsedTxn]:
    """Parse our documented schema: symbol,name,asset_type,date,type,units,price.

    Optional columns: ``amount_inr``, ``fx_rate``.
    """
    out: list[ParsedTxn] = []
    for row in rows:
        units = to_units(_dec(row["units"]))
        out.append(
            ParsedTxn(
                symbol=row["symbol"].strip(),
                name=(row.get("name") or row["symbol"]).strip(),
                asset_type=AssetType(row["asset_type"].strip().upper()),
                date=_parse_date(row["date"]),
                type=TransactionType(row["type"].strip().upper()),
                units=units,
                price=to_price(_dec(row["price"])),
                amount_inr=to_money(_dec(row["amount_inr"])) if row.get("amount_inr") else None,
                fx_rate=Decimal(str(row["fx_rate"])) if row.get("fx_rate") else None,
            )
        )
    return out


def parse_zerodha(rows: Iterable[dict[str, str]]) -> list[ParsedTxn]:
    """Parse a Zerodha tradebook export (equity).

    Columns used: ``symbol``, ``trade_date``, ``trade_type`` (buy/sell),
    ``quantity``, ``price``, optional ``exchange``. NSE symbols get a ``.NS``
    suffix so they match yfinance.
    """
    out: list[ParsedTxn] = []
    for row in rows:
        symbol = row["symbol"].strip().upper()
        exchange = (row.get("exchange") or "NSE").strip().upper()
        if exchange == "NSE" and not symbol.endswith(".NS"):
            symbol = f"{symbol}.NS"
        is_buy = row["trade_type"].strip().lower() == "buy"
        ttype = TransactionType.BUY if is_buy else TransactionType.SELL
        out.append(
            ParsedTxn(
                symbol=symbol,
                name=row.get("symbol", symbol).strip(),
                asset_type=AssetType.STOCK_IN,
                date=_parse_date(row["trade_date"]),
                type=ttype,
                units=to_units(_dec(row["quantity"])),
                price=to_price(_dec(row["price"])),
            )
        )
    return out


PARSERS = {
    "generic": parse_generic,
    "zerodha": parse_zerodha,
}


class ImportService:
    """Preview and commit broker-statement imports.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.portfolio = PortfolioService(session)

    def parse(self, path: str | Path, broker: str) -> list[ParsedTxn]:
        """Parse a file with the named broker parser (rows sorted by date)."""
        parser = PARSERS.get(broker)
        if parser is None:
            raise ValueError(f"Unknown broker '{broker}'; known: {', '.join(PARSERS)}")
        rows = _read_rows(Path(path))
        parsed = parser(rows)
        parsed.sort(key=lambda t: t.date)  # buys before sells for sell validation
        return parsed

    def _existing_investment(self, symbol: str) -> Investment | None:
        return self.session.exec(
            select(Investment).where(Investment.symbol == symbol)
        ).first()

    def _is_duplicate(self, inv_id: int, txn: ParsedTxn, amount: Decimal) -> bool:
        for t in self.session.exec(
            select(Transaction).where(
                Transaction.investment_id == inv_id,
                Transaction.date == txn.date,
                Transaction.type == txn.type,
            )
        ).all():
            if t.units == txn.units and t.amount_inr == amount:
                return True
        return False

    @staticmethod
    def _amount(txn: ParsedTxn) -> Decimal:
        if txn.amount_inr is not None:
            return txn.amount_inr
        fx = txn.fx_rate or Decimal(1)
        return to_money(txn.units * txn.price * fx)

    def preview(self, path: str | Path, broker: str) -> ImportPreview:
        """Dry-run: parse and tag each row as new or duplicate (no writes)."""
        parsed = self.parse(path, broker)
        seen_new: set[str] = set()
        rows: list[PreviewRow] = []
        for txn in parsed:
            inv = self._existing_investment(txn.symbol)
            creates = inv is None and txn.symbol not in seen_new
            dup = inv is not None and self._is_duplicate(inv.id, txn, self._amount(txn))
            if creates:
                seen_new.add(txn.symbol)
            rows.append(PreviewRow(txn=txn, is_duplicate=dup, creates_investment=creates))
        return ImportPreview(broker=broker, rows=rows)

    def commit(self, path: str | Path, broker: str) -> ImportResult:
        """Import non-duplicate rows, auto-creating investments as needed."""
        parsed = self.parse(path, broker)
        imported = 0
        skipped = 0
        created: list[str] = []
        for txn in parsed:
            inv = self._existing_investment(txn.symbol)
            if inv is None:
                inv = self.portfolio.add_investment(
                    txn.symbol, txn.name, txn.asset_type,
                    currency_native="USD" if txn.asset_type == AssetType.STOCK_US else "INR",
                )
                created.append(txn.symbol)
            if self._is_duplicate(inv.id, txn, self._amount(txn)):
                skipped += 1
                continue
            self.portfolio.add_transaction(
                inv.id, txn.date, txn.type, txn.units, txn.price,
                amount_inr=txn.amount_inr, fx_rate_used=txn.fx_rate,
            )
            imported += 1
        return ImportResult(
            imported=imported, skipped_duplicates=skipped, created_investments=created
        )
