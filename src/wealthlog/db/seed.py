"""Seed data: default expense categories.

Idempotent — running it repeatedly will not create duplicates (categories are unique
on name+type).
"""

from __future__ import annotations

from sqlmodel import Session, select

from wealthlog.constants import CategoryType
from wealthlog.db.models import Category
from wealthlog.logging_conf import get_logger

logger = get_logger(__name__)

#: (name, color, icon) tuples for default expense categories.
DEFAULT_EXPENSE_CATEGORIES: list[tuple[str, str, str]] = [
    ("Food & Dining", "#E57373", "utensils"),
    ("Groceries", "#81C784", "cart"),
    ("Transport", "#64B5F6", "car"),
    ("Housing & Rent", "#A1887F", "home"),
    ("Utilities", "#FFD54F", "bolt"),
    ("Health", "#4DB6AC", "heart"),
    ("Entertainment", "#BA68C8", "film"),
    ("Shopping", "#F06292", "bag"),
    ("Education", "#7986CB", "book"),
    ("Travel", "#4FC3F7", "plane"),
    ("Investments", "#AED581", "chart"),
    ("Miscellaneous", "#90A4AE", "ellipsis"),
]

DEFAULT_INCOME_CATEGORIES: list[tuple[str, str, str]] = [
    ("Salary", "#66BB6A", "wallet"),
    ("Dividends", "#26A69A", "coins"),
    ("Interest", "#9CCC65", "percent"),
    ("Other Income", "#78909C", "plus"),
]


def seed_categories(session: Session) -> int:
    """Insert default categories if they do not already exist.

    Args:
        session: An open database session (the caller commits).

    Returns:
        The number of categories newly created.
    """
    created = 0
    rows = [
        (name, CategoryType.EXPENSE, color, icon)
        for name, color, icon in DEFAULT_EXPENSE_CATEGORIES
    ] + [
        (name, CategoryType.INCOME, color, icon)
        for name, color, icon in DEFAULT_INCOME_CATEGORIES
    ]
    for name, ctype, color, icon in rows:
        existing = session.exec(
            select(Category).where(Category.name == name, Category.type == ctype)
        ).first()
        if existing is None:
            session.add(Category(name=name, type=ctype, color=color, icon=icon))
            created += 1
    session.commit()
    logger.info("Seeded %d new categories", created)
    return created
