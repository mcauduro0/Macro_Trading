# Roadmap: Macro Fund System

## Overview

This roadmap covers three milestones of the macro trading system for a global macro hedge fund focused on Brazil and the US.

**v1.0 (Phases 1-6, Complete):** Data infrastructure — Docker stack, 11 connectors, 250+ series, TimescaleDB hypertables, transforms, FastAPI API, data quality framework. All 65 requirements delivered.

**v2.0 (Phases 7-13, Complete):** Quantitative models and agents — 5 analytical agents with quantitative models, event-driven backtesting engine, 8 trading strategies, signal aggregation, risk management, daily orchestration pipeline, LLM narrative generation, and monitoring dashboard. All 88 requirements delivered.

**v3.0 (Phases 14-19, Active):** Strategy engine, risk & portfolio management — expand from 8 to 24+ trading strategies across all asset classes (FX, rates, inflation, cupom cambial, sovereign, cross-asset), enhanced backtesting engine (portfolio-level, walk-forward, deflated Sharpe), NLP pipeline for COPOM/FOMC communications, enhanced Cross-Asset Agent with LLM narrative, signal aggregation v2 (Bayesian, crowding, staleness), risk engine v2 (Monte Carlo VaR, reverse stress, component VaR), portfolio optimization (Black-Litterman, Kelly sizing), Dagster production orchestration, Grafana monitoring, React multi-page dashboard, and comprehensive integration testing. 77 requirements mapped across 6 phases.

## Phases

**Phase Numbering:**
- Phases 1-6: v1.0 Data Infrastructure (complete)
- Phases 7-13: v2.0 Quantitative Models & Agents (complete)
- Phases 14-19: v3.0 Strategy Engine, Risk & Portfolio Management (active)
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

### v3.0 Phases (Active)

- [ ] **Phase 14: Backtesting Engine v2 & Strategy Framework** - Enhanced StrategySignal, StrategyRegistry, portfolio-level backtesting, walk-forward validation, deflated Sharpe, transaction cost model, tearsheet generation, DB migrations
- [ ] **Phase 15: New Trading Strategies** - 16 new strategies across FX (4), rates (4), inflation (2), cupom cambial (1), sovereign (3), cross-asset (2)
- [ ] **Phase 16: Cross-Asset Agent v2 & NLP Pipeline** - Enhanced CrossAssetView, HMM regime classification, consistency checking, LLM narrative, COPOM/FOMC scrapers, hawk/dove sentiment analysis
- [ ] **Phase 17: Signal Aggregation v2, Risk Engine v2 & Portfolio Optimization** - Bayesian aggregation, crowding/staleness, Monte Carlo VaR, reverse stress, component VaR, Black-Litterman, Kelly sizing
- [ ] **Phase 18: Dagster Orchestration, Monitoring & Reporting** - Dagster asset definitions, dependency graph, Grafana dashboards, AlertManager, daily report generator
- [ ] **Phase 19: Dashboard v2, API Expansion, Testing & Verification** - React multi-page dashboard (5 pages), backtest/strategy/WebSocket APIs, integration tests, CI/CD, verification script

## Phase Details

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
**Plans**: TBD

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
**Plans**: TBD

Plans:
- [ ] 15-01: FX strategies -- FX-02 Carry-Adjusted Momentum, FX-03 Flow-Based Tactical, FX-04 Vol Surface RV, FX-05 Terms of Trade
- [ ] 15-02: Rates strategies -- RATES-03 BR-US Spread, RATES-04 Term Premium, RATES-05 FOMC Event, RATES-06 COPOM Event
- [ ] 15-03: Inflation strategies (INF-02 IPCA Surprise, INF-03 Inflation Carry) and Cupom Cambial (CUPOM-02 Onshore-Offshore Spread)
- [ ] 15-04: Sovereign strategies (SOV-01 CDS Curve, SOV-02 EM Relative Value, SOV-03 Rating Migration) and Cross-Asset (CROSS-01 Regime Allocation, CROSS-02 Risk Appetite)

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
**Plans**: TBD

Plans:
- [ ] 16-01: CrossAssetView dataclass, HMM regime classification (with rule-based fallback), consistency checking, LLM narrative generation
- [ ] 16-02: COPOMScraper, FOMCScraper, nlp_documents table migration
- [ ] 16-03: CentralBankSentimentAnalyzer (term dictionary PT+EN, optional LLM), NLPProcessor pipeline (clean, score, extract, compare, persist)

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
**Plans**: TBD

Plans:
- [ ] 17-01: SignalAggregator v2 (3 methods, crowding penalty, staleness discount), SignalMonitor (flips, surges, divergence, daily summary)
- [ ] 17-02: Monte Carlo VaR (t-Student, Gaussian copula, Cholesky), parametric VaR (Ledoit-Wolf), marginal/component VaR decomposition, expanded stress scenarios, reverse stress, historical replay
- [ ] 17-03: RiskLimitsManager v2 (daily/weekly loss, risk budget), risk API routes (/var, /stress, /limits, /dashboard)
- [ ] 17-04: Black-Litterman model, mean-variance optimization, PositionSizer (vol_target, Kelly, risk_budget), portfolio_state table migration, portfolio API routes

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
**Plans**: TBD

Plans:
- [ ] 18-01: Dagster asset definitions (Bronze, Silver, Agents), Dagster definitions module, Docker Compose service, Makefile targets
- [ ] 18-02: Dagster assets for Signals, Portfolio, Risk, Report with full dependency graph
- [ ] 18-03: Grafana Docker Compose service, datasource provisioning, 4 dashboard JSONs
- [ ] 18-04: AlertManager (10 rules, Slack + email), monitoring API routes, DailyReportGenerator (7 sections, markdown/HTML/email/Slack), report API routes

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
**Plans**: TBD

Plans:
- [ ] 19-01: React dashboard App.tsx with Router, Tailwind CSS, recharts, sidebar navigation
- [ ] 19-02: StrategiesPage, SignalsPage, RiskPage, PortfolioPage, AgentsPage components
- [ ] 19-03: Backtest API routes, strategy detail API routes, WebSocket ConnectionManager (3 channels), updated main.py with all routers and Swagger tags
- [ ] 19-04: Integration tests (full pipeline E2E, all API endpoints), CI/CD update, verification script

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> ... -> 13 -> 14 -> 15 -> 16 -> 17 -> 18 -> 19

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
| 14. Backtesting Engine v2 & Strategy Framework | 0/3 | Not started | - |
| 15. New Trading Strategies | 0/4 | Not started | - |
| 16. Cross-Asset Agent v2 & NLP Pipeline | 0/3 | Not started | - |
| 17. Signal Aggregation v2, Risk Engine v2 & Portfolio Optimization | 0/4 | Not started | - |
| 18. Dagster Orchestration, Monitoring & Reporting | 0/4 | Not started | - |
| 19. Dashboard v2, API Expansion, Testing & Verification | 0/4 | Not started | - |
