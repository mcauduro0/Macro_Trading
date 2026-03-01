"""PMS (Portfolio Management System) Dagster asset definitions.

Five assets in the ``pms`` group automate the daily PMS workflow:

1. ``pms_mark_to_market`` -- Mark all open positions to current prices
2. ``pms_trade_proposals`` -- Generate trade proposals from aggregated signals
3. ``pms_morning_pack`` -- Generate the daily morning briefing
4. ``pms_performance_attribution`` -- Compute daily performance attribution
5. ``pms_portfolio_returns`` -- Compute and persist daily portfolio returns

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


def _collect_aggregated_signals(context: AssetExecutionContext) -> list[dict]:
    """Collect signals from all registered strategies via SignalAggregatorV2.

    Returns a list of signal dicts suitable for TradeWorkflowService.
    """
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
                context.log.warning(
                    f"Strategy {strategy_id} signal generation failed, skipping"
                )

        if not strategy_signals:
            context.log.warning("No strategy signals collected")
            return []

        aggregator = SignalAggregatorV2(method="bayesian")
        results = aggregator.aggregate(strategy_signals)

        # Convert AggregatedSignalV2 objects to dicts for TradeWorkflowService
        signal_dicts = []
        for r in results:
            signal_dicts.append({
                "instrument": r.instrument,
                "asset_class": getattr(r, "asset_class", "UNKNOWN"),
                "direction": r.direction,
                "conviction": r.conviction,
                "signal_source": "aggregator_v2",
                "strategy_ids": getattr(r, "strategy_ids", []),
                "suggested_notional_brl": 10_000_000.0,
            })

        context.log.info(
            f"Collected {len(signal_dicts)} aggregated signals from "
            f"{len(strategy_signals)} raw strategy signals"
        )
        return signal_dicts

    except Exception as exc:
        context.log.warning(f"Signal collection failed: {exc}")
        return []


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

    Collects signals from all registered strategies via
    SignalAggregatorV2, then converts them into trade proposals.
    """
    try:
        tws = TradeWorkflowService()

        # Collect real signals from strategy registry
        signals = _collect_aggregated_signals(context)
        context.log.info(f"Collected {len(signals)} signals for proposal generation")

        proposals = tws.generate_proposals_from_signals(signals=signals)
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


# ---------------------------------------------------------------------------
# Asset 5: Portfolio Returns
# ---------------------------------------------------------------------------


@asset(
    group_name="pms",
    retry_policy=_retry_policy,
    deps=["pms_mark_to_market"],
    description="Compute and persist daily portfolio returns for risk calculations",
)
def pms_portfolio_returns(context: AssetExecutionContext) -> Output:
    """Compute daily portfolio-level returns and store in portfolio_returns table.

    Uses current position weights with market data returns. Falls back to
    equal-weight returns across all tradeable instruments when positions use
    curve/derivative tickers without OHLCV data.

    Risk endpoints (VaR, stress, limits, dashboard) read from this table.
    """
    import numpy as np
    import pandas as pd
    from datetime import date as _date_type
    from sqlalchemy import create_engine, text

    from src.agents.data_loader import PointInTimeDataLoader
    from src.core.config import get_settings

    today = _date_type.today()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    loader = PointInTimeDataLoader()

    # Check if today's return already computed
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT 1 FROM portfolio_returns WHERE return_date = :d"),
            {"d": today},
        ).fetchone()
        if existing:
            context.log.info(f"Portfolio return for {today} already exists, skipping")
            return Output(
                value={"status": "skipped", "date": str(today)},
                metadata={"date": str(today), "reason": "already_computed"},
            )

    # Try position-weighted returns
    weights: dict[str, float] = {}
    try:
        pm = PositionManager()
        book = pm.get_book()
        positions = book.get("positions", [])
        if positions:
            weights = {p["instrument"]: p.get("weight", 0.0) for p in positions}
    except Exception:
        pass

    returns_frames: list[pd.Series] = []
    weighting_method = "position_weighted"

    if weights:
        for ticker in list(weights.keys()):
            try:
                md = loader.get_market_data(ticker, as_of_date=today, lookback_days=5)
                if md is not None and not md.empty and "close" in md.columns:
                    ret = md["close"].pct_change().dropna()
                    ret.name = ticker
                    returns_frames.append(ret)
            except Exception:
                continue

    # Fallback: all tradeable instruments, equal weight
    if not returns_frames:
        weighting_method = "equal_weight"
        try:
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
        except Exception:
            tradeable = []

        for ticker in tradeable:
            try:
                md = loader.get_market_data(ticker, as_of_date=today, lookback_days=5)
                if md is not None and not md.empty and "close" in md.columns:
                    ret = md["close"].pct_change().dropna()
                    ret.name = ticker
                    returns_frames.append(ret)
            except Exception:
                continue

    if not returns_frames:
        context.log.warning("No market data available for portfolio returns")
        return Output(
            value={"status": "no_data", "date": str(today)},
            metadata={"date": str(today), "reason": "no_market_data"},
        )

    returns_data = pd.concat(returns_frames, axis=1).dropna()
    if returns_data.empty:
        context.log.warning("Returns data empty after aligning instruments")
        return Output(
            value={"status": "no_data", "date": str(today)},
            metadata={"date": str(today), "reason": "empty_returns"},
        )

    n = returns_data.shape[1]
    if weighting_method == "position_weighted" and weights:
        w = np.array([weights.get(col, 0.0) for col in returns_data.columns])
    else:
        w = np.ones(n) / n

    # Take last row (today's return)
    daily_return = float(returns_data.iloc[-1].values @ w)

    # Load cumulative return
    with engine.connect() as conn:
        prev = conn.execute(
            text(
                "SELECT cumulative_return FROM portfolio_returns "
                "ORDER BY return_date DESC LIMIT 1"
            )
        ).fetchone()
        prev_cum = float(prev[0]) if prev else 0.0

    cumulative_return = (1 + prev_cum) * (1 + daily_return) - 1

    # Insert
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO portfolio_returns "
                "(return_date, daily_return, cumulative_return, n_instruments, weighting_method) "
                "VALUES (:d, :r, :c, :n, :m) "
                "ON CONFLICT (return_date) DO UPDATE SET "
                "daily_return = EXCLUDED.daily_return, "
                "cumulative_return = EXCLUDED.cumulative_return, "
                "n_instruments = EXCLUDED.n_instruments"
            ),
            {
                "d": today,
                "r": round(daily_return, 10),
                "c": round(cumulative_return, 10),
                "n": n,
                "m": weighting_method,
            },
        )

    context.log.info(
        f"Portfolio return stored: {today} = {daily_return:.6f} "
        f"({weighting_method}, {n} instruments)"
    )

    return Output(
        value={
            "status": "success",
            "date": str(today),
            "daily_return": round(daily_return, 6),
        },
        metadata={
            "date": str(today),
            "daily_return": round(daily_return, 6),
            "cumulative_return": round(cumulative_return, 6),
            "n_instruments": n,
            "weighting_method": weighting_method,
        },
    )
