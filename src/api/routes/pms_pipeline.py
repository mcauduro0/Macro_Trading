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
    # Summary
    # -----------------------------------------------------------------------
    all_success = all(
        step.get("status") == "success" for step in results["steps"].values()
    )
    results["status"] = "success" if all_success else "partial"

    return results
