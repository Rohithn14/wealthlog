"""Application configuration: data directory, database location, and cache TTLs.

All paths follow the XDG Base Directory spec via :mod:`platformdirs`. Values can be
overridden with environment variables (useful for tests and CI):

* ``WEALTHLOG_DATA_DIR`` — overrides the data directory.
* ``WEALTHLOG_DB_URL``   — overrides the full SQLAlchemy database URL (e.g. in-memory).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from platformdirs import user_data_dir

from wealthlog.constants import AssetType

APP_NAME: str = "wealthlog"
APP_AUTHOR: str = "wealthlog"

#: Database filename inside the data directory.
DB_FILENAME: str = "wealthlog.db"


def get_data_dir() -> Path:
    """Return the wealthlog data directory, creating it if necessary.

    Honours the ``WEALTHLOG_DATA_DIR`` environment variable; otherwise resolves to
    the XDG data dir (``~/.local/share/wealthlog`` on Linux).

    Returns:
        The absolute path to the data directory.
    """
    override = os.environ.get("WEALTHLOG_DATA_DIR")
    base = Path(override) if override else Path(user_data_dir(APP_NAME, APP_AUTHOR))
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_database_url() -> str:
    """Return the SQLAlchemy database URL for the local store.

    Honours ``WEALTHLOG_DB_URL`` (e.g. ``sqlite://`` for in-memory tests); otherwise
    points at the SQLite file in the data directory.

    Returns:
        A SQLAlchemy-compatible database URL string.
    """
    override = os.environ.get("WEALTHLOG_DB_URL")
    if override:
        return override
    return f"sqlite:///{get_data_dir() / DB_FILENAME}"


@dataclass(frozen=True)
class CacheTTLConfig:
    """Time-to-live windows for cached market data, per asset class.

    Indian/US equities and gold ETFs refresh intraday; mutual-fund NAVs are
    end-of-day published (long TTL); FX is refreshed a few times per day.
    """

    stock_in: timedelta = timedelta(minutes=15)
    stock_us: timedelta = timedelta(minutes=15)
    gold_etf: timedelta = timedelta(minutes=15)
    mf_nav: timedelta = timedelta(hours=12)
    fx_rate: timedelta = timedelta(hours=6)

    def for_asset(self, asset_type: AssetType) -> timedelta:
        """Return the cache TTL for a given asset type.

        Args:
            asset_type: The asset class to look up.

        Returns:
            The configured TTL. Falls back to the equity TTL for unknown types;
            FD has no live price and is treated as non-cacheable (zero TTL).
        """
        mapping = {
            AssetType.STOCK_IN: self.stock_in,
            AssetType.STOCK_US: self.stock_us,
            AssetType.GOLD_ETF: self.gold_etf,
            AssetType.MF: self.mf_nav,
            AssetType.FD: timedelta(0),
        }
        return mapping.get(asset_type, self.stock_in)


@dataclass(frozen=True)
class AppConfig:
    """Top-level runtime configuration."""

    data_dir: Path = field(default_factory=get_data_dir)
    database_url: str = field(default_factory=get_database_url)
    cache_ttl: CacheTTLConfig = field(default_factory=CacheTTLConfig)
    http_timeout_seconds: float = 10.0


def get_config() -> AppConfig:
    """Build an :class:`AppConfig` from the current environment.

    Returns:
        A fresh configuration object (re-reads env vars on each call).
    """
    return AppConfig()
