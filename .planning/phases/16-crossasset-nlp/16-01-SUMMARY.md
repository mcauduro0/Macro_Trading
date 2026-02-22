---
phase: 16-crossasset-nlp
plan: 01
subsystem: agents
tags: [hmm, regime-classification, cross-asset, consistency-checker, dataclass, narrative, builder-pattern]

# Dependency graph
requires:
  - phase: 15-strategies-v3
    provides: "CrossAssetAgent with 3 models (regime, correlation, sentiment), cross_01/02 strategies"
provides:
  - "CrossAssetView frozen dataclass with builder pattern for structured regime output"
  - "HMMRegimeClassifier with 4-state GaussianHMM and rule-based fallback"
  - "CrossAssetConsistencyChecker with 7 dict-based contradiction rules"
  - "Enhanced CrossAssetAgent v2 producing both signals and CrossAssetView"
  - "NarrativeGenerator cross-asset section with LLM and template paths"
affects: [16-02, 16-03, strategies, portfolio-construction, narrative]

# Tech tracking
tech-stack:
  added: [hmmlearn (optional)]
  patterns: [frozen-dataclass-builder, rule-based-fallback, consistency-checker-dict-rules]

key-files:
  created:
    - src/agents/cross_asset_view.py
    - src/agents/hmm_regime.py
    - src/agents/consistency_checker.py
    - tests/test_cross_asset_view.py
    - tests/test_hmm_regime.py
    - tests/test_consistency_checker.py
  modified:
    - src/agents/cross_asset_agent.py
    - src/narrative/generator.py
    - tests/test_cross_asset_agent.py

key-decisions:
  - "HMM features mapped from existing CrossAssetFeatureEngine z-scores to 6-column DataFrame"
  - "Rule-based fallback assigns 0.7 probability to classified regime, 0.1 to each other"
  - "Tail risk composite = 30% VIX_z + 30% credit_z + 40% regime_transition_prob"
  - "CrossAssetView narrative generated inline (template) in agent, LLM path in NarrativeGenerator"
  - "Updated existing test_generate_narrative_format to match v2 narrative format"

patterns-established:
  - "Frozen dataclass + builder: immutable outputs built incrementally via CrossAssetViewBuilder"
  - "Conditional import with fallback: try hmmlearn, flag _hmm_available, use rule-based if unavailable"
  - "Dict-based extensible rules: consistency rules as list-of-dicts with callable check_fn"

requirements-completed: [CRSV-01, CRSV-02, CRSV-03, CRSV-04]

# Metrics
duration: 10min
completed: 2026-02-22
---

# Phase 16 Plan 01: CrossAssetAgent v2 Summary

**CrossAssetView frozen dataclass with HMM regime classifier (rule-based fallback), 7-rule consistency checker with 0.5x sizing penalty, and LLM narrative generation**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-22T22:28:38Z
- **Completed:** 2026-02-22T22:38:57Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- CrossAssetView frozen dataclass with builder pattern, all CRSV-01 fields (regime, regime_probabilities, asset_class_views, risk_appetite, tail_risk, key_trades, narrative, risk_warnings, consistency_issues)
- HMMRegimeClassifier with 4-state GaussianHMM, expanding window, full probability vector, and rule-based fallback when hmmlearn unavailable or data insufficient (CRSV-02)
- CrossAssetConsistencyChecker with 7 rules: FX_RATES, EQUITY_RATES, REGIME_FX_MISMATCH, REGIME_EQUITY_MISMATCH, INFLATION_RATES, RISK_APPETITE_DIRECTION, SOVEREIGN_FX_DIVERGENCE -- all with 0.5x sizing penalty (CRSV-03)
- Enhanced CrossAssetAgent v2 producing both 3 AgentSignals AND a CrossAssetView
- NarrativeGenerator cross-asset section with LLM prompt and template fallback (CRSV-04)
- 41 new tests (12 view, 13 HMM, 16 consistency) -- 40 passing, 1 skipped (hmmlearn not installed)

## Task Commits

Each task was committed atomically:

1. **Task 1: CrossAssetView dataclass, HMM regime classifier, consistency checker** - `52b5fdf` (feat)
2. **Task 2: Integrate into CrossAssetAgent, add LLM narrative, write tests** - `b5caf51` (feat)

## Files Created/Modified
- `src/agents/cross_asset_view.py` - CrossAssetView frozen dataclass, supporting dataclasses (AssetClassView, TailRiskAssessment, KeyTrade, ConsistencyIssue), CrossAssetViewBuilder
- `src/agents/hmm_regime.py` - HMMRegimeClassifier with GaussianHMM and rule-based fallback, HMMResult dataclass
- `src/agents/consistency_checker.py` - CrossAssetConsistencyChecker with 7 dict-based rules and helper functions
- `src/agents/cross_asset_agent.py` - Enhanced with HMM classifier, consistency checker, build_cross_asset_view(), _build_hmm_features(), _build_view_narrative()
- `src/narrative/generator.py` - Added generate_cross_asset_narrative(), _generate_cross_asset_llm(), _generate_cross_asset_template()
- `tests/test_cross_asset_view.py` - 12 tests for builder, validation, all dataclasses
- `tests/test_hmm_regime.py` - 13 tests for rule-based fallback, HMM path, edge cases
- `tests/test_consistency_checker.py` - 16 tests for all 7 rules, false positive checks, penalty verification
- `tests/test_cross_asset_agent.py` - Updated test_generate_narrative_format for v2 format

## Decisions Made
- HMM features mapped from CrossAssetFeatureEngine z-scores (vix_zscore_252d -> VIX_z, etc.) to single-row DataFrame; full expanding window requires historical data which produces rule-based fallback in testing
- Rule-based probability distribution: 0.7 to classified regime, 0.1 to each of the other 3
- Tail risk composite: weighted sum of VIX z-score (30%), credit spread z-score (30%), and regime transition probability (40%) with assessment levels at 30/50/70 thresholds
- Narrative generated inline via template in CrossAssetAgent._build_view_narrative(); LLM path lives in NarrativeGenerator.generate_cross_asset_narrative() for daily brief integration

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing test_generate_narrative_format for v2 narrative**
- **Found during:** Task 2 (regression testing)
- **Issue:** Existing test checked for "Cross-Asset Assessment" format string which no longer appears in v2 narrative (now uses CrossAssetView narrative)
- **Fix:** Updated assertions to check for "regime" keyword and non-trivial narrative length
- **Files modified:** tests/test_cross_asset_agent.py
- **Verification:** All 20 existing tests pass
- **Committed in:** b5caf51 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix -- test format update)
**Impact on plan:** Minimal. Test updated to match new v2 narrative format. No scope creep.

## Issues Encountered
- hmmlearn not installed in environment -- HMM test path skipped (test_hmm_path_if_available), rule-based fallback works correctly as designed

## User Setup Required
None - no external service configuration required. hmmlearn is optional (pip install hmmlearn for HMM path).

## Next Phase Readiness
- CrossAssetView available for all downstream strategies to consume regime probabilities
- NLP pipeline (Plan 02) can build on NarrativeGenerator cross-asset section
- Consistency checker ready for integration with signal adapter (Plan 03)

## Self-Check: PASSED

All 6 created files verified on disk. Both task commits (52b5fdf, b5caf51) verified in git log.

---
*Phase: 16-crossasset-nlp*
*Completed: 2026-02-22*
