"""Centralised logging configuration.

Provides a single :func:`configure_logging` entry point and a :func:`get_logger`
helper so every module logs through a consistent, structured format. Exceptions are
never silently swallowed in this codebase — they are logged here or surfaced upward.
"""

from __future__ import annotations

import logging
import os

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_configured = False


def configure_logging(level: int | str | None = None) -> None:
    """Configure root logging once for the process.

    Args:
        level: Logging level (int or name). Defaults to the ``WEALTHLOG_LOG_LEVEL``
            environment variable, or ``WARNING`` if unset (keeps the CLI quiet; set
            ``WEALTHLOG_LOG_LEVEL=INFO`` for verbose output). Idempotent — repeated
            calls after the first are no-ops unless a new explicit level is passed.
    """
    global _configured
    resolved = level if level is not None else os.environ.get("WEALTHLOG_LOG_LEVEL", "WARNING")
    if _configured and level is None:
        return
    logging.basicConfig(level=resolved, format=_LOG_FORMAT, datefmt=_DATE_FORMAT)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger, ensuring logging is configured.

    Args:
        name: Logger name, conventionally ``__name__`` of the calling module.

    Returns:
        A configured :class:`logging.Logger`.
    """
    configure_logging()
    return logging.getLogger(name)
