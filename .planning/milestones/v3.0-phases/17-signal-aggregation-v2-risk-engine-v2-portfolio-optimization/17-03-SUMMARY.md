---
phase: 17-signal-aggregation-v2-risk-engine-v2-portfolio-optimization
plan: 03
subsystem: risk
tags: [risk-limits, loss-tracking, risk-budget, risk-api, var-endpoint, stress-endpoint, fastapi]

# Dependency graph
requires:
  - phase: 12
    provides: "RiskLimitChecker with 9 configurable limits and pre-trade validation"
  - phase: 17-02
    provides: "VaR decomposition, 6 stress scenarios, reverse stress testing, historical replay"
provides:
  - "RiskLimitsManager v2 with daily/weekly cumulative loss tracking"
  - "Risk budget allocation monitoring per position and per asset class"
  - "GET /risk/var endpoint returning VaR/CVaR at 95% and 99%"
  - "GET /risk/stress endpoint returning all 6 stress scenarios"
  - "GET /risk/limits endpoint returning limit utilization and risk budget"
  - "GET /risk/dashboard endpoint returning aggregated risk overview"
affects: [17-04, portfolio-optimization, risk-dashboard, production-monitoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Temporal loss tracking: deque(maxlen=30) FIFO with 5-business-day rolling window"
    - "Risk budget composition: position-level and asset-class-level aggregation"
    - "Risk API envelope pattern: {status, data, meta} consistent across all endpoints"
    - "Lazy imports in API endpoints to avoid circular dependencies"

key-files:
  created:
    - tests/test_risk/test_risk_limits_v2.py
    - tests/test_api/test_risk_api_v2.py
  modified:
    - src/risk/risk_limits_v2.py
    - src/api/routes/risk_api.py
    - src/risk/__init__.py

key-decisions:
  - "Daily/weekly loss breach uses absolute value comparison against positive limit thresholds"
  - "Risk budget can_add_risk threshold at 5% headroom (available_risk_budget > 0.05)"
  - "check_all_v2 overall_status has three levels: OK, WARNING (>80% utilization), BREACHED"
  - "API endpoints use sample/placeholder data with deterministic seed=42 for consistent testing"

patterns-established:
  - "RiskLimitsManager v2 as higher-level manager composing RiskLimitChecker"
  - "4 dedicated risk API endpoints following consistent envelope pattern"
  - "Risk budget reporting with position_budgets and asset_class_budgets dicts"

requirements-completed: [RSKV-07, RSKV-08]

# Metrics
duration: 6min
completed: 2026-02-23
---

# Phase 17 Plan 03: Risk Limits v2 & Risk API Summary

**RiskLimitsManager v2 with daily/weekly loss tracking and risk budget monitoring, plus 4 dedicated risk API endpoints (/var, /stress, /limits, /dashboard) with 41 comprehensive tests**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-23T00:43:35Z
- **Completed:** 2026-02-23T00:49:50Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Built RiskLimitsManager v2 extending RiskLimitChecker with temporal loss tracking (daily 2% / weekly 5% limits) and risk budget allocation per position (20% max) and asset class (40% max)
- Created 4 dedicated risk API endpoints: /risk/var (VaR/CVaR at 95%/99% for all methods), /risk/stress (6 scenarios with filtering), /risk/limits (utilization + budget), /risk/dashboard (aggregated overview with circuit breaker)
- Preserved backward-compatible /risk/report endpoint
- Exported new types (RiskLimitsManager, RiskBudgetReport, LossRecord, RiskLimitsManagerConfig) via src/risk/__init__.py
- 41 tests total: 19 for risk limits v2, 22 for risk API endpoints

## Task Commits

Each task was committed atomically:

1. **Task 1: RiskLimitsManager v2 with daily/weekly loss tracking and risk budget** - `8677f49` (feat)
2. **Task 2: Risk API routes for /var, /stress, /limits, and /dashboard** - `4bb4182` (feat)

## Files Created/Modified

- `src/risk/risk_limits_v2.py` - RiskLimitsManager v2 with loss tracking, risk budget, check_all_v2 (317 lines)
- `src/api/routes/risk_api.py` - 5 risk API endpoints: /var, /stress, /limits, /dashboard, /report (387 lines)
- `src/risk/__init__.py` - Exports for RiskLimitsManager, RiskBudgetReport, LossRecord, RiskLimitsManagerConfig
- `tests/test_risk/test_risk_limits_v2.py` - 19 tests for loss tracking, budget computation, FIFO, check_all_v2 (325 lines)
- `tests/test_api/test_risk_api_v2.py` - 22 tests for all 5 risk API endpoints (249 lines)

## Decisions Made

- Daily/weekly loss breach detection uses absolute value comparison (|pnl| > limit) so both negative and positive extreme moves are caught
- Risk budget `can_add_risk` threshold set at 5% headroom (available > 0.05) to prevent marginal risk additions near capacity
- check_all_v2 introduces a three-tier overall_status: OK (clean), WARNING (>80% utilization), BREACHED (any limit/loss/budget breach)
- API endpoints use deterministic sample data (seed=42) for consistent, predictable responses in testing; production will pull from database

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Risk limits v2 and API endpoints ready for portfolio optimization integration
- VaR, stress testing, loss tracking, and risk budget all accessible via REST API
- Ready for Plan 04 (Portfolio Optimization) which will use risk budget reports for risk-aware portfolio construction

## Self-Check: PASSED

All 5 files verified present. Both task commits (8677f49, 4bb4182) verified in git log.

---
*Phase: 17-signal-aggregation-v2-risk-engine-v2-portfolio-optimization*
*Completed: 2026-02-23*
