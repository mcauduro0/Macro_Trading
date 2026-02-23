"""Tests for PositionSizer with vol_target, fractional_kelly, and risk_budget methods.

Covers:
- vol_target_size: basic sizing, clamping to max_position
- fractional_kelly: half Kelly, negative expected return produces short
- risk_budget_size: proportional to component VaR share
- Soft limit override: conviction > 0.8 allows up to 1.2x max_position
"""

from __future__ import annotations

import pytest

from src.portfolio.position_sizer import PositionSizer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sizer() -> PositionSizer:
    """Default sizer: target_vol=10%, kelly_fraction=0.5, max_position=0.25."""
    return PositionSizer(target_vol=0.10, kelly_fraction=0.5, max_position=0.25)


# ---------------------------------------------------------------------------
# Tests: vol_target_size
# ---------------------------------------------------------------------------
class TestVolTargetSize:
    def test_basic_sizing(self, sizer: PositionSizer):
        """10% target / 20% instrument vol = 0.5, but clamped to max_position=0.25."""
        # If instrument vol is 20%, size = 0.10 / 0.20 = 0.50
        # Clamped to max_position = 0.25
        result = sizer.vol_target_size(instrument_vol=0.20)
        assert result == 0.25  # Clamped

    def test_low_vol_instrument(self, sizer: PositionSizer):
        """For very low vol instrument, size would exceed max_position."""
        result = sizer.vol_target_size(instrument_vol=0.05)
        # 0.10 / 0.05 = 2.0, clamped to 0.25
        assert result == 0.25

    def test_high_vol_instrument(self, sizer: PositionSizer):
        """For high vol instrument, size stays within bounds."""
        result = sizer.vol_target_size(instrument_vol=0.40)
        # 0.10 / 0.40 = 0.25
        assert result == 0.25

    def test_exact_target_vol_match(self, sizer: PositionSizer):
        """When instrument vol equals target vol, size = 1.0 clamped to max."""
        result = sizer.vol_target_size(instrument_vol=0.10)
        # 0.10 / 0.10 = 1.0, clamped to 0.25
        assert result == 0.25

    def test_unclamped(self):
        """Test with high max_position so result is not clamped."""
        sizer = PositionSizer(target_vol=0.10, max_position=1.0)
        result = sizer.vol_target_size(instrument_vol=0.20)
        # 0.10 / 0.20 = 0.50
        assert abs(result - 0.50) < 1e-8

    def test_zero_vol_returns_zero(self, sizer: PositionSizer):
        """Zero instrument vol returns 0.0 to avoid division by zero."""
        result = sizer.vol_target_size(instrument_vol=0.0)
        assert result == 0.0

    def test_negative_vol_returns_zero(self, sizer: PositionSizer):
        """Negative instrument vol returns 0.0."""
        result = sizer.vol_target_size(instrument_vol=-0.10)
        assert result == 0.0


# ---------------------------------------------------------------------------
# Tests: fractional_kelly_size
# ---------------------------------------------------------------------------
class TestFractionalKellySize:
    def test_half_kelly_basic(self, sizer: PositionSizer):
        """Half Kelly produces 50% of full Kelly."""
        # Full Kelly: f* = 0.10 / 0.04 = 2.5
        # Half Kelly: 0.5 * 2.5 = 1.25, clamped to 0.25
        result = sizer.fractional_kelly_size(
            expected_return=0.10, return_variance=0.04
        )
        assert result == 0.25  # Clamped

    def test_half_kelly_unclamped(self):
        """Half Kelly without clamping."""
        sizer = PositionSizer(kelly_fraction=0.5, max_position=10.0)
        result = sizer.fractional_kelly_size(
            expected_return=0.10, return_variance=0.04
        )
        # 0.5 * (0.10 / 0.04) = 0.5 * 2.5 = 1.25
        assert abs(result - 1.25) < 1e-8

    def test_negative_expected_return_produces_short(self, sizer: PositionSizer):
        """Negative expected return should produce a negative (short) position."""
        result = sizer.fractional_kelly_size(
            expected_return=-0.05, return_variance=0.04
        )
        # Full Kelly: -0.05 / 0.04 = -1.25
        # Half Kelly: 0.5 * -1.25 = -0.625, clamped to -0.25
        assert result == -0.25  # Clamped to negative max

    def test_small_expected_return(self):
        """Small expected return stays within bounds."""
        sizer = PositionSizer(kelly_fraction=0.5, max_position=0.25)
        result = sizer.fractional_kelly_size(
            expected_return=0.01, return_variance=0.04
        )
        # 0.5 * (0.01 / 0.04) = 0.5 * 0.25 = 0.125
        assert abs(result - 0.125) < 1e-8

    def test_zero_variance_returns_zero(self, sizer: PositionSizer):
        """Zero variance returns 0.0 to avoid division by zero."""
        result = sizer.fractional_kelly_size(
            expected_return=0.10, return_variance=0.0
        )
        assert result == 0.0


# ---------------------------------------------------------------------------
# Tests: risk_budget_size
# ---------------------------------------------------------------------------
class TestRiskBudgetSize:
    def test_proportional_to_component_var(self, sizer: PositionSizer):
        """Size should be proportional to component VaR share."""
        # Component VaR = 0.03, Total VaR = 0.10, Budget = 1.0
        # size = 1.0 * (0.03 / 0.10) = 0.30, clamped to 0.25
        result = sizer.risk_budget_size(
            total_risk_budget=1.0, component_var=0.03, total_var=0.10
        )
        assert result == 0.25  # Clamped

    def test_small_component_var(self, sizer: PositionSizer):
        """Small component VaR produces small position."""
        result = sizer.risk_budget_size(
            total_risk_budget=0.5, component_var=0.01, total_var=0.10
        )
        # 0.5 * (0.01 / 0.10) = 0.05
        assert abs(result - 0.05) < 1e-8

    def test_zero_total_var_returns_zero(self, sizer: PositionSizer):
        """Zero total VaR returns 0.0 to avoid division by zero."""
        result = sizer.risk_budget_size(
            total_risk_budget=1.0, component_var=0.03, total_var=0.0
        )
        assert result == 0.0


# ---------------------------------------------------------------------------
# Tests: Soft Limit Override
# ---------------------------------------------------------------------------
class TestSoftLimitOverride:
    def test_high_conviction_allows_override(self):
        """Conviction > 0.8 allows up to 1.2x max_position."""
        sizer = PositionSizer(target_vol=0.10, max_position=0.25)
        positions = {
            "ASSET_A": {
                "expected_return": 0.20,
                "variance": 0.04,
                "conviction": 0.9,
            }
        }
        result = sizer.size_portfolio(positions, method="fractional_kelly")

        # Full Kelly: 0.20 / 0.04 = 5.0
        # Half Kelly: 0.5 * 5.0 = 2.5, normally clamped to 0.25
        # But conviction > 0.8 allows 0.25 * 1.2 = 0.30
        assert result["ASSET_A"] == 0.30

    def test_low_conviction_no_override(self):
        """Conviction <= 0.8 uses standard max_position."""
        sizer = PositionSizer(target_vol=0.10, max_position=0.25)
        positions = {
            "ASSET_A": {
                "expected_return": 0.20,
                "variance": 0.04,
                "conviction": 0.5,
            }
        }
        result = sizer.size_portfolio(positions, method="fractional_kelly")

        # Half Kelly: 2.5, clamped to 0.25 (no override)
        assert result["ASSET_A"] == 0.25


# ---------------------------------------------------------------------------
# Tests: size_portfolio
# ---------------------------------------------------------------------------
class TestSizePortfolio:
    def test_vol_target_portfolio(self):
        """size_portfolio with vol_target method."""
        sizer = PositionSizer(target_vol=0.10, max_position=1.0)
        positions = {
            "A": {"volatility": 0.20},
            "B": {"volatility": 0.40},
        }
        result = sizer.size_portfolio(positions, method="vol_target")
        assert abs(result["A"] - 0.50) < 1e-6
        assert abs(result["B"] - 0.25) < 1e-6

    def test_unknown_method_returns_zero(self):
        """Unknown sizing method returns 0.0 for all positions."""
        sizer = PositionSizer()
        positions = {"A": {"volatility": 0.20}}
        result = sizer.size_portfolio(positions, method="unknown")
        assert result["A"] == 0.0
