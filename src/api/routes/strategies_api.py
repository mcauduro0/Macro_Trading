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
    """Return list of all strategies with metadata."""
    try:
        from src.agents.data_loader import PointInTimeDataLoader
        from src.strategies import ALL_STRATEGIES

        data_loader = PointInTimeDataLoader()
        strategies = []
        for strategy_id, strategy_cls in ALL_STRATEGIES.items():
            description = strategy_cls.__doc__ or ""
            description = description.strip().split("\n")[0]

            asset_class = "UNKNOWN"
            instruments: list[str] = []
            try:
                instance = strategy_cls(data_loader=data_loader)
                config = instance.config
                asset_class = (
                    config.asset_class.value
                    if hasattr(config.asset_class, "value")
                    else str(config.asset_class)
                )
                instruments = list(config.instruments)
            except Exception as exc:
                logger.debug(
                    "strategy_config_extract failed for %s: %s", strategy_id, exc
                )

            strategies.append(
                {
                    "strategy_id": strategy_id,
                    "class_name": strategy_cls.__name__,
                    "description": description,
                    "asset_class": asset_class,
                    "instruments": instruments,
                    "status": "active",
                }
            )

        return _envelope(strategies)
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Strategy dependencies unavailable: {exc}",
        )


# ---------------------------------------------------------------------------
# GET /api/v1/strategies/performance
# ---------------------------------------------------------------------------
@router.get("/performance")
async def strategies_performance():
    """Aggregate performance status across all strategies."""
    try:
        import asyncio

        from src.agents.data_loader import PointInTimeDataLoader
        from src.strategies import ALL_STRATEGIES

        def _compute():
            loader = PointInTimeDataLoader()
            as_of = date.today()
            performance = []

            for strategy_id, strategy_cls in ALL_STRATEGIES.items():
                entry = {"strategy_id": strategy_id, "status": "unknown"}
                try:
                    strategy = strategy_cls(data_loader=loader)
                    signals = strategy.generate_signals(as_of)
                    entry["status"] = "active"
                    entry["signal_count"] = len(signals) if signals else 0
                    if signals:
                        entry["instruments"] = list(
                            {s.instrument for s in signals}
                        )
                except Exception as e:
                    entry["status"] = "error"
                    entry["error"] = str(e)[:100]
                performance.append(entry)

            return {
                "strategies": performance,
                "total": len(performance),
                "active": sum(
                    1 for p in performance if p["status"] == "active"
                ),
            }

        data = await asyncio.to_thread(_compute)
        return _envelope(data)
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Strategy dependencies unavailable: {exc}",
        )


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
        raise HTTPException(
            status_code=404, detail=f"Strategy '{strategy_id}' not found"
        )

    backtest_data = await _fetch_backtest_result(strategy_id)

    if backtest_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No backtest results found for '{strategy_id}'. "
            "Run a backtest first via POST /backtest/run.",
        )

    return _envelope(backtest_data)


async def _fetch_backtest_result(strategy_id: str) -> dict | None:
    """Query backtest_results table for latest result, if available."""
    try:
        from sqlalchemy import text

        from src.core.database import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT strategy_id, sharpe_ratio, annualized_return, "
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
                    "annual_return": row.annualized_return,
                    "max_drawdown": row.max_drawdown,
                    "win_rate": row.win_rate,
                    "profit_factor": row.profit_factor,
                    "equity_curve": [],
                }
    except Exception as exc:
        logger.warning(
            "backtest_result_db_unavailable strategy_id=%s: %s", strategy_id, exc
        )
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

    strategy_cls = ALL_STRATEGIES.get(strategy_id) or StrategyRegistry._strategies.get(
        strategy_id
    )
    if strategy_cls is None:
        raise HTTPException(
            status_code=404, detail=f"Strategy '{strategy_id}' not found"
        )

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

    from src.agents.data_loader import PointInTimeDataLoader

    asset_class = "UNKNOWN"
    instruments: list[str] = []
    parameters: dict[str, Any] = {}
    try:
        instance = strategy_cls(data_loader=PointInTimeDataLoader())
        if hasattr(instance, "config") and instance.config is not None:
            config = instance.config
            asset_class = (
                config.asset_class.value
                if hasattr(config.asset_class, "value")
                else str(config.asset_class)
            )
            instruments = list(config.instruments)
            parameters = {
                "strategy_id": config.strategy_id,
                "strategy_name": config.strategy_name,
                "rebalance_frequency": (
                    config.rebalance_frequency.value
                    if hasattr(config.rebalance_frequency, "value")
                    else str(config.rebalance_frequency)
                ),
                "max_position_size": config.max_position_size,
                "max_leverage": config.max_leverage,
                "stop_loss_pct": config.stop_loss_pct,
                "take_profit_pct": config.take_profit_pct,
            }
    except Exception as exc:
        logger.debug("strategy_detail_config failed for %s: %s", strategy_id, exc)
        if metadata.get("asset_class"):
            ac = metadata["asset_class"]
            asset_class = ac.value if hasattr(ac, "value") else str(ac)
        if metadata.get("instruments"):
            instruments = metadata["instruments"]

    return _envelope(
        {
            "strategy_id": strategy_id,
            "class_name": strategy_cls.__name__,
            "asset_class": asset_class,
            "instruments": instruments,
            "description": description,
            "parameters": parameters,
            "status": "active",
        }
    )


# ---------------------------------------------------------------------------
# GET /api/v1/strategies/{strategy_id}/signal/latest -- Latest signal
# ---------------------------------------------------------------------------
@router.get("/{strategy_id}/signal/latest")
async def get_latest_signal(strategy_id: str):
    """Return the latest signal generated by the strategy.

    Instantiates the strategy and runs generate_signals() for today's date.
    Returns 503 if the strategy engine or data is unavailable.
    """
    strategy_cls, _ = _get_strategy_info(strategy_id)

    try:
        from src.agents.data_loader import PointInTimeDataLoader

        instance = strategy_cls(data_loader=PointInTimeDataLoader())
        today = date.today()
        raw_signals = await asyncio.to_thread(instance.generate_signals, today)

        if isinstance(raw_signals, list) and len(raw_signals) > 0:
            sig = raw_signals[0]
            direction = "NEUTRAL"
            strength = 0.0
            confidence = 0.0
            z_score = 0.0
            if hasattr(sig, "direction"):
                direction = (
                    sig.direction.value
                    if hasattr(sig.direction, "value")
                    else str(sig.direction)
                )
            if hasattr(sig, "suggested_size"):
                strength = float(sig.suggested_size)
            if hasattr(sig, "confidence"):
                confidence = float(sig.confidence)
            if hasattr(sig, "z_score"):
                z_score = float(sig.z_score) if sig.z_score is not None else 0.0

            return _envelope(
                {
                    "strategy_id": strategy_id,
                    "direction": direction,
                    "strength": strength,
                    "confidence": confidence,
                    "z_score": z_score,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        elif isinstance(raw_signals, dict) and raw_signals:
            first_ticker = next(iter(raw_signals))
            weight = raw_signals[first_ticker]
            direction = "LONG" if weight > 0 else ("SHORT" if weight < 0 else "NEUTRAL")
            return _envelope(
                {
                    "strategy_id": strategy_id,
                    "direction": direction,
                    "strength": abs(weight),
                    "confidence": min(abs(weight), 1.0),
                    "z_score": 0.0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        raise HTTPException(
            status_code=404,
            detail=f"No signal generated by '{strategy_id}' for {today}. "
            "The strategy may require data that is not yet available.",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "signal_latest failed strategy_id=%s: %s", strategy_id, exc, exc_info=True
        )
        raise HTTPException(
            status_code=503,
            detail=f"Signal generation failed for '{strategy_id}': {exc}. "
            "Ensure market data is available and database is running.",
        )


# ---------------------------------------------------------------------------
# GET /api/v1/strategies/{strategy_id}/signal/history -- Signal history
# ---------------------------------------------------------------------------
@router.get("/{strategy_id}/signal/history")
async def get_signal_history(
    strategy_id: str,
    days: int = Query(30, description="Number of days of history", ge=1, le=365),
):
    """Return signal history for a strategy (used for heatmap visualization).

    Returns a list of {date, direction, conviction} entries from the database.
    """
    strategy_cls, _ = _get_strategy_info(strategy_id)

    # Query strategy_signals table
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

        raise HTTPException(
            status_code=404,
            detail=f"No signal history found for '{strategy_id}' in the last {days} days. "
            "Run the daily pipeline to generate and persist signals.",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "signal_history_db error strategy_id=%s: %s",
            strategy_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Signal history unavailable: {exc}. "
            "Ensure TimescaleDB is running and strategy_signals table exists.",
        )


# ---------------------------------------------------------------------------
# PUT /api/v1/strategies/{strategy_id}/params -- Update parameters
# ---------------------------------------------------------------------------
@router.put("/{strategy_id}/params")
async def update_strategy_params(
    strategy_id: str,
    params: dict[str, Any] = Body(
        ..., description="Parameter key-value pairs to update"
    ),
):
    """Update strategy runtime parameters.

    Validates that the strategy exists and returns the updated parameters.
    Note: these are runtime parameters, not persisted to database.
    """
    strategy_cls, _ = _get_strategy_info(strategy_id)

    if not params:
        raise HTTPException(status_code=400, detail="params must not be empty")

    from src.agents.data_loader import PointInTimeDataLoader

    ALLOWED_STRATEGY_PARAMS = {
        "carry_weight",
        "beer_weight",
        "flow_weight",
        "regime_scale",
        "carry_threshold",
        "momentum_weight",
        "vol_target",
        "max_position_size",
        "max_leverage",
        "stop_loss_pct",
        "take_profit_pct",
    }
    updated_params: dict[str, Any] = {}
    try:
        instance = strategy_cls(data_loader=PointInTimeDataLoader())
        for key, value in params.items():
            if key not in ALLOWED_STRATEGY_PARAMS:
                updated_params[key] = {
                    "value": value,
                    "note": "parameter not in allowed list",
                }
            elif hasattr(instance, key):
                setattr(instance, key, value)
                updated_params[key] = value
            else:
                updated_params[key] = {
                    "value": value,
                    "note": "attribute not found on strategy class",
                }
    except Exception as exc:
        logger.warning("params_update failed strategy_id=%s: %s", strategy_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update parameters for '{strategy_id}': {exc}",
        )

    return _envelope(
        {
            "strategy_id": strategy_id,
            "updated_params": updated_params,
            "note": "Runtime parameters updated (not persisted)",
        }
    )
