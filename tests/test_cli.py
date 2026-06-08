"""Integration tests for the Typer CLI (in-memory DB via the autouse fixture)."""

from __future__ import annotations

from typer.testing import CliRunner

from wealthlog.cli.main import app

runner = CliRunner()


def run(*args: str):
    return runner.invoke(app, list(args))


class TestExpenseCommands:
    def test_add_and_summary(self):
        assert run("expense", "add", "250.50", "-d", "2026-06-05").exit_code == 0
        res = run("expense", "summary", "2026", "6")
        assert res.exit_code == 0
        assert "250.50" in res.output

    def test_add_with_category(self):
        res = run("expense", "add", "100", "-c", "Food & Dining", "-d", "2026-06-01")
        assert res.exit_code == 0

    def test_add_unknown_category_fails(self):
        res = run("expense", "add", "100", "-c", "Nonexistent")
        assert res.exit_code == 1
        assert "Unknown category" in res.output

    def test_list(self):
        run("expense", "add", "100", "-d", "2026-06-01", "--tags", "a,b")
        res = run("expense", "list")
        assert res.exit_code == 0
        assert "100" in res.output

    def test_list_filter_by_tag(self):
        run("expense", "add", "100", "-d", "2026-06-01", "--tags", "groceries")
        run("expense", "add", "200", "-d", "2026-06-02", "--tags", "fuel")
        res = run("expense", "list", "--tags", "groceries")
        assert "100" in res.output

    def test_delete(self):
        run("expense", "add", "100", "-d", "2026-06-01")
        res = run("expense", "delete", "1")
        assert res.exit_code == 0
        assert "Deleted" in res.output

    def test_delete_missing_fails(self):
        res = run("expense", "delete", "999")
        assert res.exit_code == 1


class TestCategoryCommands:
    def test_list_seeded(self):
        res = run("category", "list")
        assert res.exit_code == 0
        assert "Food & Dining" in res.output

    def test_add(self):
        res = run("category", "add", "Pets", "--type", "expense")
        assert res.exit_code == 0
        assert run("category", "list").output.count("Pets") >= 1

    def test_add_duplicate_fails(self):
        run("category", "add", "Pets")
        res = run("category", "add", "Pets")
        assert res.exit_code == 1


class TestBudgetCommands:
    def test_set_and_status(self):
        assert run("budget", "set", "Food & Dining", "1000", "-y", "2026", "-m", "6").exit_code == 0
        res = run("budget", "status", "2026", "6")
        assert res.exit_code == 0
        assert "1,000" in res.output

    def test_alert_fires_when_over(self):
        run("budget", "set", "Food & Dining", "100", "-y", "2026", "-m", "6")
        run("expense", "add", "500", "-c", "Food & Dining", "-d", "2026-06-10")
        res = run("budget", "alerts", "2026", "6")
        assert res.exit_code == 0
        assert "Food & Dining" in res.output
        assert "⚠" in res.output

    def test_no_alert_when_under(self):
        run("budget", "set", "Food & Dining", "1000", "-y", "2026", "-m", "6")
        run("expense", "add", "50", "-c", "Food & Dining", "-d", "2026-06-10")
        res = run("budget", "alerts", "2026", "6")
        assert "No budgets exceeded" in res.output


class TestInvestCommands:
    def test_add_and_buy_and_holdings(self):
        assert run("invest", "add", "INFY.NS", "Infosys", "-t", "STOCK_IN").exit_code == 0
        assert run("invest", "buy", "INFY.NS", "10", "1500", "-d", "2024-01-01").exit_code == 0
        res = run("invest", "holdings")
        assert res.exit_code == 0
        assert "INFY.NS" in res.output

    def test_invalid_asset_type_fails(self):
        res = run("invest", "add", "X", "X", "-t", "BOGUS")
        assert res.exit_code == 1

    def test_fd_cannot_use_add(self):
        res = run("invest", "add", "X", "X", "-t", "FD")
        assert res.exit_code == 1

    def test_buy_unknown_symbol_fails(self):
        res = run("invest", "buy", "NOPE", "1", "1")
        assert res.exit_code == 1

    def test_us_stock_buy_with_fx(self):
        run("invest", "add", "AAPL", "Apple", "-t", "STOCK_US", "--currency", "USD")
        res = run("invest", "buy", "AAPL", "10", "100", "-d", "2024-01-01", "--fx", "83")
        assert res.exit_code == 0
        assert "83,000" in res.output  # 10*100*83

    def test_sip_and_sell(self):
        run("invest", "add", "120503", "Axis MF", "-t", "MF")
        assert run("invest", "sip", "120503", "100", "50", "-d", "2024-01-01").exit_code == 0
        assert run("invest", "sell", "120503", "20", "55", "-d", "2025-01-01").exit_code == 0

    def test_add_fd_and_networth(self):
        res = run(
            "invest", "add-fd", "SBI FD", "100000", "7.1",
            "--start", "2024-01-01", "--maturity", "2027-01-01",
        )
        assert res.exit_code == 0
        nw = run("networth", "show")
        assert nw.exit_code == 0
        assert "FD" in nw.output

    def test_pnl_and_xirr(self):
        run("invest", "add", "INFY.NS", "Infosys", "-t", "STOCK_IN")
        run("invest", "buy", "INFY.NS", "10", "1500", "-d", "2024-01-01")
        run("invest", "sell", "INFY.NS", "10", "1800", "-d", "2025-01-01")
        assert run("invest", "pnl").exit_code == 0
        xirr = run("invest", "xirr", "-s", "INFY.NS")
        assert xirr.exit_code == 0


class TestNetWorthCommands:
    def test_show_empty(self):
        res = run("networth", "show")
        assert res.exit_code == 0
        assert "Net worth" in res.output

    def test_history(self):
        run("invest", "add", "INFY.NS", "Infosys", "-t", "STOCK_IN")
        run("invest", "buy", "INFY.NS", "10", "1500", "-d", "2026-01-15")
        res = run("networth", "history", "--start", "2026-01-01", "--end", "2026-03-31")
        assert res.exit_code == 0
        assert "2026-01" in res.output


class TestTopLevel:
    def test_version(self):
        res = run("version")
        assert res.exit_code == 0

    def test_help(self):
        assert run("--help").exit_code == 0
