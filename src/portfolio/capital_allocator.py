"""Capital allocation with constraint enforcement and drift-triggered rebalancing.

CapitalAllocator takes a PortfolioTarget from PortfolioConstructor and enforces
portfolio-level constraints (leverage, single position, asset class concentration,
risk budget). It computes trades as weight deltas from current to target and
filters out sub-threshold trades.

This module is pure computation -- no database or I/O access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import structlog

from src.core.enums import AssetClass
from src.portfolio.portfolio_constructor import PortfolioTarget

log = structlog.get_logger(__name__)

# Reference equity for weight-space trade filtering
_REFERENCE_EQUITY = 1_000_000.0


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AllocationConstraints:
    """Frozen constraints for portfolio allocation.

    Attributes:
        max_leverage: Sum of absolute weights cap (default 3.0x).
        max_single_position: Max absolute weight per instrument (default 25%).
        max_asset_class_concentration: Max sum of abs weights per asset class (default 50%).
        max_risk_budget_pct: Max risk contribution per position (default 20%).
        drift_threshold: Rebalance trigger threshold (default 5% absolute deviation).
        min_trade_notional: Minimum trade size in notional terms (default 10k).
    """

    max_leverage: float = 3.0
    max_single_position: float = 0.25
    max_asset_class_concentration: float = 0.50
    max_risk_budget_pct: float = 0.20
    drift_threshold: float = 0.05
    min_trade_notional: float = 10_000.0


@dataclass
class AllocationResult:
    """Output of capital allocation with diagnostics.

    Attributes:
        target_weights: Final constrained weights per instrument.
        trades: Weight change (delta) per instrument.
        rebalance_needed: Whether drift exceeded threshold.
        constraint_violations: Descriptions of binding constraints.
        leverage_used: Final leverage ratio (sum of abs weights).
        asset_class_exposure: Exposure per asset class.
        timestamp: UTC datetime of allocation.
    """

    target_weights: dict[str, float]
    trades: dict[str, float]
    rebalance_needed: bool
    constraint_violations: list[str]
    leverage_used: float
    asset_class_exposure: dict[str, float]
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# CapitalAllocator
# ---------------------------------------------------------------------------
class CapitalAllocator:
    """Enforce portfolio constraints and compute rebalance trades.

    Pipeline:
    1. Apply single position limit (clamp per instrument).
    2. Apply asset class concentration limit (scale down per asset class).
    3. Apply leverage limit (scale all weights proportionally).
    4. Drift check (skip rebalance if max drift <= threshold).
    5. Compute trades (target - current, filter sub-threshold).

    Args:
        constraints: Allocation constraints. Defaults to AllocationConstraints().
    """

    def __init__(
        self,
        constraints: AllocationConstraints | None = None,
    ) -> None:
        self.constraints = constraints or AllocationConstraints()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def allocate(
        self,
        portfolio_target: PortfolioTarget,
        current_weights: dict[str, float] | None = None,
        instrument_to_asset_class: dict[str, AssetClass] | None = None,
    ) -> AllocationResult:
        """Apply constraints and compute trades from target portfolio.

        Args:
            portfolio_target: Target from PortfolioConstructor.
            current_weights: Current portfolio weights (None = start from zero).
            instrument_to_asset_class: Mapping for asset class grouping.

        Returns:
            AllocationResult with constrained weights and trade deltas.
        """
        if current_weights is None:
            current_weights = {}
        if instrument_to_asset_class is None:
            instrument_to_asset_class = {}

        violations: list[str] = []
        weights = dict(portfolio_target.weights)

        # Step 1: Single position limit
        weights, pos_violations = self._apply_single_position_limit(weights)
        violations.extend(pos_violations)

        # Step 2: Asset class concentration
        weights, ac_violations = self._apply_asset_class_concentration(
            weights, instrument_to_asset_class,
        )
        violations.extend(ac_violations)

        # Step 3: Leverage limit
        weights, lev_violations = self._apply_leverage_limit(weights)
        violations.extend(lev_violations)

        # Step 4: Drift check
        max_drift = self._compute_max_drift(weights, current_weights)
        rebalance_needed = max_drift > self.constraints.drift_threshold

        if not rebalance_needed and current_weights:
            # No rebalance needed -- return current weights
            leverage_used = sum(abs(v) for v in current_weights.values())
            ac_exposure = self._compute_asset_class_exposure(
                current_weights, instrument_to_asset_class,
            )
            log.info(
                "rebalance_skipped",
                max_drift=round(max_drift, 4),
                threshold=self.constraints.drift_threshold,
            )
            return AllocationResult(
                target_weights=current_weights,
                trades={},
                rebalance_needed=False,
                constraint_violations=violations,
                leverage_used=leverage_used,
                asset_class_exposure=ac_exposure,
            )

        # Step 5: Compute trades
        trades = self._compute_trades(weights, current_weights)

        leverage_used = sum(abs(v) for v in weights.values())
        ac_exposure = self._compute_asset_class_exposure(
            weights, instrument_to_asset_class,
        )

        log.info(
            "allocation_complete",
            n_instruments=len(weights),
            n_trades=len(trades),
            leverage=round(leverage_used, 3),
            rebalance_needed=rebalance_needed,
            n_violations=len(violations),
        )

        return AllocationResult(
            target_weights=weights,
            trades=trades,
            rebalance_needed=rebalance_needed,
            constraint_violations=violations,
            leverage_used=leverage_used,
            asset_class_exposure=ac_exposure,
        )

    def check_risk_budget(
        self,
        weights: dict[str, float],
        cov_matrix: np.ndarray | None,
        instrument_list: list[str] | None,
    ) -> list[str]:
        """Check if any position exceeds the risk budget constraint.

        Computes marginal risk contribution per position:
            RC_i = w_i * (Sigma @ w)_i / (w' Sigma w)

        Args:
            weights: Instrument -> weight.
            cov_matrix: Covariance matrix (n x n). None = skip check.
            instrument_list: Instrument names matching cov_matrix columns.

        Returns:
            List of violation descriptions. Empty if none or cov not available.
        """
        if cov_matrix is None or instrument_list is None:
            return []

        n = len(instrument_list)
        if cov_matrix.shape != (n, n):
            return []

        # Build weight vector aligned with instrument_list
        w = np.array([weights.get(inst, 0.0) for inst in instrument_list])
        if np.sum(np.abs(w)) < 1e-12:
            return []

        sigma_w = cov_matrix @ w
        port_var = w @ sigma_w
        if port_var < 1e-16:
            return []

        rc = w * sigma_w / port_var

        violations: list[str] = []
        for i, inst in enumerate(instrument_list):
            if abs(rc[i]) > self.constraints.max_risk_budget_pct:
                violations.append(
                    f"{inst}: risk contribution {rc[i]:.2%} exceeds "
                    f"max {self.constraints.max_risk_budget_pct:.0%} budget"
                )

        return violations

    # ------------------------------------------------------------------
    # Internal: Constraint enforcement
    # ------------------------------------------------------------------
    def _apply_single_position_limit(
        self, weights: dict[str, float],
    ) -> tuple[dict[str, float], list[str]]:
        """Clamp each weight to [-max_single_position, +max_single_position]."""
        violations: list[str] = []
        clamped: dict[str, float] = {}
        limit = self.constraints.max_single_position

        for inst, w in weights.items():
            if abs(w) > limit:
                violations.append(
                    f"{inst}: weight {w:.3f} clamped to "
                    f"{limit * (1 if w > 0 else -1):.3f} "
                    f"(max_single_position={limit})"
                )
                clamped[inst] = limit if w > 0 else -limit
            else:
                clamped[inst] = w

        return clamped, violations

    def _apply_asset_class_concentration(
        self,
        weights: dict[str, float],
        instrument_to_asset_class: dict[str, AssetClass],
    ) -> tuple[dict[str, float], list[str]]:
        """Scale down asset class exposure if exceeding concentration limit."""
        violations: list[str] = []
        result = dict(weights)
        limit = self.constraints.max_asset_class_concentration

        # Group instruments by asset class
        ac_groups: dict[AssetClass, list[str]] = {}
        for inst, w in weights.items():
            ac = instrument_to_asset_class.get(inst)
            if ac is not None:
                ac_groups.setdefault(ac, []).append(inst)

        for ac, instruments in ac_groups.items():
            total_abs = sum(abs(result[inst]) for inst in instruments)
            if total_abs > limit:
                scale = limit / total_abs
                violations.append(
                    f"{ac.value}: total exposure {total_abs:.3f} exceeds "
                    f"max {limit:.2f}, scaling by {scale:.3f}"
                )
                for inst in instruments:
                    result[inst] *= scale

        return result, violations

    def _apply_leverage_limit(
        self, weights: dict[str, float],
    ) -> tuple[dict[str, float], list[str]]:
        """Scale all weights proportionally if leverage exceeds limit."""
        violations: list[str] = []
        total_abs = sum(abs(w) for w in weights.values())
        limit = self.constraints.max_leverage

        if total_abs > limit and total_abs > 0:
            scale = limit / total_abs
            violations.append(
                f"Leverage {total_abs:.3f}x exceeds max {limit:.1f}x, "
                f"scaling by {scale:.3f}"
            )
            return {k: v * scale for k, v in weights.items()}, violations

        return weights, violations

    # ------------------------------------------------------------------
    # Internal: Drift and trades
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_max_drift(
        target: dict[str, float],
        current: dict[str, float],
    ) -> float:
        """Compute maximum absolute deviation between target and current."""
        all_instruments = set(target) | set(current)
        if not all_instruments:
            return 0.0
        return max(
            abs(target.get(inst, 0.0) - current.get(inst, 0.0))
            for inst in all_instruments
        )

    def _compute_trades(
        self,
        target: dict[str, float],
        current: dict[str, float],
    ) -> dict[str, float]:
        """Compute trade deltas, filtering sub-threshold trades."""
        all_instruments = set(target) | set(current)
        min_delta = self.constraints.min_trade_notional / _REFERENCE_EQUITY
        trades: dict[str, float] = {}

        for inst in all_instruments:
            delta = target.get(inst, 0.0) - current.get(inst, 0.0)
            if abs(delta) >= min_delta:
                trades[inst] = delta

        return trades

    @staticmethod
    def _compute_asset_class_exposure(
        weights: dict[str, float],
        instrument_to_asset_class: dict[str, AssetClass],
    ) -> dict[str, float]:
        """Compute total absolute exposure per asset class."""
        exposure: dict[str, float] = {}
        for inst, w in weights.items():
            ac = instrument_to_asset_class.get(inst)
            ac_key = ac.value if ac else "UNCLASSIFIED"
            exposure[ac_key] = exposure.get(ac_key, 0.0) + abs(w)
        return exposure
