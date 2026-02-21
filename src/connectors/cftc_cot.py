"""CFTC Commitment of Traders (COT) connector -- disaggregated futures positioning.

Fetches positioning data from the CFTC's disaggregated futures-only reports
via two sources:
1. Historical: yearly ZIP files at cftc.gov/files/dea/history/
2. Current week: Socrata CSV API at publicreporting.cftc.gov

Computes net positions (long - short) for 4 categories x 12 contracts = 48 series,
and stores records to the flow_data hypertable.

CONTRACT_CODES maps 12 key futures contracts to their CFTC_Contract_Market_Code.
CATEGORIES maps 4 trader categories to disaggregated report column name pairs.
"""

from __future__ import annotations

import asyncio
import io
import zipfile
from datetime import date, datetime
from typing import Any

import httpx
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.connectors.base import BaseConnector, DataParsingError
from src.core.database import async_session_factory
from src.core.models.data_sources import DataSource
from src.core.models.flow_data import FlowData
from src.core.models.series_metadata import SeriesMetadata


class CftcCotConnector(BaseConnector):
    """Connector for CFTC Disaggregated Futures-Only COT reports.

    Downloads yearly ZIP archives for historical data and Socrata CSV
    for current-week data.  Computes net positions for 12 contracts x
    4 trader categories = 48 series, stored in the ``flow_data`` table.

    Usage::

        async with CftcCotConnector() as conn:
            count = await conn.run(date(2020, 1, 1), date(2025, 12, 31))
    """

    SOURCE_NAME: str = "CFTC_COT"
    BASE_URL: str = "https://www.cftc.gov"
    RATE_LIMIT_PER_SECOND: float = 1.0
    TIMEOUT_SECONDS: float = 120.0
    SOCRATA_BASE_URL: str = "https://publicreporting.cftc.gov"

    # ------------------------------------------------------------------
    # Contract registry: short name -> CFTC_Contract_Market_Code
    # ------------------------------------------------------------------
    CONTRACT_CODES: dict[str, str] = {
        "ES": "13874A",   # E-mini S&P 500
        "NQ": "209742",   # E-mini NASDAQ 100
        "YM": "124603",   # E-mini Dow
        "TY": "043602",   # 10-Year T-Note
        "US": "020601",   # 30-Year T-Bond
        "FV": "044601",   # 5-Year T-Note
        "TU": "042601",   # 2-Year T-Note
        "ED": "132741",   # Eurodollar (legacy, may use SOFR now)
        "CL": "067651",   # Crude Oil WTI
        "GC": "088691",   # Gold
        "SI": "084691",   # Silver
        "DX": "098662",   # US Dollar Index
    }

    # Reverse lookup: code -> short name
    _reverse_contract_map: dict[str, str] = {v: k for k, v in CONTRACT_CODES.items()}

    # ------------------------------------------------------------------
    # Position categories: category_name -> (long_col, short_col)
    # ------------------------------------------------------------------
    CATEGORIES: dict[str, tuple[str, str]] = {
        "DEALER": ("Dealer_Positions_Long_All", "Dealer_Positions_Short_All"),
        "ASSETMGR": ("Asset_Mgr_Positions_Long_All", "Asset_Mgr_Positions_Short_All"),
        "LEVERAGED": ("Lev_Money_Positions_Long_All", "Lev_Money_Positions_Short_All"),
        "OTHER": ("Other_Rept_Positions_Long_All", "Other_Rept_Positions_Short_All"),
    }

    # ------------------------------------------------------------------
    # Historical ZIP download
    # ------------------------------------------------------------------
    async def _download_historical_year(self, year: int) -> pd.DataFrame:
        """Download and parse one year of CFTC disaggregated data from ZIP.

        Args:
            year: Calendar year to download (e.g., 2023).

        Returns:
            pandas DataFrame filtered to tracked contracts, or empty DataFrame
            on download/parse error.
        """
        url = f"/files/dea/history/fut_disagg_txt_{year}.zip"

        try:
            response = await self._request("GET", url)
        except Exception as exc:
            self.log.warning(
                "cftc_zip_download_error",
                year=year,
                error=str(exc),
            )
            return pd.DataFrame()

        try:
            zf = zipfile.ZipFile(io.BytesIO(response.content))
            # ZIP contains a single CSV file
            csv_name = zf.namelist()[0]
            csv_bytes = zf.read(csv_name)

            df: pd.DataFrame = await asyncio.to_thread(
                pd.read_csv, io.BytesIO(csv_bytes)
            )
        except Exception as exc:
            self.log.warning(
                "cftc_zip_parse_error",
                year=year,
                error=str(exc),
            )
            return pd.DataFrame()

        if df.empty:
            return df

        # Normalise the contract market code column to string for matching
        code_col = "CFTC_Contract_Market_Code"
        if code_col not in df.columns:
            self.log.warning("cftc_missing_contract_code_column", year=year)
            return pd.DataFrame()

        df[code_col] = df[code_col].astype(str).str.strip()
        tracked_codes = set(self.CONTRACT_CODES.values())
        filtered = df[df[code_col].isin(tracked_codes)].copy()

        self.log.info(
            "cftc_historical_year_loaded",
            year=year,
            rows_total=len(df),
            rows_tracked=len(filtered),
        )
        return filtered

    # ------------------------------------------------------------------
    # Current-week Socrata CSV
    # ------------------------------------------------------------------
    async def _fetch_current_week(self) -> pd.DataFrame:
        """Fetch current-week data from the CFTC Socrata CSV API.

        Returns:
            pandas DataFrame filtered to tracked contracts, or empty
            DataFrame on error.
        """
        try:
            async with httpx.AsyncClient(
                base_url=self.SOCRATA_BASE_URL,
                timeout=httpx.Timeout(self.TIMEOUT_SECONDS),
            ) as socrata_client:
                response = await socrata_client.get(
                    "/resource/72hh-3qpy.csv",
                    params={"$limit": "5000"},
                )
                response.raise_for_status()
        except Exception as exc:
            self.log.warning(
                "cftc_socrata_fetch_error",
                error=str(exc),
            )
            return pd.DataFrame()

        try:
            df: pd.DataFrame = await asyncio.to_thread(
                pd.read_csv, io.StringIO(response.text)
            )
        except Exception as exc:
            self.log.warning(
                "cftc_socrata_parse_error",
                error=str(exc),
            )
            return pd.DataFrame()

        if df.empty:
            return df

        code_col = "cftc_contract_market_code"
        # Socrata may use lowercase column names; normalise
        if code_col not in df.columns:
            # Try the capitalised variant
            code_col = "CFTC_Contract_Market_Code"
            if code_col not in df.columns:
                self.log.warning("cftc_socrata_missing_contract_code_column")
                return pd.DataFrame()

        df[code_col] = df[code_col].astype(str).str.strip()
        tracked_codes = set(self.CONTRACT_CODES.values())
        filtered = df[df[code_col].isin(tracked_codes)].copy()

        # Normalise column names to match ZIP format if needed
        rename_map: dict[str, str] = {}
        for col in filtered.columns:
            upper = col.strip()
            if upper != col:
                rename_map[col] = upper
        if rename_map:
            filtered = filtered.rename(columns=rename_map)

        # Ensure report date column exists (Socrata may differ)
        date_col = "Report_Date_as_YYYY-MM-DD"
        if date_col not in filtered.columns:
            # Try Socrata's lowercase variant
            for candidate in ("report_date_as_yyyy_mm_dd", "report_date_as_yyyy-mm-dd"):
                if candidate in filtered.columns:
                    filtered = filtered.rename(columns={candidate: date_col})
                    break

        self.log.info(
            "cftc_socrata_loaded",
            rows_total=len(df),
            rows_tracked=len(filtered),
        )
        return filtered

    # ------------------------------------------------------------------
    # Net position computation
    # ------------------------------------------------------------------
    def compute_net_positions(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """Compute net positions for tracked contracts and categories.

        Args:
            df: Combined DataFrame from ZIP and/or Socrata sources.

        Returns:
            List of record dicts ready for storage (tagged with ``_series_key``).
        """
        if df.empty:
            return []

        records: list[dict[str, Any]] = []

        date_col = "Report_Date_as_YYYY-MM-DD"
        code_col = "CFTC_Contract_Market_Code"

        if date_col not in df.columns or code_col not in df.columns:
            self.log.warning(
                "cftc_missing_required_columns",
                columns=list(df.columns[:20]),
            )
            return []

        for _, row in df.iterrows():
            # Parse report date
            try:
                report_date = pd.to_datetime(row[date_col]).date()
            except Exception:
                continue

            # Lookup contract name
            contract_code = str(row[code_col]).strip()
            contract_name = self._reverse_contract_map.get(contract_code)
            if contract_name is None:
                continue

            for cat_name, (long_col, short_col) in self.CATEGORIES.items():
                # Validate columns exist
                if long_col not in df.columns:
                    self.log.warning(
                        "cftc_missing_category_column",
                        column=long_col,
                        category=cat_name,
                    )
                    continue
                if short_col not in df.columns:
                    self.log.warning(
                        "cftc_missing_category_column",
                        column=short_col,
                        category=cat_name,
                    )
                    continue

                try:
                    long_val = float(row[long_col])
                    short_val = float(row[short_col])
                except (ValueError, TypeError):
                    continue

                net = long_val - short_val
                series_key = f"CFTC_{contract_name}_{cat_name}_NET"

                records.append({
                    "_series_key": series_key,
                    "observation_date": report_date,
                    "value": net,
                    "flow_type": f"CFTC_{cat_name}_NET",
                    "unit": "contracts",
                    "release_time": None,
                })

        return records

    # ------------------------------------------------------------------
    # Fetch (abstract method implementation)
    # ------------------------------------------------------------------
    async def fetch(
        self,
        start_date: date,
        end_date: date,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Fetch CFTC COT data for the given date range.

        Downloads historical ZIP files for years before the current year,
        and the Socrata CSV for the current year's data.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            **kwargs: Additional arguments (unused).

        Returns:
            List of record dicts with net positions tagged with ``_series_key``.
        """
        current_year = datetime.utcnow().year
        all_dfs: list[pd.DataFrame] = []

        # Historical years: use ZIP files
        for year in range(start_date.year, min(end_date.year, current_year - 1) + 1):
            self.log.info("cftc_fetching_historical", year=year)
            df = await self._download_historical_year(year)
            if not df.empty:
                all_dfs.append(df)
            await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

        # Current year: use Socrata API
        if end_date.year >= current_year:
            self.log.info("cftc_fetching_current_week")
            df = await self._fetch_current_week()
            if not df.empty:
                all_dfs.append(df)

        if not all_dfs:
            return []

        combined = pd.concat(all_dfs, ignore_index=True)
        records = self.compute_net_positions(combined)

        # Filter to requested date range
        filtered = [
            r for r in records
            if start_date <= r["observation_date"] <= end_date
        ]

        self.log.info(
            "cftc_fetch_complete",
            total_records=len(records),
            filtered_records=len(filtered),
        )
        return filtered

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------
    async def _ensure_data_source(self) -> int:
        """Ensure a data_sources row exists for CFTC_COT. Returns its id."""
        async with async_session_factory() as session:
            async with session.begin():
                stmt = pg_insert(DataSource).values(
                    name=self.SOURCE_NAME,
                    base_url=self.BASE_URL,
                    auth_type="none",
                    rate_limit_per_minute=int(self.RATE_LIMIT_PER_SECOND * 60),
                    default_locale="en-US",
                    notes="CFTC COT - Disaggregated Futures Positioning",
                    is_active=True,
                ).on_conflict_do_nothing(index_elements=["name"])
                await session.execute(stmt)

            result = await session.execute(
                select(DataSource.id).where(DataSource.name == self.SOURCE_NAME)
            )
            row = result.scalar_one()
            return row

    async def _ensure_series_metadata(
        self,
        series_key: str,
        source_id: int,
    ) -> int:
        """Ensure a series_metadata row exists. Returns its id."""
        async with async_session_factory() as session:
            async with session.begin():
                stmt = pg_insert(SeriesMetadata).values(
                    source_id=source_id,
                    series_code=series_key,
                    name=series_key,
                    frequency="W",
                    country="US",
                    unit="contracts",
                    decimal_separator=".",
                    date_format="YYYY-MM-DD",
                    is_revisable=False,
                    release_timezone="America/New_York",
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

    # ------------------------------------------------------------------
    # Store (abstract method implementation)
    # ------------------------------------------------------------------
    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist CFTC COT records to the flow_data table.

        Ensures data_source and series_metadata rows exist before inserting.
        Uses ON CONFLICT DO NOTHING for idempotent writes.

        Args:
            records: List of record dicts from fetch(), each with ``_series_key``.

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
            FlowData, all_insertable, "uq_flow_data_natural_key"
        )
