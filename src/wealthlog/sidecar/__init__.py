"""FastAPI sidecar exposing the service layer as JSON (Milestone C1).

This is the IPC contract for the planned Tauri desktop frontend (and any future
mobile/web client). All monetary values are serialised as strings to preserve
Decimal precision; dates are ISO ``YYYY-MM-DD``. The sidecar is intentionally
stateless per request — each handler opens its own ``session_scope``.
"""

from wealthlog.sidecar.app import create_app

__all__ = ["create_app"]
