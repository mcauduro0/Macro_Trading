"""Tests for INF_BR_01 Breakeven Inflation Trade strategy.

Uses mock PointInTimeDataLoader to test signal generation under various
breakeven divergence scenarios between Focus forecast and market-implied
inflation.
"""

from datetime import date
from unittest.mock import MagicMock

from src.core.enums import SignalDirection
from src.strategies.inf_br_01_breakeven import InfBR01BreakevenStrategy


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
def _make_mock_loader(
    di_curve: dict[int, float] | None = None,
    ntnb_curve: dict[int, float] | None = None,
    focus_ipca: float | None = 5.0,
) -> MagicMock:
    """Create a mock PointInTimeDataLoader for breakeven tests.

    Args:
        di_curve: DI_PRE curve snapshot. Defaults to curve with 504 tenor.
        ntnb_curve: NTN_B_REAL curve snapshot. Defaults to curve with 504 tenor.
        focus_ipca: Focus IPCA CY median value (None = missing).
    """
    loader = MagicMock()

    # Default curves with 2Y tenors
    if di_curve is None:
        di_curve = {126: 12.0, 252: 12.5, 504: 13.0, 756: 13.5}
    if ntnb_curve is None:
        ntnb_curve = {504: 6.0, 756: 6.5, 1260: 7.0}

    def get_curve_side_effect(curve_id, as_of_date):
        if curve_id == "DI_PRE":
            return di_curve
        if curve_id == "NTN_B_REAL":
            return ntnb_curve
        return {}

    loader.get_curve.side_effect = get_curve_side_effect
    loader.get_latest_macro_value.return_value = focus_ipca

    return loader


# ---------------------------------------------------------------------------
# LONG breakeven: agent forecast > market breakeven by > threshold
# ---------------------------------------------------------------------------
class TestInfBR01Long:
    """Agent sees higher inflation than market -> LONG breakeven."""

    def test_long_when_forecast_above_breakeven(self) -> None:
        """divergence > 50bps -> LONG breakeven position."""
        # DI nominal 504 = 13.0, NTN-B real 504 = 6.0
        # market breakeven = 13.0 - 6.0 = 7.0%
        # focus_ipca = 8.5% -> divergence = 1.5% = 150bps > 50bps
        loader = _make_mock_loader(
            di_curve={504: 13.0},
            ntnb_curve={504: 6.0},
            focus_ipca=8.5,
        )

        strategy = InfBR01BreakevenStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.LONG
        assert pos.weight > 0
        assert 0.0 <= pos.confidence <= 1.0
        assert pos.strategy_id == "INF_BR_01"

    def test_long_metadata_contains_breakeven_info(self) -> None:
        loader = _make_mock_loader(
            di_curve={504: 13.0},
            ntnb_curve={504: 6.0},
            focus_ipca=8.5,
        )
        strategy = InfBR01BreakevenStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        meta = positions[0].metadata
        assert "market_breakeven" in meta
        assert "agent_forecast" in meta
        assert "divergence_bps" in meta
        assert meta["market_breakeven"] == 7.0
        assert meta["agent_forecast"] == 8.5


# ---------------------------------------------------------------------------
# SHORT breakeven: agent forecast < market breakeven by > threshold
# ---------------------------------------------------------------------------
class TestInfBR01Short:
    """Agent sees lower inflation than market -> SHORT breakeven."""

    def test_short_when_forecast_below_breakeven(self) -> None:
        """divergence < -50bps -> SHORT breakeven position."""
        # market breakeven = 13.0 - 6.0 = 7.0%
        # focus_ipca = 5.5% -> divergence = -1.5% = -150bps
        loader = _make_mock_loader(
            di_curve={504: 13.0},
            ntnb_curve={504: 6.0},
            focus_ipca=5.5,
        )

        strategy = InfBR01BreakevenStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.SHORT
        assert pos.weight < 0
        assert 0.0 <= pos.confidence <= 1.0


# ---------------------------------------------------------------------------
# Within threshold -> no position
# ---------------------------------------------------------------------------
class TestInfBR01Neutral:
    """Divergence within threshold -> no position."""

    def test_divergence_within_threshold_no_position(self) -> None:
        """abs(divergence) <= 50bps -> empty list."""
        # market breakeven = 13.0 - 6.0 = 7.0%
        # focus_ipca = 7.2% -> divergence = 0.2% = 20bps < 50bps
        loader = _make_mock_loader(
            di_curve={504: 13.0},
            ntnb_curve={504: 6.0},
            focus_ipca=7.2,
        )

        strategy = InfBR01BreakevenStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []

    def test_exact_at_threshold_no_position(self) -> None:
        """divergence exactly at 50bps -> no position (must exceed)."""
        # market breakeven = 7.0, focus = 7.5 -> divergence = 0.5% = 50bps
        # Strategy uses > not >=, so exactly at threshold = no signal
        loader = _make_mock_loader(
            di_curve={504: 13.0},
            ntnb_curve={504: 6.0},
            focus_ipca=7.5,
        )

        strategy = InfBR01BreakevenStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []


# ---------------------------------------------------------------------------
# Missing data edge cases
# ---------------------------------------------------------------------------
class TestInfBR01MissingData:
    """Missing data should return empty list, not raise."""

    def test_missing_di_curve_returns_empty(self) -> None:
        loader = _make_mock_loader(di_curve={})
        strategy = InfBR01BreakevenStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_ntnb_curve_returns_empty(self) -> None:
        loader = _make_mock_loader(ntnb_curve={})
        strategy = InfBR01BreakevenStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_focus_forecast_returns_empty(self) -> None:
        loader = _make_mock_loader(focus_ipca=None)
        strategy = InfBR01BreakevenStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_no_matching_di_tenor_returns_empty(self) -> None:
        """DI curve with no tenor near 504 days."""
        loader = _make_mock_loader(
            di_curve={21: 10.0, 42: 10.5},
            ntnb_curve={504: 6.0},
        )
        strategy = InfBR01BreakevenStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_no_matching_ntnb_tenor_returns_empty(self) -> None:
        """NTN-B curve with no tenor near 504 days."""
        loader = _make_mock_loader(
            di_curve={504: 13.0},
            ntnb_curve={1890: 7.5, 2520: 8.0},
        )
        strategy = InfBR01BreakevenStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []


# ---------------------------------------------------------------------------
# Weight and confidence bounds
# ---------------------------------------------------------------------------
class TestInfBR01Bounds:
    """Output weights and confidences must be in valid ranges."""

    def test_weight_in_bounds(self) -> None:
        """Weight must be in [-1, 1]."""
        # Large divergence
        loader = _make_mock_loader(
            di_curve={504: 13.0},
            ntnb_curve={504: 6.0},
            focus_ipca=12.0,  # divergence = 5.0% = 500bps
        )
        strategy = InfBR01BreakevenStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert -1.0 <= pos.weight <= 1.0
        assert 0.0 <= pos.confidence <= 1.0

    def test_confidence_scales_with_divergence(self) -> None:
        """Larger divergence should produce higher confidence."""
        # Small divergence: 60bps
        loader_small = _make_mock_loader(
            di_curve={504: 13.0},
            ntnb_curve={504: 6.0},
            focus_ipca=7.6,
        )
        strat_small = InfBR01BreakevenStrategy(data_loader=loader_small)
        pos_small = strat_small.generate_signals(date(2025, 6, 15))

        # Large divergence: 300bps
        loader_large = _make_mock_loader(
            di_curve={504: 13.0},
            ntnb_curve={504: 6.0},
            focus_ipca=10.0,
        )
        strat_large = InfBR01BreakevenStrategy(data_loader=loader_large)
        pos_large = strat_large.generate_signals(date(2025, 6, 15))

        assert len(pos_small) == 1 and len(pos_large) == 1
        assert pos_large[0].confidence > pos_small[0].confidence


# ---------------------------------------------------------------------------
# Custom threshold
# ---------------------------------------------------------------------------
class TestInfBR01CustomThreshold:
    """Test with custom divergence_threshold_bps."""

    def test_custom_threshold_100bps(self) -> None:
        """With 100bps threshold, 60bps divergence should not trigger."""
        # market breakeven = 7.0, focus = 7.6 -> divergence = 60bps < 100bps
        loader = _make_mock_loader(
            di_curve={504: 13.0},
            ntnb_curve={504: 6.0},
            focus_ipca=7.6,
        )
        strategy = InfBR01BreakevenStrategy(
            data_loader=loader,
            divergence_threshold_bps=100.0,
        )
        positions = strategy.generate_signals(date(2025, 6, 15))
        assert positions == []

    def test_custom_threshold_25bps_triggers(self) -> None:
        """With 25bps threshold, 40bps divergence should trigger."""
        # market breakeven = 7.0, focus = 7.4 -> divergence = 40bps > 25bps
        loader = _make_mock_loader(
            di_curve={504: 13.0},
            ntnb_curve={504: 6.0},
            focus_ipca=7.4,
        )
        strategy = InfBR01BreakevenStrategy(
            data_loader=loader,
            divergence_threshold_bps=25.0,
        )
        positions = strategy.generate_signals(date(2025, 6, 15))
        assert len(positions) == 1
        assert positions[0].direction == SignalDirection.LONG
