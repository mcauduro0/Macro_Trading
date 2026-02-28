"""Signal aggregation from analytical agents to directional consensus.

SignalAggregator combines signals from 5 agents (inflation, monetary, fiscal,
fx, cross_asset) into per-asset-class directional consensus using a domain-tuned
weighted vote. Conflict detection flags disagreements, and the CrossAsset
bilateral veto reduces exposure under extreme regime conditions.

This module is the canonical import location for ALL signal aggregation classes:
- SignalAggregator / AggregatedSignal -- agent-level aggregation (v1)
- SignalAggregatorV2 / AggregatedSignalV2 -- strategy-level aggregation (v2)

This module is pure computation -- no database or I/O access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from src.agents.base import AgentReport, AgentSignal
from src.core.enums import AssetClass, SignalDirection
from src.strategies.base import StrategyPosition

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Domain-tuned weight matrix: agent_id -> {AssetClass -> weight}.
# Weights per asset class sum to 1.0 across all 5 agents.
DEFAULT_AGENT_WEIGHTS: dict[str, dict[AssetClass, float]] = {
    "inflation_agent": {
        AssetClass.FIXED_INCOME: 0.25,
        AssetClass.FX: 0.10,
        AssetClass.EQUITY_INDEX: 0.10,
        AssetClass.COMMODITY: 0.20,
    },
    "monetary_agent": {
        AssetClass.FIXED_INCOME: 0.35,
        AssetClass.FX: 0.20,
        AssetClass.EQUITY_INDEX: 0.15,
        AssetClass.COMMODITY: 0.10,
    },
    "fiscal_agent": {
        AssetClass.FIXED_INCOME: 0.20,
        AssetClass.FX: 0.15,
        AssetClass.EQUITY_INDEX: 0.20,
        AssetClass.COMMODITY: 0.10,
    },
    "fx_agent": {
        AssetClass.FIXED_INCOME: 0.05,
        AssetClass.FX: 0.40,
        AssetClass.EQUITY_INDEX: 0.10,
        AssetClass.COMMODITY: 0.30,
    },
    "cross_asset_agent": {
        AssetClass.FIXED_INCOME: 0.15,
        AssetClass.FX: 0.15,
        AssetClass.EQUITY_INDEX: 0.45,
        AssetClass.COMMODITY: 0.30,
    },
}

# Asset classes to aggregate across
AGGREGATION_ASSET_CLASSES = [
    AssetClass.FIXED_INCOME,
    AssetClass.FX,
    AssetClass.EQUITY_INDEX,
    AssetClass.COMMODITY,
]

# Direction numeric mapping
_DIRECTION_SCORE: dict[SignalDirection, float] = {
    SignalDirection.LONG: 1.0,
    SignalDirection.SHORT: -1.0,
    SignalDirection.NEUTRAL: 0.0,
}

# Veto thresholds (bilateral)
_VETO_THRESHOLD = 0.7

# Conflict weight threshold -- agents with weight below this are ignored
# for conflict detection purposes
_CONFLICT_WEIGHT_THRESHOLD = 0.10

# Direction classification thresholds
_DIRECTION_THRESHOLD = 0.1


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class AggregatedSignal:
    """Per-asset-class consensus signal from weighted vote aggregation.

    Attributes:
        asset_class: Target asset class.
        direction: Net direction (LONG/SHORT/NEUTRAL) from weighted vote.
        net_score: Weighted sum in [-1, +1].
        confidence: Average confidence of contributing signals, 0-1.
        contributing_agents: Details per contributing agent.
        conflicts_detected: Whether any significant agent disagrees with net.
        conflict_details: Human-readable conflict descriptions.
        veto_applied: True if CrossAsset veto fired (regime score extreme).
        veto_details: Reason for veto.
        timestamp: UTC datetime of aggregation.
    """

    asset_class: AssetClass
    direction: SignalDirection
    net_score: float
    confidence: float
    contributing_agents: list[dict[str, Any]]
    conflicts_detected: bool
    conflict_details: list[str]
    veto_applied: bool
    veto_details: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# SignalAggregator
# ---------------------------------------------------------------------------
class SignalAggregator:
    """Aggregate agent signals into per-asset-class directional consensus.

    Uses a domain-tuned weight matrix to produce weighted vote consensus per
    asset class. Detects conflicts between agents and applies a bilateral
    CrossAsset veto when the regime score is extreme in either direction.

    Args:
        agent_weights: Optional custom weight matrix overriding defaults.
            Shape: {agent_id: {AssetClass: weight}}.
    """

    def __init__(
        self,
        agent_weights: dict[str, dict[AssetClass, float]] | None = None,
    ) -> None:
        self.agent_weights = agent_weights or DEFAULT_AGENT_WEIGHTS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def aggregate(
        self,
        agent_reports: dict[str, AgentReport],
    ) -> list[AggregatedSignal]:
        """Aggregate agent reports into per-asset-class consensus signals.

        For each asset class:
        1. Collects composite/main signals from each reporting agent.
        2. Computes weighted score using domain-tuned weight matrix.
        3. Classifies direction with +/- 0.1 threshold.
        4. Detects conflicts (significant agents disagreeing with net).
        5. Applies bilateral CrossAsset veto if regime score is extreme.

        Args:
            agent_reports: {agent_id: AgentReport} from the 5 agents.

        Returns:
            List of AggregatedSignal, one per asset class.
        """
        # Extract CrossAsset regime score for veto check
        regime_score = self._extract_regime_score(agent_reports)

        results: list[AggregatedSignal] = []
        for asset_class in AGGREGATION_ASSET_CLASSES:
            signal = self._aggregate_asset_class(
                asset_class,
                agent_reports,
                regime_score,
            )
            results.append(signal)

        return results

    def detect_strategy_conflicts(
        self,
        positions: dict[str, list[StrategyPosition]],
    ) -> dict[AssetClass, list[str]]:
        """Detect opposing positions within the same asset class.

        Groups positions by asset class (derived from strategy_id prefix
        mapping) and checks for conflicting directions within each group.

        Args:
            positions: {strategy_id: [StrategyPosition]}.

        Returns:
            {AssetClass: [conflict description strings]}.
        """
        # Strategy-to-asset-class mapping based on strategy_id prefix
        strategy_asset_class = _infer_strategy_asset_class_map(positions)

        # Group positions by asset class
        ac_positions: dict[AssetClass, list[StrategyPosition]] = {}
        for strategy_id, pos_list in positions.items():
            ac = strategy_asset_class.get(strategy_id)
            if ac is not None:
                ac_positions.setdefault(ac, []).extend(pos_list)

        conflicts: dict[AssetClass, list[str]] = {}
        for ac, pos_list in ac_positions.items():
            long_strats = [
                p
                for p in pos_list
                if p.direction == SignalDirection.LONG and abs(p.weight) > 1e-9
            ]
            short_strats = [
                p
                for p in pos_list
                if p.direction == SignalDirection.SHORT and abs(p.weight) > 1e-9
            ]

            if long_strats and short_strats:
                long_ids = sorted({p.strategy_id for p in long_strats})
                short_ids = sorted({p.strategy_id for p in short_strats})
                desc = (
                    f"{ac.value}: LONG by {', '.join(long_ids)} vs "
                    f"SHORT by {', '.join(short_ids)}"
                )
                conflicts.setdefault(ac, []).append(desc)

        return conflicts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _aggregate_asset_class(
        self,
        asset_class: AssetClass,
        agent_reports: dict[str, AgentReport],
        regime_score: float,
    ) -> AggregatedSignal:
        """Compute consensus for a single asset class."""
        contributing: list[dict[str, Any]] = []
        weighted_sum = 0.0
        weight_total = 0.0
        confidence_values: list[float] = []

        for agent_id, report in agent_reports.items():
            weight = self.agent_weights.get(agent_id, {}).get(asset_class, 0.0)
            if weight <= 0:
                continue

            # Find the composite or main signal for this asset class
            signal = self._find_composite_signal(report.signals, agent_id)
            if signal is None:
                continue

            direction_score = _DIRECTION_SCORE.get(signal.direction, 0.0)
            weighted_contribution = direction_score * weight * signal.confidence
            weighted_sum += weighted_contribution
            weight_total += weight
            confidence_values.append(signal.confidence)

            contributing.append(
                {
                    "agent_id": agent_id,
                    "direction": signal.direction.value,
                    "weight": weight,
                    "confidence": signal.confidence,
                }
            )

        # Normalize by non-zero weight sum
        if weight_total > 0:
            net_score = weighted_sum / weight_total
        else:
            net_score = 0.0

        # Clamp to [-1, 1]
        net_score = max(-1.0, min(1.0, net_score))

        # Direction classification
        if net_score > _DIRECTION_THRESHOLD:
            direction = SignalDirection.LONG
        elif net_score < -_DIRECTION_THRESHOLD:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL

        # Confidence = average of contributing signals
        confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else 0.0
        )

        # Conflict detection
        conflict_details: list[str] = []
        for contrib in contributing:
            contrib_direction = SignalDirection(contrib["direction"])
            contrib_weight = contrib["weight"]
            if (
                contrib_weight > _CONFLICT_WEIGHT_THRESHOLD
                and contrib_direction != direction
                and contrib_direction != SignalDirection.NEUTRAL
                and direction != SignalDirection.NEUTRAL
            ):
                conflict_details.append(
                    f"{contrib['agent_id']} signals {contrib_direction.value} "
                    f"(weight={contrib_weight:.2f}) vs net {direction.value}"
                )

        conflicts_detected = len(conflict_details) > 0

        # CrossAsset bilateral veto
        veto_applied = False
        veto_details = ""
        if abs(regime_score) > _VETO_THRESHOLD:
            veto_applied = True
            if regime_score > _VETO_THRESHOLD:
                veto_details = (
                    f"Extreme risk-off regime (score={regime_score:.2f} > "
                    f"{_VETO_THRESHOLD}): reducing exposure by 50%"
                )
            else:
                veto_details = (
                    f"Extreme risk-on/euphoria regime (score={regime_score:.2f} < "
                    f"-{_VETO_THRESHOLD}): reducing exposure by 50%"
                )
            net_score *= 0.5
            # Re-classify direction after veto reduction
            if abs(net_score) <= _DIRECTION_THRESHOLD:
                direction = SignalDirection.NEUTRAL

            log.info(
                "crossasset_veto_applied",
                asset_class=asset_class.value,
                regime_score=regime_score,
                original_net_score=net_score / 0.5,
                reduced_net_score=net_score,
            )

        return AggregatedSignal(
            asset_class=asset_class,
            direction=direction,
            net_score=net_score,
            confidence=confidence,
            contributing_agents=contributing,
            conflicts_detected=conflicts_detected,
            conflict_details=conflict_details,
            veto_applied=veto_applied,
            veto_details=veto_details,
        )

    @staticmethod
    def _find_composite_signal(
        signals: list[AgentSignal],
        agent_id: str,
    ) -> AgentSignal | None:
        """Find the composite or main signal from an agent's output.

        Preference order:
        1. Signal ID ending with "_COMPOSITE"
        2. First signal in the list
        """
        for sig in signals:
            if sig.signal_id.endswith("_COMPOSITE"):
                return sig
        return signals[0] if signals else None

    @staticmethod
    def _extract_regime_score(
        agent_reports: dict[str, AgentReport],
    ) -> float:
        """Extract the CrossAsset regime score for veto evaluation.

        Looks for a signal named CROSSASSET_REGIME from the cross_asset_agent.
        Returns 0.0 if not found.
        """
        ca_report = agent_reports.get("cross_asset_agent")
        if ca_report is None:
            return 0.0

        for signal in ca_report.signals:
            if signal.signal_id == "CROSSASSET_REGIME":
                return signal.value

        return 0.0


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
def _infer_strategy_asset_class_map(
    positions: dict[str, list[StrategyPosition]],
) -> dict[str, AssetClass]:
    """Infer asset class for each strategy from its ID prefix.

    Mapping:
    - RATES_BR_* / CUPOM_* -> FIXED_INCOME
    - FX_BR_* -> FX
    - EQ_* / EQUITY_* -> EQUITY_INDEX
    - COMM_* / COMMODITY_* -> COMMODITY
    - INF_* -> FIXED_INCOME (inflation-linked)
    - SOV_* -> FIXED_INCOME (sovereign risk)

    Falls back to None for unknown prefixes.
    """
    mapping: dict[str, AssetClass] = {}
    for strategy_id in positions:
        upper = strategy_id.upper()
        if upper.startswith(("RATES_", "CUPOM_", "INF_", "SOV_")):
            mapping[strategy_id] = AssetClass.FIXED_INCOME
        elif upper.startswith("FX_"):
            mapping[strategy_id] = AssetClass.FX
        elif upper.startswith(("EQ_", "EQUITY_")):
            mapping[strategy_id] = AssetClass.EQUITY_INDEX
        elif upper.startswith(("COMM_", "COMMODITY_")):
            mapping[strategy_id] = AssetClass.COMMODITY
    return mapping


# ---------------------------------------------------------------------------
# Re-export v2 classes for unified import access
# ---------------------------------------------------------------------------
from src.portfolio.signal_aggregator_v2 import (  # noqa: E402, F401
    AggregatedSignalV2,
    SignalAggregatorV2,
)
