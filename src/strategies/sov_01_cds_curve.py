"""SOV_01: CDS Curve Trading strategy.

Trades Brazil CDS 1Y/5Y/10Y slope and level using three components:

- **Level signal (50%)**: Z-score of 5Y CDS vs 252-day history. High z =
  credit stress elevated.
- **Slope signal (30%)**: Z-score of (5Y - 1Y) CDS slope vs history.
  Inverted slope (1Y > 5Y) = acute near-term stress.
- **Fiscal factor (20%)**: Debt-to-GDP deviation from 75% neutral level,
  clamped to [-1, 1].

Direction logic:
    - composite > 0 and |composite| < 3: mean reversion expected => SHORT CDS
      (sell protection).
    - |composite| >= 3: tail risk, follow trend => LONG CDS (buy protection).
    - composite < 0: credit cheap => LONG CDS if |z| >= 1.25.

Entry threshold: |composite_z| >= 1.25.
Stop-loss: 15% of CDS level.
Take-profit: 10% of CDS level.
Holding period: 21 days.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import structlog

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection
from src.strategies.base import BaseStrategy, StrategyConfig, StrategySignal
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
SOV_01_CONFIG = StrategyConfig(
    strategy_id="SOV_01",
    strategy_name="CDS Curve Trading",
    asset_class=AssetClass.SOVEREIGN_CREDIT,
    instruments=["CDS_BR"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.15,
    take_profit_pct=0.10,
)

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
_LEVEL_WEIGHT = 0.50
_SLOPE_WEIGHT = 0.30
_FISCAL_WEIGHT = 0.20
_CDS_LOOKBACK = 1260  # ~5 years
_ZSCORE_WINDOW = 252
_ENTRY_THRESHOLD = 1.25
_TAIL_THRESHOLD = 3.0
_FISCAL_NEUTRAL = 75.0
_FISCAL_SCALE = 10.0
_HOLDING_PERIOD = 21


@StrategyRegistry.register(
    "SOV_01",
    asset_class=AssetClass.SOVEREIGN_CREDIT,
    instruments=["CDS_BR"],
)
class Sov01CdsCurveStrategy(BaseStrategy):
    """CDS Curve Trading strategy for Brazil sovereign credit.

    Composites CDS level z-score (50%), slope z-score (30%), and fiscal
    factor (20%) into a directional CDS trade signal.

    Args:
        data_loader: PointInTimeDataLoader for fetching macro / market data.
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or SOV_01_CONFIG)
        self.data_loader = data_loader
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce StrategySignal for Brazil CDS based on curve + fiscal.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategySignal, or empty list when data
            is missing or the composite signal is below entry threshold.
        """
        # --- Component 1: Level z-score (50%) ---
        level_z = self._compute_level_z(as_of_date)
        if level_z is None:
            return []

        # --- Component 2: Slope z-score (30%) ---
        slope_z = self._compute_slope_z(as_of_date)
        # slope_z can be None if only 5Y is available; use 0.0 fallback
        if slope_z is None:
            slope_z = 0.0

        # --- Component 3: Fiscal factor (20%) ---
        fiscal_factor = self._compute_fiscal_factor(as_of_date)
        # Fiscal can be None if macro data missing; use 0.0 fallback
        if fiscal_factor is None:
            fiscal_factor = 0.0

        # --- Composite ---
        composite_z = (
            _LEVEL_WEIGHT * level_z
            + _SLOPE_WEIGHT * slope_z
            + _FISCAL_WEIGHT * fiscal_factor
        )

        self.log.info(
            "sov01_composite",
            level_z=round(level_z, 4),
            slope_z=round(slope_z, 4),
            fiscal_factor=round(fiscal_factor, 4),
            composite_z=round(composite_z, 4),
        )

        # Entry threshold
        if abs(composite_z) < _ENTRY_THRESHOLD:
            return []

        # Direction logic
        if composite_z > 0:
            if abs(composite_z) >= _TAIL_THRESHOLD:
                # Tail risk: follow trend => LONG CDS (buy protection)
                direction = SignalDirection.LONG
            else:
                # Mean reversion: credit stress elevated => SHORT CDS (sell protection)
                direction = SignalDirection.SHORT
        else:
            # Credit cheap => LONG CDS (buy protection for value)
            direction = SignalDirection.LONG

        # --- CDS spot for stop / take-profit ---
        cds_level = self._get_cds_level(as_of_date)
        entry_level = cds_level if cds_level is not None else 200.0
        stop_loss = (
            entry_level * (1 + self.config.stop_loss_pct)
            if direction == SignalDirection.LONG
            else entry_level * (1 - self.config.stop_loss_pct)
        )
        take_profit = (
            entry_level * (1 - self.config.take_profit_pct)
            if direction == SignalDirection.LONG
            else entry_level * (1 + self.config.take_profit_pct)
        )
        # Swap for SHORT (selling protection: profit if CDS falls)
        if direction == SignalDirection.SHORT:
            stop_loss = entry_level * (1 + self.config.stop_loss_pct)
            take_profit = entry_level * (1 - self.config.take_profit_pct)

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
            asset_class=AssetClass.SOVEREIGN_CREDIT,
            instruments=["CDS_BR"],
            entry_level=entry_level,
            stop_loss=stop_loss,
            take_profit=take_profit,
            holding_period_days=_HOLDING_PERIOD,
            metadata={
                "level_z": level_z,
                "slope_z": slope_z,
                "fiscal_factor": fiscal_factor,
                "composite_z": composite_z,
                "cds_level": cds_level,
            },
        )
        return [signal]

    # ------------------------------------------------------------------
    # Component 1: CDS level z-score
    # ------------------------------------------------------------------
    def _compute_level_z(self, as_of_date: date) -> Optional[float]:
        """Compute 5Y CDS level z-score vs 252-day history.

        Returns None if CDS data is missing.
        """
        cds_df = self.data_loader.get_macro_series(
            "BR_CDS_5Y",
            as_of_date,
            lookback_days=_CDS_LOOKBACK,
        )
        if cds_df.empty or len(cds_df) < 20:
            self.log.warning("sov01_missing_cds_5y", as_of_date=str(as_of_date))
            return None

        values = cds_df["value"].tolist()
        current = values[-1]
        return self.compute_z_score(current, values, window=_ZSCORE_WINDOW)

    # ------------------------------------------------------------------
    # Component 2: CDS slope z-score
    # ------------------------------------------------------------------
    def _compute_slope_z(self, as_of_date: date) -> Optional[float]:
        """Compute (5Y - 1Y) CDS slope z-score vs history.

        Returns None if 1Y CDS data is not available.
        """
        cds_5y_df = self.data_loader.get_macro_series(
            "BR_CDS_5Y",
            as_of_date,
            lookback_days=_CDS_LOOKBACK,
        )
        cds_1y_df = self.data_loader.get_macro_series(
            "BR_CDS_1Y",
            as_of_date,
            lookback_days=_CDS_LOOKBACK,
        )

        if cds_5y_df.empty or cds_1y_df.empty:
            return None

        if len(cds_5y_df) < 20 or len(cds_1y_df) < 20:
            return None

        # Align on common dates
        common_idx = cds_5y_df.index.intersection(cds_1y_df.index)
        if len(common_idx) < 20:
            return None

        slopes = (
            cds_5y_df.loc[common_idx, "value"].values
            - cds_1y_df.loc[common_idx, "value"].values
        )
        slopes_list = slopes.tolist()
        current_slope = slopes_list[-1]

        return self.compute_z_score(current_slope, slopes_list, window=_ZSCORE_WINDOW)

    # ------------------------------------------------------------------
    # Component 3: Fiscal factor
    # ------------------------------------------------------------------
    def _compute_fiscal_factor(self, as_of_date: date) -> Optional[float]:
        """Compute fiscal factor from debt-to-GDP.

        Fiscal factor = (debt_pct - 75) / 10, clamped to [-1, 1].
        Returns None if debt data is missing.
        """
        debt_pct = self.data_loader.get_latest_macro_value(
            "BR_GROSS_DEBT_PCT_GDP",
            as_of_date,
        )
        if debt_pct is None:
            # Try alternative series
            debt_pct = self.data_loader.get_latest_macro_value(
                "BR_GROSS_DEBT_GDP",
                as_of_date,
            )
        if debt_pct is None:
            return None

        factor = (debt_pct - _FISCAL_NEUTRAL) / _FISCAL_SCALE
        return max(-1.0, min(1.0, factor))

    # ------------------------------------------------------------------
    # Helper: get current CDS level
    # ------------------------------------------------------------------
    def _get_cds_level(self, as_of_date: date) -> Optional[float]:
        """Get the latest 5Y CDS level value."""
        return self.data_loader.get_latest_macro_value(
            "BR_CDS_5Y",
            as_of_date,
        )
