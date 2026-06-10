"""Liability tracking (Task 2b).

Liabilities (loans, credit-card balances, …) offset gross assets when computing net
worth. Amounts are exact INR Decimals like every other monetary value.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlmodel import Session, select

from wealthlog.constants import LiabilityCategory
from wealthlog.db.models import Liability
from wealthlog.logging_conf import get_logger
from wealthlog.money import to_money
from wealthlog.services.results import LiabilityRow

logger = get_logger(__name__)

_ZERO = Decimal("0.00")


class LiabilityService:
    """Manage liabilities and report their total.

    Args:
        session: An open database session.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_liability(
        self,
        name: str,
        amount_inr: Decimal | int | str,
        category: LiabilityCategory = LiabilityCategory.OTHER,
        due_date: dt.date | None = None,
        notes: str | None = None,
    ) -> Liability:
        """Create and persist a liability."""
        row = Liability(
            name=name,
            amount_inr=to_money(amount_inr),
            category=category,
            due_date=due_date,
            notes=notes,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        logger.info("Added liability %s: %s", name, row.amount_inr)
        return row

    def list_liabilities(self) -> list[LiabilityRow]:
        """Return all liabilities, largest first."""
        rows = self.session.exec(select(Liability)).all()
        rows.sort(key=lambda r: r.amount_inr, reverse=True)
        return [
            LiabilityRow(
                id=r.id,
                name=r.name,
                amount_inr=r.amount_inr,
                category=r.category,
                due_date=r.due_date,
                notes=r.notes,
            )
            for r in rows
        ]

    def update_amount(self, liability_id: int, amount_inr: Decimal | int | str) -> bool:
        """Update a liability's outstanding amount; ``True`` if it existed."""
        row = self.session.get(Liability, liability_id)
        if row is None:
            return False
        row.amount_inr = to_money(amount_inr)
        self.session.add(row)
        self.session.commit()
        return True

    def delete_liability(self, liability_id: int) -> bool:
        """Delete a liability; ``True`` if it existed."""
        row = self.session.get(Liability, liability_id)
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    def total_liabilities(self) -> Decimal:
        """Sum of all outstanding liability amounts (INR)."""
        rows = self.session.exec(select(Liability)).all()
        return to_money(sum((r.amount_inr for r in rows), _ZERO))
