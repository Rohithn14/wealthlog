"""Tests for category seeding and session helpers."""

from __future__ import annotations

from sqlmodel import Session, select

from wealthlog.constants import CategoryType
from wealthlog.db.models import Category
from wealthlog.db.seed import (
    DEFAULT_EXPENSE_CATEGORIES,
    DEFAULT_INCOME_CATEGORIES,
    seed_categories,
)
from wealthlog.db.session import create_db_and_tables, get_engine, reset_engine


class TestSeed:
    def test_seeds_all_defaults(self, db_session):
        created = seed_categories(db_session)
        assert created == len(DEFAULT_EXPENSE_CATEGORIES) + len(DEFAULT_INCOME_CATEGORIES)

    def test_idempotent(self, db_session):
        seed_categories(db_session)
        second = seed_categories(db_session)
        assert second == 0

    def test_total_count_stable_after_double_seed(self, db_session):
        seed_categories(db_session)
        seed_categories(db_session)
        total = len(db_session.exec(select(Category)).all())
        assert total == len(DEFAULT_EXPENSE_CATEGORIES) + len(DEFAULT_INCOME_CATEGORIES)

    def test_expense_and_income_split(self, db_session):
        seed_categories(db_session)
        expenses = db_session.exec(
            select(Category).where(Category.type == CategoryType.EXPENSE)
        ).all()
        incomes = db_session.exec(
            select(Category).where(Category.type == CategoryType.INCOME)
        ).all()
        assert len(expenses) == len(DEFAULT_EXPENSE_CATEGORIES)
        assert len(incomes) == len(DEFAULT_INCOME_CATEGORIES)

    def test_categories_have_color_and_icon(self, db_session):
        seed_categories(db_session)
        for cat in db_session.exec(select(Category)).all():
            assert cat.color
            assert cat.icon


class TestSessionHelpers:
    def test_create_db_and_tables_idempotent(self):
        engine = get_engine()
        create_db_and_tables(engine)
        create_db_and_tables(engine)  # should not raise

    def test_get_engine_caches(self):
        assert get_engine() is get_engine()

    def test_reset_engine_rebuilds(self):
        first = get_engine()
        reset_engine()
        assert get_engine() is not first

    def test_session_context_manager(self):
        from wealthlog.db.session import get_session

        engine = get_engine()
        create_db_and_tables(engine)
        with get_session(engine) as session:
            assert isinstance(session, Session)
