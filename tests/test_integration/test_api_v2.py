"""API v2 endpoint integration tests.

Tests the v2 endpoints added in Phases 17-18:
  risk/var, risk/stress, risk/limits,
  portfolio/target, portfolio/rebalance-trades, portfolio/attribution,
  reports/daily/latest.

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
    """Return a synchronous TestClient for v2 endpoint tests."""
    from starlette.testclient import TestClient

    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestAPIv2Endpoints:
    """Verify all v2 endpoints return HTTP 200."""

    def test_risk_var(self, client):
        """GET /api/v1/risk/var -> 200."""
        resp = client.get("/api/v1/risk/var")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    def test_risk_stress(self, client):
        """GET /api/v1/risk/stress -> 200."""
        resp = client.get("/api/v1/risk/stress")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    def test_risk_limits(self, client):
        """GET /api/v1/risk/limits -> 200."""
        resp = client.get("/api/v1/risk/limits")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    def test_portfolio_target(self, client):
        """GET /api/v1/portfolio/target -> 200."""
        resp = client.get("/api/v1/portfolio/target")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    def test_portfolio_rebalance_trades(self, client):
        """GET /api/v1/portfolio/rebalance-trades -> 200."""
        resp = client.get("/api/v1/portfolio/rebalance-trades")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    def test_portfolio_attribution(self, client):
        """GET /api/v1/portfolio/attribution -> 200."""
        resp = client.get("/api/v1/portfolio/attribution")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body

    def test_reports_daily(self, client):
        """GET /api/v1/reports/daily/latest -> 200."""
        resp = client.get("/api/v1/reports/daily/latest")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
