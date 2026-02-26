"""RATES_BR_03: BR DI Curve Slope (Flattener/Steepener) strategy.

Computes the z-score of the 2Y-5Y slope on the DI curve relative to its
rolling 252-day history.  When the slope is unusually steep or flat, the
strategy enters a flattener or steepener trade, respectively.

Monetary cycle context (Selic direction) informs position direction:

- Slope unusually steep (z > threshold): FLATTENER (long 2Y, short 5Y)
  in both easing (front-end compresses more) and tightening (front-end
  rises faster) cycles.
- Slope unusually flat/inverted (z < -threshold): STEEPENER (long 5Y,
  short 2Y) -- expect normalization.

The strategy consumes DI curve data and macro series (Selic, Focus IPCA)
via the PointInTimeDataLoader.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import structlog

from src.agents.base import AgentSignal, classify_strength
from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection
from src.core.utils.tenors import find_closest_tenor
from src.strategies.base import BaseStrategy, StrategyConfig, StrategyPosition

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
RATES_BR_03_CONFIG = StrategyConfig(
    strategy_id="RATES_BR_03",
    strategy_name="BR DI Curve Slope",
    asset_class=AssetClass.FIXED_INCOME,
    instruments=["DI_PRE"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.03,
    take_profit_pct=0.06,
)

# Tenor targets in business days
_2Y_TARGET = 504
_5Y_TARGET = 1260
_TENOR_TOLERANCE = 100  # tolerance for matching available tenors


class RatesBR03SlopeStrategy(BaseStrategy):
    """DI Curve Slope (Flattener/Steepener) strategy.

    Trades the 2Y-5Y slope of the DI curve based on its z-score relative
    to the rolling 252-day distribution, conditioned on the monetary cycle.

    Args:
        data_loader: PointInTimeDataLoader for fetching curve and macro data.
        slope_z_threshold: Z-score threshold for generating a signal (default 1.5).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        slope_z_threshold: float = 1.5,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or RATES_BR_03_CONFIG)
        self.data_loader = data_loader
        self.slope_z_threshold = slope_z_threshold
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """Produce target positions based on DI 2Y-5Y slope z-score analysis.

        Steps:
            1. Load DI curve and identify 2Y and 5Y tenors.
            2. Compute current slope = rate_5Y - rate_2Y.
            3. Load historical rate series for both tenors.
            4. Compute rolling 252-day z-score of the slope.
            5. Check monetary cycle (Selic direction) for context.
            6. Generate flattener/steepener position based on z-score and cycle.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategyPosition, or empty list if data
            is insufficient or z-score is within threshold.
        """
        # 1. Load DI curve
        curve = self.data_loader.get_curve("DI_PRE", as_of_date)
        if not curve:
            self.log.warning("empty_curve", as_of_date=str(as_of_date))
            return []

        # Identify 2Y and 5Y tenors
        tenor_2y = find_closest_tenor(curve, _2Y_TARGET, _TENOR_TOLERANCE)
        tenor_5y = find_closest_tenor(curve, _5Y_TARGET, _TENOR_TOLERANCE)

        if tenor_2y is None or tenor_5y is None:
            self.log.warning(
                "missing_tenors",
                tenor_2y=tenor_2y,
                tenor_5y=tenor_5y,
                available=list(curve.keys()),
            )
            return []

        # 2. Current slope
        current_slope = curve[tenor_5y] - curve[tenor_2y]

        # 3. Load historical rate series
        hist_2y = self.data_loader.get_curve_history(
            "DI_PRE", tenor_2y, as_of_date, lookback_days=756
        )
        hist_5y = self.data_loader.get_curve_history(
            "DI_PRE", tenor_5y, as_of_date, lookback_days=756
        )

        if hist_2y.empty or hist_5y.empty:
            self.log.warning("empty_history", as_of_date=str(as_of_date))
            return []

        # 4. Compute historical slope series (aligned by date)
        slope_series = self._compute_slope_series(hist_2y, hist_5y)
        if slope_series is None or len(slope_series) < 60:
            self.log.warning(
                "insufficient_slope_history",
                points=0 if slope_series is None else len(slope_series),
            )
            return []

        # 5. Compute z-score of current slope vs rolling 252-day stats
        z_score = self._compute_z_score(current_slope, slope_series)
        if z_score is None:
            return []

        # 6. Load monetary cycle context
        cycle_direction = self._detect_monetary_cycle(as_of_date)

        # 7. Generate signal
        return self._generate_slope_position(
            z_score, current_slope, cycle_direction, tenor_2y, tenor_5y, as_of_date
        )

    def _compute_slope_series(
        self,
        hist_2y: pd.DataFrame,
        hist_5y: pd.DataFrame,
    ) -> pd.Series | None:
        """Compute historical slope series from aligned 2Y and 5Y histories.

        Args:
            hist_2y: DataFrame with 'rate' column for 2Y tenor.
            hist_5y: DataFrame with 'rate' column for 5Y tenor.

        Returns:
            Series of slope values (5Y - 2Y) indexed by date, or None.
        """
        # Align by date (inner join)
        combined = hist_2y[["rate"]].join(
            hist_5y[["rate"]], lsuffix="_2y", rsuffix="_5y", how="inner"
        )
        if combined.empty:
            return None
        return combined["rate_5y"] - combined["rate_2y"]

    def _compute_z_score(
        self,
        current_slope: float,
        slope_series: pd.Series,
    ) -> float | None:
        """Compute z-score of current slope vs rolling 252-day distribution.

        Args:
            current_slope: Today's 5Y-2Y slope.
            slope_series: Historical slope values.

        Returns:
            Z-score float, or None if std is zero/nan.
        """
        # Use the last 252 points (or all available if fewer)
        window = slope_series.tail(252)
        mean = float(window.mean())
        std = float(window.std())

        if std <= 0 or np.isnan(std):
            return None

        return (current_slope - mean) / std

    def _detect_monetary_cycle(self, as_of_date: date) -> str:
        """Detect monetary cycle direction from Selic target history.

        Looks at the last 2 changes in the Selic target series to determine
        if the BCB is easing, tightening, or holding.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            One of 'easing', 'tightening', or 'holding'.
        """
        selic_hist = self.data_loader.get_macro_series(
            "BR_SELIC_TARGET", as_of_date, lookback_days=756
        )
        if selic_hist.empty or len(selic_hist) < 2:
            return "holding"

        # Get the last few distinct values
        values = selic_hist["value"].dropna()
        if len(values) < 2:
            return "holding"

        # Detect direction of the last 2 changes
        changes = values.diff().dropna()
        recent_changes = changes.tail(2)

        if recent_changes.empty:
            return "holding"

        last_change = float(recent_changes.iloc[-1])
        if last_change < 0:
            return "easing"
        elif last_change > 0:
            return "tightening"
        return "holding"

    def _generate_slope_position(
        self,
        z_score: float,
        current_slope: float,
        cycle_direction: str,
        tenor_2y: int,
        tenor_5y: int,
        as_of_date: date,
    ) -> list[StrategyPosition]:
        """Generate flattener/steepener position from slope z-score.

        Args:
            z_score: Slope z-score.
            current_slope: Current 5Y-2Y slope.
            cycle_direction: 'easing', 'tightening', or 'holding'.
            tenor_2y: Matched 2Y tenor.
            tenor_5y: Matched 5Y tenor.
            as_of_date: Reference date.

        Returns:
            List with single position or empty list.
        """
        if z_score > self.slope_z_threshold:
            # Slope unusually steep -> FLATTENER (positive weight convention)
            direction = SignalDirection.LONG
            raw_weight_sign = 1.0
        elif z_score < -self.slope_z_threshold:
            # Slope unusually flat/inverted -> STEEPENER (negative weight convention)
            direction = SignalDirection.SHORT
            raw_weight_sign = -1.0
        else:
            # Z-score within threshold -> NEUTRAL
            return []

        confidence = min(1.0, abs(z_score) / (self.slope_z_threshold * 2.5))
        strength = classify_strength(confidence)

        signal_id = f"DI_SLOPE_{tenor_2y}_{tenor_5y}"

        agent_signal = AgentSignal(
            signal_id=signal_id,
            agent_id=self.strategy_id,
            timestamp=np.datetime64("now"),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=z_score,
            horizon_days=63,  # quarterly horizon
            metadata={
                "z_score": z_score,
                "current_slope": current_slope,
                "cycle_direction": cycle_direction,
                "tenor_2y": tenor_2y,
                "tenor_5y": tenor_5y,
                "trade_type": "flattener" if raw_weight_sign > 0 else "steepener",
            },
        )

        positions = self.signals_to_positions([agent_signal])

        # Enrich metadata
        for pos in positions:
            pos.metadata.update({
                "z_score": z_score,
                "current_slope": current_slope,
                "cycle_direction": cycle_direction,
                "tenor_2y": tenor_2y,
                "tenor_5y": tenor_5y,
                "trade_type": "flattener" if raw_weight_sign > 0 else "steepener",
                "curve_date": str(as_of_date),
            })

        self.log.info(
            "slope_signal_generated",
            z_score=round(z_score, 3),
            slope=round(current_slope, 4),
            cycle=cycle_direction,
            trade="flattener" if raw_weight_sign > 0 else "steepener",
        )

        return positions
