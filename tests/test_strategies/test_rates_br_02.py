"""Tests for RATES_BR_02 Taylor Rule Misalignment strategy.

Uses mock PointInTimeDataLoader to test signal generation under various
Taylor-market gap scenarios.
"""

from datetime import date
from unittest.mock import MagicMock

from src.core.enums import SignalDirection
from src.strategies.rates_br_02_taylor import RatesBR02TaylorStrategy


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
def _make_mock_loader(
    selic: float | None = 13.75,
    focus_ipca: float | None = 5.0,
    curve: dict[int, float] | None = None,
    output_gap: float | None = None,
) -> MagicMock:
    """Create a mock PointInTimeDataLoader with configurable return values.

    Args:
        selic: Selic target value (None = missing).
        focus_ipca: Focus IPCA median (None = missing).
        curve: DI curve dict (None = default with 252-day tenor).
        output_gap: Output gap value (None = not available).
    """
    loader = MagicMock()

    def get_latest_side_effect(series_code, as_of_date):
        if series_code == "BR_SELIC_TARGET":
            return selic
        if series_code.startswith("BR_FOCUS_IPCA_") and series_code.endswith("_MEDIAN"):
            return focus_ipca
        if series_code == "BR_OUTPUT_GAP":
            return output_gap
        return None

    loader.get_latest_macro_value.side_effect = get_latest_side_effect
    loader.get_curve.return_value = curve if curve is not None else {252: 12.0}

    return loader


# ---------------------------------------------------------------------------
# SHORT signal: Taylor > market (market too dovish)
# ---------------------------------------------------------------------------
class TestRatesBR02Short:
    """Taylor rate > market rate -> SHORT DI (rates should rise)."""

    def test_short_when_taylor_above_market(self) -> None:
        """Gap = taylor - market > 100bps -> SHORT."""
        # With pi_e=5.0, r_star=4.5, alpha=1.5, beta=0.5, gap=0:
        # taylor = 4.5 + 5.0 + 1.5*(5.0-3.0) + 0.5*0 = 4.5 + 5.0 + 3.0 = 12.5
        # market = 10.0 -> gap = 2.5% = 250bps > 100bps
        loader = _make_mock_loader(selic=13.75, focus_ipca=5.0, curve={252: 10.0})

        strategy = RatesBR02TaylorStrategy(data_loader=loader, gap_threshold_bps=100.0)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.SHORT
        assert pos.weight < 0
        assert 0.0 <= pos.confidence <= 1.0

    def test_short_metadata_contains_gap(self) -> None:
        loader = _make_mock_loader(selic=13.75, focus_ipca=5.0, curve={252: 10.0})
        strategy = RatesBR02TaylorStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        assert "taylor_rate" in positions[0].metadata
        assert "market_rate" in positions[0].metadata
        assert "gap_bps" in positions[0].metadata


# ---------------------------------------------------------------------------
# LONG signal: Taylor < market (market too hawkish)
# ---------------------------------------------------------------------------
class TestRatesBR02Long:
    """Taylor rate < market rate -> LONG DI (rates should fall)."""

    def test_long_when_taylor_below_market(self) -> None:
        """Gap < -100bps -> LONG."""
        # taylor = 4.5 + 5.0 + 1.5*(5.0-3.0) + 0 = 12.5
        # market = 16.0 -> gap = -3.5% = -350bps
        loader = _make_mock_loader(selic=13.75, focus_ipca=5.0, curve={252: 16.0})

        strategy = RatesBR02TaylorStrategy(data_loader=loader, gap_threshold_bps=100.0)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.LONG
        assert pos.weight > 0
        assert 0.0 <= pos.confidence <= 1.0


# ---------------------------------------------------------------------------
# No position: gap within threshold
# ---------------------------------------------------------------------------
class TestRatesBR02Neutral:
    """Gap within threshold -> no position."""

    def test_no_position_within_threshold(self) -> None:
        # taylor = 4.5 + 5.0 + 1.5*(5.0-3.0) + 0 = 12.5
        # market = 12.5 -> gap = 0bps
        loader = _make_mock_loader(selic=13.75, focus_ipca=5.0, curve={252: 12.5})

        strategy = RatesBR02TaylorStrategy(data_loader=loader, gap_threshold_bps=100.0)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []

    def test_small_gap_within_threshold(self) -> None:
        # taylor = 12.5, market = 12.0 -> gap = 0.5% = 50bps < 100bps
        loader = _make_mock_loader(selic=13.75, focus_ipca=5.0, curve={252: 12.0})

        strategy = RatesBR02TaylorStrategy(data_loader=loader, gap_threshold_bps=100.0)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []


# ---------------------------------------------------------------------------
# Missing data
# ---------------------------------------------------------------------------
class TestRatesBR02MissingData:
    """Missing data should return empty list, not raise."""

    def test_missing_selic_returns_empty(self) -> None:
        loader = _make_mock_loader(selic=None)
        strategy = RatesBR02TaylorStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))
        assert positions == []

    def test_missing_focus_ipca_returns_empty(self) -> None:
        loader = _make_mock_loader(focus_ipca=None)
        strategy = RatesBR02TaylorStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))
        assert positions == []

    def test_missing_di_curve_returns_empty(self) -> None:
        loader = _make_mock_loader(curve={})
        strategy = RatesBR02TaylorStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))
        assert positions == []

    def test_no_1y_tenor_in_curve_returns_empty(self) -> None:
        # Only very short tenors, no 252-day equivalent
        loader = _make_mock_loader(curve={21: 10.0, 42: 10.5})
        strategy = RatesBR02TaylorStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))
        assert positions == []


# ---------------------------------------------------------------------------
# Weight and confidence bounds
# ---------------------------------------------------------------------------
class TestRatesBR02Bounds:
    """Output weights and confidences must be in valid ranges."""

    def test_weight_in_bounds(self) -> None:
        # Large gap -> high confidence
        loader = _make_mock_loader(selic=13.75, focus_ipca=8.0, curve={252: 5.0})
        strategy = RatesBR02TaylorStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        if positions:
            pos = positions[0]
            assert -1.0 <= pos.weight <= 1.0
            assert 0.0 <= pos.confidence <= 1.0

    def test_confidence_scales_with_gap(self) -> None:
        """Larger gap should produce higher confidence."""
        # Small gap: taylor=12.5, market=11.0 -> gap=1.5%=150bps
        loader_small = _make_mock_loader(focus_ipca=5.0, curve={252: 11.0})
        strat_small = RatesBR02TaylorStrategy(data_loader=loader_small)
        pos_small = strat_small.generate_signals(date(2025, 6, 15))

        # Large gap: taylor=12.5, market=8.0 -> gap=4.5%=450bps
        loader_large = _make_mock_loader(focus_ipca=5.0, curve={252: 8.0})
        strat_large = RatesBR02TaylorStrategy(data_loader=loader_large)
        pos_large = strat_large.generate_signals(date(2025, 6, 15))

        assert len(pos_small) == 1 and len(pos_large) == 1
        assert pos_large[0].confidence > pos_small[0].confidence


# ---------------------------------------------------------------------------
# Custom threshold
# ---------------------------------------------------------------------------
class TestRatesBR02CustomThreshold:
    """Test with custom gap_threshold_bps."""

    def test_custom_threshold_200bps(self) -> None:
        # taylor=12.5, market=11.0 -> gap=1.5%=150bps
        # With 200bps threshold -> no position (150 < 200)
        loader = _make_mock_loader(focus_ipca=5.0, curve={252: 11.0})
        strategy = RatesBR02TaylorStrategy(data_loader=loader, gap_threshold_bps=200.0)
        positions = strategy.generate_signals(date(2025, 6, 15))
        assert positions == []

    def test_custom_threshold_50bps_triggers(self) -> None:
        # taylor=12.5, market=12.0 -> gap=0.5%=50bps
        # With 50bps threshold -> position (50 >= 50... but threshold is >, not >=)
        # Actually abs(50) <= 50, so it should NOT trigger (plan says "exceeds")
        # Let's use market=11.9 -> gap=0.6%=60bps > 50bps
        loader = _make_mock_loader(focus_ipca=5.0, curve={252: 11.9})
        strategy = RatesBR02TaylorStrategy(data_loader=loader, gap_threshold_bps=50.0)
        positions = strategy.generate_signals(date(2025, 6, 15))
        assert len(positions) == 1


# ---------------------------------------------------------------------------
# 1Y tenor finding
# ---------------------------------------------------------------------------
class TestRatesBR02TenorFinding:
    """Test that the strategy finds the closest tenor to 252 days."""

    def test_exact_252_tenor(self) -> None:
        loader = _make_mock_loader(focus_ipca=5.0, curve={252: 10.0})
        strategy = RatesBR02TaylorStrategy(data_loader=loader)
        rate = strategy._get_1y_rate({252: 10.5})
        assert rate == 10.5

    def test_closest_tenor_within_tolerance(self) -> None:
        loader = _make_mock_loader()
        strategy = RatesBR02TaylorStrategy(data_loader=loader)
        # 240 is within 50-day tolerance of 252
        rate = strategy._get_1y_rate({126: 9.0, 240: 10.5, 504: 11.0})
        assert rate == 10.5

    def test_no_tenor_in_tolerance(self) -> None:
        loader = _make_mock_loader()
        strategy = RatesBR02TaylorStrategy(data_loader=loader)
        # Only tenors far from 252
        rate = strategy._get_1y_rate({21: 9.0, 42: 9.5, 756: 12.0})
        assert rate is None
