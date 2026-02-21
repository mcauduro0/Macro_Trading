"""Tests for RATES_BR_04 US Rates Spillover strategy.

Uses mock PointInTimeDataLoader to test signal generation under various
DI-UST spread and weekly UST move scenarios.
"""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from src.core.enums import SignalDirection
from src.strategies.rates_br_04_spillover import RatesBR04SpilloverStrategy


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
def _make_history(rates: list[float], start_date: str = "2024-01-01") -> pd.DataFrame:
    """Build a synthetic curve history DataFrame.

    Args:
        rates: List of rate values (one per business day).
        start_date: First date in the series.

    Returns:
        DataFrame with 'rate' column indexed by date.
    """
    dates = pd.bdate_range(start=start_date, periods=len(rates))
    return pd.DataFrame({"rate": rates}, index=dates)


def _make_mock_loader(
    di_hist: pd.DataFrame | None = None,
    ust_hist: pd.DataFrame | None = None,
) -> MagicMock:
    """Create a mock PointInTimeDataLoader for spillover tests.

    Args:
        di_hist: DI 1Y rate history.
        ust_hist: UST 1Y rate history.
    """
    loader = MagicMock()

    def curve_history_side_effect(curve_id, tenor, as_of_date, lookback_days=756):
        if curve_id == "DI_PRE" and di_hist is not None:
            return di_hist
        if curve_id == "UST_NOM" and ust_hist is not None:
            return ust_hist
        return pd.DataFrame(columns=["date", "rate"])

    loader.get_curve_history.side_effect = curve_history_side_effect
    return loader


# ---------------------------------------------------------------------------
# Spread overshoot (z > threshold) after large UST move -> LONG DI
# ---------------------------------------------------------------------------
class TestRatesBR04Long:
    """Spread too wide + big UST move -> LONG DI (fade)."""

    def test_spread_overshoot_long_di(self) -> None:
        """DI-UST spread well above mean after big UST move -> LONG."""
        # DI stable at 13.0, then jumps to 14.0 in last 5 days (spread widens)
        di_rates = [13.0] * 195 + [14.0] * 5
        di_hist = _make_history(di_rates)

        # UST drops from 4.0 to 3.98 over the last 5 days (20bps)
        # ust_values[-1]=3.98, ust_values[-5]=3.98, ust_values[-6]=4.0
        # Actually we need [-1] vs [-5] to differ: use graduated drop
        ust_rates = [4.0] * 194 + [4.0, 3.996, 3.992, 3.988, 3.984, 3.980]
        ust_hist = _make_history(ust_rates)

        loader = _make_mock_loader(di_hist=di_hist, ust_hist=ust_hist)
        strategy = RatesBR04SpilloverStrategy(
            data_loader=loader,
            spread_z_threshold=1.5,
            ust_weekly_move_bps=10.0,
        )
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.LONG
        assert pos.weight > 0
        assert 0.0 <= pos.confidence <= 1.0


# ---------------------------------------------------------------------------
# Spread undershoot (z < -threshold) after large UST move -> SHORT DI
# ---------------------------------------------------------------------------
class TestRatesBR04Short:
    """Spread too narrow + big UST move -> SHORT DI (fade)."""

    def test_spread_undershoot_short_di(self) -> None:
        """DI-UST spread well below mean after big UST move -> SHORT."""
        # DI drops in last 5 days (spread narrows)
        di_rates = [13.0] * 195 + [12.0] * 5
        di_hist = _make_history(di_rates)

        # UST rises gradually over last 5 days (20bps total)
        ust_rates = [4.0] * 194 + [4.0, 4.004, 4.008, 4.012, 4.016, 4.020]
        ust_hist = _make_history(ust_rates)

        loader = _make_mock_loader(di_hist=di_hist, ust_hist=ust_hist)
        strategy = RatesBR04SpilloverStrategy(
            data_loader=loader,
            spread_z_threshold=1.5,
            ust_weekly_move_bps=10.0,
        )
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.SHORT
        assert pos.weight < 0
        assert 0.0 <= pos.confidence <= 1.0


# ---------------------------------------------------------------------------
# Small UST move -> no signal
# ---------------------------------------------------------------------------
class TestRatesBR04SmallUSTMove:
    """UST move below threshold -> no position."""

    def test_small_ust_move_no_signal(self) -> None:
        """Weekly UST change < ust_weekly_move_bps -> no position."""
        # DI and UST both stable
        di_hist = _make_history([13.0] * 200)
        # UST barely moves (< 15bps = 0.0015)
        ust_rates = [4.0] * 195 + [4.0001] * 5
        ust_hist = _make_history(ust_rates)

        loader = _make_mock_loader(di_hist=di_hist, ust_hist=ust_hist)
        strategy = RatesBR04SpilloverStrategy(
            data_loader=loader,
            spread_z_threshold=2.0,
            ust_weekly_move_bps=15.0,
        )
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []


# ---------------------------------------------------------------------------
# Spread within threshold -> no position
# ---------------------------------------------------------------------------
class TestRatesBR04WithinThreshold:
    """Spread z-score within threshold -> no position."""

    def test_spread_within_threshold_no_position(self) -> None:
        """Spread z-score near zero despite UST move -> no position."""
        # DI stable at 13.0 (spread is at historical mean)
        di_hist = _make_history([13.0] * 200)
        # UST moves enough but spread stays normal
        ust_rates = [4.0] * 195 + [3.998] * 5
        ust_hist = _make_history(ust_rates)

        loader = _make_mock_loader(di_hist=di_hist, ust_hist=ust_hist)
        strategy = RatesBR04SpilloverStrategy(
            data_loader=loader,
            spread_z_threshold=2.0,
            ust_weekly_move_bps=10.0,
        )
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []


# ---------------------------------------------------------------------------
# Missing data edge cases
# ---------------------------------------------------------------------------
class TestRatesBR04MissingData:
    """Missing data should return empty list, not raise."""

    def test_missing_di_history_returns_empty(self) -> None:
        ust_hist = _make_history([4.0] * 200)
        loader = _make_mock_loader(di_hist=None, ust_hist=ust_hist)
        strategy = RatesBR04SpilloverStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_ust_history_returns_empty(self) -> None:
        di_hist = _make_history([13.0] * 200)
        loader = _make_mock_loader(di_hist=di_hist, ust_hist=None)
        strategy = RatesBR04SpilloverStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_both_empty_returns_empty(self) -> None:
        loader = _make_mock_loader(di_hist=None, ust_hist=None)
        strategy = RatesBR04SpilloverStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []


# ---------------------------------------------------------------------------
# Weight and confidence bounds
# ---------------------------------------------------------------------------
class TestRatesBR04Bounds:
    """Output weights and confidences must be in valid ranges."""

    def test_weight_in_bounds(self) -> None:
        """Weight must be in [-1, 1]."""
        # Large spread overshoot
        di_rates = [13.0] * 180 + [16.0] * 20
        di_hist = _make_history(di_rates)
        ust_rates = [4.0] * 195 + [3.997] * 5
        ust_hist = _make_history(ust_rates)

        loader = _make_mock_loader(di_hist=di_hist, ust_hist=ust_hist)
        strategy = RatesBR04SpilloverStrategy(
            data_loader=loader,
            spread_z_threshold=1.0,
            ust_weekly_move_bps=10.0,
        )
        positions = strategy.generate_signals(date(2025, 6, 15))

        if positions:
            pos = positions[0]
            assert -1.0 <= pos.weight <= 1.0
            assert 0.0 <= pos.confidence <= 1.0

    def test_strategy_id_matches(self) -> None:
        loader = _make_mock_loader()
        strategy = RatesBR04SpilloverStrategy(data_loader=loader)
        assert strategy.strategy_id == "RATES_BR_04"
