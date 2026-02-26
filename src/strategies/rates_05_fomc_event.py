"""RATES_05: FOMC Event Strategy.

Positions around FOMC meetings [-5, +2] business days.  Pre-event: compares
market-implied FFR path (via UST short-end) to a simple Taylor Rule model.
When divergence is significant (|z| >= threshold), takes a directional UST
position.  Post-event: adaptively exits when the divergence z-score reverts
below 0.5.  Outside the FOMC window, returns no signal.

Per locked decision: market pricing only for the expectation baseline --
Fed Funds futures / UST curve.  No survey data.
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
RATES_05_CONFIG = StrategyConfig(
    strategy_id="RATES_05",
    strategy_name="FOMC Event Strategy",
    asset_class=AssetClass.RATES_US,
    instruments=["UST_NOM"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.015,
    take_profit_pct=0.02,
)

# Taylor Rule parameters
_R_STAR = 2.5
_INFLATION_TARGET = 2.0

# FOMC meeting dates (announcement day).
# Comprehensive list covering 2015-2026.
FOMC_DATES: list[date] = [
    # 2015
    date(2015, 1, 28), date(2015, 3, 18), date(2015, 4, 29),
    date(2015, 6, 17), date(2015, 7, 29), date(2015, 9, 17),
    date(2015, 10, 28), date(2015, 12, 16),
    # 2016
    date(2016, 1, 27), date(2016, 3, 16), date(2016, 4, 27),
    date(2016, 6, 15), date(2016, 7, 27), date(2016, 9, 21),
    date(2016, 11, 2), date(2016, 12, 14),
    # 2017
    date(2017, 2, 1), date(2017, 3, 15), date(2017, 5, 3),
    date(2017, 6, 14), date(2017, 7, 26), date(2017, 9, 20),
    date(2017, 11, 1), date(2017, 12, 13),
    # 2018
    date(2018, 1, 31), date(2018, 3, 21), date(2018, 5, 2),
    date(2018, 6, 13), date(2018, 8, 1), date(2018, 9, 26),
    date(2018, 11, 8), date(2018, 12, 19),
    # 2019
    date(2019, 1, 30), date(2019, 3, 20), date(2019, 5, 1),
    date(2019, 6, 19), date(2019, 7, 31), date(2019, 9, 18),
    date(2019, 10, 30), date(2019, 12, 11),
    # 2020
    date(2020, 1, 29), date(2020, 3, 3), date(2020, 3, 15),
    date(2020, 4, 29), date(2020, 6, 10), date(2020, 7, 29),
    date(2020, 9, 16), date(2020, 11, 5), date(2020, 12, 16),
    # 2021
    date(2021, 1, 27), date(2021, 3, 17), date(2021, 4, 28),
    date(2021, 6, 16), date(2021, 7, 28), date(2021, 9, 22),
    date(2021, 11, 3), date(2021, 12, 15),
    # 2022
    date(2022, 1, 26), date(2022, 3, 16), date(2022, 5, 4),
    date(2022, 6, 15), date(2022, 7, 27), date(2022, 9, 21),
    date(2022, 11, 2), date(2022, 12, 14),
    # 2023
    date(2023, 2, 1), date(2023, 3, 22), date(2023, 5, 3),
    date(2023, 6, 14), date(2023, 7, 26), date(2023, 9, 20),
    date(2023, 11, 1), date(2023, 12, 13),
    # 2024
    date(2024, 1, 31), date(2024, 3, 20), date(2024, 5, 1),
    date(2024, 6, 12), date(2024, 7, 31), date(2024, 9, 18),
    date(2024, 11, 7), date(2024, 12, 18),
    # 2025
    date(2025, 1, 29), date(2025, 3, 19), date(2025, 5, 7),
    date(2025, 6, 18), date(2025, 7, 30), date(2025, 9, 17),
    date(2025, 10, 29), date(2025, 12, 17),
    # 2026
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 5, 6),
    date(2026, 6, 17), date(2026, 7, 29), date(2026, 9, 16),
    date(2026, 10, 28), date(2026, 12, 16),
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
    "RATES_05",
    asset_class=AssetClass.RATES_US,
    instruments=["UST_NOM"],
)
class Rates05FomcEventStrategy(BaseStrategy):
    """FOMC event-driven strategy on US Treasuries.

    Positions before FOMC when market-implied FFR path diverges from a
    Taylor Rule model.  Exits adaptively after the event when z-score
    reverts.

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
        super().__init__(config=config or RATES_05_CONFIG)
        self.data_loader = data_loader
        self.entry_z_threshold = entry_z_threshold
        self.exit_z_threshold = exit_z_threshold
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    def _is_fomc_window(self, as_of_date: date) -> tuple[bool, int, date | None]:
        """Check if as_of_date falls within an FOMC event window.

        Window: [-5, +2] business days relative to the FOMC announcement.

        Args:
            as_of_date: Date to check.

        Returns:
            Tuple of (in_window, days_to_fomc, fomc_date).
            days_to_fomc is negative before, positive after.
            Returns (False, 0, None) if outside any window.
        """
        for fomc_date in FOMC_DATES:
            bdays = _business_days_between(as_of_date, fomc_date)
            # bdays > 0 means fomc_date is in the future (pre-event)
            # bdays < 0 means fomc_date is in the past (post-event)
            if -2 <= bdays <= 5:
                # days_to_fomc: positive = days until FOMC, negative = days after
                return True, bdays, fomc_date

        return False, 0, None

    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce signals for FOMC event positioning.

        Pre-event: compare market-implied rate to Taylor rule, z-score
        the divergence.  Post-event: exit if z-score has reverted.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List of StrategySignal, or empty list if outside window or
            data insufficient.
        """
        in_window, days_to_fomc, fomc_date = self._is_fomc_window(as_of_date)
        if not in_window:
            return []

        # Load UST curve for market-implied rate
        ust_curve = self.data_loader.get_curve("UST_NOM", as_of_date)
        if not ust_curve:
            self.log.warning("missing_ust_curve", as_of_date=str(as_of_date))
            return []

        # Extract short-end (2Y) rate as market-implied FFR path proxy
        ust_2y_tenor = min(ust_curve.keys(), key=lambda t: abs(t - 504))
        market_implied = ust_curve[ust_2y_tenor]

        # Taylor Rule model
        us_cpi = self.data_loader.get_latest_macro_value("US_CPI_YOY", as_of_date)
        us_ffr = self.data_loader.get_latest_macro_value("US_FED_FUNDS", as_of_date)

        if us_cpi is None:
            self.log.warning("missing_cpi", as_of_date=str(as_of_date))
            return []

        # Simple Taylor Rule: r* + inflation + 0.5*(inflation - target) + 0.5*output_gap
        # Approximate output_gap from FFR level deviation from neutral
        output_gap_proxy = 0.0
        if us_ffr is not None:
            # If FFR is well below neutral (r_star + inflation), economy may be loose
            neutral = _R_STAR + us_cpi
            output_gap_proxy = max(-2.0, min(2.0, (us_ffr - neutral) * 0.3))

        taylor_rate = (
            _R_STAR
            + us_cpi
            + 0.5 * (us_cpi - _INFLATION_TARGET)
            + 0.5 * output_gap_proxy
        )

        # Divergence
        divergence = market_implied - taylor_rate

        # Build divergence history for z-score
        divergence_history = self._build_divergence_history(as_of_date)
        if len(divergence_history) < 30:
            self.log.warning(
                "short_divergence_history",
                points=len(divergence_history),
            )
            return []

        z_score = self.compute_z_score(divergence, divergence_history, window=504)

        # Post-event adaptive exit (days +1, +2)
        if days_to_fomc < 0:
            # After FOMC: if z has reverted, no signal (exit position)
            if abs(z_score) < self.exit_z_threshold:
                self.log.info(
                    "post_fomc_exit",
                    z_score=round(z_score, 3),
                    days_after=abs(days_to_fomc),
                )
                return []

        # Pre-event entry (or maintaining post-event if z still elevated)
        if abs(z_score) < self.entry_z_threshold:
            return []

        # Direction: divergence > 0 -> market more hawkish than model -> LONG UST
        # divergence < 0 -> market more dovish -> SHORT UST
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
                "market_implied": market_implied,
                "taylor_rate": taylor_rate,
                "divergence": divergence,
                "us_cpi": us_cpi,
                "us_ffr": us_ffr,
                "days_to_fomc": days_to_fomc,
                "fomc_date": str(fomc_date),
                "phase": "pre_event" if days_to_fomc >= 0 else "post_event",
            },
        )

        self.log.info(
            "fomc_signal",
            z_score=round(z_score, 3),
            divergence=round(divergence, 4),
            direction=direction.value,
            days_to_fomc=days_to_fomc,
        )

        return [signal]

    def _build_divergence_history(self, as_of_date: date) -> list[float]:
        """Build history of market-implied vs Taylor Rule divergences.

        Uses UST 2Y curve history and CPI macro series to compute
        historical divergences for z-scoring.

        Args:
            as_of_date: PIT reference date.

        Returns:
            List of divergence values (most recent last).
        """
        ust_hist = self.data_loader.get_curve_history(
            "UST_NOM", 504, as_of_date, lookback_days=756
        )
        cpi_hist = self.data_loader.get_macro_series(
            "US_CPI_YOY", as_of_date, lookback_days=756
        )

        if ust_hist.empty or cpi_hist.empty:
            return []

        # Align on dates
        combined = ust_hist[["rate"]].join(
            cpi_hist[["value"]], how="outer"
        )
        combined = combined.ffill().dropna()

        if combined.empty:
            return []

        divergences = []
        for _, row in combined.iterrows():
            mkt = float(row["rate"])
            cpi = float(row["value"])
            taylor = _R_STAR + cpi + 0.5 * (cpi - _INFLATION_TARGET)
            divergences.append(mkt - taylor)

        return divergences
