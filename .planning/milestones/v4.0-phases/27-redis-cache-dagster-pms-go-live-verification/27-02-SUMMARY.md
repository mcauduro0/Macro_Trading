---
phase: 27-redis-cache-dagster-pms-go-live-verification
plan: 02
subsystem: orchestration
tags: [dagster, pms, redis, cache-warming, scheduling, cron]

# Dependency graph
requires:
  - phase: 27-01
    provides: "PMSCache with tiered TTLs and write-through helpers"
  - phase: 20
    provides: "PositionManager, MarkToMarketService"
  - phase: 21
    provides: "TradeWorkflowService, MorningPackService"
  - phase: 22
    provides: "PerformanceAttributionEngine"
  - phase: 18
    provides: "Dagster orchestration framework with assets_bronze pattern"
provides:
  - "4 PMS Dagster assets (MTM, proposals, morning pack, attribution) with Redis cache warming"
  - "pms_eod_job: EOD pipeline at 21:00 UTC (MTM + attribution)"
  - "pms_preopen_job: pre-open pipeline at 09:30 UTC (MTM + proposals + morning pack)"
  - "26 total registered Dagster assets across 8 layers"
affects: [27-03, 27-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [dagster-pms-assets, redis-cache-warming-after-persistence, dual-schedule-eod-preopen]

key-files:
  created:
    - src/orchestration/assets_pms.py
  modified:
    - src/orchestration/definitions.py

key-decisions:
  - "PMS assets use sync wrappers with asyncio.run() for Redis cache warming (matching assets_bronze pattern)"
  - "Pre-open schedule offset 30 min from daily_pipeline (09:30 vs 09:00 UTC) to avoid contention"
  - "Attribution is EOD-only; pre-open job includes MTM + proposals + morning pack (3 assets)"

patterns-established:
  - "PMS asset cache warming: each asset warms Redis after completing its work via asyncio.run()"
  - "Dual-schedule PMS: EOD for MTM+attribution, pre-open for MTM+proposals+morning_pack"

requirements-completed: [PMS-DAG-01, PMS-DAG-02]

# Metrics
duration: 3min
completed: 2026-02-26
---

# Phase 27 Plan 02: Dagster PMS Pipeline Summary

**4 PMS Dagster assets with Redis cache warming, dual schedules (EOD 21:00 UTC + pre-open 09:30 UTC), and dependency-ordered execution**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T23:57:07Z
- **Completed:** 2026-02-26T00:01:03Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created 4 PMS Dagster asset definitions (MTM, trade proposals, morning pack, attribution) with correct dependency chain
- Each asset warms Redis cache after completing its work for instant dashboard data
- Registered EOD and pre-open schedules with pre-open offset 30 min from daily pipeline
- Updated Definitions to 26 total assets, 4 jobs, 3 schedules

## Task Commits

Each task was committed atomically:

1. **Task 1: PMS Dagster assets with cache warming** - `c4c1d26` (feat)
2. **Task 2: Register PMS assets in Definitions with two scheduled jobs** - `87a74ec` (feat)

## Files Created/Modified
- `src/orchestration/assets_pms.py` - 4 PMS Dagster asset definitions with Redis cache warming
- `src/orchestration/definitions.py` - Updated with PMS imports, jobs, and schedules (26 assets total)

## Decisions Made
- PMS assets use sync wrappers with asyncio.run() for Redis cache warming, matching the existing pattern from assets_bronze.py
- Pre-open schedule at 09:30 UTC, 30 minutes after the daily_pipeline_schedule at 09:00 UTC, to avoid simultaneous execution contention
- Attribution is EOD-only per locked decision; pre-open job selects only 3 assets (MTM + proposals + morning pack)
- Trade proposals pass empty signals list to generate_proposals_from_signals, relying on internal signal sources

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Dagster is not installed in the local Python environment (runs in Docker container). Verification commands that require dagster imports cannot execute locally. This is consistent with all existing orchestration modules (assets_bronze.py etc.) which also fail to import without dagster. Syntax validation confirmed both files parse correctly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- PMS pipeline assets ready for Dagster UI visualization under pms group
- EOD and pre-open schedules registered and ready for activation
- Cache warming integrated for instant dashboard data after pipeline runs

## Self-Check: PASSED

- [x] src/orchestration/assets_pms.py exists
- [x] src/orchestration/definitions.py exists
- [x] 27-02-SUMMARY.md exists
- [x] Commit c4c1d26 found in git log
- [x] Commit 87a74ec found in git log

---
*Phase: 27-redis-cache-dagster-pms-go-live-verification*
*Completed: 2026-02-26*
