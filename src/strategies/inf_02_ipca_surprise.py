"""INF_02: IPCA Surprise Trade strategy.

Trades NTN-Bs and breakevens around IPCA/IPCA-15 releases when the model
forecast (seasonal model or IPCA-15 preview) diverges from the Focus consensus.

Model forecast logic:
    1. If IPCA-15 (preview) is available for the current month, use it
       as the model forecast (it is a leading indicator of the full IPCA).
    2. Otherwise, compute a seasonal average for the current month from
       the past 5 years of IPCA monthly readings.

Trade direction:
    - surprise_z > 0 (model expects higher than Focus): upside inflation
      surprise expected => SHORT NTN-Bs (real rates rise) / SHORT breakevens.
    - surprise_z < 0 (model expects lower than Focus): downside inflation
      surprise => LONG NTN-Bs (real rates fall) / LONG breakevens.

Entry is restricted to the IPCA release window ([-3, +2] business days around
the ~10th of each month), with a carryover window of up to 14 days if the
most recent surprise z-score remains extreme (|z| > 1.5).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import structlog

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection
from src.strategies.base import BaseStrategy, StrategyConfig, StrategySignal
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
INF_02_CONFIG = StrategyConfig(
    strategy_id="INF_02",
    strategy_name="IPCA Surprise Trade",
    asset_class=AssetClass.INFLATION_BR,
    instruments=["NTN_B_REAL", "DI_PRE"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.015,
    take_profit_pct=0.025,
)

# IPCA release calendar: typically around the 10th of each month
_IPCA_RELEASE_DAY = 10
# Window around release: [-3, +2] business days
_PRE_RELEASE_DAYS = 3
_POST_RELEASE_DAYS = 2
# How long to hold if surprise remains extreme post-release
_POST_RELEASE_CARRYOVER_DAYS = 14
# Extreme z-score threshold for carryover
_EXTREME_Z_THRESHOLD = 1.5
# Entry z-score threshold
_ENTRY_Z_THRESHOLD = 1.0
# Lookback for seasonal model (5 years)
_SEASONAL_LOOKBACK_DAYS = 1825
# Lookback for surprise history (24+ months)
_SURPRISE_LOOKBACK_MONTHS = 24
# Holding period
_HOLDING_PERIOD_DAYS = 14


@StrategyRegistry.register(
    "INF_02",
    asset_class=AssetClass.INFLATION_BR,
    instruments=["NTN_B_REAL", "DI_PRE"],
)
class Inf02IpcaSurpriseStrategy(BaseStrategy):
    """IPCA Surprise Trade strategy.

    Trades NTN-Bs and breakevens around IPCA releases when the model
    forecast diverges from the Focus consensus.

    Args:
        data_loader: PointInTimeDataLoader for fetching macro data.
        entry_z_threshold: Minimum |z-score| to trigger entry (default 1.0).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        entry_z_threshold: float = _ENTRY_Z_THRESHOLD,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or INF_02_CONFIG)
        self.data_loader = data_loader
        self.entry_z_threshold = entry_z_threshold
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Main signal generation
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Generate signals based on IPCA surprise analysis.

        Steps:
            1. Build model IPCA forecast (IPCA-15 or seasonal average).
            2. Load Focus consensus forecast.
            3. Compute surprise z-score from divergence history.
            4. Check IPCA release window / carryover.
            5. Generate signal if within window and z-score exceeds threshold.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List of StrategySignal objects, or empty list if data is
            missing or conditions are not met.
        """
        # 1. Build model IPCA forecast
        model_forecast = self._build_model_forecast(as_of_date)
        if model_forecast is None:
            self.log.warning("missing_model_forecast", as_of_date=str(as_of_date))
            return []

        # 2. Load Focus consensus
        focus_df = self.data_loader.get_focus_expectations("IPCA", as_of_date)
        if focus_df.empty:
            self.log.warning("missing_focus_expectations", as_of_date=str(as_of_date))
            return []

        focus_median = float(focus_df["value"].iloc[-1])

        # 3. Compute surprise z-score
        surprise_z = self._compute_surprise_z(
            model_forecast,
            focus_median,
            as_of_date,
        )
        if surprise_z is None:
            self.log.warning(
                "insufficient_surprise_history", as_of_date=str(as_of_date)
            )
            return []

        # 4. Check IPCA release window
        near_release = self._near_ipca_release(as_of_date)
        in_carryover = not near_release and abs(surprise_z) > _EXTREME_Z_THRESHOLD

        if not near_release and not in_carryover:
            self.log.debug(
                "outside_ipca_window",
                surprise_z=round(surprise_z, 3),
                as_of_date=str(as_of_date),
            )
            return []

        # 5. Check entry threshold
        if abs(surprise_z) < self.entry_z_threshold:
            self.log.debug(
                "below_entry_threshold",
                surprise_z=round(surprise_z, 3),
                threshold=self.entry_z_threshold,
            )
            return []

        # 6. Determine direction
        # surprise_z > 0: model expects higher inflation than Focus
        #   => upside surprise => SHORT NTN-Bs (real rates rise)
        # surprise_z < 0: model expects lower => LONG NTN-Bs
        if surprise_z > 0:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.LONG

        strength = self.classify_strength(surprise_z)
        confidence = min(1.0, abs(surprise_z) / 3.0)
        suggested_size = self.size_from_conviction(surprise_z)

        signal = StrategySignal(
            strategy_id=self.strategy_id,
            timestamp=datetime.utcnow(),
            direction=direction,
            strength=strength,
            confidence=confidence,
            z_score=surprise_z,
            raw_value=model_forecast - focus_median,
            suggested_size=suggested_size,
            asset_class=AssetClass.INFLATION_BR,
            instruments=self.config.instruments,
            stop_loss=self.config.stop_loss_pct,
            take_profit=self.config.take_profit_pct,
            holding_period_days=_HOLDING_PERIOD_DAYS,
            metadata={
                "model_forecast": model_forecast,
                "focus_median": focus_median,
                "surprise_z": surprise_z,
                "near_release": near_release,
                "in_carryover": in_carryover,
                "as_of_date": str(as_of_date),
            },
        )

        self.log.info(
            "ipca_surprise_signal",
            direction=direction.value,
            surprise_z=round(surprise_z, 3),
            model_forecast=round(model_forecast, 4),
            focus_median=round(focus_median, 4),
            confidence=round(confidence, 3),
        )

        return [signal]

    # ------------------------------------------------------------------
    # Model forecast: IPCA-15 or seasonal average
    # ------------------------------------------------------------------
    def _build_model_forecast(self, as_of_date: date) -> float | None:
        """Build model IPCA forecast for the current month.

        Priority:
            1. IPCA-15 (preview) for the current month, if available.
            2. Seasonal average for the current month from 5 years of history.

        Args:
            as_of_date: Reference date.

        Returns:
            Model forecast value, or None if insufficient data.
        """
        # Try IPCA-15 first
        ipca15 = self.data_loader.get_latest_macro_value(
            "BR_IPCA15_MOM",
            as_of_date,
        )
        if ipca15 is not None:
            return ipca15

        # Fall back to seasonal average
        ipca_df = self.data_loader.get_macro_series(
            "BR_IPCA_MOM",
            as_of_date,
            lookback_days=_SEASONAL_LOOKBACK_DAYS,
        )
        if ipca_df.empty:
            return None

        # Filter to same month as as_of_date
        current_month = as_of_date.month
        same_month = ipca_df[ipca_df.index.month == current_month]

        if same_month.empty:
            return None

        seasonal_avg = float(same_month["value"].mean())
        return seasonal_avg

    # ------------------------------------------------------------------
    # Surprise z-score computation
    # ------------------------------------------------------------------
    def _compute_surprise_z(
        self,
        model_forecast: float,
        focus_median: float,
        as_of_date: date,
    ) -> float | None:
        """Compute z-score of the model-Focus divergence.

        Builds a history of (actual IPCA - Focus forecast) surprises over
        24+ months, computes std of those surprises, and z-scores the
        current divergence.

        Args:
            model_forecast: Model's IPCA forecast.
            focus_median: Focus consensus IPCA forecast.
            as_of_date: Reference date.

        Returns:
            Z-score float, or None if insufficient history.
        """
        # Load IPCA actuals for surprise history
        ipca_df = self.data_loader.get_macro_series(
            "BR_IPCA_MOM",
            as_of_date,
            lookback_days=_SEASONAL_LOOKBACK_DAYS,
        )
        if ipca_df.empty or len(ipca_df) < _SURPRISE_LOOKBACK_MONTHS:
            return None

        # Load Focus history for surprise computation
        focus_df = self.data_loader.get_focus_expectations(
            "IPCA",
            as_of_date,
            lookback_days=_SEASONAL_LOOKBACK_DAYS,
        )
        if focus_df.empty or len(focus_df) < _SURPRISE_LOOKBACK_MONTHS:
            return None

        # Compute historical surprises: actual - focus
        # Align by merging on nearest dates
        ipca_vals = ipca_df["value"].tail(_SURPRISE_LOOKBACK_MONTHS * 2)
        focus_vals = focus_df["value"].tail(_SURPRISE_LOOKBACK_MONTHS * 2)

        # Simple approach: compute surprises from available paired data
        # Use inner join on date index
        combined = ipca_vals.to_frame("actual").join(
            focus_vals.to_frame("focus"),
            how="inner",
        )

        if len(combined) < 6:
            # Not enough paired data; use IPCA variability as fallback
            surprises_std = float(ipca_vals.std())
        else:
            surprises = combined["actual"] - combined["focus"]
            surprises_std = float(surprises.std())

        if surprises_std <= 0 or math.isnan(surprises_std):
            return None

        current_divergence = model_forecast - focus_median
        z_score = current_divergence / surprises_std

        return z_score

    # ------------------------------------------------------------------
    # IPCA release window detection
    # ------------------------------------------------------------------
    def _near_ipca_release(self, as_of_date: date) -> bool:
        """Check if as_of_date is within the IPCA release window.

        The IPCA is typically released around the 10th of each month.
        Window: [-3, +2] business days around the estimated release.

        Args:
            as_of_date: Date to check.

        Returns:
            True if within the release window.
        """
        # Estimate release date for current month
        year, month = as_of_date.year, as_of_date.month
        estimated_release = date(year, month, _IPCA_RELEASE_DAY)

        # Adjust if estimated_release falls on weekend
        while estimated_release.weekday() >= 5:  # Saturday=5, Sunday=6
            estimated_release += timedelta(days=1)

        # Compute business day distance
        delta_days = (as_of_date - estimated_release).days

        # Simple business-day approximation
        if delta_days >= 0:
            bdays_after = (
                sum(
                    1
                    for d in range(delta_days + 1)
                    if (estimated_release + timedelta(days=d)).weekday() < 5
                )
                - 1
            )  # subtract 1 because day 0 = release day itself
        else:
            bdays_before = sum(
                1
                for d in range(-delta_days)
                if (estimated_release - timedelta(days=d + 1)).weekday() < 5
            )
            bdays_after = -bdays_before

        return -_PRE_RELEASE_DAYS <= bdays_after <= _POST_RELEASE_DAYS
