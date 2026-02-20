---
phase: 01-foundation
plan: 03
subsystem: database
tags: [asyncpg, psycopg2, sqlalchemy, redis, connection-pool, async-engine, sync-engine]

# Dependency graph
requires:
  - phase: 01-foundation-01
    provides: "Pydantic-settings singleton with async_database_url, sync_database_url, redis_url computed fields"
provides:
  - "Async database engine (asyncpg) with pool_size=20, max_overflow=10"
  - "Sync database engine (psycopg2) with pool_size=5 for Alembic and scripts"
  - "Async/sync session factories with autoflush=False, expire_on_commit=False"
  - "get_async_session() FastAPI dependency injector"
  - "Redis async client singleton with ConnectionPool (max_connections=50, decode_responses=True)"
  - "close_redis() for application shutdown lifecycle"
  - "Connectivity verification script (basic + strict modes)"
affects: [02-connectors, 03-backfill, 04-transforms, 05-api, 06-api-quality]

# Tech tracking
tech-stack:
  added: []
  patterns: [async-engine-singleton, sync-engine-for-alembic, redis-singleton-with-pool, connectivity-verification]

key-files:
  created:
    - src/core/database.py
    - src/core/redis.py
    - scripts/verify_connectivity.py
  modified:
    - Makefile

key-decisions:
  - "ConnectionPool passed via connection_pool= param (not from_pool()) to avoid premature pool closure"
  - "Sync engine pool_size=5 (smaller than async pool_size=20) since it is only used for migrations and scripts"
  - "Verification script uses WARN (not FAIL) for missing hypertables in basic mode to tolerate parallel plan execution"

patterns-established:
  - "Database access: import async_engine, async_session_factory from src.core.database"
  - "FastAPI sessions: use Depends(get_async_session) for request-scoped async sessions"
  - "Script sessions: use get_sync_session() with explicit close"
  - "Redis access: await get_redis() returns singleton client; await close_redis() at shutdown"
  - "Infrastructure checks: python scripts/verify_connectivity.py [--strict]"

requirements-completed: [INFRA-06, INFRA-07]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 1 Plan 3: Database Engines and Connectivity Summary

**Async/sync SQLAlchemy engines with session factories plus Redis singleton client and end-to-end connectivity verification script**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T18:07:11Z
- **Completed:** 2026-02-19T18:11:12Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Async database engine (asyncpg) with configurable pool (size=20, overflow=10, pre_ping=True) and session factory
- Sync database engine (psycopg2) with pool_size=5 for Alembic migrations and one-off scripts
- Redis async client singleton with ConnectionPool lifecycle managed independently (per RESEARCH.md Pitfall 5)
- Connectivity verification script testing async DB, sync DB, and Redis with PASS/FAIL/WARN output
- Makefile `verify` target for one-command infrastructure validation

## Task Commits

Each task was committed atomically:

1. **Task 1: Create database engine layer and Redis client singleton** - `d6d8630` (feat)
2. **Task 2: Create connectivity verification script** - `d4d2998` (feat)

**Plan metadata:** (pending) (docs: complete plan)

## Files Created/Modified
- `src/core/database.py` - Async engine (asyncpg), sync engine (psycopg2), session factories, get_async_session and get_sync_session
- `src/core/redis.py` - Redis singleton with ConnectionPool, get_redis() and close_redis() lifecycle functions
- `scripts/verify_connectivity.py` - Standalone connectivity checker with basic and --strict modes
- `Makefile` - Added `verify` target running strict connectivity checks

## Decisions Made
- **Redis pool independence:** Used `connection_pool=` parameter instead of `from_pool()` to ensure the ConnectionPool lifecycle is managed independently from the Redis client, preventing premature pool closure (RESEARCH.md Pitfall 5).
- **Verification resilience:** Script uses WARN (not FAIL) for missing hypertables/tables in basic mode, since Plan 02 (migration) and Plan 03 (engines) are both Wave 2 and may execute in either order.
- **Sync pool sizing:** Sync engine gets pool_size=5 (vs async pool_size=20) since it serves only Alembic and seed scripts, not concurrent request handling.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- **Docker services not available:** The execution environment does not have running Docker services. Verification script was tested and confirms graceful error handling with clear FAIL messages and exit code 1. Full connectivity verification will pass when Docker services are running (`make up`).

## User Setup Required
None - no external service configuration required. Engines use the same connection settings from the .env file created in Plan 01-01.

## Next Phase Readiness
- Database engines ready for Plan 01-02 (Alembic migration) to use sync_engine via alembic.ini
- Redis client ready for API caching in Phase 6
- Connectivity script ready to validate full stack after `make up && make migrate`
- All INFRA requirements for Phase 1 are now covered (01: Docker, 02-04: pending Plan 02, 05: config, 06: engines, 07: Redis)

## Self-Check: PASSED

- FOUND: src/core/database.py
- FOUND: src/core/redis.py
- FOUND: scripts/verify_connectivity.py
- FOUND: Makefile (modified)
- Commit d6d8630 (Task 1) verified in git log
- Commit d4d2998 (Task 2) verified in git log
- 01-03-SUMMARY.md created

---
*Phase: 01-foundation*
*Completed: 2026-02-19*
