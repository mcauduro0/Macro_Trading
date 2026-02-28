"""Unit tests for VaR and CVaR computation across all methods.

Covers historical VaR, parametric VaR, Monte Carlo VaR (with Student-t
marginals and Cholesky correlation), CVaR/Expected Shortfall, short-history
fallback, singular covariance handling, and edge cases.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from src.risk.var_calculator import (
    VaRCalculator,
    VaRResult,
    compute_historical_var,
    compute_monte_carlo_var,
    compute_parametric_var,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def known_returns() -> np.ndarray:
    """100 deterministic returns with a known distribution.

    Built from a mix of small gains and occasional larger losses so that
    the 5th percentile (VaR_95) is predictable.
    """
    rng = np.random.default_rng(seed=12345)
    returns = rng.normal(loc=0.0005, scale=0.01, size=100)
    # Inject a few known tail losses for determinism
    returns[0] = -0.035
    returns[10] = -0.040
    returns[20] = -0.030
    returns[30] = -0.028
    returns[40] = -0.025
    return returns


@pytest.fixture
def large_returns() -> np.ndarray:
    """500 returns — enough for historical VaR without fallback."""
    rng = np.random.default_rng(seed=99999)
    return rng.normal(loc=0.0002, scale=0.012, size=500)


@pytest.fixture
def returns_matrix_3_assets() -> np.ndarray:
    """(250, 3) returns matrix for Monte Carlo VaR testing."""
    rng = np.random.default_rng(seed=777)
    # Three correlated assets via simple factor model
    factor = rng.normal(0.0, 0.008, size=250)
    idio = rng.normal(0.0, 0.005, size=(250, 3))
    loadings = np.array([0.8, 0.6, 0.4])
    returns = factor[:, np.newaxis] * loadings[np.newaxis, :] + idio
    return returns


# ---------------------------------------------------------------------------
# Historical VaR tests
# ---------------------------------------------------------------------------


class TestHistoricalVar:
    def test_historical_var_known_values(self, known_returns: np.ndarray) -> None:
        """VaR should match np.percentile of the return series."""
        var, cvar = compute_historical_var(known_returns, confidence=0.95)

        expected_var = float(np.percentile(known_returns, 5.0))
        assert abs(var - expected_var) < 1e-10, f"VaR mismatch: {var} vs {expected_var}"
        assert var < 0, "VaR should be negative (loss)"

    def test_historical_cvar_is_tail_mean(self, known_returns: np.ndarray) -> None:
        """CVaR should be the mean of returns at or below VaR."""
        var, cvar = compute_historical_var(known_returns, confidence=0.95)

        tail = known_returns[known_returns <= var]
        expected_cvar = float(tail.mean()) if len(tail) > 0 else var
        assert abs(cvar - expected_cvar) < 1e-10

    def test_historical_cvar_worse_than_var(self, known_returns: np.ndarray) -> None:
        """CVaR magnitude should be >= VaR magnitude (more negative)."""
        var, cvar = compute_historical_var(known_returns, confidence=0.95)
        assert cvar <= var, f"CVaR ({cvar}) should be <= VaR ({var})"

    def test_var_empty_returns(self) -> None:
        """Empty array should return (0.0, 0.0)."""
        var, cvar = compute_historical_var(np.array([]))
        assert var == 0.0
        assert cvar == 0.0

    def test_var_too_few_observations(self) -> None:
        """Fewer than 10 observations should return (0.0, 0.0)."""
        var, cvar = compute_historical_var(np.array([0.01, -0.02, 0.005]))
        assert var == 0.0
        assert cvar == 0.0


# ---------------------------------------------------------------------------
# Parametric VaR tests
# ---------------------------------------------------------------------------


class TestParametricVar:
    def test_parametric_var_standard_normal(self) -> None:
        """For N(0, 0.01) returns, VaR_95 should be ~ -0.0165."""
        rng = np.random.default_rng(seed=42)
        returns = rng.normal(loc=0.0, scale=0.01, size=10000)

        var, cvar = compute_parametric_var(returns, confidence=0.95)

        # Analytical VaR_95 for N(0, 0.01): 0 + 0.01 * (-1.645) = -0.01645
        assert abs(var - (-0.01645)) < 0.002, f"Parametric VaR: {var}"
        assert var < 0

    def test_parametric_cvar_below_var(self) -> None:
        """CVaR magnitude should be > VaR magnitude for Gaussian."""
        rng = np.random.default_rng(seed=42)
        returns = rng.normal(loc=0.0, scale=0.01, size=10000)

        var, cvar = compute_parametric_var(returns, confidence=0.95)

        assert cvar < var, f"CVaR ({cvar}) should be more negative than VaR ({var})"

    def test_parametric_var_with_mean(self) -> None:
        """Positive mean should shift VaR less negative."""
        rng = np.random.default_rng(seed=42)
        returns_zero = rng.normal(loc=0.0, scale=0.01, size=5000)
        rng2 = np.random.default_rng(seed=42)
        returns_pos = rng2.normal(loc=0.001, scale=0.01, size=5000)

        var_zero, _ = compute_parametric_var(returns_zero, 0.95)
        var_pos, _ = compute_parametric_var(returns_pos, 0.95)

        assert var_pos > var_zero, "Positive mean should result in less negative VaR"

    def test_parametric_var_tiny_std(self) -> None:
        """Near-zero standard deviation should return (0.0, 0.0)."""
        returns = np.full(100, 0.001)  # constant returns
        var, cvar = compute_parametric_var(returns, 0.95)
        assert var == 0.0
        assert cvar == 0.0


# ---------------------------------------------------------------------------
# Monte Carlo VaR tests
# ---------------------------------------------------------------------------


class TestMonteCarloVar:
    def test_monte_carlo_var_produces_result(
        self, returns_matrix_3_assets: np.ndarray
    ) -> None:
        """MC VaR should produce a negative VaR value."""
        weights = np.array([0.4, 0.3, 0.3])
        rng = np.random.default_rng(seed=42)

        var, cvar = compute_monte_carlo_var(
            returns_matrix_3_assets, weights, 0.95, 10_000, rng=rng
        )

        assert var < 0, f"MC VaR should be negative, got {var}"
        assert isinstance(var, float)
        assert isinstance(cvar, float)

    def test_monte_carlo_cvar_worse_than_var(
        self, returns_matrix_3_assets: np.ndarray
    ) -> None:
        """CVaR should be <= VaR (more negative = worse)."""
        weights = np.array([0.4, 0.3, 0.3])
        rng = np.random.default_rng(seed=42)

        var, cvar = compute_monte_carlo_var(
            returns_matrix_3_assets, weights, 0.95, 10_000, rng=rng
        )

        assert cvar <= var, f"CVaR ({cvar}) should be <= VaR ({var})"

    def test_monte_carlo_singular_covariance(self) -> None:
        """Near-singular returns matrix should not crash (eigenvalue floor)."""
        rng = np.random.default_rng(seed=42)
        # Create a nearly singular matrix: col 2 = col 0 + tiny noise
        base = rng.normal(0.0, 0.01, size=(100, 2))
        col3 = base[:, 0] + rng.normal(0.0, 1e-8, size=100)
        returns_matrix = np.column_stack([base, col3[:, np.newaxis]])
        weights = np.array([0.4, 0.3, 0.3])

        # Should not raise -- eigenvalue floor handles it
        var, cvar = compute_monte_carlo_var(
            returns_matrix, weights, 0.95, 5_000, rng=rng
        )
        assert isinstance(var, float)
        assert isinstance(cvar, float)

    def test_monte_carlo_reproducibility(
        self, returns_matrix_3_assets: np.ndarray
    ) -> None:
        """Same seed should produce identical results."""
        weights = np.array([0.4, 0.3, 0.3])

        rng1 = np.random.default_rng(seed=42)
        var1, cvar1 = compute_monte_carlo_var(
            returns_matrix_3_assets, weights, 0.95, 5_000, rng=rng1
        )

        rng2 = np.random.default_rng(seed=42)
        var2, cvar2 = compute_monte_carlo_var(
            returns_matrix_3_assets, weights, 0.95, 5_000, rng=rng2
        )

        assert var1 == var2
        assert cvar1 == cvar2


# ---------------------------------------------------------------------------
# VaRCalculator orchestrator tests
# ---------------------------------------------------------------------------


class TestVaRCalculator:
    def test_historical_fallback_short_history(self) -> None:
        """100 observations (< 252) should fall back to parametric with warning."""
        rng = np.random.default_rng(seed=42)
        returns = rng.normal(0.0, 0.01, size=100)

        calc = VaRCalculator(min_historical_obs=252)
        result = calc.calculate(returns, method="historical")

        assert result.method == "parametric", "Should fall back to parametric"
        assert result.confidence_warning is not None
        assert "Insufficient" in result.confidence_warning

    def test_calculate_all_methods(self, large_returns: np.ndarray) -> None:
        """Returns dict with 'historical' and 'parametric'. Monte Carlo if matrix provided."""
        calc = VaRCalculator(min_historical_obs=252)
        results = calc.calculate_all_methods(large_returns)

        assert "historical" in results
        assert "parametric" in results
        assert "monte_carlo" not in results

    def test_calculate_all_methods_with_monte_carlo(
        self, large_returns: np.ndarray, returns_matrix_3_assets: np.ndarray
    ) -> None:
        """Monte Carlo included when returns_matrix and weights provided."""
        calc = VaRCalculator(min_historical_obs=252, mc_simulations=2_000)
        weights = np.array([0.4, 0.3, 0.3])
        rng = np.random.default_rng(seed=42)

        results = calc.calculate_all_methods(
            large_returns, returns_matrix_3_assets, weights, rng=rng
        )

        assert "historical" in results
        assert "parametric" in results
        assert "monte_carlo" in results
        assert results["monte_carlo"].method == "monte_carlo"

    def test_var_99_more_extreme_than_95(self, large_returns: np.ndarray) -> None:
        """|VaR_99| > |VaR_95| for non-trivial returns."""
        calc = VaRCalculator(min_historical_obs=252)
        result = calc.calculate(large_returns, method="historical")

        assert abs(result.var_99) > abs(
            result.var_95
        ), f"|VaR_99| ({abs(result.var_99)}) should > |VaR_95| ({abs(result.var_95)})"

    def test_cvar_more_extreme_than_var_all_methods(
        self, large_returns: np.ndarray
    ) -> None:
        """CVaR should be more extreme (more negative) than VaR for all methods."""
        calc = VaRCalculator(min_historical_obs=252)

        for method in ["historical", "parametric"]:
            result = calc.calculate(large_returns, method=method)
            assert (
                result.cvar_95 <= result.var_95
            ), f"{method}: CVaR_95 ({result.cvar_95}) should be <= VaR_95 ({result.var_95})"
            assert (
                result.cvar_99 <= result.var_99
            ), f"{method}: CVaR_99 ({result.cvar_99}) should be <= VaR_99 ({result.var_99})"

    def test_var_result_fields(self, large_returns: np.ndarray) -> None:
        """VaRResult should have all expected fields populated.

        With 500 observations < default min_historical_obs=756,
        historical method falls back to parametric with a warning.
        """
        calc = VaRCalculator()
        result = calc.calculate(large_returns, method="historical")

        assert isinstance(result, VaRResult)
        # Falls back to parametric because 500 < 756 min_historical_obs
        assert result.method == "parametric"
        assert result.n_observations == len(large_returns)
        assert result.confidence_warning is not None
        assert "Insufficient" in result.confidence_warning
        assert isinstance(result.timestamp, datetime)
        assert result.var_95 < 0
        assert result.var_99 < 0


# Run with: python -m pytest tests/test_risk/test_var_calculator.py -v
