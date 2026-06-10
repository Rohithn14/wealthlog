"""Tests for ExportService and the CSV/PDF exporters."""

from __future__ import annotations

import csv
import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import AssetType, TransactionType
from wealthlog.db.models import PriceCache
from wealthlog.services.expense import ExpenseService
from wealthlog.services.export import ExportService
from wealthlog.services.portfolio import PortfolioService


@pytest.fixture
def export_svc(db_session):
    return ExportService(db_session)


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


class TestCsvExpenses:
    def test_writes_header_and_rows(self, export_svc, db_session, tmp_path):
        ExpenseService(db_session).add_expense(dt.date(2026, 1, 1), "150.50", tags=["a", "b"])
        out = export_svc.export_csv("expenses", tmp_path / "e.csv")
        assert out.exists()
        rows = _read_csv(out)
        assert rows[0] == ["id", "date", "amount_inr", "category", "subcategory",
                           "description", "tags"]
        assert rows[1][2] == "150.50"
        assert rows[1][6] == "a;b"

    def test_empty_export_has_header_only(self, export_svc, tmp_path):
        out = export_svc.export_csv("expenses", tmp_path / "e.csv")
        assert len(_read_csv(out)) == 1


class TestCsvTransactions:
    def test_transactions_export(self, export_svc, db_session, tmp_path):
        p = PortfolioService(db_session)
        inv = p.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        p.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "1500")
        out = export_svc.export_csv("transactions", tmp_path / "t.csv")
        rows = _read_csv(out)
        assert rows[0][2] == "symbol"
        assert rows[1][2] == "INFY.NS"
        assert rows[1][4] == "BUY"


class TestCsvHoldings:
    def test_holdings_export(self, export_svc, db_session, tmp_path):
        p = PortfolioService(db_session)
        inv = p.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        p.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "1000")
        db_session.add(
            PriceCache(investment_id=inv.id, price_native=Decimal("1200"),
                       price_inr=Decimal("1200"), fetched_at=dt.datetime.now())
        )
        db_session.commit()
        out = export_svc.export_csv("holdings", tmp_path / "h.csv")
        rows = _read_csv(out)
        assert rows[1][0] == "INFY.NS"
        assert rows[1][5] == "12000.00"  # market value
        assert rows[1][8] == "live"


class TestCsvErrors:
    def test_unknown_kind_raises(self, export_svc, tmp_path):
        with pytest.raises(ValueError):
            export_svc.export_csv("bogus", tmp_path / "x.csv")


class TestPdf:
    def test_pdf_created_and_nonempty(self, export_svc, db_session, tmp_path):
        p = PortfolioService(db_session)
        inv = p.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        p.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "1000")
        db_session.add(
            PriceCache(investment_id=inv.id, price_native=Decimal("1500"),
                       price_inr=Decimal("1500"), fetched_at=dt.datetime.now())
        )
        db_session.commit()
        out = export_svc.export_pdf_report(tmp_path / "report.pdf")
        assert out.exists()
        data = out.read_bytes()
        assert data.startswith(b"%PDF")
        assert len(data) > 500

    def test_pdf_empty_portfolio(self, export_svc, tmp_path):
        out = export_svc.export_pdf_report(tmp_path / "empty.pdf")
        assert out.exists()
        assert out.read_bytes().startswith(b"%PDF")

    def test_pdf_embeds_unicode_font_for_rupee(self, export_svc, tmp_path):
        # Bug #6: the bundled DejaVu font (with U+20B9) is embedded so ₹ renders.
        from wealthlog.exporters import pdf_exporter

        assert pdf_exporter._HAS_UNICODE is True
        assert pdf_exporter._RUPEE == "₹"
        out = export_svc.export_pdf_report(tmp_path / "u.pdf")
        assert b"DejaVu" in out.read_bytes()  # subset font embedded in the PDF

    def test_pdf_with_fd(self, export_svc, db_session, tmp_path):
        PortfolioService(db_session).add_fd(
            "SBI FD", "100000", "7.1", dt.date(2024, 1, 1), dt.date(2027, 1, 1)
        )
        out = export_svc.export_pdf_report(tmp_path / "fd.pdf", as_of=dt.date(2025, 1, 1))
        assert out.read_bytes().startswith(b"%PDF")


class TestCsvDirectoryCreation:
    def test_creates_parent_dirs(self, export_svc, tmp_path):
        out = export_svc.export_csv("expenses", tmp_path / "nested" / "deep" / "e.csv")
        assert out.exists()
