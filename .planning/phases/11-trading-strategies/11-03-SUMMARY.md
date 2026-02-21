---
phase: 11-trading-strategies
plan: 03
subsystem: strategies
tags: [fx, cip-basis, fiscal-risk, cupom-cambial, sovereign-spread, mean-reversion, strategy-registry]

# Dependency graph
requires:
  - phase: 11-01
    provides: "BaseStrategy ABC, StrategyConfig, StrategyPosition, RATES_BR_01, RATES_BR_02"
  - phase: 11-02
    provides: "RATES_BR_03, RATES_BR_04, INF_BR_01 strategies"
provides:
  - "FX_BR_01 USDBRL Carry & Fundamental composite strategy"
  - "CUPOM_01 CIP Basis Mean Reversion strategy"
  - "SOV_BR_01 Fiscal Risk Premium strategy"
  - "ALL_STRATEGIES registry dict with all 8 strategies by ID"
affects: [backtesting-engine, daily-pipeline, portfolio-construction]

# Tech tracking
tech-stack:
  added: []
  patterns: [composite-signal-weighting, regime-adjustment-scaling, mean-reversion-zscore, fiscal-risk-scoring, multi-position-strategy]

key-files:
  created:
    - src/strategies/fx_br_01_carry_fundamental.py
    - src/strategies/cupom_01_cip_basis.py
    - src/strategies/sov_br_01_fiscal_risk.py
    - tests/test_strategies/test_fx_br_01.py
    - tests/test_strategies/test_cupom_01.py
    - tests/test_strategies/test_sov_br_01.py
  modified:
    - src/strategies/__init__.py

key-decisions:
  - "FX_BR_01 carry-to-risk uses tanh(carry_to_risk/2) for bounded score; 21-day realized vol (annualized)"
  - "CUPOM_01 uses inner join of DI and UST curve histories for basis z-score computation"
  - "SOV_BR_01 fiscal risk = linear 60-100% GDP debt mapping + primary balance adjustment"
  - "SOV_BR_01 produces up to 2 positions (DI + USDBRL) when fiscal dominance trade triggers"
  - "ALL_STRATEGIES registry uses type[BaseStrategy] values for programmatic instantiation"

patterns-established:
  - "Composite strategy pattern: multiple scored components weighted and summed into single signal (FX_BR_01)"
  - "Regime adjustment: optional regime_score parameter scales position without hard coupling"
  - "Multi-position strategy: SOV_BR_01 returns 1-2 positions for correlated instruments"

requirements-completed: [STRAT-07, STRAT-08, STRAT-09]

# Metrics
duration: 10min
completed: 2026-02-21
---

# Phase 11 Plan 03: Final Strategies & Registry Summary

**FX/CIP basis/sovereign risk strategies (FX_BR_01, CUPOM_01, SOV_BR_01) and ALL_STRATEGIES registry exporting all 8 strategies by ID**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-21T21:32:11Z
- **Completed:** 2026-02-21T21:42:11Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- FX_BR_01 composites carry-to-risk (40%), BEER misalignment (35%), and flow score (25%) with optional regime adjustment for USDBRL directional trading
- CUPOM_01 fades extreme CIP basis z-scores (cupom cambial vs SOFR) via mean reversion at configurable threshold
- SOV_BR_01 trades fiscal dominance risk premium in long-end DI and USDBRL based on debt-to-GDP, primary balance, and spread z-score mispricing
- ALL_STRATEGIES registry dict maps all 8 strategy IDs to their classes for programmatic discovery
- 136 total tests passing across entire strategy suite (51 new in this plan: 23 FX_BR_01 + 12 CUPOM_01 + 16 SOV_BR_01)

## Task Commits

Each task was committed atomically:

1. **Task 1: FX_BR_01 Carry & Fundamental composite strategy with tests** - `190cdaf` (feat)
2. **Task 2: CUPOM_01, SOV_BR_01 strategies and ALL_STRATEGIES registry with tests** - `6b5ba0f` (feat)

## Files Created/Modified
- `src/strategies/fx_br_01_carry_fundamental.py` - USDBRL Carry & Fundamental composite (carry 40%, BEER 35%, flow 25%)
- `src/strategies/cupom_01_cip_basis.py` - CIP Basis Mean Reversion on cupom cambial vs SOFR
- `src/strategies/sov_br_01_fiscal_risk.py` - Fiscal Risk Premium trades on long-end DI and USDBRL
- `src/strategies/__init__.py` - ALL_STRATEGIES registry dict and all 8+3 base exports
- `tests/test_strategies/test_fx_br_01.py` - 23 tests: carry/BEER/flow components, direction, regime, bounds, missing data
- `tests/test_strategies/test_cupom_01.py` - 12 tests: short/long basis, neutral, missing data, bounds, config
- `tests/test_strategies/test_sov_br_01.py` - 16 tests: high/low risk+spread combos, neutral cases, fiscal risk scoring, bounds

## Decisions Made
- FX_BR_01 carry-to-risk normalizes via tanh(carry_to_risk/2); 21-day annualized realized vol from USDBRL close returns
- FX_BR_01 BEER uses 252-day rolling mean as simplified fair value (full BEER from FxEquilibriumAgent in Phase 9)
- FX_BR_01 flow score uses 21-day rolling sum z-score vs 252-day window; insufficient flow data treats as 0 (not blocking)
- CUPOM_01 uses inner join (not outer) for DI-UST history alignment to ensure matching dates
- CUPOM_01 basis z-threshold default 2.0 (conservative; 1.5-2.5 common for mean reversion)
- SOV_BR_01 fiscal risk linear mapping: 60-100% GDP debt + primary balance adjustment (deficit +20x, surplus -10x)
- SOV_BR_01 uses DI long-end rate history as spread z-score proxy when CDS unavailable
- SOV_BR_01 produces 2 correlated positions (DI + USDBRL) to capture fiscal dominance risk fully
- ALL_STRATEGIES uses type[BaseStrategy] values (not instances) for lazy instantiation by caller

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 8 Phase 11 strategies complete and tested (136 tests)
- ALL_STRATEGIES registry ready for Phase 10 backtesting engine and Phase 13 daily pipeline
- All strategies produce valid StrategyPosition with weight in [-1,1] and confidence in [0,1]
- Regime adjustment pattern (FX_BR_01) ready for Phase 12 integration

---
*Phase: 11-trading-strategies*
*Completed: 2026-02-21*
