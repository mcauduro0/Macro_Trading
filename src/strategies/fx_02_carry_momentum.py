"""FX_02: Carry-Adjusted Momentum strategy for USDBRL.

Combines two components into a directional USDBRL signal:

- **Carry z-score (50%)**: Selic-FFR spread z-scored vs 252-day history.
  High carry advantage => SHORT USDBRL (BRL strength).
- **Momentum z-score (50%)**: 63-day USDBRL log return z-scored vs
  504-day history of rolling 63-day returns.

Vol-adjusted sizing multiplies suggested_size by
``min(1.0, target_vol / realized_vol)`` where realized_vol is 21-day
annualized USDBRL vol.

Direction: composite > 0 => SHORT USDBRL (carry + momentum favor BRL).
Entry threshold: |composite_z| >= 0.75.
Stop-loss: vol-based, entry +/- 2.5 * daily_vol * sqrt(holding_period).
Take-profit: 1.5 * |entry - stop|.
Holding period: 21 days (medium-term).
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional

import numpy as np
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
FX_02_CONFIG = StrategyConfig(
    strategy_id="FX_02",
    strategy_name="USDBRL Carry-Adjusted Momentum",
    asset_class=AssetClass.FX,
    instruments=["USDBRL"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.05,
    take_profit_pct=0.10,
)

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
_CARRY_WEIGHT = 0.50
_MOMENTUM_WEIGHT = 0.50
_CARRY_LOOKBACK = 252
_MOMENTUM_RETURN_WINDOW = 63
_MOMENTUM_HISTORY_LOOKBACK = 504
_ENTRY_THRESHOLD = 0.75
_STOP_LOSS_VOL_MULT = 2.5
_TAKE_PROFIT_RATIO = 1.5
_TARGET_VOL = 0.15
_VOL_WINDOW = 21
_HOLDING_PERIOD = 21


@StrategyRegistry.register("FX_02", asset_class=AssetClass.FX, instruments=["USDBRL"])
class Fx02CarryMomentumStrategy(BaseStrategy):
    """USDBRL Carry-Adjusted Momentum strategy.

    Composites Selic-FFR carry z-score (50%) with 3M USDBRL momentum
    z-score (50%) and applies vol-adjusted sizing.

    Args:
        data_loader: PointInTimeDataLoader for fetching macro / market data.
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or FX_02_CONFIG)
        self.data_loader = data_loader
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce StrategySignal for USDBRL based on carry + momentum.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategySignal, or empty list when data
            is missing or the composite signal is below entry threshold.
        """
        # --- Component 1: Carry z-score (50%) ---
        carry_z = self._compute_carry_z(as_of_date)
        if carry_z is None:
            return []

        # --- Component 2: Momentum z-score (50%) ---
        momentum_z = self._compute_momentum_z(as_of_date)
        if momentum_z is None:
            return []

        # --- Composite ---
        composite_z = _CARRY_WEIGHT * carry_z + _MOMENTUM_WEIGHT * momentum_z

        self.log.info(
            "fx02_composite",
            carry_z=round(carry_z, 4),
            momentum_z=round(momentum_z, 4),
            composite_z=round(composite_z, 4),
        )

        # Entry threshold
        if abs(composite_z) < _ENTRY_THRESHOLD:
            return []

        # Direction: composite > 0 => SHORT USDBRL (BRL strength)
        if composite_z > 0:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.LONG

        # --- USDBRL spot and vol for sizing / stop / take-profit ---
        usdbrl_df = self.data_loader.get_market_data(
            "USDBRL", as_of_date, lookback_days=_MOMENTUM_HISTORY_LOOKBACK,
        )
        if usdbrl_df.empty or len(usdbrl_df) < _VOL_WINDOW + 1:
            return []

        spot = float(usdbrl_df["close"].iloc[-1])
        returns = usdbrl_df["close"].pct_change().dropna().tail(_VOL_WINDOW)
        if len(returns) < _VOL_WINDOW:
            return []

        daily_vol = float(returns.std(ddof=0))
        realized_vol = daily_vol * math.sqrt(252)

        # Vol-adjusted sizing
        vol_scale = min(1.0, _TARGET_VOL / realized_vol) if realized_vol > 0 else 1.0
        base_size = self.size_from_conviction(composite_z)
        suggested_size = base_size * vol_scale

        # Stop-loss: vol-based
        stop_distance = _STOP_LOSS_VOL_MULT * daily_vol * math.sqrt(_HOLDING_PERIOD) * spot
        if direction == SignalDirection.SHORT:
            stop_loss = spot + stop_distance
            take_profit = spot - _TAKE_PROFIT_RATIO * stop_distance
        else:
            stop_loss = spot - stop_distance
            take_profit = spot + _TAKE_PROFIT_RATIO * stop_distance

        strength = self.classify_strength(composite_z)
        confidence = min(1.0, abs(composite_z) / 3.0)

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
                "carry_z": carry_z,
                "momentum_z": momentum_z,
                "composite_z": composite_z,
                "daily_vol": daily_vol,
                "realized_vol": realized_vol,
                "vol_scale": vol_scale,
                "spot": spot,
            },
        )
        return [signal]

    # ------------------------------------------------------------------
    # Component 1: Carry z-score
    # ------------------------------------------------------------------
    def _compute_carry_z(self, as_of_date: date) -> Optional[float]:
        """Compute Selic-FFR carry spread z-score vs 252-day history.

        Returns None if data is missing.
        """
        br_rate = self.data_loader.get_latest_macro_value(
            "BR_SELIC_TARGET", as_of_date,
        )
        if br_rate is None:
            self.log.warning("fx02_missing_br_rate", as_of_date=str(as_of_date))
            return None

        us_rate = self.data_loader.get_latest_macro_value(
            "US_FED_FUNDS", as_of_date,
        )
        if us_rate is None:
            self.log.warning("fx02_missing_us_rate", as_of_date=str(as_of_date))
            return None

        current_spread = br_rate - us_rate

        # Build spread history over lookback
        macro_df = self.data_loader.get_macro_series(
            "BR_SELIC_TARGET", as_of_date, lookback_days=_CARRY_LOOKBACK + 100,
        )
        us_macro_df = self.data_loader.get_macro_series(
            "US_FED_FUNDS", as_of_date, lookback_days=_CARRY_LOOKBACK + 100,
        )

        if macro_df.empty or us_macro_df.empty:
            # Fallback: use current spread as z=0 equivalent
            self.log.warning("fx02_no_spread_history")
            return None

        # Align on common dates and compute spread history
        br_values = macro_df["value"].reindex(
            macro_df.index.union(us_macro_df.index), method="ffill"
        )
        us_values = us_macro_df["value"].reindex(
            br_values.index, method="ffill"
        )
        spread_history = (br_values - us_values).dropna()

        if len(spread_history) < 10:
            return None

        history_list = spread_history.tail(_CARRY_LOOKBACK).tolist()
        return self.compute_z_score(current_spread, history_list, window=_CARRY_LOOKBACK)

    # ------------------------------------------------------------------
    # Component 2: Momentum z-score
    # ------------------------------------------------------------------
    def _compute_momentum_z(self, as_of_date: date) -> Optional[float]:
        """Compute 63-day USDBRL log return z-scored vs 504-day history.

        Returns None if insufficient data.
        """
        usdbrl_df = self.data_loader.get_market_data(
            "USDBRL", as_of_date, lookback_days=_MOMENTUM_HISTORY_LOOKBACK + 100,
        )
        if usdbrl_df.empty or len(usdbrl_df) < _MOMENTUM_RETURN_WINDOW + 10:
            self.log.warning(
                "fx02_insufficient_momentum_data",
                rows=len(usdbrl_df) if not usdbrl_df.empty else 0,
            )
            return None

        closes = usdbrl_df["close"]

        # Compute rolling 63-day log returns
        log_returns_63d = np.log(closes / closes.shift(_MOMENTUM_RETURN_WINDOW)).dropna()

        if len(log_returns_63d) < 20:
            return None

        current_return = float(log_returns_63d.iloc[-1])
        history_list = log_returns_63d.tail(_MOMENTUM_HISTORY_LOOKBACK).tolist()

        return self.compute_z_score(
            current_return, history_list, window=_MOMENTUM_HISTORY_LOOKBACK,
        )
