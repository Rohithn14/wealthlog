"""Tests for application configuration and cache-TTL resolution."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from wealthlog.config import (
    CacheTTLConfig,
    get_config,
    get_data_dir,
    get_database_url,
)
from wealthlog.constants import AssetType


class TestDataDir:
    def test_honours_env_override(self, tmp_path, monkeypatch):
        target = tmp_path / "custom"
        monkeypatch.setenv("WEALTHLOG_DATA_DIR", str(target))
        assert get_data_dir() == target
        assert target.is_dir()

    def test_creates_directory(self, tmp_path, monkeypatch):
        target = tmp_path / "nested" / "deep"
        monkeypatch.setenv("WEALTHLOG_DATA_DIR", str(target))
        assert get_data_dir().is_dir()

    def test_returns_path_object(self):
        assert isinstance(get_data_dir(), Path)


class TestDatabaseUrl:
    def test_honours_env_override(self, monkeypatch):
        monkeypatch.setenv("WEALTHLOG_DB_URL", "sqlite://")
        assert get_database_url() == "sqlite://"

    def test_defaults_to_file_in_data_dir(self, tmp_path, monkeypatch):
        monkeypatch.delenv("WEALTHLOG_DB_URL", raising=False)
        monkeypatch.setenv("WEALTHLOG_DATA_DIR", str(tmp_path))
        url = get_database_url()
        assert url.startswith("sqlite:///")
        assert url.endswith("wealthlog.db")


class TestCacheTTL:
    def test_defaults(self):
        ttl = CacheTTLConfig()
        assert ttl.stock_in == timedelta(minutes=15)
        assert ttl.mf_nav == timedelta(hours=12)
        assert ttl.fx_rate == timedelta(hours=6)

    def test_mf_nav_longer_than_equity(self):
        ttl = CacheTTLConfig()
        assert ttl.mf_nav > ttl.stock_in

    def test_for_asset_mapping(self):
        ttl = CacheTTLConfig()
        assert ttl.for_asset(AssetType.STOCK_IN) == ttl.stock_in
        assert ttl.for_asset(AssetType.STOCK_US) == ttl.stock_us
        assert ttl.for_asset(AssetType.GOLD_ETF) == ttl.gold_etf
        assert ttl.for_asset(AssetType.MF) == ttl.mf_nav

    def test_fd_has_zero_ttl(self):
        assert CacheTTLConfig().for_asset(AssetType.FD) == timedelta(0)

    def test_frozen(self):
        ttl = CacheTTLConfig()
        try:
            ttl.stock_in = timedelta(minutes=1)  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            assert isinstance(exc, (AttributeError, Exception))
        else:
            raise AssertionError("CacheTTLConfig should be frozen")


class TestAppConfig:
    def test_builds_from_env(self, monkeypatch):
        monkeypatch.setenv("WEALTHLOG_DB_URL", "sqlite://")
        cfg = get_config()
        assert cfg.database_url == "sqlite://"
        assert cfg.http_timeout_seconds > 0
        assert isinstance(cfg.cache_ttl, CacheTTLConfig)
