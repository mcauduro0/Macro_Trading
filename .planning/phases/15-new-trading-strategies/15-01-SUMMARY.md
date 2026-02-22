---
phase: 15-new-trading-strategies
plan: 01
subsystem: strategies
tags: [fx, usdbrl, carry, momentum, flow, vol-surface, terms-of-trade, z-score, contrarian]

# Dependency graph
requires:
  - phase: 14-backtesting-engine-v2-strategy-framework
    provides: "StrategyRegistry, BaseStrategy with compute_z_score/size_from_conviction/classify_strength, StrategySignal dataclass"
provides:
  - "FX-02 Carry-Adjusted Momentum strategy (Selic-FFR carry + 63-day USDBRL momentum)"
  - "FX-03 Flow-Based Tactical strategy (BCB flow + CFTC positioning + B3 flow with contrarian logic)"
  - "FX-04 Vol Surface Relative Value strategy (implied-realized premium + term structure + skew + kurtosis)"
  - "FX-05 Terms of Trade Misalignment strategy (commodity-weighted ToT index vs USDBRL)"
  - "35 unit tests covering all 4 new FX strategies"
affects: [15-02, 15-03, 15-04, 16-portfolio-optimization, backtesting]

# Tech tracking
tech-stack:
  added: [scipy.stats.skew, scipy.stats.kurtosis]
  patterns: [decorator-based-strategy-registration, z-score-composite-signals, vol-adjusted-sizing, contrarian-flow-logic]

key-files:
  created:
    - src/strategies/fx_02_carry_momentum.py
    - src/strategies/fx_03_flow_tactical.py
    - src/strategies/fx_04_vol_surface_rv.py
    - src/strategies/fx_05_terms_of_trade.py
    - tests/test_strategies/test_fx_new.py
  modified:
    - src/strategies/__init__.py

key-decisions:
  - "Use BaseStrategy.compute_z_score for all z-score calculations ensuring consistent methodology across strategies"
  - "FX-03 contrarian threshold at |z|>2.0 inverting signal direction for extreme positioning reversals"
  - "FX-04 implied vol proxy from mean absolute deviation scaled by sqrt(pi/2) when no direct IV series available"
  - "FX-05 commodity weights: soybean 30%, iron ore 25%, oil 20%, sugar 15%, coffee 10% reflecting Brazil export composition"
  - "Updated __init__.py to import all 4 new strategies for automatic StrategyRegistry population at package import time"

patterns-established:
  - "New strategy pattern: @StrategyRegistry.register decorator + StrategySignal output + module-level CONFIG constant"
  - "Vol-adjusted sizing: min(1.0, target_vol/realized_vol) scaling of suggested_size"
  - "Contrarian logic pattern: invert direction at extreme z-scores for mean-reversion signals"
  - "Commodity fallback tickers: try primary Yahoo ticker first, then list of alternatives"

requirements-completed: [FXST-01, FXST-02, FXST-03, FXST-04]

# Metrics
duration: 9min
completed: 2026-02-22
---

# Phase 15 Plan 01: New FX Strategies Summary

**4 new USDBRL strategies (carry-momentum, flow-tactical, vol-surface, terms-of-trade) with @StrategyRegistry.register, z-score composites, and 35 unit tests**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-22T16:49:23Z
- **Completed:** 2026-02-22T16:58:28Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Expanded FX coverage from 1 strategy (FX_BR_01) to 5 strategies with diversified signal sources
- All 4 strategies produce StrategySignal with z_score, entry_level, stop_loss, take_profit fields
- Contrarian logic in FX-03 inverts direction at |z|>2 for extreme positioning reversal detection
- Vol-adjusted sizing in FX-02 scales position size by min(1, target_vol/realized_vol)
- Commodity-weighted Terms of Trade index in FX-05 detects BRL misalignment vs fundamentals
- 35 tests pass covering registration, signal generation, missing data handling, and direction logic

## Task Commits

Each task was committed atomically:

1. **Task 1: FX-02 Carry-Adjusted Momentum + FX-03 Flow-Based Tactical** - `f93660e` (feat)
2. **Task 2: FX-04 Vol Surface RV + FX-05 Terms of Trade + Tests + __init__.py** - `6f64dd5` (feat)

## Files Created/Modified
- `src/strategies/fx_02_carry_momentum.py` - Carry-Adjusted Momentum: 50% Selic-FFR carry z + 50% 63-day momentum z, vol-adjusted sizing, 21-day holding
- `src/strategies/fx_03_flow_tactical.py` - Flow-Based Tactical: 40% BCB flow + 35% CFTC + 25% B3, contrarian at |z|>2, 14-day holding
- `src/strategies/fx_04_vol_surface_rv.py` - Vol Surface RV: 40% IV-RV premium + 25% term structure + 20% skew + 15% kurtosis, 14-day holding
- `src/strategies/fx_05_terms_of_trade.py` - Terms of Trade: commodity-weighted ToT index vs USDBRL misalignment, 28-day holding
- `tests/test_strategies/test_fx_new.py` - 35 tests covering all 4 strategies (registration, signals, missing data, contrarian, vol-sizing, direction)
- `src/strategies/__init__.py` - Updated to import and re-export all 4 new FX strategies

## Decisions Made
- Used BaseStrategy.compute_z_score consistently across all 4 strategies for standardized z-score computation
- FX-03 contrarian threshold set at |z|>2.0 to match extreme positioning literature
- FX-04 uses scipy.stats.skew and scipy.stats.kurtosis with bias=False for unbiased moment estimates
- FX-05 commodity weights based on Brazil export composition (soybean 30%, iron ore 25%, oil 20%, sugar 15%, coffee 10%)
- Updated __init__.py to auto-import new strategies (deviation from plan: necessary for registry to discover strategies at package import time)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated __init__.py to import new strategy modules**
- **Found during:** Task 2 (verification of StrategyRegistry.list_by_asset_class)
- **Issue:** New strategies registered via decorator at import time, but were not imported by __init__.py so StrategyRegistry.list_by_asset_class(AssetClass.FX) was missing FX_02/FX_03 when accessed through the package
- **Fix:** Added imports for all 4 new strategy modules in src/strategies/__init__.py and updated __all__ list
- **Files modified:** src/strategies/__init__.py
- **Verification:** `StrategyRegistry.list_by_asset_class(AssetClass.FX)` returns all 5 FX strategies
- **Committed in:** 6f64dd5 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix for strategy discovery. Without the import, new strategies would not appear in registry queries. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 5 FX strategies now available for portfolio construction and backtesting
- StrategyRegistry returns complete FX strategy list for asset-class-based allocation
- Ready for Phase 15 Plan 02 (additional strategy implementations)

## Self-Check: PASSED

All 6 files verified present. Both commit hashes (f93660e, 6f64dd5) confirmed in git log.

---
*Phase: 15-new-trading-strategies*
*Completed: 2026-02-22*
