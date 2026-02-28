"""Unit tests for the daily pipeline orchestration.

All external dependencies (DB, agents, strategies, risk) are mocked so that
tests run without a database or live services.
"""

import uuid
from datetime import date
from unittest.mock import patch

import pytest

from src.pipeline.daily_pipeline import DailyPipeline, PipelineResult


# ---------------------------------------------------------------------------
# Test PipelineResult dataclass
# ---------------------------------------------------------------------------
class TestPipelineResult:
    """Verify PipelineResult fields and defaults."""

    def test_defaults(self):
        r = PipelineResult()
        assert r.status == "SUCCESS"
        assert r.duration_seconds == 0.0
        assert r.step_timings == {}
        assert r.signal_count == 0
        assert r.position_count == 0
        assert r.regime == "NEUTRAL"
        assert r.leverage == 0.0
        assert r.var_95 == 0.0
        assert r.risk_alerts == []

    def test_run_id_is_uuid(self):
        r = PipelineResult()
        # Should not raise
        uuid.UUID(r.run_id)

    def test_custom_values(self):
        r = PipelineResult(
            date=date(2024, 1, 15),
            status="FAILED",
            signal_count=23,
            position_count=12,
            regime="RISK_OFF",
            leverage=1.8,
            var_95=-2.1,
            risk_alerts=["limit breach"],
        )
        assert r.date == date(2024, 1, 15)
        assert r.status == "FAILED"
        assert r.signal_count == 23
        assert r.position_count == 12
        assert r.regime == "RISK_OFF"
        assert r.leverage == 1.8
        assert r.var_95 == -2.1
        assert r.risk_alerts == ["limit breach"]


# ---------------------------------------------------------------------------
# Test step timing wrapper
# ---------------------------------------------------------------------------
class TestStepTimingWrapper:
    """Verify _run_step records duration and prints formatted output."""

    def test_successful_step_records_timing(self, capsys):
        pipeline = DailyPipeline(as_of_date=date(2024, 1, 15), dry_run=True)

        def dummy_step():
            pass

        pipeline._run_step("test_step", dummy_step)
        assert "test_step" in pipeline._result.step_timings
        assert pipeline._result.step_timings["test_step"] >= 0.0

        captured = capsys.readouterr()
        assert "\u2713" in captured.out  # checkmark
        assert "test_step" in captured.out

    def test_failed_step_prints_error_and_raises(self, capsys):
        pipeline = DailyPipeline(as_of_date=date(2024, 1, 15), dry_run=True)

        def failing_step():
            raise ValueError("something broke")

        with pytest.raises(RuntimeError, match="Pipeline aborted at step"):
            pipeline._run_step("bad_step", failing_step)

        captured = capsys.readouterr()
        assert "\u2717" in captured.out  # X mark
        assert "FAILED" in captured.out
        assert "something broke" in captured.out


# ---------------------------------------------------------------------------
# Test dry-run skips persistence
# ---------------------------------------------------------------------------
class TestDryRunSkipsPersistence:
    """With dry_run=True, DB write is not called."""

    @patch("src.pipeline.daily_pipeline.DailyPipeline._persist_run")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_risk")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_portfolio")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_strategies")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_aggregate")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_agents")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_quality")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_ingest")
    def test_dry_run_does_not_persist(
        self,
        mock_ingest,
        mock_quality,
        mock_agents,
        mock_aggregate,
        mock_strategies,
        mock_portfolio,
        mock_risk,
        mock_persist,
    ):
        pipeline = DailyPipeline(as_of_date=date(2024, 1, 15), dry_run=True)
        pipeline.run()
        mock_persist.assert_not_called()

    @patch("src.pipeline.daily_pipeline.DailyPipeline._persist_run")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_risk")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_portfolio")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_strategies")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_aggregate")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_agents")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_quality")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_ingest")
    def test_non_dry_run_calls_persist(
        self,
        mock_ingest,
        mock_quality,
        mock_agents,
        mock_aggregate,
        mock_strategies,
        mock_portfolio,
        mock_risk,
        mock_persist,
    ):
        pipeline = DailyPipeline(as_of_date=date(2024, 1, 15), dry_run=False)
        pipeline.run()
        mock_persist.assert_called_once()


# ---------------------------------------------------------------------------
# Test pipeline aborts on failure
# ---------------------------------------------------------------------------
class TestPipelineAbortsOnFailure:
    """If a step raises, pipeline aborts immediately with FAILED status."""

    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_quality")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_ingest")
    def test_abort_on_step_failure(self, mock_ingest, mock_quality):
        mock_quality.side_effect = RuntimeError("quality check exploded")

        pipeline = DailyPipeline(as_of_date=date(2024, 1, 15), dry_run=True)

        with pytest.raises(RuntimeError, match="Pipeline aborted"):
            pipeline.run()

        assert pipeline._result.status == "FAILED"


# ---------------------------------------------------------------------------
# Test format summary output
# ---------------------------------------------------------------------------
class TestFormatSummaryOutput:
    """Summary string contains expected fields."""

    def test_summary_contains_key_fields(self):
        pipeline = DailyPipeline(as_of_date=date(2024, 1, 15), dry_run=True)
        pipeline._result.signal_count = 23
        pipeline._result.position_count = 12
        pipeline._result.leverage = 1.8
        pipeline._result.var_95 = -2.1
        pipeline._result.regime = "NEUTRAL"
        pipeline._result.risk_alerts = []

        summary = pipeline._format_summary()

        assert "Signals: 23" in summary
        assert "Positions: 12" in summary
        assert "Leverage: 1.8x" in summary
        assert "VaR (95%): -2.1%" in summary
        assert "Regime: NEUTRAL" in summary
        assert "Risk Alerts: None" in summary

    def test_summary_shows_risk_alerts_when_present(self):
        pipeline = DailyPipeline(as_of_date=date(2024, 1, 15), dry_run=True)
        pipeline._result.risk_alerts = ["Risk level: HIGH", "Limit breached: leverage"]

        summary = pipeline._format_summary()

        assert "Risk level: HIGH" in summary
        assert "Limit breached: leverage" in summary

    def test_summary_shows_status(self):
        pipeline = DailyPipeline(as_of_date=date(2024, 1, 15), dry_run=True)
        pipeline._result.status = "SUCCESS"
        pipeline._result.duration_seconds = 21.5

        summary = pipeline._format_summary()

        assert "Status: SUCCESS" in summary
        assert "Total: 21.5s" in summary


# ---------------------------------------------------------------------------
# Test CLI argparse
# ---------------------------------------------------------------------------
class TestCLIArgparse:
    """Verify argparse defaults and custom values."""

    def test_defaults(self):
        from scripts.daily_run import parse_args

        args = parse_args([])
        assert args.date == date.today()
        assert args.dry_run is False

    def test_custom_date_and_dry_run(self):
        from scripts.daily_run import parse_args

        args = parse_args(["--date", "2024-01-15", "--dry-run"])
        assert args.date == date(2024, 1, 15)
        assert args.dry_run is True

    def test_date_only(self):
        from scripts.daily_run import parse_args

        args = parse_args(["--date", "2023-06-30"])
        assert args.date == date(2023, 6, 30)
        assert args.dry_run is False

    def test_dry_run_only(self):
        from scripts.daily_run import parse_args

        args = parse_args(["--dry-run"])
        assert args.date == date.today()
        assert args.dry_run is True


# ---------------------------------------------------------------------------
# Test full pipeline run with all mocks
# ---------------------------------------------------------------------------
class TestFullPipelineRun:
    """End-to-end pipeline run with all external deps mocked."""

    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_risk")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_portfolio")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_strategies")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_aggregate")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_agents")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_quality")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_ingest")
    def test_all_8_steps_execute_in_order(
        self,
        mock_ingest,
        mock_quality,
        mock_agents,
        mock_aggregate,
        mock_strategies,
        mock_portfolio,
        mock_risk,
    ):
        call_order = []
        mock_ingest.side_effect = lambda: call_order.append("ingest")
        mock_quality.side_effect = lambda: call_order.append("quality")
        mock_agents.side_effect = lambda: call_order.append("agents")
        mock_aggregate.side_effect = lambda: call_order.append("aggregate")
        mock_strategies.side_effect = lambda: call_order.append("strategies")
        mock_portfolio.side_effect = lambda: call_order.append("portfolio")
        mock_risk.side_effect = lambda: call_order.append("risk")

        pipeline = DailyPipeline(as_of_date=date(2024, 1, 15), dry_run=True)
        result = pipeline.run()

        assert result.status == "SUCCESS"
        assert result.duration_seconds > 0
        assert call_order == [
            "ingest",
            "quality",
            "agents",
            "aggregate",
            "strategies",
            "portfolio",
            "risk",
        ]
        # report step is not mocked, runs natively (dry_run=True skips persist)
        assert "report" in result.step_timings

    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_risk")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_portfolio")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_strategies")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_aggregate")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_agents")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_quality")
    @patch("src.pipeline.daily_pipeline.DailyPipeline._step_ingest")
    def test_step_timings_recorded_for_all_steps(
        self,
        mock_ingest,
        mock_quality,
        mock_agents,
        mock_aggregate,
        mock_strategies,
        mock_portfolio,
        mock_risk,
    ):
        pipeline = DailyPipeline(as_of_date=date(2024, 1, 15), dry_run=True)
        result = pipeline.run()

        expected_steps = [
            "ingest",
            "quality",
            "agents",
            "aggregate",
            "strategies",
            "portfolio",
            "risk",
            "report",
        ]
        for step_name in expected_steps:
            assert step_name in result.step_timings
            assert result.step_timings[step_name] >= 0.0
