"""Unit tests for RiskMonitor -- TESTV2-04 integration tests.

Tests aggregate risk report generation, risk level classification,
text formatting, and default component creation.
"""

from __future__ import annotations

import numpy as np

from src.risk.drawdown_manager import CircuitBreakerState
from src.risk.risk_monitor import RiskMonitor, RiskReport


def _synthetic_returns(n: int = 500, seed: int = 42) -> np.ndarray:
    """Generate synthetic daily returns for testing."""
    rng = np.random.default_rng(seed)
    return rng.normal(0.0002, 0.01, size=n)


def _sample_positions() -> dict[str, float]:
    """Return sample positions."""
    return {
        "DI_PRE_365": 200_000.0,
        "USDBRL": -100_000.0,
        "IBOVESPA": 150_000.0,
    }


def _sample_weights() -> dict[str, float]:
    """Return sample weights."""
    return {
        "DI_PRE_365": 0.20,
        "USDBRL": -0.10,
        "IBOVESPA": 0.15,
    }


class TestRiskMonitor:
    """Tests for RiskMonitor."""

    def test_generate_report_basic(self) -> None:
        """Report should contain all required fields."""
        monitor = RiskMonitor()
        returns = _synthetic_returns()
        report = monitor.generate_report(
            portfolio_returns=returns,
            positions=_sample_positions(),
            portfolio_value=1_000_000.0,
            weights=_sample_weights(),
            current_equity=1_000_000.0,
        )
        assert isinstance(report, RiskReport)
        assert report.portfolio_value == 1_000_000.0
        assert isinstance(report.var_results, dict)
        assert isinstance(report.stress_results, list)
        assert isinstance(report.limit_results, list)
        assert isinstance(report.limit_utilization, dict)
        assert isinstance(report.circuit_breaker_state, CircuitBreakerState)
        assert isinstance(report.drawdown_pct, float)
        assert isinstance(report.overall_risk_level, str)

    def test_report_has_var_results(self) -> None:
        """Report should contain historical and parametric VaR result keys.

        With only 500 observations (< default min_historical_obs=756),
        the historical method falls back to parametric internally.
        """
        monitor = RiskMonitor()
        returns = _synthetic_returns()
        report = monitor.generate_report(
            portfolio_returns=returns,
            positions=_sample_positions(),
            portfolio_value=1_000_000.0,
            weights=_sample_weights(),
        )
        assert "historical" in report.var_results
        assert "parametric" in report.var_results
        # With 500 obs < 756 min, historical falls back to parametric
        assert report.var_results["historical"].method == "parametric"
        assert report.var_results["parametric"].method == "parametric"

    def test_report_has_stress_results(self) -> None:
        """Report should have 6 scenario results (from default scenarios)."""
        monitor = RiskMonitor()
        returns = _synthetic_returns()
        report = monitor.generate_report(
            portfolio_returns=returns,
            positions=_sample_positions(),
            portfolio_value=1_000_000.0,
            weights=_sample_weights(),
        )
        assert len(report.stress_results) == 6
        scenario_names = {s.scenario_name for s in report.stress_results}
        assert "Taper Tantrum 2013" in scenario_names
        assert "BR Crisis 2015" in scenario_names
        assert "COVID 2020" in scenario_names
        assert "Rate Shock 2022" in scenario_names
        assert "BR Fiscal Crisis (Teto de Gastos)" in scenario_names
        assert "Global Risk-Off (Geopolitical)" in scenario_names

    def test_report_has_limit_results(self) -> None:
        """Report should have non-empty limit results."""
        monitor = RiskMonitor()
        returns = _synthetic_returns()
        report = monitor.generate_report(
            portfolio_returns=returns,
            positions=_sample_positions(),
            portfolio_value=1_000_000.0,
            weights=_sample_weights(),
        )
        assert len(report.limit_results) > 0
        assert all(hasattr(r, "breached") for r in report.limit_results)

    def test_report_risk_level_low(self) -> None:
        """Healthy portfolio should have LOW risk level."""
        monitor = RiskMonitor()
        returns = _synthetic_returns()
        report = monitor.generate_report(
            portfolio_returns=returns,
            positions=_sample_positions(),
            portfolio_value=1_000_000.0,
            weights=_sample_weights(),
            current_equity=1_000_000.0,
        )
        # Fresh portfolio with no drawdown and small VaR should be LOW
        assert report.overall_risk_level == "LOW"

    def test_report_risk_level_critical(self) -> None:
        """Breached limit should produce CRITICAL risk level."""
        from src.risk.risk_limits import RiskLimitChecker, RiskLimitsConfig

        # Use impossibly tight limits that will be breached
        tight = RiskLimitsConfig(
            max_var_95_pct=0.0001,
            max_var_99_pct=0.0001,
            max_leverage=0.01,
        )
        checker = RiskLimitChecker(config=tight)
        monitor = RiskMonitor(limit_checker=checker)
        returns = _synthetic_returns()
        report = monitor.generate_report(
            portfolio_returns=returns,
            positions=_sample_positions(),
            portfolio_value=1_000_000.0,
            weights=_sample_weights(),
        )
        assert report.overall_risk_level == "CRITICAL"

    def test_format_report_text(self) -> None:
        """Formatted report should contain key sections."""
        monitor = RiskMonitor()
        returns = _synthetic_returns()
        report = monitor.generate_report(
            portfolio_returns=returns,
            positions=_sample_positions(),
            portfolio_value=1_000_000.0,
            weights=_sample_weights(),
            current_equity=1_000_000.0,
        )
        text = monitor.format_report(report)
        assert isinstance(text, str)
        assert len(text) > 0
        assert "VaR" in text
        assert "Stress" in text
        assert "Limit" in text
        assert "Circuit Breaker" in text

    def test_default_components(self) -> None:
        """RiskMonitor with no args should create all default components."""
        monitor = RiskMonitor()
        assert monitor.var_calculator is not None
        assert monitor.stress_tester is not None
        assert monitor.limit_checker is not None
        assert monitor.drawdown_manager is not None
