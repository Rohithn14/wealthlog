"""Tests for SIPService: schedules and pending-instalment detection."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import AssetType, TransactionType
from wealthlog.services.portfolio import PortfolioService
from wealthlog.services.sip import SIPService


@pytest.fixture
def portfolio(db_session):
    return PortfolioService(db_session)


@pytest.fixture
def svc(db_session):
    return SIPService(db_session)


@pytest.fixture
def mf(portfolio):
    return portfolio.add_investment("120503", "Index Fund", AssetType.MF)


class TestAddSchedule:
    def test_unknown_investment_raises(self, svc):
        with pytest.raises(ValueError):
            svc.add_schedule(999, "5000", 1, dt.date(2026, 1, 1))

    def test_bad_day_raises(self, svc, mf):
        with pytest.raises(ValueError):
            svc.add_schedule(mf.id, "5000", 32, dt.date(2026, 1, 1))

    def test_end_before_start_raises(self, svc, mf):
        with pytest.raises(ValueError):
            svc.add_schedule(mf.id, "5000", 1, dt.date(2026, 2, 1), dt.date(2026, 1, 1))


class TestPendingSips:
    def test_all_pending_when_no_transactions(self, svc, mf):
        svc.add_schedule(mf.id, "5000", 5, dt.date(2026, 1, 1))
        pending = svc.get_pending_sips(as_of=dt.date(2026, 3, 10))
        assert [p.due_date for p in pending] == [
            dt.date(2026, 1, 5), dt.date(2026, 2, 5), dt.date(2026, 3, 5),
        ]
        assert pending[0].amount_inr == Decimal("5000.00")
        assert pending[0].symbol == "120503"

    def test_recorded_month_not_pending(self, svc, mf, portfolio):
        svc.add_schedule(mf.id, "5000", 5, dt.date(2026, 1, 1))
        # Recorded a couple of days late — still counts for the month.
        portfolio.add_transaction(
            mf.id, dt.date(2026, 2, 7), TransactionType.SIP, "50", "100"
        )
        pending = svc.get_pending_sips(as_of=dt.date(2026, 3, 10))
        assert [p.due_date for p in pending] == [dt.date(2026, 1, 5), dt.date(2026, 3, 5)]

    def test_end_date_caps_horizon(self, svc, mf):
        svc.add_schedule(mf.id, "5000", 5, dt.date(2026, 1, 1), dt.date(2026, 1, 31))
        pending = svc.get_pending_sips(as_of=dt.date(2026, 6, 1))
        assert [p.due_date for p in pending] == [dt.date(2026, 1, 5)]

    def test_due_day_clamped_to_month_length(self, svc, mf):
        svc.add_schedule(mf.id, "5000", 31, dt.date(2026, 2, 1))
        pending = svc.get_pending_sips(as_of=dt.date(2026, 2, 28))
        assert [p.due_date for p in pending] == [dt.date(2026, 2, 28)]

    def test_inactive_schedule_ignored(self, svc, mf):
        schedule = svc.add_schedule(mf.id, "5000", 5, dt.date(2026, 1, 1))
        svc.deactivate(schedule.id)
        assert svc.get_pending_sips(as_of=dt.date(2026, 3, 1)) == []
