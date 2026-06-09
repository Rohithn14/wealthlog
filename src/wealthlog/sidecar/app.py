"""FastAPI application for the wealthlog sidecar (C1 IPC contract).

Endpoints (money as strings, dates ISO):
    GET  /health
    GET  /dashboard
    GET  /holdings
    GET  /networth/history?start=&end=&mode=
    POST /transactions          {symbol,date,type,units,price,fx_rate?,amount_inr?}
    POST /expenses              {date,amount,category?,description?}
    POST /refresh-prices        -> {job_id}
    GET  /jobs/{job_id}
"""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from wealthlog.bootstrap import ensure_db, session_scope
from wealthlog.constants import TransactionType
from wealthlog.db.models import Category, Investment
from wealthlog.services.expense import ExpenseService
from wealthlog.services.fetcher import FetcherService
from wealthlog.services.networth import NetWorthService
from wealthlog.services.portfolio import PortfolioService

# In-process job registry for async price refresh. Single-user desktop scale;
# revisit with a real queue if the sidecar ever serves multiple clients.
_JOBS: dict[str, dict[str, Any]] = {}


def _money(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


class TransactionIn(BaseModel):
    symbol: str
    date: dt.date
    type: TransactionType
    units: str
    price: str
    fx_rate: str | None = None
    amount_inr: str | None = None


class ExpenseIn(BaseModel):
    date: dt.date
    amount: str
    category: str | None = None
    description: str | None = None


def create_app() -> FastAPI:
    """Build the sidecar FastAPI app (factory keeps it import-test friendly)."""
    app = FastAPI(title="wealthlog sidecar", version="1.0")

    @app.on_event("startup")
    def _startup() -> None:  # pragma: no cover - exercised via lifespan in tests
        ensure_db()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/dashboard")
    def dashboard() -> dict[str, Any]:
        with session_scope() as session:
            nw = NetWorthService(session).calculate_net_worth()
            holdings = PortfolioService(session).get_holdings()
            return {
                "net_worth_inr": _money(nw.net_worth_inr),
                "total_assets_inr": _money(nw.total_assets_inr),
                "total_liabilities_inr": _money(nw.total_liabilities_inr),
                "holdings_count": len(holdings),
                "by_asset_class": [
                    {
                        "asset_type": c.asset_type.value,
                        "market_value_inr": _money(c.market_value_inr),
                        "pct_of_total": _money(c.pct_of_total),
                    }
                    for c in nw.by_asset_class
                ],
            }

    @app.get("/holdings")
    def holdings() -> list[dict[str, Any]]:
        with session_scope() as session:
            return [
                {
                    "symbol": h.symbol,
                    "name": h.name,
                    "asset_type": h.asset_type.value,
                    "units": _money(h.units),
                    "invested_inr": _money(h.invested_inr),
                    "market_value_inr": _money(h.market_value_inr),
                    "pnl_abs_inr": _money(h.pnl_abs_inr),
                    "pnl_pct": _money(h.pnl_pct),
                    "price_is_stale": h.price_is_stale,
                }
                for h in PortfolioService(session).get_holdings()
            ]

    @app.get("/networth/history")
    def networth_history(start: dt.date, end: dt.date, mode: str = "cost") -> list[dict[str, Any]]:
        with session_scope() as session:
            try:
                points = NetWorthService(session).historical_net_worth(start, end, mode=mode)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return [
                {
                    "year": p.year,
                    "month": p.month,
                    "invested_inr": _money(p.invested_inr),
                    "market_value_inr": _money(p.market_value_inr),
                    "is_market_value": p.is_market_value,
                }
                for p in points
            ]

    @app.post("/transactions", status_code=201)
    def add_transaction(body: TransactionIn) -> dict[str, Any]:
        with session_scope() as session:
            inv = session.exec(
                select(Investment).where(Investment.symbol == body.symbol)
            ).first()
            if inv is None:
                raise HTTPException(status_code=404, detail=f"Unknown symbol '{body.symbol}'")
            try:
                txn = PortfolioService(session).add_transaction(
                    inv.id, body.date, body.type, body.units, body.price,
                    amount_inr=body.amount_inr, fx_rate_used=body.fx_rate,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"id": txn.id, "amount_inr": _money(txn.amount_inr)}

    @app.post("/expenses", status_code=201)
    def add_expense(body: ExpenseIn) -> dict[str, Any]:
        with session_scope() as session:
            category_id = None
            if body.category:
                cat = session.exec(
                    select(Category).where(Category.name == body.category)
                ).first()
                if cat is None:
                    raise HTTPException(
                        status_code=404, detail=f"Unknown category '{body.category}'"
                    )
                category_id = cat.id
            exp = ExpenseService(session).add_expense(
                body.date, body.amount, category_id=category_id, description=body.description
            )
            return {"id": exp.id, "amount_inr": _money(exp.amount_inr)}

    @app.post("/refresh-prices", status_code=202)
    async def refresh_prices() -> dict[str, str]:
        job_id = uuid.uuid4().hex
        _JOBS[job_id] = {"status": "running", "result": None}

        def work() -> dict[str, Any]:
            with session_scope() as session:
                result = FetcherService(session).refresh_prices()
                return {
                    "updated": list(result.updated),
                    "skipped_fresh": list(result.skipped_fresh),
                    "failed": [list(f) for f in result.failed],
                }

        async def run() -> None:
            try:
                _JOBS[job_id] = {"status": "done", "result": await asyncio.to_thread(work)}
            except Exception as exc:  # noqa: BLE001 - surface any fetch failure to the client
                _JOBS[job_id] = {"status": "error", "result": str(exc)}

        asyncio.create_task(run())
        return {"job_id": job_id}

    @app.get("/jobs/{job_id}")
    def job_status(job_id: str) -> dict[str, Any]:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Unknown job")
        return {"job_id": job_id, **job}

    return app


def main() -> None:  # pragma: no cover - process entry point
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=0)
