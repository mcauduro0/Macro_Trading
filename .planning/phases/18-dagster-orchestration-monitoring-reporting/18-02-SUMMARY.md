---
phase: 18-dagster-orchestration-monitoring-reporting
plan: 02
subsystem: orchestration
tags: [dagster, signals, portfolio, risk, report, pipeline]

# Dependency graph
requires:
  - phase: 18-01
    provides: "14 Dagster assets (Bronze/Silver/Agent layers), Definitions module, Docker service"
provides:
  - "8 new Dagster asset definitions (2 Signal + 2 Portfolio + 3 Risk + 1 Report)"
  - "Updated Definitions with 22 total assets and bronze_ingest job"
  - "Full dependency graph: Bronze -> Silver -> Agents -> Signals -> Portfolio -> Risk -> Report"
affects: [18-04, monitoring, reporting]

# Tech tracking
tech-stack:
  added: []
  patterns: [dagster-full-pipeline-graph, bronze-only-ingest-job, upstream-context-passing]

key-files:
  created:
    - src/orchestration/assets_signals.py
    - src/orchestration/assets_portfolio.py
    - src/orchestration/assets_risk.py
    - src/orchestration/assets_report.py
  modified:
    - src/orchestration/definitions.py

key-decisions:
  - "All downstream assets use same RetryPolicy and DailyPartitionsDefinition as Bronze/Silver/Agent layers"
  - "Report asset collects upstream context dict for DailyReportGenerator (wired in 18-04)"
  - "Bronze-only ingest job enables selective materialization for data-only refreshes"

requirements-completed: [ORCH-02]

# Metrics
duration: ~5min
completed: 2026-02-23
---

# Phase 18 Plan 02: Downstream Pipeline Assets Summary

**8 new Dagster asset definitions extending the pipeline from 14 to 22 assets with full dependency graph**

## Accomplishments
- 2 Signal assets (signal_aggregation, signal_monitor) wrapping SignalAggregatorV2 and SignalMonitor
- 2 Portfolio assets (portfolio_optimization, portfolio_sizing) wrapping PortfolioOptimizer and PositionSizer
- 3 Risk assets (risk_var, risk_stress, risk_limits) wrapping VaRCalculator, StressTester, RiskLimitsManager
- 1 Report asset (daily_report) assembling upstream outputs into structured context
- Updated definitions.py with 22 total assets, daily_pipeline job, and bronze_ingest job
- Full dependency graph visible in dagster-webserver UI

## Task Commits

1. **Task 1: Signal, Portfolio, Risk, and Report asset definitions** - `e27a5cd` (feat)
2. **Task 2: Updated Definitions module with 22 assets** - `7f5252f` (feat)

## Files Created/Modified
- `src/orchestration/assets_signals.py` - 2 Signal layer Dagster assets
- `src/orchestration/assets_portfolio.py` - 2 Portfolio layer Dagster assets
- `src/orchestration/assets_risk.py` - 3 Risk layer Dagster assets
- `src/orchestration/assets_report.py` - 1 Report layer Dagster asset
- `src/orchestration/definitions.py` - Expanded from 14 to 22 assets, added bronze_ingest job

---
*Phase: 18-dagster-orchestration-monitoring-reporting*
*Completed: 2026-02-23*
