"""ANBIMA data connector -- placeholder for future implementation.

ANBIMA (Associação Brasileira das Entidades dos Mercados Financeiro e de
Capitais) provides high-quality fixed-income market data for Brazil:

- **ETTJ (Estrutura a Termo de Taxas de Juros)**: Full yield-curve term
  structure with Nelson-Siegel-Svensson parameters for DI PRE, IPCA, and
  other curves.  More granular than the BCB swap series or Tesouro Direto.
- **NTN-B indicative rates**: Precise real-rate marks for every NTN-B
  maturity, superior to Tesouro Direto prices.
- **Debenture pricing**: Corporate bond indicative marks.
- **IMA indices**: Fixed-income index family (IMA-B, IMA-S, IRF-M, etc.).

Access requires free registration at https://data.anbima.com.br/ (the old
``debentures.com.br`` portal now redirects there).  Once registered the REST
API returns JSON and requires an ``Authorization: Bearer <token>`` header.

For the MVP the BCB DI swap series (SGS #7805-#7816) combined with Tesouro
Direto pricing provide adequate curve data.  This placeholder records the
target API surface so integration can proceed once API access is obtained.

Target endpoints (ANBIMA Data API):
    GET /feed/precos-indices/v1/titulos-publicos/mercado-secundario-TPF
    GET /feed/precos-indices/v1/debentures/mercado-secundario
    GET /feed/precos-indices/v1/indices/resultados?indice=IMA-B
"""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog

from .base import BaseConnector, ConnectorError


log = structlog.get_logger()


class AnbimaConnector(BaseConnector):
    """Placeholder connector for ANBIMA market data.

    This connector is **not yet functional**.  All methods raise
    ``NotImplementedError`` until API credentials are configured.

    Once ANBIMA API access is provisioned, implement:
    1. ``fetch()`` to pull ETTJ curves, NTN-B indicative rates, IMA indices.
    2. ``store()`` to persist results in the ``curves`` hypertable
       (curve_id ``'DI_PRE_ANBIMA'``, ``'NTN_B_REAL_ANBIMA'``, etc.)
       and ``market_data`` for IMA index levels.
    """

    SOURCE_NAME: str = "ANBIMA"
    BASE_URL: str = "https://api-sandbox.anbima.com.br"
    RATE_LIMIT_PER_SECOND: float = 5.0
    MAX_RETRIES: int = 3
    TIMEOUT_SECONDS: float = 30.0

    # Target series that will be produced once implemented:
    PLANNED_SERIES = {
        # Yield-curve term structures (ETTJ)
        "DI_PRE_ANBIMA": "ETTJ DI PRE (Nelson-Siegel-Svensson parameters)",
        "IPCA_ANBIMA": "ETTJ IPCA real-rate curve",
        "CUPOM_ANBIMA": "ETTJ cupom cambial curve",
        # NTN-B indicative rates
        "NTN_B_INDICATIVE": "NTN-B indicative rates for all maturities",
        # Fixed-income indices
        "IMA_B": "IMA-B index (NTN-B basket)",
        "IMA_B_5": "IMA-B 5 index (NTN-B >= 5 years)",
        "IMA_S": "IMA-S index (LFT / Selic-indexed)",
        "IRF_M": "IRF-M index (LTN + NTN-F / pre-fixed)",
    }

    async def fetch(
        self, start_date: date, end_date: date, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Fetch ANBIMA data for the given date range.

        .. note:: Not yet implemented.  Requires ANBIMA API credentials.

        Raises:
            NotImplementedError: Always, until API access is provisioned.
        """
        raise NotImplementedError(
            "AnbimaConnector.fetch() is not yet implemented. "
            "Register at https://data.anbima.com.br/ to obtain API credentials, "
            "then set ANBIMA_CLIENT_ID and ANBIMA_CLIENT_SECRET in .env."
        )

    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist ANBIMA records to the database.

        .. note:: Not yet implemented.

        Raises:
            NotImplementedError: Always, until fetch() is implemented.
        """
        raise NotImplementedError(
            "AnbimaConnector.store() is not yet implemented."
        )
