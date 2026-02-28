"""Alert rule definitions for the Macro Trading monitoring system.

Provides 10 configurable alert rules covering data freshness, risk metrics,
signal behavior, and pipeline health.  Each rule has a callable ``check_fn``
that receives a *context* dict and returns ``True`` when the alert should fire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------------------
# AlertRule dataclass
# ---------------------------------------------------------------------------


@dataclass
class AlertRule:
    """A single evaluatable alert rule.

    Attributes:
        rule_id: Unique identifier (e.g. ``"STALE_DATA"``).
        name: Human-readable rule name.
        description: What condition this rule detects.
        severity: ``"warning"`` or ``"critical"``.
        enabled: Runtime toggle (default ``True``).
        threshold: Configurable numeric threshold.
        cooldown_minutes: Minutes between repeated firings (default 30).
        check_fn: ``(context: dict) -> bool`` -- returns ``True`` to fire.
    """

    rule_id: str
    name: str
    description: str
    severity: str  # "warning" | "critical"
    enabled: bool = True
    threshold: float = 0.0
    cooldown_minutes: int = 30
    check_fn: Callable[[dict[str, Any]], bool] = field(default=lambda ctx: False)


# ---------------------------------------------------------------------------
# Check functions -- each receives a context dict and returns bool
# ---------------------------------------------------------------------------


def _check_stale_data(ctx: dict[str, Any]) -> bool:
    """Fire when any connector's last successful run is older than threshold seconds."""
    threshold = ctx.get("_threshold", 3600)
    pipeline_status = ctx.get("pipeline_status", {})
    for connector, info in pipeline_status.items():
        last_run_age = info.get("last_run_age", 0)
        if last_run_age > threshold:
            return True
    return False


def _check_var_breach(ctx: dict[str, Any]) -> bool:
    """Fire when VaR 95% exceeds threshold."""
    threshold = ctx.get("_threshold", 0.05)
    risk = ctx.get("risk_metrics", {})
    var_95 = risk.get("var_95", 0.0)
    return abs(var_95) > threshold


def _check_var_critical(ctx: dict[str, Any]) -> bool:
    """Fire when VaR 99% exceeds threshold."""
    threshold = ctx.get("_threshold", 0.08)
    risk = ctx.get("risk_metrics", {})
    var_99 = risk.get("var_99", 0.0)
    return abs(var_99) > threshold


def _check_drawdown_warning(ctx: dict[str, Any]) -> bool:
    """Fire when current drawdown exceeds threshold."""
    threshold = ctx.get("_threshold", 0.05)
    risk = ctx.get("risk_metrics", {})
    drawdown = risk.get("current_drawdown", 0.0)
    return abs(drawdown) > threshold


def _check_drawdown_critical(ctx: dict[str, Any]) -> bool:
    """Fire when drawdown exceeds critical threshold."""
    threshold = ctx.get("_threshold", 0.10)
    risk = ctx.get("risk_metrics", {})
    drawdown = risk.get("current_drawdown", 0.0)
    return abs(drawdown) > threshold


def _check_limit_breach(ctx: dict[str, Any]) -> bool:
    """Fire when any risk limit utilization >= threshold (100%)."""
    threshold = ctx.get("_threshold", 1.0)
    limits = ctx.get("risk_limits", {})
    for limit_name, info in limits.items():
        utilization = info.get("utilization", 0.0)
        if utilization >= threshold:
            return True
    return False


def _check_signal_flip(ctx: dict[str, Any]) -> bool:
    """Fire when signal flip count in last 24h >= threshold."""
    threshold = ctx.get("_threshold", 1)
    signal_monitor = ctx.get("signal_monitor", {})
    flip_count = signal_monitor.get("flip_count_24h", 0)
    return flip_count >= threshold


def _check_conviction_surge(ctx: dict[str, Any]) -> bool:
    """Fire when any signal conviction change > threshold."""
    threshold = ctx.get("_threshold", 0.3)
    signal_monitor = ctx.get("signal_monitor", {})
    conviction_changes = signal_monitor.get("conviction_changes", [])
    for change in conviction_changes:
        if abs(change.get("delta", 0.0)) > threshold:
            return True
    return False


def _check_pipeline_failure(ctx: dict[str, Any]) -> bool:
    """Fire when any pipeline run status = 'FAILED'."""
    pipeline_status = ctx.get("pipeline_status", {})
    for connector, info in pipeline_status.items():
        if info.get("status", "").upper() == "FAILED":
            return True
    return False


def _check_agent_stale(ctx: dict[str, Any]) -> bool:
    """Fire when any agent's last report is older than threshold seconds."""
    threshold = ctx.get("_threshold", 86400)
    agent_timestamps = ctx.get("agent_timestamps", {})
    for agent_id, info in agent_timestamps.items():
        age = info.get("age_seconds", 0)
        if age > threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# Default rule set
# ---------------------------------------------------------------------------

DEFAULT_RULES: list[AlertRule] = [
    AlertRule(
        rule_id="STALE_DATA",
        name="Stale Data",
        description="Fires when any connector's last successful run is older than threshold",
        severity="warning",
        threshold=3600,
        cooldown_minutes=30,
        check_fn=_check_stale_data,
    ),
    AlertRule(
        rule_id="VAR_BREACH",
        name="VaR Breach (95%)",
        description="Fires when VaR 95% exceeds threshold",
        severity="warning",
        threshold=0.05,
        cooldown_minutes=30,
        check_fn=_check_var_breach,
    ),
    AlertRule(
        rule_id="VAR_CRITICAL",
        name="VaR Critical (99%)",
        description="Fires when VaR 99% exceeds critical threshold",
        severity="critical",
        threshold=0.08,
        cooldown_minutes=30,
        check_fn=_check_var_critical,
    ),
    AlertRule(
        rule_id="DRAWDOWN_WARNING",
        name="Drawdown Warning",
        description="Fires when current drawdown exceeds threshold",
        severity="warning",
        threshold=0.05,
        cooldown_minutes=30,
        check_fn=_check_drawdown_warning,
    ),
    AlertRule(
        rule_id="DRAWDOWN_CRITICAL",
        name="Drawdown Critical",
        description="Fires when drawdown exceeds critical threshold",
        severity="critical",
        threshold=0.10,
        cooldown_minutes=30,
        check_fn=_check_drawdown_critical,
    ),
    AlertRule(
        rule_id="LIMIT_BREACH",
        name="Risk Limit Breach",
        description="Fires when any risk limit utilization >= 100%",
        severity="critical",
        threshold=1.0,
        cooldown_minutes=30,
        check_fn=_check_limit_breach,
    ),
    AlertRule(
        rule_id="SIGNAL_FLIP",
        name="Signal Flip",
        description="Fires when signal flip count in last 24h >= threshold",
        severity="warning",
        threshold=1,
        cooldown_minutes=30,
        check_fn=_check_signal_flip,
    ),
    AlertRule(
        rule_id="CONVICTION_SURGE",
        name="Conviction Surge",
        description="Fires when any signal conviction change exceeds threshold",
        severity="warning",
        threshold=0.3,
        cooldown_minutes=30,
        check_fn=_check_conviction_surge,
    ),
    AlertRule(
        rule_id="PIPELINE_FAILURE",
        name="Pipeline Failure",
        description="Fires when any pipeline run status is FAILED",
        severity="critical",
        threshold=0,
        cooldown_minutes=30,
        check_fn=_check_pipeline_failure,
    ),
    AlertRule(
        rule_id="AGENT_STALE",
        name="Agent Stale",
        description="Fires when any agent's last report is older than threshold",
        severity="warning",
        threshold=86400,
        cooldown_minutes=30,
        check_fn=_check_agent_stale,
    ),
]
