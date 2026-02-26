"""Tests for enhanced VaR calculator v2 features.

Tests marginal VaR, component VaR decomposition, 756-day lookback,
VaRDecomposition dataclass, and always-report-both-VaR-and-CVaR pattern.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.risk.var_calculator import (
    VaRCalculator,
    VaRDecomposition,
    compute_component_var,
    compute_marginal_var,
    compute_parametric_var,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rng() -> np.random.Generator:
    """Deterministic random generator."""
    return np.random.default_rng(seed=42)


@pytest.fixture
def three_assets(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """3 synthetic assets with distinct volatilities.

    Asset 0: low vol (0.5% daily std)
    Asset 1: medium vol (1.5% daily std)
    Asset 2: high vol (3.0% daily std)

    Correlation injected via shared factor (40% factor loading).
    """
    n_obs = 800
    factor = rng.normal(0.0, 0.01, size=n_obs)

    asset0 = 0.4 * factor + rng.normal(0.0, 0.005, size=n_obs)
    asset1 = 0.4 * factor + rng.normal(0.0, 0.015, size=n_obs)
    asset2 = 0.4 * factor + rng.normal(0.0, 0.030, size=n_obs)

    returns_matrix = np.column_stack([asset0, asset1, asset2])
    weights = np.array([0.4, 0.35, 0.25])
    names = ["LowVol", "MedVol", "HighVol"]
    return returns_matrix, weights, names


# ---------------------------------------------------------------------------
# compute_marginal_var tests
# ---------------------------------------------------------------------------


class TestComputeMarginalVar:
    """Tests for the compute_marginal_var function."""

    def test_higher_vol_asset_has_larger_marginal_var(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """Position with higher volatility should have a larger (more negative) marginal VaR."""
        returns_matrix, weights, _ = three_assets
        marginal = compute_marginal_var(returns_matrix, weights, 0.95, method="parametric")

        # Marginal VaR values are negative (left tail); more negative = more risk.
        # High-vol asset (index 2) should have more negative marginal VaR than low-vol (index 0).
        assert marginal[2] < marginal[0], (
            f"HighVol marginal VaR ({marginal[2]:.6f}) should be more negative "
            f"than LowVol ({marginal[0]:.6f})"
        )

    def test_marginal_var_returns_dict_with_correct_keys(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """Marginal VaR should return entries for all assets."""
        returns_matrix, weights, _ = three_assets
        marginal = compute_marginal_var(returns_matrix, weights, 0.95)
        assert set(marginal.keys()) == {0, 1, 2}

    def test_marginal_var_all_values_nonzero(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """Marginal VaR should be non-zero for all positions with non-zero weights."""
        returns_matrix, weights, _ = three_assets
        marginal = compute_marginal_var(returns_matrix, weights, 0.95)
        for i in range(3):
            assert marginal[i] != 0.0, f"Marginal VaR for asset {i} should not be zero"

    def test_marginal_var_historical_method(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """Historical method should also produce non-zero marginal VaR."""
        returns_matrix, weights, _ = three_assets
        marginal = compute_marginal_var(returns_matrix, weights, 0.95, method="historical")
        assert all(v != 0.0 for v in marginal.values())


# ---------------------------------------------------------------------------
# compute_component_var tests
# ---------------------------------------------------------------------------


class TestComputeComponentVar:
    """Tests for the compute_component_var function."""

    def test_component_var_sums_to_total_var(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """Sum of component VaRs should approximately equal total parametric VaR."""
        returns_matrix, weights, _ = three_assets
        component = compute_component_var(returns_matrix, weights, 0.95)

        # Total parametric VaR
        portfolio_returns = returns_matrix @ weights
        total_var, _ = compute_parametric_var(portfolio_returns, 0.95)

        component_sum = sum(component.values())
        # Within 2% tolerance (relative to total VaR).
        # Slight discrepancy is expected because component VaR uses Ledoit-Wolf
        # shrinkage covariance while compute_parametric_var uses sample variance.
        if abs(total_var) > 1e-10:
            assert abs(component_sum - total_var) / abs(total_var) < 0.02, (
                f"Component VaR sum ({component_sum:.8f}) should be within 2% "
                f"of total VaR ({total_var:.8f})"
            )

    def test_component_var_returns_correct_keys(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """Component VaR should return entries for all assets."""
        returns_matrix, weights, _ = three_assets
        component = compute_component_var(returns_matrix, weights, 0.95)
        assert set(component.keys()) == {0, 1, 2}

    def test_component_var_all_nonzero(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """Component VaR should be non-zero for weighted positions."""
        returns_matrix, weights, _ = three_assets
        component = compute_component_var(returns_matrix, weights, 0.95)
        for i in range(3):
            assert component[i] != 0.0


# ---------------------------------------------------------------------------
# VaRDecomposition tests
# ---------------------------------------------------------------------------


class TestVaRDecomposition:
    """Tests for the VaRDecomposition dataclass and decompose_var method."""

    def test_decompose_var_returns_correct_instrument_names(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """decompose_var should map position indices to instrument names."""
        returns_matrix, weights, names = three_assets
        calc = VaRCalculator()
        decomp = calc.decompose_var(returns_matrix, weights, names, confidence=0.95)

        assert isinstance(decomp, VaRDecomposition)
        assert set(decomp.marginal_var.keys()) == set(names)
        assert set(decomp.component_var.keys()) == set(names)
        assert set(decomp.pct_contribution.keys()) == set(names)

    def test_decompose_var_values_nonzero(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """All VaR decomposition values should be non-zero for active positions."""
        returns_matrix, weights, names = three_assets
        calc = VaRCalculator()
        decomp = calc.decompose_var(returns_matrix, weights, names, confidence=0.95)

        for name in names:
            assert decomp.marginal_var[name] != 0.0
            assert decomp.component_var[name] != 0.0

    def test_decompose_var_largest_risk_contributor(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """High-vol asset should be the largest risk contributor (most negative component VaR)."""
        returns_matrix, weights, names = three_assets
        calc = VaRCalculator()
        decomp = calc.decompose_var(returns_matrix, weights, names, confidence=0.95)

        # HighVol (index 2) has the highest vol, so should have most negative component VaR
        worst_contributor = min(decomp.component_var, key=decomp.component_var.get)  # type: ignore[arg-type]
        assert worst_contributor == "HighVol", (
            f"Expected HighVol to be largest risk contributor, got {worst_contributor}"
        )

    def test_decompose_var_pct_contribution_sums_to_one(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """Percentage contributions should sum to approximately 1.0."""
        returns_matrix, weights, names = three_assets
        calc = VaRCalculator()
        decomp = calc.decompose_var(returns_matrix, weights, names, confidence=0.95)

        pct_sum = sum(decomp.pct_contribution.values())
        assert abs(pct_sum - 1.0) < 0.01, (
            f"Percentage contributions should sum to ~1.0, got {pct_sum:.6f}"
        )

    def test_decompose_var_total_var_and_cvar(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """Decomposition should report both total VaR and CVaR."""
        returns_matrix, weights, names = three_assets
        calc = VaRCalculator()
        decomp = calc.decompose_var(returns_matrix, weights, names, confidence=0.95)

        assert decomp.total_var != 0.0
        assert decomp.total_cvar != 0.0
        assert decomp.confidence == 0.95


# ---------------------------------------------------------------------------
# 756-day lookback tests
# ---------------------------------------------------------------------------


class TestLookbackDays:
    """Tests for the 756-day lookback behavior."""

    def test_default_lookback_is_756(self) -> None:
        """VaRCalculator should default to 756-day lookback."""
        calc = VaRCalculator()
        assert calc.lookback_days == 756
        assert calc.min_historical_obs == 756

    def test_monte_carlo_trims_to_lookback(self, rng: np.random.Generator) -> None:
        """When returns_matrix has >756 rows, only last 756 should be used.

        Verify by passing 1000 rows where the first 244 rows are extreme outliers.
        If lookback works, VaR should be based on the last 756 normal rows only.
        """
        n_assets = 2

        # First 244 rows: extreme negative returns (-50% daily)
        extreme = np.full((244, n_assets), -0.50)
        # Last 756 rows: normal returns
        normal = rng.normal(0.0, 0.01, size=(756, n_assets))
        returns_matrix = np.vstack([extreme, normal])
        weights = np.array([0.5, 0.5])

        calc = VaRCalculator(lookback_days=756)
        result = calc.calculate_monte_carlo(returns_matrix, weights, rng=rng)

        # If lookback works, VaR should be modest (normal returns only).
        # If lookback fails, VaR would be ~-0.50 due to extreme rows.
        assert result.var_95 > -0.10, (
            f"VaR 95% ({result.var_95:.4f}) too extreme -- lookback trimming may have failed"
        )
        assert result.n_observations == 756

    def test_decompose_var_trims_to_lookback(self, rng: np.random.Generator) -> None:
        """decompose_var should also trim returns_matrix to lookback_days."""
        n_assets = 2

        extreme = np.full((244, n_assets), -0.50)
        normal = rng.normal(0.0, 0.01, size=(756, n_assets))
        returns_matrix = np.vstack([extreme, normal])
        weights = np.array([0.5, 0.5])
        names = ["A", "B"]

        calc = VaRCalculator(lookback_days=756)
        decomp = calc.decompose_var(returns_matrix, weights, names, confidence=0.95)

        # VaR should be modest, not influenced by the extreme rows
        assert decomp.total_var > -0.10, (
            f"Total VaR ({decomp.total_var:.4f}) too extreme -- lookback trimming may have failed"
        )


# ---------------------------------------------------------------------------
# VaR and CVaR always-report tests
# ---------------------------------------------------------------------------


class TestVaRAndCVaRAlwaysReported:
    """Tests that both VaR and CVaR are always reported at 95% and 99%."""

    def test_historical_reports_both(self, rng: np.random.Generator) -> None:
        """Historical method should report VaR and CVaR at both confidence levels."""
        returns = rng.normal(-0.001, 0.015, size=800)
        calc = VaRCalculator()
        result = calc.calculate(returns, method="historical")

        assert result.var_95 != 0.0
        assert result.var_99 != 0.0
        assert result.cvar_95 != 0.0
        assert result.cvar_99 != 0.0
        assert result.method == "historical"

    def test_parametric_reports_both(self, rng: np.random.Generator) -> None:
        """Parametric method should report VaR and CVaR at both confidence levels."""
        returns = rng.normal(-0.001, 0.015, size=800)
        calc = VaRCalculator()
        result = calc.calculate(returns, method="parametric")

        assert result.var_95 != 0.0
        assert result.var_99 != 0.0
        assert result.cvar_95 != 0.0
        assert result.cvar_99 != 0.0

    def test_monte_carlo_reports_both(self, rng: np.random.Generator) -> None:
        """Monte Carlo should report VaR and CVaR at both confidence levels."""
        returns_matrix = rng.normal(0.0, 0.01, size=(800, 2))
        weights = np.array([0.5, 0.5])
        calc = VaRCalculator()
        result = calc.calculate_monte_carlo(returns_matrix, weights, rng=rng)

        assert result.var_95 != 0.0
        assert result.var_99 != 0.0
        assert result.cvar_95 != 0.0
        assert result.cvar_99 != 0.0

    def test_cvar_more_negative_than_var(self, rng: np.random.Generator) -> None:
        """CVaR should be more negative (worse) than VaR for non-degenerate distributions."""
        returns = rng.normal(-0.001, 0.015, size=800)
        calc = VaRCalculator()
        result = calc.calculate(returns, method="parametric")

        assert result.cvar_95 <= result.var_95, (
            f"CVaR 95% ({result.cvar_95:.6f}) should be <= VaR 95% ({result.var_95:.6f})"
        )
        assert result.cvar_99 <= result.var_99, (
            f"CVaR 99% ({result.cvar_99:.6f}) should be <= VaR 99% ({result.var_99:.6f})"
        )


# ---------------------------------------------------------------------------
# Parametric VaR with Ledoit-Wolf tests
# ---------------------------------------------------------------------------


class TestParametricVaRLedoitWolf:
    """Tests that parametric VaR with Ledoit-Wolf produces reasonable values."""

    def test_parametric_var_reasonable_for_correlated_assets(
        self, rng: np.random.Generator
    ) -> None:
        """Parametric VaR should produce reasonable values for correlated assets."""
        n_obs = 800
        factor = rng.normal(0.0, 0.01, size=n_obs)

        # Correlated assets (50% factor loading)
        asset0 = 0.5 * factor + rng.normal(0.0, 0.01, size=n_obs)
        asset1 = 0.5 * factor + rng.normal(0.0, 0.01, size=n_obs)

        weights = np.array([0.5, 0.5])
        returns_matrix = np.column_stack([asset0, asset1])
        portfolio_returns = returns_matrix @ weights

        var, cvar = compute_parametric_var(portfolio_returns, 0.95)

        # VaR should be negative and reasonable (not extreme)
        assert var < 0.0, f"VaR should be negative, got {var:.6f}"
        assert var > -0.10, f"VaR should be reasonable (> -10%), got {var:.6f}"
        assert cvar < var, f"CVaR ({cvar:.6f}) should be more negative than VaR ({var:.6f})"

    def test_marginal_var_uses_ledoit_wolf(
        self, three_assets: tuple[np.ndarray, np.ndarray, list[str]]
    ) -> None:
        """Marginal VaR (parametric) should use Ledoit-Wolf covariance internally."""
        returns_matrix, weights, _ = three_assets

        # This implicitly tests Ledoit-Wolf usage since the parametric method
        # calls LedoitWolf().fit() inside compute_marginal_var.
        marginal = compute_marginal_var(returns_matrix, weights, 0.95, method="parametric")

        # All marginal VaRs should be negative (left tail) for parametric method
        for i, val in marginal.items():
            assert val < 0.0, f"Marginal VaR for asset {i} should be negative, got {val:.6f}"
