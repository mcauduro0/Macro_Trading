"""BCB Focus connector -- market expectations survey data.

Fetches the BCB Focus survey (Pesquisa Focus) containing market consensus
expectations for Brazilian macroeconomic indicators: IPCA, IGP-M, Selic,
GDP, and FX (exchange rate).

Key design decisions:
- OData protocol with $top/$skip pagination
- MAX_PAGES safety limit to prevent infinite loops
- Series keys encode reference year for horizon disambiguation:
  e.g., BR_FOCUS_IPCA_2026_MEDIAN
- observation_date is the survey publication date (not the reference year)
- Indicator names with accents normalized (Cambio -> CAMBIO)
- Conservative 2.0s rate limit between page requests
"""

from __future__ import annotations

import asyncio
import unicodedata
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


def _normalize_indicator_name(indicator: str) -> str:
    """Normalize indicator name for series key generation.

    Removes accents and special characters, converts to uppercase.
    Examples: "Câmbio" -> "CAMBIO", "IGP-M" -> "IGPM", "PIB" -> "PIB"
    """
    # Remove accents via unicode normalization
    nfkd = unicodedata.normalize("NFKD", indicator)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Remove non-alphanumeric chars and uppercase
    cleaned = "".join(c for c in ascii_str if c.isalnum())
    return cleaned.upper()


class BcbFocusConnector(BaseConnector):
    """Connector for BCB Focus market expectations survey.

    Fetches market consensus expectations (median, mean, etc.) for key
    Brazilian indicators via the BCB OData API with pagination.

    Usage::

        async with BcbFocusConnector() as conn:
            count = await conn.run(date(2024, 1, 1), date(2025, 1, 1))
    """

    SOURCE_NAME: str = "BCB_FOCUS"
    BASE_URL: str = "https://olinda.bcb.gov.br"
    RATE_LIMIT_PER_SECOND: float = 2.0
    TIMEOUT_SECONDS: float = 30.0
    DEFAULT_LOCALE: str = "pt-BR"
    SOURCE_NOTES: str = "BCB Focus - Pesquisa Focus de Expectativas de Mercado"
    ODATA_PAGE_SIZE: int = 1000
    MAX_PAGES: int = 100

    # -----------------------------------------------------------------------
    # Indicator configuration
    # -----------------------------------------------------------------------
    INDICATORS: dict[str, dict[str, str]] = {
        "IPCA": {"entity_set": "ExpectativasMercadoAnuais", "type": "annual"},
        "IGP-M": {"entity_set": "ExpectativasMercadoAnuais", "type": "annual"},
        "Selic": {"entity_set": "ExpectativasMercadoAnuais", "type": "annual"},
        "PIB": {"entity_set": "ExpectativasMercadoAnuais", "type": "annual"},
        "Câmbio": {"entity_set": "ExpectativasMercadoAnuais", "type": "annual"},
    }

    # -----------------------------------------------------------------------
    # OData pagination
    # -----------------------------------------------------------------------
    async def _fetch_odata_paginated(
        self, entity_set: str, odata_filter: str
    ) -> list[dict[str, Any]]:
        """Fetch all records from an OData endpoint with $top/$skip pagination.

        Terminates when:
        - A page returns fewer than ODATA_PAGE_SIZE items (partial/empty)
        - MAX_PAGES is reached (safety limit)

        Args:
            entity_set: OData entity set name (e.g., "ExpectativasMercadoAnuais").
            odata_filter: OData $filter expression.

        Returns:
            Accumulated list of all items from all pages.
        """
        url = f"/olinda/servico/Expectativas/versao/v1/odata/{entity_set}"
        all_items: list[dict[str, Any]] = []

        for page in range(self.MAX_PAGES):
            params = {
                "$format": "json",
                "$top": str(self.ODATA_PAGE_SIZE),
                "$skip": str(page * self.ODATA_PAGE_SIZE),
                "$filter": odata_filter,
                "$orderby": "Data desc",
            }

            response = await self._request("GET", url, params=params)
            data = response.json()
            items = data.get("value", [])

            all_items.extend(items)

            self.log.debug(
                "odata_page_fetched",
                entity_set=entity_set,
                page=page + 1,
                items_on_page=len(items),
                total_accumulated=len(all_items),
            )

            # Terminate if partial or empty page (last page)
            if len(items) < self.ODATA_PAGE_SIZE:
                break

            # Rate limit between pages
            await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)
        else:
            # MAX_PAGES reached without termination
            self.log.warning(
                "max_pages_reached",
                entity_set=entity_set,
                max_pages=self.MAX_PAGES,
                total_records=len(all_items),
            )

        return all_items

    # -----------------------------------------------------------------------
    # Fetch (abstract method implementation)
    # -----------------------------------------------------------------------
    async def fetch(
        self,
        start_date: date,
        end_date: date,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Fetch Focus expectations for all configured indicators.

        Args:
            start_date: Inclusive start date for survey publication date.
            end_date: Inclusive end date for survey publication date.
            **kwargs: Additional arguments (unused).

        Returns:
            List of record dicts tagged with _series_key.
        """
        all_records: list[dict[str, Any]] = []
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        for indicator, config in self.INDICATORS.items():
            entity_set = config["entity_set"]

            odata_filter = (
                f"Indicador eq '{indicator}' "
                f"and Data ge '{start_str}' "
                f"and Data le '{end_str}'"
            )

            self.log.info(
                "fetching_indicator",
                indicator=indicator,
                entity_set=entity_set,
            )

            items = await self._fetch_odata_paginated(entity_set, odata_filter)

            normalized_name = _normalize_indicator_name(indicator)

            for item in items:
                # Parse survey publication date
                data_str = item.get("Data", "")
                try:
                    obs_date = datetime.strptime(data_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    self.log.warning(
                        "invalid_date",
                        indicator=indicator,
                        raw_date=data_str,
                    )
                    continue

                # Get reference year/period
                ref = item.get("DataReferencia", "")
                ref_year = str(ref).strip()

                if not ref_year:
                    self.log.warning(
                        "missing_reference_year",
                        indicator=indicator,
                        date=data_str,
                    )
                    continue

                # Get median value (the consensus)
                mediana = item.get("Mediana")
                if mediana is None:
                    continue

                try:
                    value = float(mediana)
                except (ValueError, TypeError):
                    continue

                # Build series key: BR_FOCUS_{INDICATOR}_{YEAR}_MEDIAN
                series_key = f"BR_FOCUS_{normalized_name}_{ref_year}_MEDIAN"

                # release_time is the survey publication date with SP timezone
                release_time = datetime(
                    obs_date.year, obs_date.month, obs_date.day,
                    8, 30,  # Focus is published ~8:30 AM Brasilia time
                    tzinfo=_SP_TZ,
                )

                all_records.append({
                    "_series_key": series_key,
                    "observation_date": obs_date,
                    "value": value,
                    "release_time": release_time,
                    "revision_number": 0,
                    "source": self.SOURCE_NAME,
                })

            # Rate limit between indicators
            if indicator != list(self.INDICATORS.keys())[-1]:
                await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

        self.log.info(
            "fetch_complete",
            total_records=len(all_records),
            start=start_str,
            end=end_str,
        )
        return all_records

    async def _ensure_series_metadata(
        self, series_key: str, source_id: int
    ) -> int:
        """Ensure a series_metadata row exists for the given series. Returns its id."""
        async with async_session_factory() as session:
            async with session.begin():
                stmt = pg_insert(SeriesMetadata).values(
                    source_id=source_id,
                    series_code=series_key,
                    name=series_key,
                    frequency="W",
                    country="BR",
                    unit="percent",
                    decimal_separator=".",
                    date_format="YYYY-MM-DD",
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
                    SeriesMetadata.series_code == series_key,
                )
            )
            row = result.scalar_one()
            return row

    # -----------------------------------------------------------------------
    # Store (abstract method implementation)
    # -----------------------------------------------------------------------
    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist fetched BCB Focus records to the macro_series table.

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
