"""Focused unit tests for each v2 API endpoint with mocked dependencies.

Tests verify response structure and data for each new endpoint.
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
# Helpers
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


def _make_report(agent_id: str = "inflation_agent", n_signals: int = 1):
    return AgentReport(
        agent_id=agent_id,
        as_of_date=date(2024, 1, 15),
        generated_at=datetime(2024, 1, 15, 12, 0, 0),
        signals=[_make_signal(f"SIG_{i}", agent_id) for i in range(n_signals)],
        narrative="Test narrative",
    )


# ---------------------------------------------------------------------------
# Test app fixture
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    """TestClient with no DB lifespan."""

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
# 1. Agents list returns 5 agents
# ---------------------------------------------------------------------------
def test_agents_list_returns_5_agents(client):
    """GET /api/v1/agents returns data with 5 agent entries."""
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 5


# ---------------------------------------------------------------------------
# 2. Agent latest returns report with signals
# ---------------------------------------------------------------------------
@patch("src.api.routes.agents._get_agent_instance")
def test_agent_latest_returns_report(mock_get, client):
    """Mock agent run, verify response contains signals list."""
    mock_agent = MagicMock()
    mock_agent.backtest_run.return_value = _make_report("inflation_agent", 3)
    mock_get.return_value = mock_agent

    resp = client.get("/api/v1/agents/inflation_agent/latest")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "signals" in data
    assert len(data["signals"]) == 3
    assert data["agent_id"] == "inflation_agent"


# ---------------------------------------------------------------------------
# 3. Agent run POST triggers execution
# ---------------------------------------------------------------------------
@patch("src.api.routes.agents._get_agent_instance")
def test_agent_run_post(mock_get, client):
    """POST triggers execution and returns report."""
    mock_agent = MagicMock()
    mock_agent.run.return_value = _make_report("monetary_agent", 2)
    mock_get.return_value = mock_agent

    resp = client.post("/api/v1/agents/monetary_agent/run", json={})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["agent_id"] == "monetary_agent"
    assert len(data["signals"]) == 2


# ---------------------------------------------------------------------------
# 4. Signals latest has consensus
# ---------------------------------------------------------------------------
@patch("src.api.routes.agents._get_agent_instance")
def test_signals_latest_has_consensus(mock_get, client):
    """Verify consensus field in response."""
    mock_agent = MagicMock()
    mock_agent.backtest_run.return_value = _make_report("inflation_agent", 2)
    mock_get.return_value = mock_agent

    resp = client.get("/api/v1/signals/latest")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "consensus" in data
    assert "signals" in data


# ---------------------------------------------------------------------------
# 5. Strategies list returns 8
# ---------------------------------------------------------------------------
def test_strategies_list_returns_8(client):
    """GET /api/v1/strategies returns 24 strategies."""
    resp = client.get("/api/v1/strategies")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 24


# ---------------------------------------------------------------------------
# 6. Strategy backtest returns metrics
# ---------------------------------------------------------------------------
@patch("src.api.routes.strategies_api._fetch_backtest_result", new_callable=AsyncMock)
def test_strategy_backtest_returns_metrics(mock_fetch, client):
    """Verify sharpe_ratio, max_drawdown fields."""
    mock_fetch.return_value = {
        "strategy_id": "RATES_BR_01",
        "sharpe_ratio": 1.5,
        "annual_return": 0.12,
        "max_drawdown": -0.08,
        "win_rate": 0.55,
        "profit_factor": 1.8,
        "equity_curve": [],
    }

    resp = client.get("/api/v1/strategies/RATES_BR_01/backtest")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "sharpe_ratio" in data
    assert "max_drawdown" in data
    assert data["sharpe_ratio"] == 1.5


# ---------------------------------------------------------------------------
# 7. Portfolio current has positions
# ---------------------------------------------------------------------------
@patch("src.api.routes.portfolio_api._build_portfolio_positions")
def test_portfolio_current_has_positions(mock_build, client):
    """Verify positions list in response."""
    mock_build.return_value = [
        {
            "instrument": "DI_PRE_365",
            "direction": "LONG",
            "weight": 0.15,
            "contributing_strategy_ids": ["RATES_BR_01"],
            "asset_class": "FIXED_INCOME",
        }
    ]

    resp = client.get("/api/v1/portfolio/current")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "positions" in data
    assert len(data["positions"]) == 1
    assert "summary" in data
    assert data["summary"]["total_positions"] == 1


# ---------------------------------------------------------------------------
# 8. Portfolio risk has VaR
# ---------------------------------------------------------------------------
@patch("src.api.routes.portfolio_api._build_risk_report")
def test_portfolio_risk_has_var(mock_risk, client):
    """Verify var_95 field equivalent in response."""
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
    data = resp.json()["data"]
    assert "var" in data
    assert "historical" in data["var"]
    assert "var_95" in data["var"]["historical"]


# ---------------------------------------------------------------------------
# 9. Daily brief has content
# ---------------------------------------------------------------------------
@patch("src.api.routes.reports._generate_brief")
def test_daily_brief_has_content(mock_gen, client):
    """Verify content and source fields."""
    from src.narrative.generator import NarrativeBrief

    mock_gen.return_value = NarrativeBrief(
        content="Test daily brief content for the trading desk.",
        source="template",
        model=None,
        as_of_date=date(2024, 1, 15),
        generated_at=datetime(2024, 1, 15, 12, 0, 0),
    )

    resp = client.get("/api/v1/reports/daily-brief")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "content" in data
    assert "source" in data
    assert data["source"] == "template"
    assert len(data["content"]) > 0


# ---------------------------------------------------------------------------
# 10. Date parameter parsing
# ---------------------------------------------------------------------------
@patch("src.api.routes.agents._get_agent_instance")
def test_date_parameter_parsing(mock_get, client):
    """?date=2024-01-15 is correctly parsed and passed."""
    mock_agent = MagicMock()
    report = _make_report("inflation_agent")
    mock_agent.backtest_run.return_value = report
    mock_get.return_value = mock_agent

    resp = client.get("/api/v1/agents/inflation_agent/latest?date=2024-01-15")
    assert resp.status_code == 200

    # Verify the agent was called with the correct date
    call_args = mock_agent.backtest_run.call_args
    assert call_args[0][0] == date(2024, 1, 15)
