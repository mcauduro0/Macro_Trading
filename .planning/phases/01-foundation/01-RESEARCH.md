# Phase 1: Foundation - Research

**Researched:** 2026-02-19
**Domain:** Infrastructure stack (Docker Compose), database schema (TimescaleDB + SQLAlchemy 2.0), migrations (Alembic), configuration (pydantic-settings), async database engines, Redis client
**Confidence:** HIGH

## Summary

Phase 1 delivers the foundational infrastructure for the entire Macro Trading Data Infrastructure. This means a Docker Compose stack with five services (TimescaleDB, Redis, MongoDB, Kafka, MinIO), a complete database schema with 10 tables (7 hypertables + 3 metadata), Alembic migrations that create hypertables and configure compression, async/sync database engines, a Redis client singleton, and pydantic-settings-based configuration.

The critical technical challenges are: (1) Alembic + TimescaleDB integration, which has a well-documented pitfall where Alembic autogenerate tries to drop TimescaleDB-created indexes (Discussion #1465), (2) the TimescaleDB constraint that all unique indexes on hypertables must include the time partitioning column, requiring composite primary keys, and (3) correct Docker Compose configuration with health checks for all five services, using KRaft-mode Kafka (no Zookeeper).

**Primary recommendation:** Use raw SQL via `op.execute()` in Alembic migrations for all TimescaleDB-specific operations (enable extension, create_hypertable, ALTER TABLE compression, add_compression_policy). Do NOT rely on `sqlalchemy-timescaledb` dialect -- it is unmaintained. Use `include_name` in Alembic's `env.py` to filter out TimescaleDB auto-created indexes and internal schemas. Define all hypertable models with composite primary keys that include the time column.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- all implementation decisions are at Claude's discretion per CONTEXT.md.

### Claude's Discretion
All implementation decisions for Phase 1 are at Claude's discretion. The user trusts the builder's technical judgment for this infrastructure phase. Key areas where Claude will decide:

**Project Structure:**
- Package naming and directory layout
- Where models, config, connectors, and other modules live
- Import path conventions

**Schema Conventions:**
- Table and column naming style (snake_case expected for PostgreSQL)
- Metadata table design (instruments, series_metadata, + 1 more)
- Enum definitions (AssetClass, Frequency, Country, etc.)
- Column types, nullable/non-nullable choices

**Docker Stack Profiles:**
- Whether to use dev/prod profiles or run all services always
- Kafka inclusion strategy (the research flags premature Kafka as an anti-pattern -- Claude should consider including it as a disabled/optional service per INFRA-01 requirement)
- Resource limits and volume persistence configuration

**Development Workflow:**
- Makefile or script-based workflow
- First-time bootstrap process
- Migration workflow conventions
- .env template structure

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Docker Compose stack runs with TimescaleDB, Redis, MongoDB, Kafka, MinIO -- all healthy | Docker Compose section: exact image versions, health checks, KRaft Kafka config, networking, volumes |
| INFRA-02 | SQLAlchemy 2.0 ORM models define 10 tables with type hints and async support | SQLAlchemy 2.0 Patterns section: DeclarativeBase, Mapped[], mapped_column, composite PKs for hypertables |
| INFRA-03 | 7 TimescaleDB hypertables with compression policies | Schema Design section: all 7 hypertable schemas, compression config (segmentby, orderby, compress_after) |
| INFRA-04 | Alembic migration creates all tables, enables TimescaleDB extension, configures hypertables and compression | Alembic + TimescaleDB section: migration patterns, env.py config, index filtering, raw SQL approach |
| INFRA-05 | Configuration via pydantic-settings with .env file support for all service URLs and API keys | Pydantic-Settings section: BaseSettings pattern, nested models, env_nested_delimiter, .env template |
| INFRA-06 | Async database engine (asyncpg) and sync engine (psycopg2) with session factories | Database Engines section: async_sessionmaker, create_async_engine, sync engine for Alembic |
| INFRA-07 | Redis client singleton with connection pool | Redis Client section: redis.asyncio pattern, ConnectionPool, singleton lifecycle |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | >=2.0.36 | ORM with async support, Mapped[] type hints | Industry standard Python ORM; native async since 2.0 |
| asyncpg | >=0.30.0 | Async PostgreSQL driver | Fastest Python PostgreSQL driver; binary protocol |
| psycopg2-binary | >=2.9.10 | Sync PostgreSQL driver | Required by Alembic for migrations (Alembic does not support async natively) |
| Alembic | >=1.14.0 | Database migrations | Standard SQLAlchemy migration tool; autogenerate from models |
| pydantic-settings | >=2.7.0 | Configuration management | .env file support, type validation, nested models |
| pydantic | >=2.10.0 | Data validation | Required by pydantic-settings; used for enums, schemas |
| redis[hiredis] | >=5.2.0 | Redis client with async support | redis-py 5.x has built-in asyncio support (absorbed aioredis); hiredis for C parser speed |
| python-dotenv | >=1.0.1 | .env file loading | Required by pydantic-settings for DotEnvSettingsSource |

### Infrastructure (Docker Images)

| Image | Tag | Purpose | Why This Version |
|-------|-----|---------|-----------------|
| timescale/timescaledb | 2.18.0-pg16 | TimescaleDB on PostgreSQL 16 | Pin exact version, not `latest`; PG16 is current stable; 2.18.0 supports fast DML on compressed chunks |
| redis | 7-alpine | Redis cache | Alpine for small footprint; Redis 7 is current stable |
| mongo | 8.0 | MongoDB document store | MongoDB 8.0 is current; `mongosh` replaces deprecated `mongo` shell |
| confluentinc/cp-kafka | 7.8.0 | Kafka with KRaft mode | Confluent image supports KRaft natively; no Zookeeper needed |
| quay.io/minio/minio | RELEASE.2025-02-18T16-25-55Z | S3-compatible object storage | Pin to release date tag; `mc ready local` health check |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| structlog | >=24.4.0 | Structured JSON logging | All application logging; configured in Phase 1 for use by all subsequent phases |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw SQL in Alembic for hypertables | `sqlalchemy-timescaledb` dialect | Dialect is unmaintained (no updates in 12+ months, 47 GitHub stars). Raw SQL is explicit and reliable. |
| `timescale/timescaledb` image | `timescale/timescaledb-ha` | HA image adds pgvector, pgai, etc. Overkill for Phase 1; adds image size. Standard image sufficient. |
| `confluentinc/cp-kafka` | `apache/kafka` | Official Apache image is lighter but Confluent image has better docs, wider community adoption, and proven KRaft config patterns |
| psycopg2-binary | psycopg (v3) | psycopg3 has native async but Alembic integration is less documented; psycopg2-binary is battle-tested for Alembic |

**Installation:**
```bash
pip install "sqlalchemy>=2.0.36" "asyncpg>=0.30.0" "psycopg2-binary>=2.9.10" \
    "alembic>=1.14.0" "pydantic-settings>=2.7.0" "pydantic>=2.10.0" \
    "redis[hiredis]>=5.2.0" "python-dotenv>=1.0.1" "structlog>=24.4.0"
```

## Architecture Patterns

### Recommended Project Structure

```
src/
├── core/                    # Shared foundation (Phase 1 scope)
│   ├── __init__.py
│   ├── models/              # SQLAlchemy 2.0 ORM models
│   │   ├── __init__.py      # Re-exports Base and all models
│   │   ├── base.py          # DeclarativeBase, naming conventions, type maps
│   │   ├── instruments.py   # Instrument registry (metadata table)
│   │   ├── series_metadata.py # Series definitions (metadata table)
│   │   ├── data_sources.py  # Data source registry (3rd metadata table)
│   │   ├── market_data.py   # Price/rate hypertable
│   │   ├── macro_series.py  # Macro data with release_time (PIT)
│   │   ├── curves.py        # Yield curve points
│   │   ├── flow_data.py     # FX/capital flows
│   │   ├── fiscal_data.py   # Fiscal metrics
│   │   ├── vol_surfaces.py  # Volatility surface data
│   │   └── signals.py       # Trading signals (future use)
│   ├── database.py          # Async engine, sync engine, session factories
│   ├── config.py            # Settings via pydantic-settings
│   ├── enums.py             # Shared enumerations
│   └── redis.py             # Redis client singleton
├── connectors/              # (Phase 2+ -- created as empty package in Phase 1)
│   └── __init__.py
├── transforms/              # (Phase 5 -- created as empty package in Phase 1)
│   └── __init__.py
├── api/                     # (Phase 6 -- created as empty package in Phase 1)
│   └── __init__.py
└── __init__.py
alembic/                     # Alembic migration directory
├── versions/                # Migration scripts
├── env.py                   # Configured for async + TimescaleDB filtering
└── script.py.mako           # Template for new migrations
alembic.ini                  # Alembic configuration
docker-compose.yml           # Full infrastructure stack
.env.example                 # Template for environment variables
pyproject.toml               # Project metadata and dependencies
Makefile                     # Development workflow shortcuts
```

### Pattern 1: SQLAlchemy 2.0 DeclarativeBase with Naming Conventions

**What:** A base class that provides consistent constraint naming across all models, enabling Alembic to manage constraints reliably.

**When to use:** Always. This is the foundation all models inherit from.

**Example:**
```python
# src/core/models/base.py
from datetime import datetime, date
from typing import Optional
from sqlalchemy import MetaData, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming conventions for Alembic constraint management
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)
```

### Pattern 2: Hypertable Model with Composite Primary Key

**What:** TimescaleDB requires all unique indexes (including primary keys) to include the time partitioning column. ORM models for hypertables use composite PKs with (id, timestamp).

**When to use:** All 7 hypertable models.

**Why:** TimescaleDB partitions data into chunks by time. A unique index without the time column would require scanning ALL chunks to enforce uniqueness, which defeats the purpose of partitioning. This is an architectural requirement, not a workaround.

**Example:**
```python
# src/core/models/macro_series.py
from datetime import date, datetime
from typing import Optional
from sqlalchemy import (
    BigInteger, Date, DateTime, Float, ForeignKey,
    Index, SmallInteger, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class MacroSeries(Base):
    __tablename__ = "macro_series"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series_metadata.id"), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    release_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="When this value became known (TIMESTAMPTZ)"
    )
    revision_number: Mapped[int] = mapped_column(SmallInteger, default=0)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        # Natural key for idempotent upserts -- MUST include time column
        UniqueConstraint(
            "series_id", "observation_date", "revision_number",
            name="uq_macro_series_natural_key"
        ),
        # NOTE: Do NOT add an index on observation_date alone --
        # TimescaleDB auto-creates one when create_hypertable is called.
        Index("ix_macro_series_series_id", "series_id"),
        {"comment": "TimescaleDB hypertable partitioned on observation_date"},
    )
```

### Pattern 3: Metadata Table (Regular PostgreSQL Table, Not Hypertable)

**What:** Reference/dimension tables that do not contain time-series data. Standard auto-increment PKs, foreign keys from hypertables reference these.

**When to use:** instruments, series_metadata, data_sources tables.

**Example:**
```python
# src/core/models/instruments.py
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    exchange: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

### Pattern 4: Alembic Migration with TimescaleDB Operations

**What:** All TimescaleDB-specific operations (enable extension, create_hypertable, compression) are done via `op.execute()` with raw SQL. This is the ONLY reliable approach since there is no maintained SQLAlchemy dialect for TimescaleDB.

**When to use:** The initial migration and any migration that creates new hypertables.

**Example:**
```python
# alembic/versions/001_initial_schema.py
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # Step 1: Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # Step 2: Create tables (Alembic autogenerate handles this)
    # ... op.create_table(...) for all 10 tables ...

    # Step 3: Convert tables to hypertables
    # Market data: daily frequency, 1-month chunks
    op.execute("""
        SELECT create_hypertable(
            'market_data', 'timestamp',
            chunk_time_interval => INTERVAL '1 month',
            if_not_exists => TRUE
        );
    """)

    # Macro series: daily frequency, 1-year chunks (sparse data)
    op.execute("""
        SELECT create_hypertable(
            'macro_series', 'observation_date',
            chunk_time_interval => INTERVAL '1 year',
            if_not_exists => TRUE
        );
    """)

    # Curves: daily frequency, 3-month chunks
    op.execute("""
        SELECT create_hypertable(
            'curves', 'curve_date',
            chunk_time_interval => INTERVAL '3 months',
            if_not_exists => TRUE
        );
    """)

    # Flow data, fiscal data, vol surfaces: 1-year chunks
    for table, time_col in [
        ('flow_data', 'observation_date'),
        ('fiscal_data', 'observation_date'),
        ('vol_surfaces', 'surface_date'),
        ('signals', 'signal_date'),
    ]:
        op.execute(f"""
            SELECT create_hypertable(
                '{table}', '{time_col}',
                chunk_time_interval => INTERVAL '1 year',
                if_not_exists => TRUE
            );
        """)

    # Step 4: Enable compression with segmentby and orderby
    hypertable_compression = [
        ("market_data", "instrument_id", "timestamp DESC"),
        ("macro_series", "series_id", "observation_date DESC"),
        ("curves", "curve_id", "curve_date DESC"),
        ("flow_data", "series_id", "observation_date DESC"),
        ("fiscal_data", "series_id", "observation_date DESC"),
        ("vol_surfaces", "instrument_id", "surface_date DESC"),
        ("signals", "signal_type", "signal_date DESC"),
    ]

    for table, segmentby, orderby in hypertable_compression:
        op.execute(f"""
            ALTER TABLE {table} SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = '{segmentby}',
                timescaledb.compress_orderby = '{orderby}'
            );
        """)

    # Step 5: Add compression policies (generous delays)
    # NOTE: Policies are configured but will only compress chunks older
    # than the specified interval. Since we have no data yet, nothing
    # compresses. After backfill in Phase 4, these activate automatically.
    compression_policies = [
        ("market_data", "30 days"),
        ("macro_series", "90 days"),
        ("curves", "90 days"),
        ("flow_data", "90 days"),
        ("fiscal_data", "180 days"),
        ("vol_surfaces", "90 days"),
        ("signals", "90 days"),
    ]

    for table, delay in compression_policies:
        op.execute(f"""
            SELECT add_compression_policy('{table}', INTERVAL '{delay}');
        """)


def downgrade() -> None:
    # Remove compression policies first
    for table in [
        "signals", "vol_surfaces", "fiscal_data",
        "flow_data", "curves", "macro_series", "market_data",
    ]:
        op.execute(f"SELECT remove_compression_policy('{table}', if_exists => true);")
        op.execute(f"ALTER TABLE {table} SET (timescaledb.compress = false);")

    # Drop tables in reverse dependency order
    # ... op.drop_table(...) ...

    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE;")
```

### Pattern 5: Alembic env.py for TimescaleDB + Async

**What:** Alembic env.py configured to (a) filter out TimescaleDB auto-created indexes and internal schemas, (b) support both sync CLI execution (via psycopg2) and potential async programmatic execution, and (c) use the shared naming convention from Base.

**When to use:** Always -- this is the env.py configuration for the project.

**Critical details:**
- Use `include_name` to exclude TimescaleDB auto-created indexes (pattern: `{table}_{time_col}_idx`)
- Use `include_name` to exclude TimescaleDB internal schemas
- Target metadata must be `Base.metadata` from the models
- Use `postgresql+psycopg2://` connection string for Alembic (NOT asyncpg)

**Example:**
```python
# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from src.core.models.base import Base
# Import all models so they register with Base.metadata
from src.core.models import (  # noqa: F401
    instruments, series_metadata, data_sources,
    market_data, macro_series, curves,
    flow_data, fiscal_data, vol_surfaces, signals,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# TimescaleDB schemas to exclude from autogenerate
TIMESCALEDB_SCHEMAS = {
    "_timescaledb_catalog",
    "_timescaledb_internal",
    "_timescaledb_cache",
    "_timescaledb_config",
    "timescaledb_information",
    "timescaledb_experimental",
}

# TimescaleDB auto-creates indexes like "{table}_{time_col}_idx"
# These must be excluded or Alembic autogenerate will try to drop them
TIMESCALEDB_INDEX_SUFFIXES = ("_idx",)
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

def run_migrations_offline() -> None:
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
```

### Anti-Patterns to Avoid

- **Using `sqlalchemy-timescaledb` dialect:** Unmaintained (no updates in 12+ months). Use raw SQL via `op.execute()` instead.
- **Auto-increment-only primary keys on hypertables:** TimescaleDB requires time column in all unique indexes. Use composite PKs.
- **Using `TIMESTAMP` without timezone:** Always use `DateTime(timezone=True)` (maps to TIMESTAMPTZ). Per Pitfall 6 from PITFALLS.md.
- **Enabling compression before backfill:** Configure policies in Phase 1, but ensure `compress_after` delays are generous enough that no data gets compressed until after Phase 4 backfill completes.
- **Running Alembic with asyncpg driver:** Alembic's CLI uses sync execution. Use `postgresql+psycopg2://` in alembic.ini. The async engine (`postgresql+asyncpg://`) is for application code only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Database migrations | Custom DDL scripts | Alembic with `op.execute()` for TimescaleDB | Migration versioning, rollbacks, autogenerate for schema drift detection |
| Configuration management | Custom env parsing | pydantic-settings with BaseSettings | Type validation, .env support, nested models, environment variable precedence |
| Connection pooling | Manual connection tracking | SQLAlchemy engine pool + Redis ConnectionPool | Both have battle-tested pool implementations with health checks |
| Constraint naming | Manual constraint names | SQLAlchemy MetaData naming_convention | Consistent names across 10 tables; Alembic needs predictable names |
| Redis async support | Separate aioredis library | redis-py 5.x `redis.asyncio` | aioredis was absorbed into redis-py; single library for sync and async |
| TimescaleDB hypertable creation | ORM-level abstraction | Raw SQL in Alembic `op.execute()` | No maintained Python abstraction exists; raw SQL is explicit and documented |

**Key insight:** The TimescaleDB-specific parts of this stack (hypertable creation, compression policies, extension enablement) have no reliable Python abstraction. Raw SQL in migrations is the standard approach used by the TimescaleDB community and is explicitly documented in official resources.

## Common Pitfalls

### Pitfall 1: Alembic Autogenerate Drops TimescaleDB Indexes (Discussion #1465)

**What goes wrong:** When TimescaleDB converts a table to a hypertable via `create_hypertable()`, it automatically creates an index on the time column (e.g., `market_data_timestamp_idx`). Since Alembic did not create this index, every subsequent `alembic revision --autogenerate` produces a migration that drops it.

**Why it happens:** Alembic compares its model metadata (which has no record of this index) against the database (which has the index). The diff shows an "extra" index that should be removed.

**How to avoid:** Configure `include_name` in `env.py` to exclude known TimescaleDB auto-created index names. See the env.py pattern above. The index naming pattern is `{tablename}_{time_column}_idx`.

**Warning signs:** Autogenerate keeps producing `op.drop_index('{table}_{col}_idx')` migrations that you have to manually delete.

**Confidence:** HIGH -- documented in official Alembic repo, Discussion #1465.

### Pitfall 2: Unique Constraints Must Include Time Column

**What goes wrong:** You define a unique constraint or primary key on a hypertable without including the time partitioning column. `create_hypertable()` fails with: `ERROR: cannot create a unique index without the column "{time_col}" (used in partitioning)`.

**Why it happens:** TimescaleDB partitions data into chunks by time. Enforcing uniqueness across chunks without the partition key would require scanning all chunks -- a fundamental architectural limitation.

**How to avoid:** Every unique constraint and primary key on hypertable models MUST include the time column. For this project, use composite PKs like `(id, observation_date)`. The `ON CONFLICT` clause in upserts should reference the natural key constraint which also includes the time column.

**Warning signs:** Migration fails when `create_hypertable()` is called after table creation.

**Confidence:** HIGH -- documented in TimescaleDB official docs ("Enforce constraints with unique indexes").

### Pitfall 3: TimescaleDB Internal Schemas Break Alembic Reflection

**What goes wrong:** When using `include_schemas=True` in Alembic (or when Alembic reflects the database), TimescaleDB's internal schemas (`_timescaledb_catalog`, `_timescaledb_internal`, etc.) contain tables without standard columns, causing `NoSuchTableError` exceptions.

**Why it happens:** TimescaleDB creates several internal schemas when the extension is installed. These contain metadata tables that don't conform to standard PostgreSQL table structure.

**How to avoid:** Use `include_name` to filter out all TimescaleDB schemas at the reflection stage (before Alembic tries to inspect them). See the `TIMESCALEDB_SCHEMAS` set in the env.py pattern.

**Warning signs:** `sqlalchemy.exc.NoSuchTableError: cache_inval_hypertable` during autogenerate.

**Confidence:** HIGH -- documented in Alembic Issue #733.

### Pitfall 4: Alembic Uses Sync Driver, Application Uses Async

**What goes wrong:** Developer puts `postgresql+asyncpg://` in `alembic.ini`. Alembic CLI hangs or crashes because it does not natively support async execution.

**Why it happens:** Alembic's CLI and migration runner are synchronous. While there IS a cookbook pattern for running Alembic with async engines programmatically, the standard CLI requires a sync driver.

**How to avoid:** Use TWO connection strings: `postgresql+psycopg2://` in `alembic.ini` for migrations, `postgresql+asyncpg://` in application config for runtime. Both point to the same database. Pydantic-settings can construct both URLs from the same host/port/db/user/password components.

**Warning signs:** Alembic commands hang indefinitely or raise event loop errors.

**Confidence:** HIGH -- documented in Alembic Cookbook ("Using asyncio with Alembic").

### Pitfall 5: Redis Client Lifecycle in Async Context

**What goes wrong:** Developer creates Redis client inside an `async with` block or uses `Redis.from_pool()`, then the client/pool gets closed prematurely when the context exits. Subsequent requests fail with connection errors.

**Why it happens:** `redis.asyncio.Redis` has an internal usage counter. When using `async with` or `from_pool()`, exiting the context decrements the counter and may close the pool.

**How to avoid:** Create the Redis client as a module-level singleton. Pass `connection_pool=` parameter (not `from_pool()`) so the pool lifecycle is managed independently. Close explicitly in application shutdown (e.g., FastAPI lifespan `shutdown` event).

**Warning signs:** Intermittent `ConnectionError` from Redis after the first few requests succeed.

**Confidence:** HIGH -- documented in redis-py asyncio examples.

## Code Examples

### Docker Compose (Full Stack)

```yaml
# docker-compose.yml
version: "3.9"

services:
  timescaledb:
    image: timescale/timescaledb:2.18.0-pg16
    container_name: macro_timescaledb
    environment:
      POSTGRES_DB: macro_trading
      POSTGRES_USER: macro_user
      POSTGRES_PASSWORD: macro_pass
    ports:
      - "5432:5432"
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U macro_user -d macro_trading"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: macro_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  mongodb:
    image: mongo:8.0
    container_name: macro_mongodb
    environment:
      MONGO_INITDB_ROOT_USERNAME: macro_user
      MONGO_INITDB_ROOT_PASSWORD: macro_pass
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s
    restart: unless-stopped

  kafka:
    image: confluentinc/cp-kafka:7.8.0
    container_name: macro_kafka
    ports:
      - "9092:9092"
    environment:
      # KRaft mode (no Zookeeper)
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      # Listeners
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      # Single-broker settings
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      # Cluster ID (pre-generated for reproducibility)
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
    volumes:
      - kafka_data:/var/lib/kafka/data
    healthcheck:
      test: ["CMD-SHELL", "kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1"]
      interval: 15s
      timeout: 10s
      retries: 5
      start_period: 30s
    profiles:
      - full  # Only starts with: docker compose --profile full up
    restart: unless-stopped

  minio:
    image: quay.io/minio/minio:RELEASE.2025-02-18T16-25-55Z
    container_name: macro_minio
    ports:
      - "9000:9000"
      - "9001:9001"  # Console
    environment:
      MINIO_ROOT_USER: minio_user
      MINIO_ROOT_PASSWORD: minio_pass
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  timescaledb_data:
  redis_data:
  mongodb_data:
  kafka_data:
  minio_data:
```

**Key decisions in this Docker Compose:**
1. **Kafka uses `profiles: [full]`** -- per ARCHITECTURE.md Anti-Pattern 4, Kafka is not needed for Phase 0-4 batch ingestion. It starts only when explicitly requested (`docker compose --profile full up`). This satisfies INFRA-01 (all services can run healthy) while avoiding premature Kafka complexity.
2. **All services have health checks** with appropriate `start_period` for slow-starting services.
3. **Named volumes** for data persistence across container restarts.
4. **Pin exact versions** -- never use `latest` tags.

### Pydantic Settings Configuration

```python
# src/core/config.py
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # Project
    project_name: str = "Macro Trading"
    debug: bool = False

    # TimescaleDB / PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "macro_trading"
    postgres_user: str = "macro_user"
    postgres_password: str = "macro_pass"

    # SQLAlchemy pool settings
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_pre_ping: bool = True

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_max_connections: int = 50

    # MongoDB
    mongo_host: str = "localhost"
    mongo_port: int = 27017
    mongo_user: str = "macro_user"
    mongo_password: str = "macro_pass"
    mongo_db: str = "macro_trading"

    # MinIO
    minio_host: str = "localhost"
    minio_port: int = 9000
    minio_access_key: str = "minio_user"
    minio_secret_key: str = "minio_pass"
    minio_bucket: str = "macro-data"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"

    # API Keys (external data sources)
    fred_api_key: str = ""

    @computed_field
    @property
    def async_database_url(self) -> str:
        """Async connection string for asyncpg."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """Sync connection string for psycopg2 (used by Alembic)."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        """Redis connection URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @computed_field
    @property
    def mongo_url(self) -> str:
        """MongoDB connection URL."""
        return (
            f"mongodb://{self.mongo_user}:{self.mongo_password}"
            f"@{self.mongo_host}:{self.mongo_port}/{self.mongo_db}"
            f"?authSource=admin"
        )


# Singleton instance
settings = Settings()
```

### Database Engine Setup

```python
# src/core/database.py
from collections.abc import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

# Async engine (for application runtime -- asyncpg)
async_engine = create_async_engine(
    settings.async_database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=settings.db_pool_pre_ping,
    echo=settings.debug,
)

# Async session factory
async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)

# Sync engine (for Alembic, seeds, one-off scripts -- psycopg2)
sync_engine = create_engine(
    settings.sync_database_url,
    pool_size=5,
    pool_pre_ping=True,
    echo=settings.debug,
)

# Sync session factory
sync_session_factory = sessionmaker(
    sync_engine,
    autoflush=False,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injector for async database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_sync_session() -> Session:
    """Get a sync session for scripts and migrations."""
    return sync_session_factory()
```

### Redis Client Singleton

```python
# src/core/redis.py
import redis.asyncio as aioredis
from .config import settings

# Connection pool (created once, shared across all Redis operations)
_redis_pool: aioredis.ConnectionPool | None = None
_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get the singleton async Redis client."""
    global _redis_pool, _redis_client
    if _redis_client is None:
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
        )
        _redis_client = aioredis.Redis(connection_pool=_redis_pool)
    return _redis_client


async def close_redis() -> None:
    """Close Redis client and pool. Call during application shutdown."""
    global _redis_pool, _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
```

### .env.example Template

```bash
# .env.example — Copy to .env and fill in values

# TimescaleDB / PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=macro_trading
POSTGRES_USER=macro_user
POSTGRES_PASSWORD=macro_pass

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# MongoDB
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_USER=macro_user
MONGO_PASSWORD=macro_pass
MONGO_DB=macro_trading

# MinIO
MINIO_HOST=localhost
MINIO_PORT=9000
MINIO_ACCESS_KEY=minio_user
MINIO_SECRET_KEY=minio_pass
MINIO_BUCKET=macro-data

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# External API Keys
FRED_API_KEY=

# Application
DEBUG=false
```

## Schema Design (10 Tables)

### 3 Metadata Tables (Regular PostgreSQL)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `instruments` | Registry of tradeable instruments (FX, indices, commodities, ETFs) | id, ticker, name, asset_class, country, currency, exchange, is_active |
| `series_metadata` | Registry of all 200+ data series with source info, frequency, locale | id, source_id, series_code, name, frequency, country, unit, decimal_separator, date_format, is_revisable, release_timezone |
| `data_sources` | Registry of external data providers (BCB SGS, FRED, Yahoo, etc.) | id, name, base_url, auth_type, rate_limit_per_minute, default_locale, notes |

**Rationale for `data_sources` as the 3rd metadata table:** It normalizes provider information out of `series_metadata`. Each series references its source. This enables per-source rate limiting, health monitoring, and locale handling. When a source changes its base URL or rate limit, it is updated in one place rather than across 50+ series rows.

### 7 Hypertables (TimescaleDB)

| Table | Time Column | Chunk Interval | Segmentby | Compress After | Key Columns |
|-------|-------------|---------------|-----------|----------------|-------------|
| `market_data` | timestamp (TIMESTAMPTZ) | 1 month | instrument_id | 30 days | instrument_id, timestamp, frequency, open, high, low, close, volume, adjusted_close |
| `macro_series` | observation_date (DATE) | 1 year | series_id | 90 days | series_id, observation_date, value, release_time (TIMESTAMPTZ), revision_number, source |
| `curves` | curve_date (DATE) | 3 months | curve_id | 90 days | curve_id, curve_date, tenor_days, tenor_label, rate, curve_type, source |
| `flow_data` | observation_date (DATE) | 1 year | series_id | 90 days | series_id, observation_date, value, flow_type, unit, release_time (TIMESTAMPTZ) |
| `fiscal_data` | observation_date (DATE) | 1 year | series_id | 180 days | series_id, observation_date, value, fiscal_metric, unit, release_time (TIMESTAMPTZ) |
| `vol_surfaces` | surface_date (DATE) | 1 year | instrument_id | 90 days | instrument_id, surface_date, delta, tenor_days, implied_vol, call_put |
| `signals` | signal_date (DATE) | 1 year | signal_type | 90 days | signal_type, signal_date, instrument_id, value, confidence, metadata_json |

### Unique Constraints (for ON CONFLICT DO NOTHING)

Every hypertable has a natural key constraint that includes the time column:

| Table | Natural Key (Unique Constraint) |
|-------|-------------------------------|
| `market_data` | (instrument_id, timestamp, frequency) |
| `macro_series` | (series_id, observation_date, revision_number) |
| `curves` | (curve_id, curve_date, tenor_days) |
| `flow_data` | (series_id, observation_date, flow_type) |
| `fiscal_data` | (series_id, observation_date, fiscal_metric) |
| `vol_surfaces` | (instrument_id, surface_date, delta, tenor_days) |
| `signals` | (signal_type, signal_date, instrument_id) |

These constraints enable idempotent `INSERT ... ON CONFLICT DO NOTHING` patterns across all connectors.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `declarative_base()` function | `class Base(DeclarativeBase)` | SQLAlchemy 2.0 (Jan 2023) | Better type checking, IDE support, cleaner inheritance |
| `Column()` with `String`, etc. | `Mapped[str] = mapped_column()` | SQLAlchemy 2.0 | Full type hint support, `Optional` maps to nullable |
| `aioredis` separate package | `redis.asyncio` in redis-py 5.x | redis-py 5.0 (2023) | Single package for sync and async; aioredis merged in |
| Zookeeper + Kafka | KRaft mode Kafka | Kafka 3.3 (production-ready, 2022) | Eliminates Zookeeper dependency; simpler deployment |
| `mongo` shell | `mongosh` | MongoDB 5.0 (2021), `mongo` removed in 6.0 | Health checks must use `mongosh` not `mongo` |
| `curl` for MinIO health | `mc ready local` | MinIO 2024+ | `curl` removed from MinIO images; `mc` is bundled |
| TimescaleDB `create_hypertable()` old API | `create_hypertable()` with `by_range()` new API | TimescaleDB 2.13 | Both APIs work; old API is simpler for our use case |

**Deprecated/outdated:**
- `aioredis` package: Merged into redis-py; do not install separately
- `declarative_base()`: Still works but loses type checking benefits
- `sqlalchemy-timescaledb` dialect: Unmaintained; use raw SQL
- Zookeeper for Kafka: Deprecated in 3.5, removal planned in 4.0

## Open Questions

1. **Exact TimescaleDB 2.18.0 image tag availability**
   - What we know: `timescale/timescaledb:latest-pg16` exists; version-specific tags like `2.18.0-pg16` are published
   - What's unclear: The exact latest stable tag at time of implementation
   - Recommendation: Check Docker Hub at implementation time; pin the latest stable `2.x.x-pg16` tag

2. **Alembic autogenerate precision with 7 hypertables**
   - What we know: The `include_name` filter handles known index names
   - What's unclear: Whether TimescaleDB creates additional internal objects beyond the time column index that would confuse autogenerate
   - Recommendation: After initial migration, run `alembic revision --autogenerate` and verify it produces an empty migration. If not, add additional exclusions.

3. **Foreign key from hypertable to metadata table**
   - What we know: TimescaleDB has limitations on foreign keys FROM hypertables (Issue #138). Foreign keys TO hypertables are not supported, but FK FROM hypertables to regular tables works.
   - What's unclear: Whether there are performance implications for FK constraints on hypertables with millions of rows
   - Recommendation: Define FKs in the model for ORM integrity, but consider dropping them in production if they cause performance issues during bulk inserts. The `ON CONFLICT DO NOTHING` pattern provides data integrity regardless.

## Sources

### Primary (HIGH confidence)
- [Alembic Discussion #1465](https://github.com/sqlalchemy/alembic/discussions/1465) -- TimescaleDB hypertable index conflict and `include_name` solution
- [Alembic Issue #733](https://github.com/sqlalchemy/alembic/issues/733) -- TimescaleDB internal schema reflection errors
- [Alembic Cookbook: Using asyncio](https://alembic.sqlalchemy.org/en/latest/cookbook.html) -- Async migration pattern
- [SQLAlchemy 2.0 ORM Mapped Class Overview](https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html) -- DeclarativeBase, Mapped[], mapped_column
- [TimescaleDB: Enforce constraints with unique indexes](https://www.tigerdata.com/docs/use-timescale/latest/hypertables/hypertables-and-unique-indexes) -- Unique constraint must include time column
- [TimescaleDB: create_hypertable API](https://docs.timescale.com/api/latest/hypertable/create_hypertable/) -- chunk_time_interval, if_not_exists
- [TimescaleDB: Compression documentation](https://docs.timescale.com/use-timescale/latest/compression/) -- segmentby, orderby, add_compression_policy
- [redis-py asyncio examples](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html) -- Async client, connection pool lifecycle
- [redis-py connections docs](https://redis.readthedocs.io/en/stable/connections.html) -- ConnectionPool, from_pool vs connection_pool param
- [Pydantic Settings Management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) -- BaseSettings, SettingsConfigDict, env_nested_delimiter
- [MinIO GitHub: Health check discussion](https://github.com/minio/minio/discussions/18375) -- `mc ready local` replaces `curl`

### Secondary (MEDIUM confidence)
- [FastAPI + SQLAlchemy 2.0 patterns](https://dev-faizan.medium.com/fastapi-sqlalchemy-2-0-modern-async-database-patterns-7879d39b6843) -- Async engine/session patterns verified against official docs
- [Kafka KRaft Docker Compose 2025](https://theexceptioncatcher.com/2025/06/kafka-in-2025-a-clean-docker-compose-setup-without-zookeeper/) -- KRaft env vars, single-broker config
- [Confluent: How to run Kafka locally with Docker](https://developer.confluent.io/confluent-tutorials/kafka-on-docker/) -- Official Confluent KRaft tutorial
- [Running Apache Kafka KRaft on Docker (Instaclustr)](https://www.instaclustr.com/education/apache-spark/running-apache-kafka-kraft-on-docker-tutorial-and-best-practices/) -- KRaft best practices
- [MongoDB Docker health check with mongosh](https://gist.github.com/maitrungduc1410/f2f7b34d2e736912471b006c6dba17e5) -- `mongosh` replaces `mongo`
- [Redis Docker Compose health check](https://www.strangebuzz.com/en/snippets/redis-service-docker-compose-healthcheck) -- `redis-cli ping` pattern
- [TimescaleDB Docker Compose setup](https://compositecode.blog/2025/03/28/setup-timescaledb-with-docker-compose-a-step-by-step-guide/) -- pg_isready health check
- [Snyk: sqlalchemy-timescaledb health analysis](https://snyk.io/advisor/python/sqlalchemy-timescaledb) -- Package inactive/unmaintained

### Tertiary (LOW confidence)
- [timescaledb PyPI package (v0.0.4)](https://pypi.org/project/timescaledb/) -- New alternative to sqlalchemy-timescaledb; too early/beta to recommend (v0.0.4, March 2025)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries are well-documented, versions verified against PyPI/Docker Hub
- Architecture: HIGH -- Patterns derived from official SQLAlchemy 2.0 docs and Alembic cookbook, cross-verified
- Pitfalls: HIGH -- All 5 pitfalls documented in official repos (Alembic Discussion #1465, Issue #733, TimescaleDB docs, redis-py docs)
- Docker Compose: HIGH -- Health check patterns verified against official docs for each service (TimescaleDB, Redis, MongoDB, MinIO, Kafka)
- Schema design: MEDIUM -- Schema is sound but the exact column set for each table may need refinement during implementation

**Research date:** 2026-02-19
**Valid until:** 2026-04-19 (60 days -- infrastructure stack is stable; library versions may increment but patterns hold)
