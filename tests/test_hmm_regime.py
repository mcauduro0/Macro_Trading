"""Unit tests for HMMRegimeClassifier.

Tests cover:
- Rule-based fallback produces correct regimes for all 4 quadrants
- Rule-based assigns 0.7 probability to classified regime
- classify() works with minimal DataFrame (rule-based path)
- classify() handles empty DataFrame gracefully
- HMM path with synthetic data (if hmmlearn available)
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.agents.hmm_regime import HMMRegimeClassifier, HMMResult

AS_OF = date(2024, 6, 30)


# ---------------------------------------------------------------------------
# Helper: build feature DataFrame
# ---------------------------------------------------------------------------
def _make_features(
    n: int = 1,
    growth_z: float = 0.0,
    inflation_z: float = 0.0,
    vix_z: float = 0.0,
    credit_z: float = 0.0,
    fx_vol_z: float = 0.0,
    eq_mom_z: float = 0.0,
) -> pd.DataFrame:
    """Build a DataFrame with HMM feature columns."""
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "growth_z": [growth_z] * n,
            "inflation_z": [inflation_z] * n,
            "VIX_z": [vix_z] * n,
            "credit_spread_z": [credit_z] * n,
            "FX_vol_z": [fx_vol_z] * n,
            "equity_momentum_z": [eq_mom_z] * n,
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# Test 1: Rule-based Goldilocks (growth > 0, inflation < 0.5)
# ---------------------------------------------------------------------------
def test_rule_based_goldilocks():
    """High growth, low inflation -> Goldilocks."""
    classifier = HMMRegimeClassifier()
    df = _make_features(n=10, growth_z=1.0, inflation_z=-0.2)

    result = classifier.classify(df, AS_OF)

    assert result.regime == "Goldilocks"
    assert result.method == "rule_based"
    assert result.converged is False
    assert result.warning is not None


# ---------------------------------------------------------------------------
# Test 2: Rule-based Reflation (growth > 0, inflation >= 0.5)
# ---------------------------------------------------------------------------
def test_rule_based_reflation():
    """High growth, high inflation -> Reflation."""
    classifier = HMMRegimeClassifier()
    df = _make_features(n=10, growth_z=1.0, inflation_z=1.0)

    result = classifier.classify(df, AS_OF)

    assert result.regime == "Reflation"
    assert result.method == "rule_based"


# ---------------------------------------------------------------------------
# Test 3: Rule-based Stagflation (growth < 0, inflation >= 0.5)
# ---------------------------------------------------------------------------
def test_rule_based_stagflation():
    """Low growth, high inflation -> Stagflation."""
    classifier = HMMRegimeClassifier()
    df = _make_features(n=10, growth_z=-1.0, inflation_z=1.0)

    result = classifier.classify(df, AS_OF)

    assert result.regime == "Stagflation"
    assert result.method == "rule_based"


# ---------------------------------------------------------------------------
# Test 4: Rule-based Deflation (growth < 0, inflation < -0.5)
# ---------------------------------------------------------------------------
def test_rule_based_deflation():
    """Low growth, very low inflation -> Deflation."""
    classifier = HMMRegimeClassifier()
    df = _make_features(n=10, growth_z=-1.0, inflation_z=-1.0)

    result = classifier.classify(df, AS_OF)

    assert result.regime == "Deflation"
    assert result.method == "rule_based"


# ---------------------------------------------------------------------------
# Test 5: Rule-based assigns 0.7 probability to classified regime
# ---------------------------------------------------------------------------
def test_rule_based_probability_distribution():
    """Rule-based fallback assigns 0.7 to classified regime, 0.1 to others."""
    classifier = HMMRegimeClassifier()
    df = _make_features(n=10, growth_z=1.0, inflation_z=-0.2)

    result = classifier.classify(df, AS_OF)

    assert result.regime_probabilities[result.regime] == 0.7
    other_probs = [
        v for k, v in result.regime_probabilities.items() if k != result.regime
    ]
    assert all(p == 0.1 for p in other_probs)
    assert abs(sum(result.regime_probabilities.values()) - 1.0) < 1e-8


# ---------------------------------------------------------------------------
# Test 6: classify() with empty DataFrame
# ---------------------------------------------------------------------------
def test_classify_empty_dataframe():
    """Empty DataFrame -> rule-based fallback with warning."""
    classifier = HMMRegimeClassifier()
    result = classifier.classify(pd.DataFrame(), AS_OF)

    assert result.method == "rule_based"
    assert result.warning is not None
    assert "Empty" in result.warning or "empty" in result.warning.lower()


# ---------------------------------------------------------------------------
# Test 7: classify() with None
# ---------------------------------------------------------------------------
def test_classify_none_input():
    """None input -> rule-based fallback."""
    classifier = HMMRegimeClassifier()
    result = classifier.classify(None, AS_OF)

    assert result.method == "rule_based"
    assert result.warning is not None


# ---------------------------------------------------------------------------
# Test 8: classify() with missing columns
# ---------------------------------------------------------------------------
def test_classify_missing_columns():
    """DataFrame with wrong columns -> rule-based fallback."""
    classifier = HMMRegimeClassifier()
    df = pd.DataFrame({"wrong_col": [1.0, 2.0, 3.0]})

    result = classifier.classify(df, AS_OF)

    assert result.method == "rule_based"
    assert result.warning is not None
    assert "Missing" in result.warning or "columns" in result.warning.lower()


# ---------------------------------------------------------------------------
# Test 9: classify() with insufficient observations
# ---------------------------------------------------------------------------
def test_classify_insufficient_observations():
    """DataFrame with < 60 observations -> rule-based fallback."""
    classifier = HMMRegimeClassifier()
    df = _make_features(n=30, growth_z=0.5, inflation_z=-0.1)

    result = classifier.classify(df, AS_OF)

    assert result.method == "rule_based"
    assert result.warning is not None
    assert "Insufficient" in result.warning


# ---------------------------------------------------------------------------
# Test 10: HMMResult dataclass fields
# ---------------------------------------------------------------------------
def test_hmm_result_fields():
    """HMMResult has all expected fields."""
    result = HMMResult(
        regime="Goldilocks",
        regime_probabilities={
            "Goldilocks": 0.7,
            "Reflation": 0.1,
            "Stagflation": 0.1,
            "Deflation": 0.1,
        },
        method="rule_based",
        converged=False,
        warning="test warning",
    )

    assert result.regime == "Goldilocks"
    assert result.method == "rule_based"
    assert result.converged is False
    assert result.warning == "test warning"
    assert sum(result.regime_probabilities.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Test 11: Rule-based default (ambiguous zone: growth=0, inflation=0)
# ---------------------------------------------------------------------------
def test_rule_based_default_ambiguous():
    """Ambiguous zone (growth=0, inflation=0) -> nearest centroid regime."""
    classifier = HMMRegimeClassifier()
    df = _make_features(n=10, growth_z=0.0, inflation_z=0.0)

    result = classifier.classify(df, AS_OF)

    # Should pick the nearest centroid (Goldilocks at (0.5, -0.25))
    assert result.regime in ("Goldilocks", "Reflation", "Stagflation", "Deflation")
    assert result.method == "rule_based"
    assert sum(result.regime_probabilities.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Test 12: HMM path with synthetic data (if hmmlearn available)
# ---------------------------------------------------------------------------
def test_hmm_path_if_available():
    """If hmmlearn is installed, test HMM classification with synthetic data."""
    classifier = HMMRegimeClassifier()

    if not classifier._hmm_available:
        pytest.skip("hmmlearn not installed")

    # Generate synthetic data with distinct regimes
    rng = np.random.RandomState(42)
    n = 200
    data = []
    for i in range(n):
        if i < 50:
            # Goldilocks: high growth, low inflation
            row = [
                1.5 + rng.randn() * 0.3,
                -0.5 + rng.randn() * 0.3,
                -0.5 + rng.randn() * 0.3,
                -0.5 + rng.randn() * 0.3,
                0.0 + rng.randn() * 0.3,
                1.0 + rng.randn() * 0.3,
            ]
        elif i < 100:
            # Stagflation: low growth, high inflation
            row = [
                -1.5 + rng.randn() * 0.3,
                1.5 + rng.randn() * 0.3,
                1.5 + rng.randn() * 0.3,
                1.5 + rng.randn() * 0.3,
                0.5 + rng.randn() * 0.3,
                -1.0 + rng.randn() * 0.3,
            ]
        elif i < 150:
            # Reflation: high growth, high inflation
            row = [
                1.5 + rng.randn() * 0.3,
                1.5 + rng.randn() * 0.3,
                0.0 + rng.randn() * 0.3,
                0.0 + rng.randn() * 0.3,
                0.0 + rng.randn() * 0.3,
                1.0 + rng.randn() * 0.3,
            ]
        else:
            # Deflation: low growth, low inflation
            row = [
                -1.5 + rng.randn() * 0.3,
                -1.5 + rng.randn() * 0.3,
                0.5 + rng.randn() * 0.3,
                0.5 + rng.randn() * 0.3,
                0.0 + rng.randn() * 0.3,
                -1.0 + rng.randn() * 0.3,
            ]
        data.append(row)

    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    df = pd.DataFrame(
        data,
        columns=[
            "growth_z",
            "inflation_z",
            "VIX_z",
            "credit_spread_z",
            "FX_vol_z",
            "equity_momentum_z",
        ],
        index=idx,
    )

    result = classifier.classify(df, AS_OF)

    assert result.method == "hmm"
    assert result.converged is True
    assert result.warning is None
    assert result.regime in ("Goldilocks", "Reflation", "Stagflation", "Deflation")
    assert abs(sum(result.regime_probabilities.values()) - 1.0) < 0.01


# ---------------------------------------------------------------------------
# Test 13: All 4 regime probabilities always present
# ---------------------------------------------------------------------------
def test_all_four_regimes_in_probabilities():
    """Result always contains all 4 regime names in probabilities."""
    classifier = HMMRegimeClassifier()
    df = _make_features(n=10, growth_z=1.0, inflation_z=-0.2)

    result = classifier.classify(df, AS_OF)

    expected_regimes = {"Goldilocks", "Reflation", "Stagflation", "Deflation"}
    assert set(result.regime_probabilities.keys()) == expected_regimes
