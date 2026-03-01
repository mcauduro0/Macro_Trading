"""PMS Pipeline Trigger endpoint.

Provides a manual trigger to run the full PMS daily pipeline without
requiring Dagster. This endpoint orchestrates:

1. Mark-to-Market (MTM) -- refresh all open position prices
2. Signal collection -- aggregate signals from all registered strategies
3. Trade proposal generation -- convert signals into actionable proposals
4. Morning pack generation -- produce the daily briefing

Usage:
    POST /api/v1/pms/pipeline/trigger

This is essential for environments where Dagster is not running
(e.g., docker-compose without the ``dagster`` profile).
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from src.cache import PMSCache, get_pms_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pms/pipeline", tags=["PMS - Pipeline"])


@router.post("/trigger")
async def trigger_pipeline(
    cache: PMSCache = Depends(get_pms_cache),
):
    """Trigger the full PMS daily pipeline manually.

    Runs MTM, signal collection, proposal generation, and morning pack
    generation in sequence. Returns a summary of each step.
    """
    results = {
        "status": "running",
        "date": date.today().isoformat(),
        "steps": {},
    }

    # -----------------------------------------------------------------------
    # Step 1: Mark-to-Market
    # -----------------------------------------------------------------------
    try:
        from src.pms.position_manager import PositionManager

        pm = PositionManager()
        # Hydrate from DB if available
        try:
            from src.pms.db_loader import hydrate_position_manager

            hydrate_position_manager(pm)
        except Exception:
            logger.debug("Pipeline: PM hydration skipped (no DB loader)")

        updated = pm.mark_to_market()
        book = pm.get_book()

        # Cache the book
        try:
            await cache.set_book(book)
        except Exception:
            logger.warning("Pipeline: cache write failed for book")

        results["steps"]["mtm"] = {
            "status": "success",
            "positions_updated": len(updated),
            "total_unrealized_pnl": book.get("summary", {}).get(
                "total_unrealized_pnl_brl", 0.0
            ),
        }
        logger.info("Pipeline MTM: %d positions updated", len(updated))
    except Exception as exc:
        results["steps"]["mtm"] = {"status": "error", "error": str(exc)}
        logger.error("Pipeline MTM failed: %s", exc)

    # -----------------------------------------------------------------------
    # Step 2: Collect aggregated signals
    # -----------------------------------------------------------------------
    signals = []
    try:
        from src.agents.data_loader import PointInTimeDataLoader
        from src.portfolio.signal_aggregator_v2 import SignalAggregatorV2
        from src.strategies import ALL_STRATEGIES

        loader = PointInTimeDataLoader()
        strategy_signals = []
        as_of = date.today()

        for strategy_id, strategy_cls in ALL_STRATEGIES.items():
            try:
                strategy = (
                    strategy_cls(data_loader=loader)
                    if isinstance(strategy_cls, type)
                    else strategy_cls
                )
                if hasattr(strategy, "generate_signals"):
                    sigs = strategy.generate_signals(as_of)
                    if sigs:
                        strategy_signals.extend(
                            sigs if isinstance(sigs, list) else [sigs]
                        )
            except Exception:
                logger.debug("Pipeline: strategy %s failed, skipping", strategy_id)

        if strategy_signals:
            aggregator = SignalAggregatorV2(method="bayesian")
            aggregated = aggregator.aggregate(strategy_signals)

            for r in aggregated:
                signals.append(
                    {
                        "instrument": r.instrument,
                        "asset_class": getattr(r, "asset_class", "UNKNOWN"),
                        "direction": r.direction,
                        "conviction": r.conviction,
                        "signal_source": "aggregator_v2",
                        "strategy_ids": getattr(r, "strategy_ids", []),
                        "suggested_notional_brl": 10_000_000.0,
                    }
                )

        results["steps"]["signals"] = {
            "status": "success",
            "raw_signals": len(strategy_signals),
            "aggregated_signals": len(signals),
        }
        logger.info(
            "Pipeline signals: %d raw -> %d aggregated",
            len(strategy_signals),
            len(signals),
        )
    except Exception as exc:
        results["steps"]["signals"] = {"status": "error", "error": str(exc)}
        logger.error("Pipeline signal collection failed: %s", exc)

    # -----------------------------------------------------------------------
    # Step 3: Generate trade proposals
    # -----------------------------------------------------------------------
    try:
        from src.pms.trade_workflow import TradeWorkflowService

        tws = TradeWorkflowService()
        # Hydrate from DB
        try:
            from src.pms.db_loader import hydrate_trade_workflow

            hydrate_trade_workflow(tws)
        except Exception:
            logger.debug("Pipeline: TWS hydration skipped")

        proposals = tws.generate_proposals_from_signals(signals=signals)

        results["steps"]["proposals"] = {
            "status": "success",
            "proposals_generated": len(proposals),
            "instruments": [p["instrument"] for p in proposals],
        }
        logger.info("Pipeline proposals: %d generated", len(proposals))
    except Exception as exc:
        results["steps"]["proposals"] = {"status": "error", "error": str(exc)}
        logger.error("Pipeline proposal generation failed: %s", exc)

    # -----------------------------------------------------------------------
    # Step 4: Generate morning pack
    # -----------------------------------------------------------------------
    try:
        from src.pms.morning_pack import MorningPackService

        mps = MorningPackService()
        # Hydrate from DB
        try:
            from src.pms.db_loader import hydrate_morning_pack_service

            hydrate_morning_pack_service(mps)
        except Exception:
            logger.debug("Pipeline: MPS hydration skipped")

        today = date.today()
        briefing = mps.generate(briefing_date=today)

        # Cache the briefing
        try:
            await cache.set_morning_pack(today.isoformat(), briefing)
        except Exception:
            logger.warning("Pipeline: cache write failed for morning pack")

        sections_count = len(briefing.get("sections", {}))
        results["steps"]["morning_pack"] = {
            "status": "success",
            "date": today.isoformat(),
            "sections": sections_count,
        }
        logger.info("Pipeline morning pack: %d sections", sections_count)
    except Exception as exc:
        results["steps"]["morning_pack"] = {"status": "error", "error": str(exc)}
        logger.error("Pipeline morning pack failed: %s", exc)

    # -----------------------------------------------------------------------
    # Step 5: Compute and store daily portfolio returns
    # -----------------------------------------------------------------------
    try:
        import numpy as np
        import pandas as pd
        from sqlalchemy import create_engine, text

        from src.agents.data_loader import PointInTimeDataLoader
        from src.core.config import get_settings

        settings = get_settings()
        engine = create_engine(settings.database_url)
        today = date.today()
        ret_loader = PointInTimeDataLoader()

        # Check if table exists
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM portfolio_returns LIMIT 0"))
        except Exception:
            logger.info("Pipeline: portfolio_returns table does not exist yet")
            raise RuntimeError(
                "portfolio_returns table not created — run migration 010"
            )

        # Check if already computed
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM portfolio_returns WHERE return_date = :d"),
                {"d": today},
            ).fetchone()

        if existing:
            results["steps"]["portfolio_returns"] = {
                "status": "skipped",
                "reason": "already_computed",
            }
        else:
            # Load tradeable instruments
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT DISTINCT i.ticker "
                        "FROM instruments i "
                        "INNER JOIN market_data md ON md.instrument_id = i.id "
                        "ORDER BY i.ticker"
                    )
                ).fetchall()
                tradeable = [r[0] for r in rows] if rows else []

            returns_frames = []
            for ticker in tradeable:
                try:
                    md = ret_loader.get_market_data(
                        ticker, as_of_date=today, lookback_days=5
                    )
                    if md is not None and not md.empty and "close" in md.columns:
                        ret = md["close"].pct_change().dropna()
                        ret.index = ret.index.normalize()
                        ret.name = ticker
                        returns_frames.append(ret)
                except Exception:
                    continue

            if returns_frames:
                returns_data = pd.concat(returns_frames, axis=1).dropna()
                if not returns_data.empty:
                    n = returns_data.shape[1]
                    w = np.ones(n) / n
                    daily_return = float(returns_data.iloc[-1].values @ w)

                    with engine.connect() as conn:
                        prev = conn.execute(
                            text(
                                "SELECT cumulative_return FROM portfolio_returns "
                                "ORDER BY return_date DESC LIMIT 1"
                            )
                        ).fetchone()
                    prev_cum = float(prev[0]) if prev else 0.0
                    cumulative_return = (1 + prev_cum) * (1 + daily_return) - 1

                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                "INSERT INTO portfolio_returns "
                                "(return_date, daily_return, cumulative_return, "
                                "n_instruments, weighting_method) "
                                "VALUES (:d, :r, :c, :n, :m) "
                                "ON CONFLICT (return_date) DO UPDATE SET "
                                "daily_return = EXCLUDED.daily_return, "
                                "cumulative_return = EXCLUDED.cumulative_return"
                            ),
                            {
                                "d": today,
                                "r": round(daily_return, 10),
                                "c": round(cumulative_return, 10),
                                "n": n,
                                "m": "equal_weight",
                            },
                        )

                    results["steps"]["portfolio_returns"] = {
                        "status": "success",
                        "daily_return": round(daily_return, 6),
                        "n_instruments": n,
                    }
                    logger.info(
                        "Pipeline portfolio returns: %.6f (%d instruments)",
                        daily_return,
                        n,
                    )
                else:
                    results["steps"]["portfolio_returns"] = {
                        "status": "skipped",
                        "reason": "no_data_after_alignment",
                    }
            else:
                results["steps"]["portfolio_returns"] = {
                    "status": "skipped",
                    "reason": "no_market_data",
                }
    except Exception as exc:
        results["steps"]["portfolio_returns"] = {
            "status": "error",
            "error": str(exc),
        }
        logger.warning("Pipeline portfolio returns failed: %s", exc)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    all_success = all(
        step.get("status") in ("success", "skipped")
        for step in results["steps"].values()
    )
    results["status"] = "success" if all_success else "partial"

    return results


@router.post("/backfill-returns")
async def backfill_portfolio_returns():
    """Backfill portfolio_returns table from all available market data history.

    Computes equal-weight daily returns for every historical date that has
    market data, filling in the portfolio_returns table so that risk
    endpoints (VaR, dashboard, stress) have enough observations to work.

    This is idempotent — existing dates are updated via ON CONFLICT.
    """
    try:
        import numpy as np
        import pandas as pd
        from sqlalchemy import create_engine, text

        from src.agents.data_loader import PointInTimeDataLoader
        from src.core.config import get_settings

        settings = get_settings()
        engine = create_engine(settings.database_url)

        # Verify table exists
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM portfolio_returns LIMIT 0"))
        except Exception:
            raise HTTPException(
                status_code=503,
                detail="portfolio_returns table not created — run migration 010",
            )

        # Load all tradeable instruments
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT DISTINCT i.ticker "
                    "FROM instruments i "
                    "INNER JOIN market_data md ON md.instrument_id = i.id "
                    "ORDER BY i.ticker"
                )
            ).fetchall()
            tradeable = [r[0] for r in rows] if rows else []

        if not tradeable:
            raise HTTPException(
                status_code=503,
                detail="No tradeable instruments with market data found.",
            )

        # Load full history for all instruments
        loader = PointInTimeDataLoader()
        returns_frames = []
        for ticker in tradeable:
            try:
                md = loader.get_market_data(
                    ticker, as_of_date=date.today(), lookback_days=504
                )
                if md is not None and not md.empty and "close" in md.columns:
                    ret = md["close"].pct_change().dropna()
                    ret.index = ret.index.normalize()
                    ret.name = ticker
                    returns_frames.append(ret)
            except Exception:
                continue

        if not returns_frames:
            raise HTTPException(
                status_code=503,
                detail="No market data available for backfill.",
            )

        returns_data = pd.concat(returns_frames, axis=1).dropna()
        if returns_data.empty:
            raise HTTPException(
                status_code=503,
                detail="No aligned returns data after joining instruments.",
            )

        n = returns_data.shape[1]
        w = np.ones(n) / n
        daily_returns = returns_data.values @ w  # shape: (n_days,)
        dates = returns_data.index.date if hasattr(returns_data.index, 'date') else returns_data.index

        # Compute cumulative returns
        cumulative = np.cumprod(1 + daily_returns) - 1

        # Bulk insert
        inserted = 0
        with engine.begin() as conn:
            for i, (d, r, c) in enumerate(zip(dates, daily_returns, cumulative)):
                conn.execute(
                    text(
                        "INSERT INTO portfolio_returns "
                        "(return_date, daily_return, cumulative_return, "
                        "n_instruments, weighting_method) "
                        "VALUES (:d, :r, :c, :n, :m) "
                        "ON CONFLICT (return_date) DO UPDATE SET "
                        "daily_return = EXCLUDED.daily_return, "
                        "cumulative_return = EXCLUDED.cumulative_return"
                    ),
                    {
                        "d": d,
                        "r": round(float(r), 10),
                        "c": round(float(c), 10),
                        "n": n,
                        "m": "equal_weight",
                    },
                )
                inserted += 1

        # Verify final count
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM portfolio_returns")
            ).scalar()

        return {
            "status": "success",
            "rows_inserted": inserted,
            "total_rows": count,
            "n_instruments": n,
            "date_range": {
                "first": str(dates[0]),
                "last": str(dates[-1]),
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Backfill portfolio returns failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Backfill failed: {exc}",
        )
