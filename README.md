# wealthlog

[![CI](https://github.com/Rohithn14/wealthlog/actions/workflows/ci.yml/badge.svg)](https://github.com/Rohithn14/wealthlog/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![uv](https://img.shields.io/badge/built%20with-uv-de5fe9.svg)](https://github.com/astral-sh/uv)

> Local-first personal finance & investment tracker. INR-first, tracks a mixed
> Indian + US portfolio, with expenses, budgets, net worth, XIRR/P&L, and exports —
> usable from the **CLI**, **TUI**, or a **web/desktop dashboard**.

## Features

- **Expenses** — log & categorise spending with tags, dates, and custom categories.
- **Investments** — Indian stocks (NSE/BSE), Indian mutual funds (lump sum + SIP),
  gold ETFs, US stocks, and fixed deposits. P&L (absolute + %) and **XIRR** per
  asset and portfolio-wide.
- **Budgets** — per-category monthly limits with overage alerts.
- **Net worth** — assets − liabilities, broken down by asset class, all in INR.
- **Export** — CSV (raw data) and PDF (formatted report).
- **Three interfaces** — `wealthlog` (web/desktop), `wealthlog-tui` (terminal),
  `wealthlog-cli` (scriptable).

INR is the single display currency; USD assets are auto-converted using a cached
live FX rate, and the UI always shows when the rate was last fetched.

## Installation

Requires [`uv`](https://github.com/astral-sh/uv) and Python 3.11+.

```bash
git clone https://github.com/Rohithn14/wealthlog.git
cd wealthlog
uv sync
```

## Usage

Three interfaces over one shared core:

```bash
uv run wealthlog          # web/desktop dashboard at http://127.0.0.1:8080
uv run wealthlog-tui      # terminal UI (press 'r' to refresh, 'q' to quit)
uv run wealthlog-cli --help   # scriptable commands
```

### CLI examples

```bash
# Expenses
uv run wealthlog-cli expense add 250.50 -c "Food & Dining" -d 2026-06-05 --tags lunch,office
uv run wealthlog-cli expense summary 2026 6

# Budgets (alerts fire when spending exceeds the limit)
uv run wealthlog-cli budget set "Food & Dining" 8000 -y 2026 -m 6
uv run wealthlog-cli budget alerts 2026 6

# Investments — Indian stock, US stock (INR via FX), mutual-fund SIP, fixed deposit
uv run wealthlog-cli invest add INFY.NS "Infosys" -t STOCK_IN
uv run wealthlog-cli invest buy INFY.NS 10 1500 -d 2024-01-01
uv run wealthlog-cli invest add AAPL "Apple" -t STOCK_US --currency USD
uv run wealthlog-cli invest buy AAPL 5 190 -d 2024-03-01 --fx 83
uv run wealthlog-cli invest add 120503 "Axis Bluechip" -t MF
uv run wealthlog-cli invest sip 120503 100 50 -d 2024-01-01
uv run wealthlog-cli invest add-fd "SBI FD" 100000 7.1 --start 2024-01-01 --maturity 2027-01-01

# Live prices (yfinance / mfapi.in / frankfurter FX), with caching + manual fallback
uv run wealthlog-cli invest refresh
uv run wealthlog-cli invest set-price INFY.NS 1620      # manual override
uv run wealthlog-cli invest holdings
uv run wealthlog-cli invest xirr                        # portfolio-wide XIRR

# Net worth & exports
uv run wealthlog-cli networth show
uv run wealthlog-cli export csv transactions -o transactions.csv
uv run wealthlog-cli export pdf -o report.pdf
```

All amounts are stored and displayed in **INR**. USD holdings are converted using a
cached live FX rate; the holdings/dashboard views flag prices that are stale.

> _Screenshots: TODO (dashboard + TUI)._

## Development

```bash
uv sync                   # install runtime + dev dependencies
uv run pytest             # run the test suite
uv run pytest --cov=wealthlog --cov-report=term-missing
uv run ruff check .       # lint
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full developer guide.

## Tech stack

| Concern | Choice |
|---|---|
| Packaging | `uv` (src layout) |
| DB / ORM | SQLite + SQLModel + Alembic |
| CLI / TUI / Web | Typer / Textual / NiceGUI |
| Market data | yfinance, mfapi.in, frankfurter.app |
| Finance math | pyxirr, pandas |
| Export | csv (stdlib), fpdf2 |

## Architecture

```
src/wealthlog/
  config.py constants.py money.py logging_conf.py bootstrap.py
  db/         SQLModel models, Decimal-safe column type, session, seed
  finance/    pure calculations — XIRR (pyxirr) and FD accrual
  services/   business logic: expense, budget, portfolio, networth, fetcher, export
  fetchers/   market data: yfinance, mfapi.in, frankfurter FX
  exporters/  CSV (stdlib) + PDF (fpdf2)
  api/        NiceGUI web/desktop dashboard (+ headless data layer)
  tui/        Textual terminal UI
  cli/        Typer command groups
migrations/   Alembic
tests/        pytest (in-memory SQLite, network mocked)
```

Design notes: all money is `Decimal` (INR 2dp, prices 4dp, FX 6dp) and stored as exact
TEXT in SQLite (SQLite's NUMERIC affinity would coerce to float). The CLI, TUI, and web
UI are thin presentation layers over a single tested service layer. FD value is computed
analytically (no live price); XIRR returns `None` when undefined (e.g. only buys so far).

## License

[MIT](LICENSE).
