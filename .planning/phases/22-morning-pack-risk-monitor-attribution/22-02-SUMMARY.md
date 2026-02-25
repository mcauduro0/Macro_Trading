---
phase: 22-morning-pack-risk-monitor-attribution
plan: 02
subsystem: risk
tags: [risk-monitor, var, stress-testing, alerts, concentration, pms]

# Dependency graph
requires:
  - phase: 20-pms-data-models-position-manager
    provides: PositionManager with get_book(), mark_to_market(), get_pnl_timeseries()
  - phase: 17-risk-management-v3
    provides: VaRCalculator, StressTester, RiskLimitsManager v2
provides:
  - RiskMonitorService with compute_live_risk(), get_risk_trend(), generate_alerts()
  - PMSRiskLimits frozen dataclass with VaR/leverage/drawdown/concentration limits
  - Two-tier alert system (WARNING at 80%, BREACH at 100%)
  - 30-day risk trend history for dashboard charts
affects: [25-dashboard-risk-monitor, 23-attribution-performance]

# Tech tracking
tech-stack:
  added: []
  patterns: [graceful-degradation-optional-components, two-tier-alert-severity, deque-trend-history]

key-files:
  created:
    - src/pms/risk_limits_config.py
    - src/pms/risk_monitor.py
    - tests/test_pms/test_risk_monitor.py
  modified:
    - src/pms/__init__.py

key-decisions:
  - "Two-tier alerts: WARNING at 80% utilization, BREACH at 100% for all limit types"
  - "Graceful degradation: each optional component (VaRCalculator, StressTester, RiskLimitsManager) can be None"
  - "Parametric VaR computed from P&L history returns when >=20 observations; MC VaR requires >=30"
  - "Drawdown computed from cumulative daily P&L via high-water-mark method against AUM"

patterns-established:
  - "Two-tier alert pattern: scan utilization metrics, WARNING at configurable threshold (80%), BREACH at 100%"
  - "Risk snapshot deque(maxlen=30) for trend history without external storage"
  - "PMSRiskLimits.from_env() for environment-based configuration override"

requirements-completed: [PMS-RM-01, PMS-RM-02, PMS-RM-03]

# Metrics
duration: 6min
completed: 2026-02-24
---

# Phase 22 Plan 02: Risk Monitor Summary

**RiskMonitorService with daily risk snapshots covering VaR, leverage, drawdown, concentration, stress tests, and two-tier alerts (WARNING/BREACH) powered by PMSRiskLimits config**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-24T14:51:15Z
- **Completed:** 2026-02-24T14:57:15Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments
- RiskMonitorService.compute_live_risk() returns structured risk snapshot matching PMS guide specification
- Two-tier alert severity (WARNING at 80%, BREACH at 100%) for VaR, leverage, drawdown, concentration, and loss limits
- PMSRiskLimits frozen dataclass with configurable limits and from_env() classmethod
- 30-day trend history accumulation via deque for dashboard chart data
- Graceful degradation when optional risk components (VaRCalculator, StressTester, RiskLimitsManager) are None
- 14 tests passing covering structure, alerts, concentration, trend, and degradation

## Task Commits

Each task was committed atomically:

1. **Task 1: PMSRiskLimits config and RiskMonitorService** - `69f8480` (feat)

## Files Created/Modified
- `src/pms/risk_limits_config.py` - PMSRiskLimits frozen dataclass with VaR/leverage/drawdown/concentration limits and from_env()
- `src/pms/risk_monitor.py` - RiskMonitorService with compute_live_risk(), get_risk_trend(), generate_alerts()
- `tests/test_pms/test_risk_monitor.py` - 14 tests covering all risk monitor functionality
- `src/pms/__init__.py` - Added RiskMonitorService and PMSRiskLimits to package exports

## Decisions Made
- Two-tier alerts: WARNING at 80% utilization, BREACH at 100% -- consistent with RiskLimitsManager v2 check_all_v2 pattern
- Graceful degradation: each optional component can be None, service returns valid structure with defaults/empty sections
- Parametric VaR from P&L history (>= 20 observations), MC VaR only with >= 30 observations and VaRCalculator
- Drawdown via high-water-mark of cumulative daily P&L divided by AUM
- Concentration computed from get_book().by_asset_class as % of total gross notional

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed concentration OK test threshold arithmetic**
- **Found during:** Task 1 (test verification)
- **Issue:** Test used 50/50 allocation producing 83% RATES utilization (above 80% WARNING threshold)
- **Fix:** Adjusted test to use 3 asset classes with custom PMSRiskLimits having higher limits ensuring all stay below 80%
- **Files modified:** tests/test_pms/test_risk_monitor.py
- **Verification:** All 14 tests pass
- **Committed in:** 69f8480 (part of task commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test data adjustment for correct threshold arithmetic. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- RiskMonitorService ready for API endpoint wiring in Phase 25 (dashboard)
- PMSRiskLimits can be customized via PMS_RISK_* environment variables
- get_risk_trend() provides pre-built data source for dashboard trend charts

## Self-Check: PASSED

All files verified present. Commit 69f8480 verified in git log.

---
*Phase: 22-morning-pack-risk-monitor-attribution*
*Completed: 2026-02-24*
