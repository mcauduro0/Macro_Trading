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

        from src.agents.data_loader import PointInTimeDataLoader
        from src.backtesting.engine import BacktestConfig, BacktestEngine

        config = BacktestConfig(
            start_date=start,
            end_date=end,
            initial_capital=1_000_000.0,
        )

        strategy_cls = ALL_STRATEGIES.get(
            request.strategy_id,
            StrategyRegistry._strategies.get(request.strategy_id),
        )
        loader = PointInTimeDataLoader()
        strategy = strategy_cls(data_loader=loader)

        engine = BacktestEngine(config, loader)
        result = await asyncio.to_thread(engine.run, strategy)

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
    except ImportError as exc:
        logger.error("backtest_run import_error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Backtest engine dependencies unavailable: {exc}. "
            "Ensure all packages are installed (pip install -e '.[dev]').",
        )
    except Exception as exc:
        logger.error("backtest_run failed strategy_id=%s: %s", request.strategy_id, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Backtest execution failed for '{request.strategy_id}': {exc}",
        )


# ---------------------------------------------------------------------------
# GET /backtest/results -- Retrieve backtest results
# ---------------------------------------------------------------------------
@router.get("/results")
async def get_backtest_results(
    strategy_id: str = Query(..., description="Strategy ID to fetch results for"),
):
    """Retrieve stored backtest results for a strategy."""
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

        raise HTTPException(
            status_code=404,
            detail=f"No backtest results found for strategy '{strategy_id}'. "
            "Run a backtest first via POST /backtest/run.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("backtest_results_db error strategy_id=%s: %s", strategy_id, exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable for backtest results: {exc}. "
            "Ensure TimescaleDB is running and migrations are applied.",
        )


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

    weights = request.weights
    if weights is None:
        n = len(request.strategy_ids)
        weights = {sid: 1.0 / n for sid in request.strategy_ids}

    try:
        from src.agents.data_loader import PointInTimeDataLoader
        from src.backtesting.engine import BacktestConfig, BacktestEngine
        from src.strategies import ALL_STRATEGIES
        from src.strategies.registry import StrategyRegistry

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

        loader = PointInTimeDataLoader()
        strategies = []
        for sid in request.strategy_ids:
            strategy_cls = ALL_STRATEGIES.get(
                sid, StrategyRegistry._strategies.get(sid)
            )
            strategies.append(strategy_cls(data_loader=loader))

        engine = BacktestEngine(config, loader)
        result = await asyncio.to_thread(engine.run_portfolio, strategies, weights)

        portfolio_result = result["portfolio_result"]
        equity_curve = []
        if hasattr(portfolio_result, "equity_curve") and portfolio_result.equity_curve:
            equity_curve = [float(e) for _, e in portfolio_result.equity_curve]

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
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Portfolio backtest dependencies unavailable: {exc}",
        )
    except Exception as exc:
        logger.error("portfolio_backtest failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Portfolio backtest failed: {exc}",
        )


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
    missing: list[str] = []

    try:
        from sqlalchemy import text

        from src.core.database import async_session_factory

        for sid in ids:
            async with async_session_factory() as session:
                result = await session.execute(
                    text(
                        "SELECT strategy_id, sharpe_ratio, annualized_return, "
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
                else:
                    missing.append(sid)

    except Exception as exc:
        logger.error("backtest_comparison_db error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable for backtest comparison: {exc}. "
            "Ensure TimescaleDB is running.",
        )

    if missing:
        return _envelope(
            {
                "comparison": comparison,
                "missing_strategies": missing,
                "note": f"No backtest results found for: {', '.join(missing)}. "
                "Run backtests first via POST /backtest/run.",
            }
        )

    return _envelope(comparison)
