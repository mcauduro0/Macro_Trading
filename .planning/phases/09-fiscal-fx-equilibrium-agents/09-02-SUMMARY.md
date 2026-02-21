---
phase: 09-fiscal-fx-equilibrium-agents
plan: 02
subsystem: agents
tags: [fx, beer-model, carry-to-risk, cip-basis, fx-flows, ols, statsmodels, agents]

# Dependency graph
requires:
  - phase: 09-01
    provides: features/__init__.py baseline (FiscalFeatureEngine conditional import pattern)
  - phase: 08-03
    provides: MonetaryPolicyAgent._build_composite pattern, classify_strength, BaseAgent ABC

provides:
  - FxFeatureEngine with BEER OLS data, carry history, flow combined, CIP inputs
  - BeerModel OLS misalignment ±5% locked threshold
  - CarryToRiskModel 30D vol denominator, z-score ±1.0 threshold
  - FlowModel equal-weight BCB FX + CFTC 6L z-scores
  - CipBasisModel positive basis = LONG USDBRL locked
  - FxEquilibriumAgent BEER 40% + Carry 30% + Flow 20% + CIP 10% composite
  - 20 unit tests without DB for all FX models

affects:
  - 10-cross-asset-agent
  - registry.py (fx_agent already pre-registered in EXECUTION_ORDER)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - BeerModel OLS prediction using same add_constant as training (avoids shape mismatch when constant dropped)
    - FxFeatureEngine._build_carry_ratio_history resamples daily vol to monthly carry/vol ratio
    - _flow_combined uses NaN sentinel for missing components, graceful partial handling in FlowModel
    - Locked composite weights as dict keyed by signal_id (extensible pattern)

key-files:
  created:
    - src/agents/features/fx_features.py
    - src/agents/fx_agent.py
    - tests/test_fx_agent.py
  modified:
    - src/agents/features/__init__.py

key-decisions:
  - "BeerModel uses same sm.add_constant() for prediction X as training X (avoids has_constant kwarg shape mismatch)"
  - "FX_BR_COMPOSITE: locked weights BEER 40% + Carry 30% + Flow 20% + CIP 10% as dict keyed by signal_id"
  - "CipBasisModel direction locked: positive basis = LONG USDBRL (capital flow friction, BRL less attractive)"
  - "CarryToRiskModel Z_FIRE=1.0 with 30D realized PTAX vol denominator (locked per CONTEXT.md)"
  - "FlowModel: NaN for missing BCB or CFTC component falls back to single-source composite (not NO_SIGNAL)"
  - "FxFeatureEngine._build_beer_ols_data filters to 2010-present and only drops rows where log_usdbrl is NaN"

patterns-established:
  - "Pattern: FX agent has same _safe_load pattern and composite builder as FiscalAgent and MonetaryPolicyAgent"
  - "Pattern: All private model data keys prefixed with _ to distinguish from scalar features"

requirements-completed: [FXEQ-01, FXEQ-02, FXEQ-03, FXEQ-04, FXEQ-05]

# Metrics
duration: 12min
completed: 2026-02-21
---

# Phase 9 Plan 02: FX Equilibrium Agent Summary

**FxEquilibriumAgent with OLS BEER model, carry-to-risk z-score, BCB+CFTC flow composite, and CIP basis producing 5 signals with BEER 40% + Carry 30% + Flow 20% + CIP 10% locked composite**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-21T17:28:14Z
- **Completed:** 2026-02-21T17:40:14Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Built FxFeatureEngine with full BEER OLS data pipeline (monthly resampled PTAX + macro series), 30D carry/vol ratio history, BCB+CFTC flow z-scores, CIP basis computation from Focus Cambio 12M expected depreciation
- Created all 4 FX model classes (BeerModel OLS ±5% locked, CarryToRiskModel z-score |z|>1.0, FlowModel equal-weight with NaN fallback, CipBasisModel positive=LONG locked) and FxEquilibriumAgent with locked composite weights
- 20 unit tests covering all direction cases, NO_SIGNAL conditions, partial data handling, composite dampening, and locked signal constants; all pass without DB

## Task Commits

Each task was committed atomically:

1. **Task 1: FxFeatureEngine, all 4 models, FxEquilibriumAgent, __init__.py update** - `9da3249` (feat)
2. **Task 2: Unit tests for FxEquilibriumAgent + BeerModel OLS bug fix** - `a0db447` (test/fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/agents/features/fx_features.py` - FxFeatureEngine with compute(), _build_beer_ols_data(), _build_carry_ratio_history(), _build_flow_combined()
- `src/agents/fx_agent.py` - BeerModel, CarryToRiskModel, FlowModel, CipBasisModel, FxEquilibriumAgent with _build_composite()
- `src/agents/features/__init__.py` - Added conditional FxFeatureEngine import (pattern from 09-01)
- `tests/test_fx_agent.py` - 20 unit tests covering all FX model direction cases

## Decisions Made

- BeerModel prediction uses same `sm.add_constant()` as training (not `has_constant='add'`) to avoid shape mismatch when statsmodels silently drops the constant column for all-constant predictors
- FX_BR_COMPOSITE locked weights stored as dict keyed by signal_id for clear association: `{"FX_BR_BEER": 0.40, "FX_BR_CARRY_RISK": 0.30, "FX_BR_FLOW": 0.20, "FX_BR_CIP_BASIS": 0.10}`
- CipBasisModel direction is locked per CONTEXT.md: positive basis (DI 1Y > offshore USD + depreciation) signals capital flow friction = BRL less attractive = LONG USDBRL
- FlowModel with one NaN component (BCB or CFTC missing) uses remaining single component at 100% weight rather than returning NO_SIGNAL — partial data still valuable

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed BeerModel OLS prediction shape mismatch**
- **Found during:** Task 2 (Unit tests for FxEquilibriumAgent)
- **Issue:** `sm.add_constant(..., has_const=True)` raises `unexpected keyword argument 'has_const'`. After fixing to `has_constant='add'`, a second bug emerged: when all predictor values are constant across rows, statsmodels silently drops the constant column during training (shape 60x3), but `has_constant='add'` forces a 4th column for prediction (shape 1x4), causing `shapes (1,4) and (3,) not aligned` ValueError
- **Fix:** Use the identical `sm.add_constant()` call (without `has_constant` kwarg) for both training and prediction. When predictors vary (real data), constant is added consistently; when predictors are constant (test edge case), constant is dropped consistently.
- **Files modified:** src/agents/fx_agent.py (BeerModel.run())
- **Verification:** `test_beer_model_undervalued_short` and `test_beer_model_overvalued_long` both PASSED
- **Committed in:** a0db447 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Auto-fix was necessary for BeerModel correctness on non-trivial data. No scope creep.

## Issues Encountered

- statsmodels `add_constant()` behavior with all-constant predictors: silently omits constant column to avoid multicollinearity. This is expected statsmodels behavior but creates prediction shape mismatch when using `has_constant='add'` kwarg on single-row prediction. Fixed by using identical `sm.add_constant()` call for both training and prediction.

## Self-Check: PASSED

Files verified:
- FOUND: src/agents/features/fx_features.py
- FOUND: src/agents/fx_agent.py
- FOUND: tests/test_fx_agent.py
- FOUND: src/agents/features/__init__.py

Commits verified:
- FOUND: 9da3249 (Task 1: FxFeatureEngine + agent)
- FOUND: a0db447 (Task 2: tests + OLS fix)

Tests: 20 passed, 0 failed (pytest tests/test_fx_agent.py)
Import: all 4 feature engines importable from src.agents.features
Constants: BeerModel.THRESHOLD == 5.0, FxEquilibriumAgent.AGENT_ID == "fx_agent"
Registry: "fx_agent" in AgentRegistry.EXECUTION_ORDER

## Next Phase Readiness

- FxEquilibriumAgent is registerable via AgentRegistry.register() and will run 4th in EXECUTION_ORDER
- All 5 FX signals (BEER, Carry, Flow, CIP, Composite) available for Phase 10 cross-asset agent
- Phase 9 (09-02) now complete — both FiscalAgent and FxEquilibriumAgent ready for production use

---
*Phase: 09-fiscal-fx-equilibrium-agents*
*Completed: 2026-02-21*
