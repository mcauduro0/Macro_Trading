"""Portfolio construction: risk parity + conviction overlay + regime scaling.

PortfolioConstructor converts strategy positions into target portfolio weights
via a multi-stage pipeline:
1. Flatten positions into net weights per instrument.
2. Compute risk-parity base weights (Ledoit-Wolf covariance, SLSQP optimizer).
3. Apply conviction overlay based on strategy signal strength & confidence.
4. Dampen conflicted asset class weights.
5. Apply regime-dependent scaling with gradual transitions.

This module is pure computation -- no database or I/O access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import numpy as np
import structlog
from scipy.optimize import minimize

from src.core.enums import AssetClass, SignalStrength
from src.strategies.base import STRENGTH_MAP, StrategyPosition

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Regime
# ---------------------------------------------------------------------------
class RegimeState(str, Enum):
    """Discrete regime states with associated scale factors."""

    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"


# Scale factors per regime state
REGIME_SCALE: dict[RegimeState, float] = {
    RegimeState.RISK_ON: 1.0,
    RegimeState.NEUTRAL: 0.7,
    RegimeState.RISK_OFF: 0.4,
}

# Regime classification thresholds (from RESEARCH.md pitfall 4)
# regime_score > 0.3 -> RISK_OFF, regime_score < -0.3 -> RISK_ON, else NEUTRAL
REGIME_THRESHOLDS = {
    "risk_off_above": 0.3,
    "risk_on_below": -0.3,
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class PortfolioTarget:
    """Target portfolio weights with diagnostic breakdowns.

    Attributes:
        weights: Instrument -> final target weight.
        regime: Current regime classification.
        regime_scale: Actual scale applied (may be transitional).
        conflicts: Detected strategy conflicts by asset class.
        risk_parity_weights: Pre-conviction base weights for diagnostics.
        conviction_weights: Post-conviction, pre-regime weights.
        timestamp: UTC datetime of construction.
    """

    weights: dict[str, float]
    regime: RegimeState
    regime_scale: float
    conflicts: dict[AssetClass, list[str]]
    risk_parity_weights: dict[str, float]
    conviction_weights: dict[str, float]
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# PortfolioConstructor
# ---------------------------------------------------------------------------
class PortfolioConstructor:
    """Multi-stage portfolio construction: risk parity -> conviction -> regime.

    Args:
        conflict_dampening: Multiplicative factor for conflicted asset classes.
            0.60 = 40% reduction. Locked within [0.50, 0.70] range.
        transition_days: Days for gradual regime transitions. Locked at 2-3.
    """

    def __init__(
        self,
        conflict_dampening: float = 0.60,
        transition_days: int = 3,
    ) -> None:
        # Enforce locked ranges
        self.conflict_dampening = max(0.50, min(0.70, conflict_dampening))
        self.transition_days = max(2, min(3, transition_days))
        self._previous_regime: RegimeState | None = None
        self._regime_transition_day: int = 0
        self._previous_scale: float | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def construct(
        self,
        strategy_positions: dict[str, list[StrategyPosition]],
        returns_matrix: np.ndarray | None = None,
        instrument_list: list[str] | None = None,
        regime_score: float = 0.0,
        conflicts: dict[AssetClass, list[str]] | None = None,
    ) -> PortfolioTarget:
        """Construct target portfolio from strategy positions.

        Pipeline:
        1. Flatten positions into net weights per instrument.
        2. Compute risk-parity base weights (or equal weights as fallback).
        3. Apply conviction overlay.
        4. Apply conflict dampening.
        5. Apply regime scaling with gradual transitions.

        Args:
            strategy_positions: {strategy_id: [StrategyPosition]}.
            returns_matrix: (n_obs x n_instruments) returns. None = equal wt.
            instrument_list: Instrument names matching returns_matrix columns.
            regime_score: Cross-asset regime score for regime classification.
            conflicts: Pre-computed strategy conflicts by asset class.

        Returns:
            PortfolioTarget with all intermediate weight stages.
        """
        if conflicts is None:
            conflicts = {}

        # Step 1: Flatten positions -> net weights per instrument
        flat_weights, instrument_meta = self._flatten_positions(strategy_positions)

        if not flat_weights:
            current_regime = self._classify_regime(regime_score)
            regime_scale = self._compute_regime_scale(current_regime)
            return PortfolioTarget(
                weights={},
                regime=current_regime,
                regime_scale=regime_scale,
                conflicts=conflicts,
                risk_parity_weights={},
                conviction_weights={},
            )

        instruments = sorted(flat_weights.keys())

        # Step 2: Risk parity base weights
        rp_weights = self._compute_risk_parity(
            instruments,
            returns_matrix,
            instrument_list,
        )
        risk_parity_weights = dict(zip(instruments, rp_weights))

        # Apply direction from flattened positions to risk parity weights
        for inst in instruments:
            if flat_weights[inst] < 0:
                risk_parity_weights[inst] = -abs(risk_parity_weights[inst])

        # Step 3: Conviction overlay
        conviction_weights = self._apply_conviction_overlay(
            risk_parity_weights,
            instrument_meta,
        )

        # Step 4: Conflict dampening
        dampened_weights = self._apply_conflict_dampening(
            conviction_weights,
            instrument_meta,
            conflicts,
        )

        # Step 5: Regime scaling
        current_regime = self._classify_regime(regime_score)
        regime_scale = self._compute_regime_scale(current_regime)
        final_weights = {inst: w * regime_scale for inst, w in dampened_weights.items()}

        log.info(
            "portfolio_constructed",
            n_instruments=len(final_weights),
            regime=current_regime.value,
            regime_scale=round(regime_scale, 3),
            n_conflicts=sum(len(v) for v in conflicts.values()),
        )

        return PortfolioTarget(
            weights=final_weights,
            regime=current_regime,
            regime_scale=regime_scale,
            conflicts=conflicts,
            risk_parity_weights=risk_parity_weights,
            conviction_weights=conviction_weights,
        )

    # ------------------------------------------------------------------
    # Internal: Flatten positions
    # ------------------------------------------------------------------
    @staticmethod
    def _flatten_positions(
        strategy_positions: dict[str, list[StrategyPosition]],
    ) -> tuple[dict[str, float], dict[str, list[StrategyPosition]]]:
        """Merge all strategy positions into net weights per instrument.

        Returns:
            (net_weights, instrument_meta) where instrument_meta maps
            instrument -> list of contributing StrategyPositions.
        """
        net_weights: dict[str, float] = {}
        instrument_meta: dict[str, list[StrategyPosition]] = {}

        for _strategy_id, pos_list in strategy_positions.items():
            for pos in pos_list:
                net_weights[pos.instrument] = (
                    net_weights.get(pos.instrument, 0.0) + pos.weight
                )
                instrument_meta.setdefault(pos.instrument, []).append(pos)

        return net_weights, instrument_meta

    # ------------------------------------------------------------------
    # Internal: Risk parity
    # ------------------------------------------------------------------
    def _compute_risk_parity(
        self,
        instruments: list[str],
        returns_matrix: np.ndarray | None,
        instrument_list: list[str] | None,
    ) -> np.ndarray:
        """Compute risk-parity weights using Ledoit-Wolf covariance.

        Falls back to equal weights if returns_matrix is None, has fewer
        than 60 observations, or if optimization fails.
        """
        n = len(instruments)
        equal = np.ones(n) / n

        if returns_matrix is None or returns_matrix.shape[0] < 60:
            log.info("risk_parity_fallback", reason="insufficient_data", n=n)
            return equal

        # Align returns_matrix columns with instruments
        if (
            instrument_list is not None
            and len(instrument_list) == returns_matrix.shape[1]
        ):
            # Select and reorder columns to match sorted instruments
            col_map = {name: idx for idx, name in enumerate(instrument_list)}
            col_indices = []
            for inst in instruments:
                if inst in col_map:
                    col_indices.append(col_map[inst])
                else:
                    log.info(
                        "risk_parity_fallback", reason="missing_instrument", inst=inst
                    )
                    return equal
            aligned_returns = returns_matrix[:, col_indices]
        else:
            if returns_matrix.shape[1] != n:
                log.info(
                    "risk_parity_fallback",
                    reason="shape_mismatch",
                    returns_cols=returns_matrix.shape[1],
                    n_instruments=n,
                )
                return equal
            aligned_returns = returns_matrix

        # Compute Ledoit-Wolf covariance
        try:
            from sklearn.covariance import LedoitWolf

            lw = LedoitWolf()
            lw.fit(aligned_returns)
            cov = lw.covariance_
        except Exception as exc:
            log.warning("ledoit_wolf_failed", error=str(exc))
            return equal

        return _risk_parity_weights(cov)

    # ------------------------------------------------------------------
    # Internal: Conviction overlay
    # ------------------------------------------------------------------
    def _apply_conviction_overlay(
        self,
        risk_parity_weights: dict[str, float],
        instrument_meta: dict[str, list[StrategyPosition]],
    ) -> dict[str, float]:
        """Scale risk-parity weights by average conviction of contributors.

        Conviction = mean(confidence * STRENGTH_MAP[strength]) across
        contributing strategy positions.

        Re-normalizes so sum(abs(weights)) is preserved.
        """
        conviction_weights: dict[str, float] = {}
        for inst, rp_w in risk_parity_weights.items():
            contributors = instrument_meta.get(inst, [])
            if not contributors:
                conviction_weights[inst] = rp_w
                continue

            conviction_scores = []
            for pos in contributors:
                strength = pos.metadata.get("strength", "NO_SIGNAL")
                try:
                    strength_enum = SignalStrength(strength)
                except ValueError:
                    strength_enum = SignalStrength.NO_SIGNAL
                strength_mult = STRENGTH_MAP.get(strength_enum, 0.0)
                conviction_scores.append(pos.confidence * strength_mult)

            avg_conviction = (
                sum(conviction_scores) / len(conviction_scores)
                if conviction_scores
                else 0.5
            )
            # Scale by conviction (minimum floor 0.1 to avoid zeroing out)
            conviction_weights[inst] = rp_w * max(avg_conviction, 0.1)

        # Re-normalize to preserve total absolute weight
        rp_total_abs = sum(abs(v) for v in risk_parity_weights.values())
        conv_total_abs = sum(abs(v) for v in conviction_weights.values())

        if conv_total_abs > 1e-12 and rp_total_abs > 1e-12:
            scale = rp_total_abs / conv_total_abs
            conviction_weights = {k: v * scale for k, v in conviction_weights.items()}

        return conviction_weights

    # ------------------------------------------------------------------
    # Internal: Conflict dampening
    # ------------------------------------------------------------------
    def _apply_conflict_dampening(
        self,
        weights: dict[str, float],
        instrument_meta: dict[str, list[StrategyPosition]],
        conflicts: dict[AssetClass, list[str]],
    ) -> dict[str, float]:
        """Reduce weights for instruments in conflicted asset classes."""
        if not conflicts:
            return dict(weights)

        from src.portfolio.signal_aggregator import _infer_strategy_asset_class_map

        # Build instrument -> asset_class mapping
        inst_ac: dict[str, AssetClass] = {}
        for inst, positions in instrument_meta.items():
            for pos in positions:
                ac_map = _infer_strategy_asset_class_map({pos.strategy_id: [pos]})
                if pos.strategy_id in ac_map:
                    inst_ac[inst] = ac_map[pos.strategy_id]
                    break

        dampened = dict(weights)
        for inst, w in dampened.items():
            ac = inst_ac.get(inst)
            if ac is not None and ac in conflicts and conflicts[ac]:
                dampened[inst] = w * self.conflict_dampening
                log.info(
                    "conflict_dampening_applied",
                    instrument=inst,
                    asset_class=ac.value,
                    factor=self.conflict_dampening,
                )

        return dampened

    # ------------------------------------------------------------------
    # Internal: Regime
    # ------------------------------------------------------------------
    @staticmethod
    def _classify_regime(regime_score: float) -> RegimeState:
        """Classify regime score into discrete state."""
        if regime_score > REGIME_THRESHOLDS["risk_off_above"]:
            return RegimeState.RISK_OFF
        elif regime_score < REGIME_THRESHOLDS["risk_on_below"]:
            return RegimeState.RISK_ON
        return RegimeState.NEUTRAL

    def _compute_regime_scale(self, current_regime: RegimeState) -> float:
        """Compute regime scale with gradual transition.

        If regime changed from previous call, applies a linear ramp over
        ``transition_days`` to avoid whipsaw.
        """
        target_scale = REGIME_SCALE[current_regime]

        if self._previous_regime is None:
            # First call -- apply full target scale immediately
            self._previous_regime = current_regime
            self._previous_scale = target_scale
            self._regime_transition_day = 0
            return target_scale

        if current_regime != self._previous_regime:
            # Regime changed — check if this is a NEW transition or continuation
            if (
                not hasattr(self, "_target_regime")
                or self._target_regime != current_regime
            ):
                # New regime target — reset transition from current interpolated scale
                self._target_regime = current_regime
                self._transition_start_scale = (
                    self._previous_scale or REGIME_SCALE[self._previous_regime]
                )
                self._regime_transition_day = 1
            else:
                self._regime_transition_day += 1

            progress = min(
                self._regime_transition_day / self.transition_days,
                1.0,
            )
            scale = (
                self._transition_start_scale
                + (target_scale - self._transition_start_scale) * progress
            )

            if progress >= 1.0:
                # Transition complete
                self._previous_regime = current_regime
                self._previous_scale = target_scale
                self._regime_transition_day = 0
                self._target_regime = None
            return scale
        else:
            # Same regime -- no transition
            self._previous_regime = current_regime
            self._previous_scale = target_scale
            self._regime_transition_day = 0
            return target_scale


# ---------------------------------------------------------------------------
# Pure function: risk parity weights via SLSQP
# ---------------------------------------------------------------------------
def _risk_parity_weights(cov_matrix: np.ndarray) -> np.ndarray:
    """Compute risk-parity weights minimizing risk contribution dispersion.

    Objective: minimize sum((RC_i - 1/n)^2) where
        RC_i = w_i * (Sigma @ w)_i / (w' Sigma w)

    Args:
        cov_matrix: (n x n) covariance matrix.

    Returns:
        (n,) array of risk-parity weights summing to 1.0.
    """
    n = cov_matrix.shape[0]
    if n <= 1:
        return np.ones(n)

    target_rc = 1.0 / n
    w0 = np.ones(n) / n

    def objective(w: np.ndarray) -> float:
        sigma_w = cov_matrix @ w
        port_var = w @ sigma_w
        if port_var < 1e-16:
            return 0.0
        rc = w * sigma_w / port_var
        return float(np.sum((rc - target_rc) ** 2))

    bounds = [(0.01, 1.0)] * n
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

    result = minimize(
        objective,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )

    if result.success:
        weights = result.x / result.x.sum()  # Ensure exact sum=1
        return weights

    log.warning("risk_parity_optimization_failed", message=result.message)
    return w0
