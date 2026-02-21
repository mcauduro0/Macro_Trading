"""Tests for BaseAgent ABC, AgentSignal, AgentReport, and classify_strength."""

from datetime import date, datetime

import pytest

from src.agents.base import (
    AgentReport,
    AgentSignal,
    BaseAgent,
    classify_strength,
)
from src.core.enums import SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# classify_strength
# ---------------------------------------------------------------------------
class TestClassifyStrength:
    def test_strong(self) -> None:
        assert classify_strength(0.75) == SignalStrength.STRONG
        assert classify_strength(0.99) == SignalStrength.STRONG
        assert classify_strength(1.0) == SignalStrength.STRONG

    def test_moderate(self) -> None:
        assert classify_strength(0.50) == SignalStrength.MODERATE
        assert classify_strength(0.60) == SignalStrength.MODERATE
        assert classify_strength(0.74) == SignalStrength.MODERATE

    def test_weak(self) -> None:
        assert classify_strength(0.25) == SignalStrength.WEAK
        assert classify_strength(0.35) == SignalStrength.WEAK
        assert classify_strength(0.49) == SignalStrength.WEAK

    def test_no_signal(self) -> None:
        assert classify_strength(0.0) == SignalStrength.NO_SIGNAL
        assert classify_strength(0.10) == SignalStrength.NO_SIGNAL
        assert classify_strength(0.24) == SignalStrength.NO_SIGNAL


# ---------------------------------------------------------------------------
# AgentSignal dataclass
# ---------------------------------------------------------------------------
class TestAgentSignal:
    def test_creation(self) -> None:
        sig = AgentSignal(
            signal_id="INFLATION_BR_PHILLIPS",
            agent_id="inflation_agent",
            timestamp=datetime(2024, 6, 15, 12, 0, 0),
            as_of_date=date(2024, 6, 15),
            direction=SignalDirection.LONG,
            strength=SignalStrength.MODERATE,
            confidence=0.65,
            value=1.2,
            horizon_days=63,
            metadata={"model": "phillips_curve"},
        )
        assert sig.signal_id == "INFLATION_BR_PHILLIPS"
        assert sig.agent_id == "inflation_agent"
        assert sig.direction == SignalDirection.LONG
        assert sig.strength == SignalStrength.MODERATE
        assert sig.confidence == 0.65
        assert sig.value == 1.2
        assert sig.horizon_days == 63
        assert sig.metadata == {"model": "phillips_curve"}
        assert isinstance(sig.timestamp, datetime)
        assert isinstance(sig.as_of_date, date)

    def test_default_metadata(self) -> None:
        sig = AgentSignal(
            signal_id="TEST",
            agent_id="test",
            timestamp=datetime.utcnow(),
            as_of_date=date.today(),
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.NO_SIGNAL,
            confidence=0.0,
            value=0.0,
            horizon_days=21,
        )
        assert sig.metadata == {}


# ---------------------------------------------------------------------------
# AgentReport dataclass
# ---------------------------------------------------------------------------
class TestAgentReport:
    def test_creation(self) -> None:
        signals = [
            AgentSignal(
                signal_id=f"SIG_{i}",
                agent_id="test_agent",
                timestamp=datetime.utcnow(),
                as_of_date=date(2024, 6, 15),
                direction=SignalDirection.LONG,
                strength=SignalStrength.WEAK,
                confidence=0.3,
                value=float(i),
                horizon_days=21,
            )
            for i in range(3)
        ]
        report = AgentReport(
            agent_id="test_agent",
            as_of_date=date(2024, 6, 15),
            generated_at=datetime.utcnow(),
            signals=signals,
            narrative="Test narrative paragraph.",
        )
        assert report.agent_id == "test_agent"
        assert len(report.signals) == 3
        assert report.narrative == "Test narrative paragraph."
        assert report.model_diagnostics == {}
        assert report.data_quality_flags == []


# ---------------------------------------------------------------------------
# BaseAgent ABC enforcement
# ---------------------------------------------------------------------------
class TestBaseAgentABC:
    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            BaseAgent("test", "Test Agent")  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# DummyAgent -- concrete implementation for testing
# ---------------------------------------------------------------------------
class DummyAgent(BaseAgent):
    """Minimal concrete agent for unit tests."""

    def load_data(self, as_of_date):
        return {"series_a": None}

    def compute_features(self, data):
        return {"feature_1": 1.0}

    def run_models(self, features):
        return [
            AgentSignal(
                signal_id="TEST_SIG",
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                as_of_date=date(2024, 6, 15),
                direction=SignalDirection.LONG,
                strength=SignalStrength.MODERATE,
                confidence=0.6,
                value=1.2,
                horizon_days=63,
            )
        ]

    def generate_narrative(self, signals, features):
        return "Test narrative"

    def _persist_signals(self, signals):
        """No-op for unit tests -- avoid DB calls."""
        return 0

    def _persist_report(self, report):
        """No-op for unit tests -- avoid DB calls."""
        pass


class TestConcreteAgent:
    def test_backtest_run(self) -> None:
        agent = DummyAgent("dummy", "Dummy Agent")
        report = agent.backtest_run(date(2024, 6, 15))

        assert report.agent_id == "dummy"
        assert len(report.signals) == 1
        assert report.narrative == "Test narrative"
        assert report.signals[0].direction == SignalDirection.LONG
        assert report.signals[0].confidence == 0.6
        assert report.as_of_date == date(2024, 6, 15)
        assert isinstance(report.generated_at, datetime)

    def test_run_returns_report(self) -> None:
        agent = DummyAgent("dummy", "Dummy Agent")
        report = agent.run(date(2024, 6, 15))

        assert report.agent_id == "dummy"
        assert len(report.signals) == 1
        assert report.narrative == "Test narrative"

    def test_check_data_quality_flags_none(self) -> None:
        agent = DummyAgent("dummy", "Dummy Agent")
        flags = agent._check_data_quality({"key": None})
        assert flags == ["key: data is None"]

    def test_check_data_quality_no_issues(self) -> None:
        import pandas as pd

        agent = DummyAgent("dummy", "Dummy Agent")
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        flags = agent._check_data_quality({"data": df})
        assert flags == []

    def test_check_data_quality_nested_dict(self) -> None:
        agent = DummyAgent("dummy", "Dummy Agent")
        flags = agent._check_data_quality({"parent": {"child": None}})
        assert flags == ["parent.child: data is None"]


# ---------------------------------------------------------------------------
# Enum serialization
# ---------------------------------------------------------------------------
class TestEnumSerialization:
    def test_signal_direction_value(self) -> None:
        assert SignalDirection.LONG.value == "LONG"
        assert SignalDirection.SHORT.value == "SHORT"
        assert SignalDirection.NEUTRAL.value == "NEUTRAL"

    def test_signal_strength_value(self) -> None:
        assert SignalStrength.STRONG.value == "STRONG"
        assert SignalStrength.MODERATE.value == "MODERATE"
        assert SignalStrength.WEAK.value == "WEAK"
        assert SignalStrength.NO_SIGNAL.value == "NO_SIGNAL"

    def test_signal_direction_str(self) -> None:
        # str(Enum) mixin returns just the value for (str, Enum)
        assert str(SignalDirection.LONG) == "SignalDirection.LONG"
