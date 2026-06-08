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

```bash
uv run wealthlog          # web/desktop dashboard (localhost)
uv run wealthlog-tui      # terminal UI
uv run wealthlog-cli --help   # scriptable commands
```

> _Screenshots: coming once the dashboard lands (Milestone 5)._

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

## License

[MIT](LICENSE).
