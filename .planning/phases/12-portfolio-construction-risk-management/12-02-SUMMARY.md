---
phase: 12-portfolio-construction-risk-management
plan: 02
subsystem: risk
tags: [var, cvar, monte-carlo, stress-testing, student-t, ledoit-wolf, cholesky, scipy, numpy, sklearn]

# Dependency graph
requires:
  - phase: 11-trading-strategies
    provides: "Strategy positions and instrument IDs referenced in stress scenarios"
provides:
  - "VaRCalculator with historical, parametric, and Monte Carlo VaR/CVaR"
  - "StressTester with 4 historical crisis replay scenarios"
  - "VaRResult and StressResult dataclasses for risk reporting"
  - "DEFAULT_SCENARIOS list with Taper Tantrum 2013, BR Crisis 2015, COVID 2020, Rate Shock 2022"
affects: [12-03-risk-monitor, 13-daily-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure computation functions + orchestrator class (VaRCalculator, StressTester)"
    - "Frozen dataclass for immutable config (StressScenario), mutable dataclass for results (VaRResult, StressResult)"
    - "Eigenvalue floor fallback for singular covariance matrices"
    - "Student-t marginals with Cholesky-correlated draws for Monte Carlo VaR"
    - "Prefix matching for instrument ID resolution in stress scenarios (DI_PRE_365 -> DI_PRE)"

key-files:
  created:
    - src/risk/var_calculator.py
    - src/risk/stress_tester.py
    - tests/test_risk/test_var_calculator.py
    - tests/test_risk/test_stress_tester.py
  modified:
    - src/risk/__init__.py
    - tests/test_risk/__init__.py

key-decisions:
  - "Eigenvalue floor at 1e-8 for near-singular covariance matrices during Cholesky decomposition"
  - "Student-t fit fallback to normal (df=1e6) when asset has < 30 observations"
  - "Uniform clipping to [1e-6, 1-1e-6] before ppf to avoid infinities in Monte Carlo"
  - "Stress scenario prefix matching uses startswith() for DI_PRE instrument family"
  - "Stress tests are advisory only -- no position modifications (locked CONTEXT.md decision)"

patterns-established:
  - "Pure function + orchestrator: compute_historical_var(), compute_parametric_var(), compute_monte_carlo_var() as pure functions; VaRCalculator as orchestrator"
  - "StressScenario frozen dataclass with dict[str, float] shocks for instrument-level shock definitions"
  - "Optional rng parameter on Monte Carlo functions for test reproducibility"

requirements-completed: [RISK-01, RISK-02, RISK-03, RISK-04]

# Metrics
duration: 7min
completed: 2026-02-22
---

# Phase 12 Plan 02: VaR/CVaR Engine + Historical Stress Testing Summary

**VaRCalculator with 3 methods (historical/parametric/Monte Carlo with Student-t marginals) and StressTester replaying 4 crisis scenarios (Taper Tantrum, BR Crisis, COVID, Rate Shock) with position-level P&L**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-22T00:25:24Z
- **Completed:** 2026-02-22T00:32:57Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Historical VaR at 95% and 99% confidence using np.percentile with tail-mean CVaR
- Parametric VaR using Gaussian assumption with analytical Expected Shortfall formula
- Monte Carlo VaR with Student-t fitted marginals, Ledoit-Wolf covariance, Cholesky-correlated draws
- Short history fallback (<252 obs) to parametric with confidence_warning
- Singular covariance handling via eigenvalue floor at 1e-8
- StressTester with 4 locked historical crisis scenarios and position-level P&L breakdown
- Prefix matching for DI instrument family (DI_PRE_365 matches DI_PRE shock)
- 36 unit tests pass across both modules with zero lint errors

## Task Commits

Each task was committed atomically:

1. **Task 1: VaRCalculator with historical, parametric, and Monte Carlo methods** - `69117f8` (feat)
2. **Task 2: StressTester with 4 historical scenarios, package exports, and stress tests** - `97eca9b` (feat)

## Files Created/Modified
- `src/risk/var_calculator.py` - VaRCalculator class with 3 VaR methods (historical, parametric, Monte Carlo), CVaR for all methods, VaRResult dataclass (347 lines)
- `src/risk/stress_tester.py` - StressTester class with 4 default historical scenarios, position-level P&L, prefix instrument matching (285 lines)
- `src/risk/__init__.py` - Package exports: VaRCalculator, VaRResult, StressTester, StressScenario, StressResult, DEFAULT_SCENARIOS
- `tests/test_risk/test_var_calculator.py` - 19 unit tests for all VaR methods, CVaR, fallback, edge cases (303 lines)
- `tests/test_risk/test_stress_tester.py` - 17 unit tests for stress scenarios, P&L, prefix matching, advisory guarantee (285 lines)
- `tests/test_risk/__init__.py` - Test package init

## Decisions Made
- Eigenvalue floor at 1e-8 (from RESEARCH.md pitfall #1) for near-singular covariance matrices
- Student-t fit falls back to normal distribution (df=1e6) when fewer than 30 observations per asset
- Uniform random values clipped to [1e-6, 1-1e-6] before ppf to avoid infinity in Monte Carlo draws
- Stress scenario instrument matching uses exact match first, then startswith() prefix match for DI_PRE family
- Stress tests are advisory only (locked decision from CONTEXT.md) -- no position modifications

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None -- no external service configuration required.

## Next Phase Readiness
- VaRCalculator and StressTester are ready for integration into RiskMonitor (Plan 12-03)
- All code is pure computation (no I/O, no database) -- can be called from backtesting or live pipeline
- 36 total tests provide confidence for downstream integration

## Self-Check: PASSED

- All 6 files verified on disk
- Both commit hashes (69117f8, 97eca9b) verified in git log

---
*Phase: 12-portfolio-construction-risk-management*
*Completed: 2026-02-22*
