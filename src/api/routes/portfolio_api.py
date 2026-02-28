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
# Data loaders
# ---------------------------------------------------------------------------

def _load_pms_book(as_of: date | None = None) -> dict:
    """Load portfolio book from Position Manager.

    Returns the full book dict with positions and summary.
    Raises RuntimeError if PMS is unavailable.
    """
    try:
        from src.pms.position_manager import PositionManager

        pm = PositionManager()
        if as_of:
            book = pm.get_book(as_of_date=as_of)
        else:
            book = pm.get_book()
        return book
    except Exception as exc:
        raise RuntimeError(
            f"PositionManager unavailable: {exc}. "
            "Ensure PMS is configured with active positions."
        ) from exc


def _load_current_weights(as_of: date | None = None) -> dict[str, float]:
    """Load current portfolio weights from PMS.

    Returns dict of {instrument: weight}. Raises RuntimeError if unavailable.
    """
    book = _load_pms_book(as_of)
    positions = book.get("positions", [])
    if not positions:
        raise RuntimeError(
            "No positions in portfolio book. Open positions via the trade workflow."
        )
    return {p["instrument"]: p.get("weight", 0.0) for p in positions}


def _load_portfolio_returns_for_risk() -> np.ndarray:
    """Load historical portfolio returns for risk calculations.

    Tries PMS first, then database query. Raises RuntimeError if unavailable.
    """
    # Try loading from portfolio_returns table
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

    # Try computing from current positions and market data
    try:
        import pandas as pd
        from datetime import date as date_type
        weights = _load_current_weights()
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
                return returns_data.values @ w
    except Exception:
        pass

    raise RuntimeError(
        "Historical portfolio returns unavailable. Ensure database is running "
        "and market data has been collected."
    )


def _load_covariance_from_market_data(
    instruments: list[str],
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Load covariance matrix from actual market data.

    Returns (covariance_matrix, market_weights, available_instruments) computed
    from historical returns.  Only instruments with sufficient data are included,
    so the caller must use the returned ``available_instruments`` list (not the
    original input) to stay aligned with the matrix dimensions.

    Raises RuntimeError if fewer than 2 instruments have data.
    """
    try:
        import pandas as pd
        from datetime import date as date_type
        from src.agents.data_loader import PointInTimeDataLoader

        loader = PointInTimeDataLoader()
        returns_frames = []
        available_instruments: list[str] = []
        for ticker in instruments:
            try:
                md = loader.get_market_data(ticker, as_of_date=date_type.today(), lookback_days=504)
                if md is not None and not md.empty and "close" in md.columns:
                    ret = md["close"].pct_change().dropna()
                    ret.name = ticker
                    returns_frames.append(ret)
                    available_instruments.append(ticker)
            except Exception:
                continue
        returns_data = pd.concat(returns_frames, axis=1).dropna() if returns_frames else None
        if returns_data is not None and len(returns_data) >= 60 and len(available_instruments) >= 2:
            covariance = returns_data.cov().values * 252  # Annualize
            # Market-cap weights proxy: inverse volatility
            vols = np.sqrt(np.diag(covariance))
            inv_vol = 1.0 / np.where(vols > 0, vols, 1.0)
            market_weights = inv_vol / inv_vol.sum()
            logger.info(
                "covariance_loaded",
                requested=len(instruments),
                available=len(available_instruments),
                missing=[t for t in instruments if t not in available_instruments],
            )
            return covariance, market_weights, available_instruments
    except Exception:
        pass

    raise RuntimeError(
        f"Market data unavailable for instruments {instruments}. "
        "Ensure historical data has been collected by the data pipeline."
    )


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

        return _envelope(
            {
                "positions": positions,
                "summary": {
                    "total_positions": total_positions,
                    "net_leverage": round(net_leverage, 4),
                    "gross_leverage": round(gross_leverage, 4),
                },
                "as_of_date": str(as_of),
            }
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("portfolio_current error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Portfolio query failed: {exc}")


def _build_portfolio_positions(as_of: date) -> list[dict]:
    """Build portfolio positions from strategy signals."""
    from src.agents.data_loader import PointInTimeDataLoader
    from src.strategies import ALL_STRATEGIES

    data_loader = PointInTimeDataLoader()
    positions: list[dict] = []
    errors: list[str] = []

    for strategy_id, strategy_cls in ALL_STRATEGIES.items():
        try:
            strategy = strategy_cls(data_loader=data_loader)
            strat_positions = strategy.generate_signals(as_of)
            for pos in strat_positions:
                direction = (
                    pos.direction.value
                    if hasattr(pos.direction, "value")
                    else str(pos.direction)
                )
                asset_class = (
                    strategy.config.asset_class.value
                    if hasattr(strategy.config.asset_class, "value")
                    else str(strategy.config.asset_class)
                )
                positions.append(
                    {
                        "instrument": pos.instrument,
                        "direction": direction,
                        "weight": round(pos.weight, 6),
                        "contributing_strategy_ids": [strategy_id],
                        "asset_class": asset_class,
                    }
                )
        except Exception as e:
            errors.append(f"{strategy_id}: {e}")
            logger.warning("Strategy %s signal generation failed: %s", strategy_id, e)

    if not positions and errors:
        raise RuntimeError(
            f"All strategies failed to generate signals. Errors: {'; '.join(errors[:5])}"
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
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("portfolio_risk error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Risk report failed: {exc}")


def _build_risk_report() -> dict:
    """Generate risk report using RiskMonitor with real data."""
    from datetime import date as date_type

    from src.risk.risk_monitor import RiskMonitor

    monitor = RiskMonitor()

    # Load real portfolio data
    positions_data = _build_portfolio_positions(date_type.today())
    weights: dict[str, float] = {p["instrument"]: p["weight"] for p in positions_data}
    positions: dict[str, float] = dict(weights)

    # Try to get real portfolio value from PMS
    portfolio_value = 1_000_000.0  # Default initial capital
    try:
        book = _load_pms_book()
        summary = book.get("summary", {})
        nav = summary.get("total_nav_brl", 0.0)
        if nav > 0:
            portfolio_value = float(nav)
    except RuntimeError:
        logger.info("Using default portfolio value; PMS NAV not available")

    # Load real historical returns
    portfolio_returns = _load_portfolio_returns_for_risk()

    report = monitor.generate_report(
        portfolio_returns=portfolio_returns,
        positions=positions,
        portfolio_value=portfolio_value,
        weights=weights,
    )

    # Serialize VaR results
    var_data = {}
    for method_name, var_result in report.var_results.items():
        var_data[method_name] = {
            "var_95": round(var_result.var_95, 6),
            "cvar_95": round(var_result.cvar_95, 6),
            "var_99": round(var_result.var_99, 6),
            "cvar_99": round(var_result.cvar_99, 6),
        }

    # Serialize stress results
    stress_data = []
    for sr in report.stress_results:
        stress_data.append(
            {
                "scenario_name": sr.scenario_name,
                "portfolio_pnl": round(sr.portfolio_pnl, 2),
                "portfolio_pnl_pct": round(sr.portfolio_pnl_pct, 6),
            }
        )

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

    Uses Black-Litterman with real market data covariance matrix and
    portfolio optimizer with institutional constraints.
    """
    try:
        target_data = await asyncio.to_thread(_build_target_weights)
        return _envelope(target_data)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("portfolio_target error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Optimization failed: {exc}")


def _build_target_weights() -> dict:
    """Build target portfolio weights using Black-Litterman + MV optimization."""
    from src.portfolio.black_litterman import BlackLitterman
    from src.portfolio.portfolio_optimizer import PortfolioOptimizer

    # Get instruments from current positions or strategy universe
    try:
        current_weights = _load_current_weights()
        instruments = list(current_weights.keys())
    except RuntimeError:
        # No current positions - use strategy universe
        from src.strategies import ALL_STRATEGIES
        from src.agents.data_loader import PointInTimeDataLoader

        loader = PointInTimeDataLoader()
        instruments_set: set[str] = set()
        for strategy_cls in ALL_STRATEGIES.values():
            try:
                instance = strategy_cls(data_loader=loader)
                instruments_set.update(instance.config.instruments)
            except Exception:
                continue
        instruments = sorted(instruments_set)
        if not instruments:
            raise RuntimeError("No instruments available from strategies")
        current_weights = {inst: 0.0 for inst in instruments}

    # Load real covariance from market data — only instruments with data
    covariance, market_weights, available = _load_covariance_from_market_data(instruments)

    # Run Black-Litterman with no views (equilibrium only) as baseline
    bl = BlackLitterman()
    bl_result = bl.optimize(
        views=[],
        covariance=covariance,
        market_weights=market_weights,
        instrument_names=available,
        regime_clarity=0.7,
    )

    # Run mean-variance optimization on posterior returns
    optimizer = PortfolioOptimizer()
    target_weights = optimizer.optimize_with_bl(bl_result, available)

    # Include all original instruments — those without data get weight 0
    targets = []
    for inst in instruments:
        tw = target_weights.get(inst, 0.0)
        direction = "LONG" if tw > 0.001 else ("SHORT" if tw < -0.001 else "NEUTRAL")
        targets.append(
            {
                "instrument": inst,
                "direction": direction,
                "target_weight": round(tw, 6),
                "current_weight": round(current_weights.get(inst, 0.0), 6),
                "sizing_method": "mean_variance",
            }
        )

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
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("portfolio_rebalance_trades error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Rebalance computation failed: {exc}")


def _build_rebalance_trades() -> dict:
    """Compute rebalance trades from current to target."""
    from src.portfolio.portfolio_optimizer import PortfolioOptimizer

    optimizer = PortfolioOptimizer()

    # Load real current weights from PMS
    current_weights = _load_current_weights()

    # Build target weights from optimization
    target_data = _build_target_weights()
    target_weights = {
        t["instrument"]: t["target_weight"] for t in target_data["targets"]
    }

    signal_change = 0.0
    should_rebalance = optimizer.should_rebalance(
        current_weights=current_weights,
        target_weights=target_weights,
        signal_change=signal_change,
    )

    all_instruments = set(current_weights) | set(target_weights)
    trades = []

    # Get portfolio value from PMS
    total_notional = 1_000_000.0
    try:
        book = _load_pms_book()
        summary = book.get("summary", {})
        nav = summary.get("total_nav_brl", 0.0)
        if nav > 0:
            total_notional = float(nav)
    except RuntimeError:
        logger.info("Using default notional; PMS NAV not available")

    for inst in sorted(all_instruments):
        current_w = current_weights.get(inst, 0.0)
        target_w = target_weights.get(inst, 0.0)
        trade_w = target_w - current_w

        if abs(trade_w) < 0.001:
            continue

        direction = "BUY" if trade_w > 0 else "SELL"
        trades.append(
            {
                "instrument": inst,
                "direction": direction,
                "current_weight": round(current_w, 6),
                "target_weight": round(target_w, 6),
                "trade_weight": round(trade_w, 6),
                "trade_notional": round(trade_w * total_notional, 2),
            }
        )

    trigger_reason = None
    if should_rebalance:
        max_drift = (
            max(
                abs(target_weights.get(inst, 0.0) - current_weights.get(inst, 0.0))
                for inst in all_instruments
            )
            if all_instruments
            else 0.0
        )

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

    Reads from PMS position manager to compute real attribution.
    """
    try:
        attribution_data = await asyncio.to_thread(_build_attribution)
        return _envelope(attribution_data)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("portfolio_attribution error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Attribution failed: {exc}")


def _build_attribution() -> dict:
    """Build strategy attribution from real PMS data."""
    book = _load_pms_book()
    positions = book.get("positions", [])

    if not positions:
        raise RuntimeError(
            "No positions available for attribution. "
            "Open positions via the trade workflow first."
        )

    attribution = []
    by_strategy: dict[str, float] = {}
    total_pnl = 0.0

    for pos in positions:
        instrument = pos.get("instrument", "UNKNOWN")
        strat_attr = pos.get("strategy_attribution", {})
        pos_pnl = pos.get("unrealized_pnl", pos.get("pnl", 0.0))
        total_pnl += pos_pnl

        strategies = []
        for strategy_id, contribution_weight in strat_attr.items():
            contribution_pnl = round(pos_pnl * contribution_weight, 2)
            strategies.append(
                {
                    "strategy_id": strategy_id,
                    "contribution_weight": round(contribution_weight, 4),
                    "contribution_pnl": contribution_pnl,
                }
            )
            by_strategy[strategy_id] = (
                by_strategy.get(strategy_id, 0.0) + contribution_pnl
            )

        attribution.append(
            {
                "instrument": instrument,
                "strategies": strategies,
            }
        )

    by_strategy = {k: round(v, 2) for k, v in by_strategy.items()}

    return {
        "attribution": attribution,
        "total_pnl": round(total_pnl, 2),
        "by_strategy": by_strategy,
    }
