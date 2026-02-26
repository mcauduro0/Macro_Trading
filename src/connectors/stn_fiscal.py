"""STN Fiscal connector -- Brazilian government fiscal data.

Fetches fiscal indicators from the Central Bank of Brazil's SGS API.
Uses the same API pattern as BcbSgsConnector but stores records to the
fiscal_data hypertable instead of macro_series.

SERIES_REGISTRY contains 6 fiscal series covering primary balance,
debt/GDP ratios, revenue, expenditure, and social security:
- BR_PRIMARY_BALANCE_MONTHLY (5364): central government primary balance
- BR_NET_DEBT_GDP_CENTRAL (4513): net debt / GDP
- BR_GROSS_DEBT_GDP (13762): gross debt / GDP
- BR_TOTAL_REVENUE (21864): total government revenue
- BR_TOTAL_EXPENDITURE (21865): total government expenditure
- BR_SOCIAL_SEC_DEFICIT (7620): social security (RGPS) deficit

Note: Tesouro Transparente API (apidatalake.tesouro.gov.br) was evaluated
during research but found unreliable. BCB SGS is used as the sole source.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.connectors.base import BaseConnector
from src.core.database import async_session_factory
from src.core.models.fiscal_data import FiscalData
from src.core.models.series_metadata import SeriesMetadata
from src.core.utils.parsing import parse_numeric_value

# Timezone for release_time stamps
_SP_TZ = ZoneInfo("America/Sao_Paulo")


class StnFiscalConnector(BaseConnector):
    """Connector for Brazilian fiscal data from BCB SGS API.

    Fetches 6 fiscal series and stores them to the fiscal_data hypertable.

    Usage::

        async with StnFiscalConnector() as conn:
            count = await conn.run(date(2024, 1, 1), date(2025, 1, 1))
    """

    SOURCE_NAME: str = "STN_FISCAL"
    BASE_URL: str = "https://api.bcb.gov.br"
    RATE_LIMIT_PER_SECOND: float = 3.0
    MAX_DATE_RANGE_YEARS: int = 10
    DEFAULT_LOCALE: str = "pt-BR"
    SOURCE_NOTES: str = "STN Fiscal - Government fiscal data from BCB SGS"

    # -----------------------------------------------------------------------
    # Series registry: internal key -> (BCB SGS code, fiscal_metric, unit)
    # -----------------------------------------------------------------------
    SERIES_REGISTRY: dict[str, tuple[int, str, str]] = {
        "BR_PRIMARY_BALANCE_MONTHLY": (5364, "PRIMARY_BALANCE", "BRL_MM"),
        "BR_NET_DEBT_GDP_CENTRAL": (4513, "NET_DEBT_GDP", "PERCENT"),
        "BR_GROSS_DEBT_GDP": (13762, "GROSS_DEBT_GDP", "PERCENT"),
        "BR_TOTAL_REVENUE": (21864, "TOTAL_REVENUE", "BRL_MM"),
        "BR_TOTAL_EXPENDITURE": (21865, "TOTAL_EXPENDITURE", "BRL_MM"),
        "BR_SOCIAL_SEC_DEFICIT": (7620, "SOCIAL_SEC_DEFICIT", "BRL_MM"),
    }

    # -----------------------------------------------------------------------
    # Fetch a single series
    # -----------------------------------------------------------------------
    async def _fetch_series(
        self,
        series_key: str,
        series_code: int,
        fiscal_metric: str,
        unit: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch observations for a single BCB SGS fiscal series.

        Args:
            series_key: Internal series key (e.g., "BR_PRIMARY_BALANCE_MONTHLY").
            series_code: BCB SGS numeric series code.
            fiscal_metric: Fiscal metric type for the record.
            unit: Unit of measurement for the record.
            start_date: Inclusive start date.
            end_date: Inclusive end date.

        Returns:
            List of record dicts tagged with _series_key.
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
                    series_key=series_key,
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
                        series_key=series_key,
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
                    "fiscal_metric": fiscal_metric,
                    "unit": unit,
                    "release_time": datetime.now(tz=_SP_TZ),
                    "_series_key": series_key,
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
        """Fetch observations for multiple fiscal series.

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
            entry = self.SERIES_REGISTRY.get(series_key)
            if entry is None:
                self.log.warning(
                    "unknown_series_key",
                    series_key=series_key,
                )
                continue

            bcb_code, fiscal_metric, unit = entry

            self.log.info(
                "fetching_series",
                series_key=series_key,
                bcb_code=bcb_code,
                fiscal_metric=fiscal_metric,
                progress=f"{i}/{total}",
            )

            try:
                records = await self._fetch_series(
                    series_key, bcb_code, fiscal_metric, unit,
                    start_date, end_date,
                )
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
        unit: str,
        source_id: int,
    ) -> int:
        """Ensure a series_metadata row exists for the given series. Returns its id."""
        async with async_session_factory() as session:
            async with session.begin():
                stmt = pg_insert(SeriesMetadata).values(
                    source_id=source_id,
                    series_code=str(bcb_code),
                    name=series_key,
                    frequency="M",
                    country="BR",
                    unit=unit,
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
        """Persist fetched fiscal records to the fiscal_data table.

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
            entry = self.SERIES_REGISTRY.get(series_key)
            if entry is None:
                continue

            bcb_code, _fiscal_metric, unit = entry

            series_id = await self._ensure_series_metadata(
                series_key, bcb_code, unit, source_id
            )

            for rec in recs:
                rec["series_id"] = series_id
                all_insertable.append(rec)

        # Bulk insert with ON CONFLICT DO NOTHING
        return await self._bulk_insert(
            FiscalData, all_insertable, "uq_fiscal_data_natural_key"
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
