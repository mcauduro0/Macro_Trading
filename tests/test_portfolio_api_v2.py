"""Tests for enhanced portfolio API endpoints.

Covers:
- GET /portfolio/current returns 200 (backward compat)
- GET /portfolio/target returns 200 with targets list
- GET /portfolio/rebalance-trades returns 200 with trades and should_rebalance
- GET /portfolio/attribution returns 200 with attribution list
- Response envelope format: {status: "ok", data: ..., meta: {timestamp: ...}}
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.portfolio_api import router

# ---------------------------------------------------------------------------
# Mock data returned by patched builder functions
# ---------------------------------------------------------------------------
_MOCK_POSITIONS = [
    {"instrument": "DI1F27", "direction": "LONG", "weight": 0.4, "contributing_strategy_ids": ["RATES_BR_01_CARRY"], "asset_class": "RATES_BR"},
    {"instrument": "USDBRL", "direction": "SHORT", "weight": -0.3, "contributing_strategy_ids": ["FX_BR_01_CARRY"], "asset_class": "FX_BR"},
    {"instrument": "NTN_B_2027", "direction": "LONG", "weight": 0.2, "contributing_strategy_ids": ["INF_BR_01_BREAKEVEN"], "asset_class": "INFLATION_BR"},
]

_MOCK_TARGET_WEIGHTS = {
    "targets": [
        {"instrument": "DI1F27", "direction": "LONG", "target_weight": 0.35, "current_weight": 0.4, "sizing_method": "mean_variance"},
        {"instrument": "USDBRL", "direction": "SHORT", "target_weight": -0.25, "current_weight": -0.3, "sizing_method": "mean_variance"},
        {"instrument": "NTN_B_2027", "direction": "LONG", "target_weight": 0.15, "current_weight": 0.2, "sizing_method": "mean_variance"},
    ],
    "optimization": {
        "method": "black_litterman",
        "regime_clarity": 0.7,
        "constraints": {"min_weight": -1.0, "max_weight": 1.0, "max_leverage": 3.0, "long_only": False},
    },
}

_MOCK_REBALANCE = {
    "trades": [
        {"instrument": "DI1F27", "direction": "SELL", "current_weight": 0.4, "target_weight": 0.35, "trade_weight": -0.05, "trade_notional": -50000.0},
        {"instrument": "USDBRL", "direction": "BUY", "current_weight": -0.3, "target_weight": -0.25, "trade_weight": 0.05, "trade_notional": 50000.0},
    ],
    "should_rebalance": True,
    "trigger_reason": "position_drift",
    "estimated_cost": 50.0,
}

_MOCK_ATTRIBUTION = {
    "attribution": [
        {"instrument": "DI1F27", "strategies": [{"strategy_id": "RATES_BR_01_CARRY", "contribution_weight": 1.0, "contribution_pnl": 15000.0}]},
        {"instrument": "USDBRL", "strategies": [{"strategy_id": "FX_BR_01_CARRY", "contribution_weight": 1.0, "contribution_pnl": -5000.0}]},
    ],
    "total_pnl": 10000.0,
    "by_strategy": {"RATES_BR_01_CARRY": 15000.0, "FX_BR_01_CARRY": -5000.0},
}


@pytest.fixture(autouse=True)
def _mock_portfolio_data():
    """Patch portfolio builder functions so endpoints work without DB."""
    with patch("src.api.routes.portfolio_api._build_portfolio_positions", return_value=_MOCK_POSITIONS), \
         patch("src.api.routes.portfolio_api._build_target_weights", return_value=_MOCK_TARGET_WEIGHTS), \
         patch("src.api.routes.portfolio_api._build_rebalance_trades", return_value=_MOCK_REBALANCE), \
         patch("src.api.routes.portfolio_api._build_attribution", return_value=_MOCK_ATTRIBUTION):
        yield


@pytest.fixture
def client() -> TestClient:
    """TestClient with portfolio router mounted."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests: Backward compatibility
# ---------------------------------------------------------------------------
class TestPortfolioCurrent:
    def test_current_returns_200(self, client: TestClient):
        """GET /portfolio/current returns 200 with positions."""
        response = client.get("/api/v1/portfolio/current")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "data" in data
        assert "meta" in data
        assert "timestamp" in data["meta"]


# ---------------------------------------------------------------------------
# Tests: /portfolio/target
# ---------------------------------------------------------------------------
class TestPortfolioTarget:
    def test_target_returns_200(self, client: TestClient):
        """GET /portfolio/target returns 200 with targets list."""
        response = client.get("/api/v1/portfolio/target")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "targets" in data["data"]
        assert isinstance(data["data"]["targets"], list)
        assert len(data["data"]["targets"]) > 0

    def test_target_has_optimization_metadata(self, client: TestClient):
        """Response includes optimization method and constraints."""
        response = client.get("/api/v1/portfolio/target")
        data = response.json()
        opt = data["data"]["optimization"]
        assert opt["method"] == "black_litterman"
        assert "regime_clarity" in opt
        assert "constraints" in opt

    def test_target_entry_format(self, client: TestClient):
        """Each target entry has required fields."""
        response = client.get("/api/v1/portfolio/target")
        data = response.json()
        target = data["data"]["targets"][0]
        assert "instrument" in target
        assert "direction" in target
        assert "target_weight" in target
        assert "current_weight" in target
        assert "sizing_method" in target


# ---------------------------------------------------------------------------
# Tests: /portfolio/rebalance-trades
# ---------------------------------------------------------------------------
class TestPortfolioRebalanceTrades:
    def test_rebalance_trades_returns_200(self, client: TestClient):
        """GET /portfolio/rebalance-trades returns 200 with trades list."""
        response = client.get("/api/v1/portfolio/rebalance-trades")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "trades" in data["data"]
        assert isinstance(data["data"]["trades"], list)
        assert "should_rebalance" in data["data"]

    def test_rebalance_has_cost_estimate(self, client: TestClient):
        """Response includes estimated transaction cost."""
        response = client.get("/api/v1/portfolio/rebalance-trades")
        data = response.json()
        assert "estimated_cost" in data["data"]
        assert isinstance(data["data"]["estimated_cost"], (int, float))


# ---------------------------------------------------------------------------
# Tests: /portfolio/attribution
# ---------------------------------------------------------------------------
class TestPortfolioAttribution:
    def test_attribution_returns_200(self, client: TestClient):
        """GET /portfolio/attribution returns 200 with attribution list."""
        response = client.get("/api/v1/portfolio/attribution")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "attribution" in data["data"]
        assert isinstance(data["data"]["attribution"], list)

    def test_attribution_has_totals(self, client: TestClient):
        """Response includes total_pnl and by_strategy breakdown."""
        response = client.get("/api/v1/portfolio/attribution")
        data = response.json()
        assert "total_pnl" in data["data"]
        assert "by_strategy" in data["data"]
        assert isinstance(data["data"]["by_strategy"], dict)

    def test_attribution_entry_format(self, client: TestClient):
        """Each attribution entry has instrument and strategies list."""
        response = client.get("/api/v1/portfolio/attribution")
        data = response.json()
        entry = data["data"]["attribution"][0]
        assert "instrument" in entry
        assert "strategies" in entry
        assert isinstance(entry["strategies"], list)
        strat = entry["strategies"][0]
        assert "strategy_id" in strat
        assert "contribution_weight" in strat
        assert "contribution_pnl" in strat


# ---------------------------------------------------------------------------
# Tests: Response envelope
# ---------------------------------------------------------------------------
class TestResponseEnvelope:
    def test_envelope_format_target(self, client: TestClient):
        """Verify envelope format for /target endpoint."""
        response = client.get("/api/v1/portfolio/target")
        data = response.json()
        assert data["status"] == "ok"
        assert "data" in data
        assert "meta" in data
        assert "timestamp" in data["meta"]

    def test_envelope_format_attribution(self, client: TestClient):
        """Verify envelope format for /attribution endpoint."""
        response = client.get("/api/v1/portfolio/attribution")
        data = response.json()
        assert data["status"] == "ok"
        assert "data" in data
        assert "meta" in data
        assert "timestamp" in data["meta"]
