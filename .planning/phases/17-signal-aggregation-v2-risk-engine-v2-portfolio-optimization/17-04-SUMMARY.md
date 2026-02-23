---
phase: 17-signal-aggregation-v2-risk-engine-v2-portfolio-optimization
plan: 04
subsystem: portfolio
tags: [black-litterman, mean-variance, position-sizing, kelly-criterion, portfolio-optimization, rebalancing, alembic]

# Dependency graph
requires:
  - phase: 17-01
    provides: "SignalAggregatorV2 with regime-aware aggregation"
  - phase: 17-02
    provides: "VaR decomposition with marginal/component VaR for risk-budget sizing"
provides:
  - "BlackLitterman model with regime-adjusted view confidence and P/Q matrices"
  - "PortfolioOptimizer with mean-variance SLSQP optimization and rebalance thresholds"
  - "PositionSizer with vol_target, fractional_kelly (0.5x), risk_budget_size methods"
  - "PortfolioStateRecord ORM model with strategy_attribution JSONB column"
  - "Alembic migration 008: portfolio_state hypertable with compression policy"
  - "3 new portfolio API endpoints: /target, /rebalance-trades, /attribution"
affects: [dashboard-v3, live-trading, execution-management]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mean-variance utility maximization via scipy.minimize SLSQP with leverage constraints"
    - "Signal+drift dual-threshold rebalancing (signal_change > 0.15 OR drift > 0.05)"
    - "Soft position limits: 20% override margin when conviction > 0.8"
    - "Portfolio state hypertable with JSONB strategy attribution for position tracing"

key-files:
  created:
    - src/portfolio/portfolio_optimizer.py
    - src/portfolio/position_sizer.py
    - src/core/models/portfolio_state.py
    - alembic/versions/008_create_portfolio_state_table.py
    - tests/test_black_litterman.py
    - tests/test_position_sizer.py
    - tests/test_portfolio_api_v2.py
  modified:
    - src/core/models/__init__.py
    - src/api/routes/portfolio_api.py

key-decisions:
  - "size_portfolio uses raw (unclamped) sizing methods to allow soft limit overrides to take effect"
  - "Rebalance triggers on signal_change > 0.15 OR max position drift > 0.05"
  - "Portfolio API endpoints use sample/placeholder data for demonstration; live data integration deferred"
  - "portfolio_state hypertable compressed after 30 days with instrument segmentby"

patterns-established:
  - "PortfolioOptimizer.optimize_with_bl() bridges BL posterior to MV optimization"
  - "PositionSizer._raw_* internal methods for unclamped sizing before conviction-based limit selection"
  - "Strategy attribution stored as JSONB dict {strategy_id: contribution_weight} per position"

requirements-completed: [POPT-01, POPT-02, POPT-03, POPT-04, POPT-05]

# Metrics
duration: 7min
completed: 2026-02-23
---

# Phase 17 Plan 04: Portfolio Optimization Summary

**Mean-variance optimizer (scipy SLSQP) with Black-Litterman posterior inputs, PositionSizer offering vol-target/half-Kelly/risk-budget methods with soft limits, portfolio_state hypertable via Alembic 008, and 3 new API endpoints for target weights, rebalance trades, and strategy attribution**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-23T00:43:27Z
- **Completed:** 2026-02-23T00:50:27Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- PortfolioOptimizer with configurable constraints (min/max weight, leverage, long_only) using scipy SLSQP mean-variance utility maximization
- PositionSizer with 3 sizing methods: vol_target (inverse volatility), fractional_kelly (0.5x half Kelly), risk_budget_size (component VaR proportional)
- Soft position limits allow 20% override when conviction > 0.8, using raw unclamped sizing internally
- Signal+drift dual-threshold rebalancing: should_rebalance() triggers on signal_change > 0.15 OR max drift > 0.05
- PortfolioStateRecord ORM model with strategy_attribution JSONB for tracing which strategies contributed to each position
- Alembic migration 008 creates portfolio_state hypertable with 30-day compression policy
- 3 new API endpoints: /portfolio/target, /portfolio/rebalance-trades, /portfolio/attribution
- Existing /portfolio/current and /portfolio/risk endpoints preserved (backward compatible)
- 41 total tests passing (11 BL + 19 sizer + 11 API)

## Task Commits

Each task was committed atomically:

1. **Task 1: Black-Litterman tests, mean-variance optimizer, and PositionSizer** - `b810ed1` (feat)
2. **Task 2: Portfolio state ORM, migration 008, and 3 new API endpoints** - `74c0b70` (feat)

## Files Created/Modified

- `src/portfolio/portfolio_optimizer.py` - Mean-variance optimizer with SLSQP, rebalance threshold logic (252 lines)
- `src/portfolio/position_sizer.py` - 3 sizing methods with soft limit overrides (199 lines)
- `src/core/models/portfolio_state.py` - PortfolioStateRecord ORM with JSONB strategy_attribution (64 lines)
- `alembic/versions/008_create_portfolio_state_table.py` - Hypertable migration with compression (74 lines)
- `src/api/routes/portfolio_api.py` - Enhanced with /target, /rebalance-trades, /attribution (412 lines)
- `src/core/models/__init__.py` - Registered PortfolioStateRecord
- `tests/test_black_litterman.py` - Equilibrium, views, posterior, regime tests (266 lines)
- `tests/test_position_sizer.py` - vol_target, kelly, risk_budget, soft limits tests (207 lines)
- `tests/test_portfolio_api_v2.py` - API endpoint tests with envelope validation (155 lines)

## Decisions Made

- size_portfolio uses raw (unclamped) internal sizing methods (_raw_vol_target_size, etc.) before applying conviction-based limit selection, allowing soft override to work correctly even though individual methods clamp by default
- Rebalance dual-threshold: signal_change > 0.15 OR max position drift > 0.05 (both are per-decision from plan)
- Portfolio API endpoints use sample/placeholder data for demonstration purposes; integration with live strategy signals deferred to production orchestration phase
- portfolio_state hypertable uses instrument as segmentby column for compression efficiency

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed soft limit override ordering in PositionSizer**
- **Found during:** Task 1 (PositionSizer implementation)
- **Issue:** Individual sizing methods (vol_target_size, fractional_kelly_size) clamped to max_position before size_portfolio could apply the soft limit override for high-conviction positions
- **Fix:** Added internal _raw_* methods that compute unclamped sizes; size_portfolio applies conviction-based limit selection on raw sizes
- **Files modified:** src/portfolio/position_sizer.py
- **Verification:** test_high_conviction_allows_override passes (0.30 = 0.25 * 1.2)
- **Committed in:** b810ed1 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for correct soft limit behavior. No scope creep.

## Issues Encountered

None beyond the auto-fixed soft limit ordering issue.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Portfolio optimization layer complete: BL model -> MV optimizer -> position sizing
- All 3 new endpoints ready for dashboard integration
- portfolio_state table ready for position persistence via daily pipeline
- PositionSizer ready to receive VaR decomposition data from Risk Engine v2 (Plan 02)
- Phase 17 fully complete (4/4 plans done)

## Self-Check: PASSED

- All 9 files verified present
- Both task commits verified (b810ed1, 74c0b70) in git log
- Line counts: portfolio_optimizer.py 252 (min 100), position_sizer.py 199 (min 100), portfolio_state.py 64 (min 30), migration 008 74 (min 30), portfolio_api.py 412 (min 150), test_black_litterman.py 266 (min 80), test_position_sizer.py 207 (min 60), test_portfolio_api_v2.py 155 (min 50)
- 41/41 tests passing
- Import verification OK for all 4 modules (BL, Optimizer, Sizer, ORM)

---
*Phase: 17-signal-aggregation-v2-risk-engine-v2-portfolio-optimization*
*Completed: 2026-02-23*
