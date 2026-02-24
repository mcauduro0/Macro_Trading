# Roadmap: Macro Fund System

## Overview

This roadmap covers three milestones of the macro trading system for a global macro hedge fund focused on Brazil and the US.

**v1.0 (Phases 1-6, Complete):** Data infrastructure — Docker stack, 11 connectors, 250+ series, TimescaleDB hypertables, transforms, FastAPI API, data quality framework. All 65 requirements delivered.

**v2.0 (Phases 7-13, Complete):** Quantitative models and agents — 5 analytical agents with quantitative models, event-driven backtesting engine, 8 trading strategies, signal aggregation, risk management, daily orchestration pipeline, LLM narrative generation, and monitoring dashboard. All 88 requirements delivered.

**v3.0 (Phases 14-19, Complete):** Strategy engine, risk & portfolio management — expand from 8 to 24+ trading strategies across all asset classes (FX, rates, inflation, cupom cambial, sovereign, cross-asset), enhanced backtesting engine (portfolio-level, walk-forward, deflated Sharpe), NLP pipeline for COPOM/FOMC communications, enhanced Cross-Asset Agent with LLM narrative, signal aggregation v2 (Bayesian, crowding, staleness), risk engine v2 (Monte Carlo VaR, reverse stress, component VaR), portfolio optimization (Black-Litterman, Kelly sizing), Dagster production orchestration, Grafana monitoring, React multi-page dashboard, and comprehensive integration testing. 77 requirements mapped across 6 phases.

**v4.0 (Phases 20-27, Active):** Portfolio Management System (PMS) — human-in-the-loop trade workflow, position book with real-time P&L, trade blotter with approval workflow, morning pack daily briefing, risk monitor with visual limits, performance attribution engine, decision journal with compliance audit, agent intelligence hub, 7 operational frontend pages, Redis caching, Dagster PMS pipeline integration, and go-live verification. Design reference: Brevan Howard, Bridgewater, Moore Capital operational workflows. Guide: docs/GUIA_COMPLETO_CLAUDE_CODE_Fase3_PMS.md (20 etapas).

## Phases

**Phase Numbering:**
- Phases 1-6: v1.0 Data Infrastructure (complete)
- Phases 7-13: v2.0 Quantitative Models & Agents (complete)
- Phases 14-19: v3.0 Strategy Engine, Risk & Portfolio Management (complete)
- Phases 20-27: v4.0 Portfolio Management System (active)
- Decimal phases (e.g., 14.1): Urgent insertions (marked with INSERTED)

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

- [x] **Phase 14: Backtesting Engine v2 & Strategy Framework** - Enhanced StrategySignal, StrategyRegistry, portfolio-level backtesting, walk-forward validation, deflated Sharpe, transaction cost model, tearsheet generation, DB migrations (completed 2026-02-22)
- [x] **Phase 15: New Trading Strategies** - 16 new strategies across FX (4), rates (4), inflation (2), cupom cambial (1), sovereign (3), cross-asset (2) (completed 2026-02-22)
- [x] **Phase 16: Cross-Asset Agent v2 & NLP Pipeline** - Enhanced CrossAssetView, HMM regime classification, consistency checking, LLM narrative, COPOM/FOMC scrapers, hawk/dove sentiment analysis (completed 2026-02-22)
- [x] **Phase 17: Signal Aggregation v2, Risk Engine v2 & Portfolio Optimization** - Bayesian aggregation, crowding/staleness, Monte Carlo VaR, reverse stress, component VaR, Black-Litterman, Kelly sizing (completed 2026-02-23)
- [x] **Phase 18: Dagster Orchestration, Monitoring & Reporting** - Dagster asset definitions, dependency graph, Grafana dashboards, AlertManager, daily report generator (completed 2026-02-23)
- [x] **Phase 19: Dashboard v2, API Expansion, Testing & Verification** - React multi-page dashboard (5 pages), backtest/strategy/WebSocket APIs, integration tests, CI/CD, verification script (completed 2026-02-23)

### v4.0 Phases (Active)

- [ ] **Phase 20: PMS Database & Position Manager** - PMS SQLAlchemy models (PortfolioPosition, TradeProposal, DecisionJournal, DailyBriefing, PositionPnLHistory), Alembic migration with hypertables, PositionManager service, MarkToMarketService (Guide Etapas 1-2)
- [ ] **Phase 21: Trade Workflow & PMS API** - TradeWorkflowService (signal-to-proposal pipeline, approve/reject/modify, discretionary trades), 20+ PMS API endpoints (book, trades, journal), Pydantic schemas (Guide Etapas 3-4)
- [ ] **Phase 22: Morning Pack, Risk Monitor & Attribution** - MorningPackService (daily briefing generation, market snapshot, agent views, trade proposals), RiskMonitorService (real-time risk dashboard data, limit monitoring), PerformanceAttributionEngine (multi-dimensional P&L attribution) (Guide Etapas 5-6-7)
- [ ] **Phase 23: Frontend Design System & Morning Pack Page** - PMS design system (color palette, component library, layout grid), Morning Pack page (market overview cards, agent summaries, trade proposal cards, alert banner) (Guide Etapas 8-9)
- [ ] **Phase 24: Frontend Position Book & Trade Blotter** - Position Book page (live positions table, P&L columns, asset class grouping, equity curve), Trade Blotter page (pending proposals, approval workflow UI, execution form, trade history) (Guide Etapas 10-11)
- [ ] **Phase 25: Frontend Risk Monitor & Performance Attribution** - Risk Monitor page (VaR gauges, stress test visualization, limit bars, concentration chart), Performance Attribution page (P&L waterfall, strategy attribution, time-series decomposition) (Guide Etapas 12-13)
- [ ] **Phase 26: Frontend Decision Journal, Agent Intel & Compliance** - Decision Journal page (timeline view, decision cards, outcome tracking, search/filter), Agent Intelligence Hub page (agent cards with signals, narrative display), Compliance & Audit module (audit trail, hash verification) (Guide Etapas 14-15)
- [ ] **Phase 27: Redis Cache, Dagster PMS, Go-Live & Verification** - Redis caching layer for PMS queries, Dagster PMS daily pipeline (MTM, proposals, briefing, attribution), go-live checklist, disaster recovery, verification script, final documentation (Guide Etapas 16-17-18-19-20)

## Phase Details

### v3.0 Phase Details (Complete)

### Phase 14: Backtesting Engine v2 & Strategy Framework
**Goal**: Enhanced strategy infrastructure and backtesting capabilities that support portfolio-level analysis, walk-forward validation, and statistically rigorous performance measurement -- the foundation all 16 new strategies will build on
**Depends on**: Phase 13 (v2.0 complete -- existing 8 strategies, BacktestEngine, BaseStrategy, signal pipeline all functional)
**Requirements**: SFWK-01, SFWK-02, SFWK-03, SFWK-04, BTST-01, BTST-02, BTST-03, BTST-04, BTST-05, BTST-06
**Success Criteria** (what must be TRUE):
  1. User can register strategies via @StrategyRegistry.register decorator, list all strategies by asset class, and instantiate any strategy by ID -- replacing the manual ALL_STRATEGIES dict
  2. User can run BacktestEngine.run_portfolio(strategies, weights) to backtest multiple strategies together with risk allocation and see combined equity curve, drawdown, and per-strategy attribution
  3. User can run walk-forward validation that splits a backtest period into train/test windows, optimizes parameters in-sample, and reports out-of-sample performance -- detecting overfitting
  4. User can compute deflated Sharpe ratio (Bailey & Lopez de Prado) that adjusts for multiple testing bias, and generate a complete tearsheet (equity curve, drawdown chart, monthly heatmap, rolling Sharpe, trade analysis)
  5. TransactionCostModel applies per-instrument costs for 12 instruments (DI1, DDI, DOL, NDF, NTN-B, LTN, UST, ZN, ZF, ES, CDS_BR, IBOV_FUT) and Alembic migrations create strategy_state and backtest_results v2 tables
**Plans:** 3/3 plans complete

Plans:
- [ ] 14-01: Enhanced StrategySignal dataclass, StrategyRegistry with decorator, strategy_state table migration, backtest_results v2 table migration
- [ ] 14-02: BacktestEngine v2 with portfolio-level backtesting, TransactionCostModel, walk-forward validation
- [ ] 14-03: Deflated Sharpe ratio, expanded analytics (Sortino, information ratio, tail ratio, turnover, rolling Sharpe), tearsheet generation

### Phase 15: New Trading Strategies
**Goal**: 16 new trading strategies spanning all major asset classes -- FX (4), rates (4), inflation (2), cupom cambial (1), sovereign (3), and cross-asset (2) -- each producing StrategySignal outputs compatible with the enhanced framework
**Depends on**: Phase 14 (StrategyRegistry, enhanced StrategySignal, BacktestEngine v2 all operational)
**Requirements**: FXST-01, FXST-02, FXST-03, FXST-04, RTST-01, RTST-02, RTST-03, RTST-04, INST-01, INST-02, CPST-01, SVST-01, SVST-02, SVST-03, CAST-01, CAST-02
**Success Criteria** (what must be TRUE):
  1. User can list all strategies by asset class and see 24+ strategies total (8 existing + 16 new) across FX, rates, inflation, cupom cambial, sovereign, and cross-asset categories
  2. FX strategies produce valid signals: FX-02 (carry-adjusted momentum combining Selic-FFR spread with USDBRL momentum), FX-03 (flow-based from BCB/CFTC/B3 with contrarian logic at |z|>2), FX-04 (vol surface relative value), FX-05 (terms of trade misalignment)
  3. Rates strategies produce valid signals: RATES-03 (BR-US spread adjusted for CDS), RATES-04 (term premium extraction from DI vs Focus), RATES-05 (FOMC event positioning), RATES-06 (COPOM event positioning)
  4. All 16 new strategies register via @StrategyRegistry.register, populate z_score/entry_level/stop_loss/take_profit in StrategySignal, and pass backtesting with the TransactionCostModel
  5. Each strategy backtests without error over 2+ years of historical data and produces a valid tearsheet with Sharpe, drawdown, and trade statistics
**Plans:** 5/5 plans complete

Plans:
- [x] 15-01-PLAN.md -- FX strategies: FX-02 Carry-Adjusted Momentum, FX-03 Flow-Based Tactical, FX-04 Vol Surface RV, FX-05 Terms of Trade
- [x] 15-02-PLAN.md -- Rates strategies: RATES-03 BR-US Spread, RATES-04 Term Premium, RATES-05 FOMC Event, RATES-06 COPOM Event
- [x] 15-03-PLAN.md -- Inflation (INF-02 IPCA Surprise, INF-03 Inflation Carry) and Cupom Cambial (CUPOM-02 Onshore-Offshore Spread)
- [x] 15-04-PLAN.md -- Sovereign (SOV-01 CDS Curve, SOV-02 EM Relative Value, SOV-03 Rating Migration) and Cross-Asset (CROSS-01 Regime Allocation, CROSS-02 Risk Appetite)
- [ ] 15-05-PLAN.md -- Gap closure: BacktestEngine signal adapter for list[StrategySignal] compatibility + integration tests for non-zero-trade backtesting

### Phase 16: Cross-Asset Agent v2 & NLP Pipeline
**Goal**: Enhanced Cross-Asset Agent with HMM-based regime classification and LLM-powered narrative, plus a complete NLP pipeline that scrapes and analyzes COPOM and FOMC communications for hawk/dove sentiment -- feeding intelligence into strategies and agents
**Depends on**: Phase 14 (strategy framework for consuming NLP signals)
**Requirements**: CRSV-01, CRSV-02, CRSV-03, CRSV-04, NLP-01, NLP-02, NLP-03, NLP-04, NLP-05
**Success Criteria** (what must be TRUE):
  1. CrossAssetAgent produces a CrossAssetView with regime (4 states: Goldilocks, Reflation, Stagflation, Deflation), per-asset-class views, risk_appetite score, tail_risk assessment, key_trades recommendations, and risk_warnings
  2. HMM regime classifier outputs regime probabilities (not just point estimate) with fallback to rule-based classification when HMM fails to converge
  3. Cross-asset consistency checker flags contradictions (e.g., FX bullish + rates higher = inconsistent) and LLM generates structured narrative explaining regime, key drivers, and trade rationale
  4. COPOMScraper retrieves atas/comunicados from bcb.gov.br and FOMCScraper retrieves statements/minutes from federalreserve.gov, both covering 2010-present with persistent storage
  5. CentralBankSentimentAnalyzer produces hawk/dove scores [-1, +1] with change_score vs previous document, key phrases extraction, and results persist to nlp_documents table via Alembic migration
**Plans:** 3/3 plans complete

Plans:
- [ ] 16-01-PLAN.md -- CrossAssetView dataclass + builder, HMM regime classification (with rule-based fallback), consistency checking (7 rules), LLM narrative generation
- [ ] 16-02-PLAN.md -- COPOMScraper, FOMCScraper, NlpDocumentRecord ORM, nlp_documents Alembic migration 007
- [ ] 16-03-PLAN.md -- CentralBankSentimentAnalyzer (PT+EN dictionaries, optional LLM), NLPProcessor pipeline (clean, score, extract, compare, persist)

### Phase 17: Signal Aggregation v2, Risk Engine v2 & Portfolio Optimization
**Goal**: Users can aggregate signals with Bayesian methods and anti-crowding protection, compute Monte Carlo VaR with copula dependence, run reverse stress tests, and optimize portfolios using Black-Litterman with agent views -- the quantitative core of portfolio management
**Depends on**: Phase 15 (16+ new strategies producing signals), Phase 16 (enhanced Cross-Asset Agent views for regime-aware aggregation and Black-Litterman inputs)
**Requirements**: SAGG-01, SAGG-02, SAGG-03, SAGG-04, RSKV-01, RSKV-02, RSKV-03, RSKV-04, RSKV-05, RSKV-06, RSKV-07, RSKV-08, POPT-01, POPT-02, POPT-03, POPT-04, POPT-05
**Success Criteria** (what must be TRUE):
  1. SignalAggregator supports 3 aggregation methods (confidence-weighted average, rank-based, Bayesian with regime prior), applies crowding penalty when >80% of strategies agree, and discounts stale signals based on data freshness
  2. SignalMonitor detects signal flips, conviction surges, and strategy divergence, and generates a daily signal summary report
  3. Monte Carlo VaR (10,000 simulations with t-Student marginals and Gaussian copula) and parametric VaR (Ledoit-Wolf shrinkage) produce 95% and 99% confidence VaR estimates, with marginal and component VaR decomposition by position
  4. Stress testing includes 6+ scenarios (existing 4 + BR Fiscal Crisis + Global Risk-Off), reverse stress testing finds scenarios producing a given max loss, and historical replay replays actual returns from crisis periods
  5. Black-Litterman model combines market equilibrium with agent views via confidence-weighted P/Q matrices, PositionSizer offers vol_target/fractional_kelly/risk_budget methods, and portfolio_state table persists positions with strategy attribution
**Plans:** 4/4 plans complete

Plans:
- [ ] 17-01-PLAN.md -- SignalAggregator v2 (3 methods: confidence-weighted, rank-based, Bayesian with regime prior), crowding penalty, staleness discount, SignalMonitor (flips, surges, divergence, daily summary)
- [ ] 17-02-PLAN.md -- Enhanced VaR (756-day lookback, marginal/component VaR decomposition), expanded stress scenarios (+BR Fiscal Crisis, +Global Risk-Off), reverse stress testing, historical replay
- [ ] 17-03-PLAN.md -- RiskLimitsManager v2 (daily/weekly loss tracking, risk budget), 4 risk API routes (/var, /stress, /limits, /dashboard)
- [ ] 17-04-PLAN.md -- Black-Litterman model (regime-adjusted views), mean-variance optimization, PositionSizer (vol_target, half-Kelly, risk_budget), portfolio_state table migration, portfolio API routes (/target, /rebalance-trades, /attribution)

### Phase 18: Dagster Orchestration, Monitoring & Reporting
**Goal**: Production-grade orchestration with Dagster replacing the custom pipeline, Grafana monitoring dashboards with alerting, and automated daily report generation -- making the system observable and operationally reliable
**Depends on**: Phase 17 (risk engine, portfolio optimization, and signal aggregation all functional -- the pipeline needs all components to orchestrate)
**Requirements**: ORCH-01, ORCH-02, ORCH-03, ORCH-04, MNTR-01, MNTR-02, MNTR-03, MNTR-04, REPT-01, REPT-02, REPT-03
**Success Criteria** (what must be TRUE):
  1. Dagster asset definitions cover the full pipeline: Bronze layer (6 connectors with cron schedules), Silver transforms, 5 Agents (with dependency chain), Signals, Portfolio Targets, Risk Metrics, and Daily Report -- all visible in dagster-webserver UI at port 3001
  2. User can run `make dagster` to start dagster-webserver and `make dagster-run-all` to materialize all assets in dependency order
  3. Grafana runs at port 3002 with TimescaleDB datasource and 4 provisioned dashboards (pipeline health, signal overview, risk dashboard, portfolio performance) loading automatically on first start
  4. AlertManager evaluates 10 rules (stale data, VaR breach/critical, drawdown warning/critical, limit breach, signal flip, conviction surge, pipeline failure, agent stale) and sends notifications via Slack and email
  5. DailyReportGenerator produces reports with 7 sections (Market Snapshot, Regime, Agent Views, Signals, Portfolio, Risk, Actions) in markdown and HTML formats, accessible via GET /api/v1/reports/daily/latest and sendable via POST /reports/daily/send
**Plans:** 4/4 plans complete

Plans:
- [x] 18-01-PLAN.md -- Dagster asset definitions (Bronze 6, Silver 3, Agents 5), Definitions module, Docker Compose dagster-webserver service, Makefile targets (make dagster, make dagster-run-all)
- [x] 18-02-PLAN.md -- Dagster assets for Signals (2), Portfolio (2), Risk (3), Report (1) with full dependency graph, updated Definitions with 22 total assets
- [x] 18-03-PLAN.md -- Grafana Docker Compose service (port 3002), TimescaleDB datasource provisioning, 4 dashboard JSONs (pipeline_health, signal_overview, risk_dashboard, portfolio_performance)
- [x] 18-04-PLAN.md -- AlertManager (10 rules, 30-min cooldown, Slack + email), 4 monitoring API routes, DailyReportGenerator (7 sections, markdown/HTML/email/Slack), 3 report API routes

### Phase 19: Dashboard v2, API Expansion, Testing & Verification
**Goal**: A React multi-page dashboard replacing the single-page HTML dashboard, expanded API with backtest/strategy/WebSocket endpoints, and comprehensive integration tests validating all v3.0 components end-to-end
**Depends on**: Phase 18 (all v3.0 components operational -- dashboard needs data from all subsystems, tests validate the complete system)
**Requirements**: DSHV-01, DSHV-02, DSHV-03, DSHV-04, DSHV-05, DSHV-06, APIV-01, APIV-02, APIV-03, APIV-04, TSTV-01, TSTV-02, TSTV-03, TSTV-04
**Success Criteria** (what must be TRUE):
  1. React dashboard with sidebar navigation serves 5 pages: Strategies (table with expandable backtest metrics), Signals (heatmap + flip timeline), Risk (VaR gauges, stress chart, limits, concentration pie), Portfolio (positions, equity curve, monthly heatmap, attribution), Agents (cards with signal/confidence/drivers + Cross-Asset narrative)
  2. Backtest API supports POST /backtest/run (trigger backtest), GET /backtest/results (retrieve results), POST /backtest/portfolio (portfolio backtest), GET /backtest/comparison (compare strategies)
  3. Strategy API serves GET /strategies/{id} (detail), GET /strategies/{id}/signal/latest, GET /strategies/{id}/signal/history, PUT /strategies/{id}/params (update parameters), and WebSocket channels push real-time updates for signals, portfolio, and alerts
  4. Full pipeline integration test runs DB -> transforms -> agents -> strategies -> signals -> portfolio -> risk -> report without error, and all API endpoints (v1 + v2 + v3) return 200 OK
  5. CI/CD pipeline updated with lint, unit tests, and integration tests (with service containers), and verification script (scripts/verify_phase2.py) validates all v3.0 components with a formatted pass/fail report
**Plans:** 4/4 plans complete

Plans:
- [ ] 19-01-PLAN.md -- Dashboard shell: App.jsx with HashRouter, collapsible Sidebar, useFetch/useWebSocket hooks, updated dashboard.html and route serving
- [ ] 19-02-PLAN.md -- Page components: StrategiesPage (expandable rows, filters), SignalsPage (heatmap, flip timeline), RiskPage (gauges, stress bars, limits, pie), PortfolioPage (positions, equity, heatmap, attribution), AgentsPage (cards, narrative)
- [ ] 19-03-PLAN.md -- API expansion: Backtest API (4 endpoints), Strategy Detail API (4 endpoints), WebSocket ConnectionManager (3 channels), updated main.py with 14 Swagger tags
- [ ] 19-04-PLAN.md -- Testing & verification: Pipeline E2E test, API v1/v2/v3 endpoint tests, GitHub Actions CI/CD (lint + test with service containers), verify_phase2.py component checklist

### v4.0 Phase Details (Active)

### Phase 20: PMS Database & Position Manager
**Goal**: Database foundation and core position management service for the Portfolio Management System -- 6 new tables (PortfolioPosition, TradeProposal, DecisionJournal, DailyBriefing, PositionPnLHistory) with TimescaleDB hypertables, plus PositionManager and MarkToMarketService that handle the full position lifecycle (open, close, MTM, P&L tracking)
**Depends on**: Phase 19 (v3.0 complete -- all infrastructure, strategies, risk engine, dashboard operational)
**Requirements**: PMS-DB-01, PMS-DB-02, PMS-DB-03, PMS-PM-01, PMS-PM-02, PMS-PM-03, PMS-PM-04, PMS-MTM-01, PMS-MTM-02
**Success Criteria** (what must be TRUE):
  1. Alembic migration creates 5 PMS tables (portfolio_positions, trade_proposals, decision_journal, daily_briefings, position_pnl_history) with position_pnl_history as TimescaleDB hypertable with compression
  2. PositionManager.open_position() creates position with risk metrics (DV01 for rates, delta for FX), records DecisionJournal entry automatically, and returns complete position dict
  3. PositionManager.close_position() calculates realized P&L, updates DecisionJournal with outcome, and marks position as closed
  4. PositionManager.mark_to_market() updates all open positions with current prices (from DB or manual override), computes unrealized P&L, and persists daily snapshot to position_pnl_history
  5. PositionManager.get_book() returns structured book with summary (AUM, leverage, P&L today/MTD/YTD), positions list, and by_asset_class breakdown
**Plans:** 1/2 plans executed

Plans:
- [ ] 20-01-PLAN.md -- PMS SQLAlchemy models (5 models), Alembic migration 009 (hypertable + immutability trigger), model registration and tests
- [ ] 20-02-PLAN.md -- PositionManager (open/close/MTM/book), MarkToMarketService (instrument-aware pricing, DV01, VaR), pricing module (B3 PU conventions), comprehensive tests

### Phase 21: Trade Workflow & PMS API
**Goal**: Human-in-the-loop trade approval workflow and comprehensive PMS API -- system generates trade proposals from signals, manager reviews with full risk context and LLM narrative, approves/rejects/modifies, and all decisions are logged immutably
**Depends on**: Phase 20 (PMS tables, PositionManager, MTM service operational)
**Requirements**: PMS-TW-01, PMS-TW-02, PMS-TW-03, PMS-TW-04, PMS-TW-05, PMS-API-01, PMS-API-02, PMS-API-03, PMS-API-04
**Success Criteria** (what must be TRUE):
  1. TradeWorkflowService.generate_proposals_from_signals() converts aggregated signals into TradeProposal records with conviction threshold (>0.55), pre-trade risk impact estimates, and LLM-generated narrative
  2. Manager can approve (with execution price/notional), reject (with mandatory notes), or modify-and-approve proposals via API -- each action creates immutable DecisionJournal entry
  3. Discretionary trades (manager-initiated, not system-generated) can be opened via API with mandatory thesis field
  4. PMS API serves 20+ endpoints across 3 routers: pms_portfolio (book, positions, P&L, equity curve, attribution), pms_trades (proposals, approve, reject, generate), pms_journal (entries, stats, outcome recording)
  5. All Pydantic request/response schemas defined and Swagger docs show PMS tags

### Phase 22: Morning Pack, Risk Monitor & Attribution
**Goal**: Three backend services that power the operational frontend -- MorningPackService generates daily briefings consolidating all system intelligence, RiskMonitorService provides real-time risk dashboard data, and PerformanceAttributionEngine decomposes P&L across multiple dimensions
**Depends on**: Phase 21 (trade workflow and PMS API operational)
**Requirements**: PMS-MP-01, PMS-MP-02, PMS-MP-03, PMS-RM-01, PMS-RM-02, PMS-RM-03, PMS-PA-01, PMS-PA-02, PMS-PA-03
**Success Criteria** (what must be TRUE):
  1. MorningPackService.generate() produces DailyBriefing with market snapshot, agent views, regime assessment, top signals, signal changes, portfolio state, trade proposals, macro narrative (LLM), and action items
  2. RiskMonitorService provides real-time risk data: VaR (parametric + MC), stress test results, limit utilization, concentration by asset class, and alert status
  3. PerformanceAttributionEngine decomposes P&L by strategy, asset class, instrument, and time period (daily, MTD, YTD, inception)
  4. Morning Pack API endpoint (GET /api/v1/pms/morning-pack/latest) returns the latest briefing and POST generates a new one
  5. All three services integrate with existing v3.0 components (agents, signals, risk engine, portfolio optimizer)

### Phase 23: Frontend Design System & Morning Pack Page
**Goal**: PMS frontend foundation -- a cohesive design system (colors, components, layout) and the Morning Pack page as the first operational screen, giving the manager a complete daily overview before markets open
**Depends on**: Phase 22 (Morning Pack, Risk Monitor, Attribution services operational)
**Requirements**: PMS-FE-DS-01, PMS-FE-DS-02, PMS-FE-MP-01, PMS-FE-MP-02, PMS-FE-MP-03
**Success Criteria** (what must be TRUE):
  1. PMS design system with color palette (semantic colors for P&L, risk levels, directions), component library (cards, tables, gauges, badges), and responsive layout grid
  2. Morning Pack page displays: market overview cards (key indicators with daily change), agent view summaries (signal + confidence per agent), trade proposal cards (with approve/reject actions), and active alerts banner
  3. PMS navigation integrates with existing React dashboard sidebar, adding PMS section with 7 sub-pages
  4. All PMS frontend components use CDN-loaded React + Tailwind consistent with v3.0 dashboard approach

### Phase 24: Frontend Position Book & Trade Blotter
**Goal**: Two core operational pages -- Position Book shows live portfolio with P&L and risk metrics, Trade Blotter provides the approval workflow interface for reviewing and acting on system-generated trade proposals
**Depends on**: Phase 23 (design system and Morning Pack page operational)
**Requirements**: PMS-FE-PB-01, PMS-FE-PB-02, PMS-FE-PB-03, PMS-FE-TB-01, PMS-FE-TB-02, PMS-FE-TB-03
**Success Criteria** (what must be TRUE):
  1. Position Book page shows live positions table with P&L (unrealized, daily, MTD), risk metrics (DV01/delta, VaR contribution), holding days, and strategy attribution -- grouped by asset class
  2. Position Book includes equity curve chart, P&L summary cards (today, MTD, YTD), and position open/close actions
  3. Trade Blotter shows pending proposals with conviction score, risk impact preview, and system rationale -- with approve/reject/modify action buttons
  4. Trade Blotter execution form captures execution price, notional, manager thesis, target price, stop loss, and time horizon
  5. Trade history tab shows all past proposals with final status and outcome

### Phase 25: Frontend Risk Monitor & Performance Attribution
**Goal**: Risk Monitor page provides visual risk dashboard with gauges and charts, Performance Attribution page shows multi-dimensional P&L decomposition -- both essential for daily risk oversight
**Depends on**: Phase 24 (Position Book and Trade Blotter operational)
**Requirements**: PMS-FE-RM-01, PMS-FE-RM-02, PMS-FE-RM-03, PMS-FE-PA-01, PMS-FE-PA-02
**Success Criteria** (what must be TRUE):
  1. Risk Monitor page shows VaR gauges (95%/99%, parametric + MC), stress test bar chart, risk limit utilization bars, and concentration pie chart by asset class
  2. Risk Monitor includes limit breach alerts, historical VaR chart, and scenario analysis comparison
  3. Performance Attribution page shows P&L waterfall chart (by strategy contribution), asset class attribution table, and time-series decomposition (daily bars, cumulative line)
  4. Attribution supports period selection (daily, MTD, QTD, YTD, custom range)

### Phase 26: Frontend Decision Journal, Agent Intel & Compliance
**Goal**: Decision Journal page for reviewing all trading decisions with outcome tracking, Agent Intelligence Hub for viewing agent signals and narratives, and Compliance module for audit trail and integrity verification
**Depends on**: Phase 25 (Risk Monitor and Attribution pages operational)
**Requirements**: PMS-FE-DJ-01, PMS-FE-DJ-02, PMS-FE-AI-01, PMS-FE-AI-02, PMS-FE-CO-01, PMS-FE-CO-02
**Success Criteria** (what must be TRUE):
  1. Decision Journal page shows timeline view of all decisions (OPEN, CLOSE, REJECT, NOTE) with expandable detail cards showing full context (macro snapshot, portfolio state, manager rationale)
  2. Journal includes outcome tracking (realized P&L, holding days, lessons learned) and search/filter by date, asset class, decision type
  3. Agent Intelligence Hub shows agent cards with latest signal, confidence, key drivers, and risks -- plus full Cross-Asset narrative display
  4. Compliance module provides audit trail viewer, hash integrity verification for journal entries, and export functionality

### Phase 27: Redis Cache, Dagster PMS, Go-Live & Verification
**Goal**: Production hardening -- Redis caching for PMS query performance, Dagster integration for automated daily PMS pipeline (MTM, proposals, briefings, attribution), go-live checklist, disaster recovery procedures, and comprehensive verification script
**Depends on**: Phase 26 (all PMS frontend pages operational)
**Requirements**: PMS-CACHE-01, PMS-CACHE-02, PMS-DAG-01, PMS-DAG-02, PMS-GL-01, PMS-GL-02, PMS-GL-03, PMS-VER-01
**Success Criteria** (what must be TRUE):
  1. Redis caching layer accelerates PMS queries (book, positions, briefing) with configurable TTL and cache invalidation on writes
  2. Dagster PMS daily pipeline: MTM all positions -> generate trade proposals -> generate morning pack -> compute attribution -- integrated with existing Dagster definitions
  3. Go-live checklist covers: database backup/restore, monitoring alerts for PMS tables, runbook for daily operations, disaster recovery procedures
  4. Verification script (scripts/verify_phase3.py) validates all PMS components end-to-end with formatted pass/fail report
  5. All 20 etapas from guide verified, documentation updated

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
| 14. Backtesting Engine v2 & Strategy Framework | 3/3 | Complete    | 2026-02-22 |
| 15. New Trading Strategies | 5/5 | Complete   | 2026-02-22 |
| 16. Cross-Asset Agent v2 & NLP Pipeline | 3/3 | Complete    | 2026-02-22 |
| 17. Signal Aggregation v2, Risk Engine v2 & Portfolio Optimization | 4/4 | Complete    | 2026-02-23 |
| 18. Dagster Orchestration, Monitoring & Reporting | 4/4 | Complete    | 2026-02-23 |
| 19. Dashboard v2, API Expansion, Testing & Verification | 4/4 | Complete    | 2026-02-23 |

### v4.0 Portfolio Management System

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 20. PMS Database & Position Manager | 1/2 | In Progress|  |
| 21. Trade Workflow & PMS API | 0/0 | Not Started | - |
| 22. Morning Pack, Risk Monitor & Attribution | 0/0 | Not Started | - |
| 23. Frontend Design System & Morning Pack Page | 0/0 | Not Started | - |
| 24. Frontend Position Book & Trade Blotter | 0/0 | Not Started | - |
| 25. Frontend Risk Monitor & Performance Attribution | 0/0 | Not Started | - |
| 26. Frontend Decision Journal, Agent Intel & Compliance | 0/0 | Not Started | - |
| 27. Redis Cache, Dagster PMS, Go-Live & Verification | 0/0 | Not Started | - |
