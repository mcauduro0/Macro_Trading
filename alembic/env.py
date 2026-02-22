"""Alembic environment configuration for TimescaleDB + SQLAlchemy 2.0.

Filters TimescaleDB auto-created indexes and internal schemas so that
`alembic revision --autogenerate` produces clean migrations without
attempting to drop TimescaleDB-managed objects.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import all model modules so they register with Base.metadata
from src.core.models import (  # noqa: F401
    agent_reports,
    backtest_results,
    curves,
    data_sources,
    fiscal_data,
    flow_data,
    instruments,
    macro_series,
    market_data,
    series_metadata,
    signals,
    strategy_state,
    vol_surfaces,
)
from src.core.models.base import Base

# Alembic Config object -- provides access to .ini values
config = context.config

# Set up Python logging from the config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# TimescaleDB filtering
# ---------------------------------------------------------------------------

# TimescaleDB internal schemas to exclude from autogenerate reflection
TIMESCALEDB_SCHEMAS = {
    "_timescaledb_catalog",
    "_timescaledb_internal",
    "_timescaledb_cache",
    "_timescaledb_config",
    "timescaledb_information",
    "timescaledb_experimental",
}

# TimescaleDB auto-creates indexes like "{table}_{time_col}_idx" when
# create_hypertable() is called. These must be excluded or Alembic
# autogenerate will attempt to drop them on every run.
KNOWN_HYPERTABLE_TIME_COLS = {
    "market_data": "timestamp",
    "macro_series": "observation_date",
    "curves": "curve_date",
    "flow_data": "observation_date",
    "fiscal_data": "observation_date",
    "vol_surfaces": "surface_date",
    "signals": "signal_date",
}


def _is_timescaledb_index(name: str) -> bool:
    """Check if an index was auto-created by TimescaleDB."""
    if name is None:
        return False
    for table, col in KNOWN_HYPERTABLE_TIME_COLS.items():
        if name == f"{table}_{col}_idx":
            return True
    return False


def include_name(name, type_, parent_names):
    """Filter out TimescaleDB internal objects from autogenerate."""
    if type_ == "schema":
        return name not in TIMESCALEDB_SCHEMAS
    if type_ == "index":
        return not _is_timescaledb_index(name)
    return True


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to database)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_name=include_name,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
