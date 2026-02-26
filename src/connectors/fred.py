"""FRED (Federal Reserve Economic Data) connector.

Fetches US macroeconomic data series from the St. Louis Fed's FRED API.
Handles missing value convention (value == "."), revision tracking via
realtime_start/realtime_end, and FRED API key authentication.

SERIES_REGISTRY contains ~50 US macro series across five categories:
inflation, activity/labor, monetary/rates, credit, and fiscal.

REVISABLE_SERIES identifies series known to be revised (GDP, NFP, PCE, etc.)
for future point-in-time revision tracking.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.connectors.base import BaseConnector, ConnectorError
from src.core.config import settings
from src.core.database import async_session_factory
from src.core.models.macro_series import MacroSeries
from src.core.models.series_metadata import SeriesMetadata

logger = structlog.get_logger()

# Timezone for FRED release_time stamps
_NY_TZ = ZoneInfo("America/New_York")


class FredConnector(BaseConnector):
    """Connector for FRED (Federal Reserve Economic Data) API.

    Fetches ~50 US macroeconomic series covering inflation, activity/labor,
    monetary policy/rates, credit spreads, and fiscal indicators.

    Requires ``settings.fred_api_key`` to be set (free key from
    https://fred.stlouisfed.org/docs/api/api_key.html).

    Usage::

        async with FredConnector() as conn:
            count = await conn.run(date(2024, 1, 1), date(2025, 1, 1))
    """

    SOURCE_NAME: str = "FRED"
    BASE_URL: str = "https://api.stlouisfed.org"
    RATE_LIMIT_PER_SECOND: float = 2.0
    TIMEOUT_SECONDS: float = 60.0
    AUTH_TYPE: str = "api_key"
    SOURCE_NOTES: str = "Federal Reserve Economic Data (St. Louis Fed)"

    # -----------------------------------------------------------------------
    # Series registry: internal key -> FRED series code
    # -----------------------------------------------------------------------
    SERIES_REGISTRY: dict[str, str] = {
        # INFLATION
        "US_CPI_ALL_SA": "CPIAUCSL",
        "US_CPI_ALL_NSA": "CPIAUCNS",
        "US_CPI_CORE": "CPILFESL",
        "US_CPI_TRIMMED": "TRMMEANCPIM158SFRBCLE",
        "US_CPI_MEDIAN": "MEDCPIM158SFRBCLE",
        "US_CPI_STICKY": "STICKCPIM157SFRBATL",
        "US_CPI_FLEXIBLE": "FLEXCPIM157SFRBATL",
        "US_PCE_HEADLINE": "PCEPI",
        "US_PCE_CORE": "PCEPILFE",
        "US_PPI_ALL": "PPIACO",
        "US_MICHIGAN_INF_1Y": "MICH",
        "US_BEI_5Y": "T5YIE",
        "US_BEI_10Y": "T10YIE",
        "US_FWD_INF_5Y5Y": "T5YIFR",
        # ACTIVITY & LABOR
        "US_GDP_REAL": "GDPC1",
        "US_NFP_TOTAL": "PAYEMS",
        "US_NFP_PRIVATE": "USPRIV",
        "US_UNEMP_U3": "UNRATE",
        "US_UNEMP_U6": "U6RATE",
        "US_AVG_HOURLY_EARN": "CES0500000003",
        "US_JOLTS_OPENINGS": "JTSJOL",
        "US_JOLTS_QUITS": "JTSQUR",
        "US_INITIAL_CLAIMS": "ICSA",
        "US_CONT_CLAIMS": "CCSA",
        "US_INDPRO": "INDPRO",
        "US_CAP_UTIL": "TCU",
        "US_RETAIL_TOTAL": "RSAFS",
        "US_RETAIL_CONTROL": "RSFSXMV",
        "US_HOUSING_STARTS": "HOUST",
        "US_BUILDING_PERMITS": "PERMIT",
        "US_PERSONAL_INCOME": "PI",
        "US_PERSONAL_SPENDING": "PCE",
        "US_CONSUMER_SENT": "UMCSENT",
        "US_CFNAI": "CFNAI",
        # MONETARY & RATES
        "US_FED_FUNDS": "DFF",
        "US_SOFR": "SOFR",
        "US_UST_2Y": "DGS2",
        "US_UST_5Y": "DGS5",
        "US_UST_10Y": "DGS10",
        "US_UST_30Y": "DGS30",
        "US_TIPS_5Y": "DFII5",
        "US_TIPS_10Y": "DFII10",
        "US_FED_TOTAL_ASSETS": "WALCL",
        "US_FED_TREASURIES": "WTREGEN",
        "US_FED_MBS": "WSHOMCB",
        "US_ON_RRP": "RRPONTSYD",
        "US_NFCI": "NFCI",
        # CREDIT
        "US_HY_OAS": "BAMLH0A0HYM2",
        "US_IG_OAS": "BAMLC0A0CM",
        # FISCAL
        "US_FED_DEBT": "GFDEBTN",
        "US_DEBT_GDP": "GFDEGDQ188S",
    }

    # Series known to be revised after initial release
    REVISABLE_SERIES: set[str] = {
        "US_GDP_REAL",
        "US_NFP_TOTAL",
        "US_NFP_PRIVATE",
        "US_PCE_HEADLINE",
        "US_PCE_CORE",
        "US_PERSONAL_INCOME",
        "US_PERSONAL_SPENDING",
        "US_INDPRO",
        "US_RETAIL_TOTAL",
        "US_RETAIL_CONTROL",
    }

    # -----------------------------------------------------------------------
    # Fetch a single series
    # -----------------------------------------------------------------------
    async def fetch_series(
        self,
        series_code: str,
        start_date: date,
        end_date: date,
        realtime_start: date | None = None,
        realtime_end: date | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch observations for a single FRED series.

        Args:
            series_code: FRED series ID (e.g., "CPIAUCSL").
            start_date: Inclusive observation start date.
            end_date: Inclusive observation end date.
            realtime_start: Optional realtime start for vintage data.
            realtime_end: Optional realtime end for vintage data.

        Returns:
            List of record dicts with keys: observation_date, value,
            release_time, revision_number, source.
        """
        api_key = settings.fred_api_key
        if not api_key:
            raise ConnectorError(
                "FRED API key not configured. Set FRED_API_KEY in .env "
                "or register at https://fred.stlouisfed.org/docs/api/api_key.html"
            )

        params: dict[str, str] = {
            "series_id": series_code,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start_date.strftime("%Y-%m-%d"),
            "observation_end": end_date.strftime("%Y-%m-%d"),
        }

        if realtime_start is not None:
            params["realtime_start"] = realtime_start.strftime("%Y-%m-%d")
        if realtime_end is not None:
            params["realtime_end"] = realtime_end.strftime("%Y-%m-%d")

        response = await self._request(
            "GET", "/fred/series/observations", params=params
        )
        data = response.json()

        observations = data.get("observations", [])
        records: list[dict[str, Any]] = []

        for obs in observations:
            raw_value = obs.get("value", "")

            # FRED convention: "." means missing/unavailable
            if raw_value == ".":
                continue

            try:
                value = float(raw_value)
            except (ValueError, TypeError):
                self.log.warning(
                    "invalid_value",
                    series_code=series_code,
                    raw_value=raw_value,
                )
                continue

            # Parse observation date (YYYY-MM-DD)
            try:
                obs_date = datetime.strptime(obs["date"], "%Y-%m-%d").date()
            except (ValueError, KeyError, TypeError):
                self.log.warning(
                    "invalid_date",
                    series_code=series_code,
                    raw_date=obs.get("date"),
                )
                continue

            # release_time from realtime_start (when this value became known)
            rt_start = obs.get("realtime_start", "")
            try:
                release_dt = datetime.strptime(rt_start, "%Y-%m-%d").replace(
                    tzinfo=_NY_TZ
                )
            except (ValueError, TypeError):
                release_dt = datetime.now(tz=_NY_TZ)

            records.append({
                "observation_date": obs_date,
                "value": value,
                "release_time": release_dt,
                "revision_number": 0,
                "source": self.SOURCE_NAME,
            })

        return records

    # -----------------------------------------------------------------------
    # Fetch all series (abstract method implementation)
    # -----------------------------------------------------------------------
    async def fetch(
        self,
        start_date: date,
        end_date: date,
        series_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Fetch observations for multiple FRED series.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            series_ids: Optional list of internal series keys to fetch.
                If None, fetches all series in SERIES_REGISTRY.
            **kwargs: Additional arguments (unused).

        Returns:
            List of record dicts, each tagged with _series_key.
        """
        keys = series_ids or list(self.SERIES_REGISTRY.keys())
        all_records: list[dict[str, Any]] = []
        total = len(keys)

        for i, series_key in enumerate(keys, 1):
            fred_code = self.SERIES_REGISTRY.get(series_key)
            if fred_code is None:
                self.log.warning(
                    "unknown_series_key",
                    series_key=series_key,
                )
                continue

            self.log.info(
                "fetching_series",
                series_key=series_key,
                fred_code=fred_code,
                progress=f"{i}/{total}",
            )

            try:
                records = await self.fetch_series(
                    fred_code, start_date, end_date
                )
                for rec in records:
                    rec["_series_key"] = series_key
                all_records.extend(records)
            except Exception as exc:
                self.log.warning(
                    "fetch_series_error",
                    series_key=series_key,
                    fred_code=fred_code,
                    error=str(exc),
                )
                continue

            # Rate limiting between series requests
            if i < total:
                await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

        return all_records

    # -----------------------------------------------------------------------
    # Vintage fetch (stub for Phase 4 revision tracking)
    # -----------------------------------------------------------------------
    async def fetch_vintages(
        self,
        series_code: str,
        observation_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch all vintages of a specific observation for revision tracking.

        This is a stub for Phase 4 backfill. Fetches the full realtime range
        and assigns incrementing revision_numbers to prove the DATA-02
        revision tracking pattern.

        Args:
            series_code: FRED series ID (e.g., "GDPC1").
            observation_date: The specific observation date to get vintages for.

        Returns:
            List of record dicts with incrementing revision_number values.
        """
        params: dict[str, str] = {
            "series_id": series_code,
            "api_key": settings.fred_api_key,
            "file_type": "json",
            "observation_start": observation_date.strftime("%Y-%m-%d"),
            "observation_end": observation_date.strftime("%Y-%m-%d"),
            "realtime_start": "1776-07-04",  # FRED's earliest realtime
            "realtime_end": "9999-12-31",  # FRED's latest realtime
        }

        response = await self._request(
            "GET", "/fred/series/observations", params=params
        )
        data = response.json()

        observations = data.get("observations", [])
        records: list[dict[str, Any]] = []

        for revision_num, obs in enumerate(observations):
            raw_value = obs.get("value", "")
            if raw_value == ".":
                continue

            try:
                value = float(raw_value)
            except (ValueError, TypeError):
                continue

            rt_start = obs.get("realtime_start", "")
            try:
                release_dt = datetime.strptime(rt_start, "%Y-%m-%d").replace(
                    tzinfo=_NY_TZ
                )
            except (ValueError, TypeError):
                release_dt = datetime.now(tz=_NY_TZ)

            records.append({
                "observation_date": observation_date,
                "value": value,
                "release_time": release_dt,
                "revision_number": revision_num,
                "source": self.SOURCE_NAME,
            })

        return records

    async def _ensure_series_metadata(
        self,
        series_key: str,
        fred_code: str,
        source_id: int,
    ) -> int:
        """Ensure a series_metadata row exists for the given series. Returns its id."""
        is_revisable = series_key in self.REVISABLE_SERIES

        async with async_session_factory() as session:
            async with session.begin():
                stmt = pg_insert(SeriesMetadata).values(
                    source_id=source_id,
                    series_code=fred_code,
                    name=series_key,
                    frequency="D",
                    country="US",
                    unit="index",
                    decimal_separator=".",
                    date_format="YYYY-MM-DD",
                    is_revisable=is_revisable,
                    release_timezone="America/New_York",
                    is_active=True,
                ).on_conflict_do_nothing(
                    constraint="uq_series_metadata_source_series"
                )
                await session.execute(stmt)

            result = await session.execute(
                select(SeriesMetadata.id).where(
                    SeriesMetadata.source_id == source_id,
                    SeriesMetadata.series_code == fred_code,
                )
            )
            row = result.scalar_one()
            return row

    # -----------------------------------------------------------------------
    # Store records (abstract method implementation)
    # -----------------------------------------------------------------------
    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist fetched FRED records to the macro_series table.

        Ensures data_source and series_metadata rows exist before inserting.
        Uses ON CONFLICT DO NOTHING for idempotent writes.

        Args:
            records: List of record dicts from fetch(), each with _series_key.

        Returns:
            Number of rows actually inserted (excludes conflicts).
        """
        if not records:
            return 0

        # Group records by series key
        by_key: dict[str, list[dict[str, Any]]] = {}
        for rec in records:
            key = rec.pop("_series_key", None)
            if key is not None:
                by_key.setdefault(key, []).append(rec)

        # Ensure data source exists
        source_id = await self._ensure_data_source()

        # Resolve series_id for each key and attach to records
        all_insertable: list[dict[str, Any]] = []
        for series_key, recs in by_key.items():
            fred_code = self.SERIES_REGISTRY.get(series_key)
            if fred_code is None:
                continue

            series_id = await self._ensure_series_metadata(
                series_key, fred_code, source_id
            )

            for rec in recs:
                rec["series_id"] = series_id
                all_insertable.append(rec)

        # Bulk insert with ON CONFLICT DO NOTHING
        return await self._bulk_insert(
            MacroSeries, all_insertable, "uq_macro_series_natural_key"
        )

    # -----------------------------------------------------------------------
    # Run override to pass series_ids
    # -----------------------------------------------------------------------
    async def run(
        self,
        start_date: date,
        end_date: date,
        series_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> int:
        """Execute the full fetch-then-store pipeline.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            series_ids: Optional subset of series keys to fetch.
            **kwargs: Additional arguments.

        Returns:
            Number of records inserted.
        """
        records = await self.fetch(
            start_date, end_date, series_ids=series_ids, **kwargs
        )

        if not records:
            self.log.warning(
                "no_records_fetched",
                start_date=str(start_date),
                end_date=str(end_date),
            )
            return 0

        inserted = await self.store(records)
        self.log.info(
            "ingestion_complete",
            fetched=len(records),
            inserted=inserted,
            start_date=str(start_date),
            end_date=str(end_date),
        )
        return inserted
