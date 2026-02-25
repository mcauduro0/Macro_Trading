---
phase: 22-morning-pack-risk-monitor-attribution
plan: 01
subsystem: pms
tags: [morning-pack, attribution, daily-briefing, pnl-decomposition, factor-tags, llm-narrative]

# Dependency graph
requires:
  - phase: 20-pms-models-position-manager
    provides: "PositionManager with positions, P&L history, MTM, get_book()"
  - phase: 21-trade-workflow-pms-api
    provides: "TradeWorkflowService with proposals, approval workflow"
provides:
  - "MorningPackService with generate(), get_latest(), get_by_date(), get_history()"
  - "PerformanceAttributionEngine with compute_attribution(), compute_for_period(), compute_equity_curve()"
  - "Factor-based P&L attribution via FACTOR_TAGS for all 24 strategies"
affects: [23-frontend-pages, 25-operational-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns: [action-first-ordering, graceful-degradation-sections, additive-attribution, tag-based-factor-mapping]

key-files:
  created:
    - src/pms/morning_pack.py
    - src/pms/attribution.py
    - tests/test_pms/test_morning_pack.py
    - tests/test_pms/test_attribution.py
  modified: []

key-decisions:
  - "Action-first ordering: action_items and trade_proposals appear before context sections in briefing"
  - "Template-based narrative as primary fallback; LLM (Claude API) as optional enhancement"
  - "Factor attribution splits P&L equally across factors when a position maps to multiple factors"
  - "Sub-period buckets: weekly if range <= 90 days, monthly if > 90 days"
  - "Additive attribution: each dimension independently sums to total_pnl_brl"

patterns-established:
  - "Action-first briefing pattern: action items before context for operational urgency"
  - "Graceful degradation sections: each section returns {status: unavailable, reason: str} on failure"
  - "Tag-based factor mapping: FACTOR_TAGS dict maps strategy_id to factor list for attribution"

requirements-completed: [PMS-MP-01, PMS-MP-03, PMS-PA-01, PMS-PA-02, PMS-PA-03]

# Metrics
duration: 9min
completed: 2026-02-24
---

# Phase 22 Plan 01: Morning Pack & Attribution Summary

**MorningPackService with 9-section daily briefings (action-first ordering, LLM narrative with template fallback) and PerformanceAttributionEngine with 5-dimension additive P&L decomposition plus factor tags for all 24 strategies**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-24T14:51:19Z
- **Completed:** 2026-02-24T15:00:21Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- MorningPackService generates complete daily briefings with all 9 sections in action-first order
- Graceful degradation: all components optional, sections marked "unavailable" when missing
- PerformanceAttributionEngine decomposes P&L across 5 additive dimensions (strategy, asset class, instrument, factor, trade type) plus time period and performance stats
- Factor attribution covers all 24 strategies via FACTOR_TAGS mapping
- Equity curve computation with cumulative returns and drawdown tracking

## Task Commits

Each task was committed atomically:

1. **Task 1: MorningPackService with daily briefing generation** - `2dc5a23` (feat)
2. **Task 2: PerformanceAttributionEngine with multi-dimensional P&L decomposition** - `2d8dc56` (feat)

## Files Created/Modified
- `src/pms/morning_pack.py` - MorningPackService: 9-section daily briefing with action-first ordering, LLM narrative, graceful degradation
- `src/pms/attribution.py` - PerformanceAttributionEngine: 5-dimension P&L decomposition, factor tags, equity curve, performance stats
- `tests/test_pms/test_morning_pack.py` - 4 tests: generation, graceful degradation, auto-persist, action prioritization
- `tests/test_pms/test_attribution.py` - 4 tests: additive sums, factor tags, extended periods, equity curve

## Decisions Made
- Action-first ordering: action_items is the first content key in briefing dict, followed by trade_proposals
- Template-based macro narrative generates 5 paragraphs (~400 words) covering regime, agent consensus, signals, portfolio state, and risk outlook
- Factor attribution splits P&L equally across factors when a single position maps to multiple factors via FACTOR_TAGS
- Sub-period attribution uses weekly buckets for ranges <= 90 days, monthly for > 90 days
- Performance stats use ddof=0 (population std) consistent with existing analytics

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. LLM narrative uses ANTHROPIC_API_KEY if available, with template fallback.

## Next Phase Readiness
- MorningPackService and PerformanceAttributionEngine ready for Phase 23/25 frontend integration
- Both services follow in-memory patterns consistent with PositionManager and TradeWorkflowService
- Factor tags cover all 24 strategies for immediate attribution use

---
*Phase: 22-morning-pack-risk-monitor-attribution*
*Completed: 2026-02-24*
