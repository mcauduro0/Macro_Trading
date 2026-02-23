"""Report layer Dagster asset definition.

Defines the daily_report asset that collects outputs from all upstream
pipeline stages into a structured context dict. This is a placeholder
for the DailyReportGenerator that will be implemented in Plan 18-04.
"""

from datetime import date

from dagster import (
    AssetExecutionContext,
    AssetIn,
    Backoff,
    DailyPartitionsDefinition,
    RetryPolicy,
    asset,
)

# Shared configuration
_daily_partitions = DailyPartitionsDefinition(start_date="2010-01-01")
_retry_policy = RetryPolicy(
    max_retries=3,
    delay=30,
    backoff=Backoff.EXPONENTIAL,
)


def _partition_date(context: AssetExecutionContext) -> date:
    """Extract the partition date from Dagster context."""
    if context.has_partition_key:
        return date.fromisoformat(context.partition_key)
    return date.today()


# ---------------------------------------------------------------------------
# Report Asset
# ---------------------------------------------------------------------------

@asset(
    group_name="report",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    ins={
        "signal_monitor": AssetIn(key="signal_monitor"),
        "portfolio_sizing": AssetIn(key="portfolio_sizing"),
        "risk_var": AssetIn(key="risk_var"),
        "risk_stress": AssetIn(key="risk_stress"),
        "risk_limits": AssetIn(key="risk_limits"),
    },
    description="Daily report context assembly (placeholder for 18-04 DailyReportGenerator)",
)
def daily_report(
    context: AssetExecutionContext,
    signal_monitor: dict,
    portfolio_sizing: dict,
    risk_var: dict,
    risk_stress: dict,
    risk_limits: dict,
) -> dict:
    """Assemble pipeline results into a structured report context dict.

    Depends on signal_monitor, portfolio_sizing, risk_var, risk_stress,
    and risk_limits. Collects all upstream outputs into sections for
    the DailyReportGenerator (implemented in Plan 18-04).
    """
    as_of = _partition_date(context)
    context.log.info(f"Assembling daily report context for {as_of}")

    report_context = {
        "market_snapshot": {
            "date": str(as_of),
            "data_status": "ready",
        },
        "regime": {
            "source": "cross_asset_agent",
            "status": "available",
        },
        "agent_views": {
            "n_agents": 5,
            "status": "aggregated",
        },
        "signals": {
            "monitored_signals": signal_monitor.get("monitored_signals", 0),
            "flips": signal_monitor.get("flips", 0),
            "surges": signal_monitor.get("surges", 0),
            "divergences": signal_monitor.get("divergences", 0),
        },
        "portfolio": {
            "n_positions": portfolio_sizing.get("n_positions", 0),
            "sizing_method": portfolio_sizing.get("sizing_method", "vol_target"),
        },
        "risk": {
            "var_95": risk_var.get("var_95", 0.0),
            "var_99": risk_var.get("var_99", 0.0),
            "worst_stress_scenario": risk_stress.get("worst_case_scenario"),
            "worst_stress_pnl_pct": risk_stress.get("worst_case_pnl_pct", 0.0),
            "limits_status": risk_limits.get("overall_status", "OK"),
            "limits_breached": risk_limits.get("limits_breached", 0),
        },
        "actions": {
            "rebalance_needed": False,
            "alerts": [],
        },
    }

    section_count = len(report_context)

    context.log.info(
        f"Daily report context assembled: {section_count} sections for {as_of}"
    )

    return {
        "status": "report_context_ready",
        "date": str(as_of),
        "sections": section_count,
        "report_context": report_context,
    }
