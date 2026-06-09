"""Income logging, monthly aggregation, and net cashflow (income − expenses)."""

from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.db.models import Category, Income
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_money
from wealthlog.services.expense import ExpenseService
from wealthlog.services.results import CashflowSummary

logger = get_logger(__name__)


class IncomeService:
    """CRUD and reporting for income entries.

    Args:
        session: An open database session. The caller owns the session lifecycle.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_income(
        self,
        date: dt.date,
        amount: Decimal | int | str,
        category_id: int | None = None,
        source: str | None = None,
        description: str | None = None,
        account_id: int | None = None,
    ) -> Income:
        """Add a new income entry.

        Args:
            date: The income date.
            amount: Amount in INR (positive). Stored quantized to 2dp.
            category_id: Optional INCOME-type category foreign key.
            source: Optional origin (employer, broker, bank…).
            description: Optional description.
            account_id: Optional account foreign key.

        Returns:
            The persisted :class:`Income`.

        Raises:
            ValueError: If ``amount`` is not strictly positive.
        """
        money = to_money(amount)
        if money <= 0:
            raise ValueError("Income amount must be positive")
        income = Income(
            date=date,
            amount_inr=money,
            category_id=category_id,
            source=source,
            description=description,
            account_id=account_id,
        )
        self.session.add(income)
        self.session.commit()
        self.session.refresh(income)
        logger.info("Added income %s on %s for %s", income.id, date, money)
        return income

    def list_income(
        self,
        start: dt.date | None = None,
        end: dt.date | None = None,
        category_id: int | None = None,
    ) -> list[Income]:
        """List income entries matching optional filters, newest first."""
        statement = select(Income)
        if start is not None:
            statement = statement.where(Income.date >= start)
        if end is not None:
            statement = statement.where(Income.date <= end)
        if category_id is not None:
            statement = statement.where(Income.category_id == category_id)
        statement = statement.order_by(Income.date.desc(), Income.id.desc())
        return list(self.session.exec(statement).all())

    def delete_income(self, income_id: int) -> bool:
        """Delete an income entry by id; ``True`` if a row was deleted."""
        income = self.session.get(Income, income_id)
        if income is None:
            return False
        self.session.delete(income)
        self.session.commit()
        return True

    def monthly_income_summary(self, year: int, month: int) -> dict[str, Decimal]:
        """Total income per category name for a calendar month.

        Raises:
            ValueError: If ``month`` is out of range.
        """
        if not 1 <= month <= 12:
            raise ValueError("month must be in 1..12")
        last_day = calendar.monthrange(year, month)[1]
        rows = self.list_income(start=dt.date(year, month, 1), end=dt.date(year, month, last_day))
        by_category: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for row in rows:
            by_category[self._category_name(row.category_id)] += row.amount_inr
        return {k: to_money(v) for k, v in by_category.items()}

    def net_cashflow(self, year: int, month: int) -> CashflowSummary:
        """Income minus expenses for a calendar month."""
        income_total = to_money(
            sum(self.monthly_income_summary(year, month).values(), Decimal("0.00"))
        )
        expense_total = ExpenseService(self.session).monthly_summary(year, month).total_inr
        return CashflowSummary(
            year=year,
            month=month,
            income_inr=income_total,
            expenses_inr=expense_total,
            net_inr=to_money(income_total - expense_total),
        )

    def _category_name(self, category_id: int | None) -> str:
        if category_id is None:
            return "Uncategorized"
        cat = self.session.get(Category, category_id)
        return cat.name if cat else "Uncategorized"
