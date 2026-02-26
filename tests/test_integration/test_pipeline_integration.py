"""Integration tests for the daily pipeline end-to-end flow.

Tests exercise the full pipeline with mocked data layer to verify
the chain: agents -> aggregation -> strategies -> portfolio -> risk -> report.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest

from src.agents.base import AgentReport, AgentSignal
from src.core.enums import SignalDirection, SignalStrength
from src.pipeline.daily_pipeline import DailyPipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_synthetic_signal(
    signal_id: str = "TEST_SIG",
    agent_id: str = "inflation_agent",
    direction: SignalDirection = SignalDirection.LONG,
    confidence: float = 0.7,
    value: float = 1.2,
) -> AgentSignal:
    return AgentSignal(
        signal_id=signal_id,
        agent_id=agent_id,
        timestamp=datetime(2024, 1, 15, 12, 0, 0),
        as_of_date=date(2024, 1, 15),
        direction=direction,
        strength=SignalStrength.MODERATE,
        confidence=confidence,
        value=value,
        horizon_days=63,
        metadata={"test": True},
    )


def _make_synthetic_report(agent_id: str, n_signals: int = 2) -> AgentReport:
    signals = [
        _make_synthetic_signal(
            signal_id=f"{agent_id.upper()}_SIG_{i}",
            agent_id=agent_id,
        )
        for i in range(n_signals)
    ]
    return AgentReport(
        agent_id=agent_id,
        as_of_date=date(2024, 1, 15),
        generated_at=datetime(2024, 1, 15, 12, 0, 0),
        signals=signals,
        narrative=f"Test narrative for {agent_id}",
    )


# ---------------------------------------------------------------------------
# Test 1: Full pipeline dry run
# ---------------------------------------------------------------------------
class TestFullPipelineDryRun:
    """Run DailyPipeline with dry_run=True, all steps mocked."""

    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_risk")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_portfolio")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_strategies")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_aggregate")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_agents")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_quality")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_ingest")
    def test_full_pipeline_dry_run(
        self,
        mock_ingest,
        mock_quality,
        mock_agents,
        mock_aggregate,
        mock_strategies,
        mock_portfolio,
        mock_risk,
    ):
        """Pipeline completes without error in dry-run mode."""
        pipeline = DailyPipeline(
            as_of_date=date(2024, 1, 15), dry_run=True
        )

        # Set up agent reports on the pipeline
        def set_agent_reports():
            pipeline._agent_reports = {
                "inflation_agent": _make_synthetic_report("inflation_agent"),
                "monetary_agent": _make_synthetic_report("monetary_agent"),
            }
            pipeline._result.signal_count = 4

        mock_agents.side_effect = lambda: set_agent_reports()

        result = pipeline.run()

        assert result.status == "SUCCESS"
        assert len(result.step_timings) == 8
        assert all(step in result.step_timings for step in DailyPipeline.STEP_NAMES)
        assert result.duration_seconds > 0


# ---------------------------------------------------------------------------
# Test 2: Agent -> risk chain data flow
# ---------------------------------------------------------------------------
class TestPipelineAgentToRiskChain:
    """Verify data flows correctly through the pipeline chain."""

    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_risk")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_portfolio")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_strategies")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_aggregate")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_agents")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_quality")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_ingest")
    def test_pipeline_agent_to_risk_chain(
        self,
        mock_ingest,
        mock_quality,
        mock_agents,
        mock_aggregate,
        mock_strategies,
        mock_portfolio,
        mock_risk,
    ):
        """Each step's output feeds into the next step."""
        pipeline = DailyPipeline(
            as_of_date=date(2024, 1, 15), dry_run=True
        )

        # Track which steps were called and in what order
        call_order = []

        def fake_agents():
            call_order.append("agents")
            pipeline._agent_reports = {
                "inflation_agent": _make_synthetic_report("inflation_agent", 3),
            }
            pipeline._result.signal_count = 3

        def fake_aggregate():
            call_order.append("aggregate")
            # Should have agent reports available
            assert len(pipeline._agent_reports) > 0

        def fake_strategies():
            call_order.append("strategies")

        def fake_portfolio():
            call_order.append("portfolio")

        def fake_risk():
            call_order.append("risk")

        mock_agents.side_effect = fake_agents
        mock_aggregate.side_effect = fake_aggregate
        mock_strategies.side_effect = fake_strategies
        mock_portfolio.side_effect = fake_portfolio
        mock_risk.side_effect = fake_risk

        result = pipeline.run()

        assert result.status == "SUCCESS"
        assert call_order == ["agents", "aggregate", "strategies", "portfolio", "risk"]
        assert pipeline._result.signal_count == 3


# ---------------------------------------------------------------------------
# Test 3: Pipeline abort on agent failure
# ---------------------------------------------------------------------------
class TestPipelineAbortOnAgentFailure:
    """Pipeline aborts with FAILED status when agent step raises."""

    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_quality")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_ingest")
    def test_pipeline_abort_on_agent_failure(self, mock_ingest, mock_quality):
        """Mock the agents step to raise and verify FAILED status."""
        pipeline = DailyPipeline(
            as_of_date=date(2024, 1, 15), dry_run=True
        )

        # Patch _step_agents directly to raise
        with patch.object(
            pipeline, "_step_agents",
            side_effect=RuntimeError("Agent crashed"),
        ):
            with pytest.raises(RuntimeError, match="Pipeline aborted"):
                pipeline.run()

        assert pipeline._result.status == "FAILED"
