"""Tests for BudgetService: upsert, status computation, overage alerts."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.db.models import Category
from wealthlog.services.budget import BudgetService
from wealthlog.services.expense import ExpenseService


@pytest.fixture
def budget_svc(db_session):
    return BudgetService(db_session)


@pytest.fixture
def expense_svc(db_session):
    return ExpenseService(db_session)


@pytest.fixture
def category(db_session):
    cat = Category(name="Food")
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


class TestSetBudget:
    def test_creates_budget(self, budget_svc, category):
        b = budget_svc.set_budget(category.id, 6, 2026, "5000")
        assert b.id is not None
        assert b.limit_amount_inr == Decimal("5000.00")

    def test_upsert_updates_existing(self, budget_svc, category):
        first = budget_svc.set_budget(category.id, 6, 2026, "5000")
        second = budget_svc.set_budget(category.id, 6, 2026, "8000")
        assert first.id == second.id
        assert second.limit_amount_inr == Decimal("8000.00")

    def test_rejects_invalid_month(self, budget_svc, category):
        with pytest.raises(ValueError):
            budget_svc.set_budget(category.id, 0, 2026, "5000")

    def test_rejects_non_positive_limit(self, budget_svc, category):
        with pytest.raises(ValueError):
            budget_svc.set_budget(category.id, 6, 2026, "0")


class TestBudgetStatus:
    def test_under_budget(self, budget_svc, expense_svc, category):
        budget_svc.set_budget(category.id, 6, 2026, "1000")
        expense_svc.add_expense(dt.date(2026, 6, 5), "400", category_id=category.id)
        status = budget_svc.get_budget_status(2026, 6)[0]
        assert status.spent_inr == Decimal("400.00")
        assert status.remaining_inr == Decimal("600.00")
        assert status.pct_used == Decimal("40.00")
        assert status.is_over is False

    def test_over_budget(self, budget_svc, expense_svc, category):
        budget_svc.set_budget(category.id, 6, 2026, "1000")
        expense_svc.add_expense(dt.date(2026, 6, 5), "1200", category_id=category.id)
        status = budget_svc.get_budget_status(2026, 6)[0]
        assert status.is_over is True
        assert status.remaining_inr == Decimal("-200.00")
        assert status.pct_used == Decimal("120.00")

    def test_exactly_at_limit_not_over(self, budget_svc, expense_svc, category):
        budget_svc.set_budget(category.id, 6, 2026, "1000")
        expense_svc.add_expense(dt.date(2026, 6, 5), "1000", category_id=category.id)
        status = budget_svc.get_budget_status(2026, 6)[0]
        assert status.is_over is False
        assert status.remaining_inr == Decimal("0.00")

    def test_only_counts_target_month(self, budget_svc, expense_svc, category):
        budget_svc.set_budget(category.id, 6, 2026, "1000")
        expense_svc.add_expense(dt.date(2026, 5, 31), "500", category_id=category.id)
        expense_svc.add_expense(dt.date(2026, 7, 1), "500", category_id=category.id)
        status = budget_svc.get_budget_status(2026, 6)[0]
        assert status.spent_inr == Decimal("0.00")

    def test_only_counts_target_category(self, budget_svc, expense_svc, category, db_session):
        other = Category(name="Travel")
        db_session.add(other)
        db_session.commit()
        budget_svc.set_budget(category.id, 6, 2026, "1000")
        expense_svc.add_expense(dt.date(2026, 6, 5), "900", category_id=other.id)
        status = budget_svc.get_budget_status(2026, 6)[0]
        assert status.spent_inr == Decimal("0.00")

    def test_no_budgets_empty(self, budget_svc):
        assert budget_svc.get_budget_status(2026, 6) == []


class TestAlerts:
    def test_alert_only_overages(self, budget_svc, expense_svc, db_session):
        food = Category(name="Food")
        travel = Category(name="Travel")
        db_session.add(food)
        db_session.add(travel)
        db_session.commit()
        budget_svc.set_budget(food.id, 6, 2026, "1000")
        budget_svc.set_budget(travel.id, 6, 2026, "1000")
        expense_svc.add_expense(dt.date(2026, 6, 1), "1500", category_id=food.id)
        expense_svc.add_expense(dt.date(2026, 6, 1), "500", category_id=travel.id)
        alerts = budget_svc.alert_overages(2026, 6)
        assert len(alerts) == 1
        assert alerts[0].category_name == "Food"

    def test_no_alerts_when_all_under(self, budget_svc, expense_svc, category):
        budget_svc.set_budget(category.id, 6, 2026, "1000")
        expense_svc.add_expense(dt.date(2026, 6, 1), "100", category_id=category.id)
        assert budget_svc.alert_overages(2026, 6) == []
