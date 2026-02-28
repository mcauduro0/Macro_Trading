"""Real-time risk monitoring service for the PMS Risk Monitor dashboard.

RiskMonitorService bridges the existing v3.0 risk infrastructure
(VaRCalculator, StressTester, RiskLimitsManager) with the PMS position
book to provide daily risk snapshots powering the Risk Monitor frontend.

Key capabilities:
- compute_live_risk(): Complete risk snapshot with VaR, leverage,
  drawdown, concentration, stress tests, limit checks, and 2-tier alerts
- get_risk_trend(): 30-day historical trend for dashboard charts
- generate_alerts(): Two-tier alert generator (WARNING at 80%, BREACH at 100%)

Graceful degradation: Each optional component (VaRCalculator, StressTester,
RiskLimitsManager) can be None -- the service returns valid structure with
empty/default values for unavailable sections.
"""

from __future__ import annotations

from collections import deque
from datetime import date
from typing import Any

import structlog

from .position_manager import PositionManager
from .risk_limits_config import PMSRiskLimits

logger = structlog.get_logger(__name__)

# Optional imports -- these modules may not be available in all environments
try:
    from src.risk.risk_limits_v2 import RiskLimitsManager
except ImportError:  # pragma: no cover
    RiskLimitsManager = None  # type: ignore[assignment,misc]

try:
    from src.risk.var_calculator import VaRCalculator
except ImportError:  # pragma: no cover
    VaRCalculator = None  # type: ignore[assignment,misc]

try:
    from src.risk.stress_tester import StressTester
except ImportError:  # pragma: no cover
    StressTester = None  # type: ignore[assignment,misc]


class RiskMonitorService:
    """Daily risk snapshot service for the PMS Risk Monitor page.

    Computes VaR, leverage, drawdown, concentration, stress tests,
    limit utilization, and two-tier alerts from the current position book.

    Args:
        position_manager: PositionManager providing the position book.
        risk_limits_manager: Optional RiskLimitsManager for v2 limit checks.
        var_calculator: Optional VaRCalculator for parametric/MC VaR.
        stress_tester: Optional StressTester for scenario analysis.
        pms_limits: PMSRiskLimits config. Defaults to PMSRiskLimits().
    """

    def __init__(
        self,
        position_manager: PositionManager | None = None,
        risk_limits_manager: Any | None = None,
        var_calculator: Any | None = None,
        stress_tester: Any | None = None,
        pms_limits: PMSRiskLimits | None = None,
    ) -> None:
        self.position_manager = position_manager
        self.risk_limits_manager = risk_limits_manager
        self.var_calculator = var_calculator
        self.stress_tester = stress_tester
        self.pms_limits = pms_limits or PMSRiskLimits()
        self._risk_snapshots: deque[dict] = deque(maxlen=30)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_live_risk(self, as_of_date: date | None = None) -> dict:
        """Compute a complete daily risk snapshot.

        Returns a structured dict matching the PMS guide Etapa 6
        specification with keys: var, leverage, drawdown, concentration,
        stress_tests, limits_summary, alerts, as_of_date.

        Args:
            as_of_date: Reference date. Defaults to today.

        Returns:
            Complete risk snapshot dict.
        """
        ref_date = as_of_date or date.today()
        limits = self.pms_limits

        # Get position book
        book = self._get_book(ref_date)
        summary = book.get("summary", {})
        positions = book.get("positions", [])
        by_asset_class = book.get("by_asset_class", {})
        aum = summary.get("aum", 0.0) or 1.0  # Avoid division by zero

        # Compute each section
        var_section = self._compute_var_section(aum, limits)
        leverage_section = self._compute_leverage_section(summary, aum, limits)
        drawdown_section = self._compute_drawdown_section(aum, limits)
        concentration_section = self._compute_concentration_section(
            by_asset_class,
            summary,
            positions,
            limits,
        )
        stress_section = self._compute_stress_section(positions, aum)
        limits_section = self._compute_limits_section(
            book,
            var_section,
            leverage_section,
            drawdown_section,
        )

        # Build risk data without alerts (alerts computed from the data)
        risk_data: dict[str, Any] = {
            "as_of_date": ref_date,
            "var": var_section,
            "leverage": leverage_section,
            "drawdown": drawdown_section,
            "concentration": concentration_section,
            "stress_tests": stress_section,
            "limits_summary": limits_section,
            "alerts": [],
        }

        # Generate alerts from the risk data
        alerts = self.generate_alerts(risk_data)
        risk_data["alerts"] = alerts

        # Persist snapshot summary for trend history
        self._persist_snapshot(ref_date, risk_data)

        logger.info(
            "live_risk_computed",
            as_of_date=str(ref_date),
            alert_count=len(alerts),
            overall_status=limits_section.get("overall_status", "OK"),
        )

        return risk_data

    def get_risk_trend(self, days: int = 30) -> list[dict]:
        """Return last N risk snapshots for trend charts.

        Args:
            days: Number of recent snapshots to return.

        Returns:
            List of snapshot summary dicts ordered by date ascending.
        """
        snapshots = list(self._risk_snapshots)
        return snapshots[-days:] if len(snapshots) > days else snapshots

    def generate_alerts(self, risk_data: dict) -> list[dict]:
        """Generate two-tier alerts from a risk snapshot.

        Scans VaR, leverage, drawdown, and concentration utilization.
        At 80% utilization -> WARNING. At 100% -> BREACH.

        Args:
            risk_data: Risk snapshot dict from compute_live_risk().

        Returns:
            List of alert dicts with type, severity, message, value, limit.
        """
        alerts: list[dict] = []
        warning_pct = self.pms_limits.warning_threshold_pct  # 80

        # VaR alerts
        var_data = risk_data.get("var", {})
        self._check_alert(
            alerts,
            "VAR",
            var_data.get("utilization_95_pct", 0.0),
            var_data.get("parametric_95", 0.0),
            var_data.get("limit_95_pct", 0.0),
            "VaR 95%",
            warning_pct,
        )
        self._check_alert(
            alerts,
            "VAR",
            var_data.get("utilization_99_pct", 0.0),
            var_data.get("parametric_99", 0.0),
            var_data.get("limit_99_pct", 0.0),
            "VaR 99%",
            warning_pct,
        )

        # Leverage alerts
        lev_data = risk_data.get("leverage", {})
        self._check_alert(
            alerts,
            "LEVERAGE",
            lev_data.get("utilization_gross_pct", 0.0),
            lev_data.get("gross", 0.0),
            lev_data.get("limit_gross", 0.0),
            "Gross Leverage",
            warning_pct,
        )
        self._check_alert(
            alerts,
            "LEVERAGE",
            lev_data.get("utilization_net_pct", 0.0),
            lev_data.get("net", 0.0),
            lev_data.get("limit_net", 0.0),
            "Net Leverage",
            warning_pct,
        )

        # Drawdown alerts
        dd_data = risk_data.get("drawdown", {})
        dd_current = abs(dd_data.get("current_drawdown_pct", 0.0))
        dd_limit = dd_data.get("limit_pct", 0.0)
        dd_warning = dd_data.get("warning_pct", 0.0)

        if dd_limit > 0 and dd_current >= dd_limit:
            alerts.append(
                {
                    "type": "DRAWDOWN_BREACH",
                    "severity": "BREACH",
                    "message": f"Drawdown {dd_current:.2f}% breached limit {dd_limit:.2f}%",
                    "value": dd_current,
                    "limit": dd_limit,
                }
            )
        elif dd_warning > 0 and dd_current >= dd_warning:
            alerts.append(
                {
                    "type": "DRAWDOWN_WARNING",
                    "severity": "WARNING",
                    "message": f"Drawdown {dd_current:.2f}% approaching limit ({dd_warning:.2f}% warning)",
                    "value": dd_current,
                    "limit": dd_limit,
                }
            )

        # Concentration alerts
        conc_data = risk_data.get("concentration", {})
        by_ac = conc_data.get("by_asset_class", {})
        for ac_name, ac_info in by_ac.items():
            status = ac_info.get("status", "OK")
            if status == "BREACHED":
                alerts.append(
                    {
                        "type": "CONCENTRATION_BREACH",
                        "severity": "BREACH",
                        "message": (
                            f"{ac_name} concentration {ac_info['notional_pct']:.1f}%"
                            f" breached limit {ac_info['limit_pct']:.1f}%"
                        ),
                        "value": ac_info["notional_pct"],
                        "limit": ac_info["limit_pct"],
                    }
                )
            elif status == "WARNING":
                alerts.append(
                    {
                        "type": "CONCENTRATION_WARNING",
                        "severity": "WARNING",
                        "message": (
                            f"{ac_name} concentration {ac_info['notional_pct']:.1f}%"
                            f" approaching limit {ac_info['limit_pct']:.1f}%"
                        ),
                        "value": ac_info["notional_pct"],
                        "limit": ac_info["limit_pct"],
                    }
                )

        # Limits summary alerts (from risk_limits_manager checks)
        limits_data = risk_data.get("limits_summary", {})
        for check in limits_data.get("checks", []):
            util = check.get("utilization_pct", 0.0)
            if check.get("status") == "BREACHED":
                alerts.append(
                    {
                        "type": f"LOSS_{check['limit_name'].upper()}_BREACH",
                        "severity": "BREACH",
                        "message": f"{check['limit_name']} at {util:.1f}% utilization (breached)",
                        "value": check["current_value"],
                        "limit": check["limit_value"],
                    }
                )
            elif check.get("status") == "WARNING":
                alerts.append(
                    {
                        "type": f"LOSS_{check['limit_name'].upper()}_WARNING",
                        "severity": "WARNING",
                        "message": f"{check['limit_name']} at {util:.1f}% utilization (warning)",
                        "value": check["current_value"],
                        "limit": check["limit_value"],
                    }
                )

        return alerts

    # ------------------------------------------------------------------
    # Private: section builders
    # ------------------------------------------------------------------

    def _get_book(self, ref_date: date) -> dict:
        """Get position book or empty structure if no position_manager."""
        if self.position_manager is None:
            return {
                "summary": {
                    "aum": 100_000_000.0,
                    "total_notional_brl": 0.0,
                    "leverage": 0.0,
                    "open_positions": 0,
                },
                "positions": [],
                "by_asset_class": {},
            }
        return self.position_manager.get_book(as_of_date=ref_date)

    def _compute_var_section(self, aum: float, limits: PMSRiskLimits) -> dict:
        """Compute VaR section from P&L history (parametric) and optional MC."""
        var_95_pct = 0.0
        var_99_pct = 0.0
        mc_95 = None
        mc_99 = None

        # Compute parametric VaR from daily P&L snapshots
        if self.position_manager is not None:
            pnl_ts = self.position_manager.get_pnl_timeseries()
            if len(pnl_ts) >= 20:
                # Convert daily P&L to portfolio returns (fraction of AUM)
                daily_returns = [
                    snap.get("daily_pnl_brl", 0.0) / aum for snap in pnl_ts
                ]
                if self.var_calculator is not None:
                    result = self.var_calculator.calculate(
                        __import__("numpy").array(daily_returns),
                        method="parametric",
                    )
                    var_95_pct = abs(result.var_95) * 100.0  # Convert to %
                    var_99_pct = abs(result.var_99) * 100.0
                else:
                    # Simple parametric VaR without VaRCalculator
                    import numpy as np

                    returns_arr = np.array(daily_returns)
                    mu = float(np.mean(returns_arr))
                    sigma = (
                        float(np.std(returns_arr, ddof=1))
                        if len(returns_arr) > 1
                        else 0.0
                    )
                    if sigma > 1e-12:
                        from scipy import stats

                        var_95_pct = abs(mu + sigma * stats.norm.ppf(0.05)) * 100.0
                        var_99_pct = abs(mu + sigma * stats.norm.ppf(0.01)) * 100.0

                # MC VaR requires >= 30 observations
                if len(pnl_ts) >= 30 and self.var_calculator is not None:
                    try:
                        import numpy as np

                        returns_arr = np.array(daily_returns).reshape(-1, 1)
                        weights = np.array([1.0])
                        mc_result = self.var_calculator.calculate_monte_carlo(
                            returns_arr,
                            weights,
                        )
                        mc_95 = abs(mc_result.var_95) * 100.0
                        mc_99 = abs(mc_result.var_99) * 100.0
                    except Exception:
                        logger.warning("mc_var_computation_failed", exc_info=True)

        # Utilization
        util_95 = (
            (var_95_pct / limits.var_95_limit_pct * 100.0)
            if limits.var_95_limit_pct > 0
            else 0.0
        )
        util_99 = (
            (var_99_pct / limits.var_99_limit_pct * 100.0)
            if limits.var_99_limit_pct > 0
            else 0.0
        )

        return {
            "parametric_95": var_95_pct,
            "parametric_99": var_99_pct,
            "monte_carlo_95": mc_95,
            "monte_carlo_99": mc_99,
            "limit_95_pct": limits.var_95_limit_pct,
            "limit_99_pct": limits.var_99_limit_pct,
            "utilization_95_pct": util_95,
            "utilization_99_pct": util_99,
        }

    def _compute_leverage_section(
        self,
        summary: dict,
        aum: float,
        limits: PMSRiskLimits,
    ) -> dict:
        """Compute leverage section from position book summary."""
        gross = summary.get("leverage", 0.0)

        # Net leverage: (long_notional - short_notional) / AUM
        net = 0.0
        if self.position_manager is not None:
            long_notional = 0.0
            short_notional = 0.0
            for p in self.position_manager._positions:
                if p.get("is_open"):
                    if p.get("direction") == "LONG":
                        long_notional += abs(p.get("notional_brl", 0.0))
                    else:
                        short_notional += abs(p.get("notional_brl", 0.0))
            if aum > 0:
                net = (long_notional - short_notional) / aum

        util_gross = (
            (gross / limits.gross_leverage_limit * 100.0)
            if limits.gross_leverage_limit > 0
            else 0.0
        )
        util_net = (
            (abs(net) / limits.net_leverage_limit * 100.0)
            if limits.net_leverage_limit > 0
            else 0.0
        )

        return {
            "gross": gross,
            "net": net,
            "limit_gross": limits.gross_leverage_limit,
            "limit_net": limits.net_leverage_limit,
            "utilization_gross_pct": util_gross,
            "utilization_net_pct": util_net,
        }

    def _compute_drawdown_section(self, aum: float, limits: PMSRiskLimits) -> dict:
        """Compute drawdown from cumulative P&L in _pnl_history."""
        current_dd_pct = 0.0
        max_dd_pct = 0.0
        days_in_dd = 0

        if self.position_manager is not None and aum > 0:
            pnl_ts = self.position_manager.get_pnl_timeseries()
            if pnl_ts:
                # Build equity curve from cumulative daily P&L
                cumulative = 0.0
                hwm = 0.0  # High water mark of cumulative P&L
                worst_dd = 0.0
                in_dd_days = 0

                for snap in pnl_ts:
                    daily = snap.get("daily_pnl_brl", 0.0)
                    cumulative += daily
                    if cumulative > hwm:
                        hwm = cumulative
                    dd = (hwm - cumulative) / aum * 100.0 if hwm > cumulative else 0.0
                    if dd > worst_dd:
                        worst_dd = dd
                    if dd > 0:
                        in_dd_days += 1
                    else:
                        in_dd_days = 0

                current_dd_pct = (
                    (hwm - cumulative) / aum * 100.0 if hwm > cumulative else 0.0
                )
                max_dd_pct = worst_dd
                days_in_dd = in_dd_days

        return {
            "current_drawdown_pct": current_dd_pct,
            "max_drawdown_pct": max_dd_pct,
            "limit_pct": limits.drawdown_limit_pct,
            "warning_pct": limits.drawdown_warning_pct,
            "days_in_drawdown": days_in_dd,
        }

    def _compute_concentration_section(
        self,
        by_asset_class: dict,
        summary: dict,
        positions: list,
        limits: PMSRiskLimits,
    ) -> dict:
        """Compute concentration by asset class with limit checking."""
        total_gross = summary.get("total_notional_brl", 0.0)
        conc_limits = limits.concentration_limits
        warning_pct = limits.warning_threshold_pct

        ac_breakdown: dict[str, dict] = {}
        for ac_name, ac_info in by_asset_class.items():
            ac_notional = ac_info.get("notional_brl", 0.0)
            notional_pct = (
                (ac_notional / total_gross * 100.0) if total_gross > 0 else 0.0
            )
            limit_pct = conc_limits.get(ac_name, 100.0)
            utilization_pct = (
                (notional_pct / limit_pct * 100.0) if limit_pct > 0 else 0.0
            )

            if utilization_pct >= 100.0:
                status = "BREACHED"
            elif utilization_pct >= warning_pct:
                status = "WARNING"
            else:
                status = "OK"

            ac_breakdown[ac_name] = {
                "notional_pct": notional_pct,
                "limit_pct": limit_pct,
                "utilization_pct": utilization_pct,
                "status": status,
            }

        # Top 3 positions concentration
        top_3_pct = 0.0
        if positions and total_gross > 0:
            sorted_positions = sorted(
                positions,
                key=lambda p: abs(p.get("notional_brl", 0.0)),
                reverse=True,
            )
            top_3_notional = sum(
                abs(p.get("notional_brl", 0.0)) for p in sorted_positions[:3]
            )
            top_3_pct = top_3_notional / total_gross * 100.0

        return {
            "by_asset_class": ac_breakdown,
            "top_3_positions_pct": top_3_pct,
        }

    def _compute_stress_section(
        self,
        positions: list,
        aum: float,
    ) -> list[dict]:
        """Run stress tests against current positions."""
        if self.stress_tester is None or not positions:
            return []

        # Build positions dict for stress_tester: instrument -> signed notional
        pos_map: dict[str, float] = {}
        for p in positions:
            instrument = p.get("instrument", "")
            notional = abs(p.get("notional_brl", 0.0))
            direction = p.get("direction", "LONG")
            # Short positions have negative notional for stress testing
            if direction == "SHORT":
                notional = -notional
            if instrument in pos_map:
                pos_map[instrument] += notional
            else:
                pos_map[instrument] = notional

        try:
            results = self.stress_tester.run_all(pos_map, portfolio_value=aum)
            return [
                {
                    "scenario": r.scenario_name,
                    "pnl_brl": r.portfolio_pnl,
                    "pnl_pct": r.portfolio_pnl_pct * 100.0,
                    "description": next(
                        (
                            s.description
                            for s in self.stress_tester.scenarios
                            if s.name == r.scenario_name
                        ),
                        "",
                    ),
                }
                for r in results
            ]
        except Exception:
            logger.warning("stress_test_failed", exc_info=True)
            return []

    def _compute_limits_section(
        self,
        book: dict,
        var_section: dict,
        leverage_section: dict,
        drawdown_section: dict,
    ) -> dict:
        """Compute limits summary from RiskLimitsManager and PMSRiskLimits."""
        limits = self.pms_limits
        warning_pct = limits.warning_threshold_pct
        checks: list[dict] = []

        # Build checks from PMSRiskLimits thresholds
        dd_util = (
            (
                drawdown_section.get("current_drawdown_pct", 0.0)
                / limits.drawdown_limit_pct
                * 100.0
            )
            if limits.drawdown_limit_pct > 0
            else 0.0
        )
        pms_checks = [
            (
                "VaR 95%",
                var_section.get("parametric_95", 0.0),
                limits.var_95_limit_pct,
                var_section.get("utilization_95_pct", 0.0),
            ),
            (
                "VaR 99%",
                var_section.get("parametric_99", 0.0),
                limits.var_99_limit_pct,
                var_section.get("utilization_99_pct", 0.0),
            ),
            (
                "Gross Leverage",
                leverage_section.get("gross", 0.0),
                limits.gross_leverage_limit,
                leverage_section.get("utilization_gross_pct", 0.0),
            ),
            (
                "Net Leverage",
                abs(leverage_section.get("net", 0.0)),
                limits.net_leverage_limit,
                leverage_section.get("utilization_net_pct", 0.0),
            ),
            (
                "Drawdown",
                drawdown_section.get("current_drawdown_pct", 0.0),
                limits.drawdown_limit_pct,
                dd_util,
            ),
        ]

        for name, current, limit_val, util in pms_checks:
            if util >= 100.0:
                status = "BREACHED"
            elif util >= warning_pct:
                status = "WARNING"
            else:
                status = "OK"

            checks.append(
                {
                    "limit_name": name,
                    "current_value": current,
                    "limit_value": limit_val,
                    "utilization_pct": util,
                    "status": status,
                }
            )

        # Add RiskLimitsManager v2 checks if available
        if self.risk_limits_manager is not None:
            try:
                summary = book.get("summary", {})
                portfolio_state = {
                    "leverage": summary.get("leverage", 0.0),
                    "var_95": var_section.get("parametric_95", 0.0) / 100.0,
                    "var_99": var_section.get("parametric_99", 0.0) / 100.0,
                    "drawdown_pct": drawdown_section.get("current_drawdown_pct", 0.0)
                    / 100.0,
                    "weights": {},
                    "asset_class_weights": {},
                }

                # Populate weights from positions
                positions = book.get("positions", [])
                aum = summary.get("aum", 1.0) or 1.0
                for p in positions:
                    instrument = p.get("instrument", "")
                    portfolio_state["weights"][instrument] = (
                        abs(p.get("notional_brl", 0.0)) / aum
                    )
                    ac = p.get("asset_class", "UNKNOWN")
                    portfolio_state["asset_class_weights"][ac] = (
                        portfolio_state["asset_class_weights"].get(ac, 0.0)
                        + abs(p.get("notional_brl", 0.0)) / aum
                    )

                v2_result = self.risk_limits_manager.check_all_v2(portfolio_state)

                # Add loss tracking info to checks
                loss_status = v2_result.get("loss_status")
                if loss_status is not None:
                    daily_loss = abs(loss_status.daily_pnl)
                    daily_limit = self.risk_limits_manager.config.daily_loss_limit_pct
                    daily_util = (
                        (daily_loss / daily_limit * 100.0) if daily_limit > 0 else 0.0
                    )
                    daily_status = "OK"
                    if daily_util >= 100.0:
                        daily_status = "BREACHED"
                    elif daily_util >= warning_pct:
                        daily_status = "WARNING"

                    checks.append(
                        {
                            "limit_name": "Daily Loss",
                            "current_value": daily_loss,
                            "limit_value": daily_limit,
                            "utilization_pct": daily_util,
                            "status": daily_status,
                        }
                    )

                    weekly_loss = abs(loss_status.cumulative_weekly_pnl)
                    weekly_limit = self.risk_limits_manager.config.weekly_loss_limit_pct
                    weekly_util = (
                        (weekly_loss / weekly_limit * 100.0)
                        if weekly_limit > 0
                        else 0.0
                    )
                    weekly_status = "OK"
                    if weekly_util >= 100.0:
                        weekly_status = "BREACHED"
                    elif weekly_util >= warning_pct:
                        weekly_status = "WARNING"

                    checks.append(
                        {
                            "limit_name": "Weekly Loss",
                            "current_value": weekly_loss,
                            "limit_value": weekly_limit,
                            "utilization_pct": weekly_util,
                            "status": weekly_status,
                        }
                    )

                # Risk budget check
                risk_budget = v2_result.get("risk_budget")
                if risk_budget is not None:
                    budget_util = risk_budget.utilization_pct
                    budget_status = "OK"
                    if budget_util >= 100.0:
                        budget_status = "BREACHED"
                    elif budget_util >= warning_pct:
                        budget_status = "WARNING"

                    checks.append(
                        {
                            "limit_name": "Risk Budget",
                            "current_value": risk_budget.allocated_risk,
                            "limit_value": risk_budget.total_risk_budget,
                            "utilization_pct": budget_util,
                            "status": budget_status,
                        }
                    )

            except Exception:
                logger.warning("risk_limits_v2_check_failed", exc_info=True)

        # Determine overall status
        has_breach = any(c["status"] == "BREACHED" for c in checks)
        has_warning = any(c["status"] == "WARNING" for c in checks)

        if has_breach:
            overall_status = "BREACHED"
        elif has_warning:
            overall_status = "WARNING"
        else:
            overall_status = "OK"

        return {
            "overall_status": overall_status,
            "checks": checks,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_alert(
        self,
        alerts: list[dict],
        alert_category: str,
        utilization_pct: float,
        current_value: float,
        limit_value: float,
        label: str,
        warning_threshold: float,
    ) -> None:
        """Append WARNING or BREACH alert based on utilization."""
        if utilization_pct >= 100.0:
            alerts.append(
                {
                    "type": f"{alert_category}_BREACH",
                    "severity": "BREACH",
                    "message": f"{label} at {utilization_pct:.1f}% utilization (breached)",
                    "value": current_value,
                    "limit": limit_value,
                }
            )
        elif utilization_pct >= warning_threshold:
            alerts.append(
                {
                    "type": f"{alert_category}_WARNING",
                    "severity": "WARNING",
                    "message": f"{label} at {utilization_pct:.1f}% utilization (warning)",
                    "value": current_value,
                    "limit": limit_value,
                }
            )

    def _persist_snapshot(self, ref_date: date, risk_data: dict) -> None:
        """Store compact snapshot summary for trend history."""
        var_data = risk_data.get("var", {})
        dd_data = risk_data.get("drawdown", {})
        lev_data = risk_data.get("leverage", {})

        snapshot = {
            "date": ref_date,
            "var_95": var_data.get("parametric_95", 0.0),
            "var_99": var_data.get("parametric_99", 0.0),
            "leverage_gross": lev_data.get("gross", 0.0),
            "drawdown_pct": dd_data.get("current_drawdown_pct", 0.0),
            "alert_count": len(risk_data.get("alerts", [])),
            "overall_status": risk_data.get("limits_summary", {}).get(
                "overall_status", "OK"
            ),
        }
        self._risk_snapshots.append(snapshot)
