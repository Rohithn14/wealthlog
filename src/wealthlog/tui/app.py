"""wealthlog terminal UI (Textual).

Exposed as the ``wealthlog-tui`` console script. Presents a tabbed dashboard
(net worth + holdings), recent expenses, and budget status, all read through the same
service layer as the CLI and web UI. Press ``r`` to refresh, ``q`` to quit.
"""

from __future__ import annotations

from decimal import Decimal

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

from wealthlog.api.dashboard import build_dashboard_data
from wealthlog.bootstrap import session_scope
from wealthlog.logging_conf import get_logger
from wealthlog.services.expense import ExpenseService

logger = get_logger(__name__)


def _fmt_inr(amount: Decimal | None) -> str:
    return "-" if amount is None else f"Rs {amount:,.2f}"


class WealthlogApp(App):
    """The wealthlog Textual application."""

    TITLE = "wealthlog"
    SUB_TITLE = "personal finance & investments"

    #: Last-rendered summary line (exposed for testing).
    summary_text: str = ""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    CSS = """
    #summary { padding: 1; height: auto; }
    DataTable { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="dashboard"):
            with TabPane("Dashboard", id="dashboard"):
                yield Vertical(
                    Static(id="summary"),
                    DataTable(id="holdings"),
                )
            with TabPane("Expenses", id="expenses"):
                yield DataTable(id="expenses_table")
            with TabPane("Budgets", id="budgets"):
                yield DataTable(id="budgets_table")
        yield Footer()

    def on_mount(self) -> None:
        """Initialise table columns and load data."""
        self.query_one("#holdings", DataTable).add_columns(
            "Symbol", "Type", "Units", "Invested", "Value", "P&L", "Price"
        )
        self.query_one("#expenses_table", DataTable).add_columns(
            "Date", "Amount", "Category", "Description"
        )
        self.query_one("#budgets_table", DataTable).add_columns(
            "Category", "Limit", "Spent", "Remaining", "Used", "Status"
        )
        self.refresh_data()

    def action_refresh(self) -> None:
        """Reload all data from the database."""
        self.refresh_data()
        self.notify("Refreshed")

    def refresh_data(self) -> None:
        """Populate summary and tables from the service layer."""
        with session_scope() as session:
            data = build_dashboard_data(session)
            expense_rows = [
                (
                    str(e.date),
                    _fmt_inr(e.amount_inr),
                    self._category_name(session, e.category_id),
                    e.description or "-",
                )
                for e in ExpenseService(session).list_expenses()[:25]
            ]

        xirr = (
            f"{data.portfolio_xirr * Decimal(100):+.2f}%"
            if data.portfolio_xirr is not None
            else "-"
        )
        self.summary_text = (
            f"[b]Net worth:[/b] {_fmt_inr(data.net_worth.net_worth_inr)}    "
            f"[b]Invested:[/b] {_fmt_inr(data.pnl.invested_inr)}    "
            f"[b]P&L:[/b] {_fmt_inr(data.pnl.pnl_abs_inr)}    "
            f"[b]XIRR:[/b] {xirr}    "
            f"[b]Spent ({data.as_of:%b}):[/b] {_fmt_inr(data.month_total_inr)}"
        )
        self.query_one("#summary", Static).update(self.summary_text)

        holdings = self.query_one("#holdings", DataTable)
        holdings.clear()
        for h in data.holdings:
            price = _fmt_inr(h.current_price_inr) + (" (stale)" if h.price_is_stale else "")
            holdings.add_row(
                h.symbol, h.asset_type.value, f"{h.units:g}",
                _fmt_inr(h.invested_inr), _fmt_inr(h.market_value_inr),
                _fmt_inr(h.pnl_abs_inr), price,
            )

        expenses = self.query_one("#expenses_table", DataTable)
        expenses.clear()
        for row in expense_rows:
            expenses.add_row(*row)

        budgets = self.query_one("#budgets_table", DataTable)
        budgets.clear()
        for s in data.budget_statuses:
            status = "OVER" if s.is_over else "ok"
            budgets.add_row(
                s.category_name, _fmt_inr(s.limit_inr), _fmt_inr(s.spent_inr),
                _fmt_inr(s.remaining_inr), f"{s.pct_used:.0f}%", status,
            )

    @staticmethod
    def _category_name(session, category_id: int | None) -> str:
        if category_id is None:
            return "-"
        from wealthlog.db.models import Category

        cat = session.get(Category, category_id)
        return cat.name if cat else "-"


def main() -> None:
    """Launch the wealthlog TUI."""
    logger.info("Starting wealthlog TUI")
    WealthlogApp().run()


if __name__ == "__main__":  # pragma: no cover
    main()
