"""Tests for SignalAggregatorV2 -- enhanced signal aggregation with 3 methods.

Covers:
- confidence_weighted method produces correct conviction sign
- rank_based method is robust to outlier signals
- bayesian method with flat prior equals confidence_weighted
- bayesian method with Stagflation regime tilts inflation strategy weights
- crowding penalty fires at >80% agreement and reduces by 20%
- staleness discount: day-0 full weight, day-3 40% weight, day-5+ excluded
- empty signals list returns empty
- single signal passes through unchanged (no crowding)
"""

from datetime import datetime

import pytest

from src.core.enums import AssetClass, SignalDirection, SignalStrength
from src.portfolio.signal_aggregator_v2 import (
    SignalAggregatorV2,
    _count_business_days,
)
from src.strategies.base import StrategySignal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_signal(
    strategy_id: str,
    z_score: float,
    confidence: float = 0.8,
    instruments: list[str] | None = None,
    timestamp: datetime | None = None,
    asset_class: AssetClass = AssetClass.FIXED_INCOME,
) -> StrategySignal:
    """Create a StrategySignal with sensible defaults."""
    if instruments is None:
        instruments = ["DI_PRE"]
    if timestamp is None:
        timestamp = datetime.utcnow()

    direction = (
        SignalDirection.LONG
        if z_score > 0
        else (SignalDirection.SHORT if z_score < 0 else SignalDirection.NEUTRAL)
    )
    strength = (
        SignalStrength.STRONG
        if abs(z_score) >= 2.0
        else (
            SignalStrength.MODERATE
            if abs(z_score) >= 1.0
            else (
                SignalStrength.WEAK if abs(z_score) >= 0.5 else SignalStrength.NO_SIGNAL
            )
        )
    )

    return StrategySignal(
        strategy_id=strategy_id,
        timestamp=timestamp,
        direction=direction,
        strength=strength,
        confidence=confidence,
        z_score=z_score,
        raw_value=z_score,
        suggested_size=abs(z_score) / 2.0,
        asset_class=asset_class,
        instruments=instruments,
    )


# ---------------------------------------------------------------------------
# Test: confidence_weighted method
# ---------------------------------------------------------------------------
class TestConfidenceWeighted:
    def test_positive_conviction_sign(self):
        """Positive z-scores should produce positive conviction."""
        agg = SignalAggregatorV2(method="confidence_weighted")
        now = datetime.utcnow()
        signals = [
            _make_signal("RATES_BR_01", z_score=1.5, confidence=0.8, timestamp=now),
            _make_signal("RATES_BR_02", z_score=0.8, confidence=0.6, timestamp=now),
        ]
        results = agg.aggregate(signals, as_of=now)
        assert len(results) == 1
        assert results[0].conviction > 0
        assert results[0].direction == SignalDirection.LONG

    def test_negative_conviction_sign(self):
        """Negative z-scores should produce negative conviction."""
        agg = SignalAggregatorV2(method="confidence_weighted")
        now = datetime.utcnow()
        signals = [
            _make_signal("RATES_BR_01", z_score=-1.5, confidence=0.8, timestamp=now),
            _make_signal("RATES_BR_02", z_score=-0.8, confidence=0.6, timestamp=now),
        ]
        results = agg.aggregate(signals, as_of=now)
        assert len(results) == 1
        assert results[0].conviction < 0
        assert results[0].direction == SignalDirection.SHORT

    def test_mixed_signals_weighted_correctly(self):
        """Higher-confidence signal should dominate direction."""
        agg = SignalAggregatorV2(method="confidence_weighted")
        now = datetime.utcnow()
        signals = [
            _make_signal("RATES_BR_01", z_score=2.0, confidence=0.9, timestamp=now),
            _make_signal("RATES_BR_02", z_score=-0.5, confidence=0.3, timestamp=now),
        ]
        results = agg.aggregate(signals, as_of=now)
        assert len(results) == 1
        # High-confidence positive signal should dominate
        assert results[0].conviction > 0


# ---------------------------------------------------------------------------
# Test: rank_based method
# ---------------------------------------------------------------------------
class TestRankBased:
    def test_robust_to_outlier(self):
        """An extreme outlier should not dominate rank-based aggregation."""
        agg = SignalAggregatorV2(method="rank_based")
        now = datetime.utcnow()
        # 3 moderate positives + 1 extreme positive outlier
        signals = [
            _make_signal("RATES_BR_01", z_score=1.0, confidence=0.8, timestamp=now),
            _make_signal("RATES_BR_02", z_score=1.2, confidence=0.8, timestamp=now),
            _make_signal("RATES_BR_03", z_score=1.1, confidence=0.8, timestamp=now),
            _make_signal(
                "RATES_BR_04", z_score=10.0, confidence=0.8, timestamp=now
            ),  # outlier
        ]
        results = agg.aggregate(signals, as_of=now)
        assert len(results) == 1
        # Conviction should be positive but clamped/moderated
        assert results[0].conviction > 0
        # The outlier should NOT push conviction to the extreme
        assert results[0].conviction <= 1.0

    def test_single_signal_passes_through(self):
        """Single signal in rank_based should pass through."""
        agg = SignalAggregatorV2(method="rank_based")
        now = datetime.utcnow()
        signals = [
            _make_signal("RATES_BR_01", z_score=1.5, confidence=0.8, timestamp=now),
        ]
        results = agg.aggregate(signals, as_of=now)
        assert len(results) == 1
        assert results[0].conviction > 0


# ---------------------------------------------------------------------------
# Test: bayesian method
# ---------------------------------------------------------------------------
class TestBayesian:
    def test_flat_prior_equals_confidence_weighted(self):
        """Bayesian without regime_probs should behave like confidence_weighted."""
        now = datetime.utcnow()
        signals = [
            _make_signal("RATES_BR_01", z_score=1.5, confidence=0.8, timestamp=now),
            _make_signal("RATES_BR_02", z_score=0.8, confidence=0.6, timestamp=now),
        ]

        bayesian = SignalAggregatorV2(method="bayesian")
        cw = SignalAggregatorV2(method="confidence_weighted")

        b_results = bayesian.aggregate(signals, regime_probs=None, as_of=now)
        cw_results = cw.aggregate(signals, as_of=now)

        assert len(b_results) == 1
        assert len(cw_results) == 1
        assert abs(b_results[0].conviction - cw_results[0].conviction) < 1e-9

    def test_stagflation_tilts_inflation_higher(self):
        """Under Stagflation, INF_ strategies should be weighted more than RATES_."""
        now = datetime.utcnow()
        # INF strategy with moderate positive signal
        _make_signal(
            "INF_BR_01",
            z_score=1.0,
            confidence=0.7,
            timestamp=now,
        )
        # RATES strategy with same signal
        _make_signal(
            "RATES_BR_01",
            z_score=1.0,
            confidence=0.7,
            timestamp=now,
        )

        # Same instrument for comparison
        inf_signal_single = _make_signal(
            "INF_BR_01",
            z_score=1.0,
            confidence=0.7,
            timestamp=now,
            instruments=["BENCHMARK"],
        )
        rates_signal_single = _make_signal(
            "RATES_BR_01",
            z_score=1.0,
            confidence=0.7,
            timestamp=now,
            instruments=["BENCHMARK"],
        )

        agg = SignalAggregatorV2(method="bayesian")
        stagflation_probs = {
            "Goldilocks": 0.05,
            "Reflation": 0.05,
            "Stagflation": 0.85,
            "Deflation": 0.05,
        }

        # Aggregate with both competing on same instrument
        results = agg.aggregate(
            [inf_signal_single, rates_signal_single],
            regime_probs=stagflation_probs,
            as_of=now,
        )

        assert len(results) == 1
        # Check that INF_ strategy got higher weight in contributions
        contribs = results[0].contributing_strategies
        inf_weight = next(
            c["weight"] for c in contribs if c["strategy_id"] == "INF_BR_01"
        )
        rates_weight = next(
            c["weight"] for c in contribs if c["strategy_id"] == "RATES_BR_01"
        )
        # INF tilt in Stagflation is 1.5, RATES tilt is 0.7
        assert inf_weight > rates_weight

    def test_regime_context_set(self):
        """Bayesian with regime_probs should set regime_context."""
        now = datetime.utcnow()
        signals = [
            _make_signal("RATES_BR_01", z_score=1.0, confidence=0.8, timestamp=now),
        ]
        regime_probs = {
            "Goldilocks": 0.6,
            "Reflation": 0.2,
            "Stagflation": 0.1,
            "Deflation": 0.1,
        }
        agg = SignalAggregatorV2(method="bayesian")
        results = agg.aggregate(signals, regime_probs=regime_probs, as_of=now)
        assert results[0].regime_context == "Goldilocks"


# ---------------------------------------------------------------------------
# Test: crowding penalty
# ---------------------------------------------------------------------------
class TestCrowdingPenalty:
    def test_fires_at_high_agreement(self):
        """Crowding penalty should fire when >80% strategies agree on direction."""
        agg = SignalAggregatorV2(method="confidence_weighted")
        now = datetime.utcnow()
        # 5 signals, all positive -> 100% agreement > 80%
        signals = [
            _make_signal(
                f"RATES_BR_{i:02d}", z_score=1.0, confidence=0.8, timestamp=now
            )
            for i in range(5)
        ]
        results = agg.aggregate(signals, as_of=now)
        assert len(results) == 1
        assert results[0].crowding_applied is True
        assert results[0].crowding_discount == 0.2

    def test_conviction_reduced_by_20_percent(self):
        """Crowding should reduce conviction by exactly 20%."""
        agg_no_crowd = SignalAggregatorV2(
            method="confidence_weighted",
            crowding_threshold=2.0,  # impossible threshold
        )
        agg_crowd = SignalAggregatorV2(
            method="confidence_weighted",
            crowding_threshold=0.8,
        )
        now = datetime.utcnow()
        signals = [
            _make_signal(
                f"RATES_BR_{i:02d}", z_score=1.0, confidence=0.8, timestamp=now
            )
            for i in range(5)
        ]

        no_crowd_results = agg_no_crowd.aggregate(signals, as_of=now)
        crowd_results = agg_crowd.aggregate(signals, as_of=now)

        expected = no_crowd_results[0].conviction * 0.8  # 20% reduction
        assert abs(crowd_results[0].conviction - expected) < 1e-9

    def test_no_crowding_below_threshold(self):
        """No crowding when agreement is below threshold."""
        agg = SignalAggregatorV2(method="confidence_weighted")
        now = datetime.utcnow()
        # 3 positive, 2 negative -> 60% agreement, below 80%
        signals = [
            _make_signal("RATES_BR_01", z_score=1.0, confidence=0.8, timestamp=now),
            _make_signal("RATES_BR_02", z_score=1.0, confidence=0.8, timestamp=now),
            _make_signal("RATES_BR_03", z_score=1.0, confidence=0.8, timestamp=now),
            _make_signal("RATES_BR_04", z_score=-1.0, confidence=0.8, timestamp=now),
            _make_signal("RATES_BR_05", z_score=-1.0, confidence=0.8, timestamp=now),
        ]
        results = agg.aggregate(signals, as_of=now)
        assert results[0].crowding_applied is False


# ---------------------------------------------------------------------------
# Test: staleness discount
# ---------------------------------------------------------------------------
class TestStalenessDiscount:
    def test_day_0_full_weight(self):
        """Day-0 signal should have full weight (factor=1.0)."""
        agg = SignalAggregatorV2(method="confidence_weighted")
        now = datetime.utcnow()
        signals = [
            _make_signal("RATES_BR_01", z_score=1.5, confidence=0.8, timestamp=now),
        ]
        results = agg.aggregate(signals, as_of=now)
        assert len(results) == 1
        assert results[0].staleness_adjustments["RATES_BR_01"] == 1.0

    def test_day_3_40_percent_weight(self):
        """Day-3 signal should have 40% weight (factor = 1.0 - 3/5 = 0.4)."""
        agg = SignalAggregatorV2(method="confidence_weighted", staleness_max_days=5)
        # Create signal 3 business days ago (Mon->Thu, skip weekends)
        now = datetime(2026, 2, 23, 12, 0, 0)  # Monday
        # 3 biz days before Monday = previous Wednesday
        signal_time = datetime(2026, 2, 18, 12, 0, 0)  # Wednesday

        signals = [
            _make_signal(
                "RATES_BR_01", z_score=1.5, confidence=0.8, timestamp=signal_time
            ),
        ]
        results = agg.aggregate(signals, as_of=now)
        assert len(results) == 1
        factor = results[0].staleness_adjustments["RATES_BR_01"]
        assert abs(factor - 0.4) < 1e-9, f"Expected 0.4, got {factor}"

    def test_day_5_plus_excluded(self):
        """Day-5+ signal should be excluded (factor=0.0)."""
        agg = SignalAggregatorV2(method="confidence_weighted", staleness_max_days=5)
        now = datetime(2026, 2, 23, 12, 0, 0)  # Monday
        # 6 business days ago (signal too old)
        signal_time = datetime(2026, 2, 13, 12, 0, 0)  # Friday (>5 biz days before)

        signals = [
            _make_signal(
                "RATES_BR_01", z_score=1.5, confidence=0.8, timestamp=signal_time
            ),
        ]
        results = agg.aggregate(signals, as_of=now)
        # Signal should be excluded entirely
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Test: edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_empty_signals(self):
        """Empty signal list should return empty results."""
        agg = SignalAggregatorV2()
        results = agg.aggregate([])
        assert results == []

    def test_single_signal_no_crowding(self):
        """Single signal should pass through with no crowding applied."""
        agg = SignalAggregatorV2(method="confidence_weighted")
        now = datetime.utcnow()
        signals = [
            _make_signal("RATES_BR_01", z_score=1.5, confidence=0.8, timestamp=now),
        ]
        results = agg.aggregate(signals, as_of=now)
        assert len(results) == 1
        assert results[0].crowding_applied is False
        assert results[0].crowding_discount == 0.0
        # Conviction should be z_score/2.0 = 0.75
        expected_conviction = 1.5 / 2.0  # 0.75
        assert abs(results[0].conviction - expected_conviction) < 1e-9

    def test_method_attribute_set(self):
        """Aggregated result should reflect the method used."""
        now = datetime.utcnow()
        signals = [
            _make_signal("RATES_BR_01", z_score=1.0, confidence=0.8, timestamp=now)
        ]

        for method in ["confidence_weighted", "rank_based", "bayesian"]:
            agg = SignalAggregatorV2(method=method)
            results = agg.aggregate(signals, as_of=now)
            assert results[0].method == method

    def test_invalid_method_raises(self):
        """Invalid method should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid method"):
            SignalAggregatorV2(method="invalid_method")


# ---------------------------------------------------------------------------
# Test: business day counting
# ---------------------------------------------------------------------------
class TestBusinessDays:
    def test_same_day(self):
        """Same datetime should return 0 business days."""
        now = datetime(2026, 2, 23, 12, 0, 0)
        assert _count_business_days(now, now) == 0

    def test_weekday_span(self):
        """Wednesday to Friday = 2 business days."""
        start = datetime(2026, 2, 18, 12, 0, 0)  # Wednesday
        end = datetime(2026, 2, 20, 12, 0, 0)  # Friday
        assert _count_business_days(start, end) == 2

    def test_over_weekend(self):
        """Friday to Monday = 1 business day (Mon only counted)."""
        start = datetime(2026, 2, 20, 12, 0, 0)  # Friday
        end = datetime(2026, 2, 23, 12, 0, 0)  # Monday
        assert _count_business_days(start, end) == 1
