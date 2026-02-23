---
phase: 18-dagster-orchestration-monitoring-reporting
plan: 03
subsystem: monitoring
tags: [grafana, docker, dashboards, timescaledb, observability, risk, portfolio]

# Dependency graph
requires:
  - phase: 17-risk-portfolio-management
    provides: "Risk metrics tables (risk_metrics_daily, stress_test_results, risk_limits_status) and portfolio_state hypertable"
provides:
  - "Grafana Docker service on port 3002 with monitoring profile"
  - "TimescaleDB datasource auto-provisioning"
  - "4 pre-configured Grafana dashboards (pipeline health, signal overview, risk, portfolio)"
  - "Dashboard provisioning config for auto-load on first start"
affects: [19-documentation-deployment]

# Tech tracking
tech-stack:
  added: [grafana-oss-11.4.0]
  patterns: [grafana-provisioning-yaml, grafana-dashboard-json-v39, docker-compose-profiles]

key-files:
  created:
    - monitoring/grafana/provisioning/datasources/timescaledb.yml
    - monitoring/grafana/provisioning/dashboards/dashboards.yml
    - monitoring/grafana/dashboards/pipeline_health.json
    - monitoring/grafana/dashboards/signal_overview.json
    - monitoring/grafana/dashboards/risk_dashboard.json
    - monitoring/grafana/dashboards/portfolio_performance.json
  modified:
    - docker-compose.yml

key-decisions:
  - "Grafana under 'monitoring' Docker profile so it does not start with default docker compose up"
  - "Datasource UID 'timescaledb' referenced directly in all dashboard panels for consistent provisioning"
  - "All 4 dashboards auto-refresh every 15 minutes per user decision"
  - "Pipeline health as default home dashboard via GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH"

patterns-established:
  - "Grafana provisioning: YAML in monitoring/grafana/provisioning/ mounted to /etc/grafana/provisioning"
  - "Dashboard JSON files in monitoring/grafana/dashboards/ mounted to /var/lib/grafana/dashboards"
  - "Dashboard schema version 39 with browser timezone and standard Grafana JSON format"

requirements-completed: [MNTR-01, MNTR-02]

# Metrics
duration: 5min
completed: 2026-02-23
---

# Phase 18 Plan 03: Grafana Monitoring Summary

**Grafana Docker service with auto-provisioned TimescaleDB datasource and 4 dashboards: pipeline health (connector grid + timeline), signal overview (heatmap matrix + conviction), risk (VaR gauges + stress bars), portfolio performance (equity curve + attribution pie)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-23T03:24:12Z
- **Completed:** 2026-02-23T03:29:35Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Grafana Docker service on port 3002 under monitoring profile with TimescaleDB datasource auto-provisioning
- Pipeline health dashboard with 6 connector status stat panels (green/yellow/red), run duration timeline, and error log table
- Signal overview dashboard with asset class x strategy heatmap matrix, conviction bar gauge by asset class, and signal flip timeline
- Risk dashboard with 4 VaR gauge dials (95%/99%/CVaR/drawdown), stress scenario horizontal bar chart, limit utilization bars, and VaR history
- Portfolio performance dashboard with summary stats (return/Sharpe/leverage/positions), equity curve, strategy attribution donut, monthly returns bars, and stacked asset class allocation

## Task Commits

Each task was committed atomically:

1. **Task 1: Grafana Docker Compose service and datasource provisioning, pipeline_health and signal_overview dashboards** - `747391d` (feat)
2. **Task 2: Risk dashboard and portfolio performance dashboard JSON definitions** - `431cb0c` (feat)

## Files Created/Modified
- `docker-compose.yml` - Added Grafana service on port 3002 with monitoring profile and grafana_data volume
- `monitoring/grafana/provisioning/datasources/timescaledb.yml` - TimescaleDB datasource auto-provisioning with connection to timescaledb:5432
- `monitoring/grafana/provisioning/dashboards/dashboards.yml` - Dashboard provisioner pointing to /var/lib/grafana/dashboards
- `monitoring/grafana/dashboards/pipeline_health.json` - Pipeline health dashboard (11 panels: 6 connector stats, run timeline, error log)
- `monitoring/grafana/dashboards/signal_overview.json` - Signal overview dashboard (6 panels: heatmap matrix, conviction bars, flip timeline)
- `monitoring/grafana/dashboards/risk_dashboard.json` - Risk dashboard (11 panels: 4 VaR gauges, stress bars, limit utilization, VaR history)
- `monitoring/grafana/dashboards/portfolio_performance.json` - Portfolio performance dashboard (12 panels: 4 stats, equity curve, attribution pie, monthly returns, asset allocation)

## Decisions Made
- Grafana under 'monitoring' Docker Compose profile to keep default `docker compose up` lightweight
- Datasource UID set to 'timescaledb' (matching provisioned name) for direct panel references
- All 4 dashboards set to 15-minute auto-refresh per user decision
- Pipeline health set as default home dashboard via Grafana environment variable
- Signal heatmap uses SQL GROUP BY with Grafana transforms for asset-class-by-strategy matrix layout
- Risk dashboard queries reference risk_metrics_daily, stress_test_results, and risk_limits_status tables
- Portfolio performance uses last/first TimescaleDB functions for monthly return calculations

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required. Grafana starts automatically with `docker compose --profile monitoring up`.

## Next Phase Readiness
- All 4 Grafana dashboards ready for visual monitoring
- Dashboards auto-load on first Grafana start via provisioning
- Tables referenced in queries (pipeline_runs, strategy_signals, risk_metrics_daily, stress_test_results, risk_limits_status, portfolio_state) must exist in TimescaleDB for live data display
- Ready for Phase 18 Plan 04 (reporting) or Phase 19 (documentation/deployment)

## Self-Check: PASSED

All 7 files verified present on disk. Both task commits (747391d, 431cb0c) verified in git history.

---
*Phase: 18-dagster-orchestration-monitoring-reporting*
*Completed: 2026-02-23*
