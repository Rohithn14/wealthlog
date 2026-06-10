"""Shared runtime bootstrap: ensure the schema/seed exist and hand out sessions.

Used by every interface (CLI, TUI, web) so first-run behaviour is identical. For a
local single-user app this ``create_all`` bootstrap matches the Alembic head; Alembic
remains the path for evolving the schema across releases.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from wealthlog.db.models import Category
from wealthlog.db.seed import seed_categories
from wealthlog.db.session import create_db_and_tables, get_engine

#: The engine that has already been bootstrapped. Keyed on the engine object itself
#: (not the URL) so a ``reset_engine()`` — which builds a new engine for the same
#: in-memory URL in tests — correctly forces a re-bootstrap.
_bootstrapped_engine: Engine | None = None


def ensure_db(force: bool = False) -> None:
    """Create tables and seed default categories if absent (idempotent, once per engine).

    Without the sentinel this ran ``create_all`` + a categories ``SELECT`` on *every*
    ``session_scope()`` — i.e. on every UI interaction. ``force`` re-runs it regardless.
    """
    global _bootstrapped_engine
    engine = get_engine()
    if not force and _bootstrapped_engine is engine:
        return
    create_db_and_tables(engine)
    with Session(engine) as session:
        if session.exec(select(Category)).first() is None:
            try:
                seed_categories(session)
            except IntegrityError:
                # Another process seeded concurrently; the unique constraint caught it.
                session.rollback()
    _bootstrapped_engine = engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session against the bootstrapped database."""
    ensure_db()
    with Session(get_engine()) as session:
        yield session
