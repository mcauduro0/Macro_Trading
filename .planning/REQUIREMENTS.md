# Requirements: Macro Fund System

**Defined:** 2026-02-19 (v1) | 2026-02-20 (v2)
**Core Value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system — the foundation for analytical agents, quantitative strategies, and risk management

## v1 Requirements (Complete)

All 65 v1 requirements delivered in milestone v1.0 Data Infrastructure. See `.planning/MILESTONES.md` for archive.

Summary: INFRA (7/7), CONN (12/12), DATA (5/5), SEED (5/5), XFORM (14/14), API (12/12), QUAL (6/6), TEST (4/4)

## v2 Requirements

Requirements for milestone v2.0 Quantitative Models & Agents. Each maps to roadmap phases.

### Agent Framework

- [x] **AGENT-01**: BaseAgent abstract class with Template Method pattern: load_data → compute_features → run_models → generate_narrative → persist_signals
- [x] **AGENT-02**: AgentSignal dataclass with signal_id, direction (LONG/SHORT/NEUTRAL), strength, confidence (0-1), value, horizon_days, metadata
- [x] **AGENT-03**: AgentReport dataclass combining signals, narrative text, model diagnostics, and data quality flags
- [x] **AGENT-04**: PointInTimeDataLoader utility querying macro_series, curves, market_data with release_time <= as_of_date constraint
- [x] **AGENT-05**: AgentRegistry managing execution order (inflation → monetary → fiscal → fx → cross_asset) with run_all(as_of_date)
- [x] **AGENT-06**: Signal persistence to signals hypertable with ON CONFLICT DO NOTHING idempotency
- [x] **AGENT-07**: Alembic migration adding agent_reports table (agent_id, as_of_date, narrative, diagnostics JSON)

### Analytical Agents

- [x] **INFL-01**: InflationAgent with InflationFeatureEngine computing ~30 BR features (IPCA headline/cores/components/diffusion, Focus expectations, activity context) and ~15 US features (CPI/PCE core, breakevens, Michigan survey)
- [x] **INFL-02**: PhillipsCurveModel — expectations-augmented OLS: core_inflation = f(expectations, output_gap, fx_passthrough, commodity_change) on trailing 10Y window
- [x] **INFL-03**: IpcaBottomUpModel — component-level forecast for 9 IPCA groups using seasonal patterns + specific drivers, aggregated by IBGE weights
- [x] **INFL-04**: InflationSurpriseModel — z-score of rolling 3-month actual-vs-Focus surprise average as regime indicator
- [x] **INFL-05**: InflationPersistenceModel — composite score (0-100) from diffusion level, core acceleration, services momentum, expectations anchoring
- [x] **INFL-06**: UsInflationTrendModel — PCE core 3M SAAR analysis, target gap, supercore momentum
- [x] **INFL-07**: Composite INFLATION_BR_COMPOSITE signal aggregating sub-model outputs

- [x] **MONP-01**: MonetaryPolicyAgent with MonetaryFeatureEngine computing BR features (Selic target, DI curve shape/slope/curvature, real rate gap, policy inertia) and US features (Fed Funds, UST curve, Taylor Rule inputs, NFCI)
- [x] **MONP-02**: TaylorRuleModel — classic and BCB-modified: i* = r* + π_e + α(π_e - π*) + β(y_gap) + γ(inertia), with policy gap signal
- [x] **MONP-03**: KalmanFilterRStar — state-space estimation of time-varying natural rate r* using Selic history, inflation expectations, output gap
- [x] **MONP-04**: SelicPathModel — extract meeting-by-meeting implied Selic from DI curve, compare with Focus survey and model terminal rate
- [x] **MONP-05**: TermPremiumModel — estimate term premium as DI(n) minus expected short rate path from Focus, signal when TP extreme
- [x] **MONP-06**: UsFedAnalysis — US Taylor Rule, Fed policy gap, financial conditions assessment

- [x] **FISC-01**: FiscalAgent with FiscalFeatureEngine computing debt ratios, primary balance, r-g dynamics, debt composition, financing needs, market signals
- [x] **FISC-02**: DebtSustainabilityModel — IMF DSA projecting debt/GDP under 4 scenarios (baseline, adjustment, stress, tailwind) over 5Y horizon
- [x] **FISC-03**: FiscalImpulseModel — cyclically-adjusted primary balance change as fiscal expansion/contraction indicator
- [x] **FISC-04**: FiscalDominanceRisk — composite score (0-100) assessing when fiscal policy overwhelms monetary policy

- [x] **FXEQ-01**: FxEquilibriumAgent with FxFeatureEngine computing BEER inputs (terms of trade, real rate differential, NFA, productivity), carry-to-risk, flows, CIP basis, CFTC positioning, global context
- [x] **FXEQ-02**: BeerModel — Behavioral Equilibrium Exchange Rate via OLS: USDBRL_fair = f(ToT, r_diff, NFA, productivity_diff), misalignment signal
- [x] **FXEQ-03**: CarryToRiskModel — (BR_rate - US_rate) / implied_vol as carry attractiveness signal
- [x] **FXEQ-04**: FlowModel — composite flow score from BCB FX flow z-score, CFTC positioning z-score, BCB swap stock changes
- [x] **FXEQ-05**: CipBasisModel — cupom cambial minus SOFR as CIP deviation signal for funding stress

- [x] **CRSA-01**: CrossAssetAgent with RegimeDetectionModel scoring -1 (risk-off) to +1 (risk-on) from VIX, credit spreads, DXY, EM flows, UST curve slope, BR fiscal
- [x] **CRSA-02**: CorrelationAnalysis — rolling 63d correlations for 5 key pairs (USDBRL/DXY, DI/UST, IBOV/SP500, USDBRL/VIX, Oil/BRL) with break detection at |z|>2
- [x] **CRSA-03**: RiskSentimentIndex — composite 0-100 index (fear-to-greed) from VIX, HY OAS, DXY, CFTC BRL, BCB flows, CDS/EMBI proxy

### Backtesting Engine

- [x] **BACK-01**: BacktestEngine with BacktestConfig (start/end date, initial capital, rebalance frequency, transaction costs, slippage, max leverage)
- [x] **BACK-02**: Portfolio class tracking positions, cash, equity curve, trade log with mark-to-market using PointInTimeDataLoader
- [x] **BACK-03**: Rebalance execution applying target weights, transaction cost (bps), slippage (bps), and position limit enforcement
- [x] **BACK-04**: BacktestResult with complete metrics: total/annualized return, volatility, Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor, monthly returns
- [x] **BACK-05**: Point-in-time correctness enforcement — strategy.generate_signals(as_of_date) only sees data with release_time <= as_of_date
- [x] **BACK-06**: Formatted backtest report (text) and optional equity curve chart (matplotlib PNG)
- [x] **BACK-07**: Backtest results persistence to backtest_results table with equity_curve and monthly_returns JSON
- [x] **BACK-08**: Alembic migration adding strategy_signals hypertable and backtest_results table

### Trading Strategies

- [x] **STRAT-01**: BaseStrategy abstract class with StrategyConfig (id, asset class, instruments, rebalance freq, leverage/position limits, stop/take-profit) and generate_signals(as_of_date) → list[StrategyPosition]
- [x] **STRAT-02**: RATES_BR_01 Carry & Roll-Down — capture carry-to-risk at optimal DI curve tenor, sized by carry/risk ratio vs threshold
- [x] **STRAT-03**: RATES_BR_02 Taylor Rule Misalignment — trade DI direction based on gap between current Selic and Taylor-implied fair rate
- [x] **STRAT-04**: RATES_BR_03 Curve Slope — flattener/steepener on DI 2Y-5Y spread based on monetary cycle position and inflation expectations
- [x] **STRAT-05**: RATES_BR_04 US Rates Spillover — fade DI-UST spread overshoot after large UST weekly moves (mean reversion)
- [x] **STRAT-06**: INF_BR_01 Breakeven Inflation — trade breakeven (DI_PRE minus NTN_B_REAL) when agent forecast diverges from market-implied inflation
- [x] **STRAT-07**: FX_BR_01 Carry & Fundamental — composite of FX carry-to-risk (40%), BEER misalignment (35%), flow score (25%) with regime adjustment
- [x] **STRAT-08**: CUPOM_01 CIP Basis Mean Reversion — fade extreme z-scores in cupom cambial minus SOFR basis
- [x] **STRAT-09**: SOV_BR_01 Fiscal Risk Premium — trade long-end DI and USDBRL based on fiscal dominance risk vs sovereign spread level

### Signal Aggregation & Portfolio

- [x] **PORT-01**: SignalAggregator combining agent signals into directional consensus per asset class with conflict detection
- [x] **PORT-02**: PortfolioConstructor converting strategy positions to net portfolio weights with risk-budget scaling and regime adjustment (RISK_OFF → -50%)
- [x] **PORT-03**: CapitalAllocator enforcing portfolio constraints (max leverage, max single position, max asset class concentration)
- [x] **PORT-04**: Rebalance threshold check (drift > 5% triggers rebalance) and trade computation

### Risk Management

- [x] **RISK-01**: VaR calculator with historical VaR (95% and 99%, 1-day horizon) from portfolio returns
- [x] **RISK-02**: Parametric VaR using Gaussian assumption with portfolio covariance
- [x] **RISK-03**: Expected Shortfall (CVaR) as conditional expectation beyond VaR threshold
- [x] **RISK-04**: Stress testing against 4+ historical scenarios (2013 Taper Tantrum, 2015 BR Crisis, 2020 COVID, 2022 Rate Shock)
- [x] **RISK-05**: Risk limits configuration (max VaR, max drawdown, max leverage, max position, max asset class concentration)
- [x] **RISK-06**: Pre-trade limit checking — verify proposed trades don't breach limits before execution
- [x] **RISK-07**: DrawdownManager with 3-level circuit breakers: L1 (-3%) reduce 25%, L2 (-5%) reduce 50%, L3 (-8%) close all
- [x] **RISK-08**: RiskMonitor generating aggregate risk report (portfolio VaR, stress tests, limit utilization, circuit breaker status)

### Daily Pipeline

- [ ] **PIPE-01**: Daily orchestration pipeline: ingest → quality → agents → aggregate → strategies → portfolio → risk → report
- [ ] **PIPE-02**: CLI interface (scripts/daily_run.py) with --date and --dry-run options
- [ ] **PIPE-03**: Formatted summary output with agent count, signal count, position count, regime, elapsed time

### LLM Narrative

- [ ] **LLM-01**: NarrativeGenerator using Claude API (Anthropic Python SDK) with structured prompt from agent signals and features
- [ ] **LLM-02**: Daily macro brief covering regime, inflation, monetary policy, fiscal, FX, portfolio positioning, key risks
- [ ] **LLM-03**: Fallback template-based narrative when Anthropic API key is unavailable
- [ ] **LLM-04**: ANTHROPIC_API_KEY added to .env.example and settings

### Dashboard

- [ ] **DASH-01**: Single-file HTML dashboard served by FastAPI at GET /dashboard using React + Tailwind + Recharts via CDN
- [ ] **DASH-02**: Macro Dashboard tab showing key indicators from /api/v1/macro/dashboard
- [ ] **DASH-03**: Agent Signals tab with 5 agent cards (direction, confidence, signals) and consensus view
- [ ] **DASH-04**: Portfolio tab with positions table, risk metrics (VaR, leverage, drawdown)
- [ ] **DASH-05**: Backtests tab with strategy results table and equity curve chart

### API Extensions

- [ ] **APIV2-01**: GET /api/v1/agents — list registered agents with last run and signal count
- [ ] **APIV2-02**: GET /api/v1/agents/{agent_id}/latest — latest AgentReport with signals and narrative
- [ ] **APIV2-03**: POST /api/v1/agents/{agent_id}/run — trigger agent execution for specific date
- [ ] **APIV2-04**: GET /api/v1/signals/latest — latest signals from all agents with consensus
- [ ] **APIV2-05**: GET /api/v1/strategies — list 8 strategies with metadata and status
- [ ] **APIV2-06**: GET /api/v1/strategies/{strategy_id}/backtest — backtest results with equity curve
- [ ] **APIV2-07**: GET /api/v1/portfolio/current — consolidated positions with contributing strategies
- [ ] **APIV2-08**: GET /api/v1/portfolio/risk — risk report (VaR, stress tests, limits, circuit breakers)
- [ ] **APIV2-09**: GET /api/v1/reports/daily-brief — daily macro brief (LLM or template)

### Testing

- [x] **TESTV2-01**: Unit tests for each agent's feature computation (expected keys, correct types)
- [x] **TESTV2-02**: Unit tests for quantitative models (Phillips Curve, Taylor Rule, BEER) with known-input/known-output verification
- [x] **TESTV2-03**: Unit tests for backtesting engine (portfolio mark-to-market, rebalance with costs, metrics computation)
- [x] **TESTV2-04**: Unit tests for risk management (VaR calculation, limit checking, circuit breakers)
- [ ] **TESTV2-05**: Integration test: full pipeline (agents → strategies → portfolio → risk) runs without error for a known date
- [ ] **TESTV2-06**: Integration test: all API endpoints return 200 OK via FastAPI TestClient
- [ ] **TESTV2-07**: Verification script updated for Phase 0 + Phase 1 coverage

## Out of Scope (v2.0)

| Feature | Reason |
|---------|--------|
| Live order execution | Research/backtesting focus first |
| Multi-user authentication | Solo user for now |
| Bloomberg/Refinitiv integration | Free data sources only |
| ETFs/mutual funds as instruments | Stocks only per constraints |
| Production deployment (Kubernetes) | Phase 2+ |
| Real-time streaming execution | Phase 2+ |
| NLP pipeline for central bank comms | Phase 2+ |
| Additional 17 strategies (total 25) | Phase 2+ |
| Dagster/Airflow orchestration | Phase 2+ |
| Full React frontend app | Single HTML sufficient for v2.0 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AGENT-01 | Phase 7 | Complete |
| AGENT-02 | Phase 7 | Complete |
| AGENT-03 | Phase 7 | Complete |
| AGENT-04 | Phase 7 | Complete |
| AGENT-05 | Phase 7 | Complete |
| AGENT-06 | Phase 7 | Complete |
| AGENT-07 | Phase 7 | Complete |
| INFL-01 | Phase 8 | Complete |
| INFL-02 | Phase 8 | Complete |
| INFL-03 | Phase 8 | Complete |
| INFL-04 | Phase 8 | Complete |
| INFL-05 | Phase 8 | Complete |
| INFL-06 | Phase 8 | Complete |
| INFL-07 | Phase 8 | Complete |
| MONP-01 | Phase 8 | Complete |
| MONP-02 | Phase 8 | Complete |
| MONP-03 | Phase 8 | Complete |
| MONP-04 | Phase 8 | Complete |
| MONP-05 | Phase 8 | Complete |
| MONP-06 | Phase 8 | Complete |
| FISC-01 | Phase 9 | Complete |
| FISC-02 | Phase 9 | Complete |
| FISC-03 | Phase 9 | Complete |
| FISC-04 | Phase 9 | Complete |
| FXEQ-01 | Phase 9 | Complete |
| FXEQ-02 | Phase 9 | Complete |
| FXEQ-03 | Phase 9 | Complete |
| FXEQ-04 | Phase 9 | Complete |
| FXEQ-05 | Phase 9 | Complete |
| CRSA-01 | Phase 10 | Complete |
| CRSA-02 | Phase 10 | Complete |
| CRSA-03 | Phase 10 | Complete |
| BACK-01 | Phase 10 | Complete |
| BACK-02 | Phase 10 | Complete |
| BACK-03 | Phase 10 | Complete |
| BACK-04 | Phase 10 | Complete |
| BACK-05 | Phase 10 | Complete |
| BACK-06 | Phase 10 | Complete |
| BACK-07 | Phase 10 | Complete |
| BACK-08 | Phase 10 | Complete |
| STRAT-01 | Phase 11 | Complete |
| STRAT-02 | Phase 11 | Complete |
| STRAT-03 | Phase 11 | Complete |
| STRAT-04 | Phase 11 | Complete |
| STRAT-05 | Phase 11 | Complete |
| STRAT-06 | Phase 11 | Complete |
| STRAT-07 | Phase 11 | Complete |
| STRAT-08 | Phase 11 | Complete |
| STRAT-09 | Phase 11 | Complete |
| PORT-01 | Phase 12 | Complete |
| PORT-02 | Phase 12 | Complete |
| PORT-03 | Phase 12 | Complete |
| PORT-04 | Phase 12 | Complete |
| RISK-01 | Phase 12 | Complete |
| RISK-02 | Phase 12 | Complete |
| RISK-03 | Phase 12 | Complete |
| RISK-04 | Phase 12 | Complete |
| RISK-05 | Phase 12 | Complete |
| RISK-06 | Phase 12 | Complete |
| RISK-07 | Phase 12 | Complete |
| RISK-08 | Phase 12 | Complete |
| PIPE-01 | Phase 13 | Pending |
| PIPE-02 | Phase 13 | Pending |
| PIPE-03 | Phase 13 | Pending |
| LLM-01 | Phase 13 | Pending |
| LLM-02 | Phase 13 | Pending |
| LLM-03 | Phase 13 | Pending |
| LLM-04 | Phase 13 | Pending |
| DASH-01 | Phase 13 | Pending |
| DASH-02 | Phase 13 | Pending |
| DASH-03 | Phase 13 | Pending |
| DASH-04 | Phase 13 | Pending |
| DASH-05 | Phase 13 | Pending |
| APIV2-01 | Phase 13 | Pending |
| APIV2-02 | Phase 13 | Pending |
| APIV2-03 | Phase 13 | Pending |
| APIV2-04 | Phase 13 | Pending |
| APIV2-05 | Phase 13 | Pending |
| APIV2-06 | Phase 13 | Pending |
| APIV2-07 | Phase 13 | Pending |
| APIV2-08 | Phase 13 | Pending |
| APIV2-09 | Phase 13 | Pending |
| TESTV2-01 | Phase 8-13 | Complete |
| TESTV2-02 | Phase 8-13 | Complete |
| TESTV2-03 | Phase 10 | Complete |
| TESTV2-04 | Phase 12 | Complete |
| TESTV2-05 | Phase 13 | Pending |
| TESTV2-06 | Phase 13 | Pending |
| TESTV2-07 | Phase 13 | Pending |

**Coverage:**
- v2 requirements: 88 total
- Mapped to phases: 88
- Unmapped: 0

---
*Requirements defined: 2026-02-20*
*Milestone: v2.0 Quantitative Models & Agents*
