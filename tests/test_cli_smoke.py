"""Smoke tests for the CLI skeleton and interface entry points."""

from __future__ import annotations

from typer.testing import CliRunner

from wealthlog import __version__
from wealthlog.cli.main import app

runner = CliRunner()


class TestCliSkeleton:
    def test_help_exits_zero(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "wealthlog" in result.output.lower()

    def test_version_command(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        # no_args_is_help -> exit code 0 or 2 depending on Typer version, output has usage
        assert "Usage" in result.output or "Commands" in result.output


class TestEntryPointsImportable:
    def test_tui_main_importable(self):
        from wealthlog.tui.app import main

        assert callable(main)

    def test_web_main_importable(self):
        from wealthlog.api.server import main

        assert callable(main)

    def test_version_string(self):
        assert __version__ == "0.1.0"
