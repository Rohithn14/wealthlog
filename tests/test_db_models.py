"""Tests for SQLModel persistence: precision, enums, JSON tags, and constraints."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from wealthlog.constants import (
    AssetType,
    CategoryType,
    CompoundingFrequency,
    TransactionType,
)
from wealthlog.db.models import (
    Account,
    Budget,
    Category,
    Expense,
    FdDetails,
    FxRate,
    Investment,
    PriceCache,
    Transaction,
)


class TestDecimalPersistence:
    def test_money_round_trips_exactly(self, db_session):
        db_session.add(Expense(date=dt.date(2026, 1, 1), amount_inr=Decimal("1234.56")))
        db_session.commit()
        row = db_session.exec(select(Expense)).one()
        assert row.amount_inr == Decimal("1234.56")
        assert isinstance(row.amount_inr, Decimal)

    def test_money_quantized_to_two_places_on_load(self, db_session):
        db_session.add(Expense(date=dt.date(2026, 1, 1), amount_inr=Decimal("1000")))
        db_session.commit()
        row = db_session.exec(select(Expense)).one()
        assert row.amount_inr.as_tuple().exponent == -2

    def test_fx_six_places(self, db_session):
        db_session.add(
            FxRate(
                currency_pair="USD_INR",
                rate=Decimal("83.123456"),
                fetched_at=dt.datetime(2026, 1, 1, 12, 0, 0),
            )
        )
        db_session.commit()
        row = db_session.exec(select(FxRate)).one()
        assert row.rate == Decimal("83.123456")

    def test_no_float_corruption(self, db_session):
        # 0.1 + 0.2 famously != 0.3 in float; Decimal storage must be exact.
        db_session.add(Expense(date=dt.date(2026, 1, 1), amount_inr=Decimal("0.30")))
        db_session.commit()
        row = db_session.exec(select(Expense)).one()
        assert row.amount_inr == Decimal("0.30")


class TestEnumPersistence:
    def test_asset_type_stored_and_loaded(self, db_session):
        db_session.add(Investment(symbol="INFY.NS", name="Infosys", asset_type=AssetType.STOCK_IN))
        db_session.commit()
        row = db_session.exec(select(Investment)).one()
        assert row.asset_type == AssetType.STOCK_IN

    def test_category_type_default(self, db_session):
        db_session.add(Category(name="Food"))
        db_session.commit()
        row = db_session.exec(select(Category)).one()
        assert row.type == CategoryType.EXPENSE

    def test_transaction_type(self, db_session):
        inv = Investment(symbol="X", name="X", asset_type=AssetType.STOCK_US)
        db_session.add(inv)
        db_session.commit()
        db_session.add(
            Transaction(
                investment_id=inv.id,
                date=dt.date(2026, 1, 1),
                type=TransactionType.BUY,
                units=Decimal("10"),
                price_per_unit=Decimal("100.5"),
                amount_inr=Decimal("83500.00"),
            )
        )
        db_session.commit()
        row = db_session.exec(select(Transaction)).one()
        assert row.type == TransactionType.BUY


class TestJsonTags:
    def test_tags_persist_as_list(self, db_session):
        db_session.add(
            Expense(date=dt.date(2026, 1, 1), amount_inr=Decimal("10"), tags=["food", "lunch"])
        )
        db_session.commit()
        row = db_session.exec(select(Expense)).one()
        assert row.tags == ["food", "lunch"]

    def test_empty_tags_default(self, db_session):
        db_session.add(Expense(date=dt.date(2026, 1, 1), amount_inr=Decimal("10")))
        db_session.commit()
        row = db_session.exec(select(Expense)).one()
        assert row.tags == []


class TestConstraints:
    def test_category_unique_name_type(self, db_session):
        db_session.add(Category(name="Food", type=CategoryType.EXPENSE))
        db_session.commit()
        db_session.add(Category(name="Food", type=CategoryType.EXPENSE))
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_same_name_different_type_allowed(self, db_session):
        db_session.add(Category(name="Bonus", type=CategoryType.EXPENSE))
        db_session.add(Category(name="Bonus", type=CategoryType.INCOME))
        db_session.commit()
        assert len(db_session.exec(select(Category)).all()) == 2

    def test_budget_unique_category_month_year(self, db_session):
        cat = Category(name="Travel")
        db_session.add(cat)
        db_session.commit()
        db_session.add(
            Budget(category_id=cat.id, month=6, year=2026, limit_amount_inr=Decimal("5000"))
        )
        db_session.commit()
        db_session.add(
            Budget(category_id=cat.id, month=6, year=2026, limit_amount_inr=Decimal("9000"))
        )
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_fd_details_investment_unique(self, db_session):
        inv = Investment(symbol="FD1", name="SBI FD", asset_type=AssetType.FD)
        db_session.add(inv)
        db_session.commit()
        common = dict(
            principal=Decimal("100000"),
            interest_rate=Decimal("7.1"),
            start_date=dt.date(2026, 1, 1),
            maturity_date=dt.date(2027, 1, 1),
            compounding=CompoundingFrequency.QUARTERLY,
        )
        db_session.add(FdDetails(investment_id=inv.id, **common))
        db_session.commit()
        db_session.add(FdDetails(investment_id=inv.id, **common))
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestPriceCacheAndAccounts:
    def test_price_cache_round_trip(self, db_session):
        inv = Investment(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK_US,
                         currency_native="USD")
        db_session.add(inv)
        db_session.commit()
        db_session.add(
            PriceCache(
                investment_id=inv.id,
                price_native=Decimal("190.2500"),
                price_inr=Decimal("15890.1000"),
                fx_rate_used=Decimal("83.500000"),
                fetched_at=dt.datetime(2026, 1, 1, 9, 30, 0),
            )
        )
        db_session.commit()
        row = db_session.exec(select(PriceCache)).one()
        assert row.price_native == Decimal("190.2500")
        assert row.fx_rate_used == Decimal("83.500000")

    def test_account_persist(self, db_session):
        db_session.add(Account(name="HDFC Savings", type="bank", institution="HDFC"))
        db_session.commit()
        row = db_session.exec(select(Account)).one()
        assert row.name == "HDFC Savings"

    def test_date_stored_as_date(self, db_session):
        db_session.add(Expense(date=dt.date(2026, 3, 15), amount_inr=Decimal("10")))
        db_session.commit()
        row = db_session.exec(select(Expense)).one()
        assert row.date == dt.date(2026, 3, 15)
