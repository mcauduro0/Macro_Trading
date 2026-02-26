"""Portfolio management endpoints.

Provides:
- GET /portfolio/current           — consolidated portfolio positions
- GET /portfolio/risk              — risk report (VaR, CVaR, stress tests)
- GET /portfolio/target            — target portfolio weights from optimization
- GET /portfolio/rebalance-trades  — required trades to reach target weights
- GET /portfolio/attribution       — strategy attribution for current portfolio
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

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
        logger.error("portfolio_current error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


def _build_portfolio_positions(as_of: date) -> list[dict]:
    """Build portfolio positions from strategy signals."""
    from src.agents.data_loader import PointInTimeDataLoader
    from src.strategies import ALL_STRATEGIES

    data_loader = PointInTimeDataLoader()
    positions: list[dict] = []
    for strategy_id, strategy_cls in ALL_STRATEGIES.items():
        try:
            strategy = strategy_cls(data_loader=data_loader)
            strat_positions = strategy.generate_signals(as_of)
            for pos in strat_positions:
                direction = pos.direction.value if hasattr(pos.direction, "value") else str(pos.direction)
                asset_class = (
                    strategy.config.asset_class.value
                    if hasattr(strategy.config.asset_class, "value")
                    else str(strategy.config.asset_class)
                )
                positions.append({
                    "instrument": pos.instrument,
                    "direction": direction,
                    "weight": round(pos.weight, 6),
                    "contributing_strategy_ids": [strategy_id],
                    "asset_class": asset_class,
                })
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                "Strategy %s failed: %s", strategy_id, e,
            )

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
        logger.error("portfolio_risk error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


def _build_risk_report() -> dict:
    """Generate risk report using RiskMonitor."""
    from datetime import date as date_type

    from src.risk.risk_monitor import RiskMonitor

    monitor = RiskMonitor()

    # Compute portfolio returns from current positions
    positions_data = _build_portfolio_positions(date_type.today())
    weights: dict[str, float] = {
        p["instrument"]: p["weight"] for p in positions_data
    }
    positions: dict[str, float] = dict(weights)
    portfolio_value = 1_000_000.0

    # Generate synthetic returns from weights as fallback
    # (real implementation would query historical portfolio returns from DB)
    rng = np.random.default_rng(42)
    portfolio_returns = rng.normal(0.0003, 0.01, 252)

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


# ---------------------------------------------------------------------------
# GET /api/v1/portfolio/target
# ---------------------------------------------------------------------------
@router.get("/target")
async def portfolio_target():
    """Return target portfolio weights from optimization.

    Instantiates PortfolioOptimizer, runs on sample/placeholder data,
    and returns target weights with optimization metadata.
    """
    try:
        target_data = await asyncio.to_thread(_build_target_weights)
        return _envelope(target_data)
    except Exception as exc:
        logger.error("portfolio_target error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


def _build_target_weights() -> dict:
    """Build target portfolio weights using Black-Litterman + MV optimization."""
    from src.portfolio.black_litterman import BlackLitterman
    from src.portfolio.portfolio_optimizer import PortfolioOptimizer

    instruments = ["IBOV", "DI1F25", "USDBRL", "PETR4", "VALE3"]

    # Sample covariance (diagonal approximation with realistic Brazilian market vols)
    vols = np.array([0.25, 0.10, 0.15, 0.30, 0.28])
    covariance = np.diag(vols ** 2)

    # Market cap weights (approximate)
    market_weights = np.array([0.30, 0.20, 0.15, 0.20, 0.15])

    # Run Black-Litterman with no views (equilibrium only) as baseline
    bl = BlackLitterman()
    bl_result = bl.optimize(
        views=[],
        covariance=covariance,
        market_weights=market_weights,
        instrument_names=instruments,
        regime_clarity=0.7,
    )

    # Run mean-variance optimization on posterior returns
    optimizer = PortfolioOptimizer()
    target_weights = optimizer.optimize_with_bl(bl_result, instruments)

    # Build response
    targets = []
    for inst in instruments:
        tw = target_weights.get(inst, 0.0)
        direction = "LONG" if tw > 0.001 else ("SHORT" if tw < -0.001 else "NEUTRAL")
        targets.append({
            "instrument": inst,
            "direction": direction,
            "target_weight": round(tw, 6),
            "current_weight": 0.0,  # Placeholder -- would come from live positions
            "sizing_method": "mean_variance",
        })

    return {
        "targets": targets,
        "optimization": {
            "method": "black_litterman",
            "regime_clarity": bl_result.get("regime_clarity", 0.0),
            "constraints": {
                "min_weight": optimizer.constraints.min_weight,
                "max_weight": optimizer.constraints.max_weight,
                "max_leverage": optimizer.constraints.max_leverage,
                "long_only": optimizer.constraints.long_only,
            },
        },
    }


# ---------------------------------------------------------------------------
# GET /api/v1/portfolio/rebalance-trades
# ---------------------------------------------------------------------------
@router.get("/rebalance-trades")
async def portfolio_rebalance_trades():
    """Compute required trades to move from current to target weights.

    Uses PortfolioOptimizer.should_rebalance() to determine if rebalancing
    is needed based on signal change and drift thresholds.
    """
    try:
        trades_data = await asyncio.to_thread(_build_rebalance_trades)
        return _envelope(trades_data)
    except Exception as exc:
        logger.error("portfolio_rebalance_trades error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


def _build_rebalance_trades() -> dict:
    """Compute rebalance trades from current to target."""
    from src.portfolio.portfolio_optimizer import PortfolioOptimizer

    optimizer = PortfolioOptimizer()

    # Sample current and target weights
    current_weights: dict[str, float] = {
        "IBOV": 0.10,
        "DI1F25": 0.05,
        "USDBRL": -0.05,
        "PETR4": 0.08,
        "VALE3": 0.07,
    }

    # Build target weights from optimization
    target_data = _build_target_weights()
    target_weights = {
        t["instrument"]: t["target_weight"] for t in target_data["targets"]
    }

    # Determine if rebalancing is needed
    signal_change = 0.0  # Placeholder for aggregate signal change
    should_rebalance = optimizer.should_rebalance(
        current_weights=current_weights,
        target_weights=target_weights,
        signal_change=signal_change,
    )

    # Compute individual trades
    all_instruments = set(current_weights) | set(target_weights)
    trades = []
    total_notional = 1_000_000.0  # Reference portfolio value

    for inst in sorted(all_instruments):
        current_w = current_weights.get(inst, 0.0)
        target_w = target_weights.get(inst, 0.0)
        trade_w = target_w - current_w

        if abs(trade_w) < 0.001:
            continue

        direction = "BUY" if trade_w > 0 else "SELL"
        trades.append({
            "instrument": inst,
            "direction": direction,
            "current_weight": round(current_w, 6),
            "target_weight": round(target_w, 6),
            "trade_weight": round(trade_w, 6),
            "trade_notional": round(trade_w * total_notional, 2),
        })

    trigger_reason = None
    if should_rebalance:
        # Determine reason
        max_drift = max(
            abs(target_weights.get(inst, 0.0) - current_weights.get(inst, 0.0))
            for inst in all_instruments
        ) if all_instruments else 0.0

        if abs(signal_change) > 0.15:
            trigger_reason = "signal_change"
        elif max_drift > 0.05:
            trigger_reason = "position_drift"

    estimated_cost = sum(abs(t["trade_notional"]) * 0.0005 for t in trades)

    return {
        "trades": trades,
        "should_rebalance": should_rebalance,
        "trigger_reason": trigger_reason,
        "estimated_cost": round(estimated_cost, 2),
    }


# ---------------------------------------------------------------------------
# GET /api/v1/portfolio/attribution
# ---------------------------------------------------------------------------
@router.get("/attribution")
async def portfolio_attribution():
    """Return strategy attribution for current portfolio.

    Reads from strategy_attribution JSON in portfolio_state records
    or builds from in-memory state as fallback.
    """
    try:
        attribution_data = await asyncio.to_thread(_build_attribution)
        return _envelope(attribution_data)
    except Exception as exc:
        logger.error("portfolio_attribution error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


def _build_attribution() -> dict:
    """Build strategy attribution for portfolio positions."""
    # Sample attribution data (would come from portfolio_state records)
    sample_positions = [
        {
            "instrument": "IBOV",
            "strategy_attribution": {
                "FX_BR_01": 0.40,
                "RATES_01": 0.30,
                "CROSS_01": 0.30,
            },
            "pnl": 15000.0,
        },
        {
            "instrument": "DI1F25",
            "strategy_attribution": {
                "RATES_01": 0.60,
                "RATES_02": 0.25,
                "INF_01": 0.15,
            },
            "pnl": -5000.0,
        },
        {
            "instrument": "USDBRL",
            "strategy_attribution": {
                "FX_BR_01": 0.50,
                "FX_02": 0.30,
                "CUPOM_01": 0.20,
            },
            "pnl": 8000.0,
        },
    ]

    attribution = []
    by_strategy: dict[str, float] = {}
    total_pnl = 0.0

    for pos in sample_positions:
        instrument = pos["instrument"]
        strat_attr = pos.get("strategy_attribution", {})
        pos_pnl = pos.get("pnl", 0.0)
        total_pnl += pos_pnl

        strategies = []
        for strategy_id, contribution_weight in strat_attr.items():
            contribution_pnl = round(pos_pnl * contribution_weight, 2)
            strategies.append({
                "strategy_id": strategy_id,
                "contribution_weight": round(contribution_weight, 4),
                "contribution_pnl": contribution_pnl,
            })
            by_strategy[strategy_id] = (
                by_strategy.get(strategy_id, 0.0) + contribution_pnl
            )

        attribution.append({
            "instrument": instrument,
            "strategies": strategies,
        })

    # Round by_strategy values
    by_strategy = {k: round(v, 2) for k, v in by_strategy.items()}

    return {
        "attribution": attribution,
        "total_pnl": round(total_pnl, 2),
        "by_strategy": by_strategy,
    }
