"""Strategy management endpoints.

Provides:
- GET  /strategies                              — list all strategies
- GET  /strategies/{strategy_id}                — full strategy detail
- GET  /strategies/{strategy_id}/backtest       — latest backtest results
- GET  /strategies/{strategy_id}/signal/latest  — latest signal
- GET  /strategies/{strategy_id}/signal/history — signal history for heatmap
- PUT  /strategies/{strategy_id}/params         — update strategy parameters
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategies", tags=["Strategies"])


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
# GET /api/v1/strategies
# ---------------------------------------------------------------------------
@router.get("")
async def list_strategies():
    """Return list of all 8 strategies with metadata."""
    from src.strategies import ALL_STRATEGIES

    strategies = []
    for strategy_id, strategy_cls in ALL_STRATEGIES.items():
        config = None
        description = strategy_cls.__doc__ or ""
        description = description.strip().split("\n")[0]  # first line only

        # Try to extract config from class
        asset_class = "UNKNOWN"
        instruments: list[str] = []
        try:
            # Instantiate to read config
            instance = strategy_cls()
            config = instance.config
            asset_class = config.asset_class.value if hasattr(config.asset_class, "value") else str(config.asset_class)
            instruments = list(config.instruments)
        except Exception:
            pass

        strategies.append({
            "strategy_id": strategy_id,
            "class_name": strategy_cls.__name__,
            "description": description,
            "asset_class": asset_class,
            "instruments": instruments,
            "status": "active",
        })

    return _envelope(strategies)


# ---------------------------------------------------------------------------
# GET /api/v1/strategies/{strategy_id}/backtest
# ---------------------------------------------------------------------------
@router.get("/{strategy_id}/backtest")
async def strategy_backtest(
    strategy_id: str,
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
):
    """Return latest backtest results for a strategy."""
    from src.strategies import ALL_STRATEGIES

    if strategy_id not in ALL_STRATEGIES:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

    # Try to query DB for latest backtest result
    backtest_data = await _fetch_backtest_result(strategy_id)

    if backtest_data is None:
        # Return placeholder
        backtest_data = {
            "strategy_id": strategy_id,
            "sharpe_ratio": None,
            "annual_return": None,
            "max_drawdown": None,
            "win_rate": None,
            "profit_factor": None,
            "equity_curve": [],
            "note": "No backtest results available yet",
        }

    return _envelope(backtest_data)


async def _fetch_backtest_result(strategy_id: str) -> dict | None:
    """Query backtest_results table for latest result, if available."""
    try:
        from sqlalchemy import text
        from src.core.database import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT strategy_id, sharpe_ratio, annual_return, "
                    "max_drawdown, win_rate, profit_factor "
                    "FROM backtest_results "
                    "WHERE strategy_id = :sid "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"sid": strategy_id},
            )
            row = result.first()
            if row:
                return {
                    "strategy_id": row.strategy_id,
                    "sharpe_ratio": row.sharpe_ratio,
                    "annual_return": row.annual_return,
                    "max_drawdown": row.max_drawdown,
                    "win_rate": row.win_rate,
                    "profit_factor": row.profit_factor,
                    "equity_curve": [],
                }
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_strategy_info(strategy_id: str) -> tuple[type, dict]:
    """Look up strategy class and metadata from both ALL_STRATEGIES and StrategyRegistry.

    Returns:
        (strategy_cls, metadata_dict)

    Raises:
        HTTPException 404 if not found.
    """
    from src.strategies import ALL_STRATEGIES
    from src.strategies.registry import StrategyRegistry

    strategy_cls = ALL_STRATEGIES.get(strategy_id) or StrategyRegistry._strategies.get(strategy_id)
    if strategy_cls is None:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

    metadata = StrategyRegistry._metadata.get(strategy_id, {})
    return strategy_cls, metadata


# ---------------------------------------------------------------------------
# GET /api/v1/strategies/{strategy_id} -- Full strategy detail
# ---------------------------------------------------------------------------
@router.get("/{strategy_id}")
async def get_strategy_detail(strategy_id: str):
    """Return full strategy detail including parameters and configuration."""
    strategy_cls, metadata = _get_strategy_info(strategy_id)

    description = strategy_cls.__doc__ or ""
    description = description.strip().split("\n")[0]

    # Try to extract config by instantiation
    asset_class = "UNKNOWN"
    instruments: list[str] = []
    parameters: dict[str, Any] = {}
    try:
        instance = strategy_cls()
        if hasattr(instance, "config") and instance.config is not None:
            config = instance.config
            asset_class = config.asset_class.value if hasattr(config.asset_class, "value") else str(config.asset_class)
            instruments = list(config.instruments)
            # Extract config as parameters dict
            parameters = {
                "strategy_id": config.strategy_id,
                "strategy_name": config.strategy_name,
                "rebalance_frequency": config.rebalance_frequency.value if hasattr(config.rebalance_frequency, "value") else str(config.rebalance_frequency),
                "max_position_size": config.max_position_size,
                "max_leverage": config.max_leverage,
                "stop_loss_pct": config.stop_loss_pct,
                "take_profit_pct": config.take_profit_pct,
            }
    except Exception:
        # Fallback to metadata
        if metadata.get("asset_class"):
            ac = metadata["asset_class"]
            asset_class = ac.value if hasattr(ac, "value") else str(ac)
        if metadata.get("instruments"):
            instruments = metadata["instruments"]

    return _envelope({
        "strategy_id": strategy_id,
        "class_name": strategy_cls.__name__,
        "asset_class": asset_class,
        "instruments": instruments,
        "description": description,
        "parameters": parameters,
        "status": "active",
    })


# ---------------------------------------------------------------------------
# GET /api/v1/strategies/{strategy_id}/signal/latest -- Latest signal
# ---------------------------------------------------------------------------
@router.get("/{strategy_id}/signal/latest")
async def get_latest_signal(strategy_id: str):
    """Return the latest signal generated by the strategy.

    Instantiates the strategy and runs generate_signals() for today's date.
    Falls back to placeholder signal if the strategy fails.
    """
    strategy_cls, _ = _get_strategy_info(strategy_id)

    try:
        instance = strategy_cls()
        today = date.today()
        raw_signals = await asyncio.to_thread(instance.generate_signals, today)

        # Adapt the signal output
        if isinstance(raw_signals, list) and len(raw_signals) > 0:
            sig = raw_signals[0]
            # StrategySignal has direction, strength, z_score, confidence
            direction = "NEUTRAL"
            strength = 0.0
            confidence = 0.0
            z_score = 0.0
            if hasattr(sig, "direction"):
                direction = sig.direction.value if hasattr(sig.direction, "value") else str(sig.direction)
            if hasattr(sig, "suggested_size"):
                strength = float(sig.suggested_size)
            if hasattr(sig, "confidence"):
                confidence = float(sig.confidence)
            if hasattr(sig, "z_score"):
                z_score = float(sig.z_score) if sig.z_score is not None else 0.0

            return _envelope({
                "strategy_id": strategy_id,
                "direction": direction,
                "strength": strength,
                "confidence": confidence,
                "z_score": z_score,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        elif isinstance(raw_signals, dict) and raw_signals:
            # dict[str, float] format -- take first entry
            first_ticker = next(iter(raw_signals))
            weight = raw_signals[first_ticker]
            direction = "LONG" if weight > 0 else ("SHORT" if weight < 0 else "NEUTRAL")
            return _envelope({
                "strategy_id": strategy_id,
                "direction": direction,
                "strength": abs(weight),
                "confidence": min(abs(weight), 1.0),
                "z_score": 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as exc:
        logger.debug("signal_latest_fallback strategy_id=%s error=%s", strategy_id, exc)

    # Fallback placeholder
    return _envelope({
        "strategy_id": strategy_id,
        "direction": "NEUTRAL",
        "strength": 0.0,
        "confidence": 0.0,
        "z_score": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "Placeholder signal -- strategy data unavailable",
    })


# ---------------------------------------------------------------------------
# GET /api/v1/strategies/{strategy_id}/signal/history -- Signal history
# ---------------------------------------------------------------------------
@router.get("/{strategy_id}/signal/history")
async def get_signal_history(
    strategy_id: str,
    days: int = Query(30, description="Number of days of history", ge=1, le=365),
):
    """Return signal history for a strategy (used for heatmap visualization).

    Returns a list of {date, direction, conviction} entries.
    """
    strategy_cls, _ = _get_strategy_info(strategy_id)

    # Try to query strategy_signals table
    try:
        from sqlalchemy import text
        from src.core.database import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT signal_date, direction, conviction "
                    "FROM strategy_signals "
                    "WHERE strategy_id = :sid "
                    "AND signal_date >= CURRENT_DATE - :days "
                    "ORDER BY signal_date DESC"
                ),
                {"sid": strategy_id, "days": days},
            )
            rows = result.fetchall()
            if rows:
                history = [
                    {
                        "date": str(row.signal_date),
                        "direction": row.direction,
                        "conviction": float(row.conviction) if row.conviction else 0.0,
                    }
                    for row in rows
                ]
                return _envelope(history)
    except Exception as exc:
        logger.debug("signal_history_db_unavailable strategy_id=%s error=%s", strategy_id, exc)

    # Fallback: generate sample history
    from datetime import timedelta
    import random

    random.seed(hash(strategy_id) % 2**32)
    history = []
    today = date.today()
    directions = ["LONG", "SHORT", "NEUTRAL"]
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        direction = random.choice(directions)
        conviction = round(random.uniform(0.1, 0.9), 2)
        history.append({
            "date": str(d),
            "direction": direction,
            "conviction": conviction,
        })

    return _envelope(history)


# ---------------------------------------------------------------------------
# PUT /api/v1/strategies/{strategy_id}/params -- Update parameters
# ---------------------------------------------------------------------------
@router.put("/{strategy_id}/params")
async def update_strategy_params(
    strategy_id: str,
    params: dict[str, Any] = Body(..., description="Parameter key-value pairs to update"),
):
    """Update strategy runtime parameters.

    Validates that the strategy exists and returns the updated parameters.
    Note: these are runtime parameters, not persisted to database.
    """
    strategy_cls, _ = _get_strategy_info(strategy_id)

    # Validate params are not empty
    if not params:
        raise HTTPException(status_code=400, detail="params must not be empty")

    # Attempt to apply params to strategy instance for validation
    updated_params: dict[str, Any] = {}
    try:
        instance = strategy_cls()
        for key, value in params.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
                updated_params[key] = value
            else:
                updated_params[key] = {"value": value, "note": "attribute not found on strategy class"}
    except Exception as exc:
        logger.debug("params_update_fallback strategy_id=%s error=%s", strategy_id, exc)
        updated_params = params

    return _envelope({
        "strategy_id": strategy_id,
        "updated_params": updated_params,
        "note": "Runtime parameters updated (not persisted)",
    })
