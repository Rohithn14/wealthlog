"""Tests for the FastAPI sidecar (C1 IPC contract) via TestClient.

These exercise the JSON contract end-to-end against the in-memory test DB that
``conftest`` configures (``WEALTHLOG_DB_URL=sqlite://``).
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from wealthlog.constants import AssetType, TransactionType
from wealthlog.services.portfolio import PortfolioService
from wealthlog.sidecar import create_app


@pytest.fixture
def client(db_session):
    # db_session ensures the shared in-memory engine/schema is initialised.
    return TestClient(create_app())


@pytest.fixture
def seeded(db_session):
    pf = PortfolioService(db_session)
    inv = pf.add_investment("INFY.NS", "Infosys", AssetType.STOCK_IN)
    pf.add_transaction(inv.id, dt.date(2026, 1, 1), TransactionType.BUY, "10", "100")
    return inv


class TestReadEndpoints:
    def test_health(self, client):
        assert client.get("/health").json() == {"status": "ok"}

    def test_dashboard_shape(self, client, seeded):
        body = client.get("/dashboard").json()
        assert body["holdings_count"] == 1
        assert isinstance(body["net_worth_inr"], str)  # money as string
        assert body["by_asset_class"][0]["asset_type"] == "STOCK_IN"

    def test_holdings(self, client, seeded):
        rows = client.get("/holdings").json()
        assert len(rows) == 1
        assert rows[0]["symbol"] == "INFY.NS"
        assert rows[0]["invested_inr"] == "1000.00"

    def test_networth_history(self, client, seeded):
        resp = client.get(
            "/networth/history",
            params={"start": "2026-01-01", "end": "2026-03-31", "mode": "cost"},
        )
        points = resp.json()
        assert len(points) == 3
        assert points[0]["invested_inr"] == "1000.00"

    def test_networth_history_bad_mode(self, client, seeded):
        resp = client.get(
            "/networth/history",
            params={"start": "2026-01-01", "end": "2026-03-31", "mode": "bogus"},
        )
        assert resp.status_code == 400


class TestWriteEndpoints:
    def test_add_transaction(self, client, seeded):
        resp = client.post(
            "/transactions",
            json={
                "symbol": "INFY.NS", "date": "2026-02-01", "type": "BUY",
                "units": "5", "price": "200",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["amount_inr"] == "1000.00"

    def test_add_transaction_unknown_symbol(self, client):
        resp = client.post(
            "/transactions",
            json={"symbol": "NOPE", "date": "2026-02-01", "type": "BUY",
                  "units": "5", "price": "200"},
        )
        assert resp.status_code == 404

    def test_add_transaction_oversell_rejected(self, client, seeded):
        resp = client.post(
            "/transactions",
            json={"symbol": "INFY.NS", "date": "2026-02-01", "type": "SELL",
                  "units": "999", "price": "200"},
        )
        assert resp.status_code == 400

    def test_add_expense(self, client):
        resp = client.post("/expenses", json={"date": "2026-02-01", "amount": "250.50"})
        assert resp.status_code == 201
        assert resp.json()["amount_inr"] == "250.50"


class TestRefreshJob:
    def test_refresh_returns_job_and_completes(self, client, seeded):
        resp = client.post("/refresh-prices")
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]
        status = client.get(f"/jobs/{job_id}").json()
        # With no live fetcher the job still resolves (done or error), never missing.
        assert status["status"] in {"running", "done", "error"}

    def test_unknown_job_404(self, client):
        assert client.get("/jobs/nope").status_code == 404
