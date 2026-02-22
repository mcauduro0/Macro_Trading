---
phase: 12-portfolio-construction-risk-management
plan: 01
subsystem: portfolio
tags: [signal-aggregation, risk-parity, regime-scaling, conviction-overlay, capital-allocation, scipy, ledoit-wolf]

# Dependency graph
requires:
  - phase: 07-agent-framework
    provides: "AgentReport, AgentSignal dataclasses"
  - phase: 11-trading-strategies
    provides: "StrategyPosition, BaseStrategy, STRENGTH_MAP, ALL_STRATEGIES"
  - phase: 10-backtesting-engine
    provides: "Portfolio class with rebalance pattern"
provides:
  - "SignalAggregator: weighted vote consensus per asset class from agent signals"
  - "PortfolioConstructor: risk parity + conviction overlay + regime scaling"
  - "CapitalAllocator: constraint enforcement with drift-triggered rebalancing"
  - "AggregatedSignal, PortfolioTarget, AllocationResult dataclasses"
affects: [12-02, 12-03, 13-orchestration, risk-engine]

# Tech tracking
tech-stack:
  added: [scipy.optimize.minimize, sklearn.covariance.LedoitWolf]
  patterns: [risk-parity-SLSQP, regime-gradual-transition, bilateral-veto, constraint-pipeline]

key-files:
  created:
    - src/portfolio/__init__.py
    - src/portfolio/signal_aggregator.py
    - src/portfolio/portfolio_constructor.py
    - src/portfolio/capital_allocator.py
    - tests/test_portfolio/__init__.py
    - tests/test_portfolio/test_signal_aggregator.py
    - tests/test_portfolio/test_portfolio_constructor.py
    - tests/test_portfolio/test_capital_allocator.py
  modified: []

key-decisions:
  - "DEFAULT_AGENT_WEIGHTS tuned per domain: cross_asset_agent highest for EQUITY_INDEX (0.45) and COMMODITY (0.55), monetary_agent highest for FIXED_INCOME (0.35)"
  - "Bilateral veto at |regime_score| > 0.7 reduces net_score by 50% regardless of direction (both risk-off and euphoria/risk-on extremes)"
  - "Risk parity uses SLSQP with ftol=1e-12, bounds [0.01, 1.0], Ledoit-Wolf covariance; falls back to equal weights with < 60 observations"
  - "Regime thresholds: > 0.3 = RISK_OFF (0.4x), < -0.3 = RISK_ON (1.0x), else NEUTRAL (0.7x)"
  - "Gradual regime transition: linear ramp over 3 days from previous to target scale"
  - "Conflict dampening locked at 0.60 (40% reduction) within [0.50, 0.70] range"
  - "Constraint pipeline order: single position (25%) -> asset class concentration (50%) -> leverage (3x) -> drift check (5%)"

patterns-established:
  - "Pure computation modules: no database/IO access in portfolio package"
  - "Diagnostic weight stages: risk_parity_weights -> conviction_weights -> final weights in PortfolioTarget"
  - "Strategy-to-asset-class inference from strategy_id prefix (RATES_/FX_/EQ_/COMM_)"
  - "Frozen AllocationConstraints dataclass for immutable constraint configuration"

requirements-completed: [PORT-01, PORT-02, PORT-03, PORT-04]

# Metrics
duration: 12min
completed: 2026-02-22
---

# Phase 12 Plan 01: Signal Aggregation & Portfolio Construction Summary

**Weighted vote signal aggregation with bilateral CrossAsset veto, risk-parity portfolio construction via SLSQP/Ledoit-Wolf, conviction overlay with regime scaling, and 4-constraint capital allocation with drift-triggered rebalancing**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-22T00:25:29Z
- **Completed:** 2026-02-22T00:37:25Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- SignalAggregator combines 5 agent signals into directional consensus per asset class using domain-tuned weighted vote, with conflict detection and bilateral CrossAsset veto
- PortfolioConstructor computes risk-parity base weights (scipy SLSQP + Ledoit-Wolf covariance), applies conviction overlay scaling by signal strength/confidence, and regime-dependent scaling with gradual 3-day transitions
- CapitalAllocator enforces 4 constraint types (single position 25%, asset class concentration 50%, leverage 3x, risk budget 20%) with drift-triggered rebalancing at 5% threshold
- 29 comprehensive unit tests pass with zero lint errors across all 3 modules

## Task Commits

Each task was committed atomically:

1. **Task 1: SignalAggregator and PortfolioConstructor with dataclasses** - `7d05bf8` (feat)
2. **Task 2: CapitalAllocator, package exports, and all unit tests** - `933ef24` (feat)

## Files Created/Modified
- `src/portfolio/__init__.py` - Package exports: 8 public classes
- `src/portfolio/signal_aggregator.py` - SignalAggregator class, AggregatedSignal dataclass, DEFAULT_AGENT_WEIGHTS (408 lines)
- `src/portfolio/portfolio_constructor.py` - PortfolioConstructor class, PortfolioTarget, RegimeState, risk parity optimizer (471 lines)
- `src/portfolio/capital_allocator.py` - CapitalAllocator class, AllocationConstraints, AllocationResult (354 lines)
- `tests/test_portfolio/__init__.py` - Empty init
- `tests/test_portfolio/test_signal_aggregator.py` - 10 tests: weighted vote, conflicts, veto, missing agents (364 lines)
- `tests/test_portfolio/test_portfolio_constructor.py` - 9 tests: risk parity, conviction, regime, dampening (264 lines)
- `tests/test_portfolio/test_capital_allocator.py` - 9 tests: constraints, drift, trades, risk budget (193 lines)

## Decisions Made
- DEFAULT_AGENT_WEIGHTS tuned per domain: cross_asset_agent highest for EQUITY_INDEX (0.45) and COMMODITY (0.55), monetary_agent highest for FIXED_INCOME (0.35)
- Bilateral veto at |regime_score| > 0.7: reduces net_score by 50% for both extreme risk-off and euphoria/risk-on, protecting against both capital destruction and over-leveraging
- Risk parity SLSQP with ftol=1e-12, bounds [0.01, 1.0], Ledoit-Wolf covariance; equal weight fallback when < 60 observations
- Regime thresholds from RESEARCH.md: > 0.3 = RISK_OFF (0.4x), < -0.3 = RISK_ON (1.0x), else NEUTRAL (0.7x)
- Gradual regime transition over 3 days (linear ramp) to avoid whipsaw
- Conflict dampening locked at 0.60 (40% reduction) within enforced [0.50, 0.70] range
- Constraint pipeline: single position -> asset class -> leverage -> drift (order matters for correctness)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing Python dependencies**
- **Found during:** Task 1 (import verification)
- **Issue:** sqlalchemy, pydantic, pydantic-settings, asyncpg, psycopg2-binary, pandas not installed in current environment (required by upstream modules in import chain)
- **Fix:** pip install for each missing dependency
- **Files modified:** None (runtime dependencies only)
- **Verification:** All imports succeed
- **Committed in:** N/A (pip install, not committed)

**2. [Rule 1 - Bug] Fixed leverage cap test with correct weights**
- **Found during:** Task 2 (test execution)
- **Issue:** test_leverage_cap used weights > 0.25 per position which got clamped by single position limit first, making total abs weight < 3.0 (leverage cap never triggered)
- **Fix:** Changed test to use 16 positions at 0.25 each (total abs = 4.0 > 3.0, each under single position limit)
- **Files modified:** tests/test_portfolio/test_capital_allocator.py
- **Verification:** Test passes, leverage violation correctly reported
- **Committed in:** 933ef24 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Minimal. Dependency installation is environment setup. Test fix was a test logic correction.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Portfolio pipeline complete: signals -> aggregation -> construction -> allocation -> trades
- Ready for Plan 12-02 (Risk Engine: VaR, CVaR, stress testing) which builds on PortfolioTarget
- Ready for Plan 12-03 (Integration & Pipeline orchestration) which wires all components together
- All modules are pure computation (no database/IO) enabling easy testing and integration

## Self-Check: PASSED

- All 8 created files verified on disk
- Both task commits (7d05bf8, 933ef24) verified in git log
- 29/29 tests pass
- Zero lint errors

---
*Phase: 12-portfolio-construction-risk-management*
*Completed: 2026-02-22*
