"""Tests for RATES_BR_01 Carry & Roll-Down strategy.

Uses mock PointInTimeDataLoader to test signal generation under various
DI curve and carry-to-risk scenarios.
"""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from src.core.enums import SignalDirection
from src.strategies.rates_br_01_carry import RatesBR01CarryStrategy


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
def _make_mock_loader() -> MagicMock:
    """Create a mock PointInTimeDataLoader."""
    return MagicMock()


def _make_curve_history(
    rates: list[float], base_date: str = "2025-01-01"
) -> pd.DataFrame:
    """Create a mock curve history DataFrame.

    Args:
        rates: List of rate values.
        base_date: Starting date string for the index.

    Returns:
        DataFrame with 'rate' column and date index.
    """
    dates = pd.date_range(base_date, periods=len(rates), freq="B")
    df = pd.DataFrame({"rate": rates}, index=dates)
    df.index.name = "date"
    return df


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestRatesBR01CarryLong:
    """Test LONG signal when carry-to-risk exceeds positive threshold."""

    def test_long_position_above_threshold(self) -> None:
        loader = _make_mock_loader()

        # Curve with rising rates (positive carry)
        loader.get_curve.return_value = {
            126: 10.0,
            252: 11.5,
            504: 12.0,
        }

        # History for each tenor — low volatility so carry/risk is high
        def history_side_effect(curve_id, tenor, as_of, lookback_days=252):
            # Low volatility (std ~0.01 -> annualized ~0.16)
            base_rate = {126: 10.0, 252: 11.5, 504: 12.0}.get(tenor, 10.0)
            rates = [base_rate + 0.01 * (i % 3 - 1) for i in range(100)]
            return _make_curve_history(rates)

        loader.get_curve_history.side_effect = history_side_effect

        strategy = RatesBR01CarryStrategy(data_loader=loader, carry_threshold=1.5)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.LONG
        assert -1.0 <= pos.weight <= 1.0
        assert 0.0 <= pos.confidence <= 1.0
        assert "optimal_tenor" in pos.metadata


class TestRatesBR01CarryShort:
    """Test SHORT signal when carry-to-risk is below negative threshold."""

    def test_short_position_below_negative_threshold(self) -> None:
        loader = _make_mock_loader()

        # Curve with falling rates (negative carry)
        loader.get_curve.return_value = {
            126: 12.0,
            252: 10.0,
            504: 9.5,
        }

        def history_side_effect(curve_id, tenor, as_of, lookback_days=252):
            base_rate = {126: 12.0, 252: 10.0, 504: 9.5}.get(tenor, 10.0)
            rates = [base_rate + 0.01 * (i % 3 - 1) for i in range(100)]
            return _make_curve_history(rates)

        loader.get_curve_history.side_effect = history_side_effect

        strategy = RatesBR01CarryStrategy(data_loader=loader, carry_threshold=1.5)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.SHORT
        assert -1.0 <= pos.weight <= 1.0
        assert pos.weight < 0  # short = negative weight


class TestRatesBR01Neutral:
    """Test no position when carry-to-risk is within threshold."""

    def test_no_position_within_threshold(self) -> None:
        loader = _make_mock_loader()

        # Curve with very small rate differences but high volatility
        loader.get_curve.return_value = {
            126: 10.0,
            252: 10.01,
            504: 10.02,
        }

        def history_side_effect(curve_id, tenor, as_of, lookback_days=252):
            base_rate = 10.0
            # High volatility (large swings)
            rates = [base_rate + 0.5 * ((-1) ** i) for i in range(100)]
            return _make_curve_history(rates)

        loader.get_curve_history.side_effect = history_side_effect

        strategy = RatesBR01CarryStrategy(data_loader=loader, carry_threshold=1.5)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []


class TestRatesBR01EdgeCases:
    """Edge case handling for empty/insufficient data."""

    def test_empty_curve_returns_empty(self) -> None:
        loader = _make_mock_loader()
        loader.get_curve.return_value = {}

        strategy = RatesBR01CarryStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))
        assert positions == []

    def test_single_tenor_returns_empty(self) -> None:
        loader = _make_mock_loader()
        loader.get_curve.return_value = {252: 10.5}

        strategy = RatesBR01CarryStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))
        assert positions == []

    def test_insufficient_history_returns_empty(self) -> None:
        loader = _make_mock_loader()
        loader.get_curve.return_value = {126: 10.0, 252: 11.0}

        # Only 5 data points (need at least 20)
        loader.get_curve_history.return_value = _make_curve_history([10.0] * 5)

        strategy = RatesBR01CarryStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))
        assert positions == []


class TestRatesBR01OptimalTenor:
    """Verify optimal tenor selection (highest carry-to-risk ratio)."""

    def test_selects_highest_carry_to_risk(self) -> None:
        loader = _make_mock_loader()

        # Tenor 126->252 has small carry, 252->504 has large carry
        loader.get_curve.return_value = {
            126: 10.0,
            252: 10.1,  # small carry from 126
            504: 13.0,  # large carry from 252
        }

        def history_side_effect(curve_id, tenor, as_of, lookback_days=252):
            base_rate = {126: 10.0, 252: 10.1, 504: 13.0}.get(tenor, 10.0)
            # Same low volatility for both
            rates = [base_rate + 0.01 * (i % 3 - 1) for i in range(100)]
            return _make_curve_history(rates)

        loader.get_curve_history.side_effect = history_side_effect

        strategy = RatesBR01CarryStrategy(data_loader=loader, carry_threshold=0.5)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        # The optimal tenor should be 252 (carry from 252->504 is largest)
        assert positions[0].metadata["optimal_tenor"] == 252


class TestRatesBR01WeightBounds:
    """Weight and confidence must be in valid ranges."""

    def test_weight_in_bounds(self) -> None:
        loader = _make_mock_loader()

        loader.get_curve.return_value = {
            126: 10.0,
            252: 15.0,  # massive carry
        }

        def history_side_effect(curve_id, tenor, as_of, lookback_days=252):
            rates = [10.0 + 0.001 * i for i in range(100)]
            return _make_curve_history(rates)

        loader.get_curve_history.side_effect = history_side_effect

        strategy = RatesBR01CarryStrategy(data_loader=loader, carry_threshold=0.1)
        positions = strategy.generate_signals(date(2025, 6, 15))

        if positions:
            pos = positions[0]
            assert -1.0 <= pos.weight <= 1.0
            assert 0.0 <= pos.confidence <= 1.0
