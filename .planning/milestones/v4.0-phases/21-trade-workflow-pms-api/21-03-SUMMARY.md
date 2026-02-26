---
phase: 21-trade-workflow-pms-api
plan: 03
subsystem: api
tags: [fastapi, pms, journal, testclient, integration-tests, decision-journal]

# Dependency graph
requires:
  - phase: 21-trade-workflow-pms-api (plans 01-02)
    provides: TradeWorkflowService, PositionManager, PMS schemas, portfolio/trades routers
provides:
  - 4 Decision Journal API endpoints (list, detail, outcome, stats)
  - Complete PMS API surface (20+ endpoints across 3 routers)
  - 12 FastAPI TestClient integration tests for full PMS workflow
affects: [phase-22, phase-23, phase-24, phase-25, phase-26]

# Tech tracking
tech-stack:
  added: [httpx (TestClient dependency)]
  patterns: [FastAPI TestClient with module-level singleton reset for test isolation]

key-files:
  created:
    - src/api/routes/pms_journal.py
    - tests/test_pms/test_pms_api.py
  modified:
    - src/api/main.py

key-decisions:
  - "Journal stats/decision-analysis endpoint placed BEFORE /{entry_id} to avoid FastAPI path conflict"
  - "Test fixture injects shared TradeWorkflowService across all 3 router module singletons for state coherence"

patterns-established:
  - "TestClient singleton reset pattern: set _workflow on each router module, yield client, reset to None"

requirements-completed: [PMS-API-04, PMS-TW-04, PMS-TW-05]

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 21 Plan 03: PMS Journal Router & API Integration Tests Summary

**Decision Journal router with 4 endpoints (list/detail/outcome/stats), all 3 PMS routers registered in main.py, and 12 FastAPI TestClient integration tests validating full PMS workflow**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24T03:38:09Z
- **Completed:** 2026-02-24T03:42:03Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Decision Journal router with 4 endpoints: filtered+paginated listing, single entry detail, outcome recording via linked NOTE entries, and decision analysis statistics
- All 3 PMS routers (Portfolio, Trade Blotter, Decision Journal) registered in main.py with /api/v1 prefix and Swagger tags
- 12 FastAPI integration tests covering the complete PMS lifecycle: empty book, open/close positions, validation errors, proposal generation/approval/rejection, journal queries, journal stats, P&L summary, mark-to-market

## Task Commits

Each task was committed atomically:

1. **Task 1: PMS Journal router + main.py registration** - `fa950b4` (feat)
2. **Task 2: FastAPI TestClient integration tests** - `54950f7` (test)

## Files Created/Modified
- `src/api/routes/pms_journal.py` - 4 journal endpoints: list with filtering/pagination, detail, outcome recording, decision statistics
- `src/api/main.py` - Updated with 3 PMS router registrations and 3 Swagger tags
- `tests/test_pms/test_pms_api.py` - 12 integration tests using FastAPI TestClient with in-memory PMS state

## Decisions Made
- Journal stats endpoint (`/stats/decision-analysis`) defined before `/{entry_id}` in route order to prevent FastAPI treating "stats" as an entry_id path parameter
- Test fixture creates a single fresh TradeWorkflowService and injects it into all 3 router module singletons (_workflow) for coherent shared state across portfolio/trades/journal endpoints
- Installed httpx as TestClient runtime dependency (required by starlette.testclient)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed httpx for TestClient**
- **Found during:** Task 2 (integration tests)
- **Issue:** `starlette.testclient` requires httpx which was not installed
- **Fix:** `pip install httpx`
- **Verification:** All 12 tests pass

**2. [Rule 1 - Bug] Fixed test_journal_stats proposal ID targeting**
- **Found during:** Task 2 (integration tests)
- **Issue:** Test tried to reject proposal_id=1, but discretionary trade already auto-approved it. The generated proposals start at ID 2.
- **Fix:** Dynamically read generated proposal ID from response before rejecting
- **Verification:** test_journal_stats passes with correct counts

**3. [Rule 1 - Bug] Fixed MTM endpoint path in test**
- **Found during:** Task 2 (integration tests)
- **Issue:** Test used /api/v1/pms/book/mtm but actual route is /api/v1/pms/mtm
- **Fix:** Corrected URL path in test_mtm_endpoint
- **Verification:** test_mtm_endpoint passes

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 bug fixes)
**Impact on plan:** All fixes necessary for test correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 21 complete: TradeWorkflowService, PositionManager, 20+ PMS API endpoints, 74 passing tests
- PMS API ready for frontend consumption in Phases 23-26
- All PMS tests (unit + integration) pass: 74 total

## Self-Check: PASSED

- FOUND: src/api/routes/pms_journal.py
- FOUND: tests/test_pms/test_pms_api.py
- FOUND: 21-03-SUMMARY.md
- FOUND: fa950b4 (Task 1 commit)
- FOUND: 54950f7 (Task 2 commit)

---
*Phase: 21-trade-workflow-pms-api*
*Completed: 2026-02-24*
