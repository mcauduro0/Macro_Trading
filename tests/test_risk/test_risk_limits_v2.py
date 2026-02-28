"""Tests for RiskLimitsManager v2 -- daily/weekly loss tracking and risk budget.

Covers:
- Daily loss breach detection (exceeding 2% limit)
- Weekly cumulative loss breach (5-day rolling, exceeding 5%)
- Daily loss within limit (no breach)
- Risk budget computation from position contributions
- Per-position budget breach detection
- Loss history FIFO (maxlen=30)
- check_all_v2 combined output
- available_risk_budget accessor
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.risk.risk_limits_v2 import (
    LossRecord,
    RiskBudgetReport,
    RiskLimitsManager,
    RiskLimitsManagerConfig,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager(
    daily_limit: float = 0.02,
    weekly_limit: float = 0.05,
    budget_per_pos: float = 0.20,
    budget_per_ac: float = 0.40,
    total_budget: float = 1.0,
) -> RiskLimitsManager:
    """Create a manager with custom limits."""
    config = RiskLimitsManagerConfig(
        daily_loss_limit_pct=daily_limit,
        weekly_loss_limit_pct=weekly_limit,
        risk_budget_per_position=budget_per_pos,
        risk_budget_per_asset_class=budget_per_ac,
        total_risk_budget=total_budget,
    )
    return RiskLimitsManager(config=config)


# ---------------------------------------------------------------------------
# Daily loss tracking
# ---------------------------------------------------------------------------


class TestDailyLossTracking:
    """Test daily P&L recording and breach detection."""

    def test_daily_loss_breaches_limit(self):
        """A -3% daily loss breaches the 2% daily limit."""
        mgr = _make_manager(daily_limit=0.02)
        record = mgr.record_daily_pnl(date(2026, 1, 15), -0.03)

        assert isinstance(record, LossRecord)
        assert record.daily_pnl == -0.03
        assert record.breach_daily is True

    def test_daily_loss_within_limit(self):
        """-1% daily loss does not breach the 2% limit."""
        mgr = _make_manager(daily_limit=0.02)
        record = mgr.record_daily_pnl(date(2026, 1, 15), -0.01)

        assert record.breach_daily is False

    def test_positive_pnl_no_breach(self):
        """A positive day (gain) should never breach."""
        mgr = _make_manager()
        record = mgr.record_daily_pnl(date(2026, 1, 15), 0.015)

        assert record.breach_daily is False
        assert record.breach_weekly is False

    def test_strategies_pnl_stored(self):
        """Per-strategy P&L is preserved in the record."""
        mgr = _make_manager()
        strats = {"FX_BR_01": -0.005, "RATES_BR_01": 0.002}
        record = mgr.record_daily_pnl(date(2026, 1, 15), -0.003, strats)

        assert record.strategies_pnl == strats


# ---------------------------------------------------------------------------
# Weekly cumulative loss tracking
# ---------------------------------------------------------------------------


class TestWeeklyLossTracking:
    """Test 5-business-day rolling weekly cumulative loss."""

    def test_weekly_cumulative_breach(self):
        """5 days of -1.2% each = -6% weekly, breaches the 5% limit."""
        mgr = _make_manager(weekly_limit=0.05)
        base = date(2026, 1, 13)

        for i in range(5):
            record = mgr.record_daily_pnl(base + timedelta(days=i), -0.012)

        # Last record should have cumulative = -0.06, breach weekly
        assert record.cumulative_weekly_pnl == pytest.approx(-0.06, abs=1e-10)
        assert record.breach_weekly is True

    def test_weekly_within_limit(self):
        """5 days of -0.008 each = -0.04 (4%), does not breach 5% limit."""
        mgr = _make_manager(weekly_limit=0.05)
        base = date(2026, 1, 13)

        for i in range(5):
            record = mgr.record_daily_pnl(base + timedelta(days=i), -0.008)

        assert record.cumulative_weekly_pnl == pytest.approx(-0.04, abs=1e-10)
        assert record.breach_weekly is False

    def test_weekly_rolling_window(self):
        """After 7 days, only the last 5 count for weekly cumulative."""
        mgr = _make_manager(weekly_limit=0.05)
        base = date(2026, 1, 13)

        # First 2 days: large losses
        for i in range(2):
            mgr.record_daily_pnl(base + timedelta(days=i), -0.02)

        # Next 5 days: small losses -- the early large ones roll out
        for i in range(2, 7):
            record = mgr.record_daily_pnl(base + timedelta(days=i), -0.005)

        # Weekly should be 5 * -0.005 = -0.025 (only last 5 days)
        assert record.cumulative_weekly_pnl == pytest.approx(-0.025, abs=1e-10)
        assert record.breach_weekly is False


# ---------------------------------------------------------------------------
# Risk budget
# ---------------------------------------------------------------------------


class TestRiskBudget:
    """Test risk budget computation and reporting."""

    def test_basic_budget_computation(self):
        """3 positions summing to 0.6 leaves 0.4 available."""
        mgr = _make_manager(total_budget=1.0)

        contributions = {"USDBRL": 0.20, "DI_PRE": 0.25, "IBOV": 0.15}
        ac_map = {"USDBRL": "FX", "DI_PRE": "RATES", "IBOV": "EQUITY"}

        report = mgr.compute_risk_budget(contributions, ac_map)

        assert isinstance(report, RiskBudgetReport)
        assert report.allocated_risk == pytest.approx(0.60, abs=1e-10)
        assert report.available_risk_budget == pytest.approx(0.40, abs=1e-10)
        assert report.utilization_pct == pytest.approx(60.0, abs=0.1)
        assert report.can_add_risk is True

    def test_position_budget_breach(self):
        """One position contributing 25% breaches the 20% per-position limit."""
        mgr = _make_manager(budget_per_pos=0.20)

        contributions = {"USDBRL": 0.25, "DI_PRE": 0.10}
        ac_map = {"USDBRL": "FX", "DI_PRE": "RATES"}

        report = mgr.compute_risk_budget(contributions, ac_map)

        assert report.position_budgets["USDBRL"]["breached"] is True
        assert report.position_budgets["DI_PRE"]["breached"] is False

    def test_asset_class_budget_breach(self):
        """Two positions in same asset class summing > 40% breaches AC limit."""
        mgr = _make_manager(budget_per_ac=0.40)

        contributions = {"DI_PRE_360": 0.25, "DI_PRE_720": 0.20}
        ac_map = {"DI_PRE_360": "RATES", "DI_PRE_720": "RATES"}

        report = mgr.compute_risk_budget(contributions, ac_map)

        # RATES total = 0.45, exceeds 0.40 limit
        assert report.asset_class_budgets["RATES"]["breached"] is True
        assert report.asset_class_budgets["RATES"]["allocated"] == pytest.approx(
            0.45, abs=1e-10
        )

    def test_cannot_add_risk_when_full(self):
        """When available budget < 5%, can_add_risk is False."""
        mgr = _make_manager(total_budget=1.0)

        contributions = {"A": 0.32, "B": 0.33, "C": 0.32}
        ac_map = {"A": "FX", "B": "RATES", "C": "EQUITY"}

        report = mgr.compute_risk_budget(contributions, ac_map)

        # Allocated 0.97, available 0.03 < 0.05
        assert report.can_add_risk is False


# ---------------------------------------------------------------------------
# Loss history FIFO
# ---------------------------------------------------------------------------


class TestLossHistoryFIFO:
    """Test the max-30 deque behavior for loss records."""

    def test_fifo_max_30(self):
        """Adding 35 records keeps only the last 30."""
        mgr = _make_manager()
        base = date(2026, 1, 1)

        for i in range(35):
            mgr.record_daily_pnl(base + timedelta(days=i), -0.001)

        history = mgr.get_loss_history(n_days=100)
        assert len(history) == 30

        # First remaining record should be day 5 (0-indexed)
        assert history[0].date == base + timedelta(days=5)

    def test_get_history_fewer_records(self):
        """Requesting more days than available returns all records."""
        mgr = _make_manager()
        mgr.record_daily_pnl(date(2026, 1, 1), -0.001)
        mgr.record_daily_pnl(date(2026, 1, 2), -0.002)

        history = mgr.get_loss_history(n_days=10)
        assert len(history) == 2


# ---------------------------------------------------------------------------
# check_all_v2
# ---------------------------------------------------------------------------


class TestCheckAllV2:
    """Test the combined limit + loss + budget check."""

    def test_returns_combined_status(self):
        """check_all_v2 returns all 4 expected keys."""
        mgr = _make_manager()

        state = {
            "weights": {"A": 0.10},
            "leverage": 0.10,
            "var_95": -0.01,
            "var_99": -0.02,
            "drawdown_pct": 0.005,
        }

        result = mgr.check_all_v2(state)

        assert "limit_results" in result
        assert "loss_status" in result
        assert "risk_budget" in result
        assert "overall_status" in result

    def test_breached_status_from_loss(self):
        """check_all_v2 shows BREACHED when daily loss exceeds limit."""
        mgr = _make_manager(daily_limit=0.02)
        mgr.record_daily_pnl(date(2026, 1, 15), -0.03)

        state = {
            "weights": {"A": 0.10},
            "leverage": 0.10,
        }

        result = mgr.check_all_v2(state)
        assert result["overall_status"] == "BREACHED"
        assert result["loss_status"] is not None
        assert result["loss_status"].breach_daily is True

    def test_ok_status_when_clean(self):
        """check_all_v2 shows OK when no breaches."""
        mgr = _make_manager()

        state = {
            "weights": {"A": 0.10},
            "leverage": 0.10,
        }

        result = mgr.check_all_v2(state)
        assert result["overall_status"] == "OK"

    def test_budget_included_when_contributions_provided(self):
        """check_all_v2 includes risk budget when contributions + map provided."""
        mgr = _make_manager()

        state = {
            "weights": {"A": 0.10},
            "leverage": 0.10,
            "risk_contributions": {"A": 0.15, "B": 0.10},
            "asset_class_map": {"A": "FX", "B": "RATES"},
        }

        result = mgr.check_all_v2(state)
        assert result["risk_budget"] is not None
        assert result["risk_budget"].allocated_risk == pytest.approx(0.25, abs=1e-10)


# ---------------------------------------------------------------------------
# available_risk_budget accessor
# ---------------------------------------------------------------------------


class TestAvailableRiskBudget:
    """Test the quick available risk budget accessor."""

    def test_initial_budget_is_full(self):
        """Before any computation, full budget is available."""
        mgr = _make_manager(total_budget=1.0)
        assert mgr.available_risk_budget() == 1.0

    def test_after_budget_computation(self):
        """After compute_risk_budget, available reflects allocated."""
        mgr = _make_manager(total_budget=1.0)

        contributions = {"A": 0.30, "B": 0.25}
        ac_map = {"A": "FX", "B": "RATES"}
        mgr.compute_risk_budget(contributions, ac_map)

        assert mgr.available_risk_budget() == pytest.approx(0.45, abs=1e-10)
