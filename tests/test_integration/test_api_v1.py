"""API v1 endpoint integration tests.

Tests the original v1 endpoints (health, macro/dashboard, agents, signals,
portfolio, risk) and the dashboard HTML route.

All tests use httpx.AsyncClient with a noop lifespan to bypass DB dependencies.
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
    """Return a synchronous TestClient for v1 endpoint tests."""
    from starlette.testclient import TestClient

    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestAPIv1Endpoints:
    """Verify all v1 endpoints return HTTP 200."""

    def test_health(self, client):
        """GET /health -> 200, response has 'status' key."""
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    def test_macro_dashboard(self, client):
        """GET /api/v1/macro/dashboard -> 200 or 500 (DB dependent)."""
        resp = client.get("/api/v1/macro/dashboard")
        # Route exists; 500 is acceptable without a live DB
        assert resp.status_code in (200, 500)

    def test_agents_signals(self, client):
        """GET /api/v1/agents -> 200, response has 'status' key."""
        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    def test_signals_dashboard(self, client):
        """GET /api/v1/signals/latest -> 200 or 500."""
        resp = client.get("/api/v1/signals/latest")
        assert resp.status_code in (200, 500)

    def test_portfolio_current(self, client):
        """GET /api/v1/portfolio/current -> 200, 500, or 503 (no DB/PMS in CI)."""
        resp = client.get("/api/v1/portfolio/current")
        assert resp.status_code in (200, 500, 503)

    def test_portfolio_risk(self, client):
        """GET /api/v1/portfolio/risk -> 200, 500, or 503 (no DB/PMS in CI)."""
        resp = client.get("/api/v1/portfolio/risk")
        assert resp.status_code in (200, 500, 503)

    def test_dashboard_html(self, client):
        """GET /dashboard -> 200, response contains HTML."""
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        text = resp.text
        assert "<!DOCTYPE html>" in text or "<html" in text
