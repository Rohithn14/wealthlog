"""Tests for IncomeService: CRUD, monthly summary, and net cashflow."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.constants import CategoryType
from wealthlog.db.models import Category
from wealthlog.services.expense import ExpenseService
from wealthlog.services.income import IncomeService


@pytest.fixture
def svc(db_session):
    return IncomeService(db_session)


@pytest.fixture
def salary_category(db_session):
    cat = Category(name="Salary", type=CategoryType.INCOME)
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


class TestAddIncome:
    def test_add_and_quantize(self, svc):
        row = svc.add_income(dt.date(2026, 6, 1), "85000.005")
        assert row.amount_inr == Decimal("85000.01")
        assert row.id is not None

    def test_zero_amount_raises(self, svc):
        with pytest.raises(ValueError):
            svc.add_income(dt.date(2026, 6, 1), "0")

    def test_negative_amount_raises(self, svc):
        with pytest.raises(ValueError):
            svc.add_income(dt.date(2026, 6, 1), "-10")

    def test_delete(self, svc):
        row = svc.add_income(dt.date(2026, 6, 1), "100")
        assert svc.delete_income(row.id) is True
        assert svc.delete_income(row.id) is False


class TestListAndSummary:
    def test_list_filters_by_range(self, svc):
        svc.add_income(dt.date(2026, 5, 31), "1")
        svc.add_income(dt.date(2026, 6, 1), "2")
        rows = svc.list_income(start=dt.date(2026, 6, 1))
        assert [r.amount_inr for r in rows] == [Decimal("2.00")]

    def test_monthly_summary_by_category(self, svc, salary_category):
        svc.add_income(dt.date(2026, 6, 1), "85000", category_id=salary_category.id)
        svc.add_income(dt.date(2026, 6, 15), "500")
        summary = svc.monthly_income_summary(2026, 6)
        assert summary["Salary"] == Decimal("85000.00")
        assert summary["Uncategorized"] == Decimal("500.00")

    def test_bad_month_raises(self, svc):
        with pytest.raises(ValueError):
            svc.monthly_income_summary(2026, 13)


class TestNetCashflow:
    def test_income_minus_expenses(self, svc, db_session):
        svc.add_income(dt.date(2026, 6, 1), "1000")
        ExpenseService(db_session).add_expense(dt.date(2026, 6, 10), "400")
        flow = svc.net_cashflow(2026, 6)
        assert flow.income_inr == Decimal("1000.00")
        assert flow.expenses_inr == Decimal("400.00")
        assert flow.net_inr == Decimal("600.00")

    def test_negative_net(self, svc, db_session):
        ExpenseService(db_session).add_expense(dt.date(2026, 6, 10), "400")
        flow = svc.net_cashflow(2026, 6)
        assert flow.net_inr == Decimal("-400.00")
