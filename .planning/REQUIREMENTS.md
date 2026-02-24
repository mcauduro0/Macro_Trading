# Requirements: Macro Fund System

**Defined:** 2026-02-19 (v1) | 2026-02-20 (v2) | 2026-02-22 (v3) | 2026-02-23 (v4)
**Core Value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system — the foundation for analytical agents, quantitative strategies, risk management, and portfolio operations

## v1 Requirements (Complete)

All 65 v1 requirements delivered in milestone v1.0 Data Infrastructure. See `.planning/MILESTONES.md` for archive.

Summary: INFRA (7/7), CONN (12/12), DATA (5/5), SEED (5/5), XFORM (14/14), API (12/12), QUAL (6/6), TEST (4/4)

## v2 Requirements (Complete)

All 88 v2 requirements delivered in milestone v2.0 Quantitative Models & Agents.

Summary: AGENT (7/7), INFL (7/7), MONP (6/6), FISC (4/4), FXEQ (5/5), CRSA (3/3), BACK (8/8), STRAT (9/9), PORT (4/4), RISK (8/8), PIPE (3/3), LLM (4/4), DASH (5/5), APIV2 (9/9), TESTV2 (7/7)

## v3 Requirements (Complete)

All 77 v3 requirements delivered in milestone v3.0 Strategy Engine, Risk & Portfolio Management.

Summary: SFWK (4/4), BTST (6/6), FXST (4/4), RTST (4/4), INST (2/2), CPST (1/1), SVST (3/3), CAST (2/2), CRSV (4/4), NLP (5/5), SAGG (4/4), RSKV (8/8), POPT (5/5), ORCH (4/4), MNTR (4/4), DSHV (6/6), REPT (3/3), APIV (4/4), TSTV (4/4)

## v4 Requirements

Requirements for milestone v4.0 Portfolio Management System (PMS). Each maps to roadmap phases.

### PMS Database & Models

- [ ] **PMDB-01**: PMS position table (position_id, instrument, direction, quantity, avg_price, unrealized_pnl, realized_pnl, strategy_attribution, opened_at, updated_at) with Alembic migration
- [ ] **PMDB-02**: PMS trades table (trade_id, position_id, instrument, side, quantity, price, fees, slippage, executed_at, strategy_id, approval_status) with Alembic migration
- [ ] **PMDB-03**: PMS orders table (order_id, trade_id, instrument, side, order_type, quantity, limit_price, status, submitted_at, filled_at) with Alembic migration
- [ ] **PMDB-04**: PMS trade_approvals table (approval_id, trade_id, requested_by, approved_by, status, reason, requested_at, resolved_at) with Alembic migration
- [ ] **PMDB-05**: PMS attribution_snapshots table (snapshot_date, position_id, gross_pnl, transaction_costs, allocation_effect, selection_effect, interaction_effect) with Alembic migration

### Position Manager

- [ ] **POSM-01**: PositionManager class with open_position, close_position, update_mark, get_positions, get_position_by_id methods
- [ ] **POSM-02**: Real-time P&L calculation: unrealized (mark-to-market vs avg_price), realized (closed trades), total
- [ ] **POSM-03**: Position aggregation by instrument, asset class, strategy, and direction (long/short/net)
- [ ] **POSM-04**: Position history tracking with daily snapshots for time-series analysis

### Trade Workflow (Human-in-the-Loop)

- [ ] **TRAD-01**: TradeWorkflowManager with suggest_trade (from signals), submit_for_approval, approve, reject, execute lifecycle
- [ ] **TRAD-02**: Trade suggestion engine consuming aggregated signals and portfolio optimizer output to generate trade proposals
- [ ] **TRAD-03**: Approval workflow: suggested -> pending_review -> approved/rejected -> executed/cancelled with audit trail
- [ ] **TRAD-04**: Trade execution recording with fill price, slippage, fees, and strategy attribution

### PMS API Endpoints

- [ ] **PAPI-01**: Position endpoints: GET /pms/positions, GET /pms/positions/{id}, GET /pms/positions/summary, GET /pms/positions/history
- [ ] **PAPI-02**: Trade endpoints: GET /pms/trades, POST /pms/trades/suggest, GET /pms/trades/{id}, GET /pms/trades/pending
- [ ] **PAPI-03**: Approval endpoints: POST /pms/approvals/{trade_id}/approve, POST /pms/approvals/{trade_id}/reject, GET /pms/approvals/pending
- [ ] **PAPI-04**: Morning Pack endpoint: GET /pms/morning-pack (daily briefing JSON)
- [ ] **PAPI-05**: Risk Monitor endpoints: GET /pms/risk/realtime, GET /pms/risk/exposures, GET /pms/risk/breaches
- [ ] **PAPI-06**: Attribution endpoints: GET /pms/attribution/daily, GET /pms/attribution/cumulative, GET /pms/attribution/by-strategy
- [ ] **PAPI-07**: Decision Journal endpoints: GET /pms/journal, POST /pms/journal/entry, GET /pms/journal/{date}

### Morning Pack

- [ ] **MORN-01**: MorningPackGenerator producing daily briefing with market snapshot (overnight moves, key levels, calendar)
- [ ] **MORN-02**: Morning Pack includes signal summary (new signals, flips, conviction changes since previous close)
- [ ] **MORN-03**: Morning Pack includes risk status (current VaR, limit utilization, notable exposures)
- [ ] **MORN-04**: Morning Pack includes suggested trades for the day with rationale from agent views

### Risk Monitor

- [ ] **RMON-01**: RealTimeRiskMonitor polling positions and market data for continuous limit checking
- [ ] **RMON-02**: Exposure breakdown by asset class, geography, direction, and risk factor
- [ ] **RMON-03**: Breach detection and alerting when limits approach (warning at 80%) or exceed thresholds
- [ ] **RMON-04**: Risk monitor integrates with existing RiskLimitsManager v2 and AlertManager

### Performance Attribution

- [ ] **PERF-01**: Brinson-Fachler attribution decomposing P&L into allocation effect, selection effect, and interaction effect
- [ ] **PERF-02**: Factor-based attribution decomposing returns by risk factors (rates, FX, credit, vol, regime)
- [ ] **PERF-03**: Strategy-level P&L decomposition showing contribution of each strategy to total portfolio P&L
- [ ] **PERF-04**: Daily and cumulative attribution snapshots persisted to attribution_snapshots table

### Design System

- [ ] **DSYS-01**: Shared component library: StatusBadge, DataTable (sortable, filterable), MetricCard, ChartContainer
- [ ] **DSYS-02**: Shared component library: ApprovalButton, TimelineEvent, ExposureBar, AlertBanner
- [ ] **DSYS-03**: Consistent color palette, typography, spacing tokens across all PMS screens
- [ ] **DSYS-04**: Loading states, empty states, and error states for all PMS components

### Frontend: Morning Pack Screen

- [ ] **FMRN-01**: Morning Pack page displaying market snapshot, calendar events, key levels
- [ ] **FMRN-02**: Signal summary section with new/changed signals highlighted, sortable by conviction
- [ ] **FMRN-03**: Suggested trades section with approve/reject inline actions
- [ ] **FMRN-04**: Risk overview section with limit utilization bars and warning indicators

### Frontend: Position Book Screen

- [ ] **FPOS-01**: Position Book page with sortable table of all positions (instrument, direction, quantity, avg price, P&L, weight)
- [ ] **FPOS-02**: Position grouping/filtering by asset class, strategy, direction
- [ ] **FPOS-03**: Position detail expandable row with entry history, mark-to-market chart, strategy attribution

### Frontend: Trade Blotter Screen

- [ ] **FTBL-01**: Trade Blotter page with chronological list of all trades (date, instrument, side, quantity, price, status)
- [ ] **FTBL-02**: Pending trades section with approve/reject actions and trade rationale display
- [ ] **FTBL-03**: Trade filtering by status (pending, approved, rejected, executed), date range, instrument

### Frontend: Risk Monitor Screen

- [ ] **FRSK-01**: Risk Monitor page with real-time VaR gauges, limit utilization bars, exposure heatmap
- [ ] **FRSK-02**: Breach alerts panel with severity, timestamp, affected limit, and current value
- [ ] **FRSK-03**: Exposure breakdown charts (by asset class, geography, risk factor)

### Frontend: Performance Attribution Screen

- [ ] **FATT-01**: Attribution page with Brinson-Fachler waterfall chart (allocation, selection, interaction effects)
- [ ] **FATT-02**: Strategy contribution bar chart showing each strategy's P&L contribution over time
- [ ] **FATT-03**: Factor exposure chart showing returns decomposed by risk factors
- [ ] **FATT-04**: Date range selector and benchmark comparison toggle

### Frontend: Decision Journal & Agent Intelligence Screen

- [ ] **FDJR-01**: Decision Journal page with timeline of PM decisions (trades, overrides, notes) linked to outcomes
- [ ] **FDJR-02**: Agent Intelligence panel showing all 5 agent views, confidence levels, and key drivers side-by-side
- [ ] **FDJR-03**: Cross-Asset narrative display with regime assessment and trade recommendations
- [ ] **FDJR-04**: Decision outcome tracking: what was decided, what happened, P&L impact

### Compliance, Audit & Security

- [ ] **COMP-01**: Audit trail for all trade lifecycle events (suggest, approve, reject, execute, cancel) with timestamp and user
- [ ] **COMP-02**: Trade logging with pre-trade and post-trade snapshots for regulatory compliance
- [ ] **COMP-03**: Role-based access control for PMS operations (viewer, trader, portfolio_manager, risk_manager)
- [ ] **COMP-04**: Audit log API: GET /pms/audit/trades, GET /pms/audit/approvals with date range filtering

### Redis Cache Optimization

- [ ] **CACH-01**: Cache layer for PMS hot-path queries: current positions, latest risk metrics, morning pack
- [ ] **CACH-02**: Cache invalidation strategy: position updates invalidate position cache, trade execution invalidates blotter cache
- [ ] **CACH-03**: Cache warming on startup and after Dagster pipeline completion

### Dagster PMS Pipeline

- [ ] **DPMS-01**: Dagster PMS assets: morning_pack, trade_suggestions, risk_snapshot, attribution_snapshot, decision_journal_sync
- [ ] **DPMS-02**: PMS daily schedule: morning pack (07:00), trade suggestions (08:00), EOD attribution (18:30)
- [ ] **DPMS-03**: PMS assets integrated into existing Dagster definitions with dependency on existing Bronze/Silver/Agent layers

### Go-Live & Disaster Recovery

- [ ] **GOLV-01**: Go-Live checklist document covering PMS-specific pre-launch validation (positions, trades, approvals workflow)
- [ ] **GOLV-02**: Disaster recovery procedures for PMS data (position backup, trade history export, recovery runbook)
- [ ] **GOLV-03**: Health check endpoints for PMS subsystem: GET /pms/health (DB, cache, pipeline status)

### Verification & Testing

- [ ] **VRFY-01**: PMS integration test: trade lifecycle E2E (signal -> suggest -> approve -> execute -> position update -> attribution)
- [ ] **VRFY-02**: PMS API integration test: all /pms/* endpoints return 200 OK with valid payloads
- [ ] **VRFY-03**: PMS verification script (scripts/verify_pms.py) validating all v4.0 components with formatted report
- [ ] **VRFY-04**: CI/CD updated with PMS test suite in GitHub Actions workflow

## Out of Scope (v4.0)

| Feature | Reason |
|---------|--------|
| Live exchange connectivity (FIX) | PMS records trades, doesn't route to exchanges |
| Multi-fund / multi-portfolio | Single fund for now |
| Bloomberg/Refinitiv real-time feeds | Free data sources only |
| Kubernetes / Helm deployment | Docker Compose sufficient |
| Options / Greeks | Futures and linear instruments only |
| Mobile app / PWA | Desktop operational screens |
| Automated trade execution | Human-in-the-loop is a v4.0 requirement |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| (To be filled during roadmap creation) | | |

**Coverage:**
- v4 requirements: 65 total (PMDB:5, POSM:4, TRAD:4, PAPI:7, MORN:4, RMON:4, PERF:4, DSYS:4, FMRN:4, FPOS:3, FTBL:3, FRSK:3, FATT:4, FDJR:4, COMP:4, CACH:3, DPMS:3, GOLV:3, VRFY:4)
- Mapped to phases: 0
- Unmapped: 65

---
*Requirements defined: 2026-02-23*
*Milestone: v4.0 Portfolio Management System (PMS)*
