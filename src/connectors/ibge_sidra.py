"""IBGE SIDRA connector -- disaggregated IPCA inflation data by component.

Fetches IPCA (Brazilian CPI) data broken down by 9 consumption groups from
IBGE's SIDRA API, Table 7060. Provides both MoM percentage change (variable 63)
and basket weights (variable 2265) per group.

Key design decisions:
- Path-based URL (not query params) per SIDRA convention
- First element of response (index 0) is always a header row -- must be skipped
- Periods in YYYYMM format, converted to first-of-month dates
- Invalid values ("", "-", "...") silently skipped
- Conservative 1.0 req/s rate limit (IBGE has no documented limit)
- 60s timeout (SIDRA can be slow for large queries)
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

logger = structlog.get_logger()

_SP_TZ = ZoneInfo("America/Sao_Paulo")


class IbgeSidraConnector(BaseConnector):
    """Connector for IBGE SIDRA -- IPCA disaggregated by 9 consumption groups.

    Fetches Table 7060 (IPCA monthly) with:
    - Variable 63: MoM percentage change per group
    - Variable 2265: Weight (share) of each group in the IPCA basket

    Usage::

        async with IbgeSidraConnector() as conn:
            count = await conn.run(date(2024, 1, 1), date(2024, 12, 31))
    """

    SOURCE_NAME: str = "IBGE_SIDRA"
    BASE_URL: str = "https://apisidra.ibge.gov.br"
    RATE_LIMIT_PER_SECOND: float = 1.0
    TIMEOUT_SECONDS: float = 60.0
    DEFAULT_LOCALE: str = "pt-BR"
    SOURCE_NOTES: str = "IBGE SIDRA - Sistema IBGE de Recuperacao Automatica"

    # -----------------------------------------------------------------------
    # IPCA group classification codes (SIDRA c315)
    # -----------------------------------------------------------------------
    IPCA_GROUPS: dict[str, int] = {
        "FOOD": 7169,
        "HOUSING": 7170,
        "HOUSEHOLD": 7445,
        "CLOTHING": 7171,
        "TRANSPORT": 7432,
        "HEALTH": 7172,
        "PERSONAL": 7173,
        "EDUCATION": 7174,
        "COMMUNICATION": 7175,
    }

    # Reverse map: code -> group name (built once at class level)
    _CODE_TO_NAME: dict[str, str] = {
        str(code): name for name, code in IPCA_GROUPS.items()
    }

    # SIDRA variable codes
    _VAR_MOM_CHANGE: int = 63
    _VAR_WEIGHT: int = 2265

    # -----------------------------------------------------------------------
    # Period helpers
    # -----------------------------------------------------------------------
    @staticmethod
    def _date_to_period(d: date) -> str:
        """Convert a date to YYYYMM period format."""
        return f"{d.year:04d}{d.month:02d}"

    @staticmethod
    def _period_to_date(period_str: str) -> date | None:
        """Convert YYYYMM period to first-of-month date.

        Args:
            period_str: Period string in YYYYMM format (e.g., "202401").

        Returns:
            date(year, month, 1) or None if parsing fails.
        """
        if not period_str or len(period_str) != 6:
            return None
        try:
            year = int(period_str[:4])
            month = int(period_str[4:6])
            return date(year, month, 1)
        except (ValueError, TypeError):
            return None

    # -----------------------------------------------------------------------
    # Fetch variable data from SIDRA
    # -----------------------------------------------------------------------
    async def _fetch_variable(
        self, variable: int, start_period: str, end_period: str
    ) -> list[dict[str, Any]]:
        """Fetch a single SIDRA variable for all IPCA groups.

        Uses path-based URL per SIDRA convention:
        /values/t/7060/n1/all/v/{variable}/p/{start}-{end}/c315/{group_codes}

        Args:
            variable: SIDRA variable code (63 for MoM, 2265 for weight).
            start_period: Start period in YYYYMM format.
            end_period: End period in YYYYMM format.

        Returns:
            List of parsed record dicts.
        """
        group_codes = ",".join(str(c) for c in self.IPCA_GROUPS.values())
        url = (
            f"/values/t/7060/n1/all/v/{variable}"
            f"/p/{start_period}-{end_period}"
            f"/c315/{group_codes}"
        )

        response = await self._request("GET", url)
        data = response.json()

        if not isinstance(data, list):
            self.log.warning(
                "unexpected_response_format",
                variable=variable,
                response_type=type(data).__name__,
            )
            return []

        if len(data) == 0:
            return []

        # CRITICAL: Skip first element (header/metadata row)
        records: list[dict[str, Any]] = []
        for item in data[1:]:
            period_code = item.get("D3C", "")
            group_code = str(item.get("D4C", ""))
            raw_value = item.get("V", "")

            # Skip invalid values
            if not raw_value or raw_value in ("-", "...", "."):
                continue

            # Parse period to date
            obs_date = self._period_to_date(period_code)
            if obs_date is None:
                self.log.warning(
                    "invalid_period",
                    period_code=period_code,
                    variable=variable,
                )
                continue

            # Map group code to name
            group_name = self._CODE_TO_NAME.get(group_code)
            if group_name is None:
                self.log.warning(
                    "unknown_group_code",
                    group_code=group_code,
                    variable=variable,
                )
                continue

            # Parse numeric value
            try:
                value = float(raw_value)
            except (ValueError, TypeError):
                self.log.warning(
                    "invalid_value",
                    raw_value=raw_value,
                    group=group_name,
                    period=period_code,
                )
                continue

            # Build series key based on variable type
            if variable == self._VAR_MOM_CHANGE:
                series_key = f"BR_IPCA_{group_name}_MOM"
            elif variable == self._VAR_WEIGHT:
                series_key = f"BR_IPCA_{group_name}_WEIGHT"
            else:
                series_key = f"BR_IPCA_{group_name}_V{variable}"

            records.append(
                {
                    "_series_key": series_key,
                    "observation_date": obs_date,
                    "value": value,
                    "release_time": datetime(
                        obs_date.year,
                        obs_date.month,
                        15,
                        tzinfo=_SP_TZ,
                    ),
                    "revision_number": 0,
                    "source": self.SOURCE_NAME,
                }
            )

        return records

    # -----------------------------------------------------------------------
    # Fetch (abstract method implementation)
    # -----------------------------------------------------------------------
    async def fetch(
        self,
        start_date: date,
        end_date: date,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Fetch IPCA component data for all 9 groups.

        Fetches both MoM percentage change (var 63) and weight (var 2265)
        for all IPCA groups across the date range.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            **kwargs: Additional arguments (unused).

        Returns:
            List of record dicts tagged with _series_key.
        """
        start_period = self._date_to_period(start_date)
        end_period = self._date_to_period(end_date)

        all_records: list[dict[str, Any]] = []

        # Fetch MoM change (variable 63)
        self.log.info(
            "fetching_variable",
            variable="MoM change (63)",
            start=start_period,
            end=end_period,
        )
        mom_records = await self._fetch_variable(
            self._VAR_MOM_CHANGE, start_period, end_period
        )
        all_records.extend(mom_records)

        # Rate limit between requests
        await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

        # Fetch weight (variable 2265)
        self.log.info(
            "fetching_variable",
            variable="Weight (2265)",
            start=start_period,
            end=end_period,
        )
        weight_records = await self._fetch_variable(
            self._VAR_WEIGHT, start_period, end_period
        )
        all_records.extend(weight_records)

        self.log.info(
            "fetch_complete",
            mom_records=len(mom_records),
            weight_records=len(weight_records),
            total=len(all_records),
        )
        return all_records

    async def _ensure_series_metadata(self, series_key: str, source_id: int) -> int:
        """Ensure a series_metadata row exists for the given series. Returns its id."""
        async with async_session_factory() as session:
            async with session.begin():
                stmt = (
                    pg_insert(SeriesMetadata)
                    .values(
                        source_id=source_id,
                        series_code=series_key,
                        name=series_key,
                        frequency="M",
                        country="BR",
                        unit="percent",
                        decimal_separator=".",
                        date_format="YYYYMM",
                        is_revisable=False,
                        release_timezone="America/Sao_Paulo",
                        is_active=True,
                    )
                    .on_conflict_do_nothing(
                        constraint="uq_series_metadata_source_series"
                    )
                )
                await session.execute(stmt)

            result = await session.execute(
                select(SeriesMetadata.id).where(
                    SeriesMetadata.source_id == source_id,
                    SeriesMetadata.series_code == series_key,
                )
            )
            row = result.scalar_one()
            return row

    # -----------------------------------------------------------------------
    # Store (abstract method implementation)
    # -----------------------------------------------------------------------
    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist fetched IBGE SIDRA records to the macro_series table.

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
            series_id = await self._ensure_series_metadata(series_key, source_id)

            for rec in recs:
                rec["series_id"] = series_id
                all_insertable.append(rec)

        # Bulk insert with ON CONFLICT DO NOTHING
        return await self._bulk_insert(
            MacroSeries, all_insertable, "uq_macro_series_natural_key"
        )
