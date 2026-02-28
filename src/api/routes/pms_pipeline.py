"""PMS Pipeline Trigger endpoint.

Provides a manual trigger to run the full PMS daily pipeline without
requiring Dagster. This endpoint orchestrates:

1. Mark-to-Market (MTM) -- refresh all open position prices
2. Agent execution -- run all 5 analytical agents to generate signals
3. Strategy signal collection -- aggregate strategy signals
4. Trade proposal generation -- convert signals into actionable proposals
5. Morning pack generation -- produce the daily briefing with all services wired

Usage:
    POST /api/v1/pms/pipeline/trigger

This is essential for environments where Dagster is not running
(e.g., docker-compose without the ``dagster`` profile).
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends

from src.cache import PMSCache, get_pms_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pms/pipeline", tags=["PMS - Pipeline"])


def _ensure_agents_registered() -> None:
    """Register all 5 agents in the AgentRegistry if not already present."""
    from src.agents.registry import AgentRegistry

    if AgentRegistry.list_registered():
        return  # Already registered

    from src.agents.cross_asset_agent import CrossAssetAgent
    from src.agents.fiscal_agent import FiscalAgent
    from src.agents.fx_agent import FxEquilibriumAgent
    from src.agents.inflation_agent import InflationAgent
    from src.agents.monetary_agent import MonetaryPolicyAgent

    for agent_cls in [
        InflationAgent,
        MonetaryPolicyAgent,
        FiscalAgent,
        FxEquilibriumAgent,
        CrossAssetAgent,
    ]:
        try:
            agent = agent_cls()
            AgentRegistry.register(agent)
        except (ValueError, Exception) as exc:
            logger.debug("Agent %s already registered or failed: %s", agent_cls, exc)


@router.post("/trigger")
async def trigger_pipeline(
    cache: PMSCache = Depends(get_pms_cache),
):
    """Trigger the full PMS daily pipeline manually.

    Runs MTM, agents, signal collection, proposal generation, and morning pack
    generation in sequence. Returns a summary of each step.
    """
    results = {
        "status": "running",
        "date": date.today().isoformat(),
        "steps": {},
    }

    # -----------------------------------------------------------------------
    # Step 0: Ensure agents are registered
    # -----------------------------------------------------------------------
    try:
        _ensure_agents_registered()
        from src.agents.registry import AgentRegistry

        results["steps"]["agent_registration"] = {
            "status": "success",
            "registered": AgentRegistry.list_registered(),
        }
    except Exception as exc:
        results["steps"]["agent_registration"] = {
            "status": "error",
            "error": str(exc),
        }
        logger.error("Pipeline agent registration failed: %s", exc)

    # -----------------------------------------------------------------------
    # Step 1: Mark-to-Market
    # -----------------------------------------------------------------------
    pm = None
    try:
        from src.pms.position_manager import PositionManager

        pm = PositionManager()
        try:
            from src.pms.db_loader import hydrate_position_manager

            hydrate_position_manager(pm)
        except Exception:
            logger.debug("Pipeline: PM hydration skipped (no DB loader)")

        updated = pm.mark_to_market()
        book = pm.get_book()

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
    # Step 2: Run all agents to generate fresh signals
    # -----------------------------------------------------------------------
    try:
        from src.agents.registry import AgentRegistry

        as_of = date.today()
        agent_reports = AgentRegistry.run_all(as_of)

        results["steps"]["agents"] = {
            "status": "success",
            "agents_run": len(agent_reports),
            "agents": list(agent_reports.keys()),
        }
        logger.info("Pipeline agents: %d agents run", len(agent_reports))
    except Exception as exc:
        results["steps"]["agents"] = {"status": "error", "error": str(exc)}
        logger.error("Pipeline agents failed: %s", exc)

    # -----------------------------------------------------------------------
    # Step 3: Collect aggregated strategy signals
    # -----------------------------------------------------------------------
    signals = []
    aggregator = None
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

        aggregator = SignalAggregatorV2(method="bayesian")
        if strategy_signals:
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
    # Step 4: Generate trade proposals
    # -----------------------------------------------------------------------
    tws = None
    try:
        from src.pms.trade_workflow import TradeWorkflowService

        tws = TradeWorkflowService()
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
    # Step 5: Generate morning pack with ALL services wired
    # -----------------------------------------------------------------------
    try:
        from src.pms.morning_pack import MorningPackService

        mps = MorningPackService(
            position_manager=pm,
            trade_workflow=tws,
            signal_aggregator=aggregator,
        )
        # Hydrate with existing briefings from DB
        try:
            from src.pms.db_loader import hydrate_morning_pack_service

            hydrate_morning_pack_service(mps)
        except Exception:
            logger.debug("Pipeline: MPS hydration skipped")

        today = date.today()
        briefing = mps.generate(briefing_date=today, force=True)

        # Cache the briefing
        try:
            await cache.set_morning_pack(today.isoformat(), briefing)
        except Exception:
            logger.warning("Pipeline: cache write failed for morning pack")

        # Count populated sections (not "unavailable")
        populated = 0
        for key in [
            "trade_proposals",
            "market_snapshot",
            "agent_views",
            "regime",
            "top_signals",
            "signal_changes",
            "portfolio_state",
            "macro_narrative",
        ]:
            val = briefing.get(key)
            if isinstance(val, dict) and val.get("status") == "unavailable":
                continue
            if val:
                populated += 1

        results["steps"]["morning_pack"] = {
            "status": "success",
            "date": today.isoformat(),
            "populated_sections": populated,
            "total_sections": 8,
        }
        logger.info("Pipeline morning pack: %d/%d sections populated", populated, 8)
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
