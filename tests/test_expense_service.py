"""Tests for ExpenseService: add, list/filter, monthly summary, delete."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from wealthlog.db.models import Category
from wealthlog.services.expense import ExpenseService


@pytest.fixture
def svc(db_session):
    return ExpenseService(db_session)


@pytest.fixture
def category(db_session):
    cat = Category(name="Food")
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


class TestAddExpense:
    def test_basic_add(self, svc):
        e = svc.add_expense(dt.date(2026, 1, 5), "150.50")
        assert e.id is not None
        assert e.amount_inr == Decimal("150.50")

    def test_quantizes_amount(self, svc):
        e = svc.add_expense(dt.date(2026, 1, 5), "150.005")
        assert e.amount_inr == Decimal("150.01")

    def test_accepts_int_and_decimal(self, svc):
        assert svc.add_expense(dt.date(2026, 1, 1), 100).amount_inr == Decimal("100.00")
        assert svc.add_expense(dt.date(2026, 1, 1), Decimal("9.9")).amount_inr == Decimal("9.90")

    def test_rejects_zero(self, svc):
        with pytest.raises(ValueError):
            svc.add_expense(dt.date(2026, 1, 1), "0")

    def test_rejects_negative(self, svc):
        with pytest.raises(ValueError):
            svc.add_expense(dt.date(2026, 1, 1), "-5")

    def test_rejects_float(self, svc):
        with pytest.raises(TypeError):
            svc.add_expense(dt.date(2026, 1, 1), 10.5)

    def test_stores_tags_and_meta(self, svc, category):
        e = svc.add_expense(
            dt.date(2026, 1, 1), "10", category_id=category.id,
            subcategory="lunch", description="dosa", tags=["food", "outside"],
        )
        assert e.tags == ["food", "outside"]
        assert e.subcategory == "lunch"
        assert e.category_id == category.id


class TestListExpenses:
    def _seed(self, svc, category):
        svc.add_expense(dt.date(2026, 1, 1), "100", category_id=category.id, tags=["a"])
        svc.add_expense(dt.date(2026, 1, 15), "200", tags=["a", "b"])
        svc.add_expense(dt.date(2026, 2, 1), "300", category_id=category.id)

    def test_list_all(self, svc, category):
        self._seed(svc, category)
        assert len(svc.list_expenses()) == 3

    def test_sorted_desc_by_date(self, svc, category):
        self._seed(svc, category)
        rows = svc.list_expenses()
        assert rows[0].date >= rows[-1].date

    def test_filter_date_range(self, svc, category):
        self._seed(svc, category)
        rows = svc.list_expenses(start=dt.date(2026, 1, 1), end=dt.date(2026, 1, 31))
        assert len(rows) == 2

    def test_filter_category(self, svc, category):
        self._seed(svc, category)
        rows = svc.list_expenses(category_id=category.id)
        assert len(rows) == 2

    def test_filter_tags_subset(self, svc, category):
        self._seed(svc, category)
        assert len(svc.list_expenses(tags=["a"])) == 2
        assert len(svc.list_expenses(tags=["a", "b"])) == 1
        assert len(svc.list_expenses(tags=["nonexistent"])) == 0

    def test_empty_when_no_match(self, svc):
        assert svc.list_expenses(start=dt.date(2030, 1, 1)) == []


class TestMonthlySummary:
    def test_totals_and_count(self, svc, category):
        svc.add_expense(dt.date(2026, 3, 1), "100", category_id=category.id)
        svc.add_expense(dt.date(2026, 3, 20), "250", category_id=category.id)
        svc.add_expense(dt.date(2026, 4, 1), "999")  # other month
        summary = svc.monthly_summary(2026, 3)
        assert summary.total_inr == Decimal("350.00")
        assert summary.count == 2

    def test_by_category_breakdown(self, svc, category):
        svc.add_expense(dt.date(2026, 3, 1), "100", category_id=category.id)
        svc.add_expense(dt.date(2026, 3, 2), "50")  # uncategorized
        summary = svc.monthly_summary(2026, 3)
        assert summary.by_category["Food"] == Decimal("100.00")
        assert summary.by_category["Uncategorized"] == Decimal("50.00")

    def test_empty_month(self, svc):
        summary = svc.monthly_summary(2026, 7)
        assert summary.total_inr == Decimal("0.00")
        assert summary.count == 0

    def test_invalid_month_raises(self, svc):
        with pytest.raises(ValueError):
            svc.monthly_summary(2026, 13)

    def test_handles_month_boundaries(self, svc):
        svc.add_expense(dt.date(2026, 2, 28), "10")  # last day of Feb (non-leap)
        summary = svc.monthly_summary(2026, 2)
        assert summary.count == 1


class TestDelete:
    def test_delete_existing(self, svc):
        e = svc.add_expense(dt.date(2026, 1, 1), "10")
        assert svc.delete_expense(e.id) is True
        assert svc.get_expense(e.id) is None

    def test_delete_missing_returns_false(self, svc):
        assert svc.delete_expense(99999) is False
