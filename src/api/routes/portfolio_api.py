"""Portfolio management endpoints.

Provides:
- GET /portfolio/current — consolidated portfolio positions
- GET /portfolio/risk    — risk report (VaR, CVaR, stress tests)
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------
def _envelope(data: Any) -> dict:
    return {
        "status": "ok",
        "data": data,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
    }


# ---------------------------------------------------------------------------
# GET /api/v1/portfolio/current
# ---------------------------------------------------------------------------
@router.get("/current")
async def portfolio_current(
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
):
    """Return consolidated portfolio positions."""
    from datetime import date as date_type

    as_of = date_type.today()
    if date:
        try:
            as_of = date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {date}")

    try:
        positions = await asyncio.to_thread(_build_portfolio_positions, as_of)
        total_positions = len(positions)
        gross_leverage = sum(abs(p["weight"]) for p in positions)
        net_leverage = sum(p["weight"] for p in positions)

        return _envelope({
            "positions": positions,
            "summary": {
                "total_positions": total_positions,
                "net_leverage": round(net_leverage, 4),
                "gross_leverage": round(gross_leverage, 4),
            },
            "as_of_date": str(as_of),
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _build_portfolio_positions(as_of: date) -> list[dict]:
    """Build portfolio positions from strategy signals."""
    from src.strategies import ALL_STRATEGIES

    positions: list[dict] = []
    for strategy_id, strategy_cls in ALL_STRATEGIES.items():
        try:
            strategy = strategy_cls()
            strat_positions = strategy.generate_signals(as_of)
            for pos in strat_positions:
                direction = pos.direction.value if hasattr(pos.direction, "value") else str(pos.direction)
                asset_class = strategy.config.asset_class.value if hasattr(strategy.config.asset_class, "value") else str(strategy.config.asset_class)
                positions.append({
                    "instrument": pos.instrument,
                    "direction": direction,
                    "weight": round(pos.weight, 6),
                    "contributing_strategy_ids": [strategy_id],
                    "asset_class": asset_class,
                })
        except Exception:
            pass

    return positions


# ---------------------------------------------------------------------------
# GET /api/v1/portfolio/risk
# ---------------------------------------------------------------------------
@router.get("/risk")
async def portfolio_risk(
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
):
    """Return risk report: VaR, CVaR, stress tests, limits."""
    try:
        risk_data = await asyncio.to_thread(_build_risk_report)
        return _envelope(risk_data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _build_risk_report() -> dict:
    """Generate risk report using RiskMonitor."""
    from src.risk.risk_monitor import RiskMonitor

    monitor = RiskMonitor()
    portfolio_returns = np.array([0.001, -0.002, 0.0015, -0.001, 0.0005])
    positions: dict[str, float] = {}
    weights: dict[str, float] = {}
    portfolio_value = 1_000_000.0

    report = monitor.generate_report(
        portfolio_returns=portfolio_returns,
        positions=positions,
        portfolio_value=portfolio_value,
        weights=weights,
    )

    # Serialize VaR results
    var_data = {}
    for method, var_result in report.var_results.items():
        var_data[method] = {
            "var_95": round(var_result.var_95, 6),
            "cvar_95": round(var_result.cvar_95, 6),
            "var_99": round(var_result.var_99, 6),
            "cvar_99": round(var_result.cvar_99, 6),
        }

    # Serialize stress results
    stress_data = []
    for sr in report.stress_results:
        stress_data.append({
            "scenario_name": sr.scenario_name,
            "portfolio_pnl": round(sr.portfolio_pnl, 2),
            "portfolio_pnl_pct": round(sr.portfolio_pnl_pct, 6),
        })

    # Limit utilization
    limit_util = {}
    for lr in report.limit_results:
        limit_util[lr.limit_name] = round(lr.utilization_pct, 2)

    return {
        "var": var_data,
        "stress_tests": stress_data,
        "limit_utilization": limit_util,
        "circuit_breaker_status": report.circuit_breaker_state.value,
        "risk_level": report.overall_risk_level,
        "drawdown_pct": round(report.drawdown_pct, 6),
        "portfolio_value": portfolio_value,
    }
