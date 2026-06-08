"""Shared pytest fixtures.

The database fixtures point wealthlog at an in-memory SQLite engine so tests never
touch the real data file. They become fully wired in Milestone 1 once the models and
session helpers exist; for now they configure the environment defensively.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch) -> None:
    """Redirect wealthlog's data dir and DB to a throwaway location for every test."""
    monkeypatch.setenv("WEALTHLOG_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WEALTHLOG_DB_URL", "sqlite://")  # shared in-memory
    # Ensure no stray real-path leakage.
    os.environ.pop("WEALTHLOG_LOG_LEVEL", None)
