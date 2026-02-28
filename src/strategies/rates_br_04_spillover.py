"""RATES_BR_04: US Rates Spillover to BR DI strategy.

Fades DI-UST spread overshoot after large weekly UST moves via mean
reversion.  When US Treasury rates move significantly in a week and the
DI-UST spread deviates from its historical norm (measured by z-score),
the strategy bets on spread normalization:

- Spread too wide (z > threshold after big UST move): LONG DI
  (expect DI rates to fall back toward equilibrium spread).
- Spread too narrow (z < -threshold after big UST move): SHORT DI
  (expect DI rates to rise toward equilibrium spread).

The strategy consumes DI and UST curve data via the PointInTimeDataLoader.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import structlog

from src.agents.base import AgentSignal, classify_strength
from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection
from src.strategies.base import BaseStrategy, StrategyConfig, StrategyPosition

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
RATES_BR_04_CONFIG = StrategyConfig(
    strategy_id="RATES_BR_04",
    strategy_name="US Rates Spillover to BR DI",
    asset_class=AssetClass.FIXED_INCOME,
    instruments=["DI_PRE"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.04,
    take_profit_pct=0.08,
)

# Tenor targets
_DI_1Y_TENOR = 252  # ~1 year in business days
_UST_1Y_TENOR = 365  # ~1 year in calendar days


class RatesBR04SpilloverStrategy(BaseStrategy):
    """US Rates Spillover strategy on the BR DI curve.

    Fades DI-UST spread overshoot after large weekly US Treasury moves
    via mean reversion of the spread z-score.

    Args:
        data_loader: PointInTimeDataLoader for fetching curve data.
        spread_z_threshold: Z-score threshold for spread overshoot signal
            (default 2.0).
        ust_weekly_move_bps: Minimum weekly UST move in bps to trigger
            the strategy (default 15.0).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        spread_z_threshold: float = 2.0,
        ust_weekly_move_bps: float = 15.0,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or RATES_BR_04_CONFIG)
        self.data_loader = data_loader
        self.spread_z_threshold = spread_z_threshold
        self.ust_weekly_move_bps = ust_weekly_move_bps
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """Produce target positions based on DI-UST spread mean reversion.

        Steps:
            1. Load DI 1Y and UST 1Y rate histories.
            2. Compute DI-UST spread series (aligned, forward-filled).
            3. Check weekly UST change (5 business days).
            4. Compute z-score of current spread vs rolling 252-day stats.
            5. Generate LONG/SHORT DI if spread overshoots after big UST move.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategyPosition, or empty list if data
            is insufficient, UST move is small, or spread is within bounds.
        """
        # 1. Load DI 1Y history
        di_hist = self.data_loader.get_curve_history(
            "DI_PRE",
            _DI_1Y_TENOR,
            as_of_date,
            lookback_days=756,
        )
        if di_hist.empty:
            self.log.warning("empty_di_history", as_of_date=str(as_of_date))
            return []

        # 2. Load UST 1Y history
        ust_hist = self.data_loader.get_curve_history(
            "UST_NOM",
            _UST_1Y_TENOR,
            as_of_date,
            lookback_days=756,
        )
        if ust_hist.empty:
            self.log.warning("empty_ust_history", as_of_date=str(as_of_date))
            return []

        # 3. Compute spread series (DI_1Y - UST_1Y, aligned, forward-filled)
        spread_series = self._compute_spread_series(di_hist, ust_hist)
        if spread_series is None or len(spread_series) < 60:
            self.log.warning(
                "insufficient_spread_history",
                points=0 if spread_series is None else len(spread_series),
            )
            return []

        # 4. Check weekly UST change (5 business days)
        ust_values = ust_hist["rate"].dropna()
        if len(ust_values) < 6:
            self.log.warning("insufficient_ust_for_weekly_change")
            return []

        weekly_ust_change = float(ust_values.iloc[-1] - ust_values.iloc[-5])
        weekly_ust_bps = abs(weekly_ust_change) * 10000

        if weekly_ust_bps < self.ust_weekly_move_bps:
            self.log.info(
                "ust_move_too_small",
                weekly_bps=round(weekly_ust_bps, 2),
                threshold=self.ust_weekly_move_bps,
            )
            return []

        # 5. Compute spread z-score
        current_spread = float(spread_series.iloc[-1])
        z_score = self._compute_z_score(current_spread, spread_series)
        if z_score is None:
            return []

        self.log.info(
            "spillover_analysis",
            current_spread=round(current_spread, 4),
            z_score=round(z_score, 4),
            weekly_ust_bps=round(weekly_ust_bps, 2),
        )

        # 6. Generate signal
        return self._generate_spillover_position(
            z_score,
            current_spread,
            weekly_ust_change,
            weekly_ust_bps,
            as_of_date,
        )

    def _compute_spread_series(
        self,
        di_hist: pd.DataFrame,
        ust_hist: pd.DataFrame,
    ) -> pd.Series | None:
        """Compute DI-UST spread series, forward-filling for holiday mismatches.

        Args:
            di_hist: DataFrame with 'rate' column for DI 1Y.
            ust_hist: DataFrame with 'rate' column for UST 1Y.

        Returns:
            Series of spread values (DI - UST), or None if empty.
        """
        combined = di_hist[["rate"]].join(
            ust_hist[["rate"]],
            lsuffix="_di",
            rsuffix="_ust",
            how="outer",
        )
        # Forward-fill for holiday mismatches
        combined = combined.ffill().dropna()
        if combined.empty:
            return None
        return combined["rate_di"] - combined["rate_ust"]

    def _compute_z_score(
        self,
        current_value: float,
        series: pd.Series,
    ) -> float | None:
        """Compute z-score of current value vs rolling 252-day distribution.

        Args:
            current_value: Current observation.
            series: Historical values.

        Returns:
            Z-score, or None if std is zero/nan.
        """
        window = series.tail(252)
        mean = float(window.mean())
        std = float(window.std())

        if std <= 0 or np.isnan(std):
            return None

        return (current_value - mean) / std

    def _generate_spillover_position(
        self,
        z_score: float,
        current_spread: float,
        weekly_ust_change: float,
        weekly_ust_bps: float,
        as_of_date: date,
    ) -> list[StrategyPosition]:
        """Generate position from spread z-score after UST move.

        Args:
            z_score: Spread z-score.
            current_spread: Current DI-UST spread.
            weekly_ust_change: Raw weekly UST change (decimal).
            weekly_ust_bps: Absolute weekly UST move in bps.
            as_of_date: Reference date.

        Returns:
            List with single position or empty list.
        """
        if z_score > self.spread_z_threshold:
            # Spread too wide: DI overshot the UST move -> LONG DI
            # (expect DI rates to fall back = bond prices rise)
            direction = SignalDirection.LONG
        elif z_score < -self.spread_z_threshold:
            # Spread too narrow: DI underreacted to UST move -> SHORT DI
            # (expect DI rates to rise = bond prices fall)
            direction = SignalDirection.SHORT
        else:
            return []

        confidence = min(1.0, abs(z_score) / (self.spread_z_threshold * 2))
        strength = classify_strength(confidence)

        signal_id = f"DI_UST_SPREAD_{_DI_1Y_TENOR}"

        agent_signal = AgentSignal(
            signal_id=signal_id,
            agent_id=self.strategy_id,
            timestamp=np.datetime64("now"),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=z_score,
            horizon_days=21,  # ~1 month horizon for mean reversion
            metadata={
                "z_score": z_score,
                "current_spread": current_spread,
                "weekly_ust_change": weekly_ust_change,
                "weekly_ust_bps": weekly_ust_bps,
            },
        )

        positions = self.signals_to_positions([agent_signal])

        # Enrich metadata
        for pos in positions:
            pos.metadata.update(
                {
                    "z_score": z_score,
                    "current_spread": current_spread,
                    "weekly_ust_change": weekly_ust_change,
                    "weekly_ust_bps": weekly_ust_bps,
                    "curve_date": str(as_of_date),
                }
            )

        self.log.info(
            "spillover_signal_generated",
            z_score=round(z_score, 3),
            spread=round(current_spread, 4),
            direction=direction.value,
            weekly_ust_bps=round(weekly_ust_bps, 2),
        )

        return positions
