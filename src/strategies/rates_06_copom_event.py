"""RATES_06: COPOM Event Strategy.

Positions around COPOM meetings [-5, +2] business days.  Pre-event: compares
DI1-implied Selic move to a simple BCB reaction-function model based on
inflation deviation from target bands.  When divergence is significant,
takes a directional DI position.  Post-event: adaptively exits when the
divergence z-score reverts below 0.5.

Per locked decision: market pricing only for expectation baseline -- DI1
curve for COPOM.  No Focus survey data in the baseline.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import structlog

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection
from src.strategies.base import BaseStrategy, StrategyConfig, StrategySignal
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
RATES_06_CONFIG = StrategyConfig(
    strategy_id="RATES_06",
    strategy_name="COPOM Event Strategy",
    asset_class=AssetClass.RATES_BR,
    instruments=["DI_PRE"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.015,
    take_profit_pct=0.02,
)

# BCB reaction function parameters
_IPCA_UPPER_BAND = 4.5  # Upper target band (%)
_IPCA_LOWER_BAND = 3.0  # Lower target band (%)
_SELIC_MOVE_SIZE = 0.25  # Standard Selic move increment (25bps)

# COPOM meeting dates (announcement day -- typically Wednesday after
# the 2-day meeting).  Comprehensive list covering 2015-2026.
COPOM_DATES: list[date] = [
    # 2015
    date(2015, 1, 21),
    date(2015, 3, 4),
    date(2015, 4, 29),
    date(2015, 6, 3),
    date(2015, 7, 29),
    date(2015, 9, 2),
    date(2015, 10, 21),
    date(2015, 11, 25),
    # 2016
    date(2016, 1, 20),
    date(2016, 3, 2),
    date(2016, 4, 27),
    date(2016, 6, 8),
    date(2016, 7, 20),
    date(2016, 8, 31),
    date(2016, 10, 19),
    date(2016, 11, 30),
    # 2017
    date(2017, 1, 11),
    date(2017, 2, 22),
    date(2017, 4, 12),
    date(2017, 5, 31),
    date(2017, 7, 26),
    date(2017, 9, 6),
    date(2017, 10, 25),
    date(2017, 12, 6),
    # 2018
    date(2018, 2, 7),
    date(2018, 3, 21),
    date(2018, 5, 16),
    date(2018, 6, 20),
    date(2018, 8, 1),
    date(2018, 9, 19),
    date(2018, 10, 31),
    date(2018, 12, 12),
    # 2019
    date(2019, 2, 6),
    date(2019, 3, 20),
    date(2019, 5, 8),
    date(2019, 6, 19),
    date(2019, 7, 31),
    date(2019, 9, 18),
    date(2019, 10, 30),
    date(2019, 12, 11),
    # 2020
    date(2020, 2, 5),
    date(2020, 3, 18),
    date(2020, 5, 6),
    date(2020, 6, 17),
    date(2020, 8, 5),
    date(2020, 9, 16),
    date(2020, 10, 28),
    date(2020, 12, 9),
    # 2021
    date(2021, 1, 20),
    date(2021, 3, 17),
    date(2021, 5, 5),
    date(2021, 6, 16),
    date(2021, 8, 4),
    date(2021, 9, 22),
    date(2021, 10, 27),
    date(2021, 12, 8),
    # 2022
    date(2022, 2, 2),
    date(2022, 3, 16),
    date(2022, 5, 4),
    date(2022, 6, 15),
    date(2022, 8, 3),
    date(2022, 9, 21),
    date(2022, 10, 26),
    date(2022, 12, 7),
    # 2023
    date(2023, 2, 1),
    date(2023, 3, 22),
    date(2023, 5, 3),
    date(2023, 6, 21),
    date(2023, 8, 2),
    date(2023, 9, 20),
    date(2023, 11, 1),
    date(2023, 12, 13),
    # 2024
    date(2024, 1, 31),
    date(2024, 3, 20),
    date(2024, 5, 8),
    date(2024, 6, 19),
    date(2024, 7, 31),
    date(2024, 9, 18),
    date(2024, 11, 6),
    date(2024, 12, 11),
    # 2025
    date(2025, 1, 29),
    date(2025, 3, 19),
    date(2025, 5, 7),
    date(2025, 6, 18),
    date(2025, 7, 30),
    date(2025, 9, 17),
    date(2025, 10, 29),
    date(2025, 12, 10),
    # 2026
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 5, 6),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
]


def _business_days_between(d1: date, d2: date) -> int:
    """Count business days between two dates (signed).

    Positive if d2 > d1.  Excludes weekends but not holidays.

    Args:
        d1: Start date.
        d2: End date.

    Returns:
        Signed count of business days.
    """
    if d1 == d2:
        return 0
    sign = 1 if d2 > d1 else -1
    start, end = min(d1, d2), max(d1, d2)
    count = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count * sign


@StrategyRegistry.register(
    "RATES_06",
    asset_class=AssetClass.RATES_BR,
    instruments=["DI_PRE"],
)
class Rates06CopomEventStrategy(BaseStrategy):
    """COPOM event-driven strategy on BR DI curve.

    Positions before COPOM when DI1-implied Selic move diverges from a
    BCB reaction-function model.  Exits adaptively after the event when
    z-score reverts.

    Args:
        data_loader: PointInTimeDataLoader for fetching curve and macro data.
        entry_z_threshold: Minimum |z| during pre-event window (default 1.0).
        exit_z_threshold: Z below which post-event exit triggers (default 0.5).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        entry_z_threshold: float = 1.0,
        exit_z_threshold: float = 0.5,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or RATES_06_CONFIG)
        self.data_loader = data_loader
        self.entry_z_threshold = entry_z_threshold
        self.exit_z_threshold = exit_z_threshold
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    def _is_copom_window(self, as_of_date: date) -> tuple[bool, int, date | None]:
        """Check if as_of_date falls within a COPOM event window.

        Window: [-5, +2] business days relative to COPOM announcement.

        Args:
            as_of_date: Date to check.

        Returns:
            Tuple of (in_window, days_to_copom, copom_date).
            days_to_copom is negative after the meeting, positive before.
            Returns (False, 0, None) if outside any window.
        """
        for copom_date in COPOM_DATES:
            bdays = _business_days_between(as_of_date, copom_date)
            # bdays > 0 means copom_date is in the future (pre-event)
            # bdays < 0 means copom_date is in the past (post-event)
            if -2 <= bdays <= 5:
                return True, bdays, copom_date

        return False, 0, None

    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce signals for COPOM event positioning.

        Pre-event: compare DI1-implied Selic move to BCB reaction function.
        Post-event: exit if z-score has reverted below threshold.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List of StrategySignal, or empty list if outside window or
            data insufficient.
        """
        in_window, days_to_copom, copom_date = self._is_copom_window(as_of_date)
        if not in_window:
            return []

        # Load DI curve for market-implied Selic move
        di_curve = self.data_loader.get_curve("DI_PRE", as_of_date)
        if not di_curve:
            self.log.warning("missing_di_curve", as_of_date=str(as_of_date))
            return []

        # Extract short-end rate (closest to 30 days or shortest available)
        di_short_tenor = min(di_curve.keys(), key=lambda t: abs(t - 30))
        di_short_rate = di_curve[di_short_tenor]

        # Current Selic
        current_selic = self.data_loader.get_latest_macro_value(
            "BR_SELIC_TARGET", as_of_date
        )
        if current_selic is None:
            self.log.warning("missing_selic", as_of_date=str(as_of_date))
            return []

        # DI-implied Selic move (annualized rate difference)
        di_implied_move = di_short_rate - current_selic

        # BCB reaction function model
        model_implied_move = self._bcb_reaction_function(as_of_date)
        if model_implied_move is None:
            return []

        # Divergence
        divergence = di_implied_move - model_implied_move

        # Build divergence history for z-score
        divergence_history = self._build_divergence_history(as_of_date)
        if len(divergence_history) < 30:
            self.log.warning(
                "short_divergence_history",
                points=len(divergence_history),
            )
            return []

        z_score = self.compute_z_score(divergence, divergence_history, window=252)

        # Post-event adaptive exit (days_to_copom < 0 means after COPOM)
        if days_to_copom < 0:
            if abs(z_score) < self.exit_z_threshold:
                self.log.info(
                    "post_copom_exit",
                    z_score=round(z_score, 3),
                    days_after=abs(days_to_copom),
                )
                return []

        # Entry threshold
        if abs(z_score) < self.entry_z_threshold:
            return []

        # Direction: divergence > 0 -> DI pricing more hawkish than model
        # -> expect dovish surprise -> LONG DI (rates fall)
        # divergence < 0 -> DI pricing more dovish -> SHORT DI
        if z_score > 0:
            direction = SignalDirection.LONG
        else:
            direction = SignalDirection.SHORT

        strength = self.classify_strength(z_score)
        confidence = min(1.0, abs(z_score) / (self.entry_z_threshold * 3))
        suggested_size = self.size_from_conviction(
            z_score, max_size=self.config.max_position_size
        )

        signal = StrategySignal(
            strategy_id=self.config.strategy_id,
            timestamp=datetime.utcnow(),
            direction=direction,
            strength=strength,
            confidence=confidence,
            z_score=z_score,
            raw_value=divergence,
            suggested_size=suggested_size,
            asset_class=self.config.asset_class,
            instruments=self.config.instruments,
            stop_loss=self.config.stop_loss_pct,
            take_profit=self.config.take_profit_pct,
            holding_period_days=7,
            metadata={
                "di_short_rate": di_short_rate,
                "current_selic": current_selic,
                "di_implied_move": di_implied_move,
                "model_implied_move": model_implied_move,
                "divergence": divergence,
                "days_to_copom": days_to_copom,
                "copom_date": str(copom_date),
                "phase": "pre_event" if days_to_copom >= 0 else "post_event",
            },
        )

        self.log.info(
            "copom_signal",
            z_score=round(z_score, 3),
            divergence=round(divergence, 4),
            direction=direction.value,
            days_to_copom=days_to_copom,
        )

        return [signal]

    def _bcb_reaction_function(self, as_of_date: date) -> float | None:
        """Compute a simple BCB reaction-function estimate of the next Selic move.

        Uses IPCA 12-month inflation vs target band:
        - IPCA > upper band (4.5%) -> model expects hike (+25bps = +0.25%)
        - IPCA < lower band (3.0%) -> model expects cut (-25bps = -0.25%)
        - Otherwise -> neutral (0%)

        This is deliberately simple; the alpha comes from comparing this
        to what DI1 is pricing.

        Args:
            as_of_date: PIT reference date.

        Returns:
            Model-implied Selic move in percentage points, or None if
            inflation data is unavailable.
        """
        ipca_12m = self.data_loader.get_latest_macro_value("BR_IPCA_12M", as_of_date)
        if ipca_12m is None:
            self.log.warning("missing_ipca", as_of_date=str(as_of_date))
            return None

        if ipca_12m > _IPCA_UPPER_BAND:
            return _SELIC_MOVE_SIZE  # Expect hike
        elif ipca_12m < _IPCA_LOWER_BAND:
            return -_SELIC_MOVE_SIZE  # Expect cut
        else:
            return 0.0  # Neutral

    def _build_divergence_history(self, as_of_date: date) -> list[float]:
        """Build history of DI-implied vs model divergences.

        Uses DI short-end curve history and Selic / IPCA macro series
        to compute historical divergences for z-scoring.

        Args:
            as_of_date: PIT reference date.

        Returns:
            List of divergence values (most recent last).
        """
        # Use 30-day DI tenor history
        di_hist = self.data_loader.get_curve_history(
            "DI_PRE", 30, as_of_date, lookback_days=504
        )
        selic_hist = self.data_loader.get_macro_series(
            "BR_SELIC_TARGET", as_of_date, lookback_days=504
        )
        ipca_hist = self.data_loader.get_macro_series(
            "BR_IPCA_12M", as_of_date, lookback_days=504
        )

        if di_hist.empty or selic_hist.empty or ipca_hist.empty:
            return []

        # Align
        combined = (
            di_hist[["rate"]]
            .join(
                selic_hist[["value"]].rename(columns={"value": "selic"}),
                how="outer",
            )
            .join(
                ipca_hist[["value"]].rename(columns={"value": "ipca"}),
                how="outer",
            )
        )
        combined = combined.ffill().dropna()

        if combined.empty:
            return []

        divergences = []
        for _, row in combined.iterrows():
            di_rate = float(row["rate"])
            selic = float(row["selic"])
            ipca = float(row["ipca"])

            di_implied = di_rate - selic

            if ipca > _IPCA_UPPER_BAND:
                model = _SELIC_MOVE_SIZE
            elif ipca < _IPCA_LOWER_BAND:
                model = -_SELIC_MOVE_SIZE
            else:
                model = 0.0

            divergences.append(di_implied - model)

        return divergences
