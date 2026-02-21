---
phase: 11-trading-strategies
plan: 02
subsystem: strategies
tags: [fixed-income, curve-slope, spillover, breakeven-inflation, di-curve, ust, ntn-b, z-score, mean-reversion]

# Dependency graph
requires:
  - phase: 11-01
    provides: "BaseStrategy ABC, StrategyConfig, StrategyPosition, RATES_BR_01, RATES_BR_02"
provides:
  - "RATES_BR_03 Curve Slope (flattener/steepener) strategy"
  - "RATES_BR_04 US Rates Spillover mean-reversion strategy"
  - "INF_BR_01 Breakeven Inflation Trade strategy"
affects: [11-03, backtesting, portfolio-construction, signal-aggregation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Z-score threshold pattern for curve slope and spread signals"
    - "Outer join with forward-fill for cross-market holiday alignment (DI vs UST)"
    - "Breakeven = nominal - real rate tenor matching with tolerance"

key-files:
  created:
    - src/strategies/rates_br_03_slope.py
    - src/strategies/rates_br_04_spillover.py
    - src/strategies/inf_br_01_breakeven.py
    - tests/test_strategies/test_rates_br_03.py
    - tests/test_strategies/test_rates_br_04.py
    - tests/test_strategies/test_inf_br_01.py
  modified:
    - src/strategies/__init__.py

key-decisions:
  - "RATES_BR_03: Slope z-score uses rolling 252-day (or available) window; flattener for z > threshold regardless of easing/tightening cycle"
  - "RATES_BR_04: Outer join with ffill for DI-UST holiday alignment; weekly UST change = ust[-1] - ust[-5] (5 business days)"
  - "INF_BR_01: Focus on 2Y tenor as primary breakeven signal (most liquid); divergence_threshold_bps=50 default"
  - "Confidence formula: RATES_BR_03 uses /(threshold*2.5), RATES_BR_04 uses /(threshold*2), INF_BR_01 uses /(threshold*3) -- varying by strategy risk profile"

patterns-established:
  - "Cross-market spread strategy pattern: load two curve histories, outer join + ffill, compute spread z-score"
  - "Relative-value inflation strategy: compute breakeven from nominal-real curves, compare to survey-based forecast"

requirements-completed: [STRAT-04, STRAT-05, STRAT-06]

# Metrics
duration: 10min
completed: 2026-02-21
---

# Phase 11 Plan 02: Trading Strategies Wave 2 Summary

**Three macro strategies: DI 2Y-5Y curve slope flattener/steepener, US rates spillover mean-reversion, and breakeven inflation trade using Focus vs market-implied divergence**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-21T21:16:42Z
- **Completed:** 2026-02-21T21:27:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- RATES_BR_03 trades DI 2Y-5Y slope using z-score vs 252-day history, generating flattener/steepener positions based on monetary cycle context
- RATES_BR_04 fades DI-UST spread overshoot after large weekly UST moves (>15bps default) via mean reversion of spread z-score
- INF_BR_01 trades breakeven inflation when Focus IPCA forecast diverges from market-implied breakeven (nominal DI minus NTN-B real) by >50bps
- All 85 strategy tests passing (27 base + 8 BR01 + 16 BR02 + 11 BR03 + 9 BR04 + 14 INF01)

## Task Commits

Each task was committed atomically:

1. **Task 1: RATES_BR_03 Curve Slope + RATES_BR_04 US Rates Spillover** - `81f4dbd` (feat)
2. **Task 2: INF_BR_01 Breakeven Inflation Trade** - `8695944` (feat)

## Files Created/Modified
- `src/strategies/rates_br_03_slope.py` - DI 2Y-5Y curve slope strategy with z-score analysis and monetary cycle detection
- `src/strategies/rates_br_04_spillover.py` - US rates spillover to BR DI via spread mean-reversion after large UST moves
- `src/strategies/inf_br_01_breakeven.py` - Breakeven inflation trade comparing Focus forecast to market-implied breakeven
- `tests/test_strategies/test_rates_br_03.py` - 11 tests: flattener/steepener/neutral/missing data/bounds
- `tests/test_strategies/test_rates_br_04.py` - 9 tests: spread overshoot/undershoot/small UST move/missing data/bounds
- `tests/test_strategies/test_inf_br_01.py` - 14 tests: long/short/neutral/missing data (5 cases)/bounds/custom threshold
- `src/strategies/__init__.py` - Added exports for all three new strategy classes

## Decisions Made
- RATES_BR_03 slope z-score uses rolling 252-day window (or all available if <252); flattener for z > threshold in both easing and tightening cycles (per plan specification)
- RATES_BR_04 uses outer join with forward-fill for cross-market holiday alignment between DI and UST histories; weekly UST change measured as ust[-1] - ust[-5] in the UST-specific history
- INF_BR_01 focuses on 2Y tenor (~504 days) as primary breakeven signal with 100-day tolerance for tenor matching; separate tolerance-based tenor finding for both DI and NTN-B curves
- Confidence scaling varies by strategy risk profile: slope uses /(threshold*2.5), spillover uses /(threshold*2), breakeven uses /(threshold*3)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test data to produce z-scores above threshold**
- **Found during:** Task 1 (RATES_BR_03 and RATES_BR_04 tests)
- **Issue:** Initial test data for flattener tests produced z-score of 0.78 (below 1.5 threshold); UST weekly change data had identical values at [-1] and [-5] positions producing 0.0 bps change
- **Fix:** Adjusted RATES_BR_03 test histories to create larger slope contrast (13.1->16.0 for 5Y); adjusted RATES_BR_04 UST rates to use graduated changes so [-1] and [-5] differ
- **Files modified:** tests/test_strategies/test_rates_br_03.py, tests/test_strategies/test_rates_br_04.py
- **Verification:** All 20 tests for both strategies pass
- **Committed in:** 81f4dbd (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test data)
**Impact on plan:** Test data correction only. No scope creep. Strategy logic unchanged.

## Issues Encountered
None beyond the test data adjustment documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 5 strategies now complete (RATES_BR_01 through RATES_BR_04 + INF_BR_01)
- Ready for Plan 11-03 which will add remaining strategies
- All strategies follow consistent BaseStrategy pattern with signals_to_positions constraint enforcement

## Self-Check: PASSED

- All 7 created/modified files verified on disk
- Commit 81f4dbd verified in git log
- Commit 8695944 verified in git log
- 85 tests passing across all strategy test files

---
*Phase: 11-trading-strategies*
*Completed: 2026-02-21*
