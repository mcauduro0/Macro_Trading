---
phase: 11-trading-strategies
plan: 01
subsystem: strategies
tags: [trading-strategies, BaseStrategy, DI-curve, carry-rolldown, taylor-rule, fixed-income]

# Dependency graph
requires:
  - phase: 07-agent-framework-data-loader
    provides: "BaseAgent ABC, AgentSignal, PointInTimeDataLoader, classify_strength"
provides:
  - "BaseStrategy ABC with StrategyConfig and StrategyPosition dataclasses"
  - "signals_to_positions constraint engine with locked weight formula"
  - "RATES_BR_01 Carry & Roll-Down strategy for DI curve"
  - "RATES_BR_02 Taylor Rule Misalignment strategy for DI curve"
affects: [11-02-PLAN, 11-03-PLAN, backtesting, portfolio-construction]

# Tech tracking
tech-stack:
  added: []
  patterns: [strategy-abc-pattern, signals-to-positions-engine, carry-risk-analysis, taylor-rule-model]

key-files:
  created:
    - src/strategies/__init__.py
    - src/strategies/base.py
    - src/strategies/rates_br_01_carry.py
    - src/strategies/rates_br_02_taylor.py
    - tests/test_strategies/test_base.py
    - tests/test_strategies/test_rates_br_01.py
    - tests/test_strategies/test_rates_br_02.py
  modified: []

key-decisions:
  - "STRENGTH_MAP locked: STRONG=1.0, MODERATE=0.6, WEAK=0.3, NO_SIGNAL=0.0"
  - "Weight formula: strength_base * confidence * max_position_size with leverage proportional scaling"
  - "NEUTRAL signals produce 50% scale-down of existing position weight"
  - "RATES_BR_01 carry_threshold=1.5 default; confidence scales linearly to 2x threshold"
  - "RATES_BR_02 gap_threshold=100bps default; Taylor r_star=4.5%, alpha=1.5, beta=0.5"
  - "RATES_BR_02 1Y tenor lookup uses 50-day tolerance window around 252 days"

patterns-established:
  - "Strategy ABC pattern: BaseStrategy with generate_signals(as_of_date) -> list[StrategyPosition]"
  - "signals_to_positions engine: converts AgentSignal to StrategyPosition via locked formula"
  - "StrategyConfig frozen dataclass with 9 fields for immutable strategy configuration"
  - "Strategy tests use mock PointInTimeDataLoader with side_effect for data scenarios"

requirements-completed: [STRAT-01, STRAT-02, STRAT-03]

# Metrics
duration: 10min
completed: 2026-02-21
---

# Phase 11 Plan 01: BaseStrategy Framework + BR Rates Strategies Summary

**BaseStrategy ABC with locked weight formula (strength x confidence x max_size), RATES_BR_01 carry-to-risk DI tenor selection, and RATES_BR_02 Taylor rule gap trading**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-21T21:01:44Z
- **Completed:** 2026-02-21T21:12:12Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- BaseStrategy ABC with frozen StrategyConfig (9 fields), StrategyPosition dataclass, and strategy_id property
- signals_to_positions engine: STRENGTH_MAP-based weight formula, NEUTRAL 50% scale-down, max_position_size clamping, leverage enforcement
- RATES_BR_01 Carry & Roll-Down: computes carry-to-risk at each DI curve tenor pair, selects optimal tenor, goes LONG/SHORT when ratio exceeds threshold
- RATES_BR_02 Taylor Rule Misalignment: computes Taylor-implied rate vs 1Y DI market rate, trades when gap exceeds 100bps
- 51 tests total (27 base + 8 RATES_BR_01 + 16 RATES_BR_02), all passing with zero lint errors

## Task Commits

Each task was committed atomically:

1. **Task 1: BaseStrategy ABC with StrategyConfig, StrategyPosition, and constraint engine** - `33bfabd` (feat)
2. **Task 2: RATES_BR_01 Carry & Roll-Down and RATES_BR_02 Taylor Misalignment strategies** - `716d1bb` (feat)

## Files Created/Modified
- `src/strategies/__init__.py` - Package exports for BaseStrategy, StrategyConfig, StrategyPosition, and both rate strategies
- `src/strategies/base.py` - BaseStrategy ABC, StrategyConfig frozen dataclass, StrategyPosition, STRENGTH_MAP, signals_to_positions, validate_position
- `src/strategies/rates_br_01_carry.py` - RatesBR01CarryStrategy: carry-to-risk DI tenor analysis
- `src/strategies/rates_br_02_taylor.py` - RatesBR02TaylorStrategy: Taylor rule gap trading
- `tests/test_strategies/__init__.py` - Test package init
- `tests/test_strategies/test_base.py` - 27 tests for base framework (frozen config, weight formula, clamping, leverage, ABC)
- `tests/test_strategies/test_rates_br_01.py` - 8 tests for carry strategy (LONG/SHORT/neutral/edge cases/bounds)
- `tests/test_strategies/test_rates_br_02.py` - 16 tests for Taylor strategy (SHORT/LONG/neutral/missing data/bounds/custom threshold/tenor finding)

## Decisions Made
- STRENGTH_MAP values locked per CONTEXT.md: STRONG=1.0, MODERATE=0.6, WEAK=0.3, NO_SIGNAL=0.0
- NEUTRAL signals: weight = existing_weight * 0.5 (50% scale-down); no existing position = 0.0
- RATES_BR_01 default carry_threshold=1.5; confidence = min(1.0, ratio / (threshold * 2))
- RATES_BR_02 default gap_threshold=100bps; confidence = min(1.0, abs(gap_bps) / (threshold * 3))
- RATES_BR_02 Taylor parameters: r_star=4.5%, pi_target=3.0%, alpha=1.5, beta=0.5, output_gap defaults to 0.0
- RATES_BR_02 1Y tenor lookup: finds closest tenor to 252 days within 50-day tolerance window
- Both strategies handle missing/insufficient data gracefully by returning empty list

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff import ordering in base.py**
- **Found during:** Task 1 (verification)
- **Issue:** Import block in base.py was not sorted per ruff I001 rule
- **Fix:** Applied `ruff check --fix` to auto-sort imports
- **Files modified:** src/strategies/base.py
- **Verification:** `ruff check` passes with zero errors
- **Committed in:** 33bfabd (Task 1 commit)

**2. [Rule 1 - Bug] Removed unused imports in strategy and test files**
- **Found during:** Task 2 (verification)
- **Issue:** SignalStrength imported but unused in both rate strategies; pytest and patch imported but unused in test files
- **Fix:** Applied `ruff check --fix` to remove unused imports
- **Files modified:** src/strategies/rates_br_01_carry.py, src/strategies/rates_br_02_taylor.py, tests/test_strategies/test_rates_br_01.py, tests/test_strategies/test_rates_br_02.py
- **Verification:** `ruff check` passes with zero errors
- **Committed in:** 716d1bb (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 lint fixes)
**Impact on plan:** Trivial lint cleanups, no scope creep.

## Issues Encountered
- structlog, sqlalchemy, pydantic, asyncpg, numpy not pre-installed in environment -- installed via pip as blocking dependencies (Rule 3). These are existing project dependencies, not new additions.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BaseStrategy framework ready for remaining 6 strategies (Plans 11-02 and 11-03)
- signals_to_positions engine locked and tested for reuse by all strategy subclasses
- PointInTimeDataLoader integration pattern established via mock testing

## Self-Check: PASSED

- All 8 files verified present on disk
- Commit 33bfabd verified in git log
- Commit 716d1bb verified in git log
- 51/51 tests passing
- Zero lint errors

---
*Phase: 11-trading-strategies*
*Completed: 2026-02-21*
