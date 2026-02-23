---
phase: 17-signal-aggregation-v2-risk-engine-v2-portfolio-optimization
plan: 01
subsystem: portfolio
tags: [signal-aggregation, bayesian, regime-tilting, crowding, staleness, monitoring]

# Dependency graph
requires:
  - phase: 14-strategy-framework-v2-registry-backtesting-analytics
    provides: "StrategySignal dataclass, StrategyRegistry"
  - phase: 16-cross-asset-agent-v2-nlp-pipeline
    provides: "CrossAssetView with regime_probabilities, HMM regime model"
provides:
  - "SignalAggregatorV2 with 3 aggregation methods (confidence_weighted, rank_based, bayesian)"
  - "REGIME_STRATEGY_TILTS matrix for regime-aware strategy weighting"
  - "AggregatedSignalV2 dataclass with crowding/staleness metadata"
  - "SignalMonitor with flip/surge/divergence detection"
  - "DailySignalSummary with grouped asset-class reporting"
affects: [risk-engine-v2, portfolio-optimization, dashboard-v3]

# Tech tracking
tech-stack:
  added: []
  patterns: [bayesian-regime-prior, staleness-linear-decay, crowding-penalty, signal-monitoring]

key-files:
  created:
    - src/portfolio/signal_aggregator_v2.py
    - src/portfolio/signal_monitor.py
    - tests/test_signal_aggregator_v2.py
    - tests/test_signal_monitor.py
  modified: []

key-decisions:
  - "Bayesian default method with flat prior when no regime context available"
  - "Regime tilts shift WHICH strategies to trust, not overall conviction level"
  - "Crowding penalty is gentle 20% reduction at >80% agreement threshold"
  - "Staleness linear decay over 5 business days (weekday-only counting)"
  - "Signal flip = any sign change; conviction surge = absolute >0.3; divergence = >0.5 within asset class"

patterns-established:
  - "Strategy conviction derived from z_score/2.0 clamped to [-1,+1]"
  - "Regime tilting via REGIME_STRATEGY_TILTS prefix-matched matrix"
  - "Strategy-to-asset-class mapping via strategy_id prefix convention"

requirements-completed: [SAGG-01, SAGG-02, SAGG-03, SAGG-04]

# Metrics
duration: 8min
completed: 2026-02-23
---

# Phase 17 Plan 01: Signal Aggregation v2 & Signal Monitor Summary

**Bayesian regime-aware signal aggregation with 3 methods (confidence-weighted, rank-based, Bayesian with regime tilts), crowding penalty, staleness decay, and anomaly monitoring (flips, surges, divergence)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-23T00:29:20Z
- **Completed:** 2026-02-23T00:37:20Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- SignalAggregatorV2 with 3 aggregation methods operating on StrategySignal objects
- Bayesian method uses REGIME_STRATEGY_TILTS matrix to shift which strategies to trust based on HMM regime probabilities
- Crowding penalty (20% reduction) and staleness discount (5 business day linear decay) applied across all methods
- SignalMonitor detects signal flips, conviction surges (>0.3), and strategy divergence (>0.5 within asset class)
- Comprehensive daily summary with signals grouped by asset class, regime context, and all alerts
- 39 total tests passing (21 aggregator + 18 monitor)

## Task Commits

Each task was committed atomically:

1. **Task 1: SignalAggregatorV2 with 3 methods, crowding, staleness** - `0a070be` (feat)
2. **Task 2: SignalMonitor with flip/surge/divergence and daily summary** - `c54c04a` (feat)

## Files Created/Modified
- `src/portfolio/signal_aggregator_v2.py` - Enhanced signal aggregator with 3 methods, crowding, staleness, regime tilting (376 lines)
- `src/portfolio/signal_monitor.py` - Signal monitor with flip/surge/divergence detection and daily summary (393 lines)
- `tests/test_signal_aggregator_v2.py` - Tests for all 3 methods, crowding, staleness, business days (21 tests)
- `tests/test_signal_monitor.py` - Tests for flip, surge, divergence detection and daily summary (18 tests)

## Decisions Made
- Bayesian is default aggregation method; flat prior (tilt=1.0) when no regime_probs provided
- Regime tilts determine WHICH strategies to trust (INF_ strategies get 1.5x in Stagflation, RATES_ get 0.7x), not overall conviction level
- Crowding penalty is a gentle 20% conviction reduction when >80% of strategies agree on direction
- Staleness uses weekday-only business day counting (no holiday calendar) with linear decay to zero over 5 days
- Signal conviction derived from z_score / 2.0 clamped to [-1, +1]
- Direction threshold at 0.05 (half of Phase 12's 0.1) for strategy-level granularity
- Signal flip = any sign change (positive/negative/zero transitions)
- Conviction surge uses pure magnitude check (not volatility-adjusted) at 0.3 threshold
- Strategy divergence = pairwise within same asset class (strategy_id prefix mapping) at 0.5 threshold

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- SignalAggregatorV2 ready to receive StrategySignal objects from 25 strategies
- SignalMonitor ready to integrate with daily portfolio pipeline
- AggregatedSignalV2 output ready for Risk Engine v2 (Plan 02) and Portfolio Optimization (Plan 03-04)
- Original signal_aggregator.py preserved for backward compatibility

## Self-Check: PASSED

- All 4 files exist (signal_aggregator_v2.py, signal_monitor.py, and tests)
- Both commits verified (0a070be, c54c04a)
- Line counts: 534, 537, 390, 373 (all above minimums: 200, 150, 100, 80)
- 39/39 tests passing
- Import verification OK for both modules
- Original signal_aggregator.py untouched

---
*Phase: 17-signal-aggregation-v2-risk-engine-v2-portfolio-optimization*
*Completed: 2026-02-23*
