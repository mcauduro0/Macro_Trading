"""Bronze layer Dagster asset definitions for all 15 data connectors.

Each asset wraps one data source connector, executing the async fetch-and-store
pipeline via asyncio.run().  Assets use daily partitions (from 2010-01-01)
for date-range backfill support and a retry policy of 3 attempts with
30-second exponential backoff.

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
    AnbimaConnector,
    B3MarketDataConnector,
    BcbFocusConnector,
    BcbFxFlowConnector,
    BcbPtaxConnector,
    BcbSgsConnector,
    CftcCotConnector,
    FmpTreasuryConnector,
    FredConnector,
    IbgeSidraConnector,
    OecdSdmxConnector,
    StnFiscalConnector,
    TradingEconDiCurveConnector,
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


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest BCB Focus market consensus forecasts (IPCA, SELIC, GDP, etc.)",
)
def bronze_bcb_focus(context: AssetExecutionContext) -> dict:
    """Fetch BCB Focus survey consensus forecasts for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching BCB Focus data for {as_of}")
    try:
        records = asyncio.run(_run_connector(BcbFocusConnector, as_of, as_of))
        context.log.info(f"BCB Focus: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"BCB Focus fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest BCB FX flow decomposition (commercial, financial, interbank)",
)
def bronze_bcb_fx_flow(context: AssetExecutionContext) -> dict:
    """Fetch BCB FX flow data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching BCB FX Flow data for {as_of}")
    try:
        records = asyncio.run(_run_connector(BcbFxFlowConnector, as_of, as_of))
        context.log.info(f"BCB FX Flow: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"BCB FX Flow fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest IBGE SIDRA IPCA components by category",
)
def bronze_ibge_sidra(context: AssetExecutionContext) -> dict:
    """Fetch IBGE SIDRA IPCA component data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching IBGE SIDRA data for {as_of}")
    try:
        records = asyncio.run(_run_connector(IbgeSidraConnector, as_of, as_of))
        context.log.info(f"IBGE SIDRA: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"IBGE SIDRA fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest STN Brazilian fiscal data (primary balance, debt, deficit)",
)
def bronze_stn_fiscal(context: AssetExecutionContext) -> dict:
    """Fetch STN fiscal data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching STN Fiscal data for {as_of}")
    try:
        records = asyncio.run(_run_connector(StnFiscalConnector, as_of, as_of))
        context.log.info(f"STN Fiscal: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"STN Fiscal fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest CFTC Commitments of Traders positioning data",
)
def bronze_cftc_cot(context: AssetExecutionContext) -> dict:
    """Fetch CFTC COT positioning data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching CFTC COT data for {as_of}")
    try:
        records = asyncio.run(_run_connector(CftcCotConnector, as_of, as_of))
        context.log.info(f"CFTC COT: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"CFTC COT fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest ANBIMA yield curves (ETTJ), NTN-B prices, and IMA indices",
)
def bronze_anbima(context: AssetExecutionContext) -> dict:
    """Fetch ANBIMA fixed-income data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching ANBIMA data for {as_of}")
    try:
        records = asyncio.run(_run_connector(AnbimaConnector, as_of, as_of))
        context.log.info(f"ANBIMA: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"ANBIMA fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest OECD Economic Outlook structural estimates (output gap, NAIRU)",
)
def bronze_oecd(context: AssetExecutionContext) -> dict:
    """Fetch OECD SDMX structural macro data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching OECD data for {as_of}")
    try:
        records = asyncio.run(_run_connector(OecdSdmxConnector, as_of, as_of))
        context.log.info(f"OECD: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"OECD fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest FMP US Treasury yield curves (fallback to Treasury.gov)",
)
def bronze_fmp_treasury(context: AssetExecutionContext) -> dict:
    """Fetch FMP US Treasury yield curve data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching FMP Treasury data for {as_of}")
    try:
        records = asyncio.run(_run_connector(FmpTreasuryConnector, as_of, as_of))
        context.log.info(f"FMP Treasury: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"FMP Treasury fetch failed: {exc}")
        raise


@asset(
    group_name="bronze",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    description="Ingest Trading Economics Brazilian DI curve (long tenors: 2Y, 5Y, 10Y)",
)
def bronze_te_di_curve(context: AssetExecutionContext) -> dict:
    """Fetch Trading Economics DI curve data for the partition date."""
    as_of = _partition_date(context)
    context.log.info(f"Fetching Trading Economics DI curve for {as_of}")
    try:
        records = asyncio.run(_run_connector(TradingEconDiCurveConnector, as_of, as_of))
        context.log.info(f"TE DI Curve: {records} records ingested")
        return {"status": "success", "records_fetched": records}
    except Exception as exc:
        context.log.error(f"TE DI Curve fetch failed: {exc}")
        raise
