"""Tests for PortfolioConstructor: risk parity, conviction overlay, regime scaling.

All tests use synthetic data -- no database or external data required.
"""

from __future__ import annotations

import numpy as np

from src.core.enums import AssetClass, SignalDirection
from src.portfolio.portfolio_constructor import (
    PortfolioConstructor,
    PortfolioTarget,
    RegimeState,
    _risk_parity_weights,
)
from src.strategies.base import StrategyPosition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_position(
    strategy_id: str,
    instrument: str,
    weight: float,
    confidence: float = 0.80,
    direction: SignalDirection = SignalDirection.LONG,
    strength: str = "STRONG",
) -> StrategyPosition:
    """Create a test StrategyPosition."""
    return StrategyPosition(
        strategy_id=strategy_id,
        instrument=instrument,
        weight=weight,
        confidence=confidence,
        direction=direction,
        entry_signal=f"{strategy_id}_SIG",
        metadata={"strength": strength},
    )


def _make_equal_vol_returns(
    n_obs: int = 252,
    n_assets: int = 3,
    vol: float = 0.01,
    seed: int = 42,
) -> np.ndarray:
    """Create returns matrix with equal vol and zero correlation."""
    rng = np.random.RandomState(seed)
    return rng.normal(0, vol, (n_obs, n_assets))


def _make_unequal_vol_returns(
    n_obs: int = 252,
    seed: int = 42,
) -> np.ndarray:
    """Create returns for 3 assets with different vols: low, medium, high."""
    rng = np.random.RandomState(seed)
    r1 = rng.normal(0, 0.005, (n_obs, 1))  # low vol
    r2 = rng.normal(0, 0.015, (n_obs, 1))  # medium vol
    r3 = rng.normal(0, 0.030, (n_obs, 1))  # high vol
    return np.hstack([r1, r2, r3])


# ---------------------------------------------------------------------------
# Tests: Risk parity
# ---------------------------------------------------------------------------
class TestRiskParity:
    """Test risk-parity weight computation."""

    def test_risk_parity_equal_vol(self) -> None:
        """3 assets with equal vol and zero correlation -> approximately equal weights."""
        returns = _make_equal_vol_returns(n_obs=500, n_assets=3)
        from sklearn.covariance import LedoitWolf
        lw = LedoitWolf()
        lw.fit(returns)
        cov = lw.covariance_

        weights = _risk_parity_weights(cov)
        assert weights.shape == (3,)
        assert abs(np.sum(weights) - 1.0) < 1e-6
        # Equal vol => roughly equal weights
        for w in weights:
            assert abs(w - 1 / 3) < 0.05

    def test_risk_parity_unequal_vol(self) -> None:
        """Higher vol asset gets lower weight."""
        returns = _make_unequal_vol_returns(n_obs=500)
        from sklearn.covariance import LedoitWolf
        lw = LedoitWolf()
        lw.fit(returns)
        cov = lw.covariance_

        weights = _risk_parity_weights(cov)
        assert weights.shape == (3,)
        assert abs(np.sum(weights) - 1.0) < 1e-6
        # Low vol asset (idx 0) should have highest weight
        assert weights[0] > weights[1] > weights[2]

    def test_fallback_equal_weights_no_returns(self) -> None:
        """No returns_matrix -> equal weights."""
        pc = PortfolioConstructor()
        positions = {
            "RATES_BR_01": [
                _make_position("RATES_BR_01", "DI_PRE_365", 0.10),
                _make_position("RATES_BR_01", "DI_PRE_720", 0.08),
            ],
        }
        result = pc.construct(positions, returns_matrix=None)
        assert isinstance(result, PortfolioTarget)
        # Without returns, risk parity falls back to equal weights
        rp = result.risk_parity_weights
        n = len(rp)
        for v in rp.values():
            assert abs(abs(v) - 1 / n) < 0.01


# ---------------------------------------------------------------------------
# Tests: Conviction overlay
# ---------------------------------------------------------------------------
class TestConvictionOverlay:
    """Test conviction-based weight scaling."""

    def test_conviction_overlay_scales(self) -> None:
        """Higher conviction strategy gets larger weight relative to low conviction."""
        pc = PortfolioConstructor()

        positions = {
            "RATES_BR_01": [
                _make_position(
                    "RATES_BR_01", "INST_A", 0.15,
                    confidence=0.95, strength="STRONG",
                ),
            ],
            "RATES_BR_02": [
                _make_position(
                    "RATES_BR_02", "INST_B", 0.15,
                    confidence=0.30, strength="WEAK",
                ),
            ],
        }

        result = pc.construct(positions, returns_matrix=None)
        # After conviction overlay: INST_A (high confidence * STRONG) should
        # have a larger conviction weight than INST_B (low confidence * WEAK)
        conv = result.conviction_weights
        # Before re-normalization, the ratio should favor INST_A
        # After re-normalization, the total abs weight is preserved but
        # INST_A gets a larger share
        assert abs(conv["INST_A"]) > abs(conv["INST_B"])


# ---------------------------------------------------------------------------
# Tests: Regime scaling
# ---------------------------------------------------------------------------
class TestRegimeScaling:
    """Test regime classification and scaling."""

    def test_regime_scaling_risk_on(self) -> None:
        """regime_score < -0.3 -> scale=1.0 (RISK_ON)."""
        pc = PortfolioConstructor()
        positions = {
            "RATES_BR_01": [
                _make_position("RATES_BR_01", "DI_PRE_365", 0.20),
            ],
        }
        result = pc.construct(positions, regime_score=-0.5)
        assert result.regime == RegimeState.RISK_ON
        assert result.regime_scale == 1.0

    def test_regime_scaling_risk_off(self) -> None:
        """regime_score > 0.3 -> scale=0.4 (RISK_OFF)."""
        pc = PortfolioConstructor()
        positions = {
            "RATES_BR_01": [
                _make_position("RATES_BR_01", "DI_PRE_365", 0.20),
            ],
        }
        result = pc.construct(positions, regime_score=0.5)
        assert result.regime == RegimeState.RISK_OFF
        assert result.regime_scale == 0.4

    def test_regime_scaling_neutral(self) -> None:
        """regime_score ~0.0 -> scale=0.7 (NEUTRAL)."""
        pc = PortfolioConstructor()
        positions = {
            "RATES_BR_01": [
                _make_position("RATES_BR_01", "DI_PRE_365", 0.20),
            ],
        }
        result = pc.construct(positions, regime_score=0.0)
        assert result.regime == RegimeState.NEUTRAL
        assert result.regime_scale == 0.7

    def test_regime_transition_gradual(self) -> None:
        """Regime change applies partial scale on day 1 (not instant)."""
        pc = PortfolioConstructor(transition_days=3)
        positions = {
            "RATES_BR_01": [
                _make_position("RATES_BR_01", "DI_PRE_365", 0.20),
            ],
        }

        # First call: RISK_ON (scale=1.0)
        result1 = pc.construct(positions, regime_score=-0.5)
        assert result1.regime == RegimeState.RISK_ON
        assert result1.regime_scale == 1.0

        # Second call: RISK_OFF (should NOT jump to 0.4 immediately)
        result2 = pc.construct(positions, regime_score=0.5)
        assert result2.regime == RegimeState.RISK_OFF
        # Day 1 of 3 transition: scale = 1.0 + (0.4 - 1.0) * (1/3) = 0.8
        assert abs(result2.regime_scale - 0.8) < 0.05

        # Third call: still RISK_OFF day 2
        result3 = pc.construct(positions, regime_score=0.5)
        # Day 2 of 3: scale = 1.0 + (0.4 - 1.0) * (2/3) = 0.6
        assert abs(result3.regime_scale - 0.6) < 0.05

        # Fourth call: transition complete
        result4 = pc.construct(positions, regime_score=0.5)
        # Day 3 of 3: scale = 0.4
        assert abs(result4.regime_scale - 0.4) < 0.05


# ---------------------------------------------------------------------------
# Tests: Conflict dampening
# ---------------------------------------------------------------------------
class TestConflictDampening:
    """Test weight reduction for conflicted asset classes."""

    def test_conflict_dampening(self) -> None:
        """Conflicted asset class positions reduced by ~40%."""
        pc = PortfolioConstructor(conflict_dampening=0.60)

        positions = {
            "RATES_BR_01": [
                _make_position("RATES_BR_01", "DI_PRE_365", 0.20),
            ],
        }

        conflicts = {AssetClass.FIXED_INCOME: ["RATES_BR_01 vs RATES_BR_02"]}

        # Construct with no regime scaling (regime_score=-0.5 -> RISK_ON -> 1.0x)
        result = pc.construct(
            positions,
            regime_score=-0.5,
            conflicts=conflicts,
        )

        # The DI_PRE_365 weight should be dampened relative to no conflicts
        result_no_conflict = pc.construct(
            positions,
            regime_score=-0.5,
            conflicts={},
        )

        # Dampened weight should be ~60% of undampened weight
        dampened_w = abs(result.weights.get("DI_PRE_365", 0.0))
        undampened_w = abs(result_no_conflict.weights.get("DI_PRE_365", 0.0))
        if undampened_w > 0:
            ratio = dampened_w / undampened_w
            assert abs(ratio - 0.60) < 0.05, f"Expected ~0.60 ratio, got {ratio:.3f}"
