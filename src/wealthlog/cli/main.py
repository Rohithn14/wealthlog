"""wealthlog command-line interface (Typer).

Scriptable entry point exposed as the ``wealthlog-cli`` console script. Command groups:
``expense``, ``category``, ``budget``, ``invest``, and ``networth`` — together giving
full feature parity with the service layer.
"""

from __future__ import annotations

import typer

from wealthlog import __version__
from wealthlog.cli.commands import (
    budget,
    category,
    expense,
    export,
    imports,
    income,
    invest,
    networth,
)

app = typer.Typer(
    name="wealthlog",
    help="Local-first personal finance & investment tracker (INR-first).",
    no_args_is_help=True,
    add_completion=True,
)

app.add_typer(expense.app, name="expense")
app.add_typer(income.app, name="income")
app.add_typer(category.app, name="category")
app.add_typer(budget.app, name="budget")
app.add_typer(invest.app, name="invest")
app.add_typer(networth.app, name="networth")
app.add_typer(export.app, name="export")
app.add_typer(imports.app, name="import")


@app.callback()
def _main() -> None:
    """wealthlog — local-first personal finance & investment tracker."""


@app.command()
def version() -> None:
    """Print the installed wealthlog version."""
    typer.echo(__version__)


if __name__ == "__main__":  # pragma: no cover
    app()
