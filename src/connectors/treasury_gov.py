"""US Treasury yield curve connector.

Fetches daily nominal (UST_NOM) and real/TIPS (UST_REAL) yield curves from
Treasury.gov CSV files, one year at a time. Computes breakeven inflation
yields (UST_BEI = nominal - real) at matching tenors.

All three curve families are stored in the ``curves`` hypertable via
``_bulk_insert(CurveData, ...)`` with ON CONFLICT DO NOTHING.

Data source:
    https://home.treasury.gov/resource-center/data-chart-center/interest-rates

Rates in the CSV files are in percentage (e.g., 4.52 for 4.52%) and are
converted to decimal (4.52 -> 0.0452) before storage.
"""

from __future__ import annotations

import asyncio
import io
from datetime import date
from typing import Any

import pandas as pd
import structlog

from src.connectors.base import BaseConnector
from src.core.models.curves import CurveData

logger = structlog.get_logger()


class TreasuryGovConnector(BaseConnector):
    """Connector for US Treasury nominal, real (TIPS), and breakeven yield curves.

    Usage::

        async with TreasuryGovConnector() as conn:
            count = await conn.run(date(2024, 1, 1), date(2025, 12, 31))
    """

    SOURCE_NAME: str = "TREASURY_GOV"
    BASE_URL: str = "https://home.treasury.gov"
    RATE_LIMIT_PER_SECOND: float = 2.0
    TIMEOUT_SECONDS: float = 60.0

    # URL templates for Treasury CSV downloads
    NOMINAL_URL: str = (
        "/resource-center/data-chart-center/interest-rates/"
        "daily-treasury-rates.csv/all/{year}"
        "?type=daily_treasury_yield_curve"
        "&field_tdr_date_value={year}&_format=csv"
    )
    REAL_URL: str = (
        "/resource-center/data-chart-center/interest-rates/"
        "daily-treasury-rates.csv/all/{year}"
        "?type=daily_treasury_real_yield_curve"
        "&field_tdr_date_value={year}&_format=csv"
    )

    # Tenor mapping: CSV column name -> (tenor_label, tenor_days)
    TENOR_MAP: dict[str, tuple[str, int]] = {
        "1 Mo":  ("1M",  30),
        "2 Mo":  ("2M",  60),
        "3 Mo":  ("3M",  90),
        "4 Mo":  ("4M",  120),
        "6 Mo":  ("6M",  180),
        "1 Yr":  ("1Y",  365),
        "2 Yr":  ("2Y",  730),
        "3 Yr":  ("3Y",  1095),
        "5 Yr":  ("5Y",  1825),
        "7 Yr":  ("7Y",  2555),
        "10 Yr": ("10Y", 3650),
        "20 Yr": ("20Y", 7300),
        "30 Yr": ("30Y", 10950),
    }

    # -----------------------------------------------------------------------
    # CSV parsing
    # -----------------------------------------------------------------------
    async def _fetch_curve_csv(
        self,
        url_template: str,
        year: int,
        curve_id: str,
        curve_type: str,
    ) -> list[dict[str, Any]]:
        """Fetch and parse a Treasury yield curve CSV for a single year.

        Args:
            url_template: URL template with ``{year}`` placeholder.
            year: Calendar year to fetch.
            curve_id: Curve identifier (e.g., 'UST_NOM', 'UST_REAL').
            curve_type: Curve type string (e.g., 'sovereign_nominal').

        Returns:
            List of CurveData-compatible dicts.
        """
        url = url_template.format(year=year)
        records: list[dict[str, Any]] = []

        try:
            response = await self._request("GET", url)
            csv_text = response.text
        except Exception as exc:
            self.log.warning(
                "treasury_csv_fetch_error",
                curve_id=curve_id,
                year=year,
                error=str(exc),
            )
            return []

        # Validate response is CSV, not HTML error page
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("text/html") or csv_text.strip().startswith("<!"):
            self.log.warning(
                "treasury_csv_html_response",
                curve_id=curve_id,
                year=year,
                content_type=content_type,
            )
            return []

        if not csv_text.strip():
            self.log.warning("treasury_csv_empty_response", curve_id=curve_id, year=year)
            return []

        # Parse CSV in a thread to avoid blocking the event loop
        try:
            df = await asyncio.to_thread(
                pd.read_csv, io.StringIO(csv_text)
            )
        except Exception as exc:
            self.log.warning(
                "treasury_csv_parse_error",
                curve_id=curve_id,
                year=year,
                error=str(exc),
            )
            return []

        if df.empty or "Date" not in df.columns:
            self.log.warning(
                "treasury_csv_empty_or_no_date_column",
                curve_id=curve_id,
                year=year,
                columns=list(df.columns),
            )
            return []

        for _, row in df.iterrows():
            # Parse date column
            try:
                curve_date = pd.to_datetime(row["Date"]).date()
            except (ValueError, TypeError):
                continue

            # Process each known tenor column
            for col_name, (tenor_label, tenor_days) in self.TENOR_MAP.items():
                if col_name not in df.columns:
                    continue  # Skip unknown/missing columns dynamically

                raw_val = row.get(col_name)

                # Skip NaN, empty, and "N/A" values
                if pd.isna(raw_val):
                    continue
                if isinstance(raw_val, str):
                    stripped = raw_val.strip()
                    if stripped in ("", "N/A", "n/a", "-"):
                        continue
                    try:
                        rate_pct = float(stripped)
                    except ValueError:
                        continue
                else:
                    try:
                        rate_pct = float(raw_val)
                    except (ValueError, TypeError):
                        continue

                # Convert percentage to decimal (4.52 -> 0.0452)
                rate_decimal = rate_pct / 100.0

                records.append({
                    "curve_id": curve_id,
                    "curve_date": curve_date,
                    "tenor_days": tenor_days,
                    "tenor_label": tenor_label,
                    "rate": rate_decimal,
                    "curve_type": curve_type,
                    "source": "TREASURY_GOV",
                })

        self.log.info(
            "treasury_csv_parsed",
            curve_id=curve_id,
            year=year,
            record_count=len(records),
        )
        return records

    # -----------------------------------------------------------------------
    # Breakeven computation
    # -----------------------------------------------------------------------
    @staticmethod
    def _compute_breakeven(
        nominal_records: list[dict[str, Any]],
        real_records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Compute breakeven inflation yield curve (UST_BEI = nominal - real).

        Matches records on (curve_date, tenor_label) and computes the
        breakeven rate at each matching tenor.

        Args:
            nominal_records: UST_NOM CurveData-compatible dicts.
            real_records: UST_REAL CurveData-compatible dicts.

        Returns:
            List of UST_BEI CurveData-compatible dicts.
        """
        # Index real rates by (curve_date, tenor_label)
        real_index: dict[tuple[date, str], dict[str, Any]] = {}
        for rec in real_records:
            key = (rec["curve_date"], rec["tenor_label"])
            real_index[key] = rec

        breakeven_records: list[dict[str, Any]] = []
        for nom_rec in nominal_records:
            key = (nom_rec["curve_date"], nom_rec["tenor_label"])
            real_rec = real_index.get(key)
            if real_rec is None:
                continue

            bei_rate = nom_rec["rate"] - real_rec["rate"]

            breakeven_records.append({
                "curve_id": "UST_BEI",
                "curve_date": nom_rec["curve_date"],
                "tenor_days": nom_rec["tenor_days"],
                "tenor_label": nom_rec["tenor_label"],
                "rate": bei_rate,
                "curve_type": "breakeven",
                "source": "TREASURY_GOV",
            })

        return breakeven_records

    # -----------------------------------------------------------------------
    # Abstract method implementations
    # -----------------------------------------------------------------------
    async def fetch(
        self, start_date: date, end_date: date, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Fetch nominal, real, and breakeven US Treasury yield curves.

        Fetches CSV data year by year, filters to [start_date, end_date],
        and computes breakeven yields at matching tenors.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            **kwargs: Additional arguments (unused).

        Returns:
            Combined list of UST_NOM, UST_REAL, and UST_BEI records.
        """
        all_nominal: list[dict[str, Any]] = []
        all_real: list[dict[str, Any]] = []

        for year in range(start_date.year, end_date.year + 1):
            self.log.info("fetching_treasury_year", year=year)

            nominal = await self._fetch_curve_csv(
                self.NOMINAL_URL, year, "UST_NOM", "sovereign_nominal"
            )
            all_nominal.extend(nominal)

            await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

            real = await self._fetch_curve_csv(
                self.REAL_URL, year, "UST_REAL", "sovereign_real"
            )
            all_real.extend(real)

            await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

        # Filter to requested date range
        all_nominal = [
            r for r in all_nominal
            if start_date <= r["curve_date"] <= end_date
        ]
        all_real = [
            r for r in all_real
            if start_date <= r["curve_date"] <= end_date
        ]

        # Compute breakeven
        breakeven = self._compute_breakeven(all_nominal, all_real)

        total = all_nominal + all_real + breakeven
        self.log.info(
            "fetch_complete",
            nominal_count=len(all_nominal),
            real_count=len(all_real),
            breakeven_count=len(breakeven),
            total=len(total),
        )
        return total

    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist curve records to the curves hypertable.

        Uses ON CONFLICT DO NOTHING on the natural key
        (curve_id, curve_date, tenor_days) for idempotent writes.

        Args:
            records: List of CurveData-compatible dicts.

        Returns:
            Number of rows actually inserted (excludes conflicts).
        """
        return await self._bulk_insert(
            CurveData, records, "uq_curves_natural_key"
        )
