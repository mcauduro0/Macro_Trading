"""Trading Economics Brazilian DI curve connector.

Fetches daily Brazilian government bond yields (DI swap rates) for tenors
2Y, 5Y, and 10Y from Trading Economics, supplementing the BCB SGS data
which only covers tenors up to 360 days.

Stores data in the ``curves`` hypertable with curve_id ``DI_PRE``, using
tenor_days that match what MonetaryFeatureEngine expects:
  504 (2Y), 1260 (5Y), 2520 (10Y).

Data source:
    https://api.tradingeconomics.com/markets/historical/{symbol}

Rates from Trading Economics are in percentage (e.g., 13.427 for 13.427%)
and are converted to decimal (13.427 -> 0.13427) before storage.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from typing import Any

import httpx
import pandas as pd
import structlog

from src.connectors.base import BaseConnector
from src.core.models.curves import CurveData

logger = structlog.get_logger()


class TradingEconDiCurveConnector(BaseConnector):
    """Connector for Brazilian DI curve (long tenors) via Trading Economics.

    Fetches daily bond yield data for GEBR2Y, GEBR5Y, GEBR10Y from
    Trading Economics' markets/historical endpoint.

    Usage::

        async with TradingEconDiCurveConnector() as conn:
            count = await conn.run(date(2010, 1, 1), date(2025, 12, 31))
    """

    SOURCE_NAME: str = "TE_DI_CURVE"
    BASE_URL: str = "https://api.tradingeconomics.com"
    RATE_LIMIT_PER_SECOND: float = 2.0
    TIMEOUT_SECONDS: float = 60.0

    # Trading Economics API credentials from environment
    TE_API_KEY: str = os.environ.get("TE_API_KEY", "")

    # Symbol mapping: TE symbol -> (tenor_label, tenor_days)
    # tenor_days aligned with MonetaryFeatureEngine expectations
    SYMBOL_MAP: dict[str, tuple[str, int]] = {
        "GEBR2Y:IND":  ("2Y",  504),    # ~2 years in trading days
        "GEBR5Y:IND":  ("5Y",  1260),   # ~5 years in trading days
        "GEBR10Y:IND": ("10Y", 2520),   # ~10 years in trading days
    }

    # -----------------------------------------------------------------------
    # Fetch one symbol
    # -----------------------------------------------------------------------
    async def _fetch_symbol(
        self,
        symbol: str,
        tenor_label: str,
        tenor_days: int,
        from_date: date,
        to_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch historical data for a single bond yield symbol.

        Args:
            symbol: Trading Economics symbol (e.g., "GEBR10Y:IND").
            tenor_label: Human-readable tenor (e.g., "10Y").
            tenor_days: Tenor in trading days.
            from_date: Inclusive start date.
            to_date: Inclusive end date.

        Returns:
            List of CurveData-compatible dicts.
        """
        url = (
            f"/markets/historical/{symbol}"
            f"?d1={from_date.isoformat()}"
            f"&d2={to_date.isoformat()}"
            f"&c={self.TE_API_KEY}"
        )

        records: list[dict[str, Any]] = []

        try:
            response = await self._request("GET", url)
            data = response.json()
        except Exception as exc:
            self.log.warning(
                "te_di_fetch_error",
                symbol=symbol,
                from_date=str(from_date),
                to_date=str(to_date),
                error=str(exc),
            )
            return []

        if not isinstance(data, list):
            self.log.warning(
                "te_di_unexpected_response",
                symbol=symbol,
                response_type=type(data).__name__,
            )
            return []

        for entry in data:
            try:
                # TE date format: "DD/MM/YYYY" or ISO
                date_str = entry.get("Date", "")
                curve_date = pd.to_datetime(date_str, dayfirst=True).date()
            except (ValueError, TypeError):
                continue

            # Use Close price as the rate
            raw_val = entry.get("Close")
            if raw_val is None:
                continue

            try:
                rate_pct = float(raw_val)
            except (ValueError, TypeError):
                continue

            # Convert percentage to decimal (13.427 -> 0.13427)
            rate_decimal = rate_pct / 100.0

            records.append({
                "curve_id": "DI_PRE",
                "curve_date": curve_date,
                "tenor_days": tenor_days,
                "tenor_label": tenor_label,
                "rate": rate_decimal,
                "curve_type": "swap",
                "source": "TRADING_ECONOMICS",
            })

        self.log.info(
            "te_di_symbol_parsed",
            symbol=symbol,
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
        """Fetch Brazilian DI curve (long tenors) from Trading Economics.

        Fetches 2Y, 5Y, and 10Y bond yields in 1-year chunks per symbol.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            **kwargs: Additional arguments (unused).

        Returns:
            List of DI_PRE CurveData-compatible records.
        """
        all_records: list[dict[str, Any]] = []

        for symbol, (tenor_label, tenor_days) in self.SYMBOL_MAP.items():
            self.log.info(
                "te_di_fetching_symbol",
                symbol=symbol,
                tenor=tenor_label,
            )

            # Process in 1-year chunks (TE API works well with yearly ranges)
            chunk_start = start_date
            while chunk_start <= end_date:
                chunk_end = min(
                    date(chunk_start.year, 12, 31),
                    end_date,
                )

                records = await self._fetch_symbol(
                    symbol, tenor_label, tenor_days,
                    chunk_start, chunk_end,
                )
                all_records.extend(records)

                chunk_start = date(chunk_start.year + 1, 1, 1)
                await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

        self.log.info(
            "te_di_fetch_complete",
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
