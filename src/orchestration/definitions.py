"""Central Dagster Definitions module for the Macro Trading system.

Registers all 22 assets across 7 layers (Bronze, Silver, Agents, Signals,
Portfolio, Risk, Report), defines the daily pipeline job and Bronze-only
ingest job, and configures the weekday cron schedule at 09:00 UTC (06:00 BRT).

The ``defs`` variable is the Dagster convention entry point -- Dagster
discovers it automatically when pointed at this module via
``-m src.orchestration.definitions``.
"""

from dagster import Definitions, ScheduleDefinition, define_asset_job

# Import all assets -- Bronze
from src.orchestration.assets_bronze import (
    bronze_b3_market_data,
    bronze_bcb_ptax,
    bronze_bcb_sgs,
    bronze_fred,
    bronze_treasury_gov,
    bronze_yahoo,
)

# Import all assets -- Silver
from src.orchestration.assets_silver import (
    silver_curves,
    silver_macro,
    silver_returns,
)

# Import all assets -- Agents
from src.orchestration.assets_agents import (
    agent_cross_asset,
    agent_fiscal,
    agent_fx_equilibrium,
    agent_inflation,
    agent_monetary_policy,
)

# Import all assets -- Signals
from src.orchestration.assets_signals import (
    signal_aggregation,
    signal_monitor,
)

# Import all assets -- Portfolio
from src.orchestration.assets_portfolio import (
    portfolio_optimization,
    portfolio_sizing,
)

# Import all assets -- Risk
from src.orchestration.assets_risk import (
    risk_limits,
    risk_stress,
    risk_var,
)

# Import all assets -- Report
from src.orchestration.assets_report import daily_report

# ---------------------------------------------------------------------------
# Asset lists
# ---------------------------------------------------------------------------

bronze_assets = [
    bronze_bcb_sgs,
    bronze_fred,
    bronze_yahoo,
    bronze_bcb_ptax,
    bronze_b3_market_data,
    bronze_treasury_gov,
]

all_assets = [
    # Bronze (6)
    bronze_bcb_sgs,
    bronze_fred,
    bronze_yahoo,
    bronze_bcb_ptax,
    bronze_b3_market_data,
    bronze_treasury_gov,
    # Silver (3)
    silver_curves,
    silver_returns,
    silver_macro,
    # Agents (5)
    agent_inflation,
    agent_monetary_policy,
    agent_fiscal,
    agent_fx_equilibrium,
    agent_cross_asset,
    # Signals (2)
    signal_aggregation,
    signal_monitor,
    # Portfolio (2)
    portfolio_optimization,
    portfolio_sizing,
    # Risk (3)
    risk_var,
    risk_stress,
    risk_limits,
    # Report (1)
    daily_report,
]

# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

# Full pipeline job -- materializes all 22 assets in dependency order
daily_pipeline_job = define_asset_job(
    name="daily_pipeline",
    selection=all_assets,
    description="Full daily pipeline: Bronze -> Silver -> Agents -> Signals -> Portfolio -> Risk -> Report",
)

# Bronze-only ingest job for selective materialization
bronze_job = define_asset_job(
    name="bronze_ingest",
    selection=bronze_assets,
    description="Ingest Bronze layer data only",
)

# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

# Cron schedule: 09:00 UTC = 06:00 BRT, weekdays only
daily_schedule = ScheduleDefinition(
    job=daily_pipeline_job,
    cron_schedule="0 9 * * 1-5",
    name="daily_pipeline_schedule",
)

# ---------------------------------------------------------------------------
# Dagster Definitions entry point
# ---------------------------------------------------------------------------

defs = Definitions(
    assets=all_assets,
    schedules=[daily_schedule],
    jobs=[daily_pipeline_job, bronze_job],
)
