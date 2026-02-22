---
phase: 15-new-trading-strategies
plan: 03
subsystem: strategies
tags: [inflation, ipca, breakeven, carry, cupom-cambial, onshore-offshore, z-score, mean-reversion]

# Dependency graph
requires:
  - phase: 14-backtesting-engine-v2-strategy-framework
    provides: "StrategyRegistry, BaseStrategy, StrategySignal, StrategyConfig, BacktestEngine v2"
provides:
  - "INF-02 IPCA Surprise Trade strategy (event-driven around IPCA releases)"
  - "INF-03 Inflation Carry strategy (breakeven vs 3 fundamental benchmarks)"
  - "CUPOM-02 Onshore-Offshore Spread strategy (z-score mean reversion)"
  - "26 unit tests covering signal generation, missing data, registration"
affects: [15-04, 16-ml-regime-classification, 17-dagster-orchestration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "IPCA release calendar window detection for event-driven trading"
    - "Composite z-score from multiple benchmark comparisons"
    - "Onshore-offshore spread as CIP basis proxy"

key-files:
  created:
    - "src/strategies/inf_02_ipca_surprise.py"
    - "src/strategies/inf_03_inflation_carry.py"
    - "src/strategies/cupom_02_onshore_offshore.py"
    - "tests/test_strategies/test_inf_cupom_new.py"
  modified: []

key-decisions:
  - "INF-02 uses IPCA-15 as primary model forecast when available, falling back to 5-year seasonal average"
  - "INF-02 IPCA release window: [-3, +2] business days around ~10th with 14-day carryover for extreme z-scores"
  - "INF-03 composite z-score: average of 3 z-scores comparing breakeven to BCB target, IPCA 12M, and Focus"
  - "CUPOM-02 prefers 6M tenor with fallback to 3M; spread = DI - UST as CIP basis proxy"

patterns-established:
  - "Event-driven strategies: release window detection + carryover logic for post-event signal persistence"
  - "Multi-benchmark composite scoring: average z-scores across multiple fundamental anchors"

requirements-completed: [INST-01, INST-02, CPST-01]

# Metrics
duration: 7min
completed: 2026-02-22
---

# Phase 15 Plan 03: INF-02 IPCA Surprise, INF-03 Inflation Carry, CUPOM-02 Onshore-Offshore Summary

**Three inflation/cupom strategies: IPCA release event trading with seasonal model, breakeven carry vs BCB/IPCA/Focus benchmarks, and onshore-offshore spread mean reversion**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-22T16:49:08Z
- **Completed:** 2026-02-22T16:57:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- INF-02 implements IPCA release window detection and seasonal/IPCA-15 model forecast with surprise z-scoring
- INF-03 compares 2Y breakeven to 3 benchmarks (BCB target, IPCA 12M, Focus) via composite z-score
- CUPOM-02 trades onshore DI vs offshore UST+fwd spread with z-score mean reversion at 1.5 threshold
- All 3 strategies return empty lists on missing data (no forward-fill, no degraded models)
- 26 unit tests pass covering registration, signal generation, direction logic, and missing data handling

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement INF-02, INF-03, CUPOM-02** - `df61a39` (feat)
2. **Task 2: Tests for INF-02, INF-03, CUPOM-02** - `f1ced1d` (test)

## Files Created/Modified
- `src/strategies/inf_02_ipca_surprise.py` - IPCA Surprise Trade strategy with release window + seasonal model
- `src/strategies/inf_03_inflation_carry.py` - Inflation Carry strategy comparing breakeven to 3 benchmarks
- `src/strategies/cupom_02_onshore_offshore.py` - Onshore-Offshore Spread mean reversion strategy
- `tests/test_strategies/test_inf_cupom_new.py` - 26 unit tests for all 3 strategies

## Decisions Made
- INF-02 uses IPCA-15 as primary model forecast (leading indicator) with seasonal average fallback
- INF-02 release window: [-3, +2] business days around estimated ~10th release with 14-day carryover if |z| > 1.5
- INF-03 BCB target hardcoded at 3.0% with 1.5pp band (current policy parameters)
- CUPOM-02 uses simplified CIP basis (DI - UST) as onshore-offshore spread proxy
- CUPOM-02 higher entry threshold (1.5 vs 1.0) to account for spread noise
- All 3 strategies produce StrategySignal (v3.0 dataclass) rather than StrategyPosition

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed INF-02 missing Focus test**
- **Found during:** Task 2 (Tests)
- **Issue:** Test for missing Focus data was not properly overriding the mock side_effect (return_value does not override side_effect in MagicMock)
- **Fix:** Used side_effect override for both get_focus_expectations and get_macro_series
- **Files modified:** tests/test_strategies/test_inf_cupom_new.py
- **Verification:** All 26 tests pass
- **Committed in:** f1ced1d (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix in test)
**Impact on plan:** Minor test mock fix. No scope creep.

## Issues Encountered
None beyond the test mock fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 11 strategies now registered (8 original + INF_02 + INF_03 + CUPOM_02)
- INFLATION_BR asset class has 2 strategies (INF_02, INF_03) alongside INF_BR_01
- CUPOM_CAMBIAL asset class has 1 strategy (CUPOM_02) alongside CUPOM_01
- Ready for 15-04 (remaining strategies: sovereign, cross-asset)

## Self-Check: PASSED

- All 4 created files verified on disk
- Both task commits (df61a39, f1ced1d) verified in git log
- 26/26 tests passing

---
*Phase: 15-new-trading-strategies*
*Completed: 2026-02-22*
