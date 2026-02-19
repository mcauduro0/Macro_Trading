---
phase: 01-foundation
plan: 02
subsystem: database
tags: [sqlalchemy, timescaledb, alembic, orm, hypertables, compression, postgresql]

# Dependency graph
requires:
  - phase: 01-foundation-01
    provides: "Project scaffolding, pydantic-settings config with database URLs, shared enums"
provides:
  - "10 SQLAlchemy 2.0 ORM models (3 metadata + 7 hypertable) with Mapped[] type hints"
  - "Alembic migration creating all tables with TimescaleDB hypertables and compression"
  - "TimescaleDB-aware env.py filtering internal schemas and auto-created indexes"
  - "Base DeclarativeBase with naming conventions for constraint management"
  - "Natural-key UniqueConstraints on all hypertables for ON CONFLICT DO NOTHING"
affects: [02-connectors, 03-backfill, 04-transforms, 05-api]

# Tech tracking
tech-stack:
  added: []
  patterns: [composite-pk-hypertable, natural-key-upsert, timescaledb-index-filtering, declarative-base-naming-conventions]

key-files:
  created:
    - src/core/models/__init__.py
    - src/core/models/base.py
    - src/core/models/instruments.py
    - src/core/models/series_metadata.py
    - src/core/models/data_sources.py
    - src/core/models/market_data.py
    - src/core/models/macro_series.py
    - src/core/models/curves.py
    - src/core/models/flow_data.py
    - src/core/models/fiscal_data.py
    - src/core/models/vol_surfaces.py
    - src/core/models/signals.py
    - alembic.ini
    - alembic/env.py
    - alembic/script.py.mako
    - alembic/versions/001_initial_schema.py
  modified: []

key-decisions:
  - "Raw SQL via op.execute() for all TimescaleDB operations (no dialect dependency)"
  - "Composite primary keys (id, time_col) on all 7 hypertable models per TimescaleDB requirement"
  - "Named constraints following convention dict for Alembic interoperability"
  - "Manual migration rather than autogenerate to control TimescaleDB operation ordering"

patterns-established:
  - "Hypertable model: composite PK with BigInteger id + time column, natural-key UniqueConstraint"
  - "Metadata table: standard auto-increment PK with DateTime(timezone=True) timestamps"
  - "Alembic filtering: include_name function excludes TimescaleDB schemas and auto-indexes"
  - "Migration ordering: extension -> metadata tables -> hypertable tables -> create_hypertable -> compression -> policies"

requirements-completed: [INFRA-02, INFRA-03, INFRA-04]

# Metrics
duration: 6min
completed: 2026-02-19
---

# Phase 1 Plan 2: Database Schema Summary

**10 SQLAlchemy 2.0 ORM models with TimescaleDB hypertables, compression policies, and Alembic migration for the complete Macro Trading schema**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-19T18:07:22Z
- **Completed:** 2026-02-19T18:13:51Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments
- 10 SQLAlchemy 2.0 ORM model classes with Mapped[] type hints: 3 metadata tables (Instrument, DataSource, SeriesMetadata) and 7 hypertable models (MarketData, MacroSeries, CurveData, FlowData, FiscalData, VolSurface, Signal)
- All 7 hypertable models use composite primary keys including the time partitioning column, with natural-key UniqueConstraints for idempotent ON CONFLICT DO NOTHING writes
- MacroSeries includes release_time (TIMESTAMPTZ) for point-in-time correct backtesting
- Alembic initial migration (001_initial_schema) creates all tables, converts 7 to hypertables with correct chunk intervals, enables compression with proper segmentby columns, and sets compression policies
- TimescaleDB-aware env.py filters internal schemas and auto-created indexes to prevent autogenerate drift

## Task Commits

Each task was committed atomically:

1. **Task 1: Create all 10 SQLAlchemy 2.0 ORM models** - `8e0e795` (feat)
2. **Task 2: Create Alembic configuration and initial migration** - `3d1e282` (feat)

**Plan metadata:** (pending) (docs: complete plan)

## Files Created/Modified
- `src/core/models/base.py` - DeclarativeBase with naming conventions for ix, uq, ck, fk, pk
- `src/core/models/instruments.py` - Instrument metadata table (ticker, asset_class, country, currency)
- `src/core/models/data_sources.py` - Data source registry (name, base_url, auth_type, rate_limit)
- `src/core/models/series_metadata.py` - Series registry with UniqueConstraint on (source_id, series_code)
- `src/core/models/market_data.py` - OHLCV hypertable, PK (id, timestamp), segmentby instrument_id
- `src/core/models/macro_series.py` - Macro data hypertable with release_time for PIT correctness
- `src/core/models/curves.py` - Yield curve hypertable, PK (id, curve_date), segmentby curve_id
- `src/core/models/flow_data.py` - Capital flow hypertable, PK (id, observation_date)
- `src/core/models/fiscal_data.py` - Fiscal metrics hypertable, PK (id, observation_date)
- `src/core/models/vol_surfaces.py` - Vol surface hypertable, PK (id, surface_date)
- `src/core/models/signals.py` - Signals hypertable, PK (id, signal_date), nullable instrument_id and series_id FKs
- `src/core/models/__init__.py` - Re-exports Base and all 10 model classes
- `alembic.ini` - Alembic config with psycopg2 sync driver for CLI migrations
- `alembic/env.py` - TimescaleDB-aware env with include_name filtering
- `alembic/script.py.mako` - Standard Alembic migration template
- `alembic/versions/001_initial_schema.py` - Initial migration: 10 tables, 7 hypertables, compression

## Decisions Made
- **Raw SQL for TimescaleDB:** Used `op.execute()` for create_hypertable, compression, and policies. No maintained Python dialect exists (sqlalchemy-timescaledb is abandoned). This is the TimescaleDB community's recommended approach.
- **Manual migration:** Wrote the initial migration by hand rather than autogenerate to control the exact ordering of TimescaleDB operations (extension -> tables -> hypertables -> compression -> policies).
- **Named constraints:** All constraints use explicit names following the naming convention dict, ensuring Alembic can manage them reliably across future migrations.
- **Compression policy delays:** market_data at 30 days (high-frequency), fiscal_data at 180 days (slow-publishing), all others at 90 days. Generous enough that Phase 4 backfill will complete before compression activates.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- **Docker daemon not available:** TimescaleDB is not running in this environment (Docker daemon inactive). The migration was verified via Alembic's offline SQL generation mode (`alembic upgrade head --sql`), which confirmed correct DDL for all 10 tables, 7 hypertable conversions, compression settings, and policies. Actual migration execution will occur when Docker is started with `make up && make migrate`. This matches the same environment limitation documented in Plan 01-01.

## User Setup Required
None - run `make up && make migrate` when Docker is available to apply the migration.

## Next Phase Readiness
- All 10 model classes ready for import by connectors (Phase 2-3)
- Natural-key UniqueConstraints enable `INSERT ... ON CONFLICT DO NOTHING` in all connectors
- MacroSeries.release_time enables point-in-time filtering in transforms (Phase 5)
- Plan 01-03 (async database engine, Redis client) can proceed immediately
- Migration will need to run (`alembic upgrade head`) before any connector writes data

## Self-Check: PASSED

- All 16 created files verified present on disk
- Commit 8e0e795 (Task 1) verified in git log
- Commit 3d1e282 (Task 2) verified in git log
- 01-02-SUMMARY.md verified present

---
*Phase: 01-foundation*
*Completed: 2026-02-19*
