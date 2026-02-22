"""Tests for CapitalAllocator: constraint enforcement, drift threshold, trades.

All tests use synthetic portfolio targets -- no database or external data required.
"""

from __future__ import annotations

import numpy as np

from src.core.enums import AssetClass
from src.portfolio.capital_allocator import (
    AllocationConstraints,
    CapitalAllocator,
)
from src.portfolio.portfolio_constructor import PortfolioTarget, RegimeState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_target(weights: dict[str, float]) -> PortfolioTarget:
    """Create a minimal PortfolioTarget for testing."""
    return PortfolioTarget(
        weights=weights,
        regime=RegimeState.NEUTRAL,
        regime_scale=0.7,
        conflicts={},
        risk_parity_weights=dict(weights),
        conviction_weights=dict(weights),
    )


# ---------------------------------------------------------------------------
# Tests: Leverage cap
# ---------------------------------------------------------------------------
class TestLeverageCap:
    """Test leverage limit enforcement."""

    def test_leverage_cap(self) -> None:
        """Weights exceeding 3x scaled down proportionally."""
        allocator = CapitalAllocator()
        # Each position <= 0.25 (passes single position cap)
        # Total abs = 0.25*16 = 4.0 > 3.0 (triggers leverage cap)
        weights = {f"INST_{i:02d}": 0.25 for i in range(16)}
        target = _make_target(weights)
        result = allocator.allocate(target)

        assert result.leverage_used <= 3.0 + 1e-9
        assert any("Leverage" in v for v in result.constraint_violations)


# ---------------------------------------------------------------------------
# Tests: Single position cap
# ---------------------------------------------------------------------------
class TestSinglePositionCap:
    """Test single position size constraint."""

    def test_single_position_cap(self) -> None:
        """Weight > 0.25 clamped to 0.25."""
        allocator = CapitalAllocator()
        target = _make_target({"INST_A": 0.40, "INST_B": -0.30})
        result = allocator.allocate(target)

        assert abs(result.target_weights["INST_A"]) <= 0.25 + 1e-9
        assert abs(result.target_weights["INST_B"]) <= 0.25 + 1e-9
        assert any("clamped" in v for v in result.constraint_violations)


# ---------------------------------------------------------------------------
# Tests: Asset class concentration
# ---------------------------------------------------------------------------
class TestAssetClassConcentration:
    """Test asset class exposure limit."""

    def test_asset_class_concentration(self) -> None:
        """FI weights > 50% scaled to 50%."""
        allocator = CapitalAllocator()
        target = _make_target({
            "DI_PRE_365": 0.25,
            "DI_PRE_720": 0.25,
            "DI_PRE_1080": 0.20,
        })
        inst_ac = {
            "DI_PRE_365": AssetClass.FIXED_INCOME,
            "DI_PRE_720": AssetClass.FIXED_INCOME,
            "DI_PRE_1080": AssetClass.FIXED_INCOME,
        }
        result = allocator.allocate(
            target, instrument_to_asset_class=inst_ac,
        )

        fi_exposure = result.asset_class_exposure.get("FIXED_INCOME", 0.0)
        assert fi_exposure <= 0.50 + 1e-9
        assert any("FIXED_INCOME" in v for v in result.constraint_violations)


# ---------------------------------------------------------------------------
# Tests: Drift threshold
# ---------------------------------------------------------------------------
class TestDriftThreshold:
    """Test drift-triggered rebalancing."""

    def test_drift_below_threshold_no_rebalance(self) -> None:
        """Drift < 5% -> rebalance_needed=False."""
        allocator = CapitalAllocator()
        target = _make_target({"INST_A": 0.12, "INST_B": 0.08})
        current = {"INST_A": 0.10, "INST_B": 0.07}

        result = allocator.allocate(target, current_weights=current)
        assert result.rebalance_needed is False
        assert result.trades == {}

    def test_drift_above_threshold_rebalance(self) -> None:
        """Drift > 5% -> rebalance_needed=True."""
        allocator = CapitalAllocator()
        target = _make_target({"INST_A": 0.20, "INST_B": 0.05})
        current = {"INST_A": 0.10, "INST_B": 0.05}

        result = allocator.allocate(target, current_weights=current)
        assert result.rebalance_needed is True
        assert len(result.trades) > 0


# ---------------------------------------------------------------------------
# Tests: Trade computation
# ---------------------------------------------------------------------------
class TestTradeComputation:
    """Test correct delta between target and current weights."""

    def test_trade_computation(self) -> None:
        """trades[inst] = target - current."""
        allocator = CapitalAllocator()
        target = _make_target({"INST_A": 0.20, "INST_B": -0.10})
        current = {"INST_A": 0.10, "INST_B": 0.0}

        result = allocator.allocate(target, current_weights=current)
        assert result.rebalance_needed is True
        assert abs(result.trades.get("INST_A", 0.0) - 0.10) < 1e-6
        assert abs(result.trades.get("INST_B", 0.0) - (-0.10)) < 1e-6

    def test_min_trade_filter(self) -> None:
        """Tiny trades (below min_trade_notional / ref_equity) are filtered out."""
        constraints = AllocationConstraints(min_trade_notional=50_000.0)
        allocator = CapitalAllocator(constraints=constraints)
        # min_delta = 50_000 / 1_000_000 = 0.05
        # Trade of 0.01 should be filtered
        target = _make_target({"INST_A": 0.20, "INST_B": 0.01})
        current = {"INST_A": 0.10, "INST_B": 0.0}

        result = allocator.allocate(target, current_weights=current)
        # INST_A delta = 0.10 (above 0.05) -> included
        # INST_B delta = 0.01 (below 0.05) -> filtered
        assert "INST_A" in result.trades
        assert "INST_B" not in result.trades


# ---------------------------------------------------------------------------
# Tests: Risk budget check
# ---------------------------------------------------------------------------
class TestRiskBudget:
    """Test risk budget violation detection."""

    def test_risk_budget_violation_detected(self) -> None:
        """Position contributing > 20% risk flagged."""
        allocator = CapitalAllocator()

        # Build a covariance where INST_A dominates risk
        # 3 instruments with very unequal variance
        cov = np.array([
            [0.04, 0.001, 0.001],
            [0.001, 0.0004, 0.0001],
            [0.001, 0.0001, 0.0004],
        ])
        instruments = ["INST_A", "INST_B", "INST_C"]
        # Heavy weight on high-variance asset
        weights = {"INST_A": 0.60, "INST_B": 0.20, "INST_C": 0.20}

        violations = allocator.check_risk_budget(
            weights, cov, instruments,
        )
        assert len(violations) > 0
        assert any("INST_A" in v for v in violations)

    def test_all_constraints_pass(self) -> None:
        """Well-balanced portfolio passes all checks."""
        allocator = CapitalAllocator()
        target = _make_target({"INST_A": 0.15, "INST_B": 0.10, "INST_C": -0.08})
        result = allocator.allocate(target)

        # These weights are all within constraints
        assert result.leverage_used <= 3.0
        assert all(abs(w) <= 0.25 for w in result.target_weights.values())
        assert len(result.constraint_violations) == 0
