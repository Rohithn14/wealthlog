"""Recurring expense rules and idempotent instance generation.

Each rule carries a ``last_generated`` watermark; generation enumerates due dates in
``(last_generated, as_of]`` and advances the watermark in the same commit, so
re-running for the same date creates nothing new.
"""

from __future__ import annotations

import calendar
import datetime as dt
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.constants import RecurrenceFrequency
from wealthlog.db.models import Expense, RecurringExpense
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_money

logger = get_logger(__name__)


def _clamped_day(year: int, month: int, day: int) -> dt.date:
    return dt.date(year, month, min(day, calendar.monthrange(year, month)[1]))


class RecurringExpenseService:
    """Manage recurring-expense rules and materialise due expenses.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_rule(
        self,
        amount: Decimal | int | str,
        frequency: RecurrenceFrequency,
        category_id: int | None = None,
        day_of_month: int | None = None,
        description: str | None = None,
        start_from: dt.date | None = None,
    ) -> RecurringExpense:
        """Create a recurring-expense rule.

        Args:
            amount: Instance amount in INR (positive).
            frequency: DAILY, WEEKLY, or MONTHLY.
            category_id: Optional category for generated expenses.
            day_of_month: Required for MONTHLY (1-31, clamped to month length).
            description: Copied onto generated expenses.
            start_from: Generation starts after this date (defaults to today, so
                no historical backfill).

        Returns:
            The persisted :class:`RecurringExpense`.

        Raises:
            ValueError: If the amount is not positive or MONTHLY lacks a valid day.
        """
        money = to_money(amount)
        if money <= 0:
            raise ValueError("Recurring amount must be positive")
        if frequency == RecurrenceFrequency.MONTHLY:
            if day_of_month is None or not 1 <= day_of_month <= 31:
                raise ValueError("MONTHLY rules need day_of_month in 1..31")
        rule = RecurringExpense(
            amount_inr=money,
            category_id=category_id,
            frequency=frequency,
            day_of_month=day_of_month,
            description=description,
            active=True,
            last_generated=start_from or dt.date.today(),
        )
        self.session.add(rule)
        self.session.commit()
        self.session.refresh(rule)
        return rule

    def list_rules(self, include_inactive: bool = False) -> list[RecurringExpense]:
        """List recurring rules (active only by default)."""
        statement = select(RecurringExpense)
        if not include_inactive:
            statement = statement.where(RecurringExpense.active == True)  # noqa: E712
        return list(self.session.exec(statement).all())

    def deactivate(self, rule_id: int) -> bool:
        """Deactivate a rule; ``True`` if it existed."""
        rule = self.session.get(RecurringExpense, rule_id)
        if rule is None:
            return False
        rule.active = False
        self.session.add(rule)
        self.session.commit()
        return True

    def generate_due_instances(self, as_of: dt.date | None = None) -> list[Expense]:
        """Materialise expenses due up to ``as_of`` for every active rule.

        Idempotent: each rule's ``last_generated`` watermark advances with the
        created rows in one commit, so repeat calls create nothing.

        Returns:
            The newly created :class:`Expense` rows.
        """
        as_of = as_of or dt.date.today()
        created: list[Expense] = []
        for rule in self.list_rules():
            due_dates = self._due_dates(rule, as_of)
            for due in due_dates:
                expense = Expense(
                    date=due,
                    amount_inr=rule.amount_inr,
                    category_id=rule.category_id,
                    description=rule.description,
                    tags=["recurring"],
                )
                self.session.add(expense)
                created.append(expense)
            if due_dates or rule.last_generated is None:
                rule.last_generated = as_of
                self.session.add(rule)
        self.session.commit()
        if created:
            logger.info("Generated %d recurring expense(s) up to %s", len(created), as_of)
        return created

    @staticmethod
    def _due_dates(rule: RecurringExpense, as_of: dt.date) -> list[dt.date]:
        anchor = rule.last_generated or as_of
        if as_of <= anchor:
            return []
        dates: list[dt.date] = []
        if rule.frequency == RecurrenceFrequency.DAILY:
            day = anchor + dt.timedelta(days=1)
            while day <= as_of:
                dates.append(day)
                day += dt.timedelta(days=1)
        elif rule.frequency == RecurrenceFrequency.WEEKLY:
            day = anchor + dt.timedelta(days=7)
            while day <= as_of:
                dates.append(day)
                day += dt.timedelta(days=7)
        else:  # MONTHLY
            year, month = anchor.year, anchor.month
            while True:
                month += 1
                if month > 12:
                    month, year = 1, year + 1
                due = _clamped_day(year, month, rule.day_of_month or 1)
                if due > as_of:
                    break
                if due > anchor:
                    dates.append(due)
            # Also catch a due day later in the anchor's own month.
            first = _clamped_day(anchor.year, anchor.month, rule.day_of_month or 1)
            if anchor < first <= as_of:
                dates.insert(0, first)
        return dates
