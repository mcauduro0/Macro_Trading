"""API v3 endpoint and WebSocket integration tests.

Tests the v3 endpoints added in Phase 19:
  REST: backtest/run, backtest/results, backtest/portfolio, backtest/comparison,
        strategies/{id}, strategies/{id}/signal/latest, strategies/{id}/signal/history
  WebSocket: /ws/signals, /ws/portfolio, /ws/alerts

All tests use starlette TestClient with a noop lifespan.
Marked with @pytest.mark.integration.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi import FastAPI


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def test_app():
    """Create a FastAPI app with noop lifespan (no DB required)."""

    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield

    with patch("src.api.main.lifespan", _noop_lifespan):
        import importlib
        import src.api.main

        importlib.reload(src.api.main)
        app = src.api.main.app

    return app


@pytest.fixture(scope="module")
def client(test_app):
    """Return a synchronous TestClient for v3 endpoint tests."""
    from starlette.testclient import TestClient

    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# REST endpoint tests
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestAPIv3RESTEndpoints:
    """Verify all v3 REST endpoints return HTTP 200 or 202."""

    def test_backtest_run(self, client):
        """POST /api/v1/backtest/run -> 200 or 202."""
        resp = client.post(
            "/api/v1/backtest/run",
            json={"strategy_id": "RATES_BR_01"},
        )
        assert resp.status_code in (200, 202)
        body = resp.json()
        assert "status" in body

    def test_backtest_results(self, client):
        """GET /api/v1/backtest/results?strategy_id=RATES_BR_01 -> 200."""
        resp = client.get(
            "/api/v1/backtest/results",
            params={"strategy_id": "RATES_BR_01"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    def test_backtest_portfolio(self, client):
        """POST /api/v1/backtest/portfolio -> 200 or 202."""
        resp = client.post(
            "/api/v1/backtest/portfolio",
            json={"strategy_ids": ["RATES_BR_01"]},
        )
        assert resp.status_code in (200, 202)
        body = resp.json()
        assert "status" in body

    def test_backtest_comparison(self, client):
        """GET /api/v1/backtest/comparison?strategy_ids=... -> 200."""
        resp = client.get(
            "/api/v1/backtest/comparison",
            params={"strategy_ids": "RATES_BR_01,FX_BR_01"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    def test_strategy_detail(self, client):
        """GET /api/v1/strategies/RATES_BR_01 -> 200, has strategy_id."""
        resp = client.get("/api/v1/strategies/RATES_BR_01")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert body["data"]["strategy_id"] == "RATES_BR_01"

    def test_strategy_signal_latest(self, client):
        """GET /api/v1/strategies/RATES_BR_01/signal/latest -> 200."""
        resp = client.get("/api/v1/strategies/RATES_BR_01/signal/latest")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    def test_strategy_signal_history(self, client):
        """GET /api/v1/strategies/RATES_BR_01/signal/history -> 200."""
        resp = client.get("/api/v1/strategies/RATES_BR_01/signal/history")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body


# ---------------------------------------------------------------------------
# WebSocket tests
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestAPIv3WebSockets:
    """Verify all 3 WebSocket channels accept connections."""

    def test_ws_signals(self, client):
        """Connect to /ws/signals, assert connection accepted."""
        with client.websocket_connect("/ws/signals") as ws:
            # Connection accepted if we get here without exception
            assert ws is not None

    def test_ws_portfolio(self, client):
        """Connect to /ws/portfolio, assert connection accepted."""
        with client.websocket_connect("/ws/portfolio") as ws:
            assert ws is not None

    def test_ws_alerts(self, client):
        """Connect to /ws/alerts, assert connection accepted."""
        with client.websocket_connect("/ws/alerts") as ws:
            assert ws is not None
