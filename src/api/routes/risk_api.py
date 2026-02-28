"""Risk API endpoints for VaR, stress testing, limits, and dashboard.

Provides:
- GET /risk/var       -- VaR/CVaR at 95% and 99% for all methods
- GET /risk/stress    -- Stress scenario results (6 scenarios)
- GET /risk/limits    -- Current limit utilization and breach status
- GET /risk/dashboard -- Aggregated risk overview
- GET /risk/report    -- Backward-compatible portfolio risk report
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk", tags=["Risk"])


# ---------------------------------------------------------------------------
# Response envelope (consistent with existing v2 endpoints)
# ---------------------------------------------------------------------------


def _envelope(data: Any) -> dict:
    return {
        "status": "ok",
        "data": data,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
    }


def _error_response(message: str) -> dict:
    return {
        "status": "error",
        "error": message,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
    }


# ---------------------------------------------------------------------------
# Helpers: build sample data for computation
# ---------------------------------------------------------------------------


def _sample_portfolio_returns() -> np.ndarray:
    """Generate sample portfolio returns for VaR computation.

    In production this would pull from the database. For now returns
    a deterministic synthetic series with realistic properties.
    """
    rng = np.random.default_rng(seed=42)
    # 252 days of daily returns with ~15% annualized vol
    daily_vol = 0.15 / np.sqrt(252)
    returns = rng.normal(loc=0.0003, scale=daily_vol, size=252)
    return returns


def _sample_positions() -> dict[str, float]:
    """Build sample positions for stress testing."""
    return {
        "USDBRL": 200_000.0,
        "DI_PRE_360": 300_000.0,
        "NTN_B_REAL": 250_000.0,
        "IBOVESPA": 150_000.0,
        "SP500": 100_000.0,
    }


def _sample_portfolio_value() -> float:
    return 1_000_000.0


# ---------------------------------------------------------------------------
# GET /risk/var
# ---------------------------------------------------------------------------


@router.get("/var")
async def risk_var(
    method: Optional[str] = Query(
        "all",
        description="VaR method: historical, parametric, monte_carlo, or all",
    ),
    confidence: Optional[int] = Query(
        None,
        description="Confidence level: 95 or 99 (default: both reported)",
    ),
):
    """Return VaR and CVaR at 95% and 99% confidence levels.

    When method='all', returns results for historical, parametric, and
    monte_carlo methods. A single method can be selected to narrow output.
    """
    try:
        from src.risk.var_calculator import VaRCalculator

        def _compute_var():
            calc = VaRCalculator()
            returns = _sample_portfolio_returns()

            valid_methods = {"historical", "parametric", "monte_carlo", "all"}
            selected = method if method in valid_methods else "all"

            results: dict[str, dict] = {}
            warning = None

            if selected in ("historical", "all"):
                vr = calc.calculate(returns, "historical")
                results["historical"] = {
                    "method": "historical",
                    "var_95": round(vr.var_95, 6),
                    "var_99": round(vr.var_99, 6),
                    "cvar_95": round(vr.cvar_95, 6),
                    "cvar_99": round(vr.cvar_99, 6),
                    "n_observations": vr.n_observations,
                }
                if vr.confidence_warning:
                    warning = vr.confidence_warning

            if selected in ("parametric", "all"):
                vr = calc.calculate(returns, "parametric")
                results["parametric"] = {
                    "method": "parametric",
                    "var_95": round(vr.var_95, 6),
                    "var_99": round(vr.var_99, 6),
                    "cvar_95": round(vr.cvar_95, 6),
                    "cvar_99": round(vr.cvar_99, 6),
                    "n_observations": vr.n_observations,
                }

            if selected in ("monte_carlo", "all"):
                # Build a simple returns matrix for Monte Carlo
                rng = np.random.default_rng(seed=42)
                n_assets = 3
                n_obs = 252
                daily_vol = 0.15 / np.sqrt(252)
                returns_matrix = rng.normal(
                    loc=0.0003, scale=daily_vol, size=(n_obs, n_assets)
                )
                weights = np.array([0.4, 0.35, 0.25])

                vr = calc.calculate_monte_carlo(returns_matrix, weights, rng=rng)
                results["monte_carlo"] = {
                    "method": "monte_carlo",
                    "var_95": round(vr.var_95, 6),
                    "var_99": round(vr.var_99, 6),
                    "cvar_95": round(vr.cvar_95, 6),
                    "cvar_99": round(vr.cvar_99, 6),
                    "n_observations": vr.n_observations,
                }

            output: dict[str, Any] = {"results": results}
            if warning:
                output["warning"] = warning
            if selected != "all":
                # For a single method, flatten to just that result
                output["results"] = results.get(selected, {})

            return output

        data = await asyncio.to_thread(_compute_var)
        return _envelope(data)

    except Exception as exc:
        logger.error("risk_api error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# GET /risk/stress
# ---------------------------------------------------------------------------


@router.get("/stress")
async def risk_stress(
    scenario: Optional[str] = Query(
        None,
        description="Filter by scenario name (optional)",
    ),
):
    """Return stress test results for all 6 scenarios (or a filtered one)."""
    try:
        from src.risk.stress_tester import StressTester

        def _compute_stress():
            tester = StressTester()
            positions = _sample_positions()
            portfolio_value = _sample_portfolio_value()

            all_results = tester.run_all(positions, portfolio_value)

            scenarios_out = []
            for sr in all_results:
                entry = {
                    "scenario_name": sr.scenario_name,
                    "portfolio_pnl": round(sr.portfolio_pnl, 2),
                    "portfolio_pnl_pct": round(sr.portfolio_pnl_pct, 6),
                    "worst_position": sr.worst_position,
                    "positions_impacted": sr.positions_impacted,
                }
                scenarios_out.append(entry)

            # If specific scenario requested, filter
            if scenario:
                scenario_lower = scenario.lower()
                scenarios_out = [
                    s
                    for s in scenarios_out
                    if scenario_lower in s["scenario_name"].lower()
                ]

            return {"scenarios": scenarios_out}

        data = await asyncio.to_thread(_compute_stress)
        return _envelope(data)

    except Exception as exc:
        logger.error("risk_api error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# GET /risk/limits
# ---------------------------------------------------------------------------


@router.get("/limits")
async def risk_limits():
    """Return current limit utilization and breach status."""
    try:
        from src.risk.risk_limits_v2 import RiskLimitsManager

        def _compute_limits():
            mgr = RiskLimitsManager()

            # Build a portfolio state for limit checking
            portfolio_state = {
                "weights": {
                    "USDBRL": 0.20,
                    "DI_PRE": 0.30,
                    "IBOV": 0.15,
                    "SP500": 0.10,
                },
                "leverage": 0.75,
                "var_95": -0.015,
                "var_99": -0.025,
                "drawdown_pct": 0.008,
                "risk_contributions": {
                    "USDBRL": 0.10,
                    "DI_PRE": 0.15,
                    "IBOV": 0.08,
                    "SP500": 0.05,
                },
                "asset_class_weights": {"FX": 0.20, "RATES": 0.30, "EQUITY": 0.25},
                "strategy_daily_pnl": {"FX_BR_01": -0.003, "RATES_BR_01": 0.002},
                "asset_class_daily_pnl": {
                    "FX": -0.003,
                    "RATES": 0.002,
                    "EQUITY": -0.001,
                },
                "asset_class_map": {
                    "USDBRL": "FX",
                    "DI_PRE": "RATES",
                    "IBOV": "EQUITY",
                    "SP500": "EQUITY",
                },
            }

            result = mgr.check_all_v2(portfolio_state)

            # Serialize limit results
            limits_out = []
            for lr in result["limit_results"]:
                limits_out.append(
                    {
                        "limit_name": lr.limit_name,
                        "limit_value": lr.limit_value,
                        "current_value": lr.current_value,
                        "utilization_pct": round(lr.utilization_pct, 2),
                        "breached": lr.breached,
                    }
                )

            # Loss status
            loss_status = None
            ls = result.get("loss_status")
            if ls is not None:
                loss_status = {
                    "daily_pnl": ls.daily_pnl,
                    "weekly_pnl": ls.cumulative_weekly_pnl,
                    "daily_breached": ls.breach_daily,
                    "weekly_breached": ls.breach_weekly,
                }

            # Risk budget
            risk_budget = None
            rb = result.get("risk_budget")
            if rb is not None:
                risk_budget = {
                    "total": rb.total_risk_budget,
                    "allocated": rb.allocated_risk,
                    "available": rb.available_risk_budget,
                    "utilization_pct": rb.utilization_pct,
                }

            return {
                "limits": limits_out,
                "loss_status": loss_status,
                "risk_budget": risk_budget,
                "overall_status": result["overall_status"],
            }

        data = await asyncio.to_thread(_compute_limits)
        return _envelope(data)

    except Exception as exc:
        logger.error("risk_api error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# GET /risk/dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
async def risk_dashboard():
    """Return aggregated risk overview combining VaR, stress, limits, and circuit breaker."""
    try:
        from src.risk.risk_monitor import RiskMonitor

        def _compute_dashboard():
            monitor = RiskMonitor()
            portfolio_returns = _sample_portfolio_returns()
            positions = _sample_positions()
            portfolio_value = _sample_portfolio_value()
            weights = {k: v / portfolio_value for k, v in positions.items()}

            report = monitor.generate_report(
                portfolio_returns=portfolio_returns,
                positions=positions,
                portfolio_value=portfolio_value,
                weights=weights,
            )

            # Serialize VaR
            var_data: dict[str, dict] = {}
            for method_name, vr in report.var_results.items():
                var_data[method_name] = {
                    "var_95": round(vr.var_95, 6),
                    "cvar_95": round(vr.cvar_95, 6),
                    "var_99": round(vr.var_99, 6),
                    "cvar_99": round(vr.cvar_99, 6),
                }

            # Worst stress scenario
            worst_stress: dict[str, Any] = {}
            if report.stress_results:
                worst = min(report.stress_results, key=lambda s: s.portfolio_pnl)
                worst_stress = {
                    "scenario_name": worst.scenario_name,
                    "pnl_pct": round(worst.portfolio_pnl_pct, 6),
                }

            # Count breached limits
            limits_breached = sum(1 for lr in report.limit_results if lr.breached)

            return {
                "overall_risk_level": report.overall_risk_level,
                "portfolio_value": report.portfolio_value,
                "var": var_data,
                "worst_stress": worst_stress,
                "limits_breached": limits_breached,
                "circuit_breaker": {
                    "state": report.circuit_breaker_state.value,
                    "scale": report.circuit_breaker_scale,
                    "drawdown_pct": round(report.drawdown_pct, 6),
                },
            }

        data = await asyncio.to_thread(_compute_dashboard)
        return _envelope(data)

    except Exception as exc:
        logger.error("risk_api error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# GET /risk/report  (backward compatibility)
# ---------------------------------------------------------------------------


@router.get("/report")
async def risk_report(
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
):
    """Return portfolio risk report (VaR, stress tests, limits).

    Preserved for backward compatibility. Delegates to portfolio_api._build_risk_report.
    """
    try:
        from src.api.routes.portfolio_api import _build_risk_report

        risk_data = await asyncio.to_thread(_build_risk_report)
        return _envelope(risk_data)
    except Exception as exc:
        logger.error("risk_api error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")
