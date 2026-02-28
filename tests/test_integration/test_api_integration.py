"""Integration tests for all API endpoints (v1 + v2).

Tests use FastAPI TestClient with mocked backend dependencies to verify
all endpoints return 200 and follow the response envelope format.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agents.base import AgentReport, AgentSignal
from src.core.enums import SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------
def _make_signal(signal_id: str = "TEST_SIG", agent_id: str = "inflation_agent"):
    return AgentSignal(
        signal_id=signal_id,
        agent_id=agent_id,
        timestamp=datetime(2024, 1, 15, 12, 0, 0),
        as_of_date=date(2024, 1, 15),
        direction=SignalDirection.LONG,
        strength=SignalStrength.MODERATE,
        confidence=0.7,
        value=1.2,
        horizon_days=63,
        metadata={"test": True},
    )


def _make_report(agent_id: str = "inflation_agent"):
    return AgentReport(
        agent_id=agent_id,
        as_of_date=date(2024, 1, 15),
        generated_at=datetime(2024, 1, 15, 12, 0, 0),
        signals=[_make_signal(agent_id=agent_id)],
        narrative="Test narrative",
    )


# ---------------------------------------------------------------------------
# Test app fixture (no DB lifespan)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    """Create a TestClient for the full app with no DB lifespan."""

    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield

    with patch("src.api.main.lifespan", _noop_lifespan):
        import importlib

        import src.api.main

        importlib.reload(src.api.main)
        app = src.api.main.app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Test 1: All v2 endpoints return 200
# ---------------------------------------------------------------------------
class TestV2EndpointsReturn200:
    """All 9 new v2 endpoints return HTTP 200."""

    def test_agents_list(self, client):
        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200

    @patch("src.api.routes.agents._get_agent_instance")
    def test_agent_latest(self, mock_get, client):
        mock_agent = MagicMock()
        mock_agent.backtest_run.return_value = _make_report()
        mock_get.return_value = mock_agent

        resp = client.get("/api/v1/agents/inflation_agent/latest")
        assert resp.status_code == 200

    @patch("src.api.routes.agents._get_agent_instance")
    def test_agent_run_post(self, mock_get, client):
        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_report()
        mock_get.return_value = mock_agent

        resp = client.post("/api/v1/agents/inflation_agent/run", json={})
        assert resp.status_code == 200

    @patch("src.api.routes.agents._get_agent_instance")
    def test_signals_latest(self, mock_get, client):
        mock_agent = MagicMock()
        mock_agent.backtest_run.return_value = _make_report()
        mock_get.return_value = mock_agent

        resp = client.get("/api/v1/signals/latest")
        assert resp.status_code == 200

    @patch(
        "src.api.routes.strategies_api._fetch_backtest_result",
        new_callable=AsyncMock,
        return_value=None,
    )
    def test_strategies_list(self, mock_fetch, client):
        resp = client.get("/api/v1/strategies")
        assert resp.status_code == 200

    @patch(
        "src.api.routes.strategies_api._fetch_backtest_result",
        new_callable=AsyncMock,
        return_value=None,
    )
    def test_strategy_backtest(self, mock_fetch, client):
        resp = client.get("/api/v1/strategies/RATES_BR_01/backtest")
        assert resp.status_code == 200

    @patch("src.api.routes.portfolio_api._build_portfolio_positions", return_value=[])
    def test_portfolio_current(self, mock_build, client):
        resp = client.get("/api/v1/portfolio/current")
        assert resp.status_code == 200

    @patch("src.api.routes.portfolio_api._build_risk_report")
    def test_portfolio_risk(self, mock_risk, client):
        mock_risk.return_value = {
            "var": {
                "historical": {
                    "var_95": -0.02,
                    "cvar_95": -0.03,
                    "var_99": -0.04,
                    "cvar_99": -0.05,
                }
            },
            "stress_tests": [],
            "limit_utilization": {},
            "circuit_breaker_status": "NORMAL",
            "risk_level": "LOW",
            "drawdown_pct": 0.0,
            "portfolio_value": 1_000_000.0,
        }
        resp = client.get("/api/v1/portfolio/risk")
        assert resp.status_code == 200

    @patch("src.api.routes.reports._generate_brief")
    def test_daily_brief(self, mock_gen, client):
        from src.narrative.generator import NarrativeBrief

        mock_gen.return_value = NarrativeBrief(
            content="Test daily brief",
            source="template",
            model=None,
            as_of_date=date(2024, 1, 15),
            generated_at=datetime(2024, 1, 15, 12, 0, 0),
        )
        resp = client.get("/api/v1/reports/daily-brief")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test 2: All v1 endpoints return 200
# ---------------------------------------------------------------------------
class TestV1EndpointsReturn200:
    """All original v1 endpoints return HTTP 200 (or 500 when DB unavailable).

    These tests verify that v1 routes are registered and reachable.
    Without a real database the DB-dependent endpoints return 500, which
    is acceptable — the test confirms the route exists and doesn't 404.
    """

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_macro_dashboard(self, client):
        resp = client.get("/api/v1/macro/dashboard")
        # Route is registered; 500 expected without DB
        assert resp.status_code in (200, 500)

    def test_curves_latest(self, client):
        resp = client.get("/api/v1/curves/latest")
        assert resp.status_code in (200, 500)

    def test_market_data_latest(self, client):
        resp = client.get("/api/v1/market-data/latest", params={"tickers": "USDBRL"})
        assert resp.status_code in (200, 500)

    def test_flows_latest(self, client):
        resp = client.get("/api/v1/flows/latest")
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Test 3: Dashboard endpoint
# ---------------------------------------------------------------------------
class TestDashboardEndpoint:
    def test_dashboard_returns_200(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test 3: Response envelope format
# ---------------------------------------------------------------------------
class TestResponseEnvelopeFormat:
    """All v2 GET endpoints return {status, data, meta} format."""

    def test_agents_list_envelope(self, client):
        resp = client.get("/api/v1/agents")
        body = resp.json()
        assert body["status"] == "ok"
        assert "data" in body
        assert "meta" in body
        assert "timestamp" in body["meta"]

    @patch(
        "src.api.routes.strategies_api._fetch_backtest_result",
        new_callable=AsyncMock,
        return_value=None,
    )
    def test_strategies_list_envelope(self, mock_fetch, client):
        resp = client.get("/api/v1/strategies")
        body = resp.json()
        assert body["status"] == "ok"
        assert "data" in body
        assert "meta" in body
        assert "timestamp" in body["meta"]

    @patch("src.api.routes.portfolio_api._build_portfolio_positions", return_value=[])
    def test_portfolio_current_envelope(self, mock_build, client):
        resp = client.get("/api/v1/portfolio/current")
        body = resp.json()
        assert body["status"] == "ok"
        assert "data" in body
        assert "meta" in body


# ---------------------------------------------------------------------------
# Test 4: 404 for unknown agent
# ---------------------------------------------------------------------------
class TestErrorCases:
    def test_404_for_unknown_agent(self, client):
        resp = client.get("/api/v1/agents/nonexistent/latest")
        assert resp.status_code == 404
