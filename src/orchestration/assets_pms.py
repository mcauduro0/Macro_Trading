"""PMS (Portfolio Management System) Dagster asset definitions.

Four assets in the ``pms`` group automate the daily PMS workflow:

1. ``pms_mark_to_market`` -- Mark all open positions to current prices
2. ``pms_trade_proposals`` -- Generate trade proposals from aggregated signals
3. ``pms_morning_pack`` -- Generate the daily morning briefing
4. ``pms_performance_attribution`` -- Compute daily performance attribution

Each asset warms the Redis cache after completing its work so the manager
sees fresh data instantly via the dashboard.  Two scheduled runs drive these
assets:

- **EOD** (21:00 UTC / 18:00 BRT): MTM + attribution
- **Pre-open** (09:30 UTC / 06:30 BRT): MTM + proposals + morning pack
"""

import asyncio
import logging
from datetime import date

from dagster import (
    AssetExecutionContext,
    Output,
    RetryPolicy,
    asset,
)

from src.cache.pms_cache import PMSCache
from src.core.redis import get_redis
from src.pms.attribution import PerformanceAttributionEngine
from src.pms.morning_pack import MorningPackService
from src.pms.position_manager import PositionManager
from src.pms.trade_workflow import TradeWorkflowService

logger = logging.getLogger(__name__)

# Shared retry policy for transient failures (network, DB, Redis)
_retry_policy = RetryPolicy(max_retries=2, delay=30)


async def _warm_cache_book(book_data: dict) -> None:
    """Write-through: cache the portfolio book in Redis."""
    redis = await get_redis()
    cache = PMSCache(redis)
    await cache.set_book(book_data)


async def _warm_cache_morning_pack(date_key: str, briefing_data: dict) -> None:
    """Write-through: cache the morning pack briefing in Redis."""
    redis = await get_redis()
    cache = PMSCache(redis)
    await cache.set_morning_pack(date_key, briefing_data)


async def _warm_cache_attribution(period_key: str, attribution_data: dict) -> None:
    """Write-through: cache attribution results in Redis."""
    redis = await get_redis()
    cache = PMSCache(redis)
    await cache.set_attribution(period_key, attribution_data)


# ---------------------------------------------------------------------------
# Asset 1: Mark-to-Market
# ---------------------------------------------------------------------------


@asset(
    group_name="pms",
    retry_policy=_retry_policy,
    description="Mark-to-market all open positions using latest prices",
)
def pms_mark_to_market(context: AssetExecutionContext) -> Output:
    """Mark all open positions to current market prices.

    After MTM completes, the updated book is written to Redis so the
    dashboard shows near-real-time data without hitting the DB.
    """
    try:
        pm = PositionManager()
        updated_positions = pm.mark_to_market()
        book = pm.get_book()

        positions_updated = len(updated_positions)
        total_pnl = book.get("summary", {}).get("total_unrealized_pnl_brl", 0.0)

        # Warm Redis cache with fresh book data
        asyncio.run(_warm_cache_book(book))

        context.log.info(
            f"MTM complete: {positions_updated} positions updated, "
            f"total unrealized P&L: {total_pnl:,.2f} BRL"
        )

        return Output(
            value={"status": "success", "positions_updated": positions_updated},
            metadata={
                "positions_updated": positions_updated,
                "total_unrealized_pnl": total_pnl,
            },
        )
    except Exception as exc:
        context.log.error(f"MTM failed: {exc}")
        raise


# ---------------------------------------------------------------------------
# Asset 2: Trade Proposals
# ---------------------------------------------------------------------------


@asset(
    group_name="pms",
    retry_policy=_retry_policy,
    deps=["pms_mark_to_market"],
    description="Generate trade proposals from aggregated signals",
)
def pms_trade_proposals(context: AssetExecutionContext) -> Output:
    """Generate trade proposals from the latest aggregated signals.

    Depends on ``pms_mark_to_market`` so proposals reflect current
    portfolio state and avoid stale position data.
    """
    try:
        tws = TradeWorkflowService()
        # Generate proposals from signals (empty list = use internal signals)
        proposals = tws.generate_proposals_from_signals(signals=[])
        proposals_count = len(proposals)

        context.log.info(f"Trade proposals generated: {proposals_count}")

        return Output(
            value={"status": "success", "proposals_generated": proposals_count},
            metadata={
                "proposals_generated": proposals_count,
            },
        )
    except Exception as exc:
        context.log.error(f"Trade proposal generation failed: {exc}")
        raise


# ---------------------------------------------------------------------------
# Asset 3: Morning Pack
# ---------------------------------------------------------------------------


@asset(
    group_name="pms",
    retry_policy=_retry_policy,
    deps=["pms_mark_to_market", "pms_trade_proposals"],
    description="Generate daily morning pack briefing",
)
def pms_morning_pack(context: AssetExecutionContext) -> Output:
    """Generate the daily morning pack briefing.

    Depends on both ``pms_mark_to_market`` and ``pms_trade_proposals``
    so the briefing includes fresh positions and pending proposals.
    After generation, the briefing is cached in Redis.
    """
    try:
        mps = MorningPackService()
        today = date.today()
        briefing = mps.generate(briefing_date=today)

        today_str = today.isoformat()
        sections_count = len(briefing.get("sections", {}))

        # Warm Redis cache with fresh briefing
        asyncio.run(_warm_cache_morning_pack(today_str, briefing))

        context.log.info(
            f"Morning pack generated for {today_str}: " f"{sections_count} sections"
        )

        return Output(
            value={"status": "success", "date": today_str},
            metadata={
                "date": today_str,
                "sections_count": sections_count,
            },
        )
    except Exception as exc:
        context.log.error(f"Morning pack generation failed: {exc}")
        raise


# ---------------------------------------------------------------------------
# Asset 4: Performance Attribution
# ---------------------------------------------------------------------------


@asset(
    group_name="pms",
    retry_policy=_retry_policy,
    deps=["pms_mark_to_market"],
    description="Compute daily performance attribution",
)
def pms_performance_attribution(context: AssetExecutionContext) -> Output:
    """Compute daily performance attribution across all dimensions.

    Depends on ``pms_mark_to_market`` for fresh P&L data.
    After computation, results are cached in Redis.
    """
    try:
        engine = PerformanceAttributionEngine()
        attribution = engine.compute_for_period("daily")

        today_str = date.today().isoformat()
        total_pnl = attribution.get("total_pnl_brl", 0.0)
        dimensions = len(attribution.get("by_strategy", []))

        # Warm Redis cache with attribution results
        period_key = f"daily_{today_str}"
        asyncio.run(_warm_cache_attribution(period_key, attribution))

        context.log.info(
            f"Attribution computed for {today_str}: "
            f"{dimensions} strategy dimensions, total P&L: {total_pnl:,.2f} BRL"
        )

        return Output(
            value={"status": "success", "date": today_str},
            metadata={
                "date": today_str,
                "total_pnl": total_pnl,
            },
        )
    except Exception as exc:
        context.log.error(f"Performance attribution failed: {exc}")
        raise
