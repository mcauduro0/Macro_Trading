---
phase: 09-fiscal-fx-equilibrium-agents
plan: 01
subsystem: agents
tags: [fiscal, debt-sustainability, brazil, dsa, primary-balance, fiscal-dominance, cftc, brl]

# Dependency graph
requires:
  - phase: 07-agent-framework-data-loader
    provides: BaseAgent ABC, AgentSignal, AgentReport, PointInTimeDataLoader, classify_strength
  - phase: 08-inflation-monetary-policy-agents
    provides: features/__init__.py conditional import pattern, MonetaryFeatureEngine pattern
provides:
  - FiscalFeatureEngine with compute() returning debt ratios, r-g dynamics, primary balance, CB credibility
  - DebtSustainabilityModel — IMF 4-scenario DSA, d_{t+1} formula, 5Y projection, baseline-as-primary signal
  - FiscalImpulseModel — 12M primary balance z-score, LONG for fiscal expansion, SHORT for contraction
  - FiscalDominanceRisk — composite 0-100 from 4 weighted components (0.35/0.30/0.20/0.15), locked thresholds 33/66
  - FiscalAgent orchestrating 4 signals (DSA + Impulse + DominanceRisk + Composite)
  - FISCAL_BR_COMPOSITE with equal 1/3 weights and 0.70 conflict dampening
  - BRL futures (6L) already present in CftcCotConnector.CONTRACT_CODES
  - 14 unit tests for all 3 models and composite, no DB required
affects:
  - 09-02-fx-equilibrium-agent (uses CFTC_6L_LEVERAGED_NET via BRL contract added here)
  - AgentRegistry (FiscalAgent registerable after this plan)
  - backtesting-engine (FiscalAgent.backtest_run() available)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - IMF-style 4-scenario DSA with locked formula d_{t+1} = d_t*(1+r)/(1+g) - pb
    - Baseline-as-primary approach for DSA direction (not majority-vote scenarios)
    - Confidence from scenario consensus (how many of 4 scenarios show stabilizing debt)
    - Composite 0-100 risk score with neutral-value substitution for NaN subscores
    - Equal-weight composite with 0.70 conflict dampening (same pattern as MonetaryPolicyAgent)
    - Conditional import pattern in features/__init__.py for wave-1 independence

key-files:
  created:
    - src/agents/features/fiscal_features.py
    - src/agents/fiscal_agent.py
    - tests/test_fiscal_agent.py
  modified:
    - src/agents/features/__init__.py

key-decisions:
  - "FiscalDominanceRisk substitutes 50 (neutral midpoint) for NaN subscores — partial signal still valuable"
  - "DSA uses baseline-as-primary approach: baseline_delta > THRESHOLD → LONG, not majority-vote across scenarios"
  - "DSA confidence from scenario consensus: 4/4 stabilizing → 1.0, 3/4 → 0.70, 2/4 → 0.40, 1/4 → 0.20, 0/4 → 0.05"
  - "FiscalImpulseModel direction: positive z (pb improving) = SHORT (fiscal contraction = BRL positive)"
  - "Equal weights (1/3) for FISCAL_BR_COMPOSITE — all 3 fiscal signals are independent indicators"
  - "FiscalAgent stores as_of_date in data dict via data['_as_of_date'] for compute_features access"
  - "BRL futures (6L: 102741) was already present in CftcCotConnector.CONTRACT_CODES — no change needed"

patterns-established:
  - "FiscalFeatureEngine follows Phase 8 _-prefix convention for private model keys"
  - "All fiscal computations guarded with try/except returning np.nan on failure"
  - "Model classes receive pre-assembled private data keys from feature engine"

requirements-completed: [FISC-01, FISC-02, FISC-03, FISC-04]

# Metrics
duration: 11min
completed: 2026-02-21
---

# Phase 09 Plan 01: Fiscal Agent Summary

**FiscalAgent with IMF 4-scenario DSA, FiscalImpulseModel, FiscalDominanceRisk (0-100 composite), equal-weight FISCAL_BR_COMPOSITE, and 14 unit tests — all without DB connection**

## Performance

- **Duration:** 11 min
- **Started:** 2026-02-21T17:10:57Z
- **Completed:** 2026-02-21T17:22:27Z
- **Tasks:** 2
- **Files modified:** 4 (created 3, modified 1)

## Accomplishments

- FiscalFeatureEngine computes 10+ fiscal features including debt ratios, r-g spread, primary balance/GDP, CB credibility z-score, and private model keys (_dsa_raw_data, _pb_history, _focus_history, _as_of_date)
- DebtSustainabilityModel implements IMF-style 4-scenario 5Y DSA with locked formula d_{t+1} = d_t*(1+r)/(1+g) - pb, baseline-as-primary signal direction, confidence from scenario consensus
- FiscalImpulseModel z-scores 12M primary balance change over 36M rolling window, LONG for fiscal expansion, SHORT for contraction
- FiscalDominanceRisk produces 0-100 composite from 4 weighted components (debt level 35%, r-g spread 30%, pb trend 20%, CB credibility 15%) with locked thresholds 33/66
- FiscalAgent orchestrates all 3 models + FISCAL_BR_COMPOSITE with equal 1/3 weights and 0.70 conflict dampening
- 14 unit tests pass without any database connection

## Task Commits

Each task was committed atomically:

1. **Task 1: Create FiscalFeatureEngine, all 3 fiscal models, FiscalAgent, update features/__init__.py** - `9a4c0d5` (feat)
2. **Task 2: Write unit tests for FiscalAgent models** - `bf0b4b6` (test)

## Files Created/Modified

- `src/agents/features/fiscal_features.py` - FiscalFeatureEngine with compute() and 4 private model key helpers
- `src/agents/fiscal_agent.py` - DebtSustainabilityModel, FiscalImpulseModel, FiscalDominanceRisk, FiscalAgent
- `src/agents/features/__init__.py` - Added conditional FiscalFeatureEngine import (wave-1 independence)
- `tests/test_fiscal_agent.py` - 14 unit tests covering all models and composite

## Decisions Made

- **Baseline-as-primary for DSA:** Signal direction uses baseline scenario only (not majority vote across 4 scenarios). Rationale: baseline represents the most likely trajectory; scenarios provide confidence calibration.
- **Confidence from scenario consensus:** 4/4 stabilizing → 1.0, down to 0/4 → 0.05. Rationale: more scenarios agreeing on stabilization = more confident in SHORT direction.
- **Neutral substitution for FiscalDominanceRisk:** NaN subscores filled with 50 (neutral midpoint) rather than excluded. Rationale: partial signal with 1-3 valid components is still informative.
- **Equal weights for composite:** All 3 signals use 1/3 each — no a priori preference among independent fiscal models.
- **BRL already present:** CftcCotConnector.CONTRACT_CODES["6L"] = "102741" was already in the file. No code change needed.

## Deviations from Plan

None - plan executed exactly as written (BRL entry was pre-existing in CFTC connector).

## Issues Encountered

- Ruff reported 3 lint issues: unused `AgentReport` import in fiscal_agent.py, one line > 120 chars in fiscal_features.py, one line > 120 chars in fiscal_agent.py. All fixed inline during Task 1.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- FiscalAgent.run() produces exactly 4 signals (DSA + Impulse + DominanceRisk + Composite) and is registerable in AgentRegistry
- CFTC BRL futures (6L) ready for FxEquilibriumAgent in Phase 09-02
- All 14 unit tests pass, no database required for development/CI

---
*Phase: 09-fiscal-fx-equilibrium-agents*
*Completed: 2026-02-21*
