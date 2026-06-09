"""Tests for RecurringExpenseService: rule CRUD and idempotent generation."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import RecurrenceFrequency
from wealthlog.services.expense import ExpenseService
from wealthlog.services.recurring import RecurringExpenseService


@pytest.fixture
def svc(db_session):
    return RecurringExpenseService(db_session)


class TestAddRule:
    def test_monthly_requires_day(self, svc):
        with pytest.raises(ValueError):
            svc.add_rule("100", RecurrenceFrequency.MONTHLY)

    def test_zero_amount_raises(self, svc):
        with pytest.raises(ValueError):
            svc.add_rule("0", RecurrenceFrequency.DAILY)

    def test_add_and_deactivate(self, svc):
        rule = svc.add_rule("100", RecurrenceFrequency.DAILY)
        assert rule.active is True
        assert svc.deactivate(rule.id) is True
        assert svc.list_rules() == []
        assert len(svc.list_rules(include_inactive=True)) == 1


class TestGenerate:
    def test_monthly_generates_on_clamped_day(self, svc, db_session):
        svc.add_rule(
            "500", RecurrenceFrequency.MONTHLY, day_of_month=31,
            description="rent", start_from=dt.date(2026, 1, 15),
        )
        created = svc.generate_due_instances(as_of=dt.date(2026, 3, 31))
        # Jan 31 (after anchor Jan 15), Feb 28 (clamped), Mar 31.
        assert [e.date for e in created] == [
            dt.date(2026, 1, 31), dt.date(2026, 2, 28), dt.date(2026, 3, 31),
        ]
        assert all(e.amount_inr == Decimal("500.00") for e in created)
        assert all("recurring" in e.tags for e in created)

    def test_idempotent(self, svc):
        svc.add_rule(
            "500", RecurrenceFrequency.MONTHLY, day_of_month=1,
            start_from=dt.date(2026, 1, 15),
        )
        first = svc.generate_due_instances(as_of=dt.date(2026, 3, 15))
        second = svc.generate_due_instances(as_of=dt.date(2026, 3, 15))
        assert len(first) == 2  # Feb 1, Mar 1
        assert second == []

    def test_daily_and_weekly(self, svc):
        svc.add_rule("10", RecurrenceFrequency.DAILY, start_from=dt.date(2026, 6, 1))
        svc.add_rule("70", RecurrenceFrequency.WEEKLY, start_from=dt.date(2026, 6, 1))
        created = svc.generate_due_instances(as_of=dt.date(2026, 6, 8))
        daily = [e for e in created if e.amount_inr == Decimal("10.00")]
        weekly = [e for e in created if e.amount_inr == Decimal("70.00")]
        assert len(daily) == 7  # Jun 2..8
        assert [e.date for e in weekly] == [dt.date(2026, 6, 8)]

    def test_inactive_rule_skipped(self, svc):
        rule = svc.add_rule("10", RecurrenceFrequency.DAILY, start_from=dt.date(2026, 6, 1))
        svc.deactivate(rule.id)
        assert svc.generate_due_instances(as_of=dt.date(2026, 6, 8)) == []

    def test_created_rows_visible_to_expense_service(self, svc, db_session):
        svc.add_rule(
            "500", RecurrenceFrequency.MONTHLY, day_of_month=1,
            start_from=dt.date(2026, 5, 15),
        )
        svc.generate_due_instances(as_of=dt.date(2026, 6, 2))
        summary = ExpenseService(db_session).monthly_summary(2026, 6)
        assert summary.total_inr == Decimal("500.00")
