"""Bronze layer Dagster asset definitions for data connectors.

Each asset wraps one of the 6 data source connectors, executing the async
fetch-and-store pipeline via asyncio.run().  Assets use daily partitions
(from 2010-01-01) for date-range backfill support and a retry policy of
3 attempts with 30-second exponential backoff.

Bronze assets are the entry points of the Dagster dependency graph.
Silver assets depend on these to run transforms.
"""

import asyncio
from datetime import date

from dagster import (
    AssetExecutionContext,
    Backoff,
    DailyPartitionsDefinition,
    RetryPolicy,
    asset,
)

from src.connectors import (
    B3MarketDataConnector,
    BcbPtaxConnector,
    BcbSgsConnector,
    FredConnector,
    TreasuryGovConnector,
    YahooFinanceConnector,
)

# Shared configuration
_daily_partitions = DailyPartitionsDefinition(start_date="2010-01-01")
_retry_policy = RetryPolicy(
    max_retries=3,
    delay=30,
    backoff=Backoff.EXPONENTIAL,
)


def _partition_date(context: AssetExecutionContext) -> date:
    """Extract the partition date from Dagster context.

    Falls back to today if no partition key is available (e.g. ad-hoc runs).
    """
    if context.has_partition_key:
        return date.fromisoformat(context.partition_key)
    return date.today()


async def _run_connector(connector_class: type, start: date, end: date) -> int:
    """Instantiate a connector within its async context manager and run it.

    Args:
        connector_class: A BaseConnector subclass.
        start: Inclusive start date for fetch.
        end: Inclusive end date for fetch.

    Returns:
        Number of records inserted.
    """
    async with connector_class() as conn:
        return await conn.run(start, end)


# ---------------------------------------------------------------------------
# Bronze Assets
# ---------------------------------------------------------------------------

@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest BCB SGS macro series (IPCA, SELIC, CDI, etc.)",
)
def bronze_bcb_sgs(context: AssetExecutionContext) -> dict:
    """Fetch BCB SGS macro series data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching BCB SGS data for {as_of}")
    try:
        records = asyncio.run(_run_connector(BcbSgsConnector, as_of, as_of))
        context.log.info(f"BCB SGS: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"BCB SGS fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest FRED US macro series (CPI, unemployment, GDP, etc.)",
)
def bronze_fred(context: AssetExecutionContext) -> dict:
    """Fetch FRED US macro series data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching FRED data for {as_of}")
    try:
        records = asyncio.run(_run_connector(FredConnector, as_of, as_of))
        context.log.info(f"FRED: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"FRED fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest Yahoo Finance market data (equities, indices, commodities)",
)
def bronze_yahoo(context: AssetExecutionContext) -> dict:
    """Fetch Yahoo Finance market data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching Yahoo Finance data for {as_of}")
    try:
        records = asyncio.run(_run_connector(YahooFinanceConnector, as_of, as_of))
        context.log.info(f"Yahoo: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"Yahoo Finance fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest BCB PTAX FX fixing rates (BRL/USD, BRL/EUR, etc.)",
)
def bronze_bcb_ptax(context: AssetExecutionContext) -> dict:
    """Fetch BCB PTAX FX fixing rates for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching BCB PTAX data for {as_of}")
    try:
        records = asyncio.run(_run_connector(BcbPtaxConnector, as_of, as_of))
        context.log.info(f"BCB PTAX: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"BCB PTAX fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest B3 market data (DI futures curve, NTN-B prices)",
)
def bronze_b3_market_data(context: AssetExecutionContext) -> dict:
    """Fetch B3 market data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching B3 market data for {as_of}")
    try:
        records = asyncio.run(_run_connector(B3MarketDataConnector, as_of, as_of))
        context.log.info(f"B3: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"B3 market data fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest US Treasury yield curves from TreasuryDirect.gov",
)
def bronze_treasury_gov(context: AssetExecutionContext) -> dict:
    """Fetch US Treasury yield curve data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching Treasury.gov data for {as_of}")
    try:
        records = asyncio.run(_run_connector(TreasuryGovConnector, as_of, as_of))
        context.log.info(f"Treasury: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"Treasury.gov fetch failed: {exc}")
        raise
