"""Central Dagster Definitions module for the Macro Trading system.

Registers all 26 assets across 8 layers (Bronze, Silver, Agents, Signals,
Portfolio, Risk, Report, PMS), defines 4 jobs (daily_pipeline, bronze_ingest,
pms_eod_pipeline, pms_preopen_pipeline) and 3 schedules (daily at 09:00 UTC,
PMS EOD at 21:00 UTC, PMS pre-open at 09:30 UTC -- offset 30 min from daily).

The ``defs`` variable is the Dagster convention entry point -- Dagster
discovers it automatically when pointed at this module via
``-m src.orchestration.definitions``.
"""

from dagster import Definitions, ScheduleDefinition, define_asset_job

# Import all assets -- Agents
from src.orchestration.assets_agents import (
    agent_cross_asset,
    agent_fiscal,
    agent_fx_equilibrium,
    agent_inflation,
    agent_monetary_policy,
)

# Import all assets -- Bronze
from src.orchestration.assets_bronze import (
    bronze_b3_market_data,
    bronze_bcb_ptax,
    bronze_bcb_sgs,
    bronze_fred,
    bronze_treasury_gov,
    bronze_yahoo,
)

# Import all assets -- PMS
from src.orchestration.assets_pms import (
    pms_mark_to_market,
    pms_morning_pack,
    pms_performance_attribution,
    pms_trade_proposals,
)

# Import all assets -- Portfolio
from src.orchestration.assets_portfolio import (
    portfolio_optimization,
    portfolio_sizing,
)

# Import all assets -- Report
from src.orchestration.assets_report import daily_report

# Import all assets -- Risk
from src.orchestration.assets_risk import (
    risk_limits,
    risk_stress,
    risk_var,
)

# Import all assets -- Signals
from src.orchestration.assets_signals import (
    signal_aggregation,
    signal_monitor,
)

# Import all assets -- Silver
from src.orchestration.assets_silver import (
    silver_curves,
    silver_macro,
    silver_returns,
)

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
    # PMS (4)
    pms_mark_to_market,
    pms_trade_proposals,
    pms_morning_pack,
    pms_performance_attribution,
]

# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

# Full pipeline job -- materializes all 22 core assets in dependency order
daily_pipeline_job = define_asset_job(
    name="daily_pipeline",
    selection=all_assets,
    description="Full daily pipeline: Bronze -> Silver -> Agents -> Signals -> Portfolio -> Risk -> Report -> PMS",
)

# Bronze-only ingest job for selective materialization
bronze_job = define_asset_job(
    name="bronze_ingest",
    selection=bronze_assets,
    description="Ingest Bronze layer data only",
)

# PMS EOD job -- MTM + attribution (after market close)
pms_eod_job = define_asset_job(
    name="pms_eod_pipeline",
    selection=[pms_mark_to_market, pms_performance_attribution],
    description="PMS End-of-Day: MTM all positions + compute attribution",
)

# PMS Pre-Open job -- MTM + proposals + morning pack (before market open)
# NOTE: Only 3 assets -- attribution is EOD-only per locked decision.
# MTM is included because proposals + morning_pack depend on it upstream.
pms_preopen_job = define_asset_job(
    name="pms_preopen_pipeline",
    selection=[pms_mark_to_market, pms_trade_proposals, pms_morning_pack],
    description="PMS Pre-Open: MTM + generate proposals + morning pack",
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

# PMS EOD: 21:00 UTC = 18:00 BRT, weekdays
pms_eod_schedule = ScheduleDefinition(
    job=pms_eod_job,
    cron_schedule="0 21 * * 1-5",
    name="pms_eod_schedule",
)

# PMS Pre-open: 09:30 UTC = 06:30 BRT, weekdays
# NOTE: daily_pipeline_schedule already fires at 09:00 UTC (0 9 * * 1-5).
# Offset PMS pre-open by 30 min to avoid simultaneous execution contention.
pms_preopen_schedule = ScheduleDefinition(
    job=pms_preopen_job,
    cron_schedule="30 9 * * 1-5",
    name="pms_preopen_schedule",
)

# ---------------------------------------------------------------------------
# Dagster Definitions entry point
# ---------------------------------------------------------------------------

defs = Definitions(
    assets=all_assets,
    schedules=[daily_schedule, pms_eod_schedule, pms_preopen_schedule],
    jobs=[daily_pipeline_job, bronze_job, pms_eod_job, pms_preopen_job],
)
