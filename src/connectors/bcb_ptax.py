"""BCB PTAX connector -- official Brazilian FX fixing rates.

Fetches the official PTAX (USD/BRL) exchange rate from the BCB OData API.
The PTAX rate is the daily FX fixing used as reference for contracts and
official statistics in Brazil.

Key design decisions:
- Date format: MM-DD-YYYY (American format required by the OData API)
- Filters for tipoBoletim='Fechamento' (closing bulletin = official PTAX)
- Maps cotacaoCompra (buy) to open, cotacaoVenda (sell) to close
- Uses dataHoraCotacao with America/Sao_Paulo timezone for release_time
- Date ranges split into 1-year chunks for API safety
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.connectors.base import BaseConnector, ConnectorError, DataParsingError
from src.core.database import async_session_factory
from src.core.models.instruments import Instrument
from src.core.models.market_data import MarketData

logger = structlog.get_logger()

SP_TZ = ZoneInfo("America/Sao_Paulo")


class BcbPtaxConnector(BaseConnector):
    """Connector for BCB PTAX official FX fixing rates.

    Fetches the daily USD/BRL fixing rate from the BCB OData API.
    Only the closing bulletin (Fechamento) is kept as the official PTAX.

    Usage::

        async with BcbPtaxConnector() as conn:
            count = await conn.run(date(2024, 1, 1), date(2024, 12, 31))
    """

    SOURCE_NAME: str = "BCB_PTAX"
    BASE_URL: str = "https://olinda.bcb.gov.br"
    RATE_LIMIT_PER_SECOND: float = 2.0
    TIMEOUT_SECONDS: float = 30.0
    TICKER_NAME: str = "USDBRL_PTAX"

    async def fetch_period(
        self, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Fetch PTAX rates for a single period from the OData API.

        CRITICAL: Date format is MM-DD-YYYY (American format). This is the
        most common PTAX API pitfall -- using DD/MM/YYYY or ISO format will
        return incorrect or empty results.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.

        Returns:
            List of record dicts for closing bulletins only.
        """
        url = (
            "/olinda/servico/PTAX/versao/v1/odata/"
            "CotacaoDolarPeriodo(dataInicial=@di,dataFinalCotacao=@df)"
        )
        params = {
            "@di": f"'{start_date.strftime('%m-%d-%Y')}'",
            "@df": f"'{end_date.strftime('%m-%d-%Y')}'",
            "$format": "json",
        }

        response = await self._request("GET", url, params=params)
        data = response.json()
        items = data.get("value", [])

        records: list[dict[str, Any]] = []
        for item in items:
            tipo_boletim = item.get("tipoBoletim", "")

            if tipo_boletim != "Fechamento":
                self.log.debug(
                    "non_closing_bulletin_skipped",
                    tipo_boletim=tipo_boletim,
                    data_hora=item.get("dataHoraCotacao"),
                )
                continue

            # Parse release time from dataHoraCotacao
            # Format: "YYYY-MM-DD HH:MM:SS.fff"
            data_hora_str = item["dataHoraCotacao"]
            try:
                release_time = datetime.strptime(
                    data_hora_str, "%Y-%m-%d %H:%M:%S.%f"
                ).replace(tzinfo=SP_TZ)
            except ValueError:
                # Try without milliseconds
                release_time = datetime.strptime(
                    data_hora_str, "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=SP_TZ)

            cotacao_compra = item["cotacaoCompra"]
            cotacao_venda = item["cotacaoVenda"]

            records.append(
                {
                    "_ticker": self.TICKER_NAME,
                    "timestamp": release_time,
                    "frequency": "daily",
                    "open": cotacao_compra,
                    "high": None,
                    "low": None,
                    "close": cotacao_venda,
                    "volume": None,
                    "adjusted_close": cotacao_venda,
                    "source": self.SOURCE_NAME,
                }
            )

        self.log.info(
            "period_fetched",
            start=str(start_date),
            end=str(end_date),
            total_bulletins=len(items),
            closing_bulletins=len(records),
        )
        return records

    async def fetch(
        self,
        start_date: date,
        end_date: date,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Fetch PTAX rates, splitting long ranges into 1-year chunks.

        The PTAX API handles long ranges but chunking is safer and avoids
        potential timeout or response size issues.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            **kwargs: Additional arguments (unused).

        Returns:
            List of record dicts from all chunks.
        """
        all_records: list[dict[str, Any]] = []

        chunk_start = start_date
        while chunk_start <= end_date:
            # End of this chunk: min(start + 1 year, end_date)
            chunk_end = min(
                date(chunk_start.year + 1, chunk_start.month, chunk_start.day)
                - timedelta(days=1),
                end_date,
            )

            records = await self.fetch_period(chunk_start, chunk_end)
            all_records.extend(records)

            # Move to next chunk
            chunk_start = chunk_end + timedelta(days=1)

        self.log.info(
            "fetch_complete",
            total_records=len(all_records),
            start=str(start_date),
            end=str(end_date),
        )
        return all_records

    async def _ensure_instrument(self) -> int:
        """Ensure the USDBRL_PTAX instrument exists in the database.

        Uses INSERT ... ON CONFLICT DO NOTHING on the ticker unique constraint,
        then returns the instrument id via SELECT.

        Returns:
            The instrument.id integer.

        Raises:
            ConnectorError: If the instrument cannot be found after upsert.
        """
        async with async_session_factory() as session:
            async with session.begin():
                stmt = pg_insert(Instrument).values(
                    ticker=self.TICKER_NAME,
                    name="PTAX Official Rate (USD/BRL)",
                    asset_class="FX",
                    country="BR",
                    currency="BRL",
                ).on_conflict_do_nothing(index_elements=["ticker"])
                await session.execute(stmt)

            result = await session.execute(
                select(Instrument.id).where(
                    Instrument.ticker == self.TICKER_NAME
                )
            )
            instrument_id = result.scalar_one_or_none()

        if instrument_id is None:
            raise ConnectorError(
                f"Failed to find instrument for ticker {self.TICKER_NAME}"
            )
        return instrument_id

    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist PTAX records to the market_data table.

        Ensures the USDBRL_PTAX instrument exists, replaces _ticker with
        instrument_id, then performs bulk insert with ON CONFLICT DO NOTHING.

        Args:
            records: List of record dicts from fetch().

        Returns:
            Number of records inserted (excluding conflicts).
        """
        if not records:
            return 0

        instrument_id = await self._ensure_instrument()

        insert_records: list[dict[str, Any]] = []
        for record in records:
            rec = {k: v for k, v in record.items() if k != "_ticker"}
            rec["instrument_id"] = instrument_id
            insert_records.append(rec)

        inserted = await self._bulk_insert(
            MarketData, insert_records, "uq_market_data_natural_key"
        )
        self.log.info(
            "store_complete",
            total=len(insert_records),
            inserted=inserted,
        )
        return inserted
