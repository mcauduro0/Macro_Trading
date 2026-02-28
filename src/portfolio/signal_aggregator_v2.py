"""Enhanced signal aggregation v2 with Bayesian regime-aware priors.

SignalAggregatorV2 works on StrategySignal objects (from src.strategies.base)
rather than AgentSignal. It provides three aggregation methods:

1. confidence_weighted: Weighted average using confidence and staleness
2. rank_based: Rank-based aggregation robust to outliers
3. bayesian (default): Bayesian with optional regime-aware strategy tilting

Additional features:
- Staleness discount: Linear decay to zero over configurable business days
- Crowding penalty: 20% conviction reduction when >80% strategies agree
- Regime tilting: Regime probabilities shift which strategies to trust

This module is pure computation -- no database or I/O access.
The original signal_aggregator.py is preserved for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import structlog

from src.core.enums import SignalDirection

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Regime-strategy tilt matrix
# ---------------------------------------------------------------------------
# Maps regime -> strategy_id prefix -> tilt multiplier.
# Determines WHICH strategies to trust based on the current regime.
# Values > 1.0 increase trust; < 1.0 decrease trust.
REGIME_STRATEGY_TILTS: dict[str, dict[str, float]] = {
    "Goldilocks": {
        "RATES_": 1.0,
        "FX_": 1.0,
        "INF_": 0.8,
        "CUPOM_": 1.0,
        "SOV_": 0.9,
        "EQ_": 1.2,
        "EQUITY_": 1.2,
        "CROSS_": 1.0,
        "COMM_": 0.9,
        "COMMODITY_": 0.9,
    },
    "Reflation": {
        "RATES_": 0.8,
        "FX_": 1.0,
        "INF_": 1.3,
        "CUPOM_": 0.9,
        "SOV_": 0.8,
        "EQ_": 1.1,
        "EQUITY_": 1.1,
        "CROSS_": 1.0,
        "COMM_": 1.3,
        "COMMODITY_": 1.3,
    },
    "Stagflation": {
        "RATES_": 0.7,
        "FX_": 0.7,
        "INF_": 1.5,
        "CUPOM_": 0.8,
        "SOV_": 1.2,
        "EQ_": 0.6,
        "EQUITY_": 0.6,
        "CROSS_": 1.0,
        "COMM_": 1.2,
        "COMMODITY_": 1.2,
    },
    "Deflation": {
        "RATES_": 1.3,
        "FX_": 0.9,
        "INF_": 0.6,
        "CUPOM_": 1.1,
        "SOV_": 1.3,
        "EQ_": 0.7,
        "EQUITY_": 0.7,
        "CROSS_": 1.0,
        "COMM_": 0.7,
        "COMMODITY_": 0.7,
    },
}

# Direction classification thresholds (half of Phase 12's 0.1, for strategy-level granularity)
_DIRECTION_THRESHOLD = 0.05

# Valid aggregation methods
_VALID_METHODS = {"confidence_weighted", "rank_based", "bayesian"}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class AggregatedSignalV2:
    """Per-instrument aggregated signal from strategy-level aggregation.

    Attributes:
        instrument: Target instrument identifier.
        direction: Net direction (LONG/SHORT/NEUTRAL) from aggregation.
        conviction: Aggregate conviction score in [-1, +1].
        confidence: Average confidence of contributing signals in [0, 1].
        method: Aggregation method used.
        contributing_strategies: Details per strategy contribution.
        crowding_applied: Whether crowding penalty fired.
        crowding_discount: Crowding discount applied (0.0 or 0.2).
        staleness_adjustments: {strategy_id: staleness discount factor}.
        regime_context: Regime name if Bayesian used, else None.
        timestamp: UTC datetime of aggregation.
    """

    instrument: str
    direction: SignalDirection
    conviction: float
    confidence: float
    method: str
    contributing_strategies: list[dict] = field(default_factory=list)
    crowding_applied: bool = False
    crowding_discount: float = 0.0
    staleness_adjustments: dict[str, float] = field(default_factory=dict)
    regime_context: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Business day helpers
# ---------------------------------------------------------------------------
def _count_business_days(start: datetime, end: datetime) -> int:
    """Count business days between start and end (inclusive of start, exclusive of end).

    Uses a simple weekday check (Mon-Fri). Does not account for holidays.

    Args:
        start: Start datetime.
        end: End datetime.

    Returns:
        Number of business days elapsed.
    """
    if end <= start:
        return 0

    start_date = start.date() if isinstance(start, datetime) else start
    end_date = end.date() if isinstance(end, datetime) else end

    count = 0
    current = start_date
    while current < end_date:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Monday=0 to Friday=4
            count += 1

    return count


# ---------------------------------------------------------------------------
# SignalAggregatorV2
# ---------------------------------------------------------------------------
class SignalAggregatorV2:
    """Enhanced signal aggregator with 3 methods, crowding, staleness, and regime tilting.

    Aggregates StrategySignal objects per instrument using one of three methods:
    - confidence_weighted: Weighted average (simple, intuitive)
    - rank_based: Rank-based (robust to outliers)
    - bayesian: Bayesian with optional regime-aware strategy tilting (default)

    Features applied to all methods:
    - Staleness discount: Linear decay over staleness_max_days business days
    - Crowding penalty: Gentle 20% reduction when >80% strategies agree

    Args:
        method: Default aggregation method ("bayesian", "confidence_weighted", "rank_based").
        staleness_max_days: Business days until signal weight reaches zero.
        crowding_threshold: Fraction of agreement to trigger crowding penalty.
        crowding_discount: Conviction reduction when crowding fires (0.2 = 20%).
    """

    def __init__(
        self,
        method: str = "bayesian",
        staleness_max_days: int = 5,
        crowding_threshold: float = 0.80,
        crowding_discount: float = 0.20,
    ) -> None:
        if method not in _VALID_METHODS:
            raise ValueError(
                f"Invalid method '{method}'. Must be one of: {_VALID_METHODS}"
            )
        self.method = method
        self.staleness_max_days = staleness_max_days
        self.crowding_threshold = crowding_threshold
        self.crowding_discount = crowding_discount

    def aggregate(
        self,
        signals: list,  # Accepts StrategySignal or StrategyPosition objects
        regime_probs: dict[str, float] | None = None,
        as_of: datetime | None = None,
    ) -> list[AggregatedSignalV2]:
        """Aggregate strategy signals into per-instrument consensus.

        Groups signals by instrument, applies staleness discount, runs the
        chosen aggregation method, and applies crowding penalty.

        Args:
            signals: List of StrategySignal objects from strategies.
            regime_probs: Optional regime probability dict (e.g.,
                {"Goldilocks": 0.6, "Reflation": 0.2, ...}) from CrossAssetView.
            as_of: Reference datetime for staleness calculation (default: now).

        Returns:
            List of AggregatedSignalV2, one per instrument.
        """
        if not signals:
            return []

        if as_of is None:
            as_of = datetime.utcnow()

        # Group signals by instrument
        # Support both StrategySignal (.instruments: list) and
        # StrategyPosition (.instrument: str) via duck typing.
        instrument_groups: dict[str, list] = {}
        for sig in signals:
            if hasattr(sig, "instruments"):
                instr_list = sig.instruments
            elif hasattr(sig, "instrument"):
                instr_list = [sig.instrument]
            else:
                continue
            for instr in instr_list:
                instrument_groups.setdefault(instr, []).append(sig)

        results: list[AggregatedSignalV2] = []
        for instrument, group_signals in sorted(instrument_groups.items()):
            agg = self._aggregate_instrument(
                instrument,
                group_signals,
                regime_probs,
                as_of,
            )
            if agg is not None:
                results.append(agg)

        return results

    # ------------------------------------------------------------------
    # Internal: per-instrument aggregation
    # ------------------------------------------------------------------
    def _aggregate_instrument(
        self,
        instrument: str,
        signals: list,
        regime_probs: dict[str, float] | None,
        as_of: datetime,
    ) -> AggregatedSignalV2 | None:
        """Aggregate signals for a single instrument."""

        # Compute staleness factors
        staleness_map: dict[str, float] = {}
        active_signals: list[tuple] = []  # (signal, staleness_factor)

        for sig in signals:
            # StrategySignal has .timestamp; StrategyPosition does not.
            # Treat missing timestamp as fresh (staleness = 0 days).
            sig_ts = getattr(sig, "timestamp", as_of)
            days = _count_business_days(sig_ts, as_of)
            factor = max(0.0, 1.0 - days / self.staleness_max_days)
            staleness_map[sig.strategy_id] = factor
            if factor > 0:
                active_signals.append((sig, factor))

        if not active_signals:
            return None

        # Run aggregation method
        if self.method == "confidence_weighted":
            conviction, confidence, contribs = self._confidence_weighted(
                active_signals,
            )
        elif self.method == "rank_based":
            conviction, confidence, contribs = self._rank_based(
                active_signals,
            )
        else:  # bayesian
            conviction, confidence, contribs = self._bayesian(
                active_signals,
                regime_probs,
            )

        # Apply crowding penalty
        crowding_applied = False
        crowding_discount_val = 0.0

        if len(active_signals) > 1:
            positive_count = sum(
                1 for sig, _ in active_signals if self._signal_conviction(sig) > 0
            )
            negative_count = sum(
                1 for sig, _ in active_signals if self._signal_conviction(sig) < 0
            )
            total = len(active_signals)
            agreement_fraction = max(positive_count, negative_count) / total

            if agreement_fraction > self.crowding_threshold:
                crowding_applied = True
                crowding_discount_val = self.crowding_discount
                conviction *= 1.0 - self.crowding_discount

                log.info(
                    "crowding_penalty_applied",
                    instrument=instrument,
                    agreement_fraction=agreement_fraction,
                    conviction_before=conviction / (1.0 - self.crowding_discount),
                    conviction_after=conviction,
                )

        # Clamp conviction to [-1, +1]
        conviction = max(-1.0, min(1.0, conviction))

        # Direction classification
        if conviction > _DIRECTION_THRESHOLD:
            direction = SignalDirection.LONG
        elif conviction < -_DIRECTION_THRESHOLD:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL

        # Determine regime context
        regime_context = None
        if self.method == "bayesian" and regime_probs:
            # Use highest-probability regime as context label
            regime_context = max(regime_probs, key=regime_probs.get)

        return AggregatedSignalV2(
            instrument=instrument,
            direction=direction,
            conviction=conviction,
            confidence=confidence,
            method=self.method,
            contributing_strategies=contribs,
            crowding_applied=crowding_applied,
            crowding_discount=crowding_discount_val,
            staleness_adjustments=staleness_map,
            regime_context=regime_context,
        )

    # ------------------------------------------------------------------
    # Method 1: Confidence-weighted average
    # ------------------------------------------------------------------
    def _confidence_weighted(
        self,
        active_signals: list[tuple],
    ) -> tuple[float, float, list[dict]]:
        """Confidence-weighted average aggregation.

        weighted_sum = sum(conviction * confidence * staleness_factor)
        weight_total = sum(confidence * staleness_factor)
        result = weighted_sum / weight_total

        Returns:
            (conviction, confidence, contributing_strategies)
        """
        weighted_sum = 0.0
        weight_total = 0.0
        confidence_values: list[float] = []
        contribs: list[dict] = []

        for sig, staleness_factor in active_signals:
            conviction = self._signal_conviction(sig)
            w = sig.confidence * staleness_factor
            weighted_sum += conviction * w
            weight_total += w
            confidence_values.append(sig.confidence)
            contribs.append(
                {
                    "strategy_id": sig.strategy_id,
                    "raw_signal": conviction,
                    "weight": w,
                    "staleness_days": (
                        round(1.0 - staleness_factor, 2) * self.staleness_max_days
                        if staleness_factor < 1.0
                        else 0
                    ),
                }
            )

        conviction = weighted_sum / weight_total if weight_total > 0 else 0.0
        confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else 0.0
        )

        return conviction, confidence, contribs

    # ------------------------------------------------------------------
    # Method 2: Rank-based
    # ------------------------------------------------------------------
    def _rank_based(
        self,
        active_signals: list[tuple],
    ) -> tuple[float, float, list[dict]]:
        """Rank-based aggregation, robust to outliers.

        Ranks signals by conviction magnitude. Assigns rank scores from
        -1.0 (bottom) to +1.0 (top), preserving direction. Final conviction
        is the mean of rank-weighted scores.

        Returns:
            (conviction, confidence, contributing_strategies)
        """
        # Get convictions with staleness
        entries: list[tuple] = []  # (sig, staleness, conviction)
        for sig, staleness_factor in active_signals:
            conv = self._signal_conviction(sig)
            entries.append((sig, staleness_factor, conv))

        # Sort by conviction (ascending)
        entries.sort(key=lambda x: x[2])
        n = len(entries)

        confidence_values: list[float] = []
        contribs: list[dict] = []
        rank_scores: list[float] = []

        for rank_idx, (sig, staleness_factor, conv) in enumerate(entries):
            # Assign rank score: linearly from -1.0 (rank 0) to +1.0 (rank n-1)
            if n == 1:
                rank_score = conv  # Single signal passes through
            else:
                rank_score = -1.0 + 2.0 * rank_idx / (n - 1)

            # Preserve original direction sign
            if conv < 0 and rank_score > 0:
                rank_score = -abs(rank_score)
            elif conv > 0 and rank_score < 0:
                rank_score = abs(rank_score)

            weighted_rank = rank_score * staleness_factor
            rank_scores.append(weighted_rank)
            confidence_values.append(sig.confidence)

            contribs.append(
                {
                    "strategy_id": sig.strategy_id,
                    "raw_signal": conv,
                    "weight": staleness_factor,
                    "staleness_days": round(
                        (1.0 - staleness_factor) * self.staleness_max_days, 1
                    ),
                }
            )

        conviction = sum(rank_scores) / len(rank_scores) if rank_scores else 0.0
        confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else 0.0
        )

        return conviction, confidence, contribs

    # ------------------------------------------------------------------
    # Method 3: Bayesian with regime prior
    # ------------------------------------------------------------------
    def _bayesian(
        self,
        active_signals: list[tuple],
        regime_probs: dict[str, float] | None,
    ) -> tuple[float, float, list[dict]]:
        """Bayesian aggregation with optional regime-aware strategy tilting.

        When regime_probs provided: tilts which strategies to trust based on
        regime probabilities. The tilt is computed as:
            tilt = sum(regime_prob * tilt_factor for each regime)

        When no regime_probs: flat prior (all strategies equally weighted by
        confidence and staleness -- equivalent to confidence_weighted).

        Returns:
            (conviction, confidence, contributing_strategies)
        """
        weighted_sum = 0.0
        weight_total = 0.0
        confidence_values: list[float] = []
        contribs: list[dict] = []

        for sig, staleness_factor in active_signals:
            conviction = self._signal_conviction(sig)
            regime_tilt = self._compute_regime_tilt(sig.strategy_id, regime_probs)

            w = sig.confidence * staleness_factor * regime_tilt
            weighted_sum += conviction * w
            weight_total += w
            confidence_values.append(sig.confidence)

            contribs.append(
                {
                    "strategy_id": sig.strategy_id,
                    "raw_signal": conviction,
                    "weight": w,
                    "staleness_days": round(
                        (1.0 - staleness_factor) * self.staleness_max_days, 1
                    ),
                    "regime_tilt": regime_tilt,
                }
            )

        conviction = weighted_sum / weight_total if weight_total > 0 else 0.0
        confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else 0.0
        )

        return conviction, confidence, contribs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _signal_conviction(sig) -> float:
        """Derive conviction from a signal object.

        For StrategySignal: conviction = z_score / 2.0, clamped to [-1, +1].
        For StrategyPosition: conviction = weight (already in [-1, +1]).
        """
        if hasattr(sig, "z_score"):
            return max(-1.0, min(1.0, sig.z_score / 2.0))
        # StrategyPosition: use weight directly (already in [-1, 1])
        if hasattr(sig, "weight"):
            return max(-1.0, min(1.0, sig.weight))
        return 0.0

    @staticmethod
    def _compute_regime_tilt(
        strategy_id: str,
        regime_probs: dict[str, float] | None,
    ) -> float:
        """Compute regime-weighted tilt for a strategy.

        Tilt = sum(regime_prob * tilt_factor) across all regimes.
        Returns 1.0 (flat prior) if no regime_probs provided.

        Args:
            strategy_id: Strategy identifier (prefix used for matching).
            regime_probs: {regime_name: probability}.

        Returns:
            Tilt multiplier (positive float).
        """
        if not regime_probs:
            return 1.0

        upper_id = strategy_id.upper()
        total_tilt = 0.0

        for regime_name, regime_prob in regime_probs.items():
            tilt_map = REGIME_STRATEGY_TILTS.get(regime_name, {})
            # Find matching prefix
            matched = False
            for prefix, tilt_factor in tilt_map.items():
                if upper_id.startswith(prefix):
                    total_tilt += regime_prob * tilt_factor
                    matched = True
                    break
            if not matched:
                # Default tilt of 1.0 for unknown strategy prefixes
                total_tilt += regime_prob * 1.0

        return max(0.01, total_tilt)  # Floor at 0.01 to avoid division by zero
