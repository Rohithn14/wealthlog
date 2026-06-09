"""Tests for TaxService: FIFO matching, LTCG/STCG classification, FY summary."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import AssetType, TransactionType
from wealthlog.services.portfolio import PortfolioService
from wealthlog.services.tax import TaxService, financial_year_bounds


@pytest.fixture
def portfolio(db_session):
    return PortfolioService(db_session)


@pytest.fixture
def svc(db_session):
    return TaxService(db_session)


class TestFinancialYearBounds:
    def test_parses_short_form(self):
        assert financial_year_bounds("2025-26") == (dt.date(2025, 4, 1), dt.date(2026, 3, 31))

    def test_parses_long_form(self):
        assert financial_year_bounds("2025-2026") == (dt.date(2025, 4, 1), dt.date(2026, 3, 31))

    def test_non_consecutive_raises(self):
        with pytest.raises(ValueError):
            financial_year_bounds("2025-27")

    def test_malformed_raises(self):
        with pytest.raises(ValueError):
            financial_year_bounds("nonsense")


class TestFifoMatching:
    def test_short_term_gain(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2025, 5, 1), TransactionType.BUY, "10", "100")
        portfolio.add_transaction(inv.id, dt.date(2025, 9, 1), TransactionType.SELL, "10", "150")
        report = svc.capital_gains_report("2025-26")
        assert len(report.rows) == 1
        row = report.rows[0]
        assert row.is_long_term is False
        assert row.cost_basis_inr == Decimal("1000.00")
        assert row.proceeds_inr == Decimal("1500.00")
        assert row.gain_inr == Decimal("500.00")
        assert report.short_term_gain_inr == Decimal("500.00")
        assert report.long_term_gain_inr == Decimal("0.00")

    def test_long_term_gain(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "100")
        portfolio.add_transaction(inv.id, dt.date(2025, 6, 1), TransactionType.SELL, "10", "200")
        report = svc.capital_gains_report("2025-26")
        assert report.rows[0].is_long_term is True
        assert report.long_term_gain_inr == Decimal("1000.00")

    def test_fifo_oldest_lot_first(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "100")
        portfolio.add_transaction(inv.id, dt.date(2025, 5, 1), TransactionType.BUY, "10", "200")
        # Sell 15: 10 from the 2024 lot (long-term) + 5 from the 2025 lot (short-term).
        portfolio.add_transaction(inv.id, dt.date(2025, 9, 1), TransactionType.SELL, "15", "300")
        report = svc.capital_gains_report("2025-26")
        assert len(report.rows) == 2
        first, second = report.rows[0], report.rows[1]
        assert first.buy_date == dt.date(2024, 1, 1) and first.is_long_term is True
        assert first.units == Decimal("10.0000")
        assert second.buy_date == dt.date(2025, 5, 1) and second.is_long_term is False
        assert second.units == Decimal("5.0000")
        # LTCG: 10*(300-100)=2000 ; STCG: 5*(300-200)=500
        assert report.long_term_gain_inr == Decimal("2000.00")
        assert report.short_term_gain_inr == Decimal("500.00")

    def test_fy_filters_disposals(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "20", "100")
        portfolio.add_transaction(inv.id, dt.date(2025, 2, 1), TransactionType.SELL, "10", "150")
        portfolio.add_transaction(inv.id, dt.date(2025, 6, 1), TransactionType.SELL, "10", "150")
        # FY 2024-25 (Apr 2024 - Mar 2025) only contains the Feb 2025 sell.
        report = svc.capital_gains_report("2024-25")
        assert len(report.rows) == 1
        assert report.rows[0].sell_date == dt.date(2025, 2, 1)

    def test_unmatched_sell_ignored_gracefully(self, svc, portfolio):
        # No buy lots: nothing to match (validation normally blocks this, but the
        # engine must not crash on legacy data).
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "100")
        portfolio.add_transaction(inv.id, dt.date(2025, 6, 1), TransactionType.SELL, "10", "200")
        report = svc.capital_gains_report("2025-26")
        assert len(report.rows) == 1


class TestTaxEstimates:
    def test_ltcg_exemption_applied(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "1000", "1000")
        # Sell for a 2L long-term gain (proceeds 1.2M, cost 1.0M).
        portfolio.add_transaction(inv.id, dt.date(2025, 6, 1), TransactionType.SELL, "1000", "1200")
        report = svc.capital_gains_report("2025-26")
        assert report.long_term_gain_inr == Decimal("200000.00")
        # 200000 - 125000 exemption = 75000 taxable; 12.5% = 9375.
        assert report.taxable_ltcg_inr == Decimal("75000.00")
        assert report.estimated_ltcg_tax_inr == Decimal("9375.00")

    def test_stcg_tax_estimate(self, svc, portfolio):
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(inv.id, dt.date(2025, 5, 1), TransactionType.BUY, "100", "100")
        portfolio.add_transaction(inv.id, dt.date(2025, 9, 1), TransactionType.SELL, "100", "200")
        report = svc.capital_gains_report("2025-26")
        # STCG 10000 * 20% = 2000.
        assert report.short_term_gain_inr == Decimal("10000.00")
        assert report.estimated_stcg_tax_inr == Decimal("2000.00")
