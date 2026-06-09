# Desktop app & sidecar (Milestone C1)

The desktop strategy is a **Tauri v2 shell + Python sidecar**: a small FastAPI
process exposes the existing service layer as JSON, and the frontend talks to it
over localhost. This keeps the tested service layer untouched and gives a single
backend that a future mobile/web client can reuse.

## What is implemented

- **`wealthlog.sidecar`** — the FastAPI app (`create_app()`), the IPC contract
  below, and the `wealthlog-sidecar` console script. Fully covered by
  `tests/test_sidecar.py` (FastAPI `TestClient`).

## IPC contract

All money is serialised as **strings** (Decimal-safe); dates are ISO `YYYY-MM-DD`.

| Method & path | Body / params | Returns |
|---|---|---|
| `GET /health` | — | `{status}` |
| `GET /dashboard` | — | net worth, asset-class split, holdings count |
| `GET /holdings` | — | list of holdings with P&L |
| `GET /networth/history` | `start, end, mode=cost\|market` | month-end series |
| `POST /transactions` | `{symbol,date,type,units,price,fx_rate?,amount_inr?}` | `{id,amount_inr}` |
| `POST /expenses` | `{date,amount,category?,description?}` | `{id,amount_inr}` |
| `POST /refresh-prices` | — | `{job_id}` (202; runs in a worker thread) |
| `GET /jobs/{job_id}` | — | `{status: running\|done\|error, result}` |

Validation errors surface as HTTP 400 (e.g. oversell, non-INR without FX);
unknown symbols/categories as 404. Price refresh is async: the handler offloads
the blocking yfinance/mfapi/FX work via `asyncio.to_thread` and the client polls
`/jobs/{id}` — the same pattern PLAN 2b prescribes for the NiceGUI refresh.

Run locally: `wealthlog-sidecar` (binds `127.0.0.1`).

## Deferred (frontend) — C1 phases 2–4

The remaining work is pure frontend and packaging, which can't be built or
tested in this Python repo and is tracked here rather than committed half-done:

1. **Tauri shell + read-only dashboard** (React + Recharts): donut allocation,
   net-worth area chart from A3 snapshots, holdings table. Spawn the sidecar via
   Tauri's sidecar API on a random localhost port; pass the port to the webview.
2. **Write flows**: transaction/expense forms posting to the sidecar; the async
   refresh job with a progress toast.
3. **Packaging**: Linux AppImage (WSL caveats), Windows MSI.

NiceGUI (`wealthlog.api.server`) stays the GUI during the transition and is
removed once Tauri reaches parity.

## C2 — Rich TUI enhancements (deferred)

Backend hooks already exist; the remaining work is Textual-widget wiring:
inline expense entry on the Expenses tab, an `F5` `@work(thread=True)` price
refresh with a `LoadingIndicator`, a horizontal-bar allocation view, and
splitting Holdings into its own tab. These are best done against a running
terminal and are out of scope for headless CI.
