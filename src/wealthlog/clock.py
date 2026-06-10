"""Time helpers.

Cache timestamps are stored and compared as **naive UTC** so a local timezone or
WSL clock change can't mis-age the price/FX cache. SQLite/SQLAlchemy reads datetimes
back without tzinfo, so storing naive UTC (rather than aware) keeps writes and reads
on the same convention.
"""

from __future__ import annotations

import datetime as dt


def utcnow() -> dt.datetime:
    """Current UTC time as a naive ``datetime`` (tzinfo stripped)."""
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)
