# Roadmap: Macro Fund System

## Overview

This roadmap covers four milestones of the macro trading system for a global macro hedge fund focused on Brazil and the US.

**v1.0 (Phases 1-6, Complete):** Data infrastructure — Docker stack, 11 connectors, 250+ series, TimescaleDB hypertables, transforms, FastAPI API, data quality framework. All 65 requirements delivered.

**v2.0 (Phases 7-13, Complete):** Quantitative models and agents — 5 analytical agents with quantitative models, event-driven backtesting engine, 8 trading strategies, signal aggregation, risk management, daily orchestration pipeline, LLM narrative generation, and monitoring dashboard. All 88 requirements delivered.

**v3.0 (Phases 14-19, Complete):** Strategy engine, risk & portfolio management — 24+ trading strategies, NLP pipeline for COPOM/FOMC, signal aggregation v2 (Bayesian), risk engine v2 (Monte Carlo VaR), portfolio optimization (Black-Litterman), Dagster orchestration, Grafana monitoring, React multi-page dashboard. All 77 requirements delivered.

**v4.0 (Phases 20-27, Active):** Portfolio Management System (PMS) — operational layer for human-in-the-loop portfolio management with position tracking, trade approval workflow, morning briefing, risk monitoring, performance attribution, 7 operational frontend screens, compliance/audit, Redis caching, Dagster PMS pipeline, and production readiness. 65 requirements across 8 phases.

## Phases

**Phase Numbering:**
- Phases 1-6: v1.0 Data Infrastructure (complete)
- Phases 7-13: v2.0 Quantitative Models & Agents (complete)
- Phases 14-19: v3.0 Strategy Engine, Risk & Portfolio Management (complete)
- Phases 20-27: v4.0 Portfolio Management System (active)

### v1.0 Phases (Complete)

- [x] **Phase 1: Foundation** - Docker stack, ORM models, hypertables, migrations, config, and database engines
- [x] **Phase 2: Core Connectors** - Base connector pattern, 4 core data sources (BCB SGS, FRED, Yahoo, PTAX), data integrity utilities, and test infrastructure
- [x] **Phase 3: Extended Connectors** - Remaining 7 data sources (Focus, B3/Tesouro, IBGE, STN, CFTC, US Treasury, FX Flow)
- [x] **Phase 4: Seed and Backfill** - Instrument/series metadata seeding, backfill orchestrator, and historical data population (2010-present)
- [x] **Phase 5: Transforms** - Curve construction, returns/vol/z-scores, macro calculations, and advanced indicators (silver layer)
- [x] **Phase 6: API and Quality** - FastAPI serving layer, all endpoints, data quality framework, verification, and CI pipeline (gold layer)

### v2.0 Phases (Complete)

- [x] **Phase 7: Agent Framework & Data Loader** - BaseAgent ABC, signal/report dataclasses, PointInTimeDataLoader, AgentRegistry, DB migration, dependency installation
- [x] **Phase 8: Inflation & Monetary Policy Agents** - InflationAgent and MonetaryPolicyAgent with quantitative models
- [x] **Phase 9: Fiscal & FX Equilibrium Agents** - FiscalAgent and FxEquilibriumAgent with DSA, BEER, carry models
- [x] **Phase 10: Cross-Asset Agent & Backtesting Engine** - CrossAssetAgent and BacktestEngine with PIT enforcement
- [x] **Phase 11: Trading Strategies** - BaseStrategy ABC and 8 initial strategies (rates, inflation, FX, cupom, sovereign)
- [x] **Phase 12: Portfolio Construction & Risk Management** - Signal aggregation, portfolio construction, VaR, stress testing, limits, circuit breakers
- [x] **Phase 13: Pipeline, LLM, Dashboard, API & Tests** - Daily pipeline, Claude API narrative, HTML dashboard, 9 API endpoints, integration tests

### v3.0 Phases (Complete)

- [x] **Phase 14: Backtesting Engine v2 & Strategy Framework** - Enhanced StrategySignal, StrategyRegistry, portfolio-level backtesting, walk-forward validation, deflated Sharpe, tearsheet
- [x] **Phase 15: New Trading Strategies** - 16 new strategies across FX (4), rates (4), inflation (2), cupom (1), sovereign (3), cross-asset (2)
- [x] **Phase 16: Cross-Asset Agent v2 & NLP Pipeline** - HMM regime classification, LLM narrative, COPOM/FOMC scrapers, hawk/dove sentiment
- [x] **Phase 17: Signal Aggregation v2, Risk Engine v2 & Portfolio Optimization** - Bayesian aggregation, Monte Carlo VaR, reverse stress, Black-Litterman, Kelly sizing
- [x] **Phase 18: Dagster Orchestration, Monitoring & Reporting** - Dagster assets, Grafana dashboards, AlertManager, daily reports
- [x] **Phase 19: Dashboard v2, API Expansion, Testing & Verification** - React 5-page dashboard, backtest/strategy/WebSocket APIs, integration tests, CI/CD

### v4.0 Phases (Active)

- [ ] **Phase 20: PMS Database & Position Manager** - PMS database schemas (6 tables), Alembic migration, PositionManager service (open, close, MTM, book, P&L history)
- [ ] **Phase 21: Trade Workflow & PMS API** - TradeWorkflowService (human-in-the-loop proposal/approval), 20+ FastAPI PMS endpoints (portfolio, trades, journal, attribution)
- [ ] **Phase 22: Morning Pack, Risk Monitor & Attribution** - MorningPackService (daily briefing), PMSRiskMonitor (live risk), PerformanceAttributionEngine (Brinson-Fachler)
- [ ] **Phase 23: Frontend Design System & Morning Pack Page** - Dark terminal design system, reusable components, Morning Pack page (macro snapshot, agents, signals, portfolio)
- [ ] **Phase 24: Frontend Position Book & Trade Blotter** - Book of Positions page (live P&L, grouping, modals), Trade Blotter page (approval workflow, statistics)
- [ ] **Phase 25: Frontend Risk Monitor & Performance Attribution** - Risk Monitor page (VaR gauges, stress tests, correlation), Performance Attribution page (Brinson waterfall, heatmap, factors)
- [ ] **Phase 26: Frontend Decision Journal, Agent Intelligence & Compliance** - Decision Journal page, Agent Intelligence page, AuditLogger, PreTradeRiskControls, JWT auth, security middleware
- [ ] **Phase 27: Redis Cache, Dagster PMS Pipeline, Go-Live & Verification** - Redis PMS caching, Dagster PMS assets/schedule, Go-Live checklist, DR playbook, verification script, final commit

## Phase Details

### Phase 20: PMS Database & Position Manager
**Goal**: Database foundation and core position management for the Portfolio Management System -- all PMS tables created with proper hypertables and the PositionManager service handling the complete position lifecycle (open, close, mark-to-market, aggregation)
**Depends on**: Phase 19 (v3.0 complete -- all analytical infrastructure operational)
**Requirements**: PMDB-01, PMDB-02, PMDB-03, PMDB-04, PMDB-05, POSM-01, POSM-02, POSM-03, POSM-04
**Guide Etapas**: 1 (Database Schemas), 2 (Position Manager)
**Success Criteria** (what must be TRUE):
  1. Six PMS tables created via Alembic migration: portfolio_positions, trade_proposals, decision_journal, daily_briefings, position_pnl_history (hypertable), and attribution_snapshots -- all with proper indexes and compression
  2. PositionManager can open a position (with entry price, notional, strategy attribution, manager thesis), close a position (calculating realized P&L), and run mark-to-market (updating unrealized P&L)
  3. PositionManager can aggregate positions by instrument, asset class, strategy, and direction, and return a complete book view with P&L and risk metrics
  4. Position P&L history is tracked daily in the position_pnl_history hypertable with DV01/delta metrics
  5. All PMS model imports work and basic model tests pass (create position, create proposal, decision journal immutability)
**Plans:** 0/? plans (to be planned)

### Phase 21: Trade Workflow & PMS API
**Goal**: Human-in-the-loop trade approval workflow and comprehensive API layer for all PMS operations -- the gestor can review system-generated trade proposals, approve/reject/modify them, and all actions are exposed via 20+ REST endpoints
**Depends on**: Phase 20 (PMS tables and PositionManager operational)
**Requirements**: TRAD-01, TRAD-02, TRAD-03, TRAD-04, PAPI-01, PAPI-02, PAPI-03, PAPI-04, PAPI-05, PAPI-06, PAPI-07
**Guide Etapas**: 3 (Trade Workflow), 4 (API Endpoints PMS Core)
**Success Criteria** (what must be TRUE):
  1. TradeWorkflowService generates trade proposals from aggregated signals and portfolio optimizer output, including risk impact analysis (VaR before/after, leverage impact)
  2. Approval workflow supports full lifecycle: PROPOSED -> APPROVED/REJECTED/MODIFIED -> EXECUTED/CANCELLED, with audit trail and manager notes at each transition
  3. 20+ PMS API endpoints serve positions (book, detail, history), trades (proposals, pending, approval actions), journal (entries, search), and attribution (daily, cumulative, by-strategy)
  4. All API endpoints accept proper request validation and return structured JSON responses
  5. Trade execution recording captures fill price, slippage, fees, and links executed trade to position
**Plans:** 0/? plans (to be planned)

### Phase 22: Morning Pack, Risk Monitor & Attribution
**Goal**: Three core PMS backend services providing the gestor's daily operational intelligence -- morning briefing, real-time risk monitoring, and performance attribution analysis
**Depends on**: Phase 21 (trade workflow and API endpoints operational for integration)
**Requirements**: MORN-01, MORN-02, MORN-03, MORN-04, RMON-01, RMON-02, RMON-03, RMON-04, PERF-01, PERF-02, PERF-03, PERF-04
**Guide Etapas**: 5 (Morning Pack), 6 (Risk Monitor), 7 (Performance Attribution)
**Success Criteria** (what must be TRUE):
  1. MorningPackService generates a complete daily briefing with market snapshot (overnight moves, key levels, calendar), signal summary (new/changed signals), risk status (VaR, limit utilization), and suggested trades with rationale
  2. Morning Pack includes LLM-generated macro narrative (Claude API with template fallback) and prioritized action items
  3. PMSRiskMonitor computes live risk metrics (VaR, leverage, drawdown, concentration) from actual positions, generates exposure breakdown by asset class/geography/factor, and detects/alerts on limit breaches (warning at 80%)
  4. PerformanceAttributionEngine computes Brinson-Fachler attribution (allocation/selection/interaction effects), factor-based attribution (rates, FX, credit, vol, regime), and strategy-level P&L decomposition
  5. Daily and cumulative attribution snapshots are persisted to the attribution_snapshots table
**Plans:** 0/? plans (to be planned)

### Phase 23: Frontend Design System & Morning Pack Page
**Goal**: Professional dark-terminal design system (Bloomberg Terminal reference) and the Morning Pack page -- the first screen the gestor sees each morning showing macro context, agent intelligence, signals, portfolio state, and suggested trades
**Depends on**: Phase 22 (morning pack, risk monitor, attribution backends all serving data)
**Requirements**: DSYS-01, DSYS-02, DSYS-03, DSYS-04, FMRN-01, FMRN-02, FMRN-03, FMRN-04
**Guide Etapas**: 8 (Design System & Base Structure), 9 (Morning Pack Page)
**Success Criteria** (what must be TRUE):
  1. Design system provides shared components (MetricCard, SignalBadge, PriceDisplay, DataTable, ApprovalButton, TimelineEvent, ExposureBar, AlertBanner) with consistent dark theme, typography, and spacing
  2. All PMS components have proper loading states, empty states, and error states
  3. Morning Pack page displays 3-column layout: Macro Snapshot | Agents & Signals | Portfolio & Actions, with LLM macro narrative (expandable, full width)
  4. Signal summary section highlights new/changed signals sortable by conviction, with approve/reject inline actions for suggested trades
  5. Risk overview shows limit utilization bars and warning indicators, auto-refreshes every 5 minutes, with date picker for historical morning packs
**Plans:** 0/? plans (to be planned)

### Phase 24: Frontend Position Book & Trade Blotter
**Goal**: Two operationally critical frontend screens -- the Book of Positions (live P&L, risk metrics, position management) and the Trade Blotter (proposal review, approval workflow, trade history)
**Depends on**: Phase 23 (design system and API client established)
**Requirements**: FPOS-01, FPOS-02, FPOS-03, FTBL-01, FTBL-02, FTBL-03
**Guide Etapas**: 10 (Book de Posições), 11 (Trade Blotter)
**Success Criteria** (what must be TRUE):
  1. Book page shows KPI header (AUM, Gross Notional, Leverage, VaR, P&L Today, P&L MTD), sortable positions table with P&L, DV01/Delta, VaR contribution, and strategy attribution
  2. Positions can be grouped/filtered by asset class, strategy, direction, with expandable rows showing thesis, target price, stop loss, and entry history
  3. Book page has modals for opening new positions (discretionary), closing positions, and manual mark-to-market
  4. Trade Blotter shows pending proposals as cards ordered by conviction with approve/reject actions, including risk impact preview and LLM rationale
  5. Approve modal allows editing execution price, notional, target, stop loss, thesis; reject modal requires reason with quick-pick chips; historical blotter shows all trades with status/date/instrument filters
**Plans:** 0/? plans (to be planned)

### Phase 25: Frontend Risk Monitor & Performance Attribution
**Goal**: Two analytical frontend screens -- Risk Monitor (real-time risk visualization with gauges, charts, and breach alerts) and Performance Attribution (multi-dimensional P&L decomposition with equity curves, heatmaps, and factor analysis)
**Depends on**: Phase 23 (design system), Phase 22 (risk monitor and attribution backends)
**Requirements**: FRSK-01, FRSK-02, FRSK-03, FATT-01, FATT-02, FATT-03, FATT-04
**Guide Etapas**: 12 (Risk Monitor), 13 (Performance Attribution)
**Success Criteria** (what must be TRUE):
  1. Risk Monitor page shows VaR gauges (semicircular Recharts), leverage and drawdown limit utilization bars, exposure heatmap, and alerts banner for breaches
  2. Historical VaR + drawdown charts with time range selector, stress test table (scenario, shock, estimated P&L), correlation heatmap, and factor exposures
  3. Performance Attribution page shows period selector (MTD/QTD/YTD/6M/1A/custom), 6 KPI cards with benchmark comparison (CDI, IMA-B, IHFA)
  4. Full-width equity curve with benchmark overlay, brush zoom, drawdown area, and monthly return heatmap (years x months)
  5. Attribution tabs: by asset class, by strategy, by position, systematic vs discretionary, with rolling Sharpe + vol chart
**Plans:** 0/? plans (to be planned)

### Phase 26: Frontend Decision Journal, Agent Intelligence & Compliance
**Goal**: Decision Journal and Agent Intelligence pages for learning and auditability, plus compliance infrastructure (audit trail, pre-trade risk controls, JWT auth, security middleware)
**Depends on**: Phase 24 (trade blotter provides decision data), Phase 22 (backends for journal and agent views)
**Requirements**: FDJR-01, FDJR-02, FDJR-03, FDJR-04, COMP-01, COMP-02, COMP-03, COMP-04
**Guide Etapas**: 14 (Decision Journal & Agent Intelligence), 15 (Compliance, Audit & Security)
**Success Criteria** (what must be TRUE):
  1. Decision Journal page shows timeline of all PM decisions (trades, overrides, notes) with expandable detail (thesis, context, outcome), full-text search, date/type/asset class filters, and CSV export
  2. Agent Intelligence page shows 5 agent cards (grid 3+2) with signals, models, narratives, consensus view table, 60-day signal history chart, and divergence detection
  3. AuditLogger dual-writes to DB + JSONL file, covering all trade lifecycle events (POSITION_OPEN/CLOSE, TRADE_APPROVED/REJECTED, RISK_BREACH, EMERGENCY_STOP)
  4. PreTradeRiskControls validates trades against fat finger, leverage, concentration, VaR, and drawdown limits before approval
  5. JWT authentication with roles (viewer/trader/portfolio_manager/risk_manager), security middleware (CORS, rate limiting, request logging), and audit log API with date range filtering
**Plans:** 0/? plans (to be planned)

### Phase 27: Redis Cache, Dagster PMS Pipeline, Go-Live & Verification
**Goal**: Production readiness -- Redis caching for PMS hot paths, Dagster PMS daily pipeline, Go-Live checklist, disaster recovery procedures, comprehensive verification script, and final documentation
**Depends on**: Phase 26 (all PMS components operational)
**Requirements**: CACH-01, CACH-02, CACH-03, DPMS-01, DPMS-02, DPMS-03, GOLV-01, GOLV-02, GOLV-03, VRFY-01, VRFY-02, VRFY-03, VRFY-04
**Guide Etapas**: 16 (Redis Cache), 17 (Dagster PMS Pipeline), 18 (Go-Live & DR), 19 (Verification Script), 20 (Final Commit & Docs)
**Success Criteria** (what must be TRUE):
  1. Redis caches PMS hot paths (current positions 30s TTL, latest risk 60s, morning pack 5min, attribution 5min) with invalidation on portfolio changes and cache warming on startup
  2. Dagster PMS assets (mark_to_market, morning_pack, trade_proposals, risk_report) with daily schedule (6:00-6:40 BRT business days) and risk breach sensor (every 5min during market hours)
  3. Go-Live checklist covers PMS-specific validation (positions, trades, approvals workflow, data quality), DR playbook covers 4 scenarios (DB down, Redis down, bad position, wrong price), with backup/restore scripts
  4. PMS health check endpoint (GET /pms/health) validates DB, cache, and pipeline status
  5. Verification script (scripts/verify_pms.py) checks all v4.0 components (6 tables, 5 services, compliance, API, 7 frontend pages, Dagster, docs), CI/CD updated with PMS tests
**Plans:** 0/? plans (to be planned)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> ... -> 19 -> 20 -> 21 -> 22 -> 23 -> 24 -> 25 -> 26 -> 27

### v1.0 Data Infrastructure

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete | 2026-02-19 |
| 2. Core Connectors | 3/3 | Complete | 2026-02-19 |
| 3. Extended Connectors | 4/4 | Complete | 2026-02-19 |
| 4. Seed and Backfill | 3/3 | Complete | 2026-02-19 |
| 5. Transforms | 3/3 | Complete | 2026-02-19 |
| 6. API and Quality | 4/4 | Complete | 2026-02-19 |

### v2.0 Quantitative Models & Agents

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 7. Agent Framework | 2/2 | Complete | 2026-02-20 |
| 8. Inflation & Monetary Agents | 3/3 | Complete | 2026-02-21 |
| 9. Fiscal & FX Agents | 2/2 | Complete | 2026-02-21 |
| 10. Cross-Asset & Backtesting | 3/3 | Complete | 2026-02-21 |
| 11. Trading Strategies | 3/3 | Complete | 2026-02-21 |
| 12. Portfolio & Risk | 3/3 | Complete | 2026-02-22 |
| 13. Pipeline, LLM, Dashboard, API & Tests | 4/4 | Complete | 2026-02-22 |

### v3.0 Strategy Engine, Risk & Portfolio Management

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 14. Backtesting Engine v2 & Strategy Framework | 3/3 | Complete | 2026-02-22 |
| 15. New Trading Strategies | 5/5 | Complete | 2026-02-22 |
| 16. Cross-Asset Agent v2 & NLP Pipeline | 3/3 | Complete | 2026-02-22 |
| 17. Signal Aggregation v2, Risk Engine v2 & Portfolio Optimization | 4/4 | Complete | 2026-02-23 |
| 18. Dagster Orchestration, Monitoring & Reporting | 4/4 | Complete | 2026-02-23 |
| 19. Dashboard v2, API Expansion, Testing & Verification | 4/4 | Complete | 2026-02-23 |

### v4.0 Portfolio Management System

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 20. PMS Database & Position Manager | 0/? | Not Started | — |
| 21. Trade Workflow & PMS API | 0/? | Not Started | — |
| 22. Morning Pack, Risk Monitor & Attribution | 0/? | Not Started | — |
| 23. Frontend Design System & Morning Pack Page | 0/? | Not Started | — |
| 24. Frontend Position Book & Trade Blotter | 0/? | Not Started | — |
| 25. Frontend Risk Monitor & Performance Attribution | 0/? | Not Started | — |
| 26. Frontend Decision Journal, Agent Intelligence & Compliance | 0/? | Not Started | — |
| 27. Redis Cache, Dagster PMS Pipeline, Go-Live & Verification | 0/? | Not Started | — |
