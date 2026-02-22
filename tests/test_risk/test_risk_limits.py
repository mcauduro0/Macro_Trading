"""Unit tests for RiskLimitChecker -- TESTV2-04 coverage.

Tests all 9 configurable limits, pre-trade checking, utilization reporting,
and custom configuration.
"""

from __future__ import annotations

from src.risk.risk_limits import (
    RiskLimitChecker,
    RiskLimitsConfig,
)


def _healthy_portfolio_state() -> dict:
    """Return a well-balanced portfolio state with no breaches."""
    return {
        "weights": {"A": 0.15, "B": 0.10, "C": -0.10, "D": 0.05},
        "leverage": 0.40,
        "var_95": -0.01,
        "var_99": -0.02,
        "drawdown_pct": 0.02,
        "risk_contributions": {"A": 0.05, "B": 0.04, "C": 0.03, "D": 0.02},
        "asset_class_weights": {"FI": 0.25, "EQ": 0.15},
        "strategy_daily_pnl": {"RATES_BR_01": 0.005, "FX_BR_01": -0.005},
        "asset_class_daily_pnl": {"FI": 0.003, "EQ": -0.01},
    }


class TestRiskLimitChecker:
    """Tests for RiskLimitChecker."""

    def test_all_limits_pass(self) -> None:
        """Well-balanced portfolio should have no breaches."""
        checker = RiskLimitChecker()
        state = _healthy_portfolio_state()
        results = checker.check_all(state)
        assert len(results) == 9
        assert all(not r.breached for r in results)

    def test_leverage_breach(self) -> None:
        """Leverage exceeding limit should be detected."""
        checker = RiskLimitChecker()
        state = _healthy_portfolio_state()
        state["leverage"] = 4.0
        results = checker.check_all(state)
        leverage_result = [r for r in results if r.limit_name == "max_leverage"][0]
        assert leverage_result.breached is True
        assert leverage_result.current_value == 4.0

    def test_var_95_breach(self) -> None:
        """VaR 95% exceeding limit should be detected."""
        checker = RiskLimitChecker()
        state = _healthy_portfolio_state()
        state["var_95"] = -0.04  # 4% > limit 3%
        results = checker.check_all(state)
        var_result = [r for r in results if r.limit_name == "max_var_95"][0]
        assert var_result.breached is True
        assert abs(var_result.current_value - 0.04) < 1e-10

    def test_drawdown_breach(self) -> None:
        """Drawdown exceeding limit should be detected."""
        checker = RiskLimitChecker()
        state = _healthy_portfolio_state()
        state["drawdown_pct"] = 0.12  # 12% > limit 10%
        results = checker.check_all(state)
        dd_result = [r for r in results if r.limit_name == "max_drawdown"][0]
        assert dd_result.breached is True

    def test_single_position_breach(self) -> None:
        """Single position exceeding limit should be detected."""
        checker = RiskLimitChecker()
        state = _healthy_portfolio_state()
        state["weights"]["A"] = 0.30  # 30% > limit 25%
        results = checker.check_all(state)
        pos_result = [r for r in results if r.limit_name == "max_single_position"][0]
        assert pos_result.breached is True

    def test_asset_class_concentration_breach(self) -> None:
        """Asset class concentration exceeding limit should be detected."""
        checker = RiskLimitChecker()
        state = _healthy_portfolio_state()
        state["asset_class_weights"] = {"FI": 0.60, "EQ": 0.40}  # 60% > limit 50%
        results = checker.check_all(state)
        ac_result = [
            r for r in results if r.limit_name == "max_asset_class_concentration"
        ][0]
        assert ac_result.breached is True

    def test_strategy_daily_loss_breach(self) -> None:
        """Strategy daily loss exceeding limit should be detected."""
        checker = RiskLimitChecker()
        state = _healthy_portfolio_state()
        state["strategy_daily_pnl"] = {
            "RATES_BR_01": -0.025,  # 2.5% loss > limit 2%
            "FX_BR_01": 0.005,
        }
        results = checker.check_all(state)
        strat_result = [
            r for r in results if r.limit_name == "max_strategy_daily_loss"
        ][0]
        assert strat_result.breached is True

    def test_pre_trade_pass(self) -> None:
        """Pre-trade check should pass when proposed weights are within limits."""
        checker = RiskLimitChecker()
        state = _healthy_portfolio_state()
        proposed = {"E": 0.05}
        all_pass, results = checker.check_pre_trade(state, proposed)
        assert all_pass is True
        assert all(not r.breached for r in results)

    def test_pre_trade_fail(self) -> None:
        """Pre-trade check should fail when proposed weights breach leverage."""
        checker = RiskLimitChecker()
        state = _healthy_portfolio_state()
        state["leverage"] = 2.8
        state["weights"] = {"A": 1.0, "B": 0.9, "C": 0.9}
        proposed = {"D": 0.5}  # total leverage -> 3.3 > 3.0
        all_pass, results = checker.check_pre_trade(state, proposed)
        assert all_pass is False
        leverage_result = [r for r in results if r.limit_name == "max_leverage"][0]
        assert leverage_result.breached is True

    def test_utilization_report(self) -> None:
        """Utilization report should show correct percentages sorted descending."""
        checker = RiskLimitChecker()
        state = _healthy_portfolio_state()
        state["leverage"] = 1.5  # 50% of limit 3.0
        results = checker.check_all(state)
        report = checker.utilization_report(results)
        assert isinstance(report, dict)
        # Verify sorted descending
        values = list(report.values())
        assert values == sorted(values, reverse=True)
        # Check leverage utilization
        assert "max_leverage" in report
        assert abs(report["max_leverage"] - 50.0) < 1e-10

    def test_custom_config(self) -> None:
        """Custom tighter limits should detect more breaches."""
        tight_config = RiskLimitsConfig(
            max_var_95_pct=0.005,  # Very tight: 0.5%
            max_leverage=1.0,
        )
        checker = RiskLimitChecker(config=tight_config)
        state = _healthy_portfolio_state()
        state["var_95"] = -0.01  # 1% > tight limit 0.5%
        state["leverage"] = 1.5  # 1.5 > tight limit 1.0
        results = checker.check_all(state)
        var_result = [r for r in results if r.limit_name == "max_var_95"][0]
        lev_result = [r for r in results if r.limit_name == "max_leverage"][0]
        assert var_result.breached is True
        assert lev_result.breached is True
