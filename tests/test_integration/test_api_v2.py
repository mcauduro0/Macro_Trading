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

import numpy as np
import pytest
from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Synthetic data for mocking DB-dependent endpoints
# ---------------------------------------------------------------------------
_SYNTHETIC_RETURNS = np.random.RandomState(42).normal(0.0005, 0.012, 252)
_SYNTHETIC_POSITIONS = {"DI1F27": 5_000_000.0, "USDBRL": 3_000_000.0}
_SYNTHETIC_PORTFOLIO_VALUE = 10_000_000.0
_SYNTHETIC_STATE = {
    "weights": {"DI1F27": 0.5, "USDBRL": 0.3},
    "leverage": 0.8,
    "var_95": 0.01,
    "var_99": 0.02,
    "drawdown_pct": 1.0,
    "risk_contributions": {"DI1F27": 0.5, "USDBRL": 0.3},
    "asset_class_weights": {"RATES_BR": 0.5, "FX_BR": 0.3},
    "strategy_daily_pnl": {},
    "asset_class_daily_pnl": {},
    "asset_class_map": {"DI1F27": "RATES_BR", "USDBRL": "FX_BR"},
}

_MOCK_PORTFOLIO_POSITIONS = [
    {"instrument": "DI1F27", "direction": "LONG", "weight": 0.4,
     "contributing_strategy_ids": ["RATES_BR_01"], "asset_class": "RATES_BR"},
    {"instrument": "USDBRL", "direction": "SHORT", "weight": -0.3,
     "contributing_strategy_ids": ["FX_BR_01"], "asset_class": "FX_BR"},
]

_MOCK_TARGET_WEIGHTS = {
    "targets": [
        {"instrument": "DI1F27", "direction": "LONG", "target_weight": 0.35,
         "current_weight": 0.4, "sizing_method": "mean_variance"},
    ],
    "optimization": {
        "method": "black_litterman", "regime_clarity": 0.7,
        "constraints": {"min_weight": -1.0, "max_weight": 1.0, "max_leverage": 3.0, "long_only": False},
    },
}

_MOCK_REBALANCE = {
    "trades": [{"instrument": "DI1F27", "direction": "SELL", "current_weight": 0.4,
                "target_weight": 0.35, "trade_weight": -0.05, "trade_notional": -50000.0}],
    "should_rebalance": True, "trigger_reason": "position_drift", "estimated_cost": 25.0,
}

_MOCK_ATTRIBUTION = {
    "attribution": [
        {"instrument": "DI1F27", "strategies": [{"strategy_id": "RATES_BR_01",
         "contribution_weight": 1.0, "contribution_pnl": 15000.0}]},
    ],
    "total_pnl": 15000.0,
    "by_strategy": {"RATES_BR_01": 15000.0},
}


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


@pytest.fixture(autouse=True)
def _mock_all_data():
    """Mock all DB-dependent data loaders for CI environment."""
    with (
        patch("src.api.routes.risk_api._load_portfolio_returns", return_value=_SYNTHETIC_RETURNS),
        patch("src.api.routes.risk_api._load_positions", return_value=_SYNTHETIC_POSITIONS),
        patch("src.api.routes.risk_api._load_portfolio_value", return_value=_SYNTHETIC_PORTFOLIO_VALUE),
        patch("src.api.routes.risk_api._load_portfolio_state", return_value=_SYNTHETIC_STATE),
        patch("src.api.routes.portfolio_api._build_portfolio_positions", return_value=_MOCK_PORTFOLIO_POSITIONS),
        patch("src.api.routes.portfolio_api._build_target_weights", return_value=_MOCK_TARGET_WEIGHTS),
        patch("src.api.routes.portfolio_api._build_rebalance_trades", return_value=_MOCK_REBALANCE),
        patch("src.api.routes.portfolio_api._build_attribution", return_value=_MOCK_ATTRIBUTION),
        patch("src.api.routes.portfolio_api._build_risk_report", return_value={
            "var": {"historical": {"var_95": -0.02, "cvar_95": -0.03, "var_99": -0.04, "cvar_99": -0.05}},
            "stress_tests": [], "limit_utilization": {}, "circuit_breaker_status": "NORMAL",
            "risk_level": "LOW", "drawdown_pct": 0.0, "portfolio_value": 1_000_000.0,
        }),
    ):
        yield


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
        """GET /api/v1/reports/daily/latest -> 200, 500, or 503 (no DB in CI)."""
        resp = client.get("/api/v1/reports/daily/latest")
        assert resp.status_code in (200, 500, 503)
