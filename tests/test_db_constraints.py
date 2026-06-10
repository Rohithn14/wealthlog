"""SQL CHECK constraints (2c / Bug #14): guard direct model writes.

Service layers already validate, but ``table=True`` SQLModels do not enforce
``Field(ge=...)`` on instantiation, so these lock the invariants at the DB level.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from wealthlog.constants import TransactionType
from wealthlog.db.models import Budget, Expense, Transaction


def test_expense_amount_must_be_positive(db_session):
    db_session.add(Expense(date=dt.date(2026, 1, 1), amount_inr="-5"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_budget_month_out_of_range_rejected(db_session):
    db_session.add(Budget(category_id=1, month=13, year=2026, limit_amount_inr="100"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_transaction_negative_units_rejected(db_session):
    db_session.add(
        Transaction(
            investment_id=1,
            date=dt.date(2026, 1, 1),
            type=TransactionType.BUY,
            units="-1",
            price_per_unit="10",
            amount_inr="10",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
