"""Tests for ImportService: parsing, dedup preview, and commit."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlmodel import select

from wealthlog.constants import AssetType, TransactionType
from wealthlog.db.models import Investment
from wealthlog.services.importer import ImportService
from wealthlog.services.portfolio import PortfolioService


@pytest.fixture
def svc(db_session):
    return ImportService(db_session)


@pytest.fixture
def portfolio(db_session):
    return PortfolioService(db_session)


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


GENERIC_CSV = """symbol,name,asset_type,date,type,units,price
INFY.NS,Infosys,STOCK_IN,2025-01-15,BUY,10,1500
INFY.NS,Infosys,STOCK_IN,2025-03-10,SELL,4,1800
"""

ZERODHA_CSV = """symbol,trade_date,exchange,trade_type,quantity,price
INFY,2025-01-15,NSE,buy,10,1500
TCS,2025-02-01,NSE,buy,5,3500
INFY,2025-03-10,NSE,sell,4,1800
"""


class TestParse:
    def test_generic_parses(self, svc, tmp_path):
        parsed = svc.parse(_write(tmp_path, "g.csv", GENERIC_CSV), "generic")
        assert len(parsed) == 2
        assert parsed[0].symbol == "INFY.NS"
        assert parsed[0].type == TransactionType.BUY
        assert parsed[0].units == Decimal("10.0000")
        assert parsed[0].price == Decimal("1500.0000")

    def test_zerodha_adds_ns_suffix(self, svc, tmp_path):
        parsed = svc.parse(_write(tmp_path, "z.csv", ZERODHA_CSV), "zerodha")
        assert {p.symbol for p in parsed} == {"INFY.NS", "TCS.NS"}
        assert all(p.asset_type == AssetType.STOCK_IN for p in parsed)

    def test_sorted_by_date(self, svc, tmp_path):
        parsed = svc.parse(_write(tmp_path, "z.csv", ZERODHA_CSV), "zerodha")
        assert [p.date for p in parsed] == sorted(p.date for p in parsed)

    def test_unknown_broker_raises(self, svc, tmp_path):
        with pytest.raises(ValueError):
            svc.parse(_write(tmp_path, "g.csv", GENERIC_CSV), "nosuchbroker")

    def test_xlsx_roundtrip(self, svc, tmp_path):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["symbol", "name", "asset_type", "date", "type", "units", "price"])
        ws.append(["INFY.NS", "Infosys", "STOCK_IN", "2025-01-15", "BUY", 10, 1500])
        path = tmp_path / "g.xlsx"
        wb.save(path)
        parsed = svc.parse(str(path), "generic")
        assert len(parsed) == 1
        assert parsed[0].units == Decimal("10.0000")


class TestPreview:
    def test_all_new_first_time(self, svc, tmp_path):
        preview = svc.preview(_write(tmp_path, "z.csv", ZERODHA_CSV), "zerodha")
        assert preview.new_count == 3
        assert preview.duplicate_count == 0
        # First occurrence of each symbol creates an investment.
        creates = [r for r in preview.rows if r.creates_investment]
        assert {r.txn.symbol for r in creates} == {"INFY.NS", "TCS.NS"}

    def test_detects_existing_duplicate(self, svc, portfolio, tmp_path):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2025, 1, 15), TransactionType.BUY, "10", "1500")
        preview = svc.preview(_write(tmp_path, "g.csv", GENERIC_CSV), "generic")
        dupes = [r for r in preview.rows if r.is_duplicate]
        assert len(dupes) == 1
        assert dupes[0].txn.date == dt.date(2025, 1, 15)


class TestCommit:
    def test_imports_and_creates_investments(self, svc, db_session, tmp_path):
        result = svc.commit(_write(tmp_path, "z.csv", ZERODHA_CSV), "zerodha")
        assert result.imported == 3
        assert result.skipped_duplicates == 0
        assert set(result.created_investments) == {"INFY.NS", "TCS.NS"}
        assert db_session.exec(select(Investment)).all()

    def test_idempotent_reimport(self, svc, tmp_path):
        path = _write(tmp_path, "z.csv", ZERODHA_CSV)
        svc.commit(path, "zerodha")
        second = svc.commit(path, "zerodha")
        assert second.imported == 0
        assert second.skipped_duplicates == 3

    def test_commit_then_holdings(self, svc, portfolio, tmp_path):
        svc.commit(_write(tmp_path, "g.csv", GENERIC_CSV), "generic")
        holding = next(h for h in portfolio.get_holdings() if h.symbol == "INFY.NS")
        # Bought 10, sold 4 -> 6 units remain.
        assert holding.units == Decimal("6.0000")
