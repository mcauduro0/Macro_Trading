"""ANBIMA data connector for Brazilian fixed-income market data.

ANBIMA (Associação Brasileira das Entidades dos Mercados Financeiro e de
Capitais) provides high-quality fixed-income market data for Brazil:

- **ETTJ (Estrutura a Termo de Taxas de Juros)**: Full yield-curve term
  structure with Nelson-Siegel-Svensson parameters for DI PRE, IPCA, and
  other curves.  More granular than the BCB swap series or Tesouro Direto.
- **NTN-B indicative rates**: Precise real-rate marks for every NTN-B
  maturity, superior to Tesouro Direto prices.
- **Debenture pricing**: Corporate bond indicative marks.
- **IMA indices**: Fixed-income index family (IMA-B, IMA-S, IRF-M, etc.).

Access requires registration at https://data.anbima.com.br/.
The REST API uses OAuth2 client credentials (client_id + client_secret)
to obtain a Bearer token, which is valid for 1 hour.

Target endpoints (ANBIMA Data API):
    GET /feed/precos-indices/v1/titulos-publicos/mercado-secundario-TPF
    GET /feed/precos-indices/v1/indices/resultados?indice=IMA-B
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.connectors.base import BaseConnector, ConnectorError
from src.core.config import settings
from src.core.database import async_session_factory
from src.core.models.curves import CurveData
from src.core.models.market_data import MarketData

logger = structlog.get_logger()

_SP_TZ = ZoneInfo("America/Sao_Paulo")


class AnbimaConnector(BaseConnector):
    """Connector for ANBIMA Data API — Brazilian fixed-income market data.

    Fetches ETTJ yield curves (DI PRE, IPCA), NTN-B indicative rates,
    and IMA index levels.  Requires ``ANBIMA_CLIENT_ID`` and
    ``ANBIMA_CLIENT_SECRET`` environment variables.

    Usage::

        async with AnbimaConnector() as conn:
            count = await conn.run(date(2024, 1, 1), date(2025, 1, 1))
    """

    SOURCE_NAME: str = "ANBIMA"
    BASE_URL: str = "https://api.anbima.com.br"
    AUTH_URL: str = "https://api.anbima.com.br/oauth/access-token"
    RATE_LIMIT_PER_SECOND: float = 5.0
    MAX_RETRIES: int = 3
    TIMEOUT_SECONDS: float = 30.0

    # Token cache
    _access_token: str | None = None
    _token_expires_at: datetime | None = None

    # NTN-B reference maturities (years → approximate tenor_days)
    _NTNB_TENOR_MAP: dict[int, int] = {
        2: 504,
        3: 756,
        5: 1260,
        7: 1764,
        10: 2520,
        15: 3780,
        20: 5040,
        30: 7560,
    }

    # IMA indices to collect
    IMA_INDICES: list[str] = ["IMA-B", "IMA-B 5", "IMA-B 5+", "IMA-S", "IRF-M"]

    async def _ensure_auth_token(self) -> str:
        """Obtain or refresh OAuth2 access token.

        Uses client_credentials grant type.

        Returns:
            Valid Bearer token string.

        Raises:
            ConnectorError: If credentials are missing or auth fails.
        """
        # Return cached token if still valid
        if (self._access_token is not None
                and self._token_expires_at is not None
                and datetime.utcnow() < self._token_expires_at):
            return self._access_token

        client_id = settings.anbima_client_id
        client_secret = settings.anbima_client_secret

        if not client_id or not client_secret:
            raise ConnectorError(
                "ANBIMA credentials not configured. Set ANBIMA_CLIENT_ID and "
                "ANBIMA_CLIENT_SECRET in .env. Register at https://data.anbima.com.br/"
            )

        response = await self._request(
            "POST",
            "",
            base_url=self.AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_data = response.json()

        self._access_token = token_data.get("access_token")
        expires_in = int(token_data.get("expires_in", 3600))
        # Refresh 5 minutes early to avoid edge cases
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 300)

        if not self._access_token:
            raise ConnectorError("ANBIMA OAuth2 returned no access_token")

        logger.info("anbima_token_obtained", expires_in=expires_in)
        return self._access_token

    async def _auth_request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        """Make an authenticated API request to ANBIMA.

        Args:
            method: HTTP method.
            path: API path (appended to BASE_URL).
            params: Query parameters.

        Returns:
            Parsed JSON response.
        """
        token = await self._ensure_auth_token()
        response = await self._request(
            method,
            path,
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
        return response.json()

    async def fetch(
        self,
        start_date: date,
        end_date: date,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Fetch ANBIMA curve and index data for the date range.

        Collects:
        1. NTN-B indicative rates (real yield curve)
        2. IMA index levels (IMA-B, IMA-S, IRF-M)

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            **kwargs: Unused.

        Returns:
            List of record dicts with _record_type ("curve" or "market_data").
        """
        all_records: list[dict[str, Any]] = []

        # Iterate over business days in the range
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Mon-Fri
                # Fetch NTN-B indicative rates
                try:
                    ntnb_records = await self._fetch_ntnb_rates(current)
                    all_records.extend(ntnb_records)
                except Exception as exc:
                    logger.debug("ntnb_fetch_failed", date=str(current), error=str(exc))

                # Fetch IMA indices
                try:
                    ima_records = await self._fetch_ima_indices(current)
                    all_records.extend(ima_records)
                except Exception as exc:
                    logger.debug("ima_fetch_failed", date=str(current), error=str(exc))

                await asyncio.sleep(1.0 / self.RATE_LIMIT_PER_SECOND)

            current += timedelta(days=1)

        logger.info(
            "anbima_fetch_complete",
            total_records=len(all_records),
            start=str(start_date),
            end=str(end_date),
        )
        return all_records

    async def _fetch_ntnb_rates(self, ref_date: date) -> list[dict[str, Any]]:
        """Fetch NTN-B indicative rates for a single date.

        Returns curve records with _record_type="curve".
        """
        date_str = ref_date.strftime("%Y-%m-%d")
        path = "/feed/precos-indices/v1/titulos-publicos/mercado-secundario-TPF"
        data = await self._auth_request("GET", path, params={"data": date_str})

        records: list[dict[str, Any]] = []
        items = data if isinstance(data, list) else data.get("content", [])

        for item in items:
            tipo = item.get("tipo_titulo", "")
            if "NTN-B" not in tipo:
                continue

            # Parse maturity date
            vencimento = item.get("data_vencimento", "")
            try:
                mat_date = datetime.strptime(vencimento, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue

            # Calculate tenor in days
            tenor_days = (mat_date - ref_date).days
            if tenor_days <= 0:
                continue

            # Get the indicative rate (real yield)
            taxa = item.get("taxa_indicativa")
            if taxa is None:
                continue

            try:
                rate = float(taxa) / 100.0  # Convert from % to decimal
            except (ValueError, TypeError):
                continue

            records.append({
                "_record_type": "curve",
                "curve_id": "NTN_B_REAL_ANBIMA",
                "curve_date": ref_date,
                "tenor_days": tenor_days,
                "rate": rate,
                "maturity_date": mat_date,
            })

        return records

    async def _fetch_ima_indices(self, ref_date: date) -> list[dict[str, Any]]:
        """Fetch IMA index levels for a single date.

        Returns market_data records with _record_type="market_data".
        """
        records: list[dict[str, Any]] = []
        date_str = ref_date.strftime("%Y-%m-%d")

        for index_name in self.IMA_INDICES:
            try:
                path = "/feed/precos-indices/v1/indices/resultados"
                data = await self._auth_request(
                    "GET",
                    path,
                    params={"indice": index_name, "data": date_str},
                )

                items = data if isinstance(data, list) else data.get("content", [])
                for item in items:
                    valor = item.get("numero_indice") or item.get("valor")
                    if valor is None:
                        continue

                    # Normalize index name for ticker (e.g. "IMA-B 5" → "ANBIMA_IMA_B_5")
                    ticker = "ANBIMA_" + index_name.replace("-", "_").replace(" ", "_").upper()

                    records.append({
                        "_record_type": "market_data",
                        "ticker": ticker,
                        "timestamp": datetime.combine(ref_date, datetime.min.time()).replace(tzinfo=_SP_TZ),
                        "close": float(valor),
                        "volume": 0.0,
                    })

            except Exception as exc:
                logger.debug(
                    "ima_index_failed",
                    index=index_name,
                    date=date_str,
                    error=str(exc),
                )

        return records

    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist ANBIMA records to curves and market_data tables.

        Curve records go to ``curves`` hypertable.
        IMA index records go to ``market_data`` hypertable.

        Args:
            records: List of record dicts from fetch().

        Returns:
            Number of rows actually inserted (sum of both tables).
        """
        if not records:
            return 0

        curve_records = [r for r in records if r.get("_record_type") == "curve"]
        market_records = [r for r in records if r.get("_record_type") == "market_data"]

        total_inserted = 0

        # Store curve records
        if curve_records:
            insertable = []
            for rec in curve_records:
                rec.pop("_record_type", None)
                rec.pop("maturity_date", None)
                insertable.append(rec)

            total_inserted += await self._bulk_insert(
                CurveData, insertable, "uq_curve_data_natural_key"
            )

        # Store market data records
        if market_records:
            from src.core.models.instruments import Instrument

            await self._ensure_data_source()

            async with async_session_factory() as session:
                for rec in market_records:
                    rec.pop("_record_type", None)
                    ticker = rec.pop("ticker", "")

                    # Ensure instrument exists
                    async with session.begin():
                        result = await session.execute(
                            select(Instrument.id).where(Instrument.ticker == ticker)
                        )
                        inst_id = result.scalar()

                        if inst_id is None:
                            stmt = pg_insert(Instrument).values(
                                ticker=ticker,
                                name=f"ANBIMA {ticker}",
                                instrument_type="INDEX",
                                exchange="ANBIMA",
                                currency="BRL",
                                is_active=True,
                            ).on_conflict_do_nothing()
                            await session.execute(stmt)
                            result = await session.execute(
                                select(Instrument.id).where(Instrument.ticker == ticker)
                            )
                            inst_id = result.scalar()

                    rec["instrument_id"] = inst_id

            total_inserted += await self._bulk_insert(
                MarketData, [r for r in market_records if "instrument_id" in r],
                "uq_market_data_instrument_timestamp",
            )

        logger.info(
            "anbima_store_complete",
            curves=len(curve_records),
            market_data=len(market_records),
            inserted=total_inserted,
        )
        return total_inserted
