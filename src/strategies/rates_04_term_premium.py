"""RATES_04: Term Premium Extraction strategy.

Estimates the term premium as DI(n) minus the Focus-consensus expected
short rate path.  When the term premium is elevated relative to history
(high z-score), the strategy expects compression and goes LONG DI.
When compressed (low z-score), goes SHORT DI.

Uses 2Y and 5Y DI tenors with Focus Selic median expectations as the
model for the expected short-rate path.
"""

from __future__ import annotations

from datetime import date, datetime

import structlog

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection
from src.core.utils.tenors import find_closest_tenor
from src.strategies.base import BaseStrategy, StrategyConfig, StrategySignal
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
RATES_04_CONFIG = StrategyConfig(
    strategy_id="RATES_04",
    strategy_name="Term Premium Extraction",
    asset_class=AssetClass.RATES_BR,
    instruments=["DI_PRE"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.015,
    take_profit_pct=0.025,
)

_2Y_TENOR = 504
_5Y_TENOR = 1260
_TENOR_TOLERANCE = 10000  # large to replicate "find closest" behavior
_TP_LOOKBACK = 252  # 1 year for z-score


@StrategyRegistry.register(
    "RATES_04",
    asset_class=AssetClass.RATES_BR,
    instruments=["DI_PRE"],
)
class Rates04TermPremiumStrategy(BaseStrategy):
    """Term premium extraction strategy on the BR DI curve.

    Estimates term premium as DI(n) minus Focus Selic median expectation.
    Trades mean-reversion of the z-scored term premium.

    Args:
        data_loader: PointInTimeDataLoader for fetching curve and macro data.
        entry_z_threshold: Minimum |z| for term premium to trigger entry
            (default 1.5).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        entry_z_threshold: float = 1.5,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or RATES_04_CONFIG)
        self.data_loader = data_loader
        self.entry_z_threshold = entry_z_threshold
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce signals based on term premium z-score mean reversion.

        Steps:
            1. Load DI curve and extract 2Y, 5Y rates.
            2. Load Focus Selic median expectation.
            3. Compute term premium = DI_tenor - Focus_Selic_avg.
            4. Build TP history and z-score.
            5. Return StrategySignal if |z| >= threshold.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List of StrategySignal, or empty list if data insufficient.
        """
        # 1. Load DI curve
        di_curve = self.data_loader.get_curve("DI_PRE", as_of_date)
        if not di_curve:
            self.log.warning("missing_di_curve", as_of_date=str(as_of_date))
            return []

        # Find closest tenors
        di_2y_tenor = find_closest_tenor(di_curve, _2Y_TENOR, _TENOR_TOLERANCE)
        di_5y_tenor = find_closest_tenor(di_curve, _5Y_TENOR, _TENOR_TOLERANCE)

        if di_2y_tenor is None or di_5y_tenor is None:
            self.log.warning("tenor_not_found", as_of_date=str(as_of_date))
            return []

        di_2y = di_curve[di_2y_tenor]
        di_5y = di_curve[di_5y_tenor]

        # 2. Load Focus Selic expectations
        focus_df = self.data_loader.get_focus_expectations("SELIC", as_of_date)
        if focus_df.empty:
            self.log.warning("missing_focus_data", as_of_date=str(as_of_date))
            return []

        # Focus Selic median = average expected Selic path
        focus_selic_avg = float(focus_df["value"].iloc[-1])

        # 3. Compute term premium
        tp_2y = di_2y - focus_selic_avg
        tp_5y = di_5y - focus_selic_avg

        # 4. Build TP history
        di_2y_hist = self.data_loader.get_curve_history(
            "DI_PRE", di_2y_tenor, as_of_date, lookback_days=504
        )
        focus_hist = self.data_loader.get_focus_expectations("SELIC", as_of_date)

        if di_2y_hist.empty or focus_hist.empty:
            self.log.warning("insufficient_history", as_of_date=str(as_of_date))
            return []

        tp_history = self._build_tp_history(di_2y_hist, focus_hist)
        if len(tp_history) < 30:
            self.log.warning(
                "short_tp_history",
                points=len(tp_history),
                as_of_date=str(as_of_date),
            )
            return []

        # Z-score of current 2Y TP
        tp_z = self.compute_z_score(tp_2y, tp_history, window=_TP_LOOKBACK)

        # 5. Signal generation
        if abs(tp_z) < self.entry_z_threshold:
            return []

        # Direction: TP z > 0 -> premium elevated -> expect compression -> LONG DI
        # TP z < 0 -> premium compressed -> expect expansion -> SHORT DI
        if tp_z > 0:
            direction = SignalDirection.LONG
        else:
            direction = SignalDirection.SHORT

        strength = self.classify_strength(tp_z)
        confidence = min(1.0, abs(tp_z) / (self.entry_z_threshold * 2.5))
        suggested_size = self.size_from_conviction(
            tp_z, max_size=self.config.max_position_size
        )

        signal = StrategySignal(
            strategy_id=self.config.strategy_id,
            timestamp=datetime.utcnow(),
            direction=direction,
            strength=strength,
            confidence=confidence,
            z_score=tp_z,
            raw_value=tp_2y,
            suggested_size=suggested_size,
            asset_class=self.config.asset_class,
            instruments=self.config.instruments,
            stop_loss=self.config.stop_loss_pct,
            take_profit=self.config.take_profit_pct,
            holding_period_days=28,
            metadata={
                "tp_2y": tp_2y,
                "tp_5y": tp_5y,
                "di_2y": di_2y,
                "di_5y": di_5y,
                "focus_selic_avg": focus_selic_avg,
                "tp_z": tp_z,
                "di_2y_tenor": di_2y_tenor,
            },
        )

        self.log.info(
            "term_premium_signal",
            tp_z=round(tp_z, 3),
            tp_2y=round(tp_2y, 4),
            direction=direction.value,
        )

        return [signal]

    @staticmethod
    def _build_tp_history(
        di_hist,
        focus_hist,
    ) -> list[float]:
        """Build term premium history from DI rate and Focus Selic histories.

        Aligns the two DataFrames on date, forward-fills, computes
        TP = DI_rate - Focus_Selic at each date.

        Args:
            di_hist: DataFrame with 'rate' column for DI tenor.
            focus_hist: DataFrame with 'value' column for Focus Selic.

        Returns:
            List of term premium values (most recent last).
        """
        combined = di_hist[["rate"]].join(
            focus_hist[["value"]], how="outer"
        )
        combined = combined.ffill().dropna()
        if combined.empty:
            return []
        tp_series = combined["rate"] - combined["value"]
        return tp_series.tolist()
