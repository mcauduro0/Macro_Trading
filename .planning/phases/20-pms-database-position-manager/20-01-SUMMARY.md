---
phase: 20-pms-database-position-manager
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, timescaledb, postgresql, orm, hypertable, trigger]

# Dependency graph
requires:
  - phase: 17-portfolio-construction
    provides: "PortfolioStateRecord model, base.py DeclarativeBase, portfolio_state hypertable pattern"
provides:
  - "5 PMS SQLAlchemy models (PortfolioPosition, TradeProposal, DecisionJournal, DailyBriefing, PositionPnLHistory)"
  - "Alembic migration 009 creating 5 tables with TimescaleDB hypertable and immutability trigger"
  - "Model re-exports in src.core.models.__init__.py"
affects: [20-02, 21-trade-workflow, 22-morning-pack, 23-pms-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual notional (BRL primary + USD derived) for cross-currency position tracking"
    - "Full risk snapshot at entry (DV01, delta, convexity, VaR contribution, spread duration)"
    - "SHA256 content_hash on immutable audit log entries"
    - "DB-level immutability trigger (prevent_journal_modification) for decision journal"
    - "Composite PK (id, snapshot_date) for TimescaleDB hypertable compatibility"
    - "Segmentby=position_id compression for position P&L history"

key-files:
  created:
    - src/core/models/pms_models.py
    - alembic/versions/009_create_pms_tables.py
    - tests/test_pms_models.py
  modified:
    - src/core/models/__init__.py

key-decisions:
  - "Models follow Mapped[] type hints pattern consistent with existing portfolio_state.py"
  - "PositionPnLHistory uses 90-day chunk interval with 60-day compression policy"
  - "DecisionJournal immutability enforced at DB level via PostgreSQL trigger on is_locked=TRUE rows"
  - "No FK constraint from position_pnl_history.position_id to portfolio_positions for hypertable compatibility"

patterns-established:
  - "PMS model naming: PortfolioPosition, TradeProposal, DecisionJournal, DailyBriefing, PositionPnLHistory"
  - "JSONB fields for extensible snapshots (market_snapshot, portfolio_snapshot, strategy_weights)"
  - "Immutability via trigger + is_locked flag pattern for audit tables"

requirements-completed: [PMS-DB-01, PMS-DB-02, PMS-DB-03]

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 20 Plan 01: PMS Database Models Summary

**5 PMS SQLAlchemy models with dual BRL/USD notional, full risk snapshot, SHA256 audit journal, TimescaleDB hypertable for P&L history, and DB-level immutability trigger**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24T02:07:19Z
- **Completed:** 2026-02-24T02:11:28Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- 5 PMS SQLAlchemy 2.0 ORM models defined with all columns matching locked decisions (dual notional, risk snapshot, strategy attribution, SHA256 hash, JSONB snapshots)
- Alembic migration 009 creates 5 tables with position_pnl_history as TimescaleDB hypertable (90-day chunks, compress after 60 days, segmentby=position_id)
- DecisionJournal has DB-level immutability trigger preventing UPDATE/DELETE on locked rows
- 27 pytest tests validating all schema definitions without database dependency

## Task Commits

Each task was committed atomically:

1. **Task 1: Create 5 PMS SQLAlchemy models in pms_models.py** - `f91591e` (feat)
2. **Task 2: Create Alembic migration 009 with hypertable and immutability trigger, plus model tests** - `92482eb` (feat)

## Files Created/Modified
- `src/core/models/pms_models.py` - 5 PMS ORM models (PortfolioPosition, TradeProposal, DecisionJournal, DailyBriefing, PositionPnLHistory)
- `alembic/versions/009_create_pms_tables.py` - Migration creating 5 tables, hypertable, compression, immutability trigger
- `tests/test_pms_models.py` - 27 schema-level unit tests for all 5 models
- `src/core/models/__init__.py` - Updated with PMS model re-exports and __all__ list (20 model classes total)

## Decisions Made
- Models follow Mapped[] type hints pattern consistent with existing portfolio_state.py for codebase consistency
- PositionPnLHistory uses 90-day chunk interval (longer than portfolio_state's default) for daily date-based partitioning
- DecisionJournal immutability enforced at DB level via PostgreSQL trigger on is_locked=TRUE rows (strongest guarantee per locked decision)
- No FK constraint from position_pnl_history.position_id to portfolio_positions for TimescaleDB hypertable compatibility (referenced conceptually in model docstring)

## Deviations from Plan

None - plan executed exactly as written. The pms_models.py and __init__.py files already existed from a prior partial execution, so Task 1 verified and committed the existing correct implementation.

## Issues Encountered
- sqlalchemy and pytest packages needed installation (not pre-installed in environment) - resolved with pip install

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 5 PMS models ready for use by PositionManager service (Plan 20-02)
- Migration 009 ready for deployment to TimescaleDB
- Models registered in src.core.models for convenient import throughout codebase
- 27 tests provide regression coverage for schema changes

## Self-Check: PASSED

All 4 claimed files verified to exist on disk. Both task commit hashes (f91591e, 92482eb) verified in git log.

---
*Phase: 20-pms-database-position-manager*
*Completed: 2026-02-24*
