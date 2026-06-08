"""Per-category monthly budgets and overage detection."""

from __future__ import annotations

import calendar
import datetime as dt
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.db.models import Budget, Category, Expense
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_money
from wealthlog.services.results import BudgetStatus

logger = get_logger(__name__)


class BudgetService:
    """Set monthly spending limits and report status against actual spending.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def set_budget(
        self,
        category_id: int,
        month: int,
        year: int,
        limit: Decimal | int | str,
    ) -> Budget:
        """Create or update the budget for a category and month (upsert).

        Args:
            category_id: Category to budget.
            month: Month (1-12).
            year: Four-digit year.
            limit: Monthly spending limit in INR (positive).

        Returns:
            The persisted :class:`Budget`.

        Raises:
            ValueError: If ``month`` is invalid or ``limit`` is not positive.
        """
        if not 1 <= month <= 12:
            raise ValueError("month must be in 1..12")
        amount = to_money(limit)
        if amount <= 0:
            raise ValueError("Budget limit must be positive")

        existing = self.session.exec(
            select(Budget).where(
                Budget.category_id == category_id,
                Budget.month == month,
                Budget.year == year,
            )
        ).first()
        if existing is not None:
            existing.limit_amount_inr = amount
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        budget = Budget(
            category_id=category_id, month=month, year=year, limit_amount_inr=amount
        )
        self.session.add(budget)
        self.session.commit()
        self.session.refresh(budget)
        logger.info("Set budget for category %s %d-%02d = %s", category_id, year, month, amount)
        return budget

    def _spent(self, category_id: int, year: int, month: int) -> Decimal:
        last_day = calendar.monthrange(year, month)[1]
        rows = self.session.exec(
            select(Expense).where(
                Expense.category_id == category_id,
                Expense.date >= dt.date(year, month, 1),
                Expense.date <= dt.date(year, month, last_day),
            )
        ).all()
        return to_money(sum((r.amount_inr for r in rows), Decimal("0.00")))

    def get_budget_status(self, year: int, month: int) -> list[BudgetStatus]:
        """Return budget-vs-spent status for every budgeted category in a month.

        Args:
            year: Four-digit year.
            month: Month (1-12).

        Returns:
            A list of :class:`BudgetStatus`, one per budget defined for that month.
        """
        budgets = self.session.exec(
            select(Budget).where(Budget.month == month, Budget.year == year)
        ).all()
        statuses: list[BudgetStatus] = []
        for budget in budgets:
            spent = self._spent(budget.category_id, year, month)
            limit = budget.limit_amount_inr
            remaining = to_money(limit - spent)
            pct = (spent / limit * Decimal(100)) if limit > 0 else Decimal(0)
            category = self.session.get(Category, budget.category_id)
            statuses.append(
                BudgetStatus(
                    category_id=budget.category_id,
                    category_name=category.name if category else "Unknown",
                    month=month,
                    year=year,
                    limit_inr=limit,
                    spent_inr=spent,
                    remaining_inr=remaining,
                    pct_used=to_money(pct),
                    is_over=spent > limit,
                )
            )
        return statuses

    def alert_overages(self, year: int, month: int) -> list[BudgetStatus]:
        """Return only the budget statuses that are over their limit."""
        return [s for s in self.get_budget_status(year, month) if s.is_over]
