---
phase: 21-trade-workflow-pms-api
plan: 01
subsystem: pms
tags: [trade-workflow, proposal-pipeline, approval-workflow, decision-journal, position-management]

# Dependency graph
requires:
  - phase: 20-pms-database-position-manager
    provides: "PositionManager, MarkToMarketService, DecisionJournal, in-memory position store"
provides:
  - "TradeWorkflowService with signal-to-proposal pipeline"
  - "Human-in-the-loop approve/reject/modify workflow"
  - "Discretionary trade support with mandatory thesis"
  - "Flip signal detection for position reversals"
  - "Template-based trade rationale with optional LLM enhancement"
affects: [21-02-pms-api, 21-03-pms-api, phase-22-execution]

# Tech tracking
tech-stack:
  added: []
  patterns: [proposal-lifecycle-state-machine, conviction-filtering-pipeline, immutable-journal-entries]

key-files:
  created:
    - src/pms/trade_workflow.py
    - tests/test_pms/test_trade_workflow.py
  modified:
    - src/pms/__init__.py

key-decisions:
  - "In-memory _proposals list (same pattern as PositionManager._positions) for decoupled dict-based storage"
  - "Template-based rationale as primary, LLM (Claude API) as optional enhancement with full fallback"
  - "Flip detection at conviction >= 0.60 against opposite open position on same instrument"
  - "Conviction min 0.55, max 5 proposals per call, sorted by conviction descending"
  - "REJECT journal entries created directly with content_hash for immutability"

patterns-established:
  - "Proposal lifecycle: PENDING -> APPROVED/REJECTED/MODIFIED state machine"
  - "Mandatory fields pattern: manager_notes for reject, manager_thesis for discretionary"
  - "Journal linking: proposal_id backlinked to OPEN journal entries after position creation"

requirements-completed: [PMS-TW-01, PMS-TW-02, PMS-TW-03, PMS-TW-04, PMS-TW-05]

# Metrics
duration: 5min
completed: 2026-02-24
---

# Phase 21 Plan 01: TradeWorkflowService Summary

**Signal-to-proposal pipeline with conviction filtering, human-in-the-loop approve/reject/modify workflow, discretionary trades, and immutable DecisionJournal logging**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-24T03:14:54Z
- **Completed:** 2026-02-24T03:19:53Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- TradeWorkflowService with 9 methods implementing complete proposal lifecycle
- 14 tests covering all workflow paths: generate, approve, reject, modify, discretionary, close, flip detection
- All 62 PMS tests pass (48 existing + 14 new) with zero regressions
- Package export updated for clean `from src.pms import TradeWorkflowService`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create TradeWorkflowService with signal-to-proposal pipeline and approval workflow** - `84fcb55` (feat)
2. **Task 2: Update src/pms/__init__.py to export TradeWorkflowService** - `1397d51` (chore)

## Files Created/Modified
- `src/pms/trade_workflow.py` - TradeWorkflowService class with 9 methods: generate_proposals_from_signals, get_pending_proposals, approve_proposal, reject_proposal, modify_and_approve_proposal, open_discretionary_trade, close_position, _estimate_portfolio_impact, _generate_trade_rationale
- `tests/test_pms/test_trade_workflow.py` - 14 tests covering conviction filtering, max limit, sorting, rationale/risk_impact generation, approve/reject/modify lifecycle, discretionary trades, position closing with outcome notes, flip signal detection
- `src/pms/__init__.py` - Added TradeWorkflowService import and __all__ entry

## Decisions Made
- In-memory _proposals list follows same dict-based pattern as PositionManager._positions for consistency
- Template-based rationale as primary method; LLM (Claude API via httpx) as optional enhancement with full try/except fallback
- Flip detection at conviction >= 0.60 checks for opposite open position on same instrument
- REJECT journal entries use PositionManager._compute_content_hash for immutability consistency
- Proposal metadata_json dict stores optional target_price, stop_loss, time_horizon

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- TradeWorkflowService ready for API layer exposure in Plan 21-02
- All in-memory stores compatible with future DB persistence wiring
- Proposal lifecycle state machine (PENDING/APPROVED/REJECTED/MODIFIED) ready for frontend integration

## Self-Check: PASSED

- [x] src/pms/trade_workflow.py exists (737 lines)
- [x] tests/test_pms/test_trade_workflow.py exists (471 lines, > 200 minimum)
- [x] 21-01-SUMMARY.md exists
- [x] Commit 84fcb55 found (Task 1)
- [x] Commit 1397d51 found (Task 2)
- [x] 14/14 tests pass
- [x] 62/62 total PMS tests pass (zero regressions)

---
*Phase: 21-trade-workflow-pms-api*
*Completed: 2026-02-24*
