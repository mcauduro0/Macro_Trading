"""Tests for BaseStrategy ABC, StrategyConfig, StrategyPosition, StrategySignal,
signals_to_positions, and v3.0 utility methods.

Validates the strategy framework's constraint engine, weight formula,
position limit enforcement, z-score computation, conviction sizing, and
strength classification.
"""

from datetime import date, datetime

import pytest

from src.agents.base import AgentSignal
from src.core.enums import AssetClass, Frequency, SignalDirection, SignalStrength
from src.strategies.base import (
    STRENGTH_MAP,
    BaseStrategy,
    StrategyConfig,
    StrategyPosition,
    StrategySignal,
)


# ---------------------------------------------------------------------------
# DummyStrategy for testing abstract base
# ---------------------------------------------------------------------------
class DummyStrategy(BaseStrategy):
    """Concrete strategy subclass for testing BaseStrategy ABC."""

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        return [
            StrategyPosition(
                strategy_id=self.config.strategy_id,
                instrument="TEST_INSTR",
                weight=0.5,
                confidence=0.8,
                direction=SignalDirection.LONG,
                entry_signal="DUMMY_SIGNAL",
            )
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_config(**overrides) -> StrategyConfig:
    """Create a StrategyConfig with sensible defaults, applying overrides."""
    defaults = dict(
        strategy_id="TEST_STRAT",
        strategy_name="Test Strategy",
        asset_class=AssetClass.FIXED_INCOME,
        instruments=["DI_PRE"],
        rebalance_frequency=Frequency.DAILY,
        max_position_size=1.0,
        max_leverage=3.0,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
    )
    defaults.update(overrides)
    return StrategyConfig(**defaults)


def _make_signal(
    direction: SignalDirection = SignalDirection.LONG,
    strength: SignalStrength = SignalStrength.STRONG,
    confidence: float = 0.9,
    signal_id: str = "TEST_SIGNAL",
) -> AgentSignal:
    """Create an AgentSignal with sensible defaults."""
    return AgentSignal(
        signal_id=signal_id,
        agent_id="test_agent",
        timestamp=datetime(2025, 6, 15, 12, 0, 0),
        as_of_date=date(2025, 6, 15),
        direction=direction,
        strength=strength,
        confidence=confidence,
        value=0.5,
        horizon_days=21,
    )


# ---------------------------------------------------------------------------
# StrategyConfig tests
# ---------------------------------------------------------------------------
class TestStrategyConfig:
    def test_frozen_immutable(self) -> None:
        """StrategyConfig should be frozen (immutable)."""
        config = _make_config()
        with pytest.raises(AttributeError):
            config.strategy_id = "CHANGED"

    def test_all_fields_present(self) -> None:
        """StrategyConfig should have all 9 required fields."""
        config = _make_config()
        assert config.strategy_id == "TEST_STRAT"
        assert config.strategy_name == "Test Strategy"
        assert config.asset_class == AssetClass.FIXED_INCOME
        assert config.instruments == ["DI_PRE"]
        assert config.rebalance_frequency == Frequency.DAILY
        assert config.max_position_size == 1.0
        assert config.max_leverage == 3.0
        assert config.stop_loss_pct == 0.05
        assert config.take_profit_pct == 0.10

    def test_frozen_flag_set(self) -> None:
        """The dataclass frozen parameter should be True."""
        assert StrategyConfig.__dataclass_params__.frozen is True


# ---------------------------------------------------------------------------
# StrategyPosition tests
# ---------------------------------------------------------------------------
class TestStrategyPosition:
    def test_fields_and_defaults(self) -> None:
        """StrategyPosition should have correct fields with metadata default."""
        pos = StrategyPosition(
            strategy_id="S1",
            instrument="DI_PRE",
            weight=0.5,
            confidence=0.8,
            direction=SignalDirection.LONG,
            entry_signal="SIG_1",
        )
        assert pos.strategy_id == "S1"
        assert pos.instrument == "DI_PRE"
        assert pos.weight == 0.5
        assert pos.confidence == 0.8
        assert pos.direction == SignalDirection.LONG
        assert pos.entry_signal == "SIG_1"
        assert pos.metadata == {}  # default_factory=dict

    def test_metadata_custom(self) -> None:
        """Custom metadata should be stored."""
        pos = StrategyPosition(
            strategy_id="S1",
            instrument="DI_PRE",
            weight=0.3,
            confidence=0.6,
            direction=SignalDirection.SHORT,
            entry_signal="SIG_2",
            metadata={"tenor": 365},
        )
        assert pos.metadata == {"tenor": 365}


# ---------------------------------------------------------------------------
# STRENGTH_MAP tests
# ---------------------------------------------------------------------------
class TestStrengthMap:
    def test_strong_value(self) -> None:
        assert STRENGTH_MAP[SignalStrength.STRONG] == 1.0

    def test_moderate_value(self) -> None:
        assert STRENGTH_MAP[SignalStrength.MODERATE] == 0.6

    def test_weak_value(self) -> None:
        assert STRENGTH_MAP[SignalStrength.WEAK] == 0.3

    def test_no_signal_value(self) -> None:
        assert STRENGTH_MAP[SignalStrength.NO_SIGNAL] == 0.0


# ---------------------------------------------------------------------------
# BaseStrategy ABC tests
# ---------------------------------------------------------------------------
class TestBaseStrategyABC:
    def test_cannot_instantiate_directly(self) -> None:
        """BaseStrategy is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            BaseStrategy(config=_make_config())

    def test_strategy_id_property(self) -> None:
        """strategy_id property should return config.strategy_id."""
        strat = DummyStrategy(config=_make_config(strategy_id="MY_STRAT"))
        assert strat.strategy_id == "MY_STRAT"

    def test_generate_signals_returns_positions(self) -> None:
        """DummyStrategy.generate_signals should return list of StrategyPosition."""
        strat = DummyStrategy(config=_make_config())
        positions = strat.generate_signals(date(2025, 6, 15))
        assert len(positions) == 1
        assert isinstance(positions[0], StrategyPosition)


# ---------------------------------------------------------------------------
# signals_to_positions tests
# ---------------------------------------------------------------------------
class TestSignalsToPositions:
    def test_long_signal_weight(self) -> None:
        """LONG signal: weight = strength_base * confidence * max_size."""
        config = _make_config(max_position_size=1.0)
        strat = DummyStrategy(config=config)
        signal = _make_signal(
            direction=SignalDirection.LONG,
            strength=SignalStrength.STRONG,
            confidence=0.8,
        )
        positions = strat.signals_to_positions([signal])
        assert len(positions) == 1
        # STRONG=1.0 * 0.8 * 1.0 = 0.8
        assert positions[0].weight == pytest.approx(0.8)
        assert positions[0].direction == SignalDirection.LONG

    def test_short_signal_negative_weight(self) -> None:
        """SHORT signal: weight should be negative."""
        config = _make_config(max_position_size=1.0)
        strat = DummyStrategy(config=config)
        signal = _make_signal(
            direction=SignalDirection.SHORT,
            strength=SignalStrength.MODERATE,
            confidence=0.7,
        )
        positions = strat.signals_to_positions([signal])
        # MODERATE=0.6 * 0.7 * 1.0 = 0.42, negated
        assert positions[0].weight == pytest.approx(-0.42)

    def test_neutral_with_existing_position(self) -> None:
        """NEUTRAL with existing weight: 50% scale-down."""
        config = _make_config(max_position_size=1.0)
        strat = DummyStrategy(config=config)
        signal = _make_signal(
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.MODERATE,
            confidence=0.5,
            signal_id="DI_PRE",
        )
        positions = strat.signals_to_positions(
            [signal], existing_weights={"DI_PRE": 0.6}
        )
        # NEUTRAL: existing * 0.5 = 0.6 * 0.5 = 0.3
        assert positions[0].weight == pytest.approx(0.3)

    def test_neutral_no_existing_position(self) -> None:
        """NEUTRAL without existing weight: weight = 0.0."""
        config = _make_config()
        strat = DummyStrategy(config=config)
        signal = _make_signal(
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.MODERATE,
            confidence=0.5,
            signal_id="DI_PRE",
        )
        positions = strat.signals_to_positions([signal])
        assert positions[0].weight == pytest.approx(0.0)

    def test_weight_clamped_at_max_position_size(self) -> None:
        """Weight should be clamped to [-max_position_size, max_position_size]."""
        config = _make_config(max_position_size=0.5)
        strat = DummyStrategy(config=config)
        signal = _make_signal(
            direction=SignalDirection.LONG,
            strength=SignalStrength.STRONG,
            confidence=1.0,
        )
        positions = strat.signals_to_positions([signal])
        # STRONG=1.0 * 1.0 * 0.5 = 0.5 (exactly at max)
        assert positions[0].weight == pytest.approx(0.5)

    def test_leverage_enforcement_scales_down(self) -> None:
        """When total abs(weights) exceeds max_leverage, scale proportionally."""
        config = _make_config(max_position_size=2.0, max_leverage=1.0)
        strat = DummyStrategy(config=config)
        sig1 = _make_signal(
            direction=SignalDirection.LONG,
            strength=SignalStrength.STRONG,
            confidence=1.0,
            signal_id="SIG_A",
        )
        sig2 = _make_signal(
            direction=SignalDirection.SHORT,
            strength=SignalStrength.STRONG,
            confidence=1.0,
            signal_id="SIG_B",
        )
        positions = strat.signals_to_positions([sig1, sig2])
        # Raw: SIG_A = 1.0*1.0*2.0 = 2.0, SIG_B = -2.0
        # Total abs = 4.0, max_leverage = 1.0, scale = 1.0/4.0 = 0.25
        # SIG_A = 2.0*0.25 = 0.5, SIG_B = -2.0*0.25 = -0.5
        total_abs = sum(abs(p.weight) for p in positions)
        assert total_abs == pytest.approx(1.0)

    def test_confidence_clamped_in_position(self) -> None:
        """Confidence in output position should be clamped to [0, 1]."""
        config = _make_config()
        strat = DummyStrategy(config=config)
        signal = _make_signal(confidence=1.5)  # out of range
        positions = strat.signals_to_positions([signal])
        assert positions[0].confidence == 1.0

    def test_weak_signal_weight(self) -> None:
        """WEAK signal should use 0.3 multiplier."""
        config = _make_config(max_position_size=1.0)
        strat = DummyStrategy(config=config)
        signal = _make_signal(
            direction=SignalDirection.LONG,
            strength=SignalStrength.WEAK,
            confidence=0.4,
        )
        positions = strat.signals_to_positions([signal])
        # WEAK=0.3 * 0.4 * 1.0 = 0.12
        assert positions[0].weight == pytest.approx(0.12)

    def test_no_signal_strength_zero_weight(self) -> None:
        """NO_SIGNAL strength should produce zero weight."""
        config = _make_config()
        strat = DummyStrategy(config=config)
        signal = _make_signal(
            direction=SignalDirection.LONG,
            strength=SignalStrength.NO_SIGNAL,
            confidence=0.5,
        )
        positions = strat.signals_to_positions([signal])
        assert positions[0].weight == pytest.approx(0.0)

    def test_multiple_signals(self) -> None:
        """Multiple signals should produce multiple positions."""
        config = _make_config()
        strat = DummyStrategy(config=config)
        signals = [
            _make_signal(signal_id="S1", confidence=0.8),
            _make_signal(signal_id="S2", confidence=0.6, direction=SignalDirection.SHORT),
        ]
        positions = strat.signals_to_positions(signals)
        assert len(positions) == 2


# ---------------------------------------------------------------------------
# validate_position tests
# ---------------------------------------------------------------------------
class TestValidatePosition:
    def test_clamps_out_of_range_weight(self) -> None:
        """Weight outside [-1, 1] should be clamped."""
        config = _make_config()
        strat = DummyStrategy(config=config)
        pos = StrategyPosition(
            strategy_id="S1",
            instrument="DI_PRE",
            weight=2.5,
            confidence=0.8,
            direction=SignalDirection.LONG,
            entry_signal="SIG",
        )
        validated = strat.validate_position(pos)
        assert validated.weight == 1.0

    def test_clamps_negative_weight(self) -> None:
        """Negative weight beyond -1 should be clamped to -1."""
        config = _make_config()
        strat = DummyStrategy(config=config)
        pos = StrategyPosition(
            strategy_id="S1",
            instrument="DI_PRE",
            weight=-3.0,
            confidence=0.5,
            direction=SignalDirection.SHORT,
            entry_signal="SIG",
        )
        validated = strat.validate_position(pos)
        assert validated.weight == -1.0

    def test_clamps_out_of_range_confidence(self) -> None:
        """Confidence outside [0, 1] should be clamped."""
        config = _make_config()
        strat = DummyStrategy(config=config)
        pos = StrategyPosition(
            strategy_id="S1",
            instrument="DI_PRE",
            weight=0.5,
            confidence=1.5,
            direction=SignalDirection.LONG,
            entry_signal="SIG",
        )
        validated = strat.validate_position(pos)
        assert validated.confidence == 1.0

    def test_valid_position_unchanged(self) -> None:
        """Valid position should pass through without changes."""
        config = _make_config()
        strat = DummyStrategy(config=config)
        pos = StrategyPosition(
            strategy_id="S1",
            instrument="DI_PRE",
            weight=0.5,
            confidence=0.7,
            direction=SignalDirection.LONG,
            entry_signal="SIG",
        )
        validated = strat.validate_position(pos)
        assert validated.weight == 0.5
        assert validated.confidence == 0.7

    def test_does_not_mutate_original(self) -> None:
        """validate_position should return a new object, not modify the original."""
        config = _make_config()
        strat = DummyStrategy(config=config)
        pos = StrategyPosition(
            strategy_id="S1",
            instrument="DI_PRE",
            weight=2.0,
            confidence=0.5,
            direction=SignalDirection.LONG,
            entry_signal="SIG",
        )
        validated = strat.validate_position(pos)
        assert pos.weight == 2.0  # original unchanged
        assert validated.weight == 1.0  # new object clamped


# ---------------------------------------------------------------------------
# StrategySignal tests (v3.0 SFWK-01)
# ---------------------------------------------------------------------------
class TestStrategySignal:
    def test_strategy_signal_creation(self) -> None:
        """StrategySignal should accept all required fields with optional defaults."""
        sig = StrategySignal(
            strategy_id="TEST_01",
            timestamp=datetime(2026, 1, 15, 12, 0, 0),
            direction=SignalDirection.LONG,
            strength=SignalStrength.STRONG,
            confidence=0.9,
            z_score=2.5,
            raw_value=100.0,
            suggested_size=0.8,
            asset_class=AssetClass.FX,
            instruments=["USDBRL"],
        )
        assert sig.strategy_id == "TEST_01"
        assert sig.z_score == 2.5
        assert sig.raw_value == 100.0
        assert sig.suggested_size == 0.8
        assert sig.confidence == 0.9
        assert sig.asset_class == AssetClass.FX
        assert sig.instruments == ["USDBRL"]
        # Optional fields default to None
        assert sig.entry_level is None
        assert sig.stop_loss is None
        assert sig.take_profit is None
        assert sig.holding_period_days is None
        assert sig.metadata == {}

    def test_strategy_signal_with_optional_fields(self) -> None:
        """StrategySignal should accept all optional fields."""
        sig = StrategySignal(
            strategy_id="TEST_02",
            timestamp=datetime(2026, 1, 15, 12, 0, 0),
            direction=SignalDirection.SHORT,
            strength=SignalStrength.MODERATE,
            confidence=0.7,
            z_score=-1.5,
            raw_value=50.0,
            suggested_size=0.4,
            asset_class=AssetClass.FIXED_INCOME,
            instruments=["DI_PRE"],
            entry_level=100.5,
            stop_loss=98.0,
            take_profit=105.0,
            holding_period_days=10,
            metadata={"model": "v2"},
        )
        assert sig.entry_level == 100.5
        assert sig.stop_loss == 98.0
        assert sig.take_profit == 105.0
        assert sig.holding_period_days == 10
        assert sig.metadata == {"model": "v2"}


# ---------------------------------------------------------------------------
# BaseStrategy v3.0 utility method tests
# ---------------------------------------------------------------------------
class TestComputeZScore:
    """Tests for BaseStrategy.compute_z_score()."""

    def _make_strat(self) -> DummyStrategy:
        return DummyStrategy(config=_make_config())

    def test_compute_z_score_normal(self) -> None:
        """z-score with varying history should return correct value."""
        strat = self._make_strat()
        history = [100, 102, 98, 101, 99]
        z = strat.compute_z_score(110, history, window=5)
        assert z > 0, f"Expected positive z-score, got {z}"

    def test_compute_z_score_zero_std(self) -> None:
        """Constant history (zero std) should return 0.0."""
        strat = self._make_strat()
        z = strat.compute_z_score(105, [100, 100, 100, 100, 100], window=5)
        assert z == 0.0

    def test_compute_z_score_empty_history(self) -> None:
        """Empty history should return 0.0."""
        strat = self._make_strat()
        assert strat.compute_z_score(100, []) == 0.0

    def test_compute_z_score_single_value(self) -> None:
        """Single-element history should return 0.0."""
        strat = self._make_strat()
        assert strat.compute_z_score(100, [100]) == 0.0


class TestSizeFromConviction:
    """Tests for BaseStrategy.size_from_conviction()."""

    def _make_strat(self) -> DummyStrategy:
        return DummyStrategy(config=_make_config())

    def test_size_from_conviction_zero(self) -> None:
        """z=0 should return 0.0."""
        strat = self._make_strat()
        assert strat.size_from_conviction(0.0) == 0.0

    def test_size_from_conviction_large(self) -> None:
        """Large z should approach max_size."""
        strat = self._make_strat()
        size = strat.size_from_conviction(5.0, max_size=1.0)
        assert size > 0.9, f"Expected > 0.9, got {size}"

    def test_size_from_conviction_moderate(self) -> None:
        """z=1.0 should be between 0.3 and 0.8."""
        strat = self._make_strat()
        size = strat.size_from_conviction(1.0, max_size=1.0)
        assert 0.3 < size < 0.8, f"Expected between 0.3 and 0.8, got {size}"


class TestClassifyStrength:
    """Tests for BaseStrategy.classify_strength()."""

    def _make_strat(self) -> DummyStrategy:
        return DummyStrategy(config=_make_config())

    def test_classify_strength_strong(self) -> None:
        """z=2.5 should classify as STRONG."""
        strat = self._make_strat()
        assert strat.classify_strength(2.5) == SignalStrength.STRONG

    def test_classify_strength_moderate(self) -> None:
        """z=1.5 should classify as MODERATE."""
        strat = self._make_strat()
        assert strat.classify_strength(1.5) == SignalStrength.MODERATE

    def test_classify_strength_weak(self) -> None:
        """z=0.7 should classify as WEAK."""
        strat = self._make_strat()
        assert strat.classify_strength(0.7) == SignalStrength.WEAK

    def test_classify_strength_no_signal(self) -> None:
        """z=0.3 should classify as NO_SIGNAL."""
        strat = self._make_strat()
        assert strat.classify_strength(0.3) == SignalStrength.NO_SIGNAL

    def test_classify_strength_negative(self) -> None:
        """z=-2.5 should classify as STRONG (uses abs)."""
        strat = self._make_strat()
        assert strat.classify_strength(-2.5) == SignalStrength.STRONG
