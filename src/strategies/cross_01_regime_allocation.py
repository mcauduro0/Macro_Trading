"""CROSS_01: Macro Regime Allocation strategy.

4-state regime classification with regime-dependent allocation trades:

Regime classification rules (rule-based; Phase 16 adds HMM):
    - **Goldilocks**: growth_z > 0 AND inflation_z < 0.5
    - **Reflation**: growth_z > 0 AND inflation_z > 0.5
    - **Stagflation**: growth_z < 0 AND inflation_z > 0.5
    - **Deflation**: growth_z < 0 AND inflation_z < -0.5

Regime-dependent allocation map (explicit trades):
    - **Goldilocks**: LONG equities, LONG DI (receive), SHORT USDBRL, LONG NTN-B
    - **Reflation**: LONG equities, SHORT DI (pay), LONG USDBRL, SHORT NTN-B
    - **Stagflation**: SHORT equities, SHORT DI (pay), LONG USDBRL
    - **Deflation**: NEUTRAL equities, LONG DI (receive), SHORT USDBRL, LONG NTN-B

Per locked decision: regime modulates sizing, never hard-suppresses.
Strategies not aligned with regime get 0.5x sizing multiplier in metadata.

Entry threshold: |regime_z| >= 0.5.
Stop-loss: 3% per position.
Take-profit: 5% per position.
Holding period: 21 days.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from enum import Enum
from typing import Optional

import structlog

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection, SignalStrength
from src.strategies.base import BaseStrategy, StrategyConfig, StrategySignal
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
CROSS_01_CONFIG = StrategyConfig(
    strategy_id="CROSS_01",
    strategy_name="Macro Regime Allocation",
    asset_class=AssetClass.CROSS_ASSET,
    instruments=["DI_PRE", "USDBRL", "IBOV_FUT", "NTN_B_REAL"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.03,
    take_profit_pct=0.05,
)

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
_ENTRY_THRESHOLD = 0.5
_HOLDING_PERIOD = 21
_ZSCORE_WINDOW = 252
_REGIME_MISALIGN_MULTIPLIER = 0.5


# ---------------------------------------------------------------------------
# Regime enum
# ---------------------------------------------------------------------------
class MacroRegime(str, Enum):
    """4-state macro regime classification."""
    GOLDILOCKS = "Goldilocks"
    REFLATION = "Reflation"
    STAGFLATION = "Stagflation"
    DEFLATION = "Deflation"


# ---------------------------------------------------------------------------
# Regime -> allocation map
# Each entry: (instrument, direction)
# ---------------------------------------------------------------------------
REGIME_ALLOCATION: dict[MacroRegime, list[tuple[str, SignalDirection]]] = {
    MacroRegime.GOLDILOCKS: [
        ("IBOV_FUT", SignalDirection.LONG),
        ("DI_PRE", SignalDirection.LONG),      # receive rates
        ("USDBRL", SignalDirection.SHORT),
        ("NTN_B_REAL", SignalDirection.LONG),
    ],
    MacroRegime.REFLATION: [
        ("IBOV_FUT", SignalDirection.LONG),
        ("DI_PRE", SignalDirection.SHORT),     # pay rates
        ("USDBRL", SignalDirection.LONG),
        ("NTN_B_REAL", SignalDirection.SHORT),
    ],
    MacroRegime.STAGFLATION: [
        ("IBOV_FUT", SignalDirection.SHORT),
        ("DI_PRE", SignalDirection.SHORT),     # pay rates
        ("USDBRL", SignalDirection.LONG),
    ],
    MacroRegime.DEFLATION: [
        ("IBOV_FUT", SignalDirection.NEUTRAL),
        ("DI_PRE", SignalDirection.LONG),      # receive rates
        ("USDBRL", SignalDirection.SHORT),
        ("NTN_B_REAL", SignalDirection.LONG),
    ],
}


@StrategyRegistry.register(
    "CROSS_01",
    asset_class=AssetClass.CROSS_ASSET,
    instruments=["DI_PRE", "USDBRL", "IBOV_FUT", "NTN_B_REAL"],
)
class Cross01RegimeAllocationStrategy(BaseStrategy):
    """Macro Regime Allocation strategy.

    Classifies the macro environment into one of 4 regimes and produces
    regime-dependent allocation trades across asset classes.

    Args:
        data_loader: PointInTimeDataLoader for fetching macro / market data.
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or CROSS_01_CONFIG)
        self.data_loader = data_loader
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce StrategySignals based on macro regime classification.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List of StrategySignals (one per instrument in the regime
            allocation map), or empty list when data is missing.
        """
        # --- Regime classification inputs ---
        growth_z = self._compute_growth_z(as_of_date)
        if growth_z is None:
            return []

        inflation_z = self._compute_inflation_z(as_of_date)
        if inflation_z is None:
            return []

        # --- Classify regime ---
        regime = self._classify_regime(growth_z, inflation_z)

        # Regime conviction: max of absolute z-scores
        regime_z = max(abs(growth_z), abs(inflation_z))

        # Regime confidence: how far from boundaries
        regime_confidence = min(1.0, regime_z / 2.0)

        self.log.info(
            "cross01_regime",
            regime=regime.value,
            growth_z=round(growth_z, 4),
            inflation_z=round(inflation_z, 4),
            regime_z=round(regime_z, 4),
        )

        # Entry threshold
        if regime_z < _ENTRY_THRESHOLD:
            return []

        # --- Generate signals from allocation map ---
        allocations = REGIME_ALLOCATION[regime]
        signals: list[StrategySignal] = []

        for instrument, direction in allocations:
            if direction == SignalDirection.NEUTRAL:
                continue

            # Sizing modulated by regime conviction
            suggested_size = self.size_from_conviction(regime_z)

            strength = self.classify_strength(regime_z)
            confidence = min(1.0, regime_z / 3.0)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                timestamp=datetime.utcnow(),
                direction=direction,
                strength=strength,
                confidence=confidence,
                z_score=regime_z if direction == SignalDirection.LONG else -regime_z,
                raw_value=regime_z,
                suggested_size=suggested_size,
                asset_class=AssetClass.CROSS_ASSET,
                instruments=[instrument],
                entry_level=None,
                stop_loss=None,
                take_profit=None,
                holding_period_days=_HOLDING_PERIOD,
                metadata={
                    "regime": regime.value,
                    "growth_z": growth_z,
                    "inflation_z": inflation_z,
                    "regime_confidence": regime_confidence,
                    "regime_z": regime_z,
                    "instrument": instrument,
                    "regime_misalign_multiplier": _REGIME_MISALIGN_MULTIPLIER,
                },
            )
            signals.append(signal)

        return signals

    # ------------------------------------------------------------------
    # Regime classification
    # ------------------------------------------------------------------
    def _classify_regime(
        self, growth_z: float, inflation_z: float,
    ) -> MacroRegime:
        """Classify macro regime from growth and inflation z-scores.

        Rules:
            - Goldilocks: growth_z > 0 AND inflation_z < 0.5
            - Reflation: growth_z > 0 AND inflation_z > 0.5
            - Stagflation: growth_z < 0 AND inflation_z > 0.5
            - Deflation: growth_z < 0 AND inflation_z < -0.5
            - Default: nearest regime if no clear classification.
        """
        if growth_z > 0 and inflation_z < 0.5:
            return MacroRegime.GOLDILOCKS
        if growth_z > 0 and inflation_z > 0.5:
            return MacroRegime.REFLATION
        if growth_z < 0 and inflation_z > 0.5:
            return MacroRegime.STAGFLATION
        if growth_z < 0 and inflation_z < -0.5:
            return MacroRegime.DEFLATION

        # Default: nearest regime based on distances
        # Between -0.5 and 0.5 for inflation with negative growth
        # => closer to Stagflation or Deflation depending on inflation
        if growth_z < 0:
            if inflation_z >= 0:
                return MacroRegime.STAGFLATION
            else:
                return MacroRegime.DEFLATION
        else:
            if inflation_z >= 0:
                return MacroRegime.REFLATION
            else:
                return MacroRegime.GOLDILOCKS

    # ------------------------------------------------------------------
    # Growth z-score
    # ------------------------------------------------------------------
    def _compute_growth_z(self, as_of_date: date) -> Optional[float]:
        """Compute GDP growth z-score from IBC-Br or GDP YOY."""
        gdp = self.data_loader.get_latest_macro_value(
            "BR_GDP_GROWTH_YOY", as_of_date,
        )
        if gdp is None:
            gdp = self.data_loader.get_latest_macro_value(
                "BR_IBC_BR_YOY", as_of_date,
            )
        if gdp is None:
            return None

        # Load growth history for z-score
        growth_df = self.data_loader.get_macro_series(
            "BR_GDP_GROWTH_YOY", as_of_date, lookback_days=1260,
        )
        if growth_df.empty:
            growth_df = self.data_loader.get_macro_series(
                "BR_IBC_BR_YOY", as_of_date, lookback_days=1260,
            )
        if growth_df.empty or len(growth_df) < 10:
            # Fallback: simple normalization around 2% neutral
            return (gdp - 2.0) / 1.5

        values = growth_df["value"].tolist()
        return self.compute_z_score(gdp, values, window=_ZSCORE_WINDOW)

    # ------------------------------------------------------------------
    # Inflation z-score
    # ------------------------------------------------------------------
    def _compute_inflation_z(self, as_of_date: date) -> Optional[float]:
        """Compute inflation z-score from trailing 12M IPCA."""
        ipca = self.data_loader.get_latest_macro_value(
            "BR_IPCA_12M", as_of_date,
        )
        if ipca is None:
            return None

        # Load inflation history for z-score
        infl_df = self.data_loader.get_macro_series(
            "BR_IPCA_12M", as_of_date, lookback_days=1260,
        )
        if infl_df.empty or len(infl_df) < 10:
            # Fallback: simple normalization around 4.5% target
            return (ipca - 4.5) / 2.0

        values = infl_df["value"].tolist()
        return self.compute_z_score(ipca, values, window=_ZSCORE_WINDOW)
