"""Tests for SignalMonitor -- flip detection, surge detection, divergence, and daily summary.

Covers:
- Flip detection: sign change in conviction -> flip detected
- No flip when both same sign but different magnitude
- Conviction surge: change > 0.3 triggers, change of 0.2 does not
- Strategy divergence: same-asset-class pair disagreeing by >0.5 flagged
- Divergence not flagged for cross-asset-class pairs
- Daily summary includes all active signals, grouped correctly
- Weekly flip count tracks flips over 7 days
- Empty signals produce valid but empty summary
"""

from datetime import date, datetime, timedelta

import pytest

from src.core.enums import AssetClass, SignalDirection, SignalStrength
from src.portfolio.signal_aggregator_v2 import AggregatedSignalV2
from src.portfolio.signal_monitor import (
    ConvictionSurge,
    DailySignalSummary,
    SignalFlip,
    SignalMonitor,
    StrategyDivergence,
)
from src.strategies.base import StrategySignal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_agg_signal(
    instrument: str,
    conviction: float,
    confidence: float = 0.8,
    strategy_id: str = "RATES_BR_01",
    method: str = "bayesian",
) -> AggregatedSignalV2:
    """Create an AggregatedSignalV2 with sensible defaults."""
    if conviction > 0.05:
        direction = SignalDirection.LONG
    elif conviction < -0.05:
        direction = SignalDirection.SHORT
    else:
        direction = SignalDirection.NEUTRAL

    return AggregatedSignalV2(
        instrument=instrument,
        direction=direction,
        conviction=conviction,
        confidence=confidence,
        method=method,
        contributing_strategies=[{
            "strategy_id": strategy_id,
            "raw_signal": conviction,
            "weight": confidence,
            "staleness_days": 0,
        }],
    )


def _make_strategy_signal(
    strategy_id: str,
    z_score: float,
    confidence: float = 0.8,
    instruments: list[str] | None = None,
    asset_class: AssetClass = AssetClass.FIXED_INCOME,
) -> StrategySignal:
    """Create a StrategySignal with sensible defaults."""
    if instruments is None:
        instruments = ["DI_PRE"]

    direction = SignalDirection.LONG if z_score > 0 else (
        SignalDirection.SHORT if z_score < 0 else SignalDirection.NEUTRAL
    )
    strength = (
        SignalStrength.STRONG if abs(z_score) >= 2.0
        else SignalStrength.MODERATE if abs(z_score) >= 1.0
        else SignalStrength.WEAK if abs(z_score) >= 0.5
        else SignalStrength.NO_SIGNAL
    )

    return StrategySignal(
        strategy_id=strategy_id,
        timestamp=datetime.utcnow(),
        direction=direction,
        strength=strength,
        confidence=confidence,
        z_score=z_score,
        raw_value=z_score,
        suggested_size=abs(z_score) / 2.0,
        asset_class=asset_class,
        instruments=instruments,
    )


# ---------------------------------------------------------------------------
# Test: flip detection
# ---------------------------------------------------------------------------
class TestFlipDetection:
    def test_positive_to_negative_flip(self):
        """Signal going from positive to negative conviction should be detected."""
        monitor = SignalMonitor()
        prev = [_make_agg_signal("DI_PRE", conviction=0.5)]
        curr = [_make_agg_signal("DI_PRE", conviction=-0.3)]

        flips = monitor.check_signal_flips(prev, curr)
        assert len(flips) == 1
        assert flips[0].instrument == "DI_PRE"
        assert flips[0].previous_direction == SignalDirection.LONG
        assert flips[0].current_direction == SignalDirection.SHORT

    def test_negative_to_positive_flip(self):
        """Signal going from negative to positive conviction should be detected."""
        monitor = SignalMonitor()
        prev = [_make_agg_signal("USDBRL", conviction=-0.4)]
        curr = [_make_agg_signal("USDBRL", conviction=0.3)]

        flips = monitor.check_signal_flips(prev, curr)
        assert len(flips) == 1
        assert flips[0].previous_direction == SignalDirection.SHORT
        assert flips[0].current_direction == SignalDirection.LONG

    def test_no_flip_same_sign_different_magnitude(self):
        """No flip when both signals have same sign but different magnitude."""
        monitor = SignalMonitor()
        prev = [_make_agg_signal("DI_PRE", conviction=0.5)]
        curr = [_make_agg_signal("DI_PRE", conviction=0.2)]

        flips = monitor.check_signal_flips(prev, curr)
        assert len(flips) == 0

    def test_flip_to_neutral(self):
        """Transition to zero/neutral should be flagged as a flip."""
        monitor = SignalMonitor()
        prev = [_make_agg_signal("DI_PRE", conviction=0.5)]
        curr = [_make_agg_signal("DI_PRE", conviction=0.0)]

        flips = monitor.check_signal_flips(prev, curr)
        assert len(flips) == 1

    def test_no_flip_for_new_instrument(self):
        """New instrument (not in previous) should not produce a flip."""
        monitor = SignalMonitor()
        prev = [_make_agg_signal("DI_PRE", conviction=0.5)]
        curr = [_make_agg_signal("USDBRL", conviction=-0.3)]

        flips = monitor.check_signal_flips(prev, curr)
        assert len(flips) == 0


# ---------------------------------------------------------------------------
# Test: conviction surge
# ---------------------------------------------------------------------------
class TestConvictionSurge:
    def test_surge_above_threshold(self):
        """Change > 0.3 should trigger a surge."""
        monitor = SignalMonitor(surge_threshold=0.3)
        prev = [_make_agg_signal("DI_PRE", conviction=0.1)]
        curr = [_make_agg_signal("DI_PRE", conviction=0.5)]

        surges = monitor.check_conviction_surge(prev, curr)
        assert len(surges) == 1
        assert surges[0].instrument == "DI_PRE"
        assert abs(surges[0].absolute_change - 0.4) < 1e-9

    def test_no_surge_below_threshold(self):
        """Change of 0.2 should NOT trigger a surge (threshold is 0.3)."""
        monitor = SignalMonitor(surge_threshold=0.3)
        prev = [_make_agg_signal("DI_PRE", conviction=0.1)]
        curr = [_make_agg_signal("DI_PRE", conviction=0.3)]

        surges = monitor.check_conviction_surge(prev, curr)
        assert len(surges) == 0

    def test_surge_negative_direction(self):
        """Large negative change should also trigger a surge."""
        monitor = SignalMonitor(surge_threshold=0.3)
        prev = [_make_agg_signal("DI_PRE", conviction=0.4)]
        curr = [_make_agg_signal("DI_PRE", conviction=-0.1)]

        surges = monitor.check_conviction_surge(prev, curr)
        assert len(surges) == 1
        assert surges[0].absolute_change == 0.5


# ---------------------------------------------------------------------------
# Test: strategy divergence
# ---------------------------------------------------------------------------
class TestStrategyDivergence:
    def test_divergence_within_asset_class(self):
        """Two same-asset-class strategies disagreeing by >0.5 should be flagged."""
        monitor = SignalMonitor(divergence_threshold=0.5)
        signals = [
            _make_strategy_signal("RATES_BR_01", z_score=1.5, instruments=["DI_PRE"]),
            _make_strategy_signal("INF_BR_01", z_score=-1.0, instruments=["NTN_B"]),
        ]
        # Both RATES_ and INF_ map to FIXED_INCOME
        # conviction_a = 1.5/2 = 0.75, conviction_b = -1.0/2 = -0.5
        # divergence = |0.75 - (-0.5)| = 1.25 > 0.5

        divs = monitor.check_strategy_divergence(signals)
        assert len(divs) == 1
        assert divs[0].asset_class == "FIXED_INCOME"
        assert divs[0].divergence > 0.5

    def test_no_divergence_cross_asset_class(self):
        """Strategies in different asset classes should NOT be compared."""
        monitor = SignalMonitor(divergence_threshold=0.5)
        signals = [
            _make_strategy_signal("RATES_BR_01", z_score=2.0, instruments=["DI_PRE"]),
            _make_strategy_signal("FX_BR_01", z_score=-2.0, instruments=["USDBRL"]),
        ]
        # RATES_ -> FIXED_INCOME, FX_ -> FX (different classes)

        divs = monitor.check_strategy_divergence(signals)
        assert len(divs) == 0

    def test_no_divergence_below_threshold(self):
        """Strategies agreeing within threshold should not be flagged."""
        monitor = SignalMonitor(divergence_threshold=0.5)
        signals = [
            _make_strategy_signal("RATES_BR_01", z_score=1.0, instruments=["DI_PRE"]),
            _make_strategy_signal("RATES_BR_02", z_score=0.8, instruments=["DI_PRE"]),
        ]
        # conviction_a = 0.5, conviction_b = 0.4 => divergence = 0.1 < 0.5

        divs = monitor.check_strategy_divergence(signals)
        assert len(divs) == 0

    def test_divergence_names_strategies(self):
        """Divergence should name the specific conflicting strategies."""
        monitor = SignalMonitor(divergence_threshold=0.5)
        signals = [
            _make_strategy_signal("RATES_BR_01", z_score=2.0, instruments=["DI_PRE"]),
            _make_strategy_signal("INF_BR_01", z_score=-2.0, instruments=["NTN_B"]),
        ]

        divs = monitor.check_strategy_divergence(signals)
        assert len(divs) == 1
        assert "INF_BR_01" in (divs[0].strategy_a, divs[0].strategy_b)
        assert "RATES_BR_01" in (divs[0].strategy_a, divs[0].strategy_b)


# ---------------------------------------------------------------------------
# Test: daily summary
# ---------------------------------------------------------------------------
class TestDailySummary:
    def test_includes_all_active_signals(self):
        """Summary should include all non-zero conviction signals."""
        monitor = SignalMonitor()
        current = [
            _make_agg_signal("DI_PRE", conviction=0.45, strategy_id="RATES_BR_01"),
            _make_agg_signal("USDBRL", conviction=0.62, strategy_id="FX_BR_01"),
        ]
        raw = [
            _make_strategy_signal("RATES_BR_01", z_score=0.9),
            _make_strategy_signal("FX_BR_01", z_score=1.2, instruments=["USDBRL"]),
        ]

        summary = monitor.generate_daily_summary(
            current, raw, regime="Goldilocks",
        )

        assert summary.date == date.today()
        assert summary.regime_context == "Goldilocks"
        assert len(summary.active_signals) >= 1

        # Check signals are present in groups
        all_instruments = []
        for group in summary.active_signals:
            for sig in group["signals"]:
                all_instruments.append(sig["instrument"])
        assert "DI_PRE" in all_instruments
        assert "USDBRL" in all_instruments

    def test_grouped_by_asset_class(self):
        """Signals should be grouped by asset class in summary."""
        monitor = SignalMonitor()
        current = [
            _make_agg_signal("DI_PRE", conviction=0.4, strategy_id="RATES_BR_01"),
            _make_agg_signal("NTN_B", conviction=-0.3, strategy_id="INF_BR_01"),
            _make_agg_signal("USDBRL", conviction=0.6, strategy_id="FX_BR_01"),
        ]
        raw = []

        summary = monitor.generate_daily_summary(current, raw, regime="Goldilocks")

        # Should have at least 2 asset class groups (FIXED_INCOME and FX)
        ac_names = [g["asset_class"] for g in summary.active_signals]
        assert "FIXED_INCOME" in ac_names
        assert "FX" in ac_names

    def test_includes_alerts_in_text(self):
        """Summary text should include alert information."""
        monitor = SignalMonitor()
        prev = [_make_agg_signal("DI_PRE", conviction=0.5, strategy_id="RATES_BR_01")]
        curr = [_make_agg_signal("DI_PRE", conviction=-0.3, strategy_id="RATES_BR_01")]
        raw = []

        summary = monitor.generate_daily_summary(
            curr, raw, regime="Stagflation", previous_signals=prev,
        )

        assert summary.alert_count >= 1
        assert "[FLIP]" in summary.summary_text
        assert "DI_PRE" in summary.summary_text

    def test_empty_signals_valid_summary(self):
        """Empty signals should produce a valid but empty summary."""
        monitor = SignalMonitor()
        summary = monitor.generate_daily_summary([], [], regime="Unknown")

        assert summary.date == date.today()
        assert summary.active_signals == []
        assert summary.flips == []
        assert summary.surges == []
        assert summary.divergences == []
        assert summary.alert_count == 0
        assert "DAILY SIGNAL SUMMARY" in summary.summary_text


# ---------------------------------------------------------------------------
# Test: weekly flip count
# ---------------------------------------------------------------------------
class TestWeeklyFlipCount:
    def test_tracks_flips_over_7_days(self):
        """Weekly flip count should include flips from last 7 calendar days."""
        monitor = SignalMonitor()

        # Generate 3 flips over time
        for i in range(3):
            prev = [_make_agg_signal("DI_PRE", conviction=0.5)]
            curr = [_make_agg_signal("DI_PRE", conviction=-0.3)]
            monitor.check_signal_flips(prev, curr)
            # Reset for next flip
            prev2 = [_make_agg_signal("DI_PRE", conviction=-0.3)]
            curr2 = [_make_agg_signal("DI_PRE", conviction=0.5)]
            monitor.check_signal_flips(prev2, curr2)

        # Generate summary -- should show all recent flips
        summary = monitor.generate_daily_summary(
            [_make_agg_signal("DI_PRE", conviction=0.5, strategy_id="RATES_BR_01")],
            [],
            regime="Goldilocks",
        )

        assert summary.weekly_flip_count == 6  # 3 pairs of flips
        assert "Weekly Flip Count: 6" in summary.summary_text

    def test_old_flips_not_counted(self):
        """Flips older than 7 days should not be counted in weekly total."""
        monitor = SignalMonitor()

        # Add an old flip manually to history
        old_flip = SignalFlip(
            instrument="DI_PRE",
            previous_direction=SignalDirection.LONG,
            current_direction=SignalDirection.SHORT,
            previous_conviction=0.5,
            current_conviction=-0.3,
            timestamp=datetime.utcnow() - timedelta(days=10),
        )
        monitor._flip_history.append(old_flip)

        summary = monitor.generate_daily_summary(
            [_make_agg_signal("DI_PRE", conviction=0.5, strategy_id="RATES_BR_01")],
            [],
            regime="Goldilocks",
        )

        assert summary.weekly_flip_count == 0
