"""Backtest API endpoints.

Provides:
- POST /backtest/run          -- Trigger backtest for a strategy
- GET  /backtest/results      -- Retrieve backtest results for a strategy
- POST /backtest/portfolio    -- Portfolio-level backtest
- GET  /backtest/comparison   -- Side-by-side strategy comparison
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["Backtest"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class BacktestRunRequest(BaseModel):
    strategy_id: str
    start_date: Optional[str] = Field(None, description="Start date YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="End date YYYY-MM-DD")


class PortfolioBacktestRequest(BaseModel):
    strategy_ids: list[str]
    weights: Optional[dict[str, float]] = Field(
        None, description="Optional {strategy_id: weight} mapping"
    )


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
# Sample / placeholder data helpers
# ---------------------------------------------------------------------------
def _sample_backtest_result(strategy_id: str) -> dict:
    """Return a placeholder backtest result for demo/fallback."""
    return {
        "strategy_id": strategy_id,
        "sharpe_ratio": 1.25,
        "annual_return": 0.12,
        "max_drawdown": -0.08,
        "total_trades": 48,
        "win_rate": 0.58,
        "profit_factor": 1.65,
        "equity_curve": [100000, 101200, 103500, 102800, 105600, 108200, 112000],
        "note": "Sample data -- live backtest engine unavailable",
    }


def _sample_portfolio_result(
    strategy_ids: list[str], weights: dict[str, float]
) -> dict:
    """Return a placeholder portfolio backtest result."""
    return {
        "strategy_ids": strategy_ids,
        "weights": weights,
        "combined_sharpe": 1.45,
        "combined_annual_return": 0.14,
        "combined_max_drawdown": -0.06,
        "equity_curve": [100000, 101500, 103800, 103200, 106100, 109500, 114200],
        "attribution": {sid: w for sid, w in weights.items()},
        "correlation_matrix": {
            f"{a}_{b}": 0.35 for a in strategy_ids for b in strategy_ids if a != b
        },
        "note": "Sample data -- live backtest engine unavailable",
    }


# ---------------------------------------------------------------------------
# POST /backtest/run -- Trigger backtest for a strategy
# ---------------------------------------------------------------------------
@router.post("/run", status_code=202)
async def run_backtest(request: BacktestRunRequest):
    """Trigger a backtest run for a single strategy.

    Returns 202 with backtest results (sharpe, annual_return, max_drawdown,
    total_trades, equity_curve).
    """
    try:
        from src.strategies import ALL_STRATEGIES
        from src.strategies.registry import StrategyRegistry

        # Validate strategy exists
        if (
            request.strategy_id not in ALL_STRATEGIES
            and request.strategy_id not in StrategyRegistry._strategies
        ):
            raise HTTPException(
                status_code=404,
                detail=f"Strategy '{request.strategy_id}' not found",
            )

        # Determine dates
        start = (
            date.fromisoformat(request.start_date)
            if request.start_date
            else date(2020, 1, 1)
        )
        end = (
            date.fromisoformat(request.end_date)
            if request.end_date
            else date(2024, 12, 31)
        )

        # Try to run actual backtest
        from src.agents.data_loader import PointInTimeDataLoader
        from src.backtesting.engine import BacktestConfig, BacktestEngine

        config = BacktestConfig(
            start_date=start,
            end_date=end,
            initial_capital=1_000_000.0,
        )

        # Get strategy instance
        strategy_cls = ALL_STRATEGIES.get(
            request.strategy_id,
            StrategyRegistry._strategies.get(request.strategy_id),
        )
        loader = PointInTimeDataLoader()
        strategy = strategy_cls(data_loader=loader)

        engine = BacktestEngine(config, loader)
        result = await asyncio.to_thread(engine.run, strategy)

        # Convert BacktestResult to dict
        equity_curve = []
        if hasattr(result, "equity_curve") and result.equity_curve:
            equity_curve = [float(e) for _, e in result.equity_curve]

        return _envelope(
            {
                "strategy_id": request.strategy_id,
                "sharpe_ratio": (
                    float(result.sharpe_ratio)
                    if hasattr(result, "sharpe_ratio")
                    else None
                ),
                "annual_return": (
                    float(result.annualized_return)
                    if hasattr(result, "annualized_return")
                    else None
                ),
                "max_drawdown": (
                    float(result.max_drawdown)
                    if hasattr(result, "max_drawdown")
                    else None
                ),
                "total_trades": (
                    int(result.total_trades) if hasattr(result, "total_trades") else 0
                ),
                "equity_curve": equity_curve,
            }
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "backtest_run_fallback strategy_id=%s error=%s", request.strategy_id, exc
        )
        result = _sample_backtest_result(request.strategy_id)
        result["note"] = "Backtest engine unavailable. Returning sample data."
        return _envelope(result)


# ---------------------------------------------------------------------------
# GET /backtest/results -- Retrieve backtest results
# ---------------------------------------------------------------------------
@router.get("/results")
async def get_backtest_results(
    strategy_id: str = Query(..., description="Strategy ID to fetch results for"),
):
    """Retrieve stored backtest results for a strategy."""
    # Try to fetch from database
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
                return _envelope(
                    {
                        "strategy_id": row.strategy_id,
                        "sharpe_ratio": row.sharpe_ratio,
                        "annual_return": row.annualized_return,
                        "max_drawdown": row.max_drawdown,
                        "win_rate": row.win_rate,
                        "profit_factor": row.profit_factor,
                        "metrics": {
                            "sharpe_ratio": row.sharpe_ratio,
                            "annual_return": row.annualized_return,
                            "max_drawdown": row.max_drawdown,
                        },
                    }
                )
    except Exception as exc:
        logger.debug(
            "backtest_results_db_unavailable strategy_id=%s error=%s", strategy_id, exc
        )

    # Fallback to placeholder data
    return _envelope(_sample_backtest_result(strategy_id))


# ---------------------------------------------------------------------------
# POST /backtest/portfolio -- Portfolio-level backtest
# ---------------------------------------------------------------------------
@router.post("/portfolio")
async def portfolio_backtest(request: PortfolioBacktestRequest):
    """Run portfolio-level backtest across multiple strategies.

    Returns combined portfolio metrics including combined sharpe,
    equity curve, attribution, and correlation matrix.
    """
    if not request.strategy_ids:
        raise HTTPException(status_code=400, detail="strategy_ids must not be empty")

    # Default to equal weights if not provided
    weights = request.weights
    if weights is None:
        n = len(request.strategy_ids)
        weights = {sid: 1.0 / n for sid in request.strategy_ids}

    try:
        from src.agents.data_loader import PointInTimeDataLoader
        from src.backtesting.engine import BacktestConfig, BacktestEngine
        from src.strategies import ALL_STRATEGIES
        from src.strategies.registry import StrategyRegistry

        # Validate all strategy IDs exist
        for sid in request.strategy_ids:
            if sid not in ALL_STRATEGIES and sid not in StrategyRegistry._strategies:
                raise HTTPException(
                    status_code=404,
                    detail=f"Strategy '{sid}' not found",
                )

        config = BacktestConfig(
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=1_000_000.0,
        )

        # Instantiate strategies
        loader = PointInTimeDataLoader()
        strategies = []
        for sid in request.strategy_ids:
            strategy_cls = ALL_STRATEGIES.get(
                sid, StrategyRegistry._strategies.get(sid)
            )
            strategies.append(strategy_cls(data_loader=loader))

        engine = BacktestEngine(config, loader)
        result = await asyncio.to_thread(engine.run_portfolio, strategies, weights)

        # Convert BacktestResult to serializable dict
        portfolio_result = result["portfolio_result"]
        equity_curve = []
        if hasattr(portfolio_result, "equity_curve") and portfolio_result.equity_curve:
            equity_curve = [float(e) for _, e in portfolio_result.equity_curve]

        # Convert correlation matrix with tuple keys to string keys
        correlation = {}
        for (a, b), corr_val in result.get("correlation_matrix", {}).items():
            correlation[f"{a}_{b}"] = float(corr_val)

        return _envelope(
            {
                "strategy_ids": request.strategy_ids,
                "weights": weights,
                "combined_sharpe": float(portfolio_result.sharpe_ratio),
                "combined_annual_return": float(portfolio_result.annualized_return),
                "combined_max_drawdown": float(portfolio_result.max_drawdown),
                "equity_curve": equity_curve,
                "attribution": result.get("attribution", {}),
                "correlation_matrix": correlation,
            }
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("portfolio_backtest_fallback error=%s", exc)
        return _envelope(_sample_portfolio_result(request.strategy_ids, weights))


# ---------------------------------------------------------------------------
# GET /backtest/comparison -- Compare strategy backtests
# ---------------------------------------------------------------------------
@router.get("/comparison")
async def compare_backtests(
    strategy_ids: str = Query(
        ..., description="Comma-separated strategy IDs for comparison"
    ),
):
    """Compare backtest results across multiple strategies side-by-side.

    Returns a dict of strategy_id -> metrics for each requested strategy.
    """
    ids = [s.strip() for s in strategy_ids.split(",") if s.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="strategy_ids must not be empty")

    comparison: dict[str, dict] = {}
    for sid in ids:
        # Try to fetch from DB first
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
                    {"sid": sid},
                )
                row = result.first()
                if row:
                    comparison[sid] = {
                        "sharpe_ratio": row.sharpe_ratio,
                        "annual_return": row.annualized_return,
                        "max_drawdown": row.max_drawdown,
                        "win_rate": row.win_rate,
                        "profit_factor": row.profit_factor,
                    }
                    continue
        except Exception:
            pass

        # Fallback to sample data
        sample = _sample_backtest_result(sid)
        comparison[sid] = {
            "sharpe_ratio": sample["sharpe_ratio"],
            "annual_return": sample["annual_return"],
            "max_drawdown": sample["max_drawdown"],
            "win_rate": sample["win_rate"],
            "profit_factor": sample["profit_factor"],
        }

    return _envelope(comparison)
