"""BCB SGS (Sistema Gerenciador de Séries Temporais) connector.

Fetches Brazilian macroeconomic data series from the Central Bank of Brazil's
SGS API. Handles DD/MM/YYYY date parsing, period-decimal value format,
and splits date ranges exceeding 10 years into chunks (BCB API limit
since March 2025).

SERIES_REGISTRY contains ~50 Brazilian macro series across five categories:
inflation, activity, monetary/credit, external, and fiscal.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.connectors.base import BaseConnector
from src.core.database import async_session_factory
from src.core.models.macro_series import MacroSeries
from src.core.models.series_metadata import SeriesMetadata
from src.core.utils.parsing import parse_numeric_value

logger = structlog.get_logger()

# Timezone for release_time stamps
_SP_TZ = ZoneInfo("America/Sao_Paulo")


class BcbSgsConnector(BaseConnector):
    """Connector for BCB SGS (Central Bank of Brazil time series API).

    Fetches ~50 Brazilian macroeconomic series covering inflation, activity,
    monetary/credit, external sector, and fiscal indicators.

    Usage::

        async with BcbSgsConnector() as conn:
            count = await conn.run(date(2024, 1, 1), date(2025, 1, 1))
    """

    SOURCE_NAME: str = "BCB_SGS"
    BASE_URL: str = "https://api.bcb.gov.br"
    RATE_LIMIT_PER_SECOND: float = 3.0
    MAX_DATE_RANGE_YEARS: int = 10
    DEFAULT_LOCALE: str = "pt-BR"
    SOURCE_NOTES: str = "BCB SGS - Sistema Gerenciador de Series Temporais"

    # -----------------------------------------------------------------------
    # Series registry: internal key -> BCB SGS numeric code
    # -----------------------------------------------------------------------
    SERIES_REGISTRY: dict[str, int] = {
        # INFLATION
        "BR_IPCA_MOM": 433,
        "BR_IPCA_YOY": 13522,
        "BR_IPCA_CORE_EX0": 11426,
        "BR_IPCA_CORE_EX3": 27838,
        "BR_IPCA_CORE_MA": 11427,
        "BR_IPCA_CORE_DP": 27839,
        "BR_IPCA_CORE_P55": 4466,
        "BR_IPCA_DIFFUSION": 21379,
        "BR_IPCA15_MOM": 7478,
        "BR_INPC_MOM": 188,
        "BR_IGP_M_MOM": 189,
        "BR_IGP_DI_MOM": 190,
        "BR_IPA_M_MOM": 225,
        "BR_IPC_S_WEEKLY": 7446,
        "BR_IPC_FIPE_WEEKLY": 10764,
        # ACTIVITY
        "BR_GDP_QOQ": 22099,
        "BR_IBC_BR": 24364,
        "BR_INDUSTRIAL_PROD": 21859,
        "BR_RETAIL_CORE": 1455,
        "BR_RETAIL_BROAD": 28473,
        "BR_SERVICES_REV": 23987,
        "BR_CONSUMER_CONF": 4393,
        "BR_BUSINESS_CONF": 7343,
        "BR_CAPACITY_UTIL": 1344,
        "BR_CAGED_NET": 28763,
        "BR_UNEMPLOYMENT": 24369,
        # MONETARY & CREDIT
        "BR_SELIC_TARGET": 432,
        "BR_SELIC_DAILY": 11,
        "BR_CDI_DAILY": 12,
        "BR_CREDIT_GDP": 20539,
        "BR_DEFAULT_PF": 21082,
        "BR_DEFAULT_PJ": 21083,
        "BR_AVG_LENDING": 20714,
        "BR_M1": 1824,
        "BR_M2": 1837,
        "BR_M3": 1838,
        "BR_M4": 1839,
        "BR_MONETARY_BASE": 1788,
        # EXTERNAL
        "BR_TRADE_BALANCE": 22707,
        "BR_CURRENT_ACCOUNT": 22885,
        "BR_CA_GDP": 22918,
        "BR_FDI": 22886,
        "BR_PORT_EQUITY": 22888,
        "BR_PORT_DEBT": 22889,
        "BR_RESERVES": 13621,
        "BR_PTAX_BUY": 1,
        "BR_PTAX_SELL": 10813,
        # FISCAL
        "BR_PRIMARY_BALANCE": 5793,
        "BR_NOMINAL_DEFICIT": 5727,
        "BR_NET_DEBT_GDP": 4513,
        "BR_GROSS_DEBT_GDP": 13762,
    }

    # -----------------------------------------------------------------------
    # Fetch a single series
    # -----------------------------------------------------------------------
    async def fetch_series(
        self, series_code: int, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Fetch observations for a single BCB SGS series.

        Automatically chunks the date range if it exceeds MAX_DATE_RANGE_YEARS.

        Args:
            series_code: BCB SGS numeric series code (e.g., 433 for IPCA MoM).
            start_date: Inclusive start date.
            end_date: Inclusive end date.

        Returns:
            List of record dicts with keys: observation_date, value,
            release_time, revision_number, source.
        """
        all_records: list[dict[str, Any]] = []
        chunks = self._chunk_date_range(start_date, end_date)

        for chunk_start, chunk_end in chunks:
            url = f"/dados/serie/bcdata.sgs.{series_code}/dados"
            params = {
                "formato": "json",
                "dataInicial": chunk_start.strftime("%d/%m/%Y"),
                "dataFinal": chunk_end.strftime("%d/%m/%Y"),
            }

            response = await self._request("GET", url, params=params)
            data = response.json()

            if not isinstance(data, list):
                self.log.warning(
                    "unexpected_response_format",
                    series_code=series_code,
                    response_type=type(data).__name__,
                )
                continue

            for item in data:
                raw_date = item.get("data", "")
                raw_value = item.get("valor", "")

                # Parse DD/MM/YYYY date
                try:
                    obs_date = datetime.strptime(raw_date, "%d/%m/%Y").date()
                except (ValueError, TypeError):
                    self.log.warning(
                        "invalid_date",
                        series_code=series_code,
                        raw_date=raw_date,
                    )
                    continue

                # Parse value (period decimal in BCB SGS JSON)
                parsed_value = parse_numeric_value(raw_value, ".")
                if parsed_value is None:
                    continue

                all_records.append({
                    "observation_date": obs_date,
                    "value": parsed_value,
                    "release_time": datetime.now(tz=_SP_TZ),
                    "revision_number": 0,
                    "source": self.SOURCE_NAME,
                })

        return all_records

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
        """Fetch observations for multiple BCB SGS series.

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
            bcb_code = self.SERIES_REGISTRY.get(series_key)
            if bcb_code is None:
                self.log.warning(
                    "unknown_series_key",
                    series_key=series_key,
                )
                continue

            self.log.info(
                "fetching_series",
                series_key=series_key,
                bcb_code=bcb_code,
                progress=f"{i}/{total}",
            )

            try:
                records = await self.fetch_series(bcb_code, start_date, end_date)
                for rec in records:
                    rec["_series_key"] = series_key
                all_records.extend(records)
            except Exception as exc:
                self.log.warning(
                    "fetch_series_error",
                    series_key=series_key,
                    bcb_code=bcb_code,
                    error=str(exc),
                )
                continue

            # Rate limiting between series requests
            if i < total:
                await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

        return all_records

    async def _ensure_series_metadata(
        self,
        series_key: str,
        bcb_code: int,
        source_id: int,
    ) -> int:
        """Ensure a series_metadata row exists for the given series. Returns its id."""
        async with async_session_factory() as session:
            async with session.begin():
                stmt = pg_insert(SeriesMetadata).values(
                    source_id=source_id,
                    series_code=str(bcb_code),
                    name=series_key,
                    frequency="D",
                    country="BR",
                    unit="index",
                    decimal_separator=".",
                    date_format="DD/MM/YYYY",
                    is_revisable=False,
                    release_timezone="America/Sao_Paulo",
                    is_active=True,
                ).on_conflict_do_nothing(
                    constraint="uq_series_metadata_source_series"
                )
                await session.execute(stmt)

            result = await session.execute(
                select(SeriesMetadata.id).where(
                    SeriesMetadata.source_id == source_id,
                    SeriesMetadata.series_code == str(bcb_code),
                )
            )
            row = result.scalar_one()
            return row

    # -----------------------------------------------------------------------
    # Store records (abstract method implementation)
    # -----------------------------------------------------------------------
    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist fetched BCB SGS records to the macro_series table.

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
            bcb_code = self.SERIES_REGISTRY.get(series_key)
            if bcb_code is None:
                continue

            series_id = await self._ensure_series_metadata(
                series_key, bcb_code, source_id
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
