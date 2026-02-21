"""Tests for RATES_BR_03 DI Curve Slope (Flattener/Steepener) strategy.

Uses mock PointInTimeDataLoader to test signal generation under various
slope z-score and monetary cycle scenarios.
"""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from src.core.enums import SignalDirection
from src.strategies.rates_br_03_slope import RatesBR03SlopeStrategy


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


def _make_selic_df(values: list[float], start_date: str = "2024-01-01") -> pd.DataFrame:
    """Build a synthetic Selic history DataFrame.

    Args:
        values: List of Selic values.
        start_date: First date in the series.

    Returns:
        DataFrame with columns matching macro_series output.
    """
    dates = pd.bdate_range(start=start_date, periods=len(values))
    df = pd.DataFrame(
        {
            "value": values,
            "release_time": dates,
            "revision_number": 1,
        },
        index=dates,
    )
    df.index.name = "date"
    return df


def _make_mock_loader(
    curve: dict[int, float] | None = None,
    hist_2y: pd.DataFrame | None = None,
    hist_5y: pd.DataFrame | None = None,
    selic_df: pd.DataFrame | None = None,
    focus_ipca: float | None = 5.0,
) -> MagicMock:
    """Create a mock PointInTimeDataLoader with configurable returns.

    Args:
        curve: DI curve snapshot. Defaults to a curve with 504 and 1260 tenors.
        hist_2y: History for 2Y tenor.
        hist_5y: History for 5Y tenor.
        selic_df: Selic target history.
        focus_ipca: Focus IPCA value.
    """
    loader = MagicMock()

    # Default curve with 2Y and 5Y tenors
    if curve is None:
        curve = {126: 12.0, 252: 12.5, 504: 13.0, 756: 13.5, 1260: 14.0}
    loader.get_curve.return_value = curve

    # Curve history: return hist_2y or hist_5y depending on tenor
    def curve_history_side_effect(curve_id, tenor, as_of_date, lookback_days=756):
        if tenor == 504 and hist_2y is not None:
            return hist_2y
        if tenor == 1260 and hist_5y is not None:
            return hist_5y
        # Default: empty
        return pd.DataFrame(columns=["date", "rate"])

    loader.get_curve_history.side_effect = curve_history_side_effect

    # Selic history
    if selic_df is not None:
        loader.get_macro_series.return_value = selic_df
    else:
        loader.get_macro_series.return_value = _make_selic_df(
            [13.75, 13.75, 13.25, 13.25, 12.75]
        )

    # Focus IPCA
    loader.get_latest_macro_value.return_value = focus_ipca

    return loader


# ---------------------------------------------------------------------------
# Steep slope -> FLATTENER (positive weight, LONG direction)
# ---------------------------------------------------------------------------
class TestRatesBR03Flattener:
    """Slope z-score > threshold -> flattener position."""

    def test_steep_slope_easing_cycle_flattener(self) -> None:
        """High z-score + easing cycle -> LONG (flattener)."""
        # Create histories where current slope is far above rolling mean
        # 2Y history: stable around 13.0
        hist_2y = _make_history([13.0] * 200)
        # 5Y history: stable at 13.1 for most history -> mean slope ~0.1
        # Then jumps to 16.0 in last 5 days
        hist_5y = _make_history([13.1] * 195 + [16.0] * 5)
        # Current curve: slope = 16.0 - 13.0 = 3.0 (far above ~0.1 mean)

        selic_df = _make_selic_df([14.25, 14.25, 13.75, 13.75, 13.25])  # easing

        loader = _make_mock_loader(
            curve={504: 13.0, 1260: 16.0},
            hist_2y=hist_2y,
            hist_5y=hist_5y,
            selic_df=selic_df,
        )

        strategy = RatesBR03SlopeStrategy(data_loader=loader, slope_z_threshold=1.5)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.LONG
        assert pos.weight > 0  # flattener = positive weight
        assert pos.metadata.get("trade_type") == "flattener"
        assert 0.0 <= pos.confidence <= 1.0

    def test_steep_slope_tightening_cycle_flattener(self) -> None:
        """High z-score + tightening cycle -> still LONG (flattener)."""
        hist_2y = _make_history([13.0] * 200)
        hist_5y = _make_history([13.1] * 195 + [16.0] * 5)

        selic_df = _make_selic_df([12.75, 12.75, 13.25, 13.25, 13.75])  # tightening

        loader = _make_mock_loader(
            curve={504: 13.0, 1260: 16.0},
            hist_2y=hist_2y,
            hist_5y=hist_5y,
            selic_df=selic_df,
        )

        strategy = RatesBR03SlopeStrategy(data_loader=loader, slope_z_threshold=1.5)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.LONG
        assert pos.weight > 0


# ---------------------------------------------------------------------------
# Flat slope -> STEEPENER (negative weight, SHORT direction)
# ---------------------------------------------------------------------------
class TestRatesBR03Steepener:
    """Slope z-score < -threshold -> steepener position."""

    def test_flat_slope_steepener(self) -> None:
        """Low z-score (flat/inverted) -> SHORT (steepener)."""
        # History where slope was normally ~1.0 but now is near 0 or inverted
        hist_2y = _make_history([13.0] * 200)
        hist_5y = _make_history([14.0] * 180 + [13.0] * 20)
        # Current slope = 13.0 - 13.0 = 0.0 (well below ~1.0 mean)

        loader = _make_mock_loader(
            curve={504: 13.0, 1260: 13.0},
            hist_2y=hist_2y,
            hist_5y=hist_5y,
        )

        strategy = RatesBR03SlopeStrategy(data_loader=loader, slope_z_threshold=1.5)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.SHORT
        assert pos.weight < 0  # steepener = negative weight
        assert pos.metadata.get("trade_type") == "steepener"


# ---------------------------------------------------------------------------
# Slope within threshold -> no position
# ---------------------------------------------------------------------------
class TestRatesBR03Neutral:
    """Slope z-score within threshold -> no position."""

    def test_slope_within_threshold_no_position(self) -> None:
        """Z-score near zero -> empty list."""
        # History and current slope are both ~1.0 -> z-score ~0
        hist_2y = _make_history([13.0] * 200)
        hist_5y = _make_history([14.0] * 200)
        # Current slope = 14.0 - 13.0 = 1.0 (matches historical mean)

        loader = _make_mock_loader(
            curve={504: 13.0, 1260: 14.0},
            hist_2y=hist_2y,
            hist_5y=hist_5y,
        )

        strategy = RatesBR03SlopeStrategy(data_loader=loader, slope_z_threshold=1.5)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []


# ---------------------------------------------------------------------------
# Missing data edge cases
# ---------------------------------------------------------------------------
class TestRatesBR03MissingData:
    """Missing data should return empty list, not raise."""

    def test_missing_curve_returns_empty(self) -> None:
        loader = _make_mock_loader(curve={})
        strategy = RatesBR03SlopeStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_2y_tenor_returns_empty(self) -> None:
        # Curve with only very short tenors -- no 504-day equivalent
        loader = _make_mock_loader(curve={21: 10.0, 42: 10.5, 1260: 14.0})
        strategy = RatesBR03SlopeStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_5y_tenor_returns_empty(self) -> None:
        # No tenor near 1260
        loader = _make_mock_loader(curve={252: 12.0, 504: 13.0})
        strategy = RatesBR03SlopeStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_empty_history_returns_empty(self) -> None:
        empty_df = pd.DataFrame(columns=["date", "rate"])
        loader = _make_mock_loader(
            curve={504: 13.0, 1260: 14.0},
            hist_2y=empty_df,
            hist_5y=empty_df,
        )
        strategy = RatesBR03SlopeStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []


# ---------------------------------------------------------------------------
# Weight and confidence bounds
# ---------------------------------------------------------------------------
class TestRatesBR03Bounds:
    """Output weights and confidences must be in valid ranges."""

    def test_weight_in_bounds(self) -> None:
        """Weight must be in [-1, 1]."""
        hist_2y = _make_history([13.0] * 200)
        hist_5y = _make_history([13.5] * 180 + [16.0] * 20)

        loader = _make_mock_loader(
            curve={504: 13.0, 1260: 16.0},
            hist_2y=hist_2y,
            hist_5y=hist_5y,
        )

        strategy = RatesBR03SlopeStrategy(data_loader=loader, slope_z_threshold=1.0)
        positions = strategy.generate_signals(date(2025, 6, 15))

        if positions:
            pos = positions[0]
            assert -1.0 <= pos.weight <= 1.0
            assert 0.0 <= pos.confidence <= 1.0

    def test_confidence_bounded_at_one(self) -> None:
        """Even extreme z-scores should cap confidence at 1.0."""
        hist_2y = _make_history([13.0] * 200)
        hist_5y = _make_history([13.5] * 190 + [20.0] * 10)

        loader = _make_mock_loader(
            curve={504: 13.0, 1260: 20.0},
            hist_2y=hist_2y,
            hist_5y=hist_5y,
        )

        strategy = RatesBR03SlopeStrategy(data_loader=loader, slope_z_threshold=0.5)
        positions = strategy.generate_signals(date(2025, 6, 15))

        if positions:
            assert positions[0].confidence <= 1.0

    def test_strategy_id_matches(self) -> None:
        loader = _make_mock_loader()
        strategy = RatesBR03SlopeStrategy(data_loader=loader)
        assert strategy.strategy_id == "RATES_BR_03"
