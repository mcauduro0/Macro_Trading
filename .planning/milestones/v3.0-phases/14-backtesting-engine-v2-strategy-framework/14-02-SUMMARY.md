---
phase: 14-backtesting-engine-v2-strategy-framework
plan: 02
subsystem: backtesting
tags: [backtesting, portfolio, walk-forward, transaction-costs, overfitting]

requires:
  - phase: 14-01
    provides: "StrategyRegistry, enhanced BaseStrategy, StrategySignal, BacktestResultRecord v2"
provides:
  - "BacktestEngine.run_portfolio for multi-strategy portfolio backtesting with weights, attribution, correlation"
  - "BacktestEngine.walk_forward_validation for train/test window splitting with overfit detection"
  - "TransactionCostModel with COST_TABLE for 12 instruments and ticker prefix matching"
  - "BacktestConfig v2 with walk_forward, cost_model, funding_rate fields"
affects: [14-03, 15-strategies, backtesting, portfolio-optimization]

tech-stack:
  added: []
  patterns: [portfolio-level-backtesting, walk-forward-validation, per-instrument-cost-model]

key-files:
  created:
    - tests/test_backtesting_v2.py
  modified:
    - src/backtesting/engine.py
    - src/backtesting/costs.py
    - src/backtesting/__init__.py

key-decisions:
  - "Portfolio equity = weighted sum of individual strategy equity curves, aligned to common date index"
  - "Walk-forward windows slide by test_months each step, overfit ratio = mean OOS Sharpe / mean IS Sharpe"
  - "TransactionCostModel uses instance-level default_bps (configurable) instead of module constant only"
  - "Attribution computed as weighted return contribution relative to total weighted return"

patterns-established:
  - "Portfolio backtesting: run individual strategies then combine equity curves"
  - "Walk-forward validation: generate windows, run train/test, report overfit ratio"
  - "Instrument cost resolution: exact match -> prefix match -> configurable default"

requirements-completed: [BTST-01, BTST-02, BTST-04]

duration: 6min
completed: 2026-02-22
---

# Phase 14 Plan 02: BacktestEngine v2 Summary

**BacktestEngine v2 with run_portfolio for multi-strategy portfolio backtesting, walk_forward_validation for overfit detection, and TransactionCostModel with 12-instrument per-instrument cost schedules**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-22T14:13:10Z
- **Completed:** 2026-02-22T14:19:37Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- BacktestEngine.run_portfolio accepts strategies + weights, returns combined BacktestResult with per-strategy attribution, correlation matrix, and individual results
- BacktestEngine.walk_forward_validation splits period into train/test windows, reports in-sample vs out-of-sample Sharpe, and logs overfit ratio (< 0.5 warns)
- TransactionCostModel has COST_TABLE with 12 instruments (DI1, DDI, DOL, NDF, NTN_B, LTN, UST, ZN, ZF, ES, CDS_BR, IBOV_FUT) with get_cost, get_cost_bps, get_round_trip_bps
- BacktestConfig v2 extends with walk_forward, train/test months, funding_rate, point_in_time, cost_model -- all defaults preserve backward compat
- 29 new tests pass, all 22 existing tests pass (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: TransactionCostModel and BacktestEngine v2 with run_portfolio and walk_forward_validation** - `4e76ae6` (feat)
2. **Task 2: Tests for BacktestEngine v2 portfolio backtesting, walk-forward, and TransactionCostModel** - `61e0333` (test)

## Files Created/Modified
- `src/backtesting/costs.py` - TransactionCostModel with 12-instrument COST_TABLE, ticker prefix matching, configurable default_bps
- `src/backtesting/engine.py` - BacktestEngine v2 with run_portfolio, walk_forward_validation, extended BacktestConfig
- `src/backtesting/__init__.py` - Added TransactionCostModel to exports
- `tests/test_backtesting_v2.py` - 29 tests covering TransactionCostModel, run_portfolio, walk-forward, BacktestConfig v2

## Decisions Made
- Portfolio equity = weighted sum of individual strategy equity curves (aligned to common DatetimeIndex via ffill/bfill)
- Walk-forward windows slide by test_months each step; overfit ratio = mean OOS Sharpe / mean IS Sharpe with < 0.5 warning threshold
- Attribution computed as each strategy's weighted return contribution divided by total weighted return
- TransactionCostModel uses instance-level default_bps (constructor arg) for customizable fallback cost

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added __init__(default_bps) to TransactionCostModel**
- **Found during:** Task 2 (test_custom_default_bps)
- **Issue:** Existing costs.py used module-level DEFAULT_COST_BPS constant but had no __init__ accepting default_bps parameter
- **Fix:** Added `__init__(self, default_bps=DEFAULT_COST_BPS)` and updated get_cost_bps to use self.default_bps
- **Files modified:** src/backtesting/costs.py
- **Verification:** test_custom_default_bps passes; all existing cost tests still pass
- **Committed in:** 61e0333 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for test correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BacktestEngine v2 ready for Phase 14 Plan 03 (any remaining backtesting infrastructure)
- run_portfolio and walk_forward_validation ready for Phase 15's 16 new strategies
- TransactionCostModel can be injected into BacktestConfig.cost_model for per-instrument cost backtesting
- All 51 tests pass (22 existing + 29 new)

## Self-Check: PASSED

All files exist. All commits verified (4e76ae6, 61e0333).

---
*Phase: 14-backtesting-engine-v2-strategy-framework*
*Completed: 2026-02-22*
