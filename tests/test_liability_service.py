"""Tests for LiabilityService (Task 2b) and its net-worth integration."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import AssetType, LiabilityCategory, TransactionType
from wealthlog.db.models import PriceCache
from wealthlog.services.liability import LiabilityService
from wealthlog.services.networth import NetWorthService
from wealthlog.services.portfolio import PortfolioService


@pytest.fixture
def svc(db_session):
    return LiabilityService(db_session)


class TestLiabilityService:
    def test_add_and_total(self, svc):
        svc.add_liability("Home loan", "2500000", category=LiabilityCategory.LOAN)
        svc.add_liability("Credit card", "45000", category=LiabilityCategory.CREDIT_CARD)
        assert svc.total_liabilities() == Decimal("2545000.00")

    def test_list_sorted_desc(self, svc):
        svc.add_liability("Small", "100")
        svc.add_liability("Big", "9999")
        rows = svc.list_liabilities()
        assert [r.name for r in rows] == ["Big", "Small"]
        assert rows[0].category == LiabilityCategory.OTHER

    def test_update_amount(self, svc):
        row = svc.add_liability("Loan", "1000")
        assert svc.update_amount(row.id, "750") is True
        assert svc.total_liabilities() == Decimal("750.00")
        assert svc.update_amount(9999, "1") is False

    def test_delete(self, svc):
        row = svc.add_liability("Loan", "1000")
        assert svc.delete_liability(row.id) is True
        assert svc.total_liabilities() == Decimal("0.00")
        assert svc.delete_liability(row.id) is False

    def test_empty_total_is_zero(self, svc):
        assert svc.total_liabilities() == Decimal("0.00")


class TestNetWorthIntegration:
    def test_liabilities_offset_net_worth(self, db_session):
        pf = PortfolioService(db_session)
        inv = pf.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        pf.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
        db_session.add(
            PriceCache(
                investment_id=inv.id, price_native=Decimal("100"),
                price_inr=Decimal("100"), fetched_at=dt.datetime.now(),
            )
        )
        db_session.commit()
        LiabilityService(db_session).add_liability("Loan", "300")

        nw = NetWorthService(db_session).calculate_net_worth()
        assert nw.total_assets_inr == Decimal("1000.00")
        assert nw.total_liabilities_inr == Decimal("300.00")
        assert nw.net_worth_inr == Decimal("700.00")
