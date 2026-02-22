---
phase: 12-portfolio-construction-risk-management
plan: 03
subsystem: risk
tags: [risk-limits, circuit-breaker, drawdown, alert-dispatch, webhook, structlog, state-machine, risk-monitor]

# Dependency graph
requires:
  - phase: 12-portfolio-construction-risk-management
    provides: "VaRCalculator, StressTester, VaRResult, StressResult from Plan 12-02"
provides:
  - "RiskLimitChecker: 9 configurable limits with pre-trade checking and utilization reporting"
  - "DrawdownManager: 3-level circuit breaker state machine (6 states) with cooldown and gradual re-entry"
  - "AlertDispatcher: structlog logging + optional webhook POST for circuit breaker events"
  - "StrategyLossTracker and AssetClassLossTracker: independent per-strategy and per-asset-class circuit breakers"
  - "RiskMonitor: aggregate risk report combining VaR, stress tests, limits, and circuit breaker status"
  - "RiskReport dataclass consumed by Phase 13 orchestration pipeline"
affects: [13-orchestration, daily-pipeline, live-trading]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "6-state circuit breaker: NORMAL -> L1_TRIGGERED -> L2_TRIGGERED -> L3_TRIGGERED -> COOLDOWN -> RECOVERING -> NORMAL"
    - "L3_TRIGGERED immediately chains to COOLDOWN within same update() call"
    - "AlertDispatcher never raises on HTTP failure (graceful degradation for trading loop safety)"
    - "Risk level classification: CRITICAL (any breach) > HIGH (>80% util or >2% dd) > MODERATE (>1% dd) > LOW"

key-files:
  created:
    - src/risk/risk_limits.py
    - src/risk/drawdown_manager.py
    - src/risk/risk_monitor.py
    - tests/test_risk/test_risk_limits.py
    - tests/test_risk/test_drawdown_manager.py
    - tests/test_risk/test_risk_monitor.py
  modified:
    - src/risk/__init__.py

key-decisions:
  - "L3_TRIGGERED immediately chains to COOLDOWN within same update() call (not deferred to next call)"
  - "AlertDispatcher uses stdlib urllib.request (no new dependency) with 5s timeout, catches URLError/HTTPError/OSError"
  - "Recovery scale factor: recovery_day / recovery_days (0.33, 0.66, 1.0 for default 3-day recovery)"
  - "L1 recovery threshold: drawdown < l1_drawdown_pct * 0.5 (must drop below half of L1 trigger to de-escalate)"
  - "Strategy/AssetClass loss trackers fire independently from portfolio DrawdownManager"
  - "Risk level classification rules: CRITICAL > HIGH > MODERATE > LOW based on limit breaches and utilization"

patterns-established:
  - "State machine with immediate chaining: L3->COOLDOWN in same call prevents stuck intermediate states"
  - "AlertDispatcher pattern: always log, optionally webhook, never crash"
  - "RiskMonitor as single entry point: all risk queries go through generate_report()"
  - "Frozen config dataclasses (RiskLimitsConfig, CircuitBreakerConfig) for immutable configuration"

requirements-completed: [RISK-05, RISK-06, RISK-07, RISK-08, TESTV2-04]

# Metrics
duration: 10min
completed: 2026-02-22
---

# Phase 12 Plan 03: Risk Limits, Circuit Breakers & Risk Monitor Summary

**9-limit RiskLimitChecker with pre-trade simulation, 3-level DrawdownManager circuit breaker (6-state machine with cooldown/recovery), AlertDispatcher (structlog + webhook), and RiskMonitor aggregating VaR/stress/limits into unified RiskReport**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-22T00:43:57Z
- **Completed:** 2026-02-22T00:54:08Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- RiskLimitChecker enforces 9 configurable limits (VaR 95/99, drawdown, leverage, single position, asset class concentration, risk budget, strategy daily loss, asset class daily loss) with pre-trade simulation and utilization reporting
- DrawdownManager implements full 6-state circuit breaker machine (NORMAL/L1/L2/L3/COOLDOWN/RECOVERING) with L3 immediately chaining to COOLDOWN, 5-day cooldown, 3-day gradual recovery ramp, and HWM reset on full recovery
- AlertDispatcher logs all circuit breaker events at WARNING level via structlog and optionally POSTs JSON to configurable webhook URL with graceful failure handling (never crashes trading loop)
- StrategyLossTracker and AssetClassLossTracker fire independently as per-strategy and per-asset-class circuit breaker layers
- RiskMonitor orchestrates VaR, stress tests, limits, and circuit breakers into a single RiskReport with risk level classification (LOW/MODERATE/HIGH/CRITICAL) and ASCII-formatted text output
- 42 new tests (11 limits + 23 drawdown + 8 monitor) bringing Phase 12 total to 107 tests

## Task Commits

Each task was committed atomically:

1. **Task 1: RiskLimitChecker, DrawdownManager, AlertDispatcher, and RiskMonitor modules** - `1e5556a` (feat)
2. **Task 2: TESTV2-04 unit tests for risk limits, circuit breakers, and risk monitor** - `1752c29` (feat)

## Files Created/Modified
- `src/risk/risk_limits.py` - RiskLimitsConfig (9 limits), LimitCheckResult, RiskLimitChecker with check_all, check_pre_trade, utilization_report (301 lines)
- `src/risk/drawdown_manager.py` - CircuitBreakerState enum, CircuitBreakerConfig, CircuitBreakerEvent, DrawdownManager (6-state machine), AlertDispatcher, StrategyLossTracker, AssetClassLossTracker (510 lines)
- `src/risk/risk_monitor.py` - RiskReport dataclass, RiskMonitor with generate_report and format_report (329 lines)
- `src/risk/__init__.py` - Updated with 16 public exports
- `tests/test_risk/test_risk_limits.py` - 11 tests: all 9 limits, pre-trade pass/fail, utilization, custom config (154 lines)
- `tests/test_risk/test_drawdown_manager.py` - 23 tests: state transitions, cooldown, recovery, events, alert dispatch, strategy/asset trackers (361 lines)
- `tests/test_risk/test_risk_monitor.py` - 8 tests: report generation, risk levels, stress results, format_report, defaults (170 lines)

## Decisions Made
- L3_TRIGGERED immediately chains to COOLDOWN within same update() call -- prevents the state machine from getting stuck in the transient L3 state across update boundaries
- AlertDispatcher uses stdlib urllib.request with 5-second timeout -- no new dependency, and catches URLError/HTTPError/OSError to ensure alerting failures never crash the trading loop
- Recovery scale factor = recovery_day / recovery_days -- produces gradual ramp of 0.33, 0.66, 1.0 for the default 3-day recovery period
- L1 recovery requires drawdown < l1_threshold * 0.5 -- prevents whipsaw between NORMAL and L1 at the boundary
- Risk level classification: CRITICAL if any limit breached, HIGH if >80% utilization or >2% drawdown, MODERATE if >1% drawdown, else LOW

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed L3_TRIGGERED to immediately chain to COOLDOWN**
- **Found during:** Task 2 (test execution)
- **Issue:** State machine used elif chain that processed L3_TRIGGERED only on the NEXT update call, but plan specifies "immediately transition to COOLDOWN"
- **Fix:** Added inline L3->COOLDOWN transition within the L2_TRIGGERED branch after setting L3_TRIGGERED, so both transitions happen in the same update() call
- **Files modified:** src/risk/drawdown_manager.py
- **Verification:** test_l3_trigger, test_cooldown_duration, test_recovery_gradual_ramp, test_recovery_to_normal all pass
- **Committed in:** 1752c29 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential for correct circuit breaker behavior. The L3 state must be transient per spec.

## Issues Encountered
None beyond the auto-fixed deviation above.

## User Setup Required
None -- no external service configuration required.

## Next Phase Readiness
- Phase 12 complete: all 3 plans delivered (signal aggregation, VaR/stress, risk limits/monitoring)
- RiskMonitor.generate_report() is the single entry point for Phase 13 daily pipeline
- All 107 Phase 12 tests pass: 29 portfolio + 78 risk
- All modules are pure computation (no database/IO) enabling easy integration and testing
- Risk package exports 16 public classes through src/risk/__init__.py

## Self-Check: PASSED

- All 7 files verified on disk
- Both task commits (1e5556a, 1752c29) verified in git log
- 78/78 risk tests pass
- 107/107 total Phase 12 tests pass
- Zero lint errors

---
*Phase: 12-portfolio-construction-risk-management*
*Completed: 2026-02-22*
