"""FMP (Financial Modeling Prep) US Treasury yield curve connector.

Fetches daily nominal US Treasury yield curves from the FMP API as a
fallback/supplement to Treasury.gov (which frequently returns empty responses).

Stores data in the ``curves`` hypertable with curve_id ``UST_NOM``, matching
the same schema used by TreasuryGovConnector for seamless interoperability.

Data source:
    https://financialmodelingprep.com/api/v4/treasury

Rates in the FMP response are in percentage (e.g., 4.52 for 4.52%) and are
converted to decimal (4.52 -> 0.0452) before storage.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from typing import Any

import pandas as pd
import structlog

from src.connectors.base import BaseConnector
from src.core.models.curves import CurveData

logger = structlog.get_logger()


class FmpTreasuryConnector(BaseConnector):
    """Connector for US Treasury nominal yield curves via FMP API.

    Fetches daily treasury rates from FMP's ``/api/v4/treasury`` endpoint
    in 6-month chunks to stay within API limits.

    Usage::

        async with FmpTreasuryConnector() as conn:
            count = await conn.run(date(2010, 1, 1), date(2025, 12, 31))
    """

    SOURCE_NAME: str = "FMP_TREASURY"
    BASE_URL: str = "https://financialmodelingprep.com"
    RATE_LIMIT_PER_SECOND: float = 5.0
    TIMEOUT_SECONDS: float = 60.0

    # FMP API key from environment
    API_KEY: str = os.environ.get("FMP_API_KEY", "")

    # Tenor mapping: FMP JSON key -> (tenor_label, tenor_days)
    # Using the same tenor_days as TreasuryGovConnector for consistency
    TENOR_MAP: dict[str, tuple[str, int]] = {
        "month1":  ("1M",  30),
        "month2":  ("2M",  60),
        "month3":  ("3M",  90),
        "month6":  ("6M",  180),
        "year1":   ("1Y",  365),
        "year2":   ("2Y",  730),
        "year3":   ("3Y",  1095),
        "year5":   ("5Y",  1825),
        "year7":   ("7Y",  2555),
        "year10":  ("10Y", 3650),
        "year20":  ("20Y", 7300),
        "year30":  ("30Y", 10950),
    }

    # -----------------------------------------------------------------------
    # Fetch chunk
    # -----------------------------------------------------------------------
    async def _fetch_chunk(
        self,
        from_date: date,
        to_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch treasury rates for a date range (max ~6 months per call).

        Args:
            from_date: Inclusive start date.
            to_date: Inclusive end date.

        Returns:
            List of CurveData-compatible dicts.
        """
        url = (
            f"/api/v4/treasury"
            f"?from={from_date.isoformat()}"
            f"&to={to_date.isoformat()}"
            f"&apikey={self.API_KEY}"
        )

        records: list[dict[str, Any]] = []

        try:
            response = await self._request("GET", url)
            data = response.json()
        except Exception as exc:
            self.log.warning(
                "fmp_treasury_fetch_error",
                from_date=str(from_date),
                to_date=str(to_date),
                error=str(exc),
            )
            return []

        if not isinstance(data, list):
            self.log.warning(
                "fmp_treasury_unexpected_response",
                response_type=type(data).__name__,
            )
            return []

        for entry in data:
            try:
                curve_date = pd.to_datetime(entry["date"]).date()
            except (ValueError, TypeError, KeyError):
                continue

            for fmp_key, (tenor_label, tenor_days) in self.TENOR_MAP.items():
                raw_val = entry.get(fmp_key)
                if raw_val is None:
                    continue

                try:
                    rate_pct = float(raw_val)
                except (ValueError, TypeError):
                    continue

                # Convert percentage to decimal (4.52 -> 0.0452)
                rate_decimal = rate_pct / 100.0

                records.append({
                    "curve_id": "UST_NOM",
                    "curve_date": curve_date,
                    "tenor_days": tenor_days,
                    "tenor_label": tenor_label,
                    "rate": rate_decimal,
                    "curve_type": "sovereign_nominal",
                    "source": "FMP",
                })

        self.log.info(
            "fmp_treasury_chunk_parsed",
            from_date=str(from_date),
            to_date=str(to_date),
            record_count=len(records),
        )
        return records

    # -----------------------------------------------------------------------
    # Abstract method implementations
    # -----------------------------------------------------------------------
    async def fetch(
        self, start_date: date, end_date: date, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Fetch nominal US Treasury yield curves from FMP API.

        Splits the date range into 6-month chunks to stay within API limits.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            **kwargs: Additional arguments (unused).

        Returns:
            List of UST_NOM CurveData-compatible records.
        """
        all_records: list[dict[str, Any]] = []

        # Process in 6-month chunks
        chunk_start = start_date
        while chunk_start <= end_date:
            chunk_end = min(chunk_start + timedelta(days=180), end_date)

            self.log.info(
                "fmp_treasury_fetching_chunk",
                from_date=str(chunk_start),
                to_date=str(chunk_end),
            )

            records = await self._fetch_chunk(chunk_start, chunk_end)
            all_records.extend(records)

            chunk_start = chunk_end + timedelta(days=1)
            await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

        self.log.info(
            "fmp_treasury_fetch_complete",
            total_records=len(all_records),
        )
        return all_records

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
