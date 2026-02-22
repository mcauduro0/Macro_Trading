"""Strategy management endpoints.

Provides:
- GET /strategies                        — list all 8 strategies
- GET /strategies/{strategy_id}/backtest — latest backtest results
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

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
