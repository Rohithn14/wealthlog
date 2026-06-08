"""Expense logging, filtering, and monthly aggregation."""

from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.db.models import Category, Expense
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_money
from wealthlog.services.results import MonthlySummary

logger = get_logger(__name__)


class ExpenseService:
    """CRUD and reporting for expenses.

    Args:
        session: An open database session. The caller owns the session lifecycle.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_expense(
        self,
        date: dt.date,
        amount: Decimal | int | str,
        category_id: int | None = None,
        subcategory: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        account_id: int | None = None,
    ) -> Expense:
        """Add a new expense.

        Args:
            date: The expense date.
            amount: Amount in INR (positive). Stored quantized to 2dp.
            category_id: Optional category foreign key.
            subcategory: Optional free-text subcategory.
            description: Optional description.
            tags: Optional list of string tags.
            account_id: Optional account foreign key.

        Returns:
            The persisted :class:`Expense`.

        Raises:
            ValueError: If ``amount`` is not strictly positive.
        """
        money = to_money(amount)
        if money <= 0:
            raise ValueError("Expense amount must be positive")
        expense = Expense(
            date=date,
            amount_inr=money,
            category_id=category_id,
            subcategory=subcategory,
            description=description,
            tags=tags or [],
            account_id=account_id,
        )
        self.session.add(expense)
        self.session.commit()
        self.session.refresh(expense)
        logger.info("Added expense %s on %s for %s", expense.id, date, money)
        return expense

    def get_expense(self, expense_id: int) -> Expense | None:
        """Return an expense by id, or ``None`` if not found."""
        return self.session.get(Expense, expense_id)

    def list_expenses(
        self,
        start: dt.date | None = None,
        end: dt.date | None = None,
        category_id: int | None = None,
        tags: list[str] | None = None,
        account_id: int | None = None,
    ) -> list[Expense]:
        """List expenses matching optional filters, newest first.

        Args:
            start: Inclusive lower date bound.
            end: Inclusive upper date bound.
            category_id: Restrict to a category.
            tags: Restrict to expenses containing **all** given tags.
            account_id: Restrict to an account.

        Returns:
            Matching expenses ordered by date descending, then id descending.
        """
        statement = select(Expense)
        if start is not None:
            statement = statement.where(Expense.date >= start)
        if end is not None:
            statement = statement.where(Expense.date <= end)
        if category_id is not None:
            statement = statement.where(Expense.category_id == category_id)
        if account_id is not None:
            statement = statement.where(Expense.account_id == account_id)
        statement = statement.order_by(Expense.date.desc(), Expense.id.desc())
        results = list(self.session.exec(statement).all())
        if tags:
            wanted = set(tags)
            results = [e for e in results if wanted.issubset(set(e.tags))]
        return results

    def delete_expense(self, expense_id: int) -> bool:
        """Delete an expense by id.

        Returns:
            ``True`` if a row was deleted, ``False`` if no such expense existed.
        """
        expense = self.session.get(Expense, expense_id)
        if expense is None:
            return False
        self.session.delete(expense)
        self.session.commit()
        return True

    def monthly_summary(self, year: int, month: int) -> MonthlySummary:
        """Summarise expenses for a calendar month.

        Args:
            year: Four-digit year.
            month: Month (1-12).

        Returns:
            A :class:`MonthlySummary` with the total, count, and per-category totals.

        Raises:
            ValueError: If ``month`` is out of range.
        """
        if not 1 <= month <= 12:
            raise ValueError("month must be in 1..12")
        last_day = calendar.monthrange(year, month)[1]
        start = dt.date(year, month, 1)
        end = dt.date(year, month, last_day)
        expenses = self.list_expenses(start=start, end=end)

        by_category: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        total = Decimal("0.00")
        for exp in expenses:
            total += exp.amount_inr
            name = self._category_name(exp.category_id)
            by_category[name] += exp.amount_inr

        return MonthlySummary(
            year=year,
            month=month,
            total_inr=to_money(total),
            count=len(expenses),
            by_category={k: to_money(v) for k, v in by_category.items()},
        )

    def _category_name(self, category_id: int | None) -> str:
        if category_id is None:
            return "Uncategorized"
        cat = self.session.get(Category, category_id)
        return cat.name if cat else "Uncategorized"
