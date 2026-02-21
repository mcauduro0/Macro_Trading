"""Tests for AgentRegistry ordered execution."""

from datetime import date, datetime
from typing import Any

import pytest

from src.agents.base import AgentReport, AgentSignal, BaseAgent
from src.agents.registry import AgentRegistry
from src.core.enums import SignalDirection, SignalStrength

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
# Module-level list to track execution order across agents
_execution_log: list[str] = []


class _TestAgent(BaseAgent):
    """Minimal agent for registry tests.  No DB side-effects."""

    def load_data(self, as_of_date: date) -> dict[str, Any]:
        return {}

    def compute_features(self, data: dict) -> dict[str, Any]:
        return {}

    def run_models(self, features: dict) -> list[AgentSignal]:
        _execution_log.append(self.agent_id)
        return [
            AgentSignal(
                signal_id=f"SIG_{self.agent_id}",
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                as_of_date=date(2024, 6, 15),
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.1,
                value=0.0,
                horizon_days=21,
            )
        ]

    def generate_narrative(self, signals: list[AgentSignal], features: dict) -> str:
        return f"Narrative from {self.agent_id}"

    def _persist_signals(self, signals):
        return 0

    def _persist_report(self, report):
        pass


class _ErrorAgent(BaseAgent):
    """Agent that raises an exception in run_models."""

    def load_data(self, as_of_date):
        return {}

    def compute_features(self, data):
        return {}

    def run_models(self, features):
        raise RuntimeError(f"Intentional failure from {self.agent_id}")

    def generate_narrative(self, signals, features):
        return ""

    def _persist_signals(self, signals):
        return 0

    def _persist_report(self, report):
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure each test starts with a clean AgentRegistry."""
    AgentRegistry.clear()
    _execution_log.clear()
    yield
    AgentRegistry.clear()
    _execution_log.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestRegisterAndGet:
    def test_register_and_get(self) -> None:
        agent = _TestAgent("alpha_agent", "Alpha Agent")
        AgentRegistry.register(agent)
        retrieved = AgentRegistry.get("alpha_agent")
        assert retrieved is agent

    def test_register_duplicate_raises(self) -> None:
        a1 = _TestAgent("dup_agent", "Dup 1")
        a2 = _TestAgent("dup_agent", "Dup 2")
        AgentRegistry.register(a1)
        with pytest.raises(ValueError, match="already registered"):
            AgentRegistry.register(a2)

    def test_get_nonexistent_raises(self) -> None:
        with pytest.raises(KeyError, match="not registered"):
            AgentRegistry.get("nonexistent")

    def test_unregister(self) -> None:
        agent = _TestAgent("to_remove", "Remove Me")
        AgentRegistry.register(agent)
        assert "to_remove" in AgentRegistry.list_registered()
        AgentRegistry.unregister("to_remove")
        assert "to_remove" not in AgentRegistry.list_registered()

    def test_unregister_nonexistent_raises(self) -> None:
        with pytest.raises(KeyError, match="not registered"):
            AgentRegistry.unregister("ghost")


class TestListRegistered:
    def test_list_is_sorted(self) -> None:
        AgentRegistry.register(_TestAgent("charlie", "C"))
        AgentRegistry.register(_TestAgent("alpha", "A"))
        AgentRegistry.register(_TestAgent("bravo", "B"))
        assert AgentRegistry.list_registered() == ["alpha", "bravo", "charlie"]

    def test_list_empty(self) -> None:
        assert AgentRegistry.list_registered() == []


class TestRunAllOrder:
    def test_execution_order(self) -> None:
        """Agents matching EXECUTION_ORDER should run in that sequence."""
        AgentRegistry.register(_TestAgent("fiscal_agent", "Fiscal"))
        AgentRegistry.register(_TestAgent("inflation_agent", "Inflation"))
        AgentRegistry.register(_TestAgent("monetary_agent", "Monetary"))

        reports = AgentRegistry.run_all_backtest(date(2024, 6, 15))

        # _execution_log was populated by run_models
        assert _execution_log == [
            "inflation_agent",
            "monetary_agent",
            "fiscal_agent",
        ]
        assert len(reports) == 3

    def test_extras_come_after_ordered(self) -> None:
        """Agents not in EXECUTION_ORDER are appended alphabetically."""
        AgentRegistry.register(_TestAgent("inflation_agent", "Inflation"))
        AgentRegistry.register(_TestAgent("zebra_agent", "Zebra"))
        AgentRegistry.register(_TestAgent("alpha_custom", "Alpha Custom"))

        AgentRegistry.run_all_backtest(date(2024, 6, 15))

        # inflation_agent first (in EXECUTION_ORDER), then extras alphabetically
        assert _execution_log == [
            "inflation_agent",
            "alpha_custom",
            "zebra_agent",
        ]


class TestRunAllErrorResilience:
    def test_continues_on_error(self) -> None:
        """A failing agent should not prevent others from running."""
        AgentRegistry.register(_ErrorAgent("inflation_agent", "Bad Inflation"))
        AgentRegistry.register(_TestAgent("monetary_agent", "Monetary"))

        reports = AgentRegistry.run_all_backtest(date(2024, 6, 15))

        # Only monetary_agent should succeed
        assert "monetary_agent" in reports
        assert "inflation_agent" not in reports
        # monetary_agent still ran despite inflation_agent failure
        assert "monetary_agent" in _execution_log

    def test_run_all_live_continues_on_error(self) -> None:
        """Same resilience test for run_all (live mode)."""
        AgentRegistry.register(_ErrorAgent("fiscal_agent", "Bad Fiscal"))
        AgentRegistry.register(_TestAgent("fx_agent", "FX"))

        reports = AgentRegistry.run_all(date(2024, 6, 15))

        assert "fx_agent" in reports
        assert "fiscal_agent" not in reports


class TestClear:
    def test_clear(self) -> None:
        AgentRegistry.register(_TestAgent("a1", "A1"))
        AgentRegistry.register(_TestAgent("a2", "A2"))
        assert len(AgentRegistry.list_registered()) == 2
        AgentRegistry.clear()
        assert AgentRegistry.list_registered() == []


class TestRunAllReports:
    def test_report_structure(self) -> None:
        AgentRegistry.register(_TestAgent("inflation_agent", "Inflation"))
        reports = AgentRegistry.run_all_backtest(date(2024, 6, 15))

        report = reports["inflation_agent"]
        assert isinstance(report, AgentReport)
        assert report.agent_id == "inflation_agent"
        assert report.as_of_date == date(2024, 6, 15)
        assert len(report.signals) == 1
        assert report.narrative == "Narrative from inflation_agent"
        assert isinstance(report.generated_at, datetime)
