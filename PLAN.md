# wealthlog — Dev Plan

> **Status (2026-06-10):** Web-UI layer (`api/server.py`, NiceGUI) bug-swept and
> covered — see **Web UI Bug Report** below. WUI-1 (async refresh crash) and WUI-2
> (spurious load-time notification) fixed; `tests/test_web_ui.py` drives the page
> headlessly via NiceGUI's `User` simulation (every tab + the fixed paths), lifting
> `api/server.py` coverage from 10% → ~73%. `wealthlog.api` added to the coverage
> source; `pytest-asyncio` added (dev), `asyncio_mode = "auto"`.
>
> **Status (2026-06-09):** Bugs #4, #5, #7, #9-gap, #10, #11 fixed; Milestone A (A1–A4) implemented — `migrations/versions/32511e50be85_*`, `services/{income,recurring,sip}.py`, market-mode `networth history`.
>
> **Milestone B — DONE.** B1 benchmark (`services/benchmark.py`, `invest benchmark`), B2 FIFO capital-gains tax (`services/tax.py`, `invest tax-report`), B3 broker import (`services/importer.py`, `wealthlog-cli import`), B4 concentration (`services/concentration.py` + `investments.sector` migration `4a58bfdfca0b`), B5 dividends (`services/dividends.py`, `invest dividends`).
>
> **Milestone C — partial.** C3 alerts complete (`services/alerts.py`, tables migration `ac8711fd3f88`, `wealthlog-cli alert`, `wealthlog-alerts` watcher). C1 sidecar/IPC contract complete (`wealthlog.sidecar`, `wealthlog-sidecar`, `docs/DESKTOP.md`); the Tauri/React frontend (C1 phases 2–4) and C2 Textual-widget enhancements remain deferred — they can't be built/tested headless (see `docs/DESKTOP.md`).
>
> **Task-2 polish — DONE (branch `feat/task2-polish`).** All remaining LOW bugs fixed:
> #2 bootstrap once-per-engine + concurrent-seed guard; #6 embedded DejaVu Unicode font
> (renders `₹`); #8 cache pruning (latest 5) + composite indexes (migration `b1c2d3e4f5a6`);
> #12 async NiceGUI price refresh; #13 FD maturity-before-start guard; #14 SQL CHECK
> constraints (migration `c2d3e4f5a6b7`); #15 expense-list unknown-category exit; #16 naive-UTC
> cache clock (`wealthlog.clock`); #17 dropped unused pandas; #18 `to_fx` (already in B-series).
> Task-2 items: 2a pruning+indexes, 2b LiabilityService (`services/liability.py`, migration
> `980cbd7b6e1e`, `wealthlog-cli liability`), 2c CHECK constraints, 2e `--format json|csv` on
> read commands + FD-xirr note. Suite 409 passing, ruff clean, all migrations round-trip.
>
> Only the pure-frontend work remains deferred (can't build/test headless): C1 Tauri/React
> phases 2–4 and C2 Textual-widget enhancements — see `docs/DESKTOP.md`.

## Bug Report (Task 1)

Legend: severity CRITICAL / HIGH / MEDIUM / LOW. "NOT A BUG" entries are areas from the audit brief that checked out fine, kept for the record.

| # | File:Lines | Severity | Root Cause | Minimal Fix |
|---|-----------|----------|------------|-------------|
| 1 | `alembic.ini:91`, `migrations/env.py:22` | NOT A BUG | `env.py` calls `config.set_main_option("sqlalchemy.url", get_database_url())` before any engine is built, so the ini placeholder is never used; `WEALTHLOG_DB_URL` is already honoured via `get_database_url()`. | None required. Optional hygiene: comment out the placeholder line in `alembic.ini` so nobody thinks it matters. Caveat: `alembic` must run from repo root with wealthlog importable (`prepend_sys_path = .`). |
| 2 | `bootstrap.py:29-34` | MEDIUM | `session_scope()` runs `ensure_db()` (= `create_all` + a `SELECT` on categories) on **every** call; TUI `refresh_data` and NiceGUI render/refresh/submit each open sessions repeatedly, so every UI interaction pays ~10 `CREATE TABLE IF NOT EXISTS` + index statements; two processes starting concurrently can both pass the empty-categories check and race on seeding (one dies with `IntegrityError` on `uq_category_name_type`). | Module-level `_bootstrapped: bool` sentinel in `bootstrap.py`, reset by `reset_engine()`; wrap `seed_categories` in `try/except IntegrityError: session.rollback()`. |
| 3 | `services/portfolio.py:236-273` (`_market_holding`) | NOT A BUG (verified) | Avg cost = `bought_amt / bought_units` where `bought_amt` is INR at historical FX; remaining `invested = avg_cost × units`. This is standard blended average-cost accounting — a USD buy at FX 83 followed by a partial SELL does **not** double-count FX (the SELL only reduces units; the blended INR cost per unit is unchanged). | None. Document the average-cost (non-FIFO) method in the docstring; FIFO lots are needed later for tax (B2). |
| 4 | `services/networth.py:78-128` + `cli/commands/networth.py:33-47` | MEDIUM (UX) + MEDIUM (math) | (a) UX: command is `networth history`; users will read it as market-value history, but it is a cost-basis proxy — only the table title hints at this. (b) Math: SELLs subtract full **proceeds** (`-t.amount_inr`), not the cost basis of the sold units, so selling at a profit drives "invested capital" down by more than was invested (can go negative). | (a) Print a one-line disclaimer in the CLI. (b) Subtract `sold_units × avg_cost` instead of proceeds, or rename the series to "net cash deployed" and document that profits withdrawn reduce it. |
| 5 | `services/portfolio.py:318-339` (FD XIRR) | HIGH | For a matured FD, the terminal flow value is clamped to maturity (`calculate_fd_value` caps accrual) but the flow **date** is `as_of` (today). pyxirr then sees the matured value arriving later than it did, diluting the annualised rate — e.g. a 1-yr 7% FD queried 1 year after maturity reports ≈3.5%. | `terminal_date = min(as_of, details.maturity_date)`; append `(terminal_date, value)`. |
| 6 | `exporters/pdf_exporter.py:1-22` | LOW | Core Latin-1 Helvetica can't render ₹ (U+20B9), so amounts say "Rs". fpdf2 ≥ 2.7 fully supports TTF Unicode embedding via `pdf.add_font("DejaVu", fname=...)` + `set_font("DejaVu")` — no system libs needed; subsetting keeps file size small. | Bundle `DejaVuSans.ttf` (or Noto Sans) under `src/wealthlog/exporters/fonts/`, register it in `_ReportPdf.__init__`, change `_rs()` to use `₹`. Keep "Rs" fallback if the font file is missing. ~20 LOC. |
| 7 | `fetchers/yfinance_fetcher.py:23-37, 58-60` | MEDIUM | (a) The `hasattr(info, "get")` guard handles dict-like *and* attribute-only `fast_info`, **but** dict-style `FastInfo` keys are camelCase (`"lastPrice"`), so `info.get("last_price")` returns `None` on older dict-like versions → silently falls through to the slower `history()` path on every fetch. (b) yfinance can return `NaN` closes; `to_price(str(nan))` → `Decimal("NaN")`, and `Decimal("NaN") <= 0` raises `InvalidOperation` **outside** the try block → uncaught crash that `refresh_prices` (which only catches `FetchError`) propagates. | (a) Try `getattr(info, "last_price", None)` first, then `info.get("lastPrice")`. (b) `import math; if price is None or math.isnan(price) or price <= 0: raise FetchError(...)` before Decimal conversion. |
| 8 | `db/models.py:124-138`, `services/fetcher.py:177-193` | MEDIUM | `PriceCache` is append-only — every refresh inserts a row, nothing prunes (grep confirms no DELETE anywhere). Growth is unbounded (~1 row/asset/15 min if refreshed aggressively). Lookups stay tolerable because `ix_prices_cache_investment_id` exists, but the `WHERE investment_id = ? ORDER BY fetched_at DESC LIMIT 1` plan needs a sort step without a composite `(investment_id, fetched_at)` index. | Add pruning (keep latest N per investment) in `_store_price` + composite index (see 2a). |
| 9 | `services/portfolio.py:246-252, 344-348` | NOT A BUG (verified) + LOW gap | DIVIDEND excluded from cost basis but included as XIRR inflow is **correct** money-weighted-return accounting (dividends are real cash returned; they should not change units/cost). XIRR is not inflated — it is the only metric that correctly credits dividends. Gap: a DIVIDEND recorded with `units > 0` (reinvestment) silently ignores the units, understating holdings. | In `add_transaction`, reject `units != 0` on DIVIDEND with a message to record reinvestment as a BUY/SIP. |
| 10 | `cli/commands/invest.py:124-133`, `services/portfolio.py:141-146` | MEDIUM | `sip` passes `fx=None, amount=None`, so `amount_inr = units × price × 1`. Nothing prevents running it (or `buy` without `--fx`) on a `currency_native="USD"` asset → INR amount understated ~88×. | In `add_transaction`: if `inv.currency_native != "INR"` and both `fx_rate_used` and `amount_inr` are None, raise `ValueError("non-INR asset requires --fx or --amount")`. CLI `sip` additionally rejects non-INR/non-MF symbols. |
| 11 | `services/portfolio.py:102-162` | MEDIUM | No SELL validation: you can sell more units than held; `_market_holding` then returns `None` (position vanishes) while `historical_net_worth` and XIRR still count the phantom proceeds — silent data corruption. | `validate_transaction` helper (see 2c): SELL units ≤ currently-held units; BUY/SELL forbidden on FD-type investments. |
| 12 | `api/server.py:148-154, 128-145` | MEDIUM | `_refresh_prices` runs synchronous yfinance/mfapi/FX HTTP calls directly in the NiceGUI event-loop click handler — the whole UI freezes for seconds–minutes (one slow symbol × timeout 10 s each). | `async def _refresh_prices(): result = await asyncio.to_thread(_do_refresh)` (see 2b). |
| 13 | `services/portfolio.py:67-100` (`add_fd`) | LOW | `add_fd` never validates `maturity_date >= start_date`; the bad row is accepted and `calculate_fd_value` raises `ValueError` later — every `holdings`/`networth`/dashboard call crashes until the row is hand-deleted. | Validate at insert time in `add_fd`. |
| 14 | `db/models.py:80-81` | LOW | `Field(ge=1, le=12)` on `Budget.month` is not enforced for `table=True` SQLModels (no validation on instantiation); only `BudgetService.set_budget` guards it, so direct model writes can store month 13. | Add SQL `CHECK` constraints (see 2c); keep the service guard. |
| 15 | `cli/commands/expense.py:63-66` | LOW | `expense list --category Foo` with an unknown category silently sets `category_id=-1` and prints an empty table — looks like "no expenses" instead of "no such category". | Print a warning / exit 1 like `expense add` does. |
| 16 | `services/fetcher.py:241-243`, `models.py:138` | LOW | All timestamps are naive `datetime.now()` local time; a TZ change (or WSL clock skew) silently mis-ages the cache (negative or inflated staleness). | Store UTC (`datetime.now(dt.UTC)`) consistently; one-time migration is unnecessary if staleness tolerates a single mixed window. |
| 17 | `pyproject.toml:17` | LOW | `pandas>=3.0.3` is declared but never imported anywhere in `src/` — dead weight (~60 MB) in every install. | Remove it (or keep it deliberately for B3 broker-import which will need `read_excel`). |
| 18 | `services/portfolio.py:141` | LOW | `Decimal(fx_rate_used)` bypasses `to_decimal`'s float guard — a float fx rate sneaks in with binary-float noise, unlike every other monetary input. | Use `to_fx(fx_rate_used)`. |

---

## Web UI Bug Report (NiceGUI `api/server.py`)

Audit of the web/desktop UI layer after `feat/web-ui-full-parity`. Both bugs are
fixed on this branch with regression tests in `tests/test_web_ui.py`.

| # | File:Lines | Severity | Root Cause | Fix |
|---|-----------|----------|------------|-----|
| WUI-1 | `api/server.py:757-760` (`_holdings_panel`) | HIGH | The "Refresh prices" button scheduled its async handler with `on_click=lambda: asyncio.ensure_future(_refresh_prices())`. `ensure_future` runs the coroutine as a detached task with an **empty slot stack**, so the first `ui.notification(...)` inside it raised `RuntimeError: The current slot cannot be determined…` and the refresh silently died (task exception never retrieved). | Pass the coroutine function directly: `on_click=_refresh_prices`. NiceGUI awaits async click handlers inside the client context, so the spinner/summary notifications render correctly. |
| WUI-2 | `api/server.py:1449-1456` (`_networth_history_view`) | LOW (UX) | The History panel calls its `@ui.refreshable history_view()` once at build time. With the date inputs still empty, `dt.date.fromisoformat("")` raised `ValueError`, firing a spurious **"Invalid date format"** error toast on *every* page load (the panel is built eagerly with all other tabs). | Guard the empty-input case: show a `"Enter a start date and click Show history."` prompt and return before parsing, so the error toast only appears for genuinely malformed input the user typed. |

**Test approach.** `tests/test_web_ui.py` uses `nicegui.testing.User` (headless, no
selenium) to: render every top-level tab + sub-panel (build-time smoke); click
every reachable action button with empty forms and assert no uncaught
exception/ERROR log (the `User` teardown enforces this); drive the seeded
dashboard/holdings/net-worth/analysis read paths; and regression-test WUI-1
(offline-stubbed refresh, asserting the in-context summary) and WUI-2 (no
notification on load). The full NiceGUI test plugin needs selenium, so the root
`conftest.py` registers only `nicegui.testing.user_plugin`.

---

## Architecture Improvements (Task 2)

### 2a Database

**PriceCache pruning** — Effort: S, ~60 LOC
- Strategy: keep the latest **5 rows per investment** (enough for debugging/audit) — simpler and more predictable than age-based pruning for irregular refreshers.
- Implementation: after each `_store_price` commit, run
  ```sql
  DELETE FROM prices_cache WHERE investment_id = :id AND id NOT IN (
    SELECT id FROM prices_cache WHERE investment_id = :id ORDER BY fetched_at DESC LIMIT 5)
  ```
  Same treatment for `fx_rates` per currency_pair. No migration needed for the pruning itself (pure DML), but ship a one-time cleanup in the index migration below.

**Missing indexes** — Effort: S, ~40 LOC (one Alembic revision)
- `ix_prices_cache_inv_fetched` on `PriceCache(investment_id, fetched_at)` — makes the latest-price lookup a pure index scan, no sort.
- `ix_transactions_inv_date` on `Transaction(investment_id, date)` — serves `_market_holding` and future per-investment date-ranged queries.
- `Expense(date)` already exists (`ix_expenses_date` in the initial migration) — no action; add `Expense(category_id, date)` composite instead, which is what `BudgetService._spent` actually filters on.
- Model side: `__table_args__ = (Index(...),)` so `create_all` and Alembic agree.

**alembic.ini / env.py** — Effort: S, ~3 LOC
- Already works (Bug #1): `env.py:22` injects `get_database_url()` which reads `WEALTHLOG_DB_URL`. Only change: comment the placeholder URL out of `alembic.ini` and add a comment pointing at `env.py`.

### 2b Service layer

**`ensure_db()` once per process** — Effort: S, ~30 LOC
```python
_bootstrapped = False
def ensure_db(force: bool = False) -> None:
    global _bootstrapped
    if _bootstrapped and not force: return
    ...existing body...
    _bootstrapped = True
```
- Sentinel must be invalidated when `reset_engine()` runs (tests change `WEALTHLOG_DB_URL`): have `reset_engine()` also reset the flag, or key the sentinel on the engine URL.
- Startup hooks: CLI — call `ensure_db()` in the Typer `@app.callback()`; TUI — in `WealthlogApp.on_mount`; NiceGUI — `app.on_startup(ensure_db)`. `session_scope()` then drops its per-call `ensure_db()`.

**Async price refresh for NiceGUI** — Effort: S/M, ~40 LOC
- Minimal: make the click handler `async` and offload:
  ```python
  async def _refresh_prices() -> None:
      n = ui.notification("Refreshing prices…", spinner=True, timeout=None)
      def work() -> RefreshResult:
          with session_scope() as session:
              return FetcherService(session).refresh_prices()
      result = await asyncio.to_thread(work)
      n.dismiss(); ...notify summary...
  ```
- SQLite session is created **inside** the worker thread (engine already uses `check_same_thread=False`). No background-worker daemon needed at this scale; revisit with C3 alerts.

**LiabilityService** — Effort: M, ~150 LOC + migration
- Schema: `Liability(id, name, amount_inr DecimalText, category ENUM[LOAN, CREDIT_CARD, OTHER], due_date date | None, notes)` + `LiabilityCategory` StrEnum in constants.
- Service: `add_liability / list_liabilities / update_amount / delete_liability / total_liabilities()`.
- `NetWorthService.calculate_net_worth` replaces the hardcoded `liabilities = _ZERO` with `LiabilityService(self.session).total_liabilities()`.
- CLI: `wealthlog-cli liability add/list/delete`. Dashboard summary card "Liabilities".

### 2c Data integrity

**CHECK constraints** — Effort: S, ~30 LOC + migration
- `DecimalText` stores TEXT, so SQL `CHECK (CAST(units AS REAL) >= 0)` is the workable form on SQLite (fine for sign checks; precision is irrelevant for `>= 0`).
- Add via `__table_args__`: `Transaction`: `units >= 0`, `price_per_unit >= 0`; `Expense.amount_inr > 0`; `Budget.limit_amount_inr > 0`; `Budget.month BETWEEN 1 AND 12`; `FdDetails.principal > 0`, `maturity_date >= start_date`.
- Alembic migration with `render_as_batch` (table rebuild on SQLite — already enabled in env.py).

**`validate_transaction` helper** — Effort: S, ~50 LOC
- New `services/validation.py` (or private method on `PortfolioService`), called at the top of `add_transaction`:
  1. Investment exists (already done).
  2. `inv.asset_type == FD` → reject BUY/SELL/SIP (FDs are valued analytically; covers Bug #11's FD half).
  3. SELL → compute currently-held units (reuse the `_market_holding` fold) and reject `units > held`.
  4. Non-INR asset with neither `fx_rate_used` nor `amount_inr` → reject (Bug #10).
  5. DIVIDEND with `units != 0` → reject (Bug #9 gap).

### 2d Testing

**Correction to the brief:** `tests/` is *not* empty — 21 test modules + `conftest.py` with isolated in-memory fixtures already exist, and CI has a coverage gate. The gaps are the bug scenarios above, not basic coverage. Plan — Effort: M:
- `test_fd.py`: add post-maturity XIRR case (Bug #5 regression), maturity-before-start rejection (Bug #13).
- `test_portfolio_service.py`: mixed USD buy + partial SELL avg-cost case (locks in #3's verified behaviour); oversell rejection; FD txn rejection; non-INR-without-fx rejection.
- `test_networth_service.py`: SELL-at-profit history case (Bug #4b).
- `test_fetchers.py`: NaN-price → `FetchError` (Bug #7b); attribute-only `fast_info` stub.
- Round-trip: export transactions CSV → re-import (lands with B3's import service); until then assert column-exact golden CSV.
- Add `pytest-asyncio` to the dev group + an `anyio`-marked test for the `to_thread` refresh wrapper.
- conftest: add a `seeded_session` fixture (categories + 1 stock + 1 MF + 1 FD + txns) so service tests stop hand-building data.

### 2e CLI/UX

- `networth history`: print `[dim]Note: cost-basis (net cash deployed), not market value.[/dim]` before the table — Effort: S, 2 LOC. Remove once A3 snapshots land.
- `invest xirr --symbol <FD>`: detect `asset_type == FD` and print `[dim]FD XIRR is analytical (computed from rate/compounding), not market-derived.[/dim]` — Effort: S, ~6 LOC.
- `--json` / `--csv` flags on read commands (`expense list/summary`, `budget status`, `invest holdings/pnl/xirr`, `networth show/history`) — Effort: M, ~150 LOC. Pattern: a shared `--format table|json|csv` option in `cli/_render.py` that serialises the service-layer dataclasses (`dataclasses.asdict` + `str(Decimal)`); table stays the default. Service layer already returns plain dataclasses, so no service changes needed.

---

## Feature Roadmap (Task 3)

### Milestone A — Polish (~1–2 weeks)

#### A1 Income Tracking — Effort: S/M (~250 LOC)
- **Schema:** reuse `Expense`-shaped table: new `Income(id, date, amount_inr, category_id → categories[type=INCOME], source, description, account_id)`. Separate table (not a sign flag on Expense) keeps budgets/summaries untouched.
- **Service:** `IncomeService.add_income / list_income / monthly_income_summary(year, month) -> dict[str, Decimal]`; `CashflowService.net_cashflow(year, month) = income − expenses` (thin function, can live on IncomeService).
- **CLI:** `wealthlog-cli income add/list/summary`, `expense summary` gains a closing "Net cashflow" line.
- Income categories are already seeded (`Salary`, `Dividends`, `Interest`, `Other Income`).

#### A2 Recurring Transactions — Effort: M (~300 LOC)
- **Schema:** `RecurringExpense(id, amount_inr, category_id, frequency ENUM[DAILY, WEEKLY, MONTHLY], day_of_month int|None, description, active bool, last_generated date|None)`.
- **Service:** `generate_due_instances(as_of) -> list[Expense]` — idempotency via `last_generated` watermark (advance it inside the same commit), *not* by scanning for matching Expense rows (fragile). Clamp `day_of_month` 29–31 to month length.
- **CLI:** `expense recurring add/list/deactivate`, `expense generate-recurring [--as-of]`. Call generation from each interface's startup hook (after 2b) — **not** inside `ensure_db()` (keep bootstrap side-effect-free).

#### A3 Historical Price Snapshots — Effort: M (~300 LOC) — *highest leverage in A*
- **Schema:** `PriceSnapshot(id, investment_id FK, date date, price_inr, source str)` + `UNIQUE(investment_id, date)`.
- **Service:** in `FetcherService._store_price`, also upsert today's snapshot (`INSERT OR REPLACE` on the unique pair). `NetWorthService.historical_net_worth` gains market-mode: for each month-end, `units held (from txns) × latest snapshot ≤ cutoff`; falls back to cost-basis with `NetWorthPoint.is_market_value: bool` flag per point.
- **CLI:** `networth history --mode market|cost` (auto picks market when ≥1 snapshot exists in range). Unblocks real charting in the web UI.

#### A4 SIP Schedule Tracking — Effort: S/M (~250 LOC)
- **Schema:** `SIPSchedule(id, investment_id FK, amount_inr, day_of_month, start_date, end_date date|None, active bool)`.
- **Service:** `get_pending_sips(as_of) -> list[PendingSIP]` — for each active schedule, enumerate due dates in `[start_date, as_of]`, subtract dates that already have a SIP transaction for that investment in that month, return the gap. `record_sip(schedule_id, date, units, nav)` convenience that writes the Transaction.
- **CLI:** `invest sip-schedule add/list`, `invest sip-due` (warns count in `holdings` output footer).

### Milestone B — Analytics (~2–4 weeks)

#### B1 Benchmark Comparison — Effort: M (~300 LOC)
- **Schema:** `Benchmark(id, name UNIQUE [NIFTY50, SENSEX, SP500, QQQM], symbol str ('^NSEI', '^BSESN', '^GSPC', 'QQQM'), currency)`. Reuse `PriceSnapshot` rows keyed by a benchmark-owned pseudo-Investment (asset_type new value `BENCHMARK`, excluded from holdings/net worth) — avoids a parallel snapshot table.
- **Service:** `BenchmarkService.benchmark_return(name, start, end)` from snapshots; `compare(start, end)` returns portfolio XIRR vs benchmark CAGR over same window.
- **CLI:** `invest benchmark --symbol NIFTY50 --start 2024-01-01 [--end]`; seeds the 4 standard benchmarks on first use. Depends on A3.

#### B2 Indian Tax P&L (LTCG/STCG) — Effort: L (~600 LOC)
- **Prereq:** FIFO lot matching (average-cost holdings stay as-is for display; tax engine re-derives lots from the transaction log — no schema change to Transaction).
- **Schema:** none required; optional `TaxRate` constants module (12.5% LTCG over ₹1.25L exemption, 20% STCG, post-July-2024 rules; keep rates in constants with effective dates, informational only).
- **Service:** `TaxService.capital_gains_report(fy: str) -> list[GainRow]` — per SELL, FIFO-match buy lots, classify LTCG (>1 yr for equity/MF) vs STCG, apply grandfathering (equity bought < 2018-02-01 → cost = max(cost, FMV on 2018-01-31); FMV needs a one-time manual price input or snapshot import).
- **CLI:** `invest tax-report --fy 2025-26 [--csv out.csv]`. Every output carries "Informational only — not tax advice; verify with a CA."

#### B3 Broker Statement Import — Effort: L (~700 LOC)
- **Deps:** add `openpyxl` (and keep `pandas` — its `read_excel` earns its place here).
- **Service:** `ImportService` with per-broker parsers → normalized `list[ParsedTxn]`; `preview(path)` (dry run, default) and `commit(parsed)`. Dedup heuristic: skip rows matching an existing txn on (investment, date, type, units, amount). Unknown symbols auto-create Investments flagged for review.
  - Zerodha `tradebook_*.xlsx` / `holdings_*.xlsx`; Groww `portfolio_export_*.xlsx`; INDmoney US-holdings CSV (needs FX at trade date — use frankfurter historical endpoint `/{date}`).
- **CLI:** `import zerodha <path> [--commit]`, same for `groww`, `indmoney`. Dry-run prints the would-be transactions table.

#### B4 Concentration Risk Report — Effort: S/M (~250 LOC)
- **Schema:** `Investment.sector: str | None` (one nullable column, batch migration); optional `AllocationTarget(asset_type, target_pct)` table for target-vs-actual.
- **Service:** `PortfolioService.concentration_report()` → top-N holdings by % of market value, sector weights, asset-class weights vs targets, `HIGH CONCENTRATION` flag on positions > 10%.
- **CLI:** `invest concentration [--top 10]`; red-flag rows in the table.

#### B5 Dividend Tracker — Effort: S (~200 LOC)
- **Schema:** none — DIVIDEND transactions already exist.
- **Service:** `DividendService.total_by_year() / total_by_holding(year) / trailing_yield(investment_id)` (12-mo dividends ÷ current market value); `absolute_return` variant on PnL that adds cumulative dividends (XIRR already credits them — Bug #9 analysis).
- **CLI:** `invest dividends [--year]`, yield column in `holdings` output (optional flag).

### Milestone C — UI overhaul (~4–8 weeks)

#### C1 Tauri Desktop App — Effort: L/XL
- **Architecture:** Tauri v2 shell + Python sidecar (recommended over PyO3 — keeps the existing service layer untouched and separately testable). Sidecar = a small FastAPI/uvicorn process exposing the service layer as JSON; Tauri spawns it via the sidecar API on a random localhost port and passes the port to the frontend.
- **IPC contract first** (design deliverable before any code): `GET /dashboard`, `GET /holdings`, `POST /transactions`, `POST /expenses`, `POST /refresh-prices` (async job + `GET /jobs/{id}`), `GET /networth/history`. All money as strings (Decimal-safe), dates ISO. This API doubles as a future mobile/web backend.
- **Frontend:** React + Recharts (donut allocation, net-worth area chart from A3 snapshots, holdings table). NiceGUI stays during the transition; delete it when Tauri reaches parity.
- **Phases:** (1) IPC contract + FastAPI sidecar with tests, ~1 wk; (2) Tauri shell + read-only dashboard, ~1–2 wk; (3) write flows + refresh job, ~1 wk; (4) packaging (Linux AppImage/WSL caveats, Windows MSI), ~1 wk.

#### C2 Rich TUI Dashboard Enhancements — Effort: M (~500 LOC)
- Inline expense entry: `Input` (amount, description, date) + `Select` (category) in a collapsible pane on the Expenses tab; reuse `ExpenseService` directly.
- `F5` price refresh: `@work(thread=True)` Textual worker calling `FetcherService.refresh_prices`, `LoadingIndicator` while running, `notify` summary (mirrors 2b's pattern).
- Allocation chart: Textual has no donut; use a horizontal bar per asset class (`Sparkline` is for time series) — honest and readable in cells.
- Tabs: Dashboard / Expenses / Budgets / Holdings already exist via `TabbedContent` except Holdings is embedded in Dashboard — split it out; add Tax tab after B2.

#### C3 Portfolio Alerts — Effort: M/L (~500 LOC)
- **Schema:** `AlertRule(id, kind ENUM[PRICE_DROP, BUDGET_PCT, SIP_DUE], threshold, investment_id|category_id nullable, active)` + `AlertEvent(rule_id, fired_at, message)` for dedup (don't re-fire same condition same day).
- **Watcher:** `wealthlog-alerts` console script (separate process; don't couple to NiceGUI's lifecycle) — evaluates rules against services every N minutes, or one-shot for cron/systemd-timer use (`wealthlog-alerts --once` is the simplest reliable Linux delivery).
- **Delivery:** `notify-send` (subprocess) first; `plyer` for cross-platform later; Telegram webhook via `WEALTHLOG_TELEGRAM_TOKEN` + `WEALTHLOG_TELEGRAM_CHAT_ID` (httpx POST, ~30 LOC). Depends on A4 (SIP due) and existing budget service.

---

## Suggested fix order (bugs only)

1. **#5** FD XIRR terminal date (wrong numbers today, 1-line fix)
2. **#10/#11/#9-gap** → one `validate_transaction` change (2c)
3. **#7** yfinance NaN crash + key fallback
4. **#2** bootstrap sentinel
5. **#4** networth history disclaimer + proceeds-vs-cost fix
6. **#8** PriceCache pruning + indexes (2a)
7. Rest (LOW) opportunistically.
