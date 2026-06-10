"""End-to-end tests for the NiceGUI web UI (``wealthlog.api.server``).

These drive the actual page through NiceGUI's headless ``User`` simulation, so
they exercise the build-time render of every tab/sub-tab plus the click
handlers — the glue layer that unit tests of the services never touch.

Regression coverage for the web-UI bugs fixed on ``feat/web-ui-full-parity``:

* **WUI-1** — the "Refresh prices" button scheduled its async handler with
  ``asyncio.ensure_future(...)``, detaching it from the client's slot stack;
  the first ``ui.notification(...)`` then raised
  ``RuntimeError: The current slot cannot be determined``. The fix passes the
  coroutine function directly so NiceGUI runs it inside the client context.
* **WUI-2** — the Net-Worth → History panel rendered its refreshable at build
  time with an empty start-date input, firing a spurious "Invalid date format"
  error notification on every page load. The fix prompts for a date instead.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Callable
from typing import Any

import pytest
from nicegui.testing import User

from wealthlog.bootstrap import session_scope
from wealthlog.constants import AssetType, LiabilityCategory, TransactionType
from wealthlog.services.expense import ExpenseService
from wealthlog.services.fetcher import FetcherService, RefreshResult
from wealthlog.services.liability import LiabilityService
from wealthlog.services.portfolio import PortfolioService

MAIN_FILE = "src/wealthlog/api/server.py"

# Apply the page-module marker to every test in this module.
pytestmark = pytest.mark.nicegui_main_file(MAIN_FILE)

TOP_LEVEL_TABS = [
    "Expenses", "Income", "Budget", "Investments", "Net Worth",
    "Liabilities", "Import/Export", "Alerts", "Categories",
]

# Unique action-button labels reachable from a freshly-opened page.
ACTION_BUTTONS = [
    "Add category", "Add liability", "Add expense", "Add income", "Set budget",
    "Add investment", "Add FD", "Set price", "Generate", "Run report", "Compare",
    "Show history", "Analyse", "Check alerts now", "Calculate", "Search",
    "Show", "Create rule", "Reload",
]


def _seed() -> None:
    """Populate the shared in-memory DB with a holding, a dividend and an expense."""
    with session_scope() as session:
        portfolio = PortfolioService(session)
        inv = portfolio.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
        portfolio.add_transaction(
            inv.id, dt.date(2024, 1, 1), TransactionType.BUY, "10", "1000"
        )
        portfolio.add_transaction(
            inv.id, dt.date(2024, 6, 1), TransactionType.DIVIDEND, "0", "0",
            amount_inr="500",
        )
        FetcherService(session).set_manual_price(inv.id, "1500")
        ExpenseService(session).add_expense(dt.date.today(), "250", description="Lunch")
        LiabilityService(session).add_liability(
            "Car loan", "50000", category=LiabilityCategory.LOAN
        )


def _patch_refresh(monkeypatch: pytest.MonkeyPatch, result: RefreshResult) -> None:
    """Stub the price refresh so it is offline and resolves on the test's loop.

    The real handler offloads via ``asyncio.to_thread``; running the worker
    inline keeps the in-client-context notification path (the WUI-1 surface)
    while removing the network call and cross-thread completion timing.
    """
    monkeypatch.setattr("wealthlog.api.server._do_refresh", lambda: result)

    async def _inline_to_thread(fn: Callable[..., Any], *args: Any, **kw: Any) -> Any:
        return fn(*args, **kw)

    monkeypatch.setattr("wealthlog.api.server.asyncio.to_thread", _inline_to_thread)


async def test_all_tabs_render(user: User) -> None:
    """Opening the page builds every tab and sub-panel without raising."""
    await user.open("/")
    for tab in TOP_LEVEL_TABS:
        user.find(tab).click()


async def test_no_spurious_notification_on_load(user: User) -> None:
    """WUI-2 regression: a fresh page load produces no error notifications."""
    await user.open("/")
    await asyncio.sleep(0.2)
    assert user.notify.messages == []


async def test_add_category_write_flow(user: User) -> None:
    """A category create through the form persists and notifies success."""
    await user.open("/")
    user.find("Category name").type("Side hustle")
    user.find("Add category").click()
    await user.should_see("Added category", retries=5)

    with session_scope() as session:
        from sqlmodel import select

        from wealthlog.db.models import Category

        names = {c.name for c in session.exec(select(Category)).all()}
    assert "Side hustle" in names


@pytest.mark.parametrize("button", ACTION_BUTTONS)
async def test_action_buttons_do_not_crash(user: User, button: str) -> None:
    """Every action button is clickable with empty/default forms.

    Invalid input must surface as a caught notification, never an uncaught
    exception (the ``User`` teardown fails the test on unretrieved task
    exceptions or ERROR logs).
    """
    await user.open("/")
    user.find(button).click()


async def test_dashboard_and_holdings_with_data(user: User) -> None:
    """Seeded data renders through the dashboard and holdings read paths."""
    _seed()
    await user.open("/")
    await user.should_see("Net worth", retries=5)  # dashboard summary card

    user.find("Investments").click()
    await user.should_see("INFY.NS", retries=5)  # holdings table
    user.find("Reload").click()
    user.find("Calculate").click()  # P&L / XIRR
    user.find("Analyse").click()  # concentration


async def test_networth_and_analysis_reads(user: User) -> None:
    """Net-worth read flow renders with seeded data."""
    _seed()
    await user.open("/")
    user.find("Net Worth").click()
    await user.should_see("Net worth", retries=5)


async def test_refresh_prices_runs_in_client_context(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WUI-1 regression: the async refresh handler runs in the client slot.

    Before the fix this clicked-handler ran detached via ``ensure_future`` and
    crashed at ``ui.notification(...)`` with an empty slot stack — caught by the
    ``User`` teardown as an unretrieved task exception. We stub the refresh so it
    is offline, then assert the in-context summary notification is shown.
    """
    _patch_refresh(monkeypatch, RefreshResult(updated=["INFY.NS"], failed=[]))
    await user.open("/")
    user.find("Investments").click()
    user.find("Refresh prices").click()
    await user.should_see("Refreshed", retries=10)
