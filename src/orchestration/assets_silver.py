"""Silver layer Dagster asset definitions for data transforms.

Silver assets depend on Bronze assets and wrap existing transform logic:
curves (Nelson-Siegel, interpolation), returns/vol/z-score computation,
and macro indicator calculations.

These are the intermediate processing layer between raw ingestion (Bronze)
and analytical agents (Agent layer).
"""

from datetime import date

from dagster import (
    AssetExecutionContext,
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
# Silver Assets
# ---------------------------------------------------------------------------


@asset(
    group_name="silver",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    deps=["bronze_b3_market_data", "bronze_treasury_gov"],
    description="Compute yield curve transforms: Nelson-Siegel fitting, interpolation, spread calculations",
)
def silver_curves(context: AssetExecutionContext) -> dict:
    """Run curve transforms on B3 DI and US Treasury data.

    Depends on bronze_b3_market_data (DI futures curve) and
    bronze_treasury_gov (US yield curves) being materialized first.
    """
    as_of = _partition_date(context)
    context.log.info(f"Computing curve transforms for {as_of}")

    from src.transforms.curves import CurveTransform

    transform = CurveTransform()
    result = transform.run(as_of)
    context.log.info(f"Curve transforms complete: {result}")
    return {"status": "success", "date": str(as_of), "result": str(result)}


@asset(
    group_name="silver",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    deps=["bronze_yahoo"],
    description="Compute returns, volatility, and z-score series from market data",
)
def silver_returns(context: AssetExecutionContext) -> dict:
    """Compute returns, rolling volatility, and z-scores from Yahoo data.

    Depends on bronze_yahoo being materialized first.
    """
    as_of = _partition_date(context)
    context.log.info(f"Computing returns/vol/z-scores for {as_of}")

    from src.transforms.returns import ReturnsTransform

    transform = ReturnsTransform()
    result = transform.run(as_of)
    context.log.info(f"Returns transforms complete: {result}")
    return {"status": "success", "date": str(as_of), "result": str(result)}


@asset(
    group_name="silver",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    deps=["bronze_bcb_sgs", "bronze_fred"],
    description="Compute macro indicator transforms from BCB and FRED data",
)
def silver_macro(context: AssetExecutionContext) -> dict:
    """Compute macro indicator calculations from BCB SGS and FRED data.

    Depends on bronze_bcb_sgs and bronze_fred being materialized first.
    """
    as_of = _partition_date(context)
    context.log.info(f"Computing macro transforms for {as_of}")

    from src.transforms.macro import MacroTransform

    transform = MacroTransform()
    result = transform.run(as_of)
    context.log.info(f"Macro transforms complete: {result}")
    return {"status": "success", "date": str(as_of), "result": str(result)}
