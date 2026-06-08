"""Database engine and session management.

Provides a process-wide engine bound to the configured database URL, helpers to
create the schema (used in tests and first-run bootstrap), and a context-managed
session. An in-memory SQLite URL (``sqlite://``) is given a shared static pool so
the schema and data persist across sessions within a single process/test.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from wealthlog.config import get_database_url
from wealthlog.logging_conf import get_logger

logger = get_logger(__name__)

_engine: Engine | None = None
_engine_url: str | None = None

# Import models so SQLModel.metadata is fully populated before create_all.
from wealthlog.db import models as _models  # noqa: E402,F401


def _build_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    kwargs: dict = {"connect_args": connect_args}
    if url in ("sqlite://", "sqlite:///:memory:"):
        # Keep one shared in-memory database for the whole process.
        kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, creating it on first use.

    The engine is rebuilt if the configured database URL changes (e.g. tests that
    set ``WEALTHLOG_DB_URL``).

    Returns:
        The active :class:`sqlalchemy.Engine`.
    """
    global _engine, _engine_url
    url = get_database_url()
    if _engine is None or _engine_url != url:
        logger.debug("Creating database engine for %s", url)
        _engine = _build_engine(url)
        _engine_url = url
    return _engine


def reset_engine() -> None:
    """Dispose and forget the current engine (primarily for test isolation)."""
    global _engine, _engine_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_url = None


def create_db_and_tables(engine: Engine | None = None) -> None:
    """Create all tables defined on the SQLModel metadata.

    Args:
        engine: Optional engine to target; defaults to :func:`get_engine`.
    """
    target = engine or get_engine()
    SQLModel.metadata.create_all(target)
    logger.debug("Ensured database schema exists")


@contextmanager
def get_session(engine: Engine | None = None) -> Iterator[Session]:
    """Yield a database session as a context manager.

    Args:
        engine: Optional engine to bind; defaults to :func:`get_engine`.

    Yields:
        An open :class:`sqlmodel.Session`. Commits are the caller's responsibility;
        the session is always closed on exit.
    """
    target = engine or get_engine()
    session = Session(target)
    try:
        yield session
    finally:
        session.close()
