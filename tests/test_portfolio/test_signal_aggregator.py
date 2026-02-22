"""Tests for SignalAggregator: weighted vote, conflict detection, CrossAsset veto.

All tests use synthetic agent reports and strategy positions --
no database or external data required.
"""

from __future__ import annotations

from datetime import date, datetime

from src.agents.base import AgentReport, AgentSignal
from src.core.enums import AssetClass, SignalDirection, SignalStrength
from src.portfolio.signal_aggregator import (
    AggregatedSignal,
    SignalAggregator,
)
from src.strategies.base import StrategyPosition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_signal(
    agent_id: str,
    signal_id: str,
    direction: SignalDirection,
    confidence: float = 0.80,
    value: float = 0.0,
) -> AgentSignal:
    """Create a test AgentSignal."""
    return AgentSignal(
        signal_id=signal_id,
        agent_id=agent_id,
        timestamp=datetime.utcnow(),
        as_of_date=date(2025, 6, 15),
        direction=direction,
        strength=SignalStrength.STRONG,
        confidence=confidence,
        value=value,
        horizon_days=21,
    )


def _make_report(agent_id: str, signals: list[AgentSignal]) -> AgentReport:
    """Create a test AgentReport."""
    return AgentReport(
        agent_id=agent_id,
        as_of_date=date(2025, 6, 15),
        generated_at=datetime.utcnow(),
        signals=signals,
        narrative="Test",
    )


def _all_agents_same_direction(
    direction: SignalDirection,
    confidence: float = 0.80,
    regime_score: float = 0.0,
) -> dict[str, AgentReport]:
    """Create reports where all 5 agents agree on direction."""
    agents = [
        "inflation_agent",
        "monetary_agent",
        "fiscal_agent",
        "fx_agent",
        "cross_asset_agent",
    ]
    reports: dict[str, AgentReport] = {}
    for agent_id in agents:
        sig_id = f"{agent_id.upper()}_COMPOSITE"
        sig = _make_signal(agent_id, sig_id, direction, confidence)
        reports[agent_id] = _make_report(agent_id, [sig])

    # Override cross_asset_agent to include CROSSASSET_REGIME signal
    ca_signals = [
        _make_signal(
            "cross_asset_agent",
            "CROSSASSET_COMPOSITE",
            direction,
            confidence,
        ),
        _make_signal(
            "cross_asset_agent",
            "CROSSASSET_REGIME",
            SignalDirection.NEUTRAL,
            confidence,
            value=regime_score,
        ),
    ]
    reports["cross_asset_agent"] = _make_report("cross_asset_agent", ca_signals)
    return reports


# ---------------------------------------------------------------------------
# Tests: Weighted vote aggregation
# ---------------------------------------------------------------------------
class TestAggregateWeightedVote:
    """Test SignalAggregator.aggregate() weighted vote consensus."""

    def test_aggregate_unanimous_long(self) -> None:
        """All agents agree LONG -> net_score > 0.5, direction=LONG, no conflicts."""
        agg = SignalAggregator()
        reports = _all_agents_same_direction(SignalDirection.LONG)
        results = agg.aggregate(reports)

        assert len(results) == 4  # one per asset class
        for sig in results:
            assert isinstance(sig, AggregatedSignal)
            assert sig.direction == SignalDirection.LONG
            assert sig.net_score > 0.5
            assert not sig.conflicts_detected
            assert not sig.veto_applied

    def test_aggregate_unanimous_short(self) -> None:
        """All agents agree SHORT -> direction=SHORT."""
        agg = SignalAggregator()
        reports = _all_agents_same_direction(SignalDirection.SHORT)
        results = agg.aggregate(reports)

        for sig in results:
            assert sig.direction == SignalDirection.SHORT
            assert sig.net_score < -0.5

    def test_aggregate_conflict(self) -> None:
        """3 agents LONG, 2 agents SHORT -> LONG but conflicts_detected=True."""
        agg = SignalAggregator()

        # inflation, monetary, fiscal -> LONG; fx, cross_asset -> SHORT
        reports = _all_agents_same_direction(SignalDirection.LONG)
        # Override fx and cross_asset to SHORT
        reports["fx_agent"] = _make_report(
            "fx_agent",
            [_make_signal("fx_agent", "FX_AGENT_COMPOSITE", SignalDirection.SHORT)],
        )
        reports["cross_asset_agent"] = _make_report(
            "cross_asset_agent",
            [
                _make_signal(
                    "cross_asset_agent",
                    "CROSSASSET_COMPOSITE",
                    SignalDirection.SHORT,
                ),
                _make_signal(
                    "cross_asset_agent",
                    "CROSSASSET_REGIME",
                    SignalDirection.NEUTRAL,
                    value=0.0,
                ),
            ],
        )

        results = agg.aggregate(reports)
        # At least one asset class should have conflicts
        any_conflict = any(sig.conflicts_detected for sig in results)
        assert any_conflict, "Expected at least one conflict"

    def test_aggregate_neutral_when_balanced(self) -> None:
        """Equal LONG/SHORT with balanced weights -> NEUTRAL."""
        # Use custom weights that are perfectly balanced for FX:
        # inflation=0.25 LONG, monetary=0.25 SHORT, fiscal=0.25 LONG, fx=0.25 SHORT
        custom_weights = {
            "inflation_agent": {
                AssetClass.FIXED_INCOME: 0.25,
                AssetClass.FX: 0.25,
                AssetClass.EQUITY_INDEX: 0.25,
                AssetClass.COMMODITY: 0.25,
            },
            "monetary_agent": {
                AssetClass.FIXED_INCOME: 0.25,
                AssetClass.FX: 0.25,
                AssetClass.EQUITY_INDEX: 0.25,
                AssetClass.COMMODITY: 0.25,
            },
            "fiscal_agent": {
                AssetClass.FIXED_INCOME: 0.25,
                AssetClass.FX: 0.25,
                AssetClass.EQUITY_INDEX: 0.25,
                AssetClass.COMMODITY: 0.25,
            },
            "fx_agent": {
                AssetClass.FIXED_INCOME: 0.25,
                AssetClass.FX: 0.25,
                AssetClass.EQUITY_INDEX: 0.25,
                AssetClass.COMMODITY: 0.25,
            },
        }
        agg = SignalAggregator(agent_weights=custom_weights)

        reports = {
            "inflation_agent": _make_report(
                "inflation_agent",
                [_make_signal("inflation_agent", "INF_COMPOSITE", SignalDirection.LONG)],
            ),
            "monetary_agent": _make_report(
                "monetary_agent",
                [_make_signal("monetary_agent", "MON_COMPOSITE", SignalDirection.SHORT)],
            ),
            "fiscal_agent": _make_report(
                "fiscal_agent",
                [_make_signal("fiscal_agent", "FIS_COMPOSITE", SignalDirection.LONG)],
            ),
            "fx_agent": _make_report(
                "fx_agent",
                [_make_signal("fx_agent", "FX_COMPOSITE", SignalDirection.SHORT)],
            ),
        }

        results = agg.aggregate(reports)
        for sig in results:
            assert sig.direction == SignalDirection.NEUTRAL
            assert abs(sig.net_score) <= 0.1

    def test_no_signals(self) -> None:
        """Empty agent reports -> all NEUTRAL."""
        agg = SignalAggregator()
        results = agg.aggregate({})
        assert len(results) == 4
        for sig in results:
            assert sig.direction == SignalDirection.NEUTRAL
            assert sig.net_score == 0.0

    def test_weights_normalize_with_missing_agents(self) -> None:
        """Only 3 of 5 agents report -> weights renormalize to available agents."""
        agg = SignalAggregator()
        reports = {
            "inflation_agent": _make_report(
                "inflation_agent",
                [_make_signal("inflation_agent", "INF_COMPOSITE", SignalDirection.LONG)],
            ),
            "monetary_agent": _make_report(
                "monetary_agent",
                [_make_signal("monetary_agent", "MON_COMPOSITE", SignalDirection.LONG)],
            ),
            "fiscal_agent": _make_report(
                "fiscal_agent",
                [_make_signal("fiscal_agent", "FIS_COMPOSITE", SignalDirection.LONG)],
            ),
        }

        results = agg.aggregate(reports)
        # Should still produce valid results for all 4 asset classes
        assert len(results) == 4
        for sig in results:
            # All reporting agents are LONG, so direction should be LONG
            # (for FIXED_INCOME where all 3 agents have weight > 0)
            if sig.asset_class == AssetClass.FIXED_INCOME:
                assert sig.direction == SignalDirection.LONG
                assert sig.net_score > 0.1


# ---------------------------------------------------------------------------
# Tests: CrossAsset veto
# ---------------------------------------------------------------------------
class TestCrossAssetVeto:
    """Test bilateral veto: extreme regime score reduces exposure."""

    def test_veto_fires_extreme_risk_off(self) -> None:
        """regime_score > 0.7 -> veto_applied=True, net_score reduced."""
        agg = SignalAggregator()
        reports = _all_agents_same_direction(
            SignalDirection.LONG, regime_score=0.8,
        )
        results = agg.aggregate(reports)

        for sig in results:
            assert sig.veto_applied is True
            assert "risk-off" in sig.veto_details.lower()
            # Score should be reduced compared to non-veto
            assert abs(sig.net_score) <= 0.5

    def test_veto_fires_extreme_risk_on(self) -> None:
        """regime_score < -0.7 -> veto_applied=True (bilateral)."""
        agg = SignalAggregator()
        reports = _all_agents_same_direction(
            SignalDirection.LONG, regime_score=-0.8,
        )
        results = agg.aggregate(reports)

        for sig in results:
            assert sig.veto_applied is True
            assert "euphoria" in sig.veto_details.lower() or "risk-on" in sig.veto_details.lower()

    def test_veto_not_fires_moderate(self) -> None:
        """regime_score = 0.3 -> veto_applied=False."""
        agg = SignalAggregator()
        reports = _all_agents_same_direction(
            SignalDirection.LONG, regime_score=0.3,
        )
        results = agg.aggregate(reports)

        for sig in results:
            assert sig.veto_applied is False
            assert sig.veto_details == ""


# ---------------------------------------------------------------------------
# Tests: Strategy conflict detection
# ---------------------------------------------------------------------------
class TestStrategyConflictDetection:
    """Test detect_strategy_conflicts() for intra-asset-class conflicts."""

    def test_detect_strategy_conflicts(self) -> None:
        """Opposing positions in same asset class -> conflict flagged."""
        agg = SignalAggregator()

        positions = {
            "RATES_BR_01": [
                StrategyPosition(
                    strategy_id="RATES_BR_01",
                    instrument="DI_PRE_365",
                    weight=0.15,
                    confidence=0.8,
                    direction=SignalDirection.LONG,
                    entry_signal="CARRY",
                ),
            ],
            "RATES_BR_02": [
                StrategyPosition(
                    strategy_id="RATES_BR_02",
                    instrument="DI_PRE_720",
                    weight=-0.10,
                    confidence=0.7,
                    direction=SignalDirection.SHORT,
                    entry_signal="TAYLOR",
                ),
            ],
        }

        conflicts = agg.detect_strategy_conflicts(positions)
        assert AssetClass.FIXED_INCOME in conflicts
        assert len(conflicts[AssetClass.FIXED_INCOME]) > 0
        desc = conflicts[AssetClass.FIXED_INCOME][0]
        assert "RATES_BR_01" in desc
        assert "RATES_BR_02" in desc

    def test_no_conflicts_same_direction(self) -> None:
        """Both strategies LONG -> no conflict."""
        agg = SignalAggregator()

        positions = {
            "RATES_BR_01": [
                StrategyPosition(
                    strategy_id="RATES_BR_01",
                    instrument="DI_PRE_365",
                    weight=0.15,
                    confidence=0.8,
                    direction=SignalDirection.LONG,
                    entry_signal="CARRY",
                ),
            ],
            "RATES_BR_02": [
                StrategyPosition(
                    strategy_id="RATES_BR_02",
                    instrument="DI_PRE_720",
                    weight=0.10,
                    confidence=0.7,
                    direction=SignalDirection.LONG,
                    entry_signal="TAYLOR",
                ),
            ],
        }

        conflicts = agg.detect_strategy_conflicts(positions)
        assert AssetClass.FIXED_INCOME not in conflicts
