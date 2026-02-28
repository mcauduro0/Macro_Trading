"""Unit tests for CrossAssetView dataclass and CrossAssetViewBuilder.

Tests cover:
- Builder produces frozen CrossAssetView correctly
- Regime probabilities validation (sums to ~1.0)
- Builder raises on missing required fields
- All supporting dataclasses (AssetClassView, TailRiskAssessment, KeyTrade, ConsistencyIssue)
"""

from __future__ import annotations

from datetime import date

import pytest

from src.agents.cross_asset_view import (
    AssetClassView,
    ConsistencyIssue,
    CrossAssetView,
    CrossAssetViewBuilder,
    KeyTrade,
    TailRiskAssessment,
)


# ---------------------------------------------------------------------------
# Test 1: Builder builds frozen dataclass correctly
# ---------------------------------------------------------------------------
def test_builder_produces_frozen_view():
    """CrossAssetViewBuilder.build() returns a frozen CrossAssetView."""
    builder = CrossAssetViewBuilder()
    builder.set_regime("Goldilocks")
    builder.set_regime_probabilities(
        {"Goldilocks": 0.7, "Reflation": 0.1, "Stagflation": 0.1, "Deflation": 0.1}
    )
    builder.set_as_of_date(date(2024, 6, 30))
    builder.set_risk_appetite(65.0)
    builder.set_narrative("Test narrative.")
    builder.add_risk_warning("Test warning")

    view = builder.build()

    assert isinstance(view, CrossAssetView)
    assert view.regime == "Goldilocks"
    assert view.risk_appetite == 65.0
    assert view.narrative == "Test narrative."
    assert "Test warning" in view.risk_warnings
    assert view.as_of_date == date(2024, 6, 30)

    # Frozen: should not allow mutation
    with pytest.raises(AttributeError):
        view.regime = "Reflation"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 2: Regime probabilities must sum to ~1.0
# ---------------------------------------------------------------------------
def test_builder_validates_probabilities_sum():
    """Builder raises ValueError if probabilities do not sum to ~1.0."""
    builder = CrossAssetViewBuilder()
    builder.set_regime("Goldilocks")
    builder.set_regime_probabilities(
        {"Goldilocks": 0.5, "Reflation": 0.1, "Stagflation": 0.1, "Deflation": 0.1}
    )
    builder.set_as_of_date(date(2024, 6, 30))

    with pytest.raises(ValueError, match="regime_probabilities must sum to"):
        builder.build()


# ---------------------------------------------------------------------------
# Test 3: Builder allows small floating-point tolerance
# ---------------------------------------------------------------------------
def test_builder_accepts_near_one_probabilities():
    """Probabilities summing to 0.9999 should be accepted (within 0.01 tol)."""
    builder = CrossAssetViewBuilder()
    builder.set_regime("Reflation")
    builder.set_regime_probabilities(
        {
            "Goldilocks": 0.25,
            "Reflation": 0.25,
            "Stagflation": 0.2499,
            "Deflation": 0.2501,
        }
    )
    builder.set_as_of_date(date(2024, 6, 30))

    view = builder.build()
    assert view.regime == "Reflation"
    total = sum(view.regime_probabilities.values())
    assert abs(total - 1.0) < 0.01


# ---------------------------------------------------------------------------
# Test 4: Builder raises on missing regime
# ---------------------------------------------------------------------------
def test_builder_raises_on_missing_regime():
    """Builder raises ValueError when regime is not set."""
    builder = CrossAssetViewBuilder()
    builder.set_regime_probabilities(
        {"Goldilocks": 0.7, "Reflation": 0.1, "Stagflation": 0.1, "Deflation": 0.1}
    )
    builder.set_as_of_date(date(2024, 6, 30))

    with pytest.raises(ValueError, match="regime must be set"):
        builder.build()


# ---------------------------------------------------------------------------
# Test 5: Builder raises on missing regime_probabilities
# ---------------------------------------------------------------------------
def test_builder_raises_on_missing_probabilities():
    """Builder raises ValueError when regime_probabilities is not set."""
    builder = CrossAssetViewBuilder()
    builder.set_regime("Goldilocks")
    builder.set_as_of_date(date(2024, 6, 30))

    with pytest.raises(ValueError, match="regime_probabilities must be set"):
        builder.build()


# ---------------------------------------------------------------------------
# Test 6: AssetClassView creation
# ---------------------------------------------------------------------------
def test_asset_class_view_creation():
    """AssetClassView frozen dataclass creates correctly."""
    view = AssetClassView(
        asset_class="FX",
        direction="SHORT",
        conviction=0.8,
        key_driver="carry_differential",
        instruments=("USDBRL",),
    )

    assert view.asset_class == "FX"
    assert view.direction == "SHORT"
    assert view.conviction == 0.8
    assert view.key_driver == "carry_differential"
    assert "USDBRL" in view.instruments

    with pytest.raises(AttributeError):
        view.direction = "LONG"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 7: TailRiskAssessment creation
# ---------------------------------------------------------------------------
def test_tail_risk_assessment_creation():
    """TailRiskAssessment frozen dataclass creates correctly."""
    tr = TailRiskAssessment(
        composite_score=45.0,
        regime_transition_prob=0.25,
        market_indicators=(("VIX_z", 1.5), ("credit_z", 0.8)),
        assessment="moderate",
    )

    assert tr.composite_score == 45.0
    assert tr.regime_transition_prob == 0.25
    assert tr.assessment == "moderate"
    assert len(tr.market_indicators) == 2


# ---------------------------------------------------------------------------
# Test 8: KeyTrade creation
# ---------------------------------------------------------------------------
def test_key_trade_creation():
    """KeyTrade frozen dataclass creates correctly."""
    trade = KeyTrade(
        instrument="USDBRL",
        direction="SHORT",
        conviction=0.85,
        rationale="BRL carry attractive in Goldilocks",
        strategy_id="FX_BR_01",
    )

    assert trade.instrument == "USDBRL"
    assert trade.direction == "SHORT"
    assert trade.conviction == 0.85
    assert trade.strategy_id == "FX_BR_01"


# ---------------------------------------------------------------------------
# Test 9: ConsistencyIssue creation with default penalty
# ---------------------------------------------------------------------------
def test_consistency_issue_default_penalty():
    """ConsistencyIssue has default sizing_penalty of 0.5."""
    issue = ConsistencyIssue(
        rule_id="FX_RATES_CONTRADICTION",
        description="FX and rates signals contradict",
        affected_instruments=("USDBRL", "DI_PRE"),
        severity="warning",
    )

    assert issue.sizing_penalty == 0.5
    assert issue.severity == "warning"
    assert len(issue.affected_instruments) == 2


# ---------------------------------------------------------------------------
# Test 10: Builder with all fields populated
# ---------------------------------------------------------------------------
def test_builder_full_population():
    """Builder populates all fields including optional ones."""
    builder = CrossAssetViewBuilder()
    builder.set_regime("Stagflation")
    builder.set_regime_probabilities(
        {"Goldilocks": 0.1, "Reflation": 0.1, "Stagflation": 0.6, "Deflation": 0.2}
    )
    builder.set_as_of_date(date(2024, 6, 30))
    builder.set_risk_appetite(25.0)
    builder.set_narrative("Stagflation regime with elevated tail risk.")
    builder.add_risk_warning("HMM fallback: insufficient data")
    builder.add_risk_warning("VIX elevated")

    builder.add_asset_class_view(
        AssetClassView(
            asset_class="equities",
            direction="SHORT",
            conviction=0.7,
            key_driver="stagflation_regime",
            instruments=("IBOV_FUT",),
        )
    )

    builder.set_tail_risk(
        TailRiskAssessment(
            composite_score=72.0,
            regime_transition_prob=0.45,
            assessment="critical",
        )
    )

    builder.add_key_trade(
        KeyTrade(
            instrument="IBOV_FUT",
            direction="SHORT",
            conviction=0.7,
            rationale="Stagflation",
        )
    )

    builder.add_consistency_issue(
        ConsistencyIssue(
            rule_id="TEST_RULE",
            description="Test issue",
            sizing_penalty=0.5,
        )
    )

    view = builder.build()

    assert view.regime == "Stagflation"
    assert view.risk_appetite == 25.0
    assert len(view.risk_warnings) == 2
    assert len(view.key_trades) == 1
    assert len(view.consistency_issues) == 1
    assert view.tail_risk is not None
    assert view.tail_risk.assessment == "critical"
    assert "equities" in view.asset_class_views


# ---------------------------------------------------------------------------
# Test 11: Builder defaults as_of_date to today if not set
# ---------------------------------------------------------------------------
def test_builder_defaults_as_of_date():
    """Builder defaults as_of_date to today if not explicitly set."""
    builder = CrossAssetViewBuilder()
    builder.set_regime("Goldilocks")
    builder.set_regime_probabilities(
        {"Goldilocks": 0.7, "Reflation": 0.1, "Stagflation": 0.1, "Deflation": 0.1}
    )

    view = builder.build()
    assert view.as_of_date == date.today()


# ---------------------------------------------------------------------------
# Test 12: Risk appetite clamped to [0, 100]
# ---------------------------------------------------------------------------
def test_risk_appetite_clamped():
    """Risk appetite is clamped to [0, 100] range."""
    builder = CrossAssetViewBuilder()
    builder.set_risk_appetite(150.0)
    assert builder._risk_appetite == 100.0

    builder.set_risk_appetite(-10.0)
    assert builder._risk_appetite == 0.0
