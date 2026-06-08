"""CLI database bootstrap helpers (re-exported from :mod:`wealthlog.bootstrap`)."""

from __future__ import annotations

from wealthlog.bootstrap import ensure_db, session_scope

__all__ = ["ensure_db", "session_scope"]
