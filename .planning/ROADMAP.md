# Roadmap: Macro Fund System

## Overview

This roadmap covers two milestones of the macro trading system for a global macro hedge fund focused on Brazil and the US.

**v1.0 (Phases 1-6, Complete):** Data infrastructure — Docker stack, 11 connectors, 250+ series, TimescaleDB hypertables, transforms, FastAPI API, data quality framework. All 65 requirements delivered.

**v2.0 (Phases 7-13, Active):** Quantitative models and agents — 5 analytical agents with quantitative models, event-driven backtesting engine, 8 trading strategies, signal aggregation, risk management, daily orchestration pipeline, LLM narrative generation, and monitoring dashboard. All 88 requirements mapped.

The build follows the agent pipeline: framework (base classes, data loader) enables agents (models, signals), agents enable strategies (trading logic), strategies feed into portfolio construction and risk management, and everything converges at the daily pipeline with dashboard and API. Point-in-time correctness — established in v1.0 via release_time tracking — is the foundation for backtesting integrity across all v2.0 components.

## Phases

**Phase Numbering:**
- Phases 1-6: v1.0 Data Infrastructure (complete)
- Phases 7-13: v2.0 Quantitative Models & Agents (active)

### v1.0 Phases (Complete)

- [x] **Phase 1: Foundation** - Docker stack, ORM models, hypertables, migrations, config, and database engines
- [x] **Phase 2: Core Connectors** - Base connector pattern, 4 core data sources (BCB SGS, FRED, Yahoo, PTAX), data integrity utilities, and test infrastructure
- [x] **Phase 3: Extended Connectors** - Remaining 7 data sources (Focus, B3/Tesouro, IBGE, STN, CFTC, US Treasury, FX Flow)
- [x] **Phase 4: Seed and Backfill** - Instrument/series metadata seeding, backfill orchestrator, and historical data population (2010-present)
- [x] **Phase 5: Transforms** - Curve construction, returns/vol/z-scores, macro calculations, and advanced indicators (silver layer)
- [x] **Phase 6: API and Quality** - FastAPI serving layer, all endpoints, data quality framework, verification, and CI pipeline (gold layer)

### v2.0 Phases (Active)

- [x] **Phase 7: Agent Framework & Data Loader** - BaseAgent ABC, signal/report dataclasses, PointInTimeDataLoader, AgentRegistry, DB migration, dependency installation
- [x] **Phase 8: Inflation & Monetary Policy Agents** - InflationAgent (Phillips Curve, IPCA bottom-up, surprise, persistence) and MonetaryPolicyAgent (Taylor Rule, Kalman r*, Selic path, term premium) (completed 2026-02-21)
- [x] **Phase 9: Fiscal & FX Equilibrium Agents** - FiscalAgent (DSA model, fiscal impulse, dominance risk) and FxEquilibriumAgent (BEER model, carry-to-risk, flows, CIP basis)
- [ ] **Phase 10: Cross-Asset Agent & Backtesting Engine** - CrossAssetAgent (regime detection, correlations, sentiment) and BacktestEngine (portfolio tracking, metrics, PIT enforcement)
- [ ] **Phase 11: Trading Strategies** - BaseStrategy ABC, 8 initial strategies (4 rates, 1 inflation, 1 FX, 1 cupom cambial, 1 sovereign)
- [ ] **Phase 12: Portfolio Construction & Risk Management** - Signal aggregation, portfolio constructor, capital allocator, VaR, stress testing, limits, circuit breakers
- [ ] **Phase 13: Pipeline, LLM, Dashboard, API & Tests** - Daily orchestration pipeline, Claude API narrative, HTML dashboard, 9 new API endpoints, integration tests, verification script

## Phase Details

### Phase 7: Agent Framework & Data Loader
**Goal**: A complete agent infrastructure — abstract base class, typed signal/report structures, point-in-time data access layer, and agent registry — that all 5 analytical agents can build on
**Depends on**: Phase 6 (v1.0 complete — data flowing, API serving, transforms available)
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06, AGENT-07
**Success Criteria** (what must be TRUE):
  1. BaseAgent abstract class enforces Template Method pattern: load_data → compute_features → run_models → generate_narrative, with concrete run() and backtest_run() methods
  2. AgentSignal dataclass captures signal_id, direction (LONG/SHORT/NEUTRAL), strength (STRONG/MODERATE/WEAK/NO_SIGNAL), confidence (0-1), value, horizon_days, and metadata dict
  3. PointInTimeDataLoader queries macro_series, curves, market_data, and flow_data with WHERE release_time <= as_of_date constraint, returning pandas DataFrames
  4. AgentRegistry.run_all(as_of_date) executes agents in dependency order (inflation → monetary → fiscal → fx → cross_asset) and returns dict of AgentReports
  5. Alembic migration creates agent_reports table (agent_id, as_of_date, narrative, diagnostics JSON) and signals persist via ON CONFLICT DO NOTHING
  6. statsmodels and scikit-learn are installed and importable for quantitative models
**Plans**: 2 plans

Plans:
- [x] 07-01-PLAN.md — BaseAgent ABC, AgentSignal/AgentReport dataclasses, SignalDirection/SignalStrength enums, PointInTimeDataLoader with PIT queries, and dependency installation (statsmodels, scikit-learn)
- [x] 07-02-PLAN.md — AgentRegistry with ordered execution, signal persistence to signals hypertable, Alembic migration for agent_reports table, and agent framework tests

### Phase 8: Inflation & Monetary Policy Agents
**Goal**: Two fully functional analytical agents — InflationAgent monitoring BR+US inflation dynamics and MonetaryPolicyAgent analyzing central bank policy — each producing quantitative signals from real models
**Depends on**: Phase 7
**Requirements**: INFL-01, INFL-02, INFL-03, INFL-04, INFL-05, INFL-06, INFL-07, MONP-01, MONP-02, MONP-03, MONP-04, MONP-05, MONP-06, TESTV2-01, TESTV2-02
**Success Criteria** (what must be TRUE):
  1. InflationAgent.run(as_of_date) produces 6+ signals: INFLATION_BR_PHILLIPS (OLS Phillips Curve), INFLATION_BR_BOTTOMUP (9-component IPCA forecast), INFLATION_BR_SURPRISE (actual vs Focus z-score), INFLATION_BR_PERSISTENCE (composite 0-100 score), INFLATION_US_TREND (PCE core analysis), INFLATION_BR_COMPOSITE (weighted average)
  2. PhillipsCurveModel fits OLS regression (core_inflation ~ expectations + output_gap + fx_passthrough + commodity_change) on trailing data and predicts 12M core inflation
  3. MonetaryPolicyAgent.run(as_of_date) produces 5+ signals: MONETARY_BR_TAYLOR (policy gap), MONETARY_BR_SELIC_PATH (market vs model), MONETARY_BR_TERM_PREMIUM (DI term premium estimate), MONETARY_US_FED_STANCE (US policy gap), MONETARY_BR_COMPOSITE
  4. TaylorRuleModel computes BCB-modified Taylor rate: i* = r* + π_e + α(π_e - π*) + β(y_gap) + γ(inertia) and signals when policy gap exceeds 100bps
  5. KalmanFilterRStar estimates time-varying natural rate r* from Selic history, inflation expectations, and output gap using state-space model
  6. Unit tests verify feature computation returns expected keys and model signals have correct direction for known inputs
**Plans**: 3 plans

Plans:
- [ ] 08-01-PLAN.md — InflationFeatureEngine (~30 BR + ~15 US features), PhillipsCurveModel (OLS), IpcaBottomUpModel (9-component seasonal forecast)
- [ ] 08-02-PLAN.md — InflationSurpriseModel, InflationPersistenceModel, UsInflationTrendModel, InflationAgent orchestration, composite signal, and inflation tests
- [ ] 08-03-PLAN.md — MonetaryFeatureEngine (BR DI curve shape + US UST curve), TaylorRuleModel, KalmanFilterRStar, SelicPathModel, TermPremiumModel, UsFedAnalysis, MonetaryPolicyAgent orchestration, and monetary tests

### Phase 9: Fiscal & FX Equilibrium Agents
**Goal**: Two more analytical agents — FiscalAgent assessing Brazil's debt sustainability and FxEquilibriumAgent modeling USDBRL fair value — completing 4 of 5 agents
**Depends on**: Phase 8
**Requirements**: FISC-01, FISC-02, FISC-03, FISC-04, FXEQ-01, FXEQ-02, FXEQ-03, FXEQ-04, FXEQ-05
**Success Criteria** (what must be TRUE):
  1. FiscalAgent.run(as_of_date) produces 3+ signals: FISCAL_BR_DSA (debt trajectory under 4 scenarios), FISCAL_BR_IMPULSE (cyclically-adjusted fiscal expansion/contraction), FISCAL_BR_DOMINANCE_RISK (composite 0-100 score)
  2. DebtSustainabilityModel projects debt/GDP over 5Y horizon under baseline, adjustment, stress, and tailwind scenarios using d_{t+1} = d_t*(1+r)/(1+g) - pb
  3. FxEquilibriumAgent.run(as_of_date) produces 4+ signals: FX_BR_BEER (USDBRL misalignment vs BEER fair value), FX_BR_CARRY_RISK (carry-to-risk ratio), FX_BR_FLOW (composite flow z-score), FX_BR_CIP_BASIS (CIP deviation)
  4. BeerModel fits OLS: USDBRL = f(terms_of_trade, real_rate_diff, NFA, productivity_diff) and signals when misalignment exceeds 5%
  5. All agent signals have confidence in [0,1] and direction in {LONG, SHORT, NEUTRAL}
**Plans**: 2 plans

Plans:
- [x] 09-01-PLAN.md — FiscalFeatureEngine (debt ratios, r-g dynamics, debt composition), DebtSustainabilityModel (IMF DSA), FiscalImpulseModel, FiscalDominanceRisk, FiscalAgent orchestration, and fiscal tests
- [x] 09-02-PLAN.md — FxFeatureEngine (BEER inputs, carry, flows, CIP, CFTC), BeerModel (OLS), CarryToRiskModel, FlowModel, CipBasisModel, FxEquilibriumAgent orchestration, and FX tests

### Phase 10: Cross-Asset Agent & Backtesting Engine
**Goal**: The final agent (CrossAssetAgent providing regime context) and a complete event-driven backtesting engine with point-in-time correctness for strategy validation
**Depends on**: Phase 9
**Requirements**: CRSA-01, CRSA-02, CRSA-03, BACK-01, BACK-02, BACK-03, BACK-04, BACK-05, BACK-06, BACK-07, BACK-08, TESTV2-03
**Success Criteria** (what must be TRUE):
  1. CrossAssetAgent.run(as_of_date) produces 3 signals: CROSSASSET_REGIME (risk-on/off score -1 to +1), CROSSASSET_SENTIMENT (fear-to-greed 0-100), CROSSASSET_CORRELATION (correlation break detection)
  2. RegimeDetectionModel scores VIX, credit spreads, DXY, EM flows, UST curve slope, and BR fiscal into a composite regime indicator
  3. BacktestEngine.run(strategy) iterates over business days, calls strategy.generate_signals(as_of_date) with point-in-time data, applies rebalance with transaction costs and slippage, and computes complete equity curve
  4. Portfolio class tracks positions, cash, equity, and trade log with mark-to-market using PointInTimeDataLoader
  5. BacktestResult contains all metrics: annualized return/vol, Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor, monthly returns
  6. Alembic migration creates strategy_signals hypertable and backtest_results table
  7. Point-in-time enforcement verified: strategy cannot access data with release_time > as_of_date during backtest
**Plans**: 3 plans

Plans:
- [ ] 10-01-PLAN.md — RegimeDetectionModel, CorrelationAnalysis, RiskSentimentIndex, CrossAssetAgent orchestration (runs last in registry), and cross-asset tests
- [ ] 10-02-PLAN.md — BacktestEngine with BacktestConfig, Portfolio class (positions, equity curve, trade log), rebalance with costs/slippage, PIT enforcement, Alembic migration for strategy_signals and backtest_results
- [ ] 10-03-PLAN.md — BacktestResult metrics computation (Sharpe, Sortino, Calmar, max DD, win rate, profit factor), formatted report generation, equity curve chart, persistence to backtest_results, and backtesting tests

### Phase 11: Trading Strategies
**Goal**: BaseStrategy abstraction and 8 initial trading strategies spanning rates, inflation, FX, cupom cambial, and sovereign risk — each consuming agent signals and producing tradeable positions
**Depends on**: Phase 10
**Requirements**: STRAT-01, STRAT-02, STRAT-03, STRAT-04, STRAT-05, STRAT-06, STRAT-07, STRAT-08, STRAT-09
**Success Criteria** (what must be TRUE):
  1. BaseStrategy ABC enforces StrategyConfig (id, asset class, instruments, rebalance frequency, leverage/position limits, stop/take-profit) and generate_signals(as_of_date) → list[StrategyPosition]
  2. RATES_BR_01 Carry & Roll-Down computes carry-to-risk at each DI curve tenor and goes long at optimal point when ratio exceeds threshold
  3. RATES_BR_02 Taylor Rule Misalignment trades DI direction when gap between Taylor-implied rate and market pricing exceeds 100bps
  4. FX_BR_01 Carry & Fundamental composites carry-to-risk (40%), BEER misalignment (35%), and flow score (25%) with regime adjustment from CrossAssetAgent
  5. All 8 strategies produce valid StrategyPosition outputs with weight in [-1,1], confidence in [0,1], and respect their configured position limits
  6. ALL_STRATEGIES dict exports all 8 strategies by ID for backtesting and pipeline integration
**Plans**: 3 plans

Plans:
- [ ] 11-01-PLAN.md — BaseStrategy ABC with StrategyConfig and StrategyPosition dataclasses, signals_to_positions with constraint enforcement, and RATES_BR_01 Carry & Roll-Down + RATES_BR_02 Taylor Misalignment strategies with tests
- [ ] 11-02-PLAN.md — RATES_BR_03 Curve Slope (flattener/steepener), RATES_BR_04 US Rates Spillover (spread mean reversion), INF_BR_01 Breakeven Inflation Trade, and strategy tests
- [ ] 11-03-PLAN.md — FX_BR_01 Carry & Fundamental, CUPOM_01 CIP Basis Mean Reversion, SOV_BR_01 Fiscal Risk Premium, ALL_STRATEGIES registry, and strategy tests

### Phase 12: Portfolio Construction & Risk Management
**Goal**: Signal aggregation across agents and strategies, portfolio construction with risk-budget scaling, and a complete risk management engine with VaR, stress testing, limits, and circuit breakers
**Depends on**: Phase 11
**Requirements**: PORT-01, PORT-02, PORT-03, PORT-04, RISK-01, RISK-02, RISK-03, RISK-04, RISK-05, RISK-06, RISK-07, RISK-08, TESTV2-04
**Success Criteria** (what must be TRUE):
  1. SignalAggregator combines agent signals into directional consensus per asset class and detects conflicting signals (e.g., inflation hawkish but monetary dovish)
  2. PortfolioConstructor converts strategy positions to net portfolio weights with risk-budget scaling and regime adjustment (RISK_OFF → reduce 50%)
  3. CapitalAllocator enforces portfolio constraints: max 3x leverage, max 25% single position, max 50% asset class concentration
  4. VaRCalculator computes historical VaR (95% and 99%) and Expected Shortfall from portfolio returns
  5. StressTester runs 4+ historical scenarios (Taper Tantrum 2013, BR Crisis 2015, COVID 2020, Rate Shock 2022) and reports portfolio P&L impact
  6. DrawdownManager implements 3-level circuit breakers: L1 (-3%) reduce 25%, L2 (-5%) reduce 50%, L3 (-8%) close all
  7. RiskMonitor generates aggregate report: VaR, stress tests, limit utilization, circuit breaker status
**Plans**: 3 plans

Plans:
- [ ] 12-01-PLAN.md — SignalAggregator (directional consensus, conflict detection), PortfolioConstructor (risk-budget scaling, regime adjustment), CapitalAllocator (constraint enforcement, rebalance threshold)
- [ ] 12-02-PLAN.md — VaRCalculator (historical + parametric), Expected Shortfall, StressTester (4+ scenarios with position-level P&L), stress scenario definitions
- [ ] 12-03-PLAN.md — RiskLimitChecker (9 configurable limits), pre-trade checking, DrawdownManager (3-level circuit breakers), RiskMonitor (aggregate report), and risk management tests

### Phase 13: Pipeline, LLM, Dashboard, API & Tests
**Goal**: A complete daily orchestration pipeline from data ingestion to risk report, LLM-powered narrative generation, a self-contained HTML dashboard, extended API endpoints, and comprehensive tests validating the entire v2.0 system
**Depends on**: Phase 12
**Requirements**: PIPE-01, PIPE-02, PIPE-03, LLM-01, LLM-02, LLM-03, LLM-04, DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, APIV2-01, APIV2-02, APIV2-03, APIV2-04, APIV2-05, APIV2-06, APIV2-07, APIV2-08, APIV2-09, TESTV2-05, TESTV2-06, TESTV2-07
**Success Criteria** (what must be TRUE):
  1. Daily pipeline (scripts/daily_run.py) executes 8 steps in sequence: ingest → quality → agents → aggregate → strategies → portfolio → risk → report, with --date and --dry-run CLI options
  2. NarrativeGenerator uses Claude API (Anthropic SDK) to produce a daily macro brief from agent signals and features, with template-based fallback when API key is unavailable
  3. HTML dashboard served at GET /dashboard shows 4 tabs: Macro Dashboard (key indicators), Agent Signals (5 agent cards with consensus), Portfolio (positions, VaR, leverage), Backtests (strategy results table, equity curve chart)
  4. 9 new API endpoints serve agent reports, signals, strategies, portfolio positions, risk metrics, and daily brief — all returning 200 OK
  5. Integration test runs full pipeline (agents → strategies → portfolio → risk) for a known date without error
  6. All API endpoints (v1 + v2) return 200 OK via FastAPI TestClient
  7. Verification script updated to validate Phase 0 + Phase 1 components end-to-end
**Plans**: 4 plans

Plans:
- [ ] 13-01-PLAN.md — Daily pipeline script (8-step orchestration with CLI), formatted summary output, Makefile targets (daily, daily-dry)
- [ ] 13-02-PLAN.md — NarrativeGenerator (Claude API + template fallback), ANTHROPIC_API_KEY config, agent narrative integration, daily-brief endpoint
- [ ] 13-03-PLAN.md — HTML dashboard (React + Tailwind + Recharts via CDN, 4 tabs, auto-refresh, dark theme), FastAPI static serving at /dashboard
- [ ] 13-04-PLAN.md — 9 new API endpoints (agents, signals, strategies, portfolio, risk), integration tests (pipeline + API), verification script update, Makefile targets

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13

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
| 8. Inflation & Monetary Agents | 3/3 | Complete    | 2026-02-21 |
| 9. Fiscal & FX Agents | 2/2 | Complete | 2026-02-21 |
| 10. Cross-Asset & Backtesting | 0/3 | Not started | - |
| 11. Trading Strategies | 0/3 | Not started | - |
| 12. Portfolio & Risk | 0/3 | Not started | - |
| 13. Pipeline, LLM, Dashboard, API & Tests | 0/4 | Not started | - |
