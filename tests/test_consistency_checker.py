"""Unit tests for CrossAssetConsistencyChecker.

Tests cover:
- Each of 7 rules fires on its contradiction condition
- No false positives when signals are consistent
- sizing_penalty is 0.5 on all issues
- check() returns empty list when no contradictions
"""

from __future__ import annotations

import pytest

from src.agents.consistency_checker import CrossAssetConsistencyChecker
from src.agents.cross_asset_view import ConsistencyIssue


# ---------------------------------------------------------------------------
# Helper: create signal dicts
# ---------------------------------------------------------------------------
def _sig(direction: str, value: float = 0.0) -> dict:
    """Create a minimal signal dict."""
    return {"direction": direction, "value": value}


# ---------------------------------------------------------------------------
# Test 1: FX_RATES_CONTRADICTION fires
# ---------------------------------------------------------------------------
def test_fx_rates_contradiction_fires():
    """SHORT USDBRL + SHORT DI -> contradiction."""
    checker = CrossAssetConsistencyChecker()
    agent_signals: dict = {}
    strategy_signals = {
        "USDBRL": _sig("SHORT"),
        "DI_PRE": _sig("SHORT"),
    }

    issues = checker.check(agent_signals, strategy_signals, "Goldilocks")

    rule_ids = [i.rule_id for i in issues]
    assert "FX_RATES_CONTRADICTION" in rule_ids
    issue = [i for i in issues if i.rule_id == "FX_RATES_CONTRADICTION"][0]
    assert issue.sizing_penalty == 0.5


# ---------------------------------------------------------------------------
# Test 2: EQUITY_RATES_CONTRADICTION fires
# ---------------------------------------------------------------------------
def test_equity_rates_contradiction_fires():
    """LONG equities + SHORT DI -> contradiction."""
    checker = CrossAssetConsistencyChecker()
    agent_signals: dict = {}
    strategy_signals = {
        "IBOV_FUT": _sig("LONG"),
        "DI_PRE": _sig("SHORT"),
    }

    issues = checker.check(agent_signals, strategy_signals, "Goldilocks")

    rule_ids = [i.rule_id for i in issues]
    assert "EQUITY_RATES_CONTRADICTION" in rule_ids


# ---------------------------------------------------------------------------
# Test 3: REGIME_FX_MISMATCH fires
# ---------------------------------------------------------------------------
def test_regime_fx_mismatch_fires():
    """Stagflation + SHORT USDBRL -> contradiction."""
    checker = CrossAssetConsistencyChecker()
    agent_signals: dict = {}
    strategy_signals = {
        "USDBRL": _sig("SHORT"),
    }

    issues = checker.check(agent_signals, strategy_signals, "Stagflation")

    rule_ids = [i.rule_id for i in issues]
    assert "REGIME_FX_MISMATCH" in rule_ids


# ---------------------------------------------------------------------------
# Test 4: REGIME_EQUITY_MISMATCH fires for Stagflation
# ---------------------------------------------------------------------------
def test_regime_equity_mismatch_stagflation():
    """Stagflation + LONG equities -> contradiction."""
    checker = CrossAssetConsistencyChecker()
    agent_signals: dict = {}
    strategy_signals = {
        "IBOV_FUT": _sig("LONG"),
    }

    issues = checker.check(agent_signals, strategy_signals, "Stagflation")

    rule_ids = [i.rule_id for i in issues]
    assert "REGIME_EQUITY_MISMATCH" in rule_ids


# ---------------------------------------------------------------------------
# Test 5: REGIME_EQUITY_MISMATCH fires for Deflation
# ---------------------------------------------------------------------------
def test_regime_equity_mismatch_deflation():
    """Deflation + LONG equities -> contradiction."""
    checker = CrossAssetConsistencyChecker()
    agent_signals: dict = {}
    strategy_signals = {
        "IBOV_FUT": _sig("LONG"),
    }

    issues = checker.check(agent_signals, strategy_signals, "Deflation")

    rule_ids = [i.rule_id for i in issues]
    assert "REGIME_EQUITY_MISMATCH" in rule_ids


# ---------------------------------------------------------------------------
# Test 6: INFLATION_RATES_CONTRADICTION fires
# ---------------------------------------------------------------------------
def test_inflation_rates_contradiction_fires():
    """HIGH inflation (SHORT) + LONG DI (receive) -> contradiction."""
    checker = CrossAssetConsistencyChecker()
    agent_signals = {
        "INFLATION_BR": _sig("SHORT"),  # SHORT = high inflation
    }
    strategy_signals = {
        "DI_PRE": _sig("LONG"),  # LONG DI = receive rates
    }

    issues = checker.check(agent_signals, strategy_signals, "Goldilocks")

    rule_ids = [i.rule_id for i in issues]
    assert "INFLATION_RATES_CONTRADICTION" in rule_ids


# ---------------------------------------------------------------------------
# Test 7: RISK_APPETITE_DIRECTION fires
# ---------------------------------------------------------------------------
def test_risk_appetite_direction_fires():
    """Sentiment < 30 + LONG equities -> contradiction."""
    checker = CrossAssetConsistencyChecker()
    agent_signals = {
        "CROSSASSET_SENTIMENT": _sig("SHORT", value=20.0),  # fear
    }
    strategy_signals = {
        "IBOV_FUT": _sig("LONG"),
    }

    issues = checker.check(agent_signals, strategy_signals, "Goldilocks")

    rule_ids = [i.rule_id for i in issues]
    assert "RISK_APPETITE_DIRECTION" in rule_ids


# ---------------------------------------------------------------------------
# Test 8: SOVEREIGN_FX_DIVERGENCE fires
# ---------------------------------------------------------------------------
def test_sovereign_fx_divergence_fires():
    """Elevated sovereign risk (SHORT) + SHORT USDBRL -> contradiction."""
    checker = CrossAssetConsistencyChecker()
    agent_signals = {
        "SOVEREIGN_RISK": _sig("SHORT"),  # SHORT = elevated risk
    }
    strategy_signals = {
        "USDBRL": _sig("SHORT"),  # SHORT = bullish BRL
    }

    issues = checker.check(agent_signals, strategy_signals, "Goldilocks")

    rule_ids = [i.rule_id for i in issues]
    assert "SOVEREIGN_FX_DIVERGENCE" in rule_ids


# ---------------------------------------------------------------------------
# Test 9: No false positives when signals are consistent
# ---------------------------------------------------------------------------
def test_no_false_positives_consistent_signals():
    """Consistent Goldilocks signals -> no issues."""
    checker = CrossAssetConsistencyChecker()
    agent_signals = {
        "CROSSASSET_SENTIMENT": _sig("LONG", value=75.0),  # greed
    }
    strategy_signals = {
        "IBOV_FUT": _sig("LONG"),
        "DI_PRE": _sig("LONG"),   # receive rates = dovish
        "USDBRL": _sig("SHORT"),  # bullish BRL
    }

    issues = checker.check(agent_signals, strategy_signals, "Goldilocks")

    # FX_RATES_CONTRADICTION should not fire (DI is LONG not SHORT)
    # EQUITY_RATES_CONTRADICTION should not fire (DI is LONG not SHORT)
    # REGIME_FX_MISMATCH should not fire (not Stagflation)
    # REGIME_EQUITY_MISMATCH should not fire (not Stagflation/Deflation)
    # RISK_APPETITE_DIRECTION should not fire (sentiment > 30)
    assert len(issues) == 0


# ---------------------------------------------------------------------------
# Test 10: All sizing penalties are 0.5
# ---------------------------------------------------------------------------
def test_all_sizing_penalties_are_half():
    """Every fired rule has sizing_penalty == 0.5."""
    checker = CrossAssetConsistencyChecker()
    # Create maximum contradiction scenario
    agent_signals = {
        "CROSSASSET_SENTIMENT": _sig("SHORT", value=15.0),
        "INFLATION_BR": _sig("SHORT"),
        "SOVEREIGN_RISK": _sig("SHORT"),
    }
    strategy_signals = {
        "USDBRL": _sig("SHORT"),
        "DI_PRE": _sig("SHORT"),
        "IBOV_FUT": _sig("LONG"),
    }

    issues = checker.check(agent_signals, strategy_signals, "Stagflation")

    assert len(issues) > 0
    for issue in issues:
        assert issue.sizing_penalty == 0.5, (
            f"Rule {issue.rule_id} has penalty {issue.sizing_penalty}, expected 0.5"
        )


# ---------------------------------------------------------------------------
# Test 11: Empty signals -> empty issues list
# ---------------------------------------------------------------------------
def test_empty_signals_no_issues():
    """No signals at all -> no contradictions."""
    checker = CrossAssetConsistencyChecker()

    issues = checker.check({}, {}, "Goldilocks")

    assert issues == []


# ---------------------------------------------------------------------------
# Test 12: Check returns ConsistencyIssue instances
# ---------------------------------------------------------------------------
def test_check_returns_consistency_issue_instances():
    """All returned items are ConsistencyIssue dataclass instances."""
    checker = CrossAssetConsistencyChecker()
    strategy_signals = {
        "USDBRL": _sig("SHORT"),
        "DI_PRE": _sig("SHORT"),
    }

    issues = checker.check({}, strategy_signals, "Goldilocks")

    for issue in issues:
        assert isinstance(issue, ConsistencyIssue)


# ---------------------------------------------------------------------------
# Test 13: 7 rules defined
# ---------------------------------------------------------------------------
def test_seven_rules_defined():
    """CrossAssetConsistencyChecker has exactly 7 rules."""
    checker = CrossAssetConsistencyChecker()
    assert len(checker.RULES) == 7


# ---------------------------------------------------------------------------
# Test 14: REGIME_FX_MISMATCH does not fire for non-Stagflation
# ---------------------------------------------------------------------------
def test_regime_fx_mismatch_no_fire_goldilocks():
    """Goldilocks + SHORT USDBRL -> no REGIME_FX_MISMATCH."""
    checker = CrossAssetConsistencyChecker()
    strategy_signals = {
        "USDBRL": _sig("SHORT"),
    }

    issues = checker.check({}, strategy_signals, "Goldilocks")

    rule_ids = [i.rule_id for i in issues]
    assert "REGIME_FX_MISMATCH" not in rule_ids


# ---------------------------------------------------------------------------
# Test 15: REGIME_EQUITY_MISMATCH does not fire for Goldilocks
# ---------------------------------------------------------------------------
def test_regime_equity_mismatch_no_fire_goldilocks():
    """Goldilocks + LONG equities -> no REGIME_EQUITY_MISMATCH."""
    checker = CrossAssetConsistencyChecker()
    strategy_signals = {
        "IBOV_FUT": _sig("LONG"),
    }

    issues = checker.check({}, strategy_signals, "Goldilocks")

    rule_ids = [i.rule_id for i in issues]
    assert "REGIME_EQUITY_MISMATCH" not in rule_ids


# ---------------------------------------------------------------------------
# Test 16: RISK_APPETITE_DIRECTION does not fire when sentiment >= 30
# ---------------------------------------------------------------------------
def test_risk_appetite_no_fire_neutral():
    """Sentiment at 50 + LONG equities -> no RISK_APPETITE_DIRECTION."""
    checker = CrossAssetConsistencyChecker()
    agent_signals = {
        "CROSSASSET_SENTIMENT": _sig("NEUTRAL", value=50.0),
    }
    strategy_signals = {
        "IBOV_FUT": _sig("LONG"),
    }

    issues = checker.check(agent_signals, strategy_signals, "Goldilocks")

    rule_ids = [i.rule_id for i in issues]
    assert "RISK_APPETITE_DIRECTION" not in rule_ids
