"""Transaction cost model with per-instrument cost tables (BTST-04).

Provides realistic transaction cost modeling for backtesting with
instrument-specific spreads, commissions, and exchange fees.

Supports 12 instruments traded by the macro fund:
- Brazilian rates: DI1, DDI
- Brazilian FX: DOL, NDF
- Brazilian bonds: NTN_B, LTN
- US rates: UST, ZN, ZF
- US equity: ES
- Credit: CDS_BR
- Brazilian equity: IBOV_FUT

Ticker prefix matching maps strategy instrument names (e.g., "DI_PRE_365")
to cost table keys (e.g., "DI1").
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# Mapping from common ticker prefixes used by strategies to cost table keys.
# Checked in order; first prefix match wins.
TICKER_MAPPING: dict[str, str] = {
    "DI_PRE": "DI1",
    "DI1_": "DI1",
    "DI1": "DI1",
    "DDI_": "DDI",
    "DDI": "DDI",
    "DOL_": "DOL",
    "DOL": "DOL",
    "USDBRL": "NDF",
    "NDF": "NDF",
    "NTN_B": "NTN_B",
    "NTNB": "NTN_B",
    "LTN_": "LTN",
    "LTN": "LTN",
    "UST_": "UST",
    "UST": "UST",
    "ZN_": "ZN",
    "ZN": "ZN",
    "ZF_": "ZF",
    "ZF": "ZF",
    "ES_": "ES",
    "ES": "ES",
    "CDS_BR": "CDS_BR",
    "CDS": "CDS_BR",
    "IBOV": "IBOV_FUT",
}

DEFAULT_COST_BPS = 2.0


class TransactionCostModel:
    """Per-instrument transaction cost model.

    Each instrument has three cost components (all in basis points):
    - spread: Bid-ask spread cost
    - commission: Broker commission
    - exchange_fee: Exchange/clearing fee

    The total one-way cost is spread + commission + exchange_fee.
    """

    COST_TABLE: dict[str, dict[str, float]] = {
        "DI1": {"spread": 0.5, "commission": 0.3, "exchange_fee": 0.2},
        "DDI": {"spread": 1.0, "commission": 0.3, "exchange_fee": 0.2},
        "DOL": {"spread": 0.3, "commission": 0.3, "exchange_fee": 0.2},
        "NDF": {"spread": 2.0, "commission": 0.0, "exchange_fee": 0.0},
        "NTN_B": {"spread": 3.0, "commission": 0.0, "exchange_fee": 0.0},
        "LTN": {"spread": 1.5, "commission": 0.0, "exchange_fee": 0.0},
        "UST": {"spread": 0.5, "commission": 0.1, "exchange_fee": 0.0},
        "ZN": {"spread": 0.3, "commission": 0.5, "exchange_fee": 0.3},
        "ZF": {"spread": 0.3, "commission": 0.5, "exchange_fee": 0.3},
        "ES": {"spread": 0.2, "commission": 0.5, "exchange_fee": 0.3},
        "CDS_BR": {"spread": 5.0, "commission": 0.0, "exchange_fee": 0.0},
        "IBOV_FUT": {"spread": 1.0, "commission": 0.3, "exchange_fee": 0.2},
    }

    def __init__(self, default_bps: float = DEFAULT_COST_BPS) -> None:
        self.default_bps = default_bps

    def _resolve_instrument(self, instrument: str) -> str | None:
        """Resolve an instrument name to a COST_TABLE key.

        Direct match first, then prefix matching via TICKER_MAPPING.

        Args:
            instrument: Instrument ticker as used by strategies.

        Returns:
            COST_TABLE key or None if no match found.
        """
        # Direct match
        if instrument in self.COST_TABLE:
            return instrument

        # Prefix matching
        upper = instrument.upper()
        for prefix, cost_key in TICKER_MAPPING.items():
            if upper.startswith(prefix):
                return cost_key

        return None

    def get_cost_bps(self, instrument: str) -> float:
        """Get total one-way cost in basis points for an instrument.

        Sum of spread + commission + exchange_fee. Falls back to prefix
        matching, then to DEFAULT_COST_BPS if instrument is unknown.

        Args:
            instrument: Instrument ticker.

        Returns:
            Total one-way cost in basis points.
        """
        resolved = self._resolve_instrument(instrument)
        if resolved is not None:
            costs = self.COST_TABLE[resolved]
            return costs["spread"] + costs["commission"] + costs["exchange_fee"]

        logger.debug(
            "instrument_not_in_cost_table instrument=%s using_default_bps=%.1f",
            instrument,
            self.default_bps,
        )
        return self.default_bps

    def get_cost(
        self, instrument: str, notional: float, is_entry: bool = True
    ) -> float:
        """Compute dollar cost for a given notional trade.

        Args:
            instrument: Instrument ticker.
            notional: Trade notional value (sign is ignored).
            is_entry: True for entry, False for exit (currently both use
                the same cost; parameter reserved for future asymmetric costs).

        Returns:
            Cost in currency units (USD/BRL).
        """
        bps = self.get_cost_bps(instrument)
        return abs(notional) * bps / 10_000

    def get_round_trip_bps(self, instrument: str) -> float:
        """Get round-trip (entry + exit) cost in basis points.

        Args:
            instrument: Instrument ticker.

        Returns:
            Round-trip cost = 2 * one-way cost.
        """
        return 2.0 * self.get_cost_bps(instrument)
