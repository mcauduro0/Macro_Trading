"""Tests for Black-Litterman model with regime-adjusted view confidence.

Covers:
- Equilibrium returns proportional to market weights (diagonal covariance)
- Posterior returns shift toward views when confidence is high
- Posterior returns stay near equilibrium when confidence is low (uncertain regime)
- Regime clarity adjusts Omega (view uncertainty)
- Empty views returns equilibrium unchanged
- Single view on one instrument shifts only that instrument
"""

from __future__ import annotations

import numpy as np
import pytest

from src.portfolio.black_litterman import (
    AgentView,
    BlackLitterman,
    BlackLittermanConfig,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def diagonal_cov() -> np.ndarray:
    """Simple 3x3 diagonal covariance (vol: 20%, 15%, 10%)."""
    return np.diag([0.04, 0.0225, 0.01])


@pytest.fixture
def equal_weights() -> np.ndarray:
    """Equal market cap weights for 3 assets."""
    return np.array([1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0])


@pytest.fixture
def bl() -> BlackLitterman:
    """Default Black-Litterman instance."""
    return BlackLitterman()


@pytest.fixture
def instrument_names() -> list[str]:
    return ["ASSET_A", "ASSET_B", "ASSET_C"]


# ---------------------------------------------------------------------------
# Tests: Equilibrium Returns
# ---------------------------------------------------------------------------
class TestEquilibriumReturns:
    def test_proportional_to_market_weights_diagonal(
        self, bl: BlackLitterman, diagonal_cov: np.ndarray
    ):
        """Equilibrium returns pi = delta * Sigma * w are proportional to
        market weights for a diagonal covariance."""
        weights = np.array([0.5, 0.3, 0.2])
        pi = bl.compute_equilibrium_returns(diagonal_cov, weights)

        # For diagonal covariance, pi_i = delta * sigma_i^2 * w_i
        # So pi should be proportional to sigma_i^2 * w_i
        expected = bl.config.risk_aversion * diagonal_cov @ weights
        np.testing.assert_array_almost_equal(pi, expected, decimal=10)

    def test_higher_weight_higher_equilibrium(
        self, bl: BlackLitterman, diagonal_cov: np.ndarray
    ):
        """Asset with higher weight should have higher implied return
        when all have same variance."""
        equal_cov = np.eye(3) * 0.04
        weights = np.array([0.5, 0.3, 0.2])
        pi = bl.compute_equilibrium_returns(equal_cov, weights)

        assert pi[0] > pi[1] > pi[2]


# ---------------------------------------------------------------------------
# Tests: View Building
# ---------------------------------------------------------------------------
class TestBuildViews:
    def test_single_view_pick_matrix(
        self,
        bl: BlackLitterman,
        instrument_names: list[str],
        diagonal_cov: np.ndarray,
    ):
        """Single view creates P with one row having 1.0 at correct column."""
        views = [AgentView("ASSET_B", 0.05, 0.9, "agent_1")]
        P, Q, Omega = bl.build_views(views, instrument_names, 1.0, diagonal_cov)

        assert P.shape == (1, 3)
        assert P[0, 1] == 1.0  # ASSET_B is index 1
        assert Q[0] == 0.05

    def test_regime_clarity_high_tight_omega(
        self,
        bl: BlackLitterman,
        instrument_names: list[str],
        diagonal_cov: np.ndarray,
    ):
        """High regime clarity (0.9) should produce tight (small) Omega values."""
        views = [AgentView("ASSET_A", 0.05, 0.8, "agent_1")]

        _, _, omega_clear = bl.build_views(views, instrument_names, 0.9, diagonal_cov)
        _, _, omega_unclear = bl.build_views(views, instrument_names, 0.2, diagonal_cov)

        # Clear regime -> tighter Omega (smaller diagonal values)
        assert omega_clear[0, 0] < omega_unclear[0, 0]

    def test_regime_clarity_low_wide_omega(
        self,
        bl: BlackLitterman,
        instrument_names: list[str],
        diagonal_cov: np.ndarray,
    ):
        """Low regime clarity (0.2) should produce wider (larger) Omega values."""
        views = [AgentView("ASSET_A", 0.05, 0.8, "agent_1")]

        _, _, omega_high = bl.build_views(views, instrument_names, 0.9, diagonal_cov)
        _, _, omega_low = bl.build_views(views, instrument_names, 0.2, diagonal_cov)

        # Uncertain regime -> wider Omega
        ratio = omega_low[0, 0] / omega_high[0, 0]
        assert ratio > 2.0  # Should be substantially wider


# ---------------------------------------------------------------------------
# Tests: Posterior Returns
# ---------------------------------------------------------------------------
class TestPosteriorReturns:
    def test_posterior_shifts_toward_view_high_confidence(
        self,
        bl: BlackLitterman,
        diagonal_cov: np.ndarray,
        instrument_names: list[str],
    ):
        """With high confidence and clear regime, posterior should shift toward view."""
        weights = np.array([1.0 / 3, 1.0 / 3, 1.0 / 3])
        equilibrium = bl.compute_equilibrium_returns(diagonal_cov, weights)

        # Agent has a strong bullish view on ASSET_A
        views = [AgentView("ASSET_A", 0.10, 0.95, "agent_1")]
        P, Q, Omega = bl.build_views(views, instrument_names, 0.95, diagonal_cov)
        posterior_mu, _ = bl.posterior_returns(equilibrium, diagonal_cov, P, Q, Omega)

        # Posterior for ASSET_A should be higher than equilibrium
        assert posterior_mu[0] > equilibrium[0]

    def test_posterior_stays_near_equilibrium_low_confidence(
        self,
        bl: BlackLitterman,
        diagonal_cov: np.ndarray,
        instrument_names: list[str],
    ):
        """With low confidence and uncertain regime, posterior stays near equilibrium."""
        weights = np.array([1.0 / 3, 1.0 / 3, 1.0 / 3])
        equilibrium = bl.compute_equilibrium_returns(diagonal_cov, weights)

        # Agent has a view but very low confidence and uncertain regime
        views = [AgentView("ASSET_A", 0.10, 0.1, "agent_1")]
        P, Q, Omega = bl.build_views(views, instrument_names, 0.1, diagonal_cov)
        posterior_mu, _ = bl.posterior_returns(equilibrium, diagonal_cov, P, Q, Omega)

        # Posterior should be very close to equilibrium
        shift = abs(posterior_mu[0] - equilibrium[0])
        # The shift should be small relative to the view-equilibrium gap
        view_gap = abs(0.10 - equilibrium[0])
        assert shift < 0.3 * view_gap  # Less than 30% of the gap

    def test_single_view_shifts_only_target_instrument(
        self,
        bl: BlackLitterman,
        diagonal_cov: np.ndarray,
        instrument_names: list[str],
    ):
        """A view on ASSET_B should shift ASSET_B's posterior the most."""
        weights = np.array([1.0 / 3, 1.0 / 3, 1.0 / 3])
        equilibrium = bl.compute_equilibrium_returns(diagonal_cov, weights)

        views = [AgentView("ASSET_B", 0.08, 0.9, "agent_1")]
        P, Q, Omega = bl.build_views(views, instrument_names, 0.9, diagonal_cov)
        posterior_mu, _ = bl.posterior_returns(equilibrium, diagonal_cov, P, Q, Omega)

        # ASSET_B shift should be larger than shifts in ASSET_A or ASSET_C
        shift_b = abs(posterior_mu[1] - equilibrium[1])
        shift_a = abs(posterior_mu[0] - equilibrium[0])
        shift_c = abs(posterior_mu[2] - equilibrium[2])

        # For diagonal covariance, single-asset view shifts only that asset
        assert shift_b > shift_a
        assert shift_b > shift_c


# ---------------------------------------------------------------------------
# Tests: Full Pipeline (optimize)
# ---------------------------------------------------------------------------
class TestOptimizePipeline:
    def test_empty_views_returns_equilibrium(
        self,
        bl: BlackLitterman,
        diagonal_cov: np.ndarray,
        equal_weights: np.ndarray,
        instrument_names: list[str],
    ):
        """With no views, posterior returns == equilibrium returns."""
        result = bl.optimize(
            views=[],
            covariance=diagonal_cov,
            market_weights=equal_weights,
            instrument_names=instrument_names,
        )

        assert result["posterior_returns"] == result["equilibrium_returns"]
        assert result["regime_clarity"] == 1.0

    def test_full_pipeline_returns_all_keys(
        self,
        bl: BlackLitterman,
        diagonal_cov: np.ndarray,
        equal_weights: np.ndarray,
        instrument_names: list[str],
    ):
        """Full pipeline result contains expected keys."""
        views = [AgentView("ASSET_A", 0.05, 0.8, "agent_1")]
        result = bl.optimize(
            views=views,
            covariance=diagonal_cov,
            market_weights=equal_weights,
            instrument_names=instrument_names,
            regime_clarity=0.85,
        )

        assert "posterior_returns" in result
        assert "posterior_covariance" in result
        assert "equilibrium_returns" in result
        assert "regime_clarity" in result
        assert result["regime_clarity"] == 0.85
        assert len(result["posterior_returns"]) == 3
        assert len(result["equilibrium_returns"]) == 3

    def test_multiple_views(
        self,
        bl: BlackLitterman,
        diagonal_cov: np.ndarray,
        equal_weights: np.ndarray,
        instrument_names: list[str],
    ):
        """Multiple views from different agents."""
        views = [
            AgentView("ASSET_A", 0.06, 0.8, "agent_1"),
            AgentView("ASSET_C", -0.02, 0.7, "agent_2"),
        ]
        result = bl.optimize(
            views=views,
            covariance=diagonal_cov,
            market_weights=equal_weights,
            instrument_names=instrument_names,
            regime_clarity=0.8,
        )

        # ASSET_A should have higher posterior than equilibrium (bullish view)
        assert result["posterior_returns"]["ASSET_A"] > result["equilibrium_returns"]["ASSET_A"]
        # ASSET_C should have lower posterior than equilibrium (bearish view)
        assert result["posterior_returns"]["ASSET_C"] < result["equilibrium_returns"]["ASSET_C"]
