"""Agent layer Dagster asset definitions.

Defines 5 analytical agent assets matching AgentRegistry.EXECUTION_ORDER:
inflation -> monetary_policy -> fiscal -> fx_equilibrium -> cross_asset.

Each agent asset depends on the appropriate Silver assets and (for
cross_asset) on all 4 prior agent assets.  Agents are invoked via the
AgentRegistry for consistent execution patterns.
"""

from datetime import date

from dagster import (
    AssetExecutionContext,
    Backoff,
    DailyPartitionsDefinition,
    RetryPolicy,
    asset,
)

from src.agents.registry import AgentRegistry

# Shared configuration
_daily_partitions = DailyPartitionsDefinition(start_date="2010-01-01")
_retry_policy = RetryPolicy(
    max_retries=3,
    delay=30,
    backoff=Backoff.EXPONENTIAL,
)

# Silver assets that all agents depend on
_silver_deps = ["silver_curves", "silver_returns", "silver_macro"]


def _partition_date(context: AssetExecutionContext) -> date:
    """Extract the partition date from Dagster context."""
    if context.has_partition_key:
        return date.fromisoformat(context.partition_key)
    return date.today()


def _ensure_agents_registered() -> None:
    """Register all 5 agents if not already registered.

    Uses lazy imports to avoid circular dependencies.
    """
    registered = AgentRegistry.list_registered()
    if len(registered) >= 5:
        return

    from src.agents.data_loader import PointInTimeDataLoader

    loader = PointInTimeDataLoader()
    AgentRegistry.clear()

    from src.agents.cross_asset_agent import CrossAssetAgent
    from src.agents.fiscal_agent import FiscalAgent
    from src.agents.fx_agent import FxEquilibriumAgent
    from src.agents.inflation_agent import InflationAgent
    from src.agents.monetary_agent import MonetaryPolicyAgent

    for agent_cls in [
        InflationAgent,
        MonetaryPolicyAgent,
        FiscalAgent,
        FxEquilibriumAgent,
        CrossAssetAgent,
    ]:
        AgentRegistry.register(agent_cls(loader=loader))


def _run_agent(agent_id: str, as_of: date) -> dict:
    """Run a single agent via the registry and return a summary dict.

    Args:
        agent_id: The registry key for the agent.
        as_of: Point-in-time reference date.

    Returns:
        Summary dict with signal count, regime (if available), and status.
    """
    _ensure_agents_registered()
    agent = AgentRegistry.get(agent_id)
    report = agent.backtest_run(as_of)
    return {
        "status": "success",
        "agent_id": agent_id,
        "signal_count": len(report.signals),
        "regime": getattr(report, "regime", None),
        "date": str(as_of),
    }


# ---------------------------------------------------------------------------
# Agent Assets
# ---------------------------------------------------------------------------


@asset(
    group_name="agents",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    deps=_silver_deps,
    description="Run Inflation Agent: IPCA analysis, inflation expectations, breakevens",
)
def agent_inflation(context: AssetExecutionContext) -> dict:
    """Execute the Inflation Agent for the partition date.

    Depends on all Silver assets for macro data and curves.
    """
    as_of = _partition_date(context)
    context.log.info(f"Running Inflation Agent for {as_of}")
    try:
        result = _run_agent("inflation_agent", as_of)
        context.log.info(f"Inflation Agent complete: {result['signal_count']} signals")
        return result
    except Exception as exc:
        context.log.error(f"Inflation Agent failed: {exc}")
        raise


@asset(
    group_name="agents",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    deps=_silver_deps + ["agent_inflation"],
    description="Run Monetary Policy Agent: SELIC/Fed Funds analysis, rate expectations",
)
def agent_monetary_policy(context: AssetExecutionContext) -> dict:
    """Execute the Monetary Policy Agent for the partition date.

    Depends on Silver assets and agent_inflation for inflation context.
    """
    as_of = _partition_date(context)
    context.log.info(f"Running Monetary Policy Agent for {as_of}")
    try:
        result = _run_agent("monetary_agent", as_of)
        context.log.info(
            f"Monetary Policy Agent complete: {result['signal_count']} signals"
        )
        return result
    except Exception as exc:
        context.log.error(f"Monetary Policy Agent failed: {exc}")
        raise


@asset(
    group_name="agents",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    deps=_silver_deps,
    description="Run Fiscal Agent: budget analysis, debt dynamics, sovereign risk",
)
def agent_fiscal(context: AssetExecutionContext) -> dict:
    """Execute the Fiscal Agent for the partition date.

    Depends on Silver assets for macro data.
    """
    as_of = _partition_date(context)
    context.log.info(f"Running Fiscal Agent for {as_of}")
    try:
        result = _run_agent("fiscal_agent", as_of)
        context.log.info(f"Fiscal Agent complete: {result['signal_count']} signals")
        return result
    except Exception as exc:
        context.log.error(f"Fiscal Agent failed: {exc}")
        raise


@asset(
    group_name="agents",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    deps=_silver_deps,
    description="Run FX Equilibrium Agent: REER models, PPP, carry-adjusted fair value",
)
def agent_fx_equilibrium(context: AssetExecutionContext) -> dict:
    """Execute the FX Equilibrium Agent for the partition date.

    Depends on Silver assets for macro data and market returns.
    """
    as_of = _partition_date(context)
    context.log.info(f"Running FX Equilibrium Agent for {as_of}")
    try:
        result = _run_agent("fx_agent", as_of)
        context.log.info(
            f"FX Equilibrium Agent complete: {result['signal_count']} signals"
        )
        return result
    except Exception as exc:
        context.log.error(f"FX Equilibrium Agent failed: {exc}")
        raise


@asset(
    group_name="agents",
    retry_policy=_retry_policy,
    partitions_def=_daily_partitions,
    deps=_silver_deps
    + [
        "agent_inflation",
        "agent_monetary_policy",
        "agent_fiscal",
        "agent_fx_equilibrium",
    ],
    description="Run Cross-Asset Agent: regime detection, cross-market signals, risk-on/off",
)
def agent_cross_asset(context: AssetExecutionContext) -> dict:
    """Execute the Cross-Asset Agent for the partition date.

    Depends on all Silver assets AND all 4 prior agent assets,
    as it synthesizes cross-market views from all other agents.
    """
    as_of = _partition_date(context)
    context.log.info(f"Running Cross-Asset Agent for {as_of}")
    try:
        result = _run_agent("cross_asset_agent", as_of)
        context.log.info(
            f"Cross-Asset Agent complete: {result['signal_count']} signals"
        )
        return result
    except Exception as exc:
        context.log.error(f"Cross-Asset Agent failed: {exc}")
        raise
