"""Shared runtime bootstrap: ensure the schema/seed exist and hand out sessions.

Used by every interface (CLI, TUI, web) so first-run behaviour is identical. For a
local single-user app this ``create_all`` bootstrap matches the Alembic head; Alembic
remains the path for evolving the schema across releases.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session, select

from wealthlog.db.models import Category
from wealthlog.db.seed import seed_categories
from wealthlog.db.session import create_db_and_tables, get_engine


def ensure_db() -> None:
    """Create tables and seed default categories if absent (idempotent)."""
    engine = get_engine()
    create_db_and_tables(engine)
    with Session(engine) as session:
        if session.exec(select(Category)).first() is None:
            seed_categories(session)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session against the bootstrapped database."""
    ensure_db()
    with Session(get_engine()) as session:
        yield session
