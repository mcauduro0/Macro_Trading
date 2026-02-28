"""OECD SDMX connector for structural macro indicators.

Fetches output gap, NAIRU, potential GDP growth, and other structural
estimates from the OECD Economic Outlook (EO) database via the SDMX
REST API.  Uses httpx for direct HTTP calls (no extra dependencies).

Key datasets:
- OECD EO (Economic Outlook): output gap, NAIRU, potential GDP, TFP
- Covers 38 OECD member countries + key non-members

Target series (OECD EO variable codes):
- GAP: Output gap (% of potential GDP)
- NAIRU: Non-accelerating inflation rate of unemployment
- GDPV_ANNPCT: Real GDP growth (annual %)
- GDPVD: GDP deflator growth (%)
- UNR: Unemployment rate
- CPI: Consumer prices (annual % change)

The OECD SDMX REST API returns JSON (SDMX-JSON format).
Base URL: https://sdmx.oecd.org/public/rest

Data is stored in the ``macro_series`` hypertable alongside FRED/BCB data.
Series codes follow the pattern ``OECD_<COUNTRY>_<VARIABLE>``
(e.g. ``OECD_BRA_GAP``, ``OECD_USA_NAIRU``).
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

_PARIS_TZ = ZoneInfo("Europe/Paris")


class OecdSdmxConnector(BaseConnector):
    """Connector for OECD SDMX REST API (Economic Outlook data).

    Fetches structural estimates (output gap, NAIRU, potential growth)
    for OECD countries.  Data is semiannual (June and December EO releases)
    but covers annual observation periods.

    Usage::

        async with OecdSdmxConnector() as conn:
            count = await conn.run(date(2015, 1, 1), date(2025, 12, 31))
    """

    SOURCE_NAME: str = "OECD"
    BASE_URL: str = "https://sdmx.oecd.org/public/rest"
    RATE_LIMIT_PER_SECOND: float = 2.0
    TIMEOUT_SECONDS: float = 120.0
    MAX_RETRIES: int = 3

    # Countries of interest (ISO-3 codes used by OECD)
    COUNTRIES: dict[str, str] = {
        "BRA": "BR",  # Brazil
        "USA": "US",  # United States
        "MEX": "MX",  # Mexico
        "CHL": "CL",  # Chile
        "COL": "CO",  # Colombia
        "GBR": "GB",  # United Kingdom
        "DEU": "DE",  # Germany
        "JPN": "JP",  # Japan
        "CHN": "CN",  # China (non-member but included in EO)
        "IND": "IN",  # India
        "ZAF": "ZA",  # South Africa
        "TUR": "TR",  # Turkey
    }

    # OECD EO variable codes → internal series suffix
    VARIABLES: dict[str, str] = {
        "GAP": "OUTPUT_GAP",  # Output gap (% of potential GDP)
        "NAIRU": "NAIRU",  # NAIRU estimate
        "GDPV_ANNPCT": "GDP_GROWTH",  # Real GDP growth (%)
        "UNR": "UNEMP_RATE",  # Unemployment rate (%)
        "CPI": "CPI_GROWTH",  # CPI growth (annual %)
    }

    # OECD EO dataflow ID
    DATAFLOW = "EO"

    async def fetch(
        self,
        start_date: date,
        end_date: date,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Fetch OECD Economic Outlook structural estimates.

        Uses the SDMX REST API data endpoint with SDMX-JSON format.
        Each country+variable combination is fetched separately to
        respect API constraints and simplify parsing.

        Args:
            start_date: Start year for observations.
            end_date: End year for observations.
            **kwargs: Unused.

        Returns:
            List of record dicts with keys: observation_date, value,
            release_time, revision_number, source, _series_key.
        """
        all_records: list[dict[str, Any]] = []
        country_codes = "+".join(self.COUNTRIES.keys())
        variable_codes = "+".join(self.VARIABLES.keys())

        start_period = f"{start_date.year}"
        end_period = f"{end_date.year}"

        # SDMX REST URL structure:
        # /data/dataflow/{agency}/{dataflow}/{version}/{key}
        # Key structure for EO: {LOCATION}.{VARIABLE}.{MEASURE}
        # We use MEASURE=A (annual) for structural estimates
        key = f"{country_codes}.{variable_codes}.A"
        url = f"/data/dataflow/OECD.SDD.NAD/{self.DATAFLOW}/1.1/{key}"

        params = {
            "startPeriod": start_period,
            "endPeriod": end_period,
            "dimensionAtObservation": "TIME_PERIOD",
        }

        try:
            response = await self._request(
                "GET",
                url,
                params=params,
                headers={"Accept": "application/vnd.sdmx.data+json;version=2.0.0"},
            )
            data = response.json()
            records = self._parse_sdmx_json(data)
            all_records.extend(records)
        except Exception as exc:
            logger.warning(
                "oecd_eo_fetch_failed",
                error=str(exc),
            )
            # Fallback: fetch country by country
            all_records = await self._fetch_country_by_country(
                start_period,
                end_period,
            )

        logger.info(
            "oecd_fetch_complete",
            total_records=len(all_records),
            start=start_period,
            end=end_period,
        )
        return all_records

    async def _fetch_country_by_country(
        self,
        start_period: str,
        end_period: str,
    ) -> list[dict[str, Any]]:
        """Fallback: fetch each country+variable pair individually."""
        all_records: list[dict[str, Any]] = []

        for country_oecd, country_iso2 in self.COUNTRIES.items():
            for var_code, var_suffix in self.VARIABLES.items():
                try:
                    key = f"{country_oecd}.{var_code}.A"
                    url = f"/data/dataflow/OECD.SDD.NAD/{self.DATAFLOW}/1.1/{key}"
                    params = {
                        "startPeriod": start_period,
                        "endPeriod": end_period,
                        "dimensionAtObservation": "TIME_PERIOD",
                    }

                    response = await self._request(
                        "GET",
                        url,
                        params=params,
                        headers={
                            "Accept": "application/vnd.sdmx.data+json;version=2.0.0"
                        },
                    )
                    data = response.json()
                    records = self._parse_sdmx_json(data)
                    all_records.extend(records)
                except Exception as exc:
                    logger.debug(
                        "oecd_country_var_failed",
                        country=country_oecd,
                        variable=var_code,
                        error=str(exc),
                    )

                await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

        return all_records

    def _parse_sdmx_json(self, data: dict) -> list[dict[str, Any]]:
        """Parse SDMX-JSON v2.0 response into flat records.

        The SDMX-JSON structure nests observations under
        data.dataSets[0].observations with compound keys.

        Returns:
            List of record dicts ready for store().
        """
        records: list[dict[str, Any]] = []

        try:
            datasets = data.get("data", {}).get("dataSets", [])
            if not datasets:
                return records

            dataset = datasets[0]
            structure = data.get("data", {}).get("structures", [{}])[0]

            # Resolve dimension values
            dims = structure.get("dimensions", {}).get("observation", [])
            series_dims = structure.get("dimensions", {}).get("series", [])

            # Build dimension value lookups
            time_values = []
            for dim in dims:
                if dim.get("id") == "TIME_PERIOD":
                    time_values = [v.get("id", "") for v in dim.get("values", [])]

            series_dim_lookups = []
            for dim in series_dims:
                values = [v.get("id", "") for v in dim.get("values", [])]
                series_dim_lookups.append(
                    {
                        "id": dim.get("id", ""),
                        "values": values,
                    }
                )

            # Parse series and observations
            series_data = dataset.get("series", {})
            for series_key, series_obj in series_data.items():
                # Decode series key (colon-separated dimension indices)
                key_parts = series_key.split(":")
                series_attrs = {}
                for i, part in enumerate(key_parts):
                    if i < len(series_dim_lookups):
                        dim_info = series_dim_lookups[i]
                        idx = int(part)
                        if idx < len(dim_info["values"]):
                            series_attrs[dim_info["id"]] = dim_info["values"][idx]

                country_oecd = series_attrs.get("REF_AREA", "")
                variable = series_attrs.get("MEASURE", "") or series_attrs.get(
                    "SUBJECT", ""
                )

                country_iso2 = self.COUNTRIES.get(country_oecd, country_oecd)
                var_suffix = self.VARIABLES.get(variable, variable)
                series_name = f"OECD_{country_iso2}_{var_suffix}"

                observations = series_obj.get("observations", {})
                for obs_key, obs_values in observations.items():
                    try:
                        time_idx = int(obs_key)
                        if time_idx >= len(time_values):
                            continue
                        period = time_values[time_idx]

                        # Parse period (typically "YYYY" for annual)
                        year = int(period[:4])
                        obs_date = date(year, 12, 31)  # Annual → end of year

                        value = obs_values[0] if obs_values else None
                        if value is None:
                            continue

                        records.append(
                            {
                                "observation_date": obs_date,
                                "value": float(value),
                                "release_time": datetime.now(tz=_PARIS_TZ),
                                "revision_number": 0,
                                "source": self.SOURCE_NAME,
                                "_series_key": series_name,
                            }
                        )
                    except (ValueError, TypeError, IndexError):
                        continue

        except Exception as exc:
            logger.warning("sdmx_json_parse_failed", error=str(exc))

        return records

    async def _ensure_series_metadata(
        self,
        series_key: str,
        source_id: int,
    ) -> int:
        """Ensure a series_metadata row exists for the given OECD series."""
        # Extract country from series key (e.g. OECD_BR_OUTPUT_GAP → BR)
        parts = series_key.split("_")
        country = parts[1] if len(parts) >= 3 else "XX"

        async with async_session_factory() as session:
            async with session.begin():
                stmt = (
                    pg_insert(SeriesMetadata)
                    .values(
                        source_id=source_id,
                        series_code=series_key,
                        name=series_key,
                        frequency="A",  # Annual
                        country=country,
                        unit="percent",
                        decimal_separator=".",
                        date_format="YYYY-MM-DD",
                        is_revisable=True,  # OECD EO revises estimates each release
                        release_timezone="Europe/Paris",
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
            return result.scalar_one()

    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist OECD records to the macro_series table.

        Uses ON CONFLICT DO NOTHING for idempotent writes.

        Args:
            records: List of record dicts from fetch().

        Returns:
            Number of rows actually inserted.
        """
        if not records:
            return 0

        by_key: dict[str, list[dict[str, Any]]] = {}
        for rec in records:
            key = rec.pop("_series_key", None)
            if key is not None:
                by_key.setdefault(key, []).append(rec)

        source_id = await self._ensure_data_source()

        all_insertable: list[dict[str, Any]] = []
        for series_key, recs in by_key.items():
            series_id = await self._ensure_series_metadata(series_key, source_id)
            for rec in recs:
                rec["series_id"] = series_id
                all_insertable.append(rec)

        return await self._bulk_insert(
            MacroSeries, all_insertable, "uq_macro_series_natural_key"
        )
