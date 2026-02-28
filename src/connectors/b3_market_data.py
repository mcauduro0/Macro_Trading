"""B3 / Tesouro Direto connector for Brazilian yield curves.

Fetches two curve families:

1. **DI Swap Curve (DI_PRE)** -- 12 tenors (30d to 360d) from BCB SGS series
   #7805 through #7816. Rates are published as percentages by the BCB and are
   converted to decimal (13.50 -> 0.1350) before storage.

2. **NTN-B Real Rate Curve (NTN_B_REAL)** -- Real (inflation-linked) sovereign
   bond yields scraped from the Tesouro Direto JSON API. This is a best-effort
   source: if the endpoint returns an error (403/404/timeout), the connector
   gracefully returns an empty list for NTN-B and still stores the DI curve.

Both curve families are stored in the ``curves`` hypertable via
``_bulk_insert(CurveData, ...)`` with ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

import structlog

from src.connectors.base import BaseConnector
from src.core.models.curves import CurveData
from src.core.utils.parsing import parse_numeric_value

logger = structlog.get_logger()


class B3MarketDataConnector(BaseConnector):
    """Connector for DI swap curve (BCB SGS) and NTN-B real rates (Tesouro Direto).

    Usage::

        async with B3MarketDataConnector() as conn:
            count = await conn.run(date(2024, 1, 1), date(2025, 1, 1))
    """

    SOURCE_NAME: str = "B3_MARKET_DATA"
    BASE_URL: str = "https://api.bcb.gov.br"
    RATE_LIMIT_PER_SECOND: float = 3.0
    MAX_DATE_RANGE_YEARS: int = 10

    TESOURO_DIRETO_URL: str = (
        "https://www.tesourodireto.com.br/json/br/com/b3/tesourodireto/"
        "service/api/treasurybondsinfo.json"
    )

    # -----------------------------------------------------------------------
    # DI Swap Curve registry: name -> (SGS code, tenor_label, tenor_days)
    # -----------------------------------------------------------------------
    DI_SWAP_REGISTRY: dict[str, tuple[int, str, int]] = {
        "DI_SWAP_30D": (7805, "1M", 30),
        "DI_SWAP_60D": (7806, "2M", 60),
        "DI_SWAP_90D": (7807, "3M", 90),
        "DI_SWAP_120D": (7808, "4M", 120),
        "DI_SWAP_150D": (7809, "5M", 150),
        "DI_SWAP_180D": (7810, "6M", 180),
        "DI_SWAP_210D": (7811, "7M", 210),
        "DI_SWAP_240D": (7812, "8M", 240),
        "DI_SWAP_270D": (7813, "9M", 270),
        "DI_SWAP_300D": (7814, "10M", 300),
        "DI_SWAP_330D": (7815, "11M", 330),
        "DI_SWAP_360D": (7816, "12M", 360),
    }

    # -----------------------------------------------------------------------
    # Fetch DI swap curve from BCB SGS
    # -----------------------------------------------------------------------
    async def fetch_di_curve(
        self, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Fetch the DI swap curve (12 tenors) from BCB SGS series #7805-#7816.

        Rates are converted from percentage to decimal (e.g., 13.50 -> 0.1350).

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.

        Returns:
            List of CurveData-compatible dicts with curve_id='DI_PRE'.
        """
        all_records: list[dict[str, Any]] = []
        total = len(self.DI_SWAP_REGISTRY)
        chunks = self._chunk_date_range(start_date, end_date)

        for i, (series_name, (sgs_code, tenor_label, tenor_days)) in enumerate(
            self.DI_SWAP_REGISTRY.items(), 1
        ):
            self.log.info(
                "fetching_di_tenor",
                series_name=series_name,
                sgs_code=sgs_code,
                progress=f"{i}/{total}",
            )

            for chunk_start, chunk_end in chunks:
                url = f"/dados/serie/bcdata.sgs.{sgs_code}/dados"
                params = {
                    "formato": "json",
                    "dataInicial": chunk_start.strftime("%d/%m/%Y"),
                    "dataFinal": chunk_end.strftime("%d/%m/%Y"),
                }

                try:
                    response = await self._request("GET", url, params=params)
                    data = response.json()
                except Exception as exc:
                    self.log.warning(
                        "di_tenor_fetch_error",
                        series_name=series_name,
                        sgs_code=sgs_code,
                        error=str(exc),
                    )
                    continue

                if not isinstance(data, list):
                    self.log.warning(
                        "unexpected_response_format",
                        series_name=series_name,
                        sgs_code=sgs_code,
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
                            series_name=series_name,
                            raw_date=raw_date,
                        )
                        continue

                    # Parse value (period-decimal in BCB SGS JSON)
                    parsed_value = parse_numeric_value(raw_value, ".")
                    if parsed_value is None:
                        continue

                    # CRITICAL: Convert percentage to decimal (13.50 -> 0.1350)
                    rate_decimal = parsed_value / 100.0

                    all_records.append(
                        {
                            "curve_id": "DI_PRE",
                            "curve_date": obs_date,
                            "tenor_days": tenor_days,
                            "tenor_label": tenor_label,
                            "rate": rate_decimal,
                            "curve_type": "swap",
                            "source": "BCB_SGS",
                        }
                    )

            # Rate limiting between series
            if i < total:
                await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

        return all_records

    # -----------------------------------------------------------------------
    # Fetch NTN-B real rates from Tesouro Direto
    # -----------------------------------------------------------------------
    async def fetch_ntnb_rates(
        self, as_of_date: date | None = None
    ) -> list[dict[str, Any]]:
        """Fetch NTN-B (IPCA+) real yields from Tesouro Direto JSON API.

        This is a best-effort data source. On any failure (403, 404, timeout),
        returns an empty list without raising an exception.

        Args:
            as_of_date: Reference date for tenor_days calculation.
                Defaults to today.

        Returns:
            List of CurveData-compatible dicts with curve_id='NTN_B_REAL',
            or an empty list on failure.
        """
        if as_of_date is None:
            as_of_date = date.today()

        records: list[dict[str, Any]] = []

        try:
            response = await self._request(
                "GET",
                self.TESOURO_DIRETO_URL,
                headers={"User-Agent": "Mozilla/5.0 (compatible; MacroTrading/1.0)"},
            )
            data = response.json()
        except Exception as exc:
            self.log.warning(
                "tesouro_direto_fetch_failed",
                error=str(exc),
            )
            return []

        # Navigate the response structure
        try:
            bond_list = data.get("response", {}).get("TrsrBdTradgList", [])
        except (AttributeError, TypeError):
            self.log.warning(
                "tesouro_direto_unexpected_format",
                data_type=type(data).__name__,
            )
            return []

        for entry in bond_list:
            try:
                bond = entry.get("TrsrBd", {})
                name = bond.get("nm", "")

                # Only process NTN-B (Tesouro IPCA+) bonds
                if "IPCA+" not in name and "IPCA" not in name:
                    continue

                # Extract real yield rate
                rate_pct = bond.get("anulInvstmtRate")
                if rate_pct is None:
                    continue

                rate_pct = float(rate_pct)

                # Extract maturity date
                maturity_str = bond.get("mtrtyDt", "")
                if not maturity_str:
                    continue

                maturity_date = datetime.fromisoformat(
                    maturity_str.replace("Z", "+00:00").split("T")[0]
                ).date()

                # Compute tenor_days from as_of_date
                tenor_days = (maturity_date - as_of_date).days
                if tenor_days <= 0:
                    continue  # Skip expired bonds

                # Build tenor label from approximate years
                years = tenor_days / 365.25
                if years < 1.5:
                    tenor_label = "1Y"
                elif years < 2.5:
                    tenor_label = "2Y"
                elif years < 4.0:
                    tenor_label = "3Y"
                elif years < 6.0:
                    tenor_label = "5Y"
                elif years < 8.0:
                    tenor_label = "7Y"
                elif years < 15.0:
                    tenor_label = "10Y"
                elif years < 25.0:
                    tenor_label = "20Y"
                else:
                    tenor_label = "30Y"

                # Convert percentage to decimal
                rate_decimal = rate_pct / 100.0

                records.append(
                    {
                        "curve_id": "NTN_B_REAL",
                        "curve_date": as_of_date,
                        "tenor_days": tenor_days,
                        "tenor_label": tenor_label,
                        "rate": rate_decimal,
                        "curve_type": "sovereign_real",
                        "source": "TESOURO_DIRETO",
                    }
                )
            except (ValueError, TypeError, KeyError) as exc:
                self.log.warning(
                    "ntnb_parse_error",
                    bond_name=entry.get("TrsrBd", {}).get("nm", "unknown"),
                    error=str(exc),
                )
                continue

        self.log.info(
            "ntnb_rates_fetched",
            count=len(records),
        )
        return records

    # -----------------------------------------------------------------------
    # Abstract method implementations
    # -----------------------------------------------------------------------
    async def fetch(
        self, start_date: date, end_date: date, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Fetch DI swap curve and NTN-B real rates.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            **kwargs: Additional arguments (unused).

        Returns:
            Combined list of DI_PRE and NTN_B_REAL CurveData-compatible dicts.
        """
        # DI swap curve from BCB SGS
        di_records = await self.fetch_di_curve(start_date, end_date)

        # NTN-B real rates from Tesouro Direto (snapshot for today)
        ntnb_records = await self.fetch_ntnb_rates(as_of_date=end_date)

        all_records = di_records + ntnb_records

        self.log.info(
            "fetch_complete",
            di_count=len(di_records),
            ntnb_count=len(ntnb_records),
            total=len(all_records),
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
        return await self._bulk_insert(CurveData, records, "uq_curves_natural_key")
