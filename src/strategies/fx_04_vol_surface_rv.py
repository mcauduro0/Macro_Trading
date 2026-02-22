"""FX_04: Vol Surface Relative Value strategy for USDBRL.

Analyzes USDBRL volatility surface through 4 statistical components:

- **Implied-Realized Premium (40%)**: Gap between implied vol proxy
  and 21-day realized vol, z-scored vs 252-day history.
- **Term Structure Slope (25%)**: Short-term (21d) vs longer-term (63d)
  realized vol ratio; inverted term structure signals stress.
- **Skew Proxy (20%)**: Skewness of 63-day daily returns. Positive
  skew = tail risk to USDBRL upside (BRL weakness).
- **Kurtosis Signal (15%)**: Excess kurtosis of 63-day returns. High
  kurtosis = fat tails = vol expansion expected.

Direction: composite > 0 => LONG USDBRL (vol surface signals BRL stress).
composite < 0 => SHORT USDBRL (vol surface cheap).
Entry threshold: |composite_z| >= 1.0.
Stop-loss: vol-based, 2.0 * daily_vol * sqrt(14) from entry.
Take-profit: 1.5 * stop distance.
Holding period: 14 days.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional

import numpy as np
import structlog
from scipy import stats as scipy_stats

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection, SignalStrength
from src.strategies.base import (
    BaseStrategy,
    StrategyConfig,
    StrategySignal,
)
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
FX_04_CONFIG = StrategyConfig(
    strategy_id="FX_04",
    strategy_name="USDBRL Vol Surface Relative Value",
    asset_class=AssetClass.FX,
    instruments=["USDBRL"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.05,
    take_profit_pct=0.075,
)

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
_IV_RV_WEIGHT = 0.40
_TERM_STRUCTURE_WEIGHT = 0.25
_SKEW_WEIGHT = 0.20
_KURTOSIS_WEIGHT = 0.15
_SHORT_VOL_WINDOW = 21
_LONG_VOL_WINDOW = 63
_MOMENTS_WINDOW = 63
_ZSCORE_LOOKBACK = 252
_HISTORY_LOOKBACK = 504
_ENTRY_THRESHOLD = 1.0
_STOP_LOSS_VOL_MULT = 2.0
_TAKE_PROFIT_RATIO = 1.5
_HOLDING_PERIOD = 14


@StrategyRegistry.register("FX_04", asset_class=AssetClass.FX, instruments=["USDBRL"])
class Fx04VolSurfaceRvStrategy(BaseStrategy):
    """USDBRL Vol Surface Relative Value strategy.

    Analyzes USDBRL vol surface through implied-realized premium (40%),
    term structure slope (25%), skew proxy (20%), and kurtosis signal (15%).

    Args:
        data_loader: PointInTimeDataLoader for fetching market data.
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or FX_04_CONFIG)
        self.data_loader = data_loader
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce StrategySignal for USDBRL based on vol surface analysis.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategySignal, or empty list when data
            is missing or the composite signal is below entry threshold.
        """
        # Load USDBRL data
        usdbrl_df = self.data_loader.get_market_data(
            "USDBRL", as_of_date, lookback_days=_HISTORY_LOOKBACK + 100,
        )
        if usdbrl_df.empty or len(usdbrl_df) < _HISTORY_LOOKBACK:
            self.log.warning(
                "fx04_insufficient_data",
                rows=len(usdbrl_df) if not usdbrl_df.empty else 0,
            )
            return []

        closes = usdbrl_df["close"]
        daily_returns = closes.pct_change().dropna()

        if len(daily_returns) < _HISTORY_LOOKBACK:
            return []

        # --- Component 1: Implied-Realized Premium (40%) ---
        iv_rv_z = self._compute_iv_rv_premium_z(daily_returns)
        if iv_rv_z is None:
            return []

        # --- Component 2: Term Structure Slope (25%) ---
        term_z = self._compute_term_structure_z(daily_returns)
        if term_z is None:
            return []

        # --- Component 3: Skew Proxy (20%) ---
        skew_z = self._compute_skew_z(daily_returns)
        if skew_z is None:
            return []

        # --- Component 4: Kurtosis Signal (15%) ---
        kurt_z = self._compute_kurtosis_z(daily_returns)
        if kurt_z is None:
            return []

        # --- Composite ---
        composite_z = (
            _IV_RV_WEIGHT * iv_rv_z
            + _TERM_STRUCTURE_WEIGHT * term_z
            + _SKEW_WEIGHT * skew_z
            + _KURTOSIS_WEIGHT * kurt_z
        )

        self.log.info(
            "fx04_composite",
            iv_rv_z=round(iv_rv_z, 4),
            term_z=round(term_z, 4),
            skew_z=round(skew_z, 4),
            kurt_z=round(kurt_z, 4),
            composite_z=round(composite_z, 4),
        )

        # Entry threshold
        if abs(composite_z) < _ENTRY_THRESHOLD:
            return []

        # Direction: composite > 0 => LONG USDBRL (vol surface signals BRL stress)
        if composite_z > 0:
            direction = SignalDirection.LONG
        else:
            direction = SignalDirection.SHORT

        spot = float(closes.iloc[-1])
        recent_returns = daily_returns.tail(_SHORT_VOL_WINDOW)
        daily_vol = float(recent_returns.std(ddof=0))

        # Vol-based stop-loss
        stop_distance = _STOP_LOSS_VOL_MULT * daily_vol * math.sqrt(_HOLDING_PERIOD) * spot
        if direction == SignalDirection.LONG:
            stop_loss = spot - stop_distance
            take_profit = spot + _TAKE_PROFIT_RATIO * stop_distance
        else:
            stop_loss = spot + stop_distance
            take_profit = spot - _TAKE_PROFIT_RATIO * stop_distance

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
                "iv_rv_z": iv_rv_z,
                "term_z": term_z,
                "skew_z": skew_z,
                "kurt_z": kurt_z,
                "composite_z": composite_z,
                "daily_vol": daily_vol,
                "spot": spot,
            },
        )
        return [signal]

    # ------------------------------------------------------------------
    # Component 1: Implied-Realized Premium
    # ------------------------------------------------------------------
    def _compute_iv_rv_premium_z(
        self, daily_returns: "pd.Series",
    ) -> Optional[float]:
        """Compute implied-realized vol premium z-score.

        Uses absolute daily return z-score scaled by sqrt(252) as
        an implied vol proxy when no direct IV series is available.
        """
        if len(daily_returns) < _ZSCORE_LOOKBACK + _SHORT_VOL_WINDOW:
            return None

        # Build rolling realized vol (21-day)
        rolling_rv = daily_returns.rolling(_SHORT_VOL_WINDOW).std(ddof=0) * math.sqrt(252)

        # Implied vol proxy: rolling mean of |returns| * sqrt(252) * sqrt(pi/2)
        # This is the volatility estimator based on mean absolute deviation
        rolling_iv = (
            daily_returns.abs().rolling(_SHORT_VOL_WINDOW).mean()
            * math.sqrt(252)
            * math.sqrt(math.pi / 2)
        )

        premium = (rolling_iv - rolling_rv).dropna()

        if len(premium) < _ZSCORE_LOOKBACK:
            return None

        current_premium = float(premium.iloc[-1])
        history_list = premium.tail(_ZSCORE_LOOKBACK).tolist()
        return self.compute_z_score(current_premium, history_list, window=_ZSCORE_LOOKBACK)

    # ------------------------------------------------------------------
    # Component 2: Term Structure Slope
    # ------------------------------------------------------------------
    def _compute_term_structure_z(
        self, daily_returns: "pd.Series",
    ) -> Optional[float]:
        """Compute short/long vol ratio z-score.

        Inverted term structure (short > long) signals stress.
        """
        if len(daily_returns) < _ZSCORE_LOOKBACK + _LONG_VOL_WINDOW:
            return None

        short_vol = daily_returns.rolling(_SHORT_VOL_WINDOW).std(ddof=0)
        long_vol = daily_returns.rolling(_LONG_VOL_WINDOW).std(ddof=0)

        # Avoid division by zero
        ratio = (short_vol / long_vol.replace(0, np.nan)).dropna()

        if len(ratio) < _ZSCORE_LOOKBACK:
            return None

        current_ratio = float(ratio.iloc[-1])
        history_list = ratio.tail(_ZSCORE_LOOKBACK).tolist()
        return self.compute_z_score(current_ratio, history_list, window=_ZSCORE_LOOKBACK)

    # ------------------------------------------------------------------
    # Component 3: Skew Proxy
    # ------------------------------------------------------------------
    def _compute_skew_z(
        self, daily_returns: "pd.Series",
    ) -> Optional[float]:
        """Compute rolling 63-day return skewness z-score.

        Positive skew = tail risk to USDBRL upside (BRL weakness).
        """
        if len(daily_returns) < _HISTORY_LOOKBACK:
            return None

        # Compute rolling skewness
        rolling_skew = daily_returns.rolling(_MOMENTS_WINDOW).apply(
            lambda x: float(scipy_stats.skew(x, bias=False)), raw=True,
        ).dropna()

        if len(rolling_skew) < _ZSCORE_LOOKBACK:
            return None

        current_skew = float(rolling_skew.iloc[-1])
        history_list = rolling_skew.tail(_HISTORY_LOOKBACK).tolist()
        return self.compute_z_score(current_skew, history_list, window=_HISTORY_LOOKBACK)

    # ------------------------------------------------------------------
    # Component 4: Kurtosis Signal
    # ------------------------------------------------------------------
    def _compute_kurtosis_z(
        self, daily_returns: "pd.Series",
    ) -> Optional[float]:
        """Compute rolling 63-day excess kurtosis z-score.

        High kurtosis = fat tails = vol expansion expected.
        """
        if len(daily_returns) < _HISTORY_LOOKBACK:
            return None

        # Compute rolling excess kurtosis
        rolling_kurt = daily_returns.rolling(_MOMENTS_WINDOW).apply(
            lambda x: float(scipy_stats.kurtosis(x, bias=False)), raw=True,
        ).dropna()

        if len(rolling_kurt) < _ZSCORE_LOOKBACK:
            return None

        current_kurt = float(rolling_kurt.iloc[-1])
        history_list = rolling_kurt.tail(_HISTORY_LOOKBACK).tolist()
        return self.compute_z_score(current_kurt, history_list, window=_HISTORY_LOOKBACK)
