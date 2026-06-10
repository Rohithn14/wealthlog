"""Bug #2: ensure_db() bootstraps once per engine, not on every session_scope()."""

from __future__ import annotations

import pytest

import wealthlog.bootstrap as bootstrap
from wealthlog.db.session import reset_engine


@pytest.fixture
def count_create(monkeypatch):
    """Count create_all invocations while still creating the schema for real."""
    real = bootstrap.create_db_and_tables
    calls = {"n": 0}

    def counting(engine=None):
        calls["n"] += 1
        return real(engine)

    monkeypatch.setattr(bootstrap, "create_db_and_tables", counting)
    bootstrap._bootstrapped_engine = None
    return calls


def test_ensure_db_is_idempotent_per_engine(count_create):
    bootstrap.ensure_db()
    bootstrap.ensure_db()
    bootstrap.ensure_db()
    assert count_create["n"] == 1  # only the first call hit create_all


def test_reset_engine_forces_rebootstrap(count_create):
    bootstrap.ensure_db()
    reset_engine()  # new engine object for the same in-memory URL
    bootstrap.ensure_db()
    assert count_create["n"] == 2
