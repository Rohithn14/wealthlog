"""SIP schedule tracking: expected instalments vs recorded SIP transactions."""

from __future__ import annotations

import calendar
import datetime as dt
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.constants import TransactionType
from wealthlog.db.models import Investment, SIPSchedule, Transaction
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_money
from wealthlog.services.results import PendingSIP

logger = get_logger(__name__)


def _clamped_day(year: int, month: int, day: int) -> dt.date:
    return dt.date(year, month, min(day, calendar.monthrange(year, month)[1]))


class SIPService:
    """Manage SIP schedules and report instalments that are due but unrecorded.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_schedule(
        self,
        investment_id: int,
        amount: Decimal | int | str,
        day_of_month: int,
        start_date: dt.date,
        end_date: dt.date | None = None,
    ) -> SIPSchedule:
        """Create a monthly SIP schedule for an investment.

        Raises:
            ValueError: If the investment is unknown, the amount is not positive,
                the day is out of range, or ``end_date`` precedes ``start_date``.
        """
        if self.session.get(Investment, investment_id) is None:
            raise ValueError(f"Investment {investment_id} does not exist")
        money = to_money(amount)
        if money <= 0:
            raise ValueError("SIP amount must be positive")
        if not 1 <= day_of_month <= 31:
            raise ValueError("day_of_month must be in 1..31")
        if end_date is not None and end_date < start_date:
            raise ValueError("end_date cannot precede start_date")
        schedule = SIPSchedule(
            investment_id=investment_id,
            amount_inr=money,
            day_of_month=day_of_month,
            start_date=start_date,
            end_date=end_date,
            active=True,
        )
        self.session.add(schedule)
        self.session.commit()
        self.session.refresh(schedule)
        return schedule

    def list_schedules(self, include_inactive: bool = False) -> list[SIPSchedule]:
        """List SIP schedules (active only by default)."""
        statement = select(SIPSchedule)
        if not include_inactive:
            statement = statement.where(SIPSchedule.active == True)  # noqa: E712
        return list(self.session.exec(statement).all())

    def deactivate(self, schedule_id: int) -> bool:
        """Deactivate a schedule; ``True`` if it existed."""
        schedule = self.session.get(SIPSchedule, schedule_id)
        if schedule is None:
            return False
        schedule.active = False
        self.session.add(schedule)
        self.session.commit()
        return True

    def get_pending_sips(self, as_of: dt.date | None = None) -> list[PendingSIP]:
        """Return instalments due on/before ``as_of`` with no SIP transaction.

        A due date is considered satisfied when the investment has any SIP
        transaction in that calendar month (exact-date matching would flag manual
        entries recorded a day late).

        Returns:
            Pending instalments, oldest first.
        """
        as_of = as_of or dt.date.today()
        pending: list[PendingSIP] = []
        for schedule in self.list_schedules():
            inv = self.session.get(Investment, schedule.investment_id)
            if inv is None:
                continue
            recorded_months = {
                (t.date.year, t.date.month)
                for t in self.session.exec(
                    select(Transaction).where(
                        Transaction.investment_id == schedule.investment_id,
                        Transaction.type == TransactionType.SIP,
                    )
                ).all()
            }
            for due in self._due_dates(schedule, as_of):
                if (due.year, due.month) not in recorded_months:
                    pending.append(
                        PendingSIP(
                            schedule_id=schedule.id,
                            investment_id=schedule.investment_id,
                            symbol=inv.symbol,
                            due_date=due,
                            amount_inr=schedule.amount_inr,
                        )
                    )
        pending.sort(key=lambda p: p.due_date)
        return pending

    @staticmethod
    def _due_dates(schedule: SIPSchedule, as_of: dt.date) -> list[dt.date]:
        horizon = min(as_of, schedule.end_date) if schedule.end_date else as_of
        dates: list[dt.date] = []
        year, month = schedule.start_date.year, schedule.start_date.month
        while (year, month) <= (horizon.year, horizon.month):
            due = _clamped_day(year, month, schedule.day_of_month)
            if schedule.start_date <= due <= horizon:
                dates.append(due)
            month += 1
            if month > 12:
                month, year = 1, year + 1
        return dates
