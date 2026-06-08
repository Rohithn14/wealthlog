"""Shared pytest fixtures.

Every test runs against a throwaway in-memory SQLite database so the real data file
is never touched. The :func:`db_session` fixture builds a fresh schema per test for
full isolation.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlmodel import Session


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch) -> Iterator[None]:
    """Redirect wealthlog's data dir and DB to a throwaway location for every test."""
    monkeypatch.setenv("WEALTHLOG_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WEALTHLOG_DB_URL", "sqlite://")  # shared in-memory (StaticPool)
    monkeypatch.delenv("WEALTHLOG_LOG_LEVEL", raising=False)
    from wealthlog.db.session import reset_engine

    reset_engine()
    yield
    reset_engine()


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Yield a session bound to a freshly-created in-memory schema."""
    from wealthlog.db.session import create_db_and_tables, get_engine

    engine = get_engine()
    create_db_and_tables(engine)
    with Session(engine) as session:
        yield session
