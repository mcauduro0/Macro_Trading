---
phase: 14-backtesting-engine-v2-strategy-framework
plan: 01
subsystem: strategies
tags: [strategy-registry, strategy-signal, z-score, alembic, sqlalchemy, dataclass]

# Dependency graph
requires:
  - phase: 09-strategy-implementation
    provides: "8 concrete strategies with ALL_STRATEGIES dict, BaseStrategy ABC"
  - phase: 10-backtesting-engine
    provides: "BacktestResultRecord ORM model, backtest_results table"
provides:
  - "StrategySignal dataclass with 15 fields (z_score, entry_level, stop_loss, take_profit, etc.)"
  - "StrategyRegistry with decorator-based registration, get, list_all, list_by_asset_class, instantiate"
  - "StrategyStateRecord ORM model for strategy_state table"
  - "BacktestResultRecord v2 columns (run_timestamp, params_json, daily_returns_json, avg_holding_days)"
  - "Alembic migration 006 for strategy_state and backtest_results v2"
  - "BaseStrategy utility methods: compute_z_score, size_from_conviction, classify_strength"
affects: [14-02-PLAN, 14-03-PLAN, 15-new-strategies, backtesting-engine-v2]

# Tech tracking
tech-stack:
  added: []
  patterns: [decorator-based-registry, z-score-signal-quantification, sigmoid-position-sizing]

key-files:
  created:
    - src/strategies/registry.py
    - src/core/models/strategy_state.py
    - alembic/versions/006_add_strategy_state_enhance_backtest_results.py
    - tests/test_strategies/test_registry.py
  modified:
    - src/strategies/base.py
    - src/strategies/__init__.py
    - src/core/enums.py
    - src/core/models/backtest_results.py
    - src/core/models/__init__.py
    - alembic/env.py
    - tests/test_strategies/test_base.py

key-decisions:
  - "Auto-register existing 8 strategies in StrategyRegistry at module load via __init__.py for backward compat"
  - "Extract asset_class metadata from module-level StrategyConfig constants for registry filtering"
  - "Migration 006 adds columns as nullable to preserve existing backtest_results data"

patterns-established:
  - "Decorator registration: new strategies use @StrategyRegistry.register(id, asset_class, instruments)"
  - "Z-score quantification: strategies compute z-score and use classify_strength/size_from_conviction"
  - "Registry coexistence: ALL_STRATEGIES dict and StrategyRegistry both populated"

requirements-completed: [SFWK-01, SFWK-02, SFWK-03, SFWK-04]

# Metrics
duration: 7min
completed: 2026-02-22
---

# Phase 14 Plan 01: Strategy Framework Foundation Summary

**StrategySignal dataclass with z-score quantification, decorator-based StrategyRegistry replacing manual dict, and strategy_state/backtest_results v2 database schema**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-22T13:54:13Z
- **Completed:** 2026-02-22T14:01:16Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments
- Enhanced BaseStrategy with StrategySignal dataclass (15 SFWK-01 fields) and utility methods (compute_z_score, size_from_conviction, classify_strength)
- Created StrategyRegistry with decorator-based registration and asset-class filtering, auto-populated with existing 8 strategies
- Created StrategyStateRecord ORM model and Alembic migration 006 for strategy_state table and backtest_results v2 columns
- Added 22 new tests covering StrategySignal, BaseStrategy utilities, and StrategyRegistry (53 total pass)

## Task Commits

Each task was committed atomically:

1. **Task 1: Enhanced StrategySignal, updated BaseStrategy, and StrategyRegistry** - `1dd3e63` (feat)
2. **Task 2: Database models and Alembic migration for strategy_state and backtest_results v2** - `7d351f6` (feat)
3. **Task 3: Tests for StrategySignal, BaseStrategy utilities, and StrategyRegistry** - `15c1f12` (test)

## Files Created/Modified
- `src/strategies/base.py` - Added StrategySignal dataclass, compute_z_score, size_from_conviction, classify_strength
- `src/strategies/registry.py` - StrategyRegistry with register decorator, get, list_all, list_by_asset_class, instantiate, instantiate_all
- `src/strategies/__init__.py` - Re-exports StrategySignal and StrategyRegistry, auto-registers existing 8 strategies
- `src/core/enums.py` - Added v3.0 AssetClass values (RATES_BR, RATES_US, INFLATION_BR, etc.)
- `src/core/models/strategy_state.py` - StrategyStateRecord ORM model with composite (strategy_id, timestamp DESC) index
- `src/core/models/backtest_results.py` - Added v2 columns: run_timestamp, params_json, daily_returns_json, avg_holding_days
- `src/core/models/__init__.py` - Added StrategyStateRecord to exports
- `alembic/env.py` - Added strategy_state and backtest_results model imports
- `alembic/versions/006_add_strategy_state_enhance_backtest_results.py` - Migration creating strategy_state table and adding v2 columns
- `tests/test_strategies/test_base.py` - Added 13 tests for StrategySignal and BaseStrategy utilities
- `tests/test_strategies/test_registry.py` - 9 tests for StrategyRegistry

## Decisions Made
- Auto-register existing 8 strategies in StrategyRegistry at module load time (in __init__.py) so both ALL_STRATEGIES dict and StrategyRegistry are populated without modifying individual strategy files
- Extract asset_class and instruments metadata from module-level StrategyConfig constants for registry filtering rather than requiring each strategy to define class attributes
- Add backtest_results v2 columns as nullable to preserve existing data (no migration issues)

## Deviations from Plan

None - plan executed exactly as written. The StrategySignal dataclass, BaseStrategy utility methods, and AssetClass enum additions were already present as uncommitted work (from planning) and were included in the Task 1 commit.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- StrategySignal and StrategyRegistry are ready for BacktestEngine v2 (Plan 14-02)
- strategy_state table schema is ready for signal persistence
- backtest_results v2 columns ready for enhanced metrics storage
- Existing 8 strategies continue to work via both ALL_STRATEGIES and StrategyRegistry
- New strategies (Phase 15) can use @StrategyRegistry.register decorator directly

## Self-Check: PASSED

- All 11 files verified as existing on disk
- All 3 task commits verified in git log (1dd3e63, 7d351f6, 15c1f12)

---
*Phase: 14-backtesting-engine-v2-strategy-framework*
*Completed: 2026-02-22*
