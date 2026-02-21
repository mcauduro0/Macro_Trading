---
phase: 08-inflation-monetary-policy-agents
plan: 01
subsystem: agents
tags: [inflation, ipca, phillips-curve, statsmodels, ols, seasonal-decomposition, ibge-weights, hp-filter, bcb, fred, feature-engine]

# Dependency graph
requires:
  - phase: 07-agent-framework-data-loader
    provides: BaseAgent ABC, AgentSignal dataclass, PointInTimeDataLoader with PIT-correct queries

provides:
  - InflationFeatureEngine with 45+ BR/US inflation features (src/agents/features/inflation_features.py)
  - src/agents/features/__init__.py package exposing InflationFeatureEngine
  - InflationAgent stub with fully implemented load_data() and compute_features()
  - PhillipsCurveModel: expectations-augmented OLS Phillips Curve on 120M rolling window
  - IpcaBottomUpModel: 9-component seasonal IBGE-weighted 12M IPCA forecast

affects:
  - 08-02-inflation-monetary-policy-agents (orchestrates InflationAgent, adds remaining sub-models)
  - 08-03-inflation-monetary-policy-agents (adds MonetaryFeatureEngine to features package)

# Tech tracking
tech-stack:
  added: [statsmodels OLS, statsmodels HP filter (hpfilter), pandas groupby seasonal, numpy compounding]
  patterns: [feature-engine delegation (Agent -> FeatureEngine), private _raw_* keys for model data prep, try/except per series load with None return]

key-files:
  created:
    - src/agents/features/__init__.py
    - src/agents/features/inflation_features.py
    - src/agents/inflation_agent.py
  modified:
    - src/agents/features/monetary_features.py (pre-existing E501 ruff fix)

key-decisions:
  - "InflationFeatureEngine delegates YoY computation to compounded 12M product ((prod(1+mom/100)-1)*100) not simple sum — matches IBGE methodology"
  - "_raw_ols_data and _raw_components are private keys in features dict — models receive pre-assembled data, not raw loaders"
  - "IBC-Br uses 10Y lookback (3650 days) for HP filter and OLS — shorter windows distort trend estimate"
  - "load_data() wraps each series in try/except returning None — InflationFeatureEngine gracefully handles all-None input"
  - "USDBRL/CRB use market_data (get_market_data) not macro_series — FX and commodities are intraday not macro releases"
  - "Focus combined into single multi-column DataFrame — 12M and EOY expectations co-indexed"
  - "IpcaBottomUpModel renormalizes IBGE weights to available components — partial coverage produces valid signal"

patterns-established:
  - "FeatureEngine pattern: stateless compute(data, as_of_date) -> dict — no DB access in feature class"
  - "Model pattern: run(features, as_of_date) -> AgentSignal — self-contained with _no_signal() helper"
  - "No-fail data loading: every series wrapped in try/except, None on failure, np.nan for missing features"
  - "Private _raw_* keys in features dict: agent prepares model-specific data during compute_features()"

requirements-completed: [INFL-01, INFL-02, INFL-03]

# Metrics
duration: 11min
completed: 2026-02-21
---

# Phase 08 Plan 01: Inflation Feature Engine and Core Models Summary

**InflationFeatureEngine with 45+ BR/US features (HP filter, 9-component IBGE, Phillips Curve OLS) and InflationAgent stub with PhillipsCurveModel and IpcaBottomUpModel**

## Performance

- **Duration:** 11 min
- **Started:** 2026-02-21T14:45:53Z
- **Completed:** 2026-02-21T14:57:00Z
- **Tasks:** 2
- **Files modified:** 4 (3 created, 1 pre-existing fix)

## Accomplishments

- Created `InflationFeatureEngine.compute()` returning 45+ keys: 30 BR features (IPCA headline/cores/9 components/sub-indices/diffusion/focus/IBC-Br output gap/FX passthrough/CRB) and 15 US features (CPI core, PCE core, PCE 3M SAAR, breakevens 5Y/10Y, Michigan 1Y/5Y, supercore, target gap)
- Implemented HP filter (lambda=1600) on IBC-Br for output gap computation, with `_raw_ols_data` DataFrame assembled for Phillips Curve OLS
- Created `PhillipsCurveModel` fitting OLS on 120-month rolling window; returns LONG when predicted core > BCB target + 0.5pp, NO_SIGNAL when fewer than 36 observations
- Created `IpcaBottomUpModel` computing trailing 5-year seasonal factors per calendar month, projecting 12M compounded IPCA from 9 IBGE-weighted components
- Created `InflationAgent` stub with fully implemented `load_data()` (20+ series, all BCB/FRED/market wrapped in try/except) and `compute_features()` (delegates to InflationFeatureEngine)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create InflationFeatureEngine with 30 BR + 15 US features** - `5e2389d` (feat)
2. **Task 2: Create InflationAgent stub, PhillipsCurveModel, and IpcaBottomUpModel** - `a4c139e` (feat)

**Plan metadata:** TBD (docs commit)

## Files Created/Modified

- `src/agents/features/__init__.py` - Package init re-exporting InflationFeatureEngine
- `src/agents/features/inflation_features.py` - InflationFeatureEngine with compute() and all private helpers
- `src/agents/inflation_agent.py` - InflationAgent, PhillipsCurveModel, IpcaBottomUpModel
- `src/agents/features/monetary_features.py` - Fixed pre-existing E501 line-too-long on line 291

## Decisions Made

- **Compounded YoY calculation:** Used `prod(1 + mom/100) - 1` multiplied by 100 for all YoY features — matches IBGE's official methodology vs simple sum approximation
- **Private `_raw_*` keys:** `_raw_ols_data` (DataFrame with OLS columns) and `_raw_components` (dict of per-component DataFrames) are assembled during `compute_features()` so model classes receive ready-to-use data without re-loading
- **10Y lookback for IBC-Br:** `get_macro_series("BCB-24363", ..., lookback_days=3650)` — HP filter and OLS on 120-month window both need full 10Y history
- **USDBRL/CRB as market_data:** FX and commodity instruments retrieved via `get_market_data()` not `get_macro_series()` — reflects their intraday nature vs lagged macro releases
- **Focus merged DataFrame:** 12M and EOY expectations co-indexed in one DataFrame — `InflationFeatureEngine._br_focus()` reads columns positionally with named fallbacks
- **IpcaBottomUpModel weight renormalization:** Divides by sum of available component weights — 7/9 components present still produces a valid proportional forecast

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing E501 ruff violation in monetary_features.py**
- **Found during:** Task 2 (ruff check on features/ directory)
- **Issue:** Line 291 of monetary_features.py was 122 chars, exceeding 120-char limit — blocked passing `ruff check src/agents/features/`
- **Fix:** Extracted boolean condition to named variable `no_data` on preceding line
- **Files modified:** src/agents/features/monetary_features.py
- **Verification:** `ruff check src/agents/features/ src/agents/inflation_agent.py` passes with zero errors
- **Committed in:** a4c139e (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug fix)
**Impact on plan:** Fix was in a pre-existing file from an earlier plan. Required to pass `ruff check src/agents/features/` as specified in Task 1 done criteria.

## Issues Encountered

- `sqlalchemy`, `pydantic`, and `asyncpg` were not installed in the current Python environment. Installed missing packages via `pip install` before verification (Rule 3 - Blocking issue). No code changes required.

## Next Phase Readiness

- Plan 08-02 can now import `InflationAgent`, `PhillipsCurveModel`, and `IpcaBottomUpModel` directly
- `run_models()` stub is ready to be populated with all 4 sub-models (Phillips Curve, Bottom-Up, Regime, Breakout)
- `generate_narrative()` stub ready for LLM-backed narrative generation
- `InflationFeatureEngine` fully tested — returns np.nan gracefully for all missing series

---
*Phase: 08-inflation-monetary-policy-agents*
*Completed: 2026-02-21*
