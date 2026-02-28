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
# Data loaders: fetch real portfolio data from PMS and database
# ---------------------------------------------------------------------------


def _load_portfolio_returns() -> np.ndarray:
    """Load historical portfolio returns from the database.

    Queries TimescaleDB for daily portfolio returns over the last 252 trading
    days. Raises RuntimeError if data is unavailable.
    """
    try:
        from sqlalchemy import create_engine, text

        from src.core.config import get_settings

        settings = get_settings()
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT daily_return FROM portfolio_returns "
                    "ORDER BY return_date DESC LIMIT 252"
                )
            )
            rows = result.fetchall()
            if rows and len(rows) >= 30:
                return np.array([float(r[0]) for r in reversed(rows)])
    except Exception:
        pass

    # Fallback: compute from market data positions
    try:
        from src.pms.position_manager import PositionManager

        pm = PositionManager()
        book = pm.get_book()
        positions = book.get("positions", [])
        if positions:
            # Use position weights with historical asset returns
            weights = {p["instrument"]: p.get("weight", 0.0) for p in positions}
            if weights:
                import pandas as pd
                from datetime import date as date_type
                from src.agents.data_loader import PointInTimeDataLoader

                loader = PointInTimeDataLoader()
                returns_frames = []
                for ticker in list(weights.keys()):
                    try:
                        md = loader.get_market_data(ticker, as_of_date=date_type.today(), lookback_days=252)
                        if md is not None and not md.empty and "close" in md.columns:
                            ret = md["close"].pct_change().dropna()
                            ret.name = ticker
                            returns_frames.append(ret)
                    except Exception:
                        continue
                if returns_frames:
                    returns_data = pd.concat(returns_frames, axis=1).dropna()
                    if len(returns_data) >= 30:
                        w = np.array([weights.get(col, 0.0) for col in returns_data.columns])
                        portfolio_returns = returns_data.values @ w
                        return portfolio_returns
    except Exception:
        pass

    raise RuntimeError(
        "Portfolio returns unavailable. Ensure database is running and "
        "portfolio_returns table is populated, or PMS has active positions "
        "with historical market data."
    )


def _load_positions() -> dict[str, float]:
    """Load current positions from the Position Manager.

    Returns dict of {instrument: notional_value}. Raises RuntimeError if
    PMS is unavailable or has no positions.
    """
    try:
        from src.pms.position_manager import PositionManager

        pm = PositionManager()
        book = pm.get_book()
        positions = book.get("positions", [])
        if positions:
            return {
                p["instrument"]: p.get("notional", p.get("weight", 0.0) * 1_000_000.0)
                for p in positions
            }
    except Exception:
        pass

    raise RuntimeError(
        "Position data unavailable. Ensure PositionManager is configured "
        "with active positions from the trade workflow."
    )


def _load_portfolio_value() -> float:
    """Load current portfolio NAV from PMS.

    Returns total portfolio value in BRL. Raises RuntimeError if unavailable.
    """
    try:
        from src.pms.position_manager import PositionManager

        pm = PositionManager()
        book = pm.get_book()
        summary = book.get("summary", {})
        nav = summary.get("total_nav_brl", summary.get("total_market_value", 0.0))
        if nav > 0:
            return float(nav)
    except Exception:
        pass

    raise RuntimeError(
        "Portfolio NAV unavailable. Ensure PositionManager is configured "
        "and positions have been marked to market."
    )


def _load_portfolio_state() -> dict:
    """Load full portfolio state for risk limit checking.

    Returns dict with weights, leverage, VaR, drawdown, risk contributions,
    and asset class mappings. Raises RuntimeError if unavailable.
    """
    try:
        from src.pms.position_manager import PositionManager

        pm = PositionManager()
        book = pm.get_book()
        positions = book.get("positions", [])
        summary = book.get("summary", {})

        if not positions:
            raise RuntimeError("No positions in book")

        weights = {p["instrument"]: p.get("weight", 0.0) for p in positions}
        risk_contributions = {p["instrument"]: abs(p.get("weight", 0.0)) for p in positions}
        asset_class_map = {p["instrument"]: p.get("asset_class", "OTHER") for p in positions}

        # Aggregate asset class weights
        ac_weights: dict[str, float] = {}
        for inst, w in weights.items():
            ac = asset_class_map.get(inst, "OTHER")
            ac_weights[ac] = ac_weights.get(ac, 0.0) + abs(w)

        return {
            "weights": weights,
            "leverage": summary.get("leverage", sum(abs(w) for w in weights.values())),
            "var_95": summary.get("var_95", 0.0),
            "var_99": summary.get("var_99", 0.0),
            "drawdown_pct": summary.get("drawdown_pct", 0.0),
            "risk_contributions": risk_contributions,
            "asset_class_weights": ac_weights,
            "strategy_daily_pnl": summary.get("strategy_daily_pnl", {}),
            "asset_class_daily_pnl": summary.get("asset_class_daily_pnl", {}),
            "asset_class_map": asset_class_map,
        }
    except Exception as exc:
        raise RuntimeError(
            f"Portfolio state unavailable for limit checking: {exc}. "
            "Ensure PositionManager has active positions."
        ) from exc


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
            returns = _load_portfolio_returns()

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
                # Build real returns matrix from portfolio positions
                positions = _load_positions()
                instruments = list(positions.keys())
                from src.agents.data_loader import PointInTimeDataLoader

                loader = PointInTimeDataLoader()
                import pandas as pd
                from datetime import date as date_type
                returns_frames = []
                for ticker in instruments:
                    try:
                        md = loader.get_market_data(ticker, as_of_date=date_type.today(), lookback_days=252)
                        if md is not None and not md.empty and "close" in md.columns:
                            ret = md["close"].pct_change().dropna()
                            ret.name = ticker
                            returns_frames.append(ret)
                    except Exception:
                        continue
                returns_df = pd.concat(returns_frames, axis=1).dropna() if returns_frames else None
                if returns_df is not None and len(returns_df) >= 30:
                    returns_matrix = returns_df.values
                    total = sum(positions.values())
                    weights = np.array([positions[i] / total for i in instruments])
                else:
                    # Use portfolio-level returns as single-asset fallback
                    returns_matrix = returns.reshape(-1, 1)
                    weights = np.array([1.0])

                vr = calc.calculate_monte_carlo(returns_matrix, weights)
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
                output["results"] = results.get(selected, {})

            return output

        data = await asyncio.to_thread(_compute_var)
        return _envelope(data)

    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("risk_var error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"VaR computation failed: {exc}")


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
            positions = _load_positions()
            portfolio_value = _load_portfolio_value()

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

    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("risk_stress error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stress test failed: {exc}")


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
            portfolio_state = _load_portfolio_state()
            result = mgr.check_all_v2(portfolio_state)

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

            loss_status = None
            ls = result.get("loss_status")
            if ls is not None:
                loss_status = {
                    "daily_pnl": ls.daily_pnl,
                    "weekly_pnl": ls.cumulative_weekly_pnl,
                    "daily_breached": ls.breach_daily,
                    "weekly_breached": ls.breach_weekly,
                }

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

    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("risk_limits error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Limit check failed: {exc}")


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
            portfolio_returns = _load_portfolio_returns()
            positions = _load_positions()
            portfolio_value = _load_portfolio_value()
            weights = {k: v / portfolio_value for k, v in positions.items()}

            report = monitor.generate_report(
                portfolio_returns=portfolio_returns,
                positions=positions,
                portfolio_value=portfolio_value,
                weights=weights,
            )

            var_data: dict[str, dict] = {}
            for method_name, vr in report.var_results.items():
                var_data[method_name] = {
                    "var_95": round(vr.var_95, 6),
                    "cvar_95": round(vr.cvar_95, 6),
                    "var_99": round(vr.var_99, 6),
                    "cvar_99": round(vr.cvar_99, 6),
                }

            worst_stress: dict[str, Any] = {}
            if report.stress_results:
                worst = min(report.stress_results, key=lambda s: s.portfolio_pnl)
                worst_stress = {
                    "scenario_name": worst.scenario_name,
                    "pnl_pct": round(worst.portfolio_pnl_pct, 6),
                }

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

    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("risk_dashboard error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Risk dashboard failed: {exc}")


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
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("risk_report error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Risk report failed: {exc}")
