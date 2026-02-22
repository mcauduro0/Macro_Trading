"""HMM-based regime classifier with rule-based fallback.

Classifies the macro regime into one of 4 states (Goldilocks, Reflation,
Stagflation, Deflation) using a Gaussian HMM on 6 cross-asset features.
Falls back to rule-based classification when hmmlearn is unavailable or
when the HMM fails to converge.

Features (z-scored):
    growth_z, inflation_z, VIX_z, credit_spread_z, FX_vol_z, equity_momentum_z

Training window: Expanding from 2010 to as_of_date.
Output: Full probability vector (not just point estimate).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conditional import of hmmlearn
# ---------------------------------------------------------------------------
try:
    from hmmlearn.hmm import GaussianHMM

    _HMM_AVAILABLE = True
except ImportError:
    GaussianHMM = None  # type: ignore[assignment,misc]
    _HMM_AVAILABLE = False


# ---------------------------------------------------------------------------
# HMMResult dataclass
# ---------------------------------------------------------------------------
@dataclass
class HMMResult:
    """Result from regime classification.

    Attributes:
        regime: Classified regime name.
        regime_probabilities: Dict mapping regime names to probabilities.
        method: Classification method ("hmm" or "rule_based").
        converged: Whether HMM converged (False for rule_based).
        warning: Optional warning message (set on fallback).
    """

    regime: str
    regime_probabilities: dict[str, float]
    method: str
    converged: bool
    warning: str | None = None


# ---------------------------------------------------------------------------
# Regime names
# ---------------------------------------------------------------------------
_REGIME_NAMES = ["Goldilocks", "Reflation", "Stagflation", "Deflation"]

_REQUIRED_COLUMNS = [
    "growth_z",
    "inflation_z",
    "VIX_z",
    "credit_spread_z",
    "FX_vol_z",
    "equity_momentum_z",
]

_MIN_OBSERVATIONS = 60


# ---------------------------------------------------------------------------
# HMMRegimeClassifier
# ---------------------------------------------------------------------------
class HMMRegimeClassifier:
    """4-state regime classifier using Gaussian HMM with rule-based fallback.

    Args:
        n_regimes: Number of HMM states (default 4).
    """

    def __init__(self, n_regimes: int = 4) -> None:
        self.n_regimes = n_regimes
        self._hmm_available = _HMM_AVAILABLE

    def classify(
        self, feature_history: pd.DataFrame, as_of_date: date
    ) -> HMMResult:
        """Classify the current regime from feature history.

        Args:
            feature_history: DataFrame with columns matching _REQUIRED_COLUMNS.
                Each row is one observation (daily). Should be expanding from
                2010 up to as_of_date.
            as_of_date: Point-in-time reference date.

        Returns:
            HMMResult with regime, probabilities, and method info.
        """
        # Validate input
        if feature_history is None or feature_history.empty:
            return self._rule_based_fallback(
                growth_z=0.0,
                inflation_z=0.0,
                warning="Empty feature history -- using rule-based fallback",
            )

        # Check required columns
        missing_cols = [
            c for c in _REQUIRED_COLUMNS if c not in feature_history.columns
        ]
        if missing_cols:
            return self._rule_based_fallback(
                growth_z=0.0,
                inflation_z=0.0,
                warning=f"Missing columns {missing_cols} -- using rule-based fallback",
            )

        # Drop NaN rows
        clean = feature_history[_REQUIRED_COLUMNS].dropna()

        if len(clean) < _MIN_OBSERVATIONS:
            # Not enough data for HMM -- use last observation with rule-based
            if len(clean) > 0:
                last = clean.iloc[-1]
                return self._rule_based_fallback(
                    growth_z=float(last["growth_z"]),
                    inflation_z=float(last["inflation_z"]),
                    warning=f"Insufficient data ({len(clean)} < {_MIN_OBSERVATIONS}) -- using rule-based fallback",
                )
            return self._rule_based_fallback(
                growth_z=0.0,
                inflation_z=0.0,
                warning="No valid observations -- using rule-based fallback",
            )

        # Attempt HMM classification
        if self._hmm_available:
            try:
                return self._hmm_classify(clean)
            except Exception as exc:
                logger.warning("HMM classification failed: %s", exc)
                last = clean.iloc[-1]
                return self._rule_based_fallback(
                    growth_z=float(last["growth_z"]),
                    inflation_z=float(last["inflation_z"]),
                    warning=f"HMM failed ({exc}) -- using rule-based fallback",
                )

        # hmmlearn not available
        last = clean.iloc[-1]
        return self._rule_based_fallback(
            growth_z=float(last["growth_z"]),
            inflation_z=float(last["inflation_z"]),
            warning="hmmlearn not installed -- using rule-based fallback",
        )

    # ------------------------------------------------------------------
    # HMM classification path
    # ------------------------------------------------------------------
    def _hmm_classify(self, clean: pd.DataFrame) -> HMMResult:
        """Classify using Gaussian HMM.

        Args:
            clean: Clean DataFrame with _REQUIRED_COLUMNS, no NaNs.

        Returns:
            HMMResult with method="hmm".
        """
        X = clean.values.astype(np.float64)

        model = GaussianHMM(
            n_components=self.n_regimes,
            covariance_type="full",
            n_iter=100,
            random_state=42,
        )
        model.fit(X)

        # Get posterior probabilities for the last observation
        posteriors = model.predict_proba(X)
        last_probs = posteriors[-1]

        # Map HMM states to regime names by examining state means
        state_regime_map = self._map_states_to_regimes(model.means_)

        # Build probability dict
        regime_probs: dict[str, float] = {}
        for state_idx in range(self.n_regimes):
            regime_name = state_regime_map[state_idx]
            if regime_name in regime_probs:
                regime_probs[regime_name] += float(last_probs[state_idx])
            else:
                regime_probs[regime_name] = float(last_probs[state_idx])

        # Ensure all 4 regimes are present
        for name in _REGIME_NAMES:
            if name not in regime_probs:
                regime_probs[name] = 0.0

        # Normalize to sum to 1.0
        total = sum(regime_probs.values())
        if total > 0:
            regime_probs = {k: v / total for k, v in regime_probs.items()}

        # Top regime
        regime = max(regime_probs, key=regime_probs.get)  # type: ignore[arg-type]

        return HMMResult(
            regime=regime,
            regime_probabilities=regime_probs,
            method="hmm",
            converged=True,
            warning=None,
        )

    def _map_states_to_regimes(self, means: np.ndarray) -> dict[int, str]:
        """Map HMM state indices to regime names based on state means.

        Logic:
        - growth_z is column 0, inflation_z is column 1
        - Goldilocks: highest growth_z mean with low inflation_z
        - Reflation: positive growth_z with high inflation_z
        - Stagflation: lowest growth_z with high inflation_z
        - Deflation: low growth_z with lowest inflation_z

        Args:
            means: Array of shape (n_regimes, n_features) -- state means.

        Returns:
            Dict mapping state index to regime name.
        """
        n_states = means.shape[0]
        growth_means = means[:, 0]
        inflation_means = means[:, 1]

        # Score each state for each regime
        state_map: dict[int, str] = {}
        used_states: set[int] = set()

        # Goldilocks: highest growth, lowest inflation
        scores = growth_means - inflation_means
        for _ in range(min(n_states, 4)):
            candidates = [i for i in range(n_states) if i not in used_states]
            if not candidates:
                break
            # Goldilocks
            if "Goldilocks" not in state_map.values():
                best = max(candidates, key=lambda i: growth_means[i] - inflation_means[i])
                state_map[best] = "Goldilocks"
                used_states.add(best)
                continue
            # Stagflation
            if "Stagflation" not in state_map.values():
                best = min(candidates, key=lambda i: growth_means[i] - inflation_means[i])
                state_map[best] = "Stagflation"
                used_states.add(best)
                continue
            # Reflation: positive growth, high inflation
            if "Reflation" not in state_map.values():
                best = max(candidates, key=lambda i: growth_means[i] + inflation_means[i])
                state_map[best] = "Reflation"
                used_states.add(best)
                continue
            # Deflation: remaining
            if "Deflation" not in state_map.values():
                best = candidates[0]
                state_map[best] = "Deflation"
                used_states.add(best)

        # Assign any remaining states
        for i in range(n_states):
            if i not in state_map:
                state_map[i] = "Deflation"

        return state_map

    # ------------------------------------------------------------------
    # Rule-based fallback
    # ------------------------------------------------------------------
    def _rule_based_fallback(
        self,
        growth_z: float,
        inflation_z: float,
        warning: str,
    ) -> HMMResult:
        """Classify regime using rule-based thresholds.

        Rules (from CROSS_01):
        - Goldilocks: growth_z > 0 AND inflation_z < 0.5
        - Reflation:  growth_z > 0 AND inflation_z >= 0.5
        - Stagflation: growth_z < 0 AND inflation_z >= 0.5
        - Deflation:  growth_z < 0 AND inflation_z < -0.5
        - Default: nearest regime based on distance

        Probabilities: 0.7 for classified regime, 0.1 for each other.

        Args:
            growth_z: Growth z-score.
            inflation_z: Inflation z-score.
            warning: Warning message describing fallback reason.

        Returns:
            HMMResult with method="rule_based".
        """
        if growth_z > 0 and inflation_z < 0.5:
            regime = "Goldilocks"
        elif growth_z > 0 and inflation_z >= 0.5:
            regime = "Reflation"
        elif growth_z < 0 and inflation_z >= 0.5:
            regime = "Stagflation"
        elif growth_z < 0 and inflation_z < -0.5:
            regime = "Deflation"
        else:
            # Default: nearest regime (growth_z == 0 or ambiguous inflation)
            # Use the closest of the 4 quadrant centroids
            centroids = {
                "Goldilocks": (0.5, -0.25),
                "Reflation": (0.5, 1.0),
                "Stagflation": (-0.5, 1.0),
                "Deflation": (-0.5, -1.0),
            }
            regime = min(
                centroids,
                key=lambda r: (growth_z - centroids[r][0]) ** 2
                + (inflation_z - centroids[r][1]) ** 2,
            )

        # Assign probabilities: 0.7 to classified, 0.1 to others
        probabilities = {name: 0.1 for name in _REGIME_NAMES}
        probabilities[regime] = 0.7

        return HMMResult(
            regime=regime,
            regime_probabilities=probabilities,
            method="rule_based",
            converged=False,
            warning=warning,
        )
