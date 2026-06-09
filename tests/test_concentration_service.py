"""Tests for ConcentrationService: single-name, sector, and asset-class weights."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import AssetType, TransactionType
from wealthlog.db.models import PriceCache
from wealthlog.services.concentration import ConcentrationService
from wealthlog.services.portfolio import PortfolioService


@pytest.fixture
def portfolio(db_session):
    return PortfolioService(db_session)


@pytest.fixture
def svc(db_session):
    return ConcentrationService(db_session)


def _add_price(session, investment_id, price_inr):
    session.add(
        PriceCache(
            investment_id=investment_id,
            price_native=Decimal(price_inr),
            price_inr=Decimal(price_inr),
            fetched_at=dt.datetime.now(),
        )
    )
    session.commit()


def _holding(portfolio, session, symbol, units, price, sector=None):
    inv = portfolio.add_investment(symbol, symbol, AssetType.STOCK_IN, sector=sector)
    portfolio.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, units, price)
    _add_price(session, inv.id, price)
    return inv


class TestConcentration:
    def test_empty_portfolio(self, svc):
        report = svc.concentration_report()
        assert report.total_value_inr == Decimal("0.00")
        assert report.top_holdings == []

    def test_weights_and_flag(self, svc, portfolio, db_session):
        # 9000 (90%) + 1000 (10%) = 10000 total.
        _holding(portfolio, db_session, "BIG.NS", "90", "100", sector="IT")
        _holding(portfolio, db_session, "SMALL.NS", "10", "100", sector="Banking")
        report = svc.concentration_report(threshold_pct="10")
        assert report.total_value_inr == Decimal("10000.00")
        assert report.top_holdings[0].symbol == "BIG.NS"
        assert report.top_holdings[0].pct_of_total == Decimal("90.00")
        assert report.top_holdings[0].is_concentrated is True
        # 10% is not strictly greater than the 10% threshold.
        assert report.top_holdings[1].is_concentrated is False

    def test_sector_weights(self, svc, portfolio, db_session):
        _holding(portfolio, db_session, "A.NS", "10", "100", sector="IT")
        _holding(portfolio, db_session, "B.NS", "10", "100", sector="IT")
        _holding(portfolio, db_session, "C.NS", "20", "100", sector="Banking")
        report = svc.concentration_report()
        weights = {w.label: w.pct_of_total for w in report.by_sector}
        assert weights["IT"] == Decimal("50.00")  # (1000+1000)/4000
        assert weights["Banking"] == Decimal("50.00")

    def test_unclassified_sector(self, svc, portfolio, db_session):
        _holding(portfolio, db_session, "A.NS", "10", "100")  # no sector
        report = svc.concentration_report()
        assert report.by_sector[0].label == "Unclassified"

    def test_top_n_limits(self, svc, portfolio, db_session):
        for i in range(5):
            _holding(portfolio, db_session, f"S{i}.NS", "10", "100")
        report = svc.concentration_report(top_n=2)
        assert len(report.top_holdings) == 2

    def test_set_sector_updates(self, svc, portfolio, db_session):
        inv = _holding(portfolio, db_session, "A.NS", "10", "100")
        portfolio.set_sector(inv.id, "Pharma")
        report = svc.concentration_report()
        assert report.by_sector[0].label == "Pharma"
