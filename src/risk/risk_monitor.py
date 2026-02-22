"""Aggregate risk monitoring and reporting.

RiskMonitor is the single entry point that produces the daily risk report
consumed by the pipeline in Phase 13. It orchestrates VaR computation,
stress testing, limit checking, and circuit breaker status into a
unified RiskReport dataclass.

All functions are pure computation -- no I/O or database access.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import structlog

from src.risk.drawdown_manager import (
    CircuitBreakerEvent,
    CircuitBreakerState,
    DrawdownManager,
)
from src.risk.risk_limits import LimitCheckResult, RiskLimitChecker
from src.risk.stress_tester import StressResult, StressTester
from src.risk.var_calculator import VaRCalculator, VaRResult

logger = structlog.get_logger(__name__)


@dataclass
class RiskReport:
    """Aggregate risk report combining all risk components.

    Attributes:
        timestamp: When the report was generated.
        portfolio_value: Total portfolio value.
        var_results: VaR/CVaR results keyed by method name.
        stress_results: Stress test results for all scenarios.
        limit_results: Limit check results for all 9 limits.
        limit_utilization: Utilization percentage per limit.
        circuit_breaker_state: Current circuit breaker state.
        circuit_breaker_scale: Current position scale factor.
        drawdown_pct: Current drawdown percentage.
        recent_cb_events: Last 10 circuit breaker events.
        conflict_log: Signal aggregation conflict messages.
        overall_risk_level: LOW, MODERATE, HIGH, or CRITICAL.
    """

    timestamp: datetime
    portfolio_value: float
    var_results: dict[str, VaRResult]
    stress_results: list[StressResult]
    limit_results: list[LimitCheckResult]
    limit_utilization: dict[str, float]
    circuit_breaker_state: CircuitBreakerState
    circuit_breaker_scale: float
    drawdown_pct: float
    recent_cb_events: list[CircuitBreakerEvent]
    conflict_log: list[str]
    overall_risk_level: str


class RiskMonitor:
    """Orchestrates all risk components into a single RiskReport.

    Args:
        var_calculator: VaR computation engine.
        stress_tester: Stress scenario replay engine.
        limit_checker: Risk limit enforcement engine.
        drawdown_manager: Circuit breaker state machine.
    """

    def __init__(
        self,
        var_calculator: VaRCalculator | None = None,
        stress_tester: StressTester | None = None,
        limit_checker: RiskLimitChecker | None = None,
        drawdown_manager: DrawdownManager | None = None,
    ) -> None:
        self.var_calculator = var_calculator or VaRCalculator()
        self.stress_tester = stress_tester or StressTester()
        self.limit_checker = limit_checker or RiskLimitChecker()
        self.drawdown_manager = drawdown_manager or DrawdownManager()

    def generate_report(
        self,
        portfolio_returns: np.ndarray,
        positions: dict[str, float],
        portfolio_value: float,
        weights: dict[str, float],
        current_equity: float | None = None,
        returns_matrix: np.ndarray | None = None,
        portfolio_weights: np.ndarray | None = None,
        conflict_log: list[str] | None = None,
    ) -> RiskReport:
        """Generate a comprehensive risk report.

        Args:
            portfolio_returns: 1-D array of daily portfolio returns.
            positions: Mapping of instrument_id -> notional value.
            portfolio_value: Total portfolio value.
            weights: Position weights as {instrument_id: weight}.
            current_equity: Current equity for circuit breaker update.
            returns_matrix: (n_obs, n_assets) array for Monte Carlo VaR.
            portfolio_weights: (n_assets,) array for Monte Carlo VaR.
            conflict_log: Signal aggregation conflict messages.

        Returns:
            RiskReport with all risk metrics.
        """
        portfolio_returns = np.asarray(portfolio_returns, dtype=np.float64).ravel()
        conflict_log = conflict_log or []

        # Step 1: VaR
        var_results: dict[str, VaRResult] = {}
        var_results["historical"] = self.var_calculator.calculate(
            portfolio_returns, "historical"
        )
        var_results["parametric"] = self.var_calculator.calculate(
            portfolio_returns, "parametric"
        )
        if returns_matrix is not None and portfolio_weights is not None:
            var_results["monte_carlo"] = self.var_calculator.calculate_monte_carlo(
                returns_matrix, portfolio_weights
            )

        # Step 2: Stress tests
        stress_results = self.stress_tester.run_all(positions, portfolio_value)

        # Step 3: Limits
        # Use historical VaR results to populate portfolio_state
        hist_var = var_results.get("historical")
        portfolio_state: dict = {
            "weights": weights,
            "leverage": sum(abs(w) for w in weights.values()),
            "var_95": hist_var.var_95 if hist_var else None,
            "var_99": hist_var.var_99 if hist_var else None,
            "drawdown_pct": self.drawdown_manager.current_drawdown(),
            "risk_contributions": None,
            "asset_class_weights": None,
            "strategy_daily_pnl": None,
            "asset_class_daily_pnl": None,
        }
        limit_results = self.limit_checker.check_all(portfolio_state)
        limit_utilization = self.limit_checker.utilization_report(limit_results)

        # Step 4: Circuit breaker
        cb_scale = 1.0
        if current_equity is not None:
            cb_scale = self.drawdown_manager.update(
                current_equity, positions
            )

        cb_state = self.drawdown_manager.state
        drawdown_pct = self.drawdown_manager.current_drawdown()
        recent_events = self.drawdown_manager.get_events()[-10:]

        # Step 5: Overall risk level
        overall_risk_level = self._classify_risk_level(
            limit_results, limit_utilization, drawdown_pct
        )

        logger.info(
            "risk_report_generated",
            portfolio_value=portfolio_value,
            overall_risk_level=overall_risk_level,
            circuit_breaker_state=cb_state.value,
            n_limits_checked=len(limit_results),
            n_stress_scenarios=len(stress_results),
        )

        return RiskReport(
            timestamp=datetime.utcnow(),
            portfolio_value=portfolio_value,
            var_results=var_results,
            stress_results=stress_results,
            limit_results=limit_results,
            limit_utilization=limit_utilization,
            circuit_breaker_state=cb_state,
            circuit_breaker_scale=cb_scale,
            drawdown_pct=drawdown_pct,
            recent_cb_events=recent_events,
            conflict_log=conflict_log,
            overall_risk_level=overall_risk_level,
        )

    def format_report(self, report: RiskReport) -> str:
        """Format a RiskReport as plain text for terminal display.

        Uses ASCII box drawing for compatibility. Sections: Portfolio Summary,
        VaR/CVaR, Stress Test Results, Limit Utilization, Circuit Breaker
        Status, Conflict Log.

        Args:
            report: RiskReport to format.

        Returns:
            Multi-line formatted string.
        """
        lines: list[str] = []
        sep = "=" * 72

        # Header
        lines.append(sep)
        lines.append(
            f"  RISK REPORT  |  {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        lines.append(
            f"  Risk Level: {report.overall_risk_level}  |  "
            f"Portfolio Value: {report.portfolio_value:,.2f}"
        )
        lines.append(sep)

        # VaR / CVaR Section
        lines.append("")
        lines.append("  VaR / CVaR")
        lines.append("  " + "-" * 68)
        lines.append(
            f"  {'Method':<16} {'VaR 95%':>12} {'CVaR 95%':>12} "
            f"{'VaR 99%':>12} {'CVaR 99%':>12}"
        )
        lines.append("  " + "-" * 68)
        for method_name, var_r in report.var_results.items():
            lines.append(
                f"  {method_name:<16} {var_r.var_95:>12.6f} {var_r.cvar_95:>12.6f} "
                f"{var_r.var_99:>12.6f} {var_r.cvar_99:>12.6f}"
            )

        # Stress Test Section
        lines.append("")
        lines.append("  Stress Test Results")
        lines.append("  " + "-" * 68)
        lines.append(
            f"  {'Scenario':<28} {'Portfolio P&L':>14} {'P&L %':>10} "
            f"{'Impacted':>10}"
        )
        lines.append("  " + "-" * 68)
        for sr in report.stress_results:
            lines.append(
                f"  {sr.scenario_name:<28} {sr.portfolio_pnl:>14,.2f} "
                f"{sr.portfolio_pnl_pct:>9.2%} {sr.positions_impacted:>10}"
            )

        # Limit Utilization Section
        lines.append("")
        lines.append("  Limit Utilization")
        lines.append("  " + "-" * 68)
        lines.append(
            f"  {'Limit':<36} {'Utilization':>12} {'Status':>12}"
        )
        lines.append("  " + "-" * 68)
        for lr in report.limit_results:
            status = "BREACHED" if lr.breached else "OK"
            bar_len = min(int(lr.utilization_pct / 5), 20)
            bar = "#" * bar_len + "." * (20 - bar_len)
            lines.append(
                f"  {lr.limit_name:<36} {lr.utilization_pct:>10.1f}%  "
                f"[{bar}] {status}"
            )

        # Circuit Breaker Section
        lines.append("")
        lines.append("  Circuit Breaker Status")
        lines.append("  " + "-" * 68)
        lines.append(
            f"  State: {report.circuit_breaker_state.value}  |  "
            f"Scale: {report.circuit_breaker_scale:.2f}  |  "
            f"Drawdown: {report.drawdown_pct:.4%}"
        )
        if report.recent_cb_events:
            lines.append(f"  Recent events: {len(report.recent_cb_events)}")
            for evt in report.recent_cb_events[-3:]:
                lines.append(
                    f"    {evt.timestamp.strftime('%Y-%m-%d %H:%M')} "
                    f"{evt.state_from.value} -> {evt.state_to.value} "
                    f"({evt.action})"
                )

        # Conflict Log
        if report.conflict_log:
            lines.append("")
            lines.append("  Conflict Log")
            lines.append("  " + "-" * 68)
            for msg in report.conflict_log:
                lines.append(f"  - {msg}")

        lines.append("")
        lines.append(sep)

        return "\n".join(lines)

    @staticmethod
    def _classify_risk_level(
        limit_results: list[LimitCheckResult],
        limit_utilization: dict[str, float],
        drawdown_pct: float,
    ) -> str:
        """Determine overall risk level from limit and drawdown state.

        Classification rules:
        - CRITICAL: any limit breached
        - HIGH: any limit > 80% utilized or drawdown > 2%
        - MODERATE: drawdown > 1%
        - LOW: otherwise

        Args:
            limit_results: Limit check results.
            limit_utilization: Utilization percentages.
            drawdown_pct: Current drawdown (positive = loss).

        Returns:
            One of "LOW", "MODERATE", "HIGH", "CRITICAL".
        """
        # CRITICAL: any limit breached
        if any(r.breached for r in limit_results):
            return "CRITICAL"

        # HIGH: any limit > 80% utilized or drawdown > 2%
        if any(u > 80.0 for u in limit_utilization.values()):
            return "HIGH"
        if drawdown_pct > 0.02:
            return "HIGH"

        # MODERATE: drawdown > 1%
        if drawdown_pct > 0.01:
            return "MODERATE"

        return "LOW"
