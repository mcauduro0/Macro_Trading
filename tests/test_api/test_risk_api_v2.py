"""Tests for risk API v2 endpoints: /var, /stress, /limits, /dashboard.

Verifies all 4 new risk endpoints return 200 with expected response
structure, and confirms backward-compatible /report still works.
Uses the same TestClient pattern as test_dashboard.py.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_test_app() -> FastAPI:
    """Build a minimal FastAPI app with risk router (no DB lifespan)."""

    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield

    from src.api.routes import risk_api

    app = FastAPI(lifespan=_noop_lifespan)
    app.include_router(risk_api.router, prefix="/api/v1")
    return app


@pytest.fixture(scope="module")
def client():
    """Provide a TestClient for the risk-API-only app."""
    app = _make_test_app()
    with TestClient(app) as c:
        yield c


# -----------------------------------------------------------------------
# GET /risk/var
# -----------------------------------------------------------------------


class TestRiskVarEndpoint:
    """Tests for GET /api/v1/risk/var."""

    def test_var_returns_200(self, client: TestClient):
        """GET /risk/var returns HTTP 200."""
        resp = client.get("/api/v1/risk/var")
        assert resp.status_code == 200

    def test_var_response_structure(self, client: TestClient):
        """Response contains status, data, and meta envelope."""
        resp = client.get("/api/v1/risk/var")
        body = resp.json()
        assert body["status"] == "ok"
        assert "data" in body
        assert "meta" in body
        assert "timestamp" in body["meta"]

    def test_var_all_methods_returned(self, client: TestClient):
        """Default method='all' returns historical, parametric, monte_carlo."""
        resp = client.get("/api/v1/risk/var")
        data = resp.json()["data"]
        results = data["results"]
        assert "historical" in results
        assert "parametric" in results
        assert "monte_carlo" in results

    def test_var_has_required_keys(self, client: TestClient):
        """Each VaR result has var_95, var_99, cvar_95, cvar_99."""
        resp = client.get("/api/v1/risk/var")
        results = resp.json()["data"]["results"]
        for method_name, vr in results.items():
            assert "var_95" in vr, f"{method_name} missing var_95"
            assert "var_99" in vr, f"{method_name} missing var_99"
            assert "cvar_95" in vr, f"{method_name} missing cvar_95"
            assert "cvar_99" in vr, f"{method_name} missing cvar_99"

    def test_var_single_method(self, client: TestClient):
        """Requesting method=parametric returns only parametric results."""
        resp = client.get("/api/v1/risk/var", params={"method": "parametric"})
        data = resp.json()["data"]
        results = data["results"]
        assert "method" in results
        assert results["method"] == "parametric"


# -----------------------------------------------------------------------
# GET /risk/stress
# -----------------------------------------------------------------------


class TestRiskStressEndpoint:
    """Tests for GET /api/v1/risk/stress."""

    def test_stress_returns_200(self, client: TestClient):
        """GET /risk/stress returns HTTP 200."""
        resp = client.get("/api/v1/risk/stress")
        assert resp.status_code == 200

    def test_stress_has_6_scenarios(self, client: TestClient):
        """Response contains exactly 6 scenario results."""
        resp = client.get("/api/v1/risk/stress")
        scenarios = resp.json()["data"]["scenarios"]
        assert len(scenarios) == 6

    def test_stress_scenario_structure(self, client: TestClient):
        """Each scenario has required keys."""
        resp = client.get("/api/v1/risk/stress")
        scenarios = resp.json()["data"]["scenarios"]
        for s in scenarios:
            assert "scenario_name" in s
            assert "portfolio_pnl" in s
            assert "portfolio_pnl_pct" in s
            assert "worst_position" in s
            assert "positions_impacted" in s

    def test_stress_filter_by_scenario(self, client: TestClient):
        """Filtering by scenario name narrows results."""
        resp = client.get("/api/v1/risk/stress", params={"scenario": "COVID"})
        scenarios = resp.json()["data"]["scenarios"]
        assert len(scenarios) == 1
        assert "COVID" in scenarios[0]["scenario_name"]


# -----------------------------------------------------------------------
# GET /risk/limits
# -----------------------------------------------------------------------


class TestRiskLimitsEndpoint:
    """Tests for GET /api/v1/risk/limits."""

    def test_limits_returns_200(self, client: TestClient):
        """GET /risk/limits returns HTTP 200."""
        resp = client.get("/api/v1/risk/limits")
        assert resp.status_code == 200

    def test_limits_has_limits_list(self, client: TestClient):
        """Response contains a 'limits' list with entries."""
        resp = client.get("/api/v1/risk/limits")
        data = resp.json()["data"]
        assert "limits" in data
        assert isinstance(data["limits"], list)
        assert len(data["limits"]) > 0

    def test_limits_entry_structure(self, client: TestClient):
        """Each limit entry has expected fields."""
        resp = client.get("/api/v1/risk/limits")
        limits = resp.json()["data"]["limits"]
        for lim in limits:
            assert "limit_name" in lim
            assert "limit_value" in lim
            assert "utilization_pct" in lim
            assert "breached" in lim

    def test_limits_has_overall_status(self, client: TestClient):
        """Response includes overall_status field."""
        resp = client.get("/api/v1/risk/limits")
        data = resp.json()["data"]
        assert "overall_status" in data

    def test_limits_has_risk_budget(self, client: TestClient):
        """Response includes risk_budget information."""
        resp = client.get("/api/v1/risk/limits")
        data = resp.json()["data"]
        assert "risk_budget" in data
        if data["risk_budget"] is not None:
            rb = data["risk_budget"]
            assert "total" in rb
            assert "allocated" in rb
            assert "available" in rb
            assert "utilization_pct" in rb


# -----------------------------------------------------------------------
# GET /risk/dashboard
# -----------------------------------------------------------------------


class TestRiskDashboardEndpoint:
    """Tests for GET /api/v1/risk/dashboard."""

    def test_dashboard_returns_200(self, client: TestClient):
        """GET /risk/dashboard returns HTTP 200."""
        resp = client.get("/api/v1/risk/dashboard")
        assert resp.status_code == 200

    def test_dashboard_has_risk_level(self, client: TestClient):
        """Response contains overall_risk_level."""
        resp = client.get("/api/v1/risk/dashboard")
        data = resp.json()["data"]
        assert "overall_risk_level" in data
        assert data["overall_risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")

    def test_dashboard_has_var(self, client: TestClient):
        """Response contains VaR section."""
        resp = client.get("/api/v1/risk/dashboard")
        data = resp.json()["data"]
        assert "var" in data
        assert isinstance(data["var"], dict)

    def test_dashboard_has_worst_stress(self, client: TestClient):
        """Response contains worst_stress scenario."""
        resp = client.get("/api/v1/risk/dashboard")
        data = resp.json()["data"]
        assert "worst_stress" in data
        assert "scenario_name" in data["worst_stress"]
        assert "pnl_pct" in data["worst_stress"]

    def test_dashboard_has_circuit_breaker(self, client: TestClient):
        """Response contains circuit_breaker status."""
        resp = client.get("/api/v1/risk/dashboard")
        data = resp.json()["data"]
        assert "circuit_breaker" in data
        cb = data["circuit_breaker"]
        assert "state" in cb
        assert "scale" in cb
        assert "drawdown_pct" in cb

    def test_dashboard_has_limits_breached_count(self, client: TestClient):
        """Response contains limits_breached count."""
        resp = client.get("/api/v1/risk/dashboard")
        data = resp.json()["data"]
        assert "limits_breached" in data
        assert isinstance(data["limits_breached"], int)


# -----------------------------------------------------------------------
# GET /risk/report (backward compatibility)
# -----------------------------------------------------------------------


class TestRiskReportBackwardCompat:
    """Tests for GET /api/v1/risk/report (preserved endpoint)."""

    def test_report_returns_200(self, client: TestClient):
        """GET /risk/report still returns HTTP 200."""
        resp = client.get("/api/v1/risk/report")
        assert resp.status_code == 200

    def test_report_has_envelope(self, client: TestClient):
        """Response has status/data/meta envelope."""
        resp = client.get("/api/v1/risk/report")
        body = resp.json()
        assert body["status"] == "ok"
        assert "data" in body
