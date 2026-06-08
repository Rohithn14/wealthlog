# Contributing to wealthlog

Thanks for your interest! wealthlog is a local-first, single-user finance tracker
built with a clean service layer so it stays contributor-friendly.

## Dev environment

Requires [`uv`](https://github.com/astral-sh/uv) and Python 3.11+.

```bash
git clone https://github.com/Rohithn14/wealthlog.git
cd wealthlog
uv sync          # installs runtime + dev dependencies into .venv
```

## Running tests

```bash
uv run pytest                                   # full suite
uv run pytest --cov=wealthlog --cov-report=term-missing
uv run pytest tests/test_expense_service.py     # a single file
```

Tests use an **in-memory SQLite** database (never your real data file). Every
service function must have tests; we deliberately favour broad, varied coverage
(happy paths, edge cases, error paths, boundary values, Decimal precision).

## Linting

```bash
uv run ruff check .
uv run ruff format .
```

## Code standards

- All public functions: type annotations + Google-style docstrings.
- Money is `Decimal`, never `float` (INR 2dp, prices 4dp, FX 6dp).
- No magic numbers — constants live in `config.py` / `constants.py`.
- Never silently swallow exceptions — log via `wealthlog.logging_conf` or raise.

## Branching & commits

- Branch per change: `feat/...`, `fix/...`, `chore/...`, `docs/...`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
- Open a PR against `main`; CI (`uv run pytest`) must pass before merge.

## Project layout

```
src/wealthlog/
  config.py constants.py money.py logging_conf.py
  db/         models, session, seed
  services/   business logic (expense, budget, portfolio, networth, fetcher, export)
  fetchers/   market data sources (yfinance, mfapi, fx)
  exporters/  csv + pdf
  finance/    pure calculations (xirr, fd)
  api/ tui/ cli/   the three interfaces
tests/        pytest suite (in-memory SQLite)
```
