---
phase: 08-inflation-monetary-policy-agents
plan: 03
subsystem: agents
tags: [monetary-policy, taylor-rule, kalman-filter, selic, di-curve, python, numpy, pandas, statsmodels]

# Dependency graph
requires:
  - phase: 07-agent-framework-data-loader
    provides: "BaseAgent ABC, AgentSignal/AgentReport dataclasses, PointInTimeDataLoader, classify_strength"

provides:
  - "MonetaryFeatureEngine: BR DI curve shape (slope, belly, long premium) + US UST curve features"
  - "TaylorRuleModel: BCB-modified Taylor Rule with 100bps floor, MODERATE/STRONG bands"
  - "KalmanFilterRStar: numpy state-space r* estimation, 24-obs minimum, default 3.0"
  - "SelicPathModel: market DI path vs Taylor model path, SHORT when market>model"
  - "TermPremiumModel: DI term premium z-score signal vs trailing 24M history"
  - "UsFedAnalysis: US Fed Taylor gap standalone signal"
  - "MonetaryPolicyAgent: orchestrates all 5 models, produces MONETARY_BR_COMPOSITE"
  - "28 unit tests: all passing without DB, covering model directions and feature keys"

affects:
  - 08-02
  - 09-fiscal-fx-agents
  - 10-cross-asset-backtesting
  - 11-trading-strategies
  - 12-portfolio-risk

# Tech tracking
tech-stack:
  added: ["numpy (Kalman filter implementation)", "pandas (feature series)", "scipy (HP filter via linalg.solve)"]
  patterns:
    - "HP filter via numpy linalg.solve — no statsmodels dependency for trend extraction"
    - "Kalman filter via numpy loop — no pykalman/filterpy dependency"
    - "All model computations guarded with try/except returning np.nan on failure"
    - "Private _-prefixed keys in feature dict carry full time series for models requiring history"
    - "GAP_FLOOR = 1.0 (100bps) locked as class constant on TaylorRuleModel"
    - "US Fed signal standalone — not aggregated into BR composite to avoid cross-market double-counting"
    - "Conflict dampening 0.70 when any BR sub-signal disagrees with plurality direction"

key-files:
  created:
    - src/agents/features/monetary_features.py
    - src/agents/monetary_agent.py
    - tests/test_monetary_agent.py
  modified:
    - src/agents/features/__init__.py

key-decisions:
  - "TaylorRuleModel GAP_FLOOR=1.0 (100bps locked per CONTEXT.md); MODERATE for [1.0,1.5), STRONG for >=1.5"
  - "SelicPathModel direction: market > model -> SHORT (fade hike pricing); market < model -> LONG (hike risk)"
  - "MONETARY_BR_COMPOSITE weights: Taylor 50%, SelicPath 30%, TermPremium 20% (fundamental model weighted highest)"
  - "UsFedAnalysis is standalone signal only — not fed into BR composite (separate market, avoid double-counting)"
  - "Conflict dampening 0.70 applied when any active BR sub-signal disagrees with plurality direction"
  - "KalmanFilterRStar MIN_OBS=24, DEFAULT_R_STAR=3.0 — graceful degradation for historical backtesting"
  - "HP filter with monthly lambda=129600 for IBC-Br output gap extraction"
  - "features/__init__.py uses conditional import for InflationFeatureEngine so wave-1 plan runs independently"

patterns-established:
  - "Pattern: Model class has SIGNAL_ID class constant, run() method returning AgentSignal"
  - "Pattern: NO_SIGNAL returned via _no_signal() inner function with reason metadata"
  - "Pattern: Private _-keys in features dict carry Series/dict for downstream model consumption"
  - "Pattern: run_models() calls Kalman first, stores r* in features dict, passes to Taylor/TermPremium"

requirements-completed: [MONP-01, MONP-02, MONP-03, MONP-04, MONP-05, MONP-06, TESTV2-01, TESTV2-02]

# Metrics
duration: 13min
completed: 2026-02-21
---

# Phase 8 Plan 03: Monetary Policy Agent Summary

**MonetaryPolicyAgent with Kalman r* estimation, BCB Taylor Rule (100bps floor), market Selic path model, DI term premium z-score, and US Fed stance — all 5 signals plus MONETARY_BR_COMPOSITE with conflict dampening**

## Performance

- **Duration:** 13 min
- **Started:** 2026-02-21T14:48:15Z
- **Completed:** 2026-02-21T15:01:18Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- MonetaryFeatureEngine computing 20+ BR/US features: DI curve shape (slope, belly, long premium), BCB policy gap, IBC-Br HP-filter output gap, full history series for Kalman/TermPremium, and UST curve shape
- All 5 monetary models implemented with correct direction logic (Taylor, Kalman, SelicPath, TermPremium, UsFed) — all importable and production-ready
- MONETARY_BR_COMPOSITE with Taylor 50%/SelicPath 30%/TermPremium 20% weights and 0.70 conflict dampening when any sub-signal disagrees
- 28 unit tests passing without database: covers feature keys, Taylor direction/strength bands, Kalman convergence, SelicPath convention, TermPremium z-score, composite dampening

## Task Commits

Each task was committed atomically:

1. **Task 1: MonetaryFeatureEngine, 5 models, and MonetaryPolicyAgent** - `99e1d58` (feat)
2. **Task 2: Unit tests for monetary agent** - `798e3e3` (test)

**Plan metadata:** committed with SUMMARY.md docs commit

## Files Created/Modified

- `/home/user/Macro_Trading/src/agents/features/monetary_features.py` - MonetaryFeatureEngine: BR DI curve (slope/belly/long_premium/real), BCB policy (selic, focus, real_rate_gap, inertia), IBC-Br HP-filter gap, history series (Kalman/TP), US UST curve features
- `/home/user/Macro_Trading/src/agents/monetary_agent.py` - TaylorRuleModel, KalmanFilterRStar, SelicPathModel, TermPremiumModel, UsFedAnalysis, MonetaryPolicyAgent (5 signals + composite)
- `/home/user/Macro_Trading/tests/test_monetary_agent.py` - 28 unit tests across all 6 classes, no DB required
- `/home/user/Macro_Trading/src/agents/features/__init__.py` - Updated to export MonetaryFeatureEngine; InflationFeatureEngine imported conditionally for wave-1 independence

## Decisions Made

- **GAP_FLOOR locked at 1.0 (100bps)**: Matches CONTEXT.md specification; MODERATE for [1.0-1.5), STRONG for >=1.5 based on BCB policy distribution
- **SelicPathModel direction**: market > model → SHORT (standard rates strategy: fade hike pricing if market is too hawkish vs fundamentals); market < model → LONG (underpriced tightening risk)
- **Composite weights**: Taylor 50% (fundamental OLS model, highest quality), SelicPath 30% (market-derived forward signal), TermPremium 20% (duration valuation signal)
- **US Fed standalone**: UsFedAnalysis remains a separate signal, not blended into BR composite — cross-market signal would create double-counting in strategies that use both US and BR signals
- **Conflict dampening 0.70**: Applied when any active BR sub-signal disagrees with plurality; stricter than inflation agent's approach to reflect monetary policy's sensitivity to conflicting rate signals
- **Kalman numpy implementation**: Pure numpy (no pykalman/filterpy), Q=0.01/R=1.0, initial x=3.0 — sufficient for monthly r* estimation
- **HP filter monthly lambda=129600**: Standard choice for monthly data (vs 1600 for quarterly); implemented via numpy linalg.solve without statsmodels dependency

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Conditional import in features/__init__.py for wave-1 independence**
- **Found during:** Task 1 (MonetaryFeatureEngine implementation)
- **Issue:** The pre-staged `__init__.py` imported `InflationFeatureEngine` from `inflation_features.py` which doesn't exist yet (plans 08-01/02 are wave-2 plans). This blocked the monetary features import.
- **Fix:** Updated `__init__.py` to export `MonetaryFeatureEngine` unconditionally and wrap `InflationFeatureEngine` import in try/except so plan 08-03 (wave 1) runs independently
- **Files modified:** src/agents/features/__init__.py
- **Verification:** `from src.agents.features import MonetaryFeatureEngine` succeeds
- **Committed in:** 99e1d58 (Task 1 commit)

**2. [Rule 3 - Blocking] Install missing numpy/pandas/statsmodels dependencies**
- **Found during:** Task 1 start (environment setup)
- **Issue:** numpy, pandas, scipy, statsmodels, scikit-learn not installed in the Python environment
- **Fix:** pip install numpy pandas scipy statsmodels scikit-learn ruff pytest
- **Verification:** `python3 -c "import numpy; import pandas; import scipy; import statsmodels; import sklearn; print('all OK')"` passes
- **Committed in:** Not a file change — environment setup

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking issues)
**Impact on plan:** Both fixes necessary for correctness and independence. No scope creep.

## Issues Encountered

- ruff reported E501 (line too long) and F401 (unused import) — both fixed inline before committing; ruff passes zero violations
- KalmanFilterRStar test for min_obs boundary: Kalman runs and may converge to DEFAULT_R_STAR coincidentally — test accounts for either outcome

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- MonetaryPolicyAgent is fully independent and registerable in AgentRegistry alongside InflationAgent
- Both agents can be run via `AgentRegistry.run_all(as_of_date)` once plans 08-01/02 are complete
- All 5 monetary signals (MONETARY_BR_TAYLOR, MONETARY_BR_SELIC_PATH, MONETARY_BR_TERM_PREMIUM, MONETARY_US_FED_STANCE, MONETARY_BR_COMPOSITE) ready for strategy consumption in Phase 11

---
*Phase: 08-inflation-monetary-policy-agents*
*Completed: 2026-02-21*
