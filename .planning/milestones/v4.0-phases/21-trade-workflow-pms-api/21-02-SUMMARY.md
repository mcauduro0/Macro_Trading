---
phase: 21-trade-workflow-pms-api
plan: 02
subsystem: api
tags: [pydantic, fastapi, rest-api, pms, portfolio, trade-blotter]

# Dependency graph
requires:
  - phase: 21-trade-workflow-pms-api
    provides: "TradeWorkflowService and PositionManager (Plan 01)"
provides:
  - "16 Pydantic v2 request/response schemas for all PMS operations"
  - "PMS Portfolio router with 10 endpoints (book, positions, MTM, P&L)"
  - "PMS Trade Blotter router with 6 endpoints (proposals lifecycle)"
affects: [21-03, 23-dashboard, 24-frontend, 25-live-trading]

# Tech tracking
tech-stack:
  added: [fastapi]
  patterns: [lazy-singleton-workflow, pydantic-v2-response-models, api-envelope-generic]

key-files:
  created:
    - src/api/schemas/__init__.py
    - src/api/schemas/pms_schemas.py
    - src/api/routes/pms_portfolio.py
    - src/api/routes/pms_trades.py
  modified: []

key-decisions:
  - "Schemas and portfolio router already existed from prior prep; only pms_trades.py was created fresh"
  - "Duplicate lazy singleton pattern in pms_trades.py per plan spec (not shared import)"

patterns-established:
  - "Lazy singleton: module-level _workflow = None with _get_workflow() factory for TradeWorkflowService"
  - "Pydantic ConfigDict(from_attributes=True) on all response models for ORM compatibility"
  - "HTTP error mapping: ValueError -> 400/404 based on message content, generic Exception -> 500"

requirements-completed: [PMS-API-01, PMS-API-02, PMS-API-03, PMS-TW-02]

# Metrics
duration: 3min
completed: 2026-02-24
---

# Phase 21 Plan 02: PMS Schemas and API Routers Summary

**16 Pydantic v2 models plus 16 FastAPI endpoints across Portfolio (10) and Trade Blotter (6) routers wrapping TradeWorkflowService**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-24T03:28:48Z
- **Completed:** 2026-02-24T03:31:38Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments
- 16 Pydantic v2 models: 9 request (OpenPosition, ClosePosition, UpdatePrice, MTM, ApproveProposal, RejectProposal, ModifyApprove, GenerateProposals, Outcome) + 6 response (Position, BookSummary, Book, TradeProposal, JournalEntry, PnLPoint) + 1 generic envelope
- PMS Portfolio router: 10 endpoints covering book view, position CRUD, mark-to-market, P&L summary, equity curve, attribution, and monthly heatmap
- PMS Trade Blotter router: 6 endpoints covering proposal listing, detail, approve, reject, modify-approve, and signal-based generation
- All endpoints validated: schema imports pass, route counts match (10 + 6), Pydantic min_length/gt constraints work correctly

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Pydantic schemas and PMS Portfolio + Trades API routers** - `0946df0` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified
- `src/api/schemas/__init__.py` - Package init for Pydantic schemas
- `src/api/schemas/pms_schemas.py` - 16 Pydantic v2 request/response models for all PMS operations
- `src/api/routes/pms_portfolio.py` - 10 portfolio endpoints (book, positions, MTM, P&L analytics)
- `src/api/routes/pms_trades.py` - 6 trade blotter endpoints (proposals CRUD + signal generation)

## Decisions Made
- Schemas file and portfolio router were pre-existing from Wave 1 prep and committed together with the new trades router
- Duplicate lazy singleton pattern in pms_trades.py rather than shared import, per plan specification
- HTTP 404 vs 400 distinction: "not found" in ValueError message triggers 404, all other ValueErrors get 400

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing fastapi dependency**
- **Found during:** Task 1 verification
- **Issue:** FastAPI not installed in system Python, preventing import verification
- **Fix:** `pip install fastapi` to unblock route module imports
- **Files modified:** None (system package only)
- **Verification:** All imports succeed after installation
- **Committed in:** Not committed (system-level dependency)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minimal -- fastapi was needed for verification only. No scope creep.

## Issues Encountered
None beyond the fastapi installation.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 16 endpoints ready for integration with main.py (Plan 03 will register routers)
- Schemas available for frontend and external tool integration
- Both routers use lazy singleton pattern, so TradeWorkflowService is only instantiated on first API call

## Self-Check: PASSED

- [x] src/api/schemas/__init__.py -- FOUND
- [x] src/api/schemas/pms_schemas.py -- FOUND
- [x] src/api/routes/pms_portfolio.py -- FOUND
- [x] src/api/routes/pms_trades.py -- FOUND
- [x] Commit 0946df0 -- FOUND

---
*Phase: 21-trade-workflow-pms-api*
*Completed: 2026-02-24*
