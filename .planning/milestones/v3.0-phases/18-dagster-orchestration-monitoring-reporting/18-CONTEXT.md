# Phase 18: Dagster Orchestration, Monitoring & Reporting - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Production-grade orchestration with Dagster replacing the custom pipeline, Grafana monitoring dashboards with alerting, and automated daily report generation. Delivers three capabilities: pipeline orchestration (run), monitoring dashboards (see), and daily reports (read). Makes the system observable and operationally reliable.

</domain>

<decisions>
## Implementation Decisions

### Pipeline Behavior
- Retry 3 times with backoff on asset failure, then skip and continue downstream assets that don't depend on the failed asset
- Daily cron schedule at 6:00 AM BRT (before B3 market open at 10:00 AM) with manual trigger via `make dagster-run-all` anytime
- Support date range backfills through Dagster's partition system (not just latest day)

### Dashboard Design
- Pipeline health dashboard: connector status grid (green/yellow/red) at top + timeline of pipeline runs with duration bars and error annotations below
- Signal overview dashboard: heatmap matrix with asset classes as rows, strategies as columns, color = signal strength/direction (-1 to +1)
- Risk dashboard: current VaR as gauge dials with limit thresholds marked + stress scenario bar chart
- All dashboards auto-refresh every 15 minutes

### Alert Rules & Routing
- All 10 alerts go to both Slack and email regardless of severity
- 30-minute cooldown per alert type to prevent flooding during sustained breaches
- Runtime configurable: API endpoints to enable/disable rules and adjust thresholds without redeployment
- No escalation path: fire once per cooldown window, team monitors

### Daily Report Content
- Full analysis depth: detailed tables, charts (embedded base64), commentary per section -- comprehensive 15-minute read
- 7 sections: Market Snapshot, Regime, Agent Views, Signals, Portfolio, Risk, Actions
- Actions section includes specific trade recommendations with sizing, instruments, and rationale (not just signal-level guidance)
- Delivery: full HTML report via email + condensed summary with key metrics to Slack (summary + link to full report, not inline)
- Also accessible via GET /api/v1/reports/daily/latest and sendable via POST /reports/daily/send

### Claude's Discretion
- Dagster asset partitioning strategy (daily partitions vs unpartitioned for stable assets)
- Grafana dashboard panel layout and sizing within the agreed structure
- Portfolio performance dashboard design (not discussed -- standard equity curve + attribution)
- Slack message block formatting and condensed summary content selection
- Email template styling
- Alert threshold default values for the 10 rules

</decisions>

<specifics>
## Specific Ideas

- Pipeline runs at 6:00 AM BRT to ensure all data is collected and processed before B3 market open (10:00 AM BRT)
- Heatmap matrix for signals inspired by typical quant fund signal dashboards -- quick visual scan of entire book
- Gauge dials for VaR dashboard -- "car dashboard" feel for risk monitoring
- Trade recommendations in Actions should be concrete: "Increase DI1 short by 20 contracts" not "DI1 signal shifted bearish"
- Slack gets a condensed summary (key metrics as Slack blocks) with a link to the full HTML report, not the entire report inlined

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 18-dagster-orchestration-monitoring-reporting*
*Context gathered: 2026-02-23*
