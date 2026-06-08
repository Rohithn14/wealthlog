"""wealthlog terminal UI (Textual).

Exposed as the ``wealthlog-tui`` console script. Milestone 0 ships a placeholder
entry point; the full Textual app (dashboard, expense/portfolio screens) lands in
Milestone 4.
"""

from __future__ import annotations

from wealthlog import __version__
from wealthlog.logging_conf import get_logger

logger = get_logger(__name__)


def main() -> None:
    """Launch the wealthlog TUI.

    Milestone 0 placeholder: prints a notice. Replaced by the Textual ``App`` runner
    in Milestone 4.
    """
    logger.info("wealthlog TUI %s starting (placeholder)", __version__)
    print(f"wealthlog TUI v{__version__} — coming in Milestone 4.")


if __name__ == "__main__":  # pragma: no cover
    main()
