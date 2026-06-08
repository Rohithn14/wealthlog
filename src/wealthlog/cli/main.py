"""wealthlog command-line interface (Typer).

This is the scriptable entry point exposed as the ``wealthlog-cli`` console script.
Milestone 0 ships the app skeleton and a ``version`` command; feature command groups
(expense, invest, budget, networth, export) are added in Milestone 3.
"""

from __future__ import annotations

import typer

from wealthlog import __version__

app = typer.Typer(
    name="wealthlog",
    help="Local-first personal finance & investment tracker (INR-first).",
    no_args_is_help=True,
    add_completion=True,
)


@app.callback()
def _main() -> None:
    """wealthlog — local-first personal finance & investment tracker."""


@app.command()
def version() -> None:
    """Print the installed wealthlog version."""
    typer.echo(__version__)


if __name__ == "__main__":  # pragma: no cover
    app()
