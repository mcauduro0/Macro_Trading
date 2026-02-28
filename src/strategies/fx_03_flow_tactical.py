"""FX_03: Flow-Based Tactical FX strategy for USDBRL.

Composites three flow components into a directional USDBRL signal with
contrarian logic at extreme positioning:

- **BCB FX flow (40%)**: 21-day rolling sum of net FX flows, z-scored
  vs 252-day history.
- **CFTC BRL positioning (35%)**: Leveraged net BRL futures positions,
  z-scored vs 2-year (104-week) history.
- **B3 foreign equity flow (25%)**: Financial FX flow proxy, 21-day
  rolling sum z-scored vs history.

Contrarian logic: When |composite_z| > 2.0, the signal direction is
inverted (extreme positioning likely leads to reversal).

Direction (non-contrarian): positive composite => SHORT USDBRL (inflows
= BRL strength).  Contrarian: flipped.
Entry threshold: |composite_z| >= 1.0.
Stop-loss: fixed 3% from entry.
Take-profit: fixed 5% from entry.
Holding period: 14 days.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import structlog

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection
from src.strategies.base import (
    BaseStrategy,
    StrategyConfig,
    StrategySignal,
)
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
FX_03_CONFIG = StrategyConfig(
    strategy_id="FX_03",
    strategy_name="USDBRL Flow-Based Tactical",
    asset_class=AssetClass.FX,
    instruments=["USDBRL"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.03,
    take_profit_pct=0.05,
)

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
_BCB_WEIGHT = 0.40
_CFTC_WEIGHT = 0.35
_B3_WEIGHT = 0.25
_BCB_LOOKBACK = 365
_CFTC_LOOKBACK = 730  # ~2 years
_B3_LOOKBACK = 365
_ROLLING_SUM_WINDOW = 21
_BCB_ZSCORE_WINDOW = 252
_CFTC_ZSCORE_WINDOW = 104 * 5  # 104 weeks in business days
_ENTRY_THRESHOLD = 1.0
_CONTRARIAN_THRESHOLD = 2.0
_STOP_LOSS_PCT = 0.03
_TAKE_PROFIT_PCT = 0.05
_HOLDING_PERIOD = 14


@StrategyRegistry.register("FX_03", asset_class=AssetClass.FX, instruments=["USDBRL"])
class Fx03FlowTacticalStrategy(BaseStrategy):
    """USDBRL Flow-Based Tactical FX strategy.

    Composites BCB FX flow (40%), CFTC BRL positioning (35%), and B3
    foreign equity flow (25%) with contrarian logic at extreme |z| > 2.

    Args:
        data_loader: PointInTimeDataLoader for fetching flow data.
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or FX_03_CONFIG)
        self.data_loader = data_loader
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce StrategySignal for USDBRL based on flow composites.

        Returns empty list if any required flow component is missing.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategySignal, or empty list.
        """
        # --- Component 1: BCB FX flow (40%) ---
        bcb_z = self._compute_bcb_flow_z(as_of_date)
        if bcb_z is None:
            return []

        # --- Component 2: CFTC BRL positioning (35%) ---
        cftc_z = self._compute_cftc_z(as_of_date)
        if cftc_z is None:
            return []

        # --- Component 3: B3 foreign equity flow (25%) ---
        b3_z = self._compute_b3_flow_z(as_of_date)
        if b3_z is None:
            return []

        # --- Composite ---
        composite_z = _BCB_WEIGHT * bcb_z + _CFTC_WEIGHT * cftc_z + _B3_WEIGHT * b3_z

        self.log.info(
            "fx03_composite",
            bcb_z=round(bcb_z, 4),
            cftc_z=round(cftc_z, 4),
            b3_z=round(b3_z, 4),
            composite_z=round(composite_z, 4),
        )

        # Entry threshold
        if abs(composite_z) < _ENTRY_THRESHOLD:
            return []

        # --- Contrarian logic ---
        is_contrarian = abs(composite_z) > _CONTRARIAN_THRESHOLD

        # Base direction: positive composite => SHORT USDBRL (inflows = BRL strength)
        if composite_z > 0:
            base_direction = SignalDirection.SHORT
        else:
            base_direction = SignalDirection.LONG

        # Invert at extremes
        if is_contrarian:
            if base_direction == SignalDirection.SHORT:
                direction = SignalDirection.LONG
            else:
                direction = SignalDirection.SHORT
        else:
            direction = base_direction

        # --- USDBRL spot for stop/take-profit ---
        usdbrl_df = self.data_loader.get_market_data(
            "USDBRL",
            as_of_date,
            lookback_days=30,
        )
        if usdbrl_df.empty:
            return []

        spot = float(usdbrl_df["close"].iloc[-1])

        # Fixed stop/take-profit
        if direction == SignalDirection.SHORT:
            stop_loss = spot * (1.0 + _STOP_LOSS_PCT)
            take_profit = spot * (1.0 - _TAKE_PROFIT_PCT)
        else:
            stop_loss = spot * (1.0 - _STOP_LOSS_PCT)
            take_profit = spot * (1.0 + _TAKE_PROFIT_PCT)

        strength = self.classify_strength(composite_z)
        confidence = min(1.0, abs(composite_z) / 3.0)
        suggested_size = self.size_from_conviction(composite_z)

        signal = StrategySignal(
            strategy_id=self.strategy_id,
            timestamp=datetime.utcnow(),
            direction=direction,
            strength=strength,
            confidence=confidence,
            z_score=composite_z,
            raw_value=composite_z,
            suggested_size=suggested_size,
            asset_class=AssetClass.FX,
            instruments=["USDBRL"],
            entry_level=spot,
            stop_loss=stop_loss,
            take_profit=take_profit,
            holding_period_days=_HOLDING_PERIOD,
            metadata={
                "bcb_z": bcb_z,
                "cftc_z": cftc_z,
                "b3_z": b3_z,
                "composite_z": composite_z,
                "is_contrarian": is_contrarian,
                "base_direction": base_direction.value,
                "spot": spot,
            },
        )
        return [signal]

    # ------------------------------------------------------------------
    # Component 1: BCB FX flow
    # ------------------------------------------------------------------
    def _compute_bcb_flow_z(self, as_of_date: date) -> Optional[float]:
        """Compute BCB net FX flow 21-day rolling sum z-score.

        Returns None if insufficient data.
        """
        flow_df = self.data_loader.get_flow_data(
            "BR_FX_FLOW_NET",
            as_of_date,
            lookback_days=_BCB_LOOKBACK,
        )
        if flow_df.empty or len(flow_df) < _ROLLING_SUM_WINDOW + 10:
            self.log.warning(
                "fx03_missing_bcb_flow", rows=len(flow_df) if not flow_df.empty else 0
            )
            return None

        rolling_sums = flow_df["value"].rolling(_ROLLING_SUM_WINDOW).sum().dropna()
        if len(rolling_sums) < 20:
            return None

        current_sum = float(rolling_sums.iloc[-1])
        history_list = rolling_sums.tail(_BCB_ZSCORE_WINDOW).tolist()
        return self.compute_z_score(
            current_sum, history_list, window=_BCB_ZSCORE_WINDOW
        )

    # ------------------------------------------------------------------
    # Component 2: CFTC BRL positioning
    # ------------------------------------------------------------------
    def _compute_cftc_z(self, as_of_date: date) -> Optional[float]:
        """Compute CFTC leveraged net BRL positioning z-score.

        Returns None if insufficient data.
        """
        cftc_df = self.data_loader.get_flow_data(
            "CFTC_6L_LEVERAGED_NET",
            as_of_date,
            lookback_days=_CFTC_LOOKBACK,
        )
        if cftc_df.empty or len(cftc_df) < 20:
            self.log.warning(
                "fx03_missing_cftc_data", rows=len(cftc_df) if not cftc_df.empty else 0
            )
            return None

        current_position = float(cftc_df["value"].iloc[-1])
        history_list = cftc_df["value"].tail(_CFTC_ZSCORE_WINDOW).tolist()
        return self.compute_z_score(
            current_position, history_list, window=_CFTC_ZSCORE_WINDOW
        )

    # ------------------------------------------------------------------
    # Component 3: B3 foreign equity flow
    # ------------------------------------------------------------------
    def _compute_b3_flow_z(self, as_of_date: date) -> Optional[float]:
        """Compute B3 foreign financial flow 21-day rolling sum z-score.

        Uses BR_FX_FLOW_FINANCIAL as proxy for foreign equity flow.
        Returns None if insufficient data.
        """
        b3_df = self.data_loader.get_flow_data(
            "BR_FX_FLOW_FINANCIAL",
            as_of_date,
            lookback_days=_B3_LOOKBACK,
        )
        if b3_df.empty or len(b3_df) < _ROLLING_SUM_WINDOW + 10:
            self.log.warning(
                "fx03_missing_b3_flow", rows=len(b3_df) if not b3_df.empty else 0
            )
            return None

        rolling_sums = b3_df["value"].rolling(_ROLLING_SUM_WINDOW).sum().dropna()
        if len(rolling_sums) < 20:
            return None

        current_sum = float(rolling_sums.iloc[-1])
        history_list = rolling_sums.tail(_BCB_ZSCORE_WINDOW).tolist()
        return self.compute_z_score(
            current_sum, history_list, window=_BCB_ZSCORE_WINDOW
        )
