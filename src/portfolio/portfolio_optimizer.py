"""Mean-variance portfolio optimization with configurable constraints.

Uses scipy.minimize (SLSQP) to find optimal portfolio weights that maximize
mean-variance utility: max w^T mu - (1/2) * lambda * w^T Sigma w, subject
to leverage, weight bound, and optional return-target constraints.

Includes should_rebalance() for signal-driven + drift-triggered rebalancing:
run optimization daily at close, but only execute trades if aggregate signal
change exceeds threshold OR position drift > X% from target.

This module is pure computation -- no database or I/O access.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog
from scipy.optimize import minimize

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OptimizationConstraints:
    """Frozen constraints for mean-variance optimization.

    Attributes:
        min_weight: Minimum weight per instrument (negative = allow shorts).
        max_weight: Maximum weight per instrument.
        max_leverage: Maximum sum of absolute weights.
        target_return: Optional target return for constrained optimization.
        long_only: If True, override min_weight to 0.0.
    """

    min_weight: float = -0.25
    max_weight: float = 0.25
    max_leverage: float = 3.0
    target_return: float | None = None
    long_only: bool = False


# ---------------------------------------------------------------------------
# PortfolioOptimizer
# ---------------------------------------------------------------------------
class PortfolioOptimizer:
    """Mean-variance optimizer using scipy SLSQP.

    Objective: minimize 0.5 * w^T Sigma w - lambda * mu^T w
    (equivalent to maximizing mean-variance utility).

    Args:
        constraints: OptimizationConstraints. Uses defaults if None.
    """

    def __init__(self, constraints: OptimizationConstraints | None = None) -> None:
        self.constraints = constraints or OptimizationConstraints()

    def optimize(
        self,
        expected_returns: np.ndarray,
        covariance: np.ndarray,
        instrument_names: list[str],
        risk_aversion: float = 2.5,
    ) -> dict[str, float]:
        """Find optimal portfolio weights via mean-variance optimization.

        Uses scipy.minimize with SLSQP. Objective function:
            minimize 0.5 * w^T Sigma w - (1/risk_aversion) * mu^T w

        Args:
            expected_returns: (n,) expected return vector.
            covariance: (n x n) covariance matrix.
            instrument_names: List of instrument names matching array columns.
            risk_aversion: Risk aversion parameter for utility trade-off.

        Returns:
            Dict of instrument_name -> optimal weight.
        """
        expected_returns = np.asarray(expected_returns, dtype=np.float64)
        covariance = np.asarray(covariance, dtype=np.float64)
        n = len(instrument_names)

        if n == 0:
            return {}

        # Determine weight bounds
        min_w = 0.0 if self.constraints.long_only else self.constraints.min_weight
        max_w = self.constraints.max_weight
        bounds = [(min_w, max_w)] * n

        # Initial guess: equal weight
        w0 = np.ones(n) / n
        # Clamp initial guess to bounds
        w0 = np.clip(w0, min_w, max_w)

        # Objective: minimize 0.5 * w^T Sigma w - (1/risk_aversion) * mu^T w
        def objective(w: np.ndarray) -> float:
            port_var = float(w @ covariance @ w)
            port_ret = float(expected_returns @ w)
            return 0.5 * port_var - (1.0 / risk_aversion) * port_ret

        def objective_jac(w: np.ndarray) -> np.ndarray:
            return covariance @ w - (1.0 / risk_aversion) * expected_returns

        # Constraints
        constraints_list = []

        # Leverage constraint: sum(|w|) <= max_leverage
        # Implemented as inequality: max_leverage - sum(|w|) >= 0
        constraints_list.append(
            {
                "type": "ineq",
                "fun": lambda w: self.constraints.max_leverage - np.sum(np.abs(w)),
            }
        )

        # Optional return target constraint
        if self.constraints.target_return is not None:
            constraints_list.append(
                {
                    "type": "eq",
                    "fun": lambda w: float(expected_returns @ w)
                    - self.constraints.target_return,
                }
            )

        result = minimize(
            objective,
            w0,
            method="SLSQP",
            jac=objective_jac,
            bounds=bounds,
            constraints=constraints_list,
            options={"ftol": 1e-12, "maxiter": 1000, "disp": False},
        )

        if not result.success:
            logger.warning(
                "optimization_failed",
                message=result.message,
                fallback="equal_weight",
            )
            # Fallback to equal weight, clamped to bounds
            weights = np.clip(np.ones(n) / n, min_w, max_w)
        else:
            weights = result.x

        # Build result dict
        weight_dict = {
            name: round(float(weights[i]), 8) for i, name in enumerate(instrument_names)
        }

        logger.info(
            "optimization_complete",
            n_instruments=n,
            success=result.success,
            leverage=round(float(np.sum(np.abs(weights))), 4),
        )

        return weight_dict

    def optimize_with_bl(
        self,
        bl_result: dict,
        instrument_names: list[str],
        risk_aversion: float = 2.5,
    ) -> dict[str, float]:
        """Convenience wrapper using Black-Litterman posterior.

        Args:
            bl_result: Output from BlackLitterman.optimize() containing
                'posterior_returns' (dict) and 'posterior_covariance' (ndarray).
            instrument_names: List of instrument names.
            risk_aversion: Risk aversion parameter.

        Returns:
            Dict of instrument_name -> optimal weight.
        """
        posterior_returns_dict = bl_result["posterior_returns"]
        posterior_covariance = bl_result["posterior_covariance"]

        # Build return vector aligned with instrument_names
        expected_returns = np.array(
            [posterior_returns_dict.get(name, 0.0) for name in instrument_names],
            dtype=np.float64,
        )

        return self.optimize(
            expected_returns=expected_returns,
            covariance=posterior_covariance,
            instrument_names=instrument_names,
            risk_aversion=risk_aversion,
        )

    def should_rebalance(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        signal_change: float,
        signal_threshold: float = 0.15,
        drift_threshold: float = 0.05,
    ) -> bool:
        """Determine whether rebalancing should execute.

        Daily optimization runs at close but only executes trades when:
        1. Aggregate signal change exceeds threshold, OR
        2. Maximum position drift from target exceeds threshold.

        Args:
            current_weights: Current portfolio weights.
            target_weights: New target portfolio weights.
            signal_change: Absolute change in aggregate signal since last rebalance.
            signal_threshold: Minimum signal change to trigger rebalance.
            drift_threshold: Maximum position drift before rebalancing.

        Returns:
            True if rebalancing should execute.
        """
        # Check signal change
        if abs(signal_change) > signal_threshold:
            logger.info(
                "rebalance_triggered",
                reason="signal_change",
                signal_change=round(signal_change, 4),
                threshold=signal_threshold,
            )
            return True

        # Check position drift
        all_instruments = set(current_weights) | set(target_weights)
        if all_instruments:
            max_drift = max(
                abs(target_weights.get(inst, 0.0) - current_weights.get(inst, 0.0))
                for inst in all_instruments
            )
            if max_drift > drift_threshold:
                logger.info(
                    "rebalance_triggered",
                    reason="position_drift",
                    max_drift=round(max_drift, 4),
                    threshold=drift_threshold,
                )
                return True

        logger.info(
            "rebalance_not_needed",
            signal_change=round(signal_change, 4),
            signal_threshold=signal_threshold,
            drift_threshold=drift_threshold,
        )
        return False
