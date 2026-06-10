"""``wealthlog-alerts`` console script — evaluate alert rules and deliver them.

Designed to run decoupled from any UI: ``--once`` (default) evaluates a single
time, suitable for cron or a systemd timer — the simplest reliable Linux delivery.
Notifications go to the desktop via ``notify-send`` when available, and always to
stdout.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess

from wealthlog.bootstrap import session_scope
from wealthlog.logging_conf import get_logger
from wealthlog.services.alerts import AlertService
from wealthlog.services.results import FiredAlert

logger = get_logger(__name__)


def _deliver(alert: FiredAlert) -> None:
    """Best-effort desktop notification plus stdout."""
    print(f"[ALERT/{alert.kind}] {alert.message}")
    if shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", f"wealthlog: {alert.kind}", alert.message],
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
            logger.debug("notify-send failed: %s", exc)


def run_once() -> int:
    """Evaluate alerts once; return the number fired."""
    with session_scope() as session:
        fired = AlertService(session).evaluate()
    for alert in fired:
        _deliver(alert)
    if not fired:
        print("No alerts.")
    return len(fired)


def main() -> None:  # pragma: no cover - thin CLI wrapper
    parser = argparse.ArgumentParser(description="Evaluate wealthlog portfolio alerts.")
    parser.add_argument(
        "--once", action="store_true", default=True,
        help="Evaluate a single time (default; use cron/systemd-timer for scheduling).",
    )
    parser.parse_args()
    run_once()


if __name__ == "__main__":  # pragma: no cover
    main()
