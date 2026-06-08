"""wealthlog web/desktop UI entry point (NiceGUI).

Exposed as the ``wealthlog`` console script. Milestone 0 ships a placeholder; the
dashboard, charts, and entry forms are built in Milestone 5. NiceGUI serves on
localhost and can also run in a native desktop window via ``native=True``.
"""

from __future__ import annotations

from wealthlog import __version__
from wealthlog.logging_conf import get_logger

logger = get_logger(__name__)


def main() -> None:
    """Launch the wealthlog web/desktop UI.

    Milestone 0 placeholder: prints a notice. Replaced by the NiceGUI ``ui.run``
    bootstrap in Milestone 5.
    """
    logger.info("wealthlog web UI %s starting (placeholder)", __version__)
    print(f"wealthlog web/desktop UI v{__version__} — coming in Milestone 5.")


if __name__ == "__main__":  # pragma: no cover
    main()
