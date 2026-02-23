"""Report layer Dagster asset definition.

Defines the daily_report asset that collects outputs from all upstream
pipeline stages and feeds them to DailyReportGenerator (Plan 18-04).
"""

from datetime import date

from src.reporting.daily_report import DailyReportGenerator

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
    description="Daily report generation via DailyReportGenerator (7 sections)",
)
def daily_report(
    context: AssetExecutionContext,
    signal_monitor: dict,
    portfolio_sizing: dict,
    risk_var: dict,
    risk_stress: dict,
    risk_limits: dict,
) -> dict:
    """Generate the daily report using DailyReportGenerator.

    Depends on signal_monitor, portfolio_sizing, risk_var, risk_stress,
    and risk_limits. Passes upstream outputs as pipeline_context.
    """
    as_of = _partition_date(context)
    context.log.info(f"Generating daily report for {as_of}")

    pipeline_context = {
        "market_snapshot": {"date": str(as_of)},
        "regime": {"source": "cross_asset_agent"},
        "agent_views": {"n_agents": 5},
        "signals": {
            "total": signal_monitor.get("monitored_signals", 0),
            "flips": signal_monitor.get("flips", 0),
        },
        "portfolio": {
            "n_positions": portfolio_sizing.get("n_positions", 0),
        },
        "risk": {
            "var_95": risk_var.get("var_95", 0.0),
            "var_99": risk_var.get("var_99", 0.0),
            "worst_stress": risk_stress.get("worst_case_scenario"),
            "limits_breached": risk_limits.get("limits_breached", 0),
        },
        "actions": {},
    }

    generator = DailyReportGenerator(as_of_date=as_of)
    report = generator.generate(pipeline_context=pipeline_context)
    section_count = len(report)

    context.log.info(f"Daily report generated with {section_count} sections")

    return {
        "status": "report_generated",
        "sections": section_count,
        "date": str(as_of),
    }
