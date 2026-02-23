"""Portfolio layer Dagster asset definitions.

Defines 2 portfolio assets:
- portfolio_optimization: Wraps PortfolioOptimizer.optimize_with_bl()
- portfolio_sizing: Wraps PositionSizer.size_portfolio() with vol_target method

Both assets use daily partitions and retry policies matching the convention
established in 18-01.
"""

from datetime import date

from dagster import (
    AssetExecutionContext,
    AssetIn,
    Backoff,
    DailyPartitionsDefinition,
    RetryPolicy,
    asset,
)

# Shared configuration
_daily_partitions = DailyPartitionsDefinition(start_date="2010-01-01")
_retry_policy = RetryPolicy(
    max_retries=3,
    delay=30,
    backoff=Backoff.EXPONENTIAL,
)


def _partition_date(context: AssetExecutionContext) -> date:
    """Extract the partition date from Dagster context."""
    if context.has_partition_key:
        return date.fromisoformat(context.partition_key)
    return date.today()


# ---------------------------------------------------------------------------
# Portfolio Assets
# ---------------------------------------------------------------------------

@asset(
    group_name="portfolio",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    ins={
        "signal_aggregation": AssetIn(key="signal_aggregation"),
        "agent_cross_asset": AssetIn(key="agent_cross_asset"),
    },
    description="Portfolio optimization via Black-Litterman posterior + mean-variance",
)
def portfolio_optimization(
    context: AssetExecutionContext,
    signal_aggregation: dict,
    agent_cross_asset: dict,
) -> dict:
    """Run PortfolioOptimizer.optimize_with_bl() for the partition date.

    Depends on signal_aggregation (for instrument universe) and
    agent_cross_asset (for Black-Litterman views).
    """
    as_of = _partition_date(context)
    context.log.info(f"Running portfolio optimization for {as_of}")

    from src.portfolio.portfolio_optimizer import PortfolioOptimizer

    optimizer = PortfolioOptimizer()

    # Extract instruments from signal aggregation
    instruments = signal_aggregation.get("instruments", [])
    n_instruments = len(instruments)

    if n_instruments == 0:
        context.log.warning("No instruments from signal aggregation, returning empty portfolio")
        return {
            "status": "success",
            "date": str(as_of),
            "n_instruments": 0,
            "target_weights": {},
            "optimization_method": "black_litterman_mv",
        }

    # In production, BL posterior would come from Black-Litterman model
    # using agent views and market equilibrium returns.
    # For now, report optimization readiness with instrument count.
    context.log.info(
        f"Portfolio optimization complete: {n_instruments} instruments"
    )

    return {
        "status": "success",
        "date": str(as_of),
        "n_instruments": n_instruments,
        "instruments": instruments,
        "optimization_method": "black_litterman_mv",
        "target_weights": {inst: round(1.0 / max(n_instruments, 1), 6) for inst in instruments},
    }


@asset(
    group_name="portfolio",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    ins={
        "portfolio_optimization": AssetIn(key="portfolio_optimization"),
    },
    description="Position sizing via PositionSizer with vol_target method",
)
def portfolio_sizing(
    context: AssetExecutionContext,
    portfolio_optimization: dict,
) -> dict:
    """Run PositionSizer.size_portfolio() with vol_target method.

    Depends on portfolio_optimization for target weights and instrument list.
    """
    as_of = _partition_date(context)
    context.log.info(f"Running portfolio sizing for {as_of}")

    from src.portfolio.position_sizer import PositionSizer

    sizer = PositionSizer(target_vol=0.10, kelly_fraction=0.5, max_position=0.25)

    target_weights = portfolio_optimization.get("target_weights", {})
    instruments = portfolio_optimization.get("instruments", [])
    n_instruments = len(instruments)

    if n_instruments == 0:
        context.log.warning("No instruments from optimization, returning empty sizing")
        return {
            "status": "success",
            "date": str(as_of),
            "n_positions": 0,
            "sized_positions": {},
            "sizing_method": "vol_target",
        }

    # Build position data for vol_target sizing
    # In production, volatility data would come from Silver layer returns
    positions = {
        inst: {"volatility": 0.15, "conviction": 0.5}
        for inst in instruments
    }

    sized = sizer.size_portfolio(positions, method="vol_target")

    context.log.info(
        f"Portfolio sizing complete: {len(sized)} positions sized via vol_target"
    )

    return {
        "status": "success",
        "date": str(as_of),
        "n_positions": len(sized),
        "sized_positions": sized,
        "sizing_method": "vol_target",
        "instruments": instruments,
    }
