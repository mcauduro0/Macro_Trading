"""Central Dagster Definitions module for the Macro Trading system.

Registers all Bronze, Silver, and Agent assets, defines the daily pipeline
job, and configures the weekday cron schedule at 09:00 UTC (06:00 BRT).

The ``defs`` variable is the Dagster convention entry point -- Dagster
discovers it automatically when pointed at this module via
``-m src.orchestration.definitions``.
"""

from dagster import Definitions, ScheduleDefinition, define_asset_job

# Import all assets
from src.orchestration.assets_agents import (
    agent_cross_asset,
    agent_fiscal,
    agent_fx_equilibrium,
    agent_inflation,
    agent_monetary_policy,
)
from src.orchestration.assets_bronze import (
    bronze_b3_market_data,
    bronze_bcb_ptax,
    bronze_bcb_sgs,
    bronze_fred,
    bronze_treasury_gov,
    bronze_yahoo,
)
from src.orchestration.assets_silver import (
    silver_curves,
    silver_macro,
    silver_returns,
)

all_assets = [
    # Bronze
    bronze_bcb_sgs,
    bronze_fred,
    bronze_yahoo,
    bronze_bcb_ptax,
    bronze_b3_market_data,
    bronze_treasury_gov,
    # Silver
    silver_curves,
    silver_returns,
    silver_macro,
    # Agents
    agent_inflation,
    agent_monetary_policy,
    agent_fiscal,
    agent_fx_equilibrium,
    agent_cross_asset,
]

# Full pipeline job -- materializes all assets in dependency order
daily_pipeline_job = define_asset_job(
    name="daily_pipeline",
    selection=all_assets,
    description="Full daily pipeline: Bronze -> Silver -> Agents",
)

# Cron schedule: 09:00 UTC = 06:00 BRT, weekdays only
daily_schedule = ScheduleDefinition(
    job=daily_pipeline_job,
    cron_schedule="0 9 * * 1-5",
    name="daily_pipeline_schedule",
)

defs = Definitions(
    assets=all_assets,
    schedules=[daily_schedule],
    jobs=[daily_pipeline_job],
)
