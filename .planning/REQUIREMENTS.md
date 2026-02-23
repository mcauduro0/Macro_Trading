# Requirements: Macro Fund System

**Defined:** 2026-02-19 (v1) | 2026-02-20 (v2) | 2026-02-22 (v3)
**Core Value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system — the foundation for analytical agents, quantitative strategies, and risk management

## v1 Requirements (Complete)

All 65 v1 requirements delivered in milestone v1.0 Data Infrastructure. See `.planning/MILESTONES.md` for archive.

Summary: INFRA (7/7), CONN (12/12), DATA (5/5), SEED (5/5), XFORM (14/14), API (12/12), QUAL (6/6), TEST (4/4)

## v2 Requirements (Complete)

All 88 v2 requirements delivered in milestone v2.0 Quantitative Models & Agents.

Summary: AGENT (7/7), INFL (7/7), MONP (6/6), FISC (4/4), FXEQ (5/5), CRSA (3/3), BACK (8/8), STRAT (9/9), PORT (4/4), RISK (8/8), PIPE (3/3), LLM (4/4), DASH (5/5), APIV2 (9/9), TESTV2 (7/7)

## v3 Requirements

Requirements for milestone v3.0 Strategy Engine, Risk & Portfolio Management. Each maps to roadmap phases.

### Strategy Framework Enhancement

- [x] **SFWK-01**: Enhanced StrategySignal dataclass with z_score, raw_value, suggested_size, entry_level, stop_loss, take_profit, holding_period_days, metadata dict
- [x] **SFWK-02**: StrategyRegistry class with register decorator, get, list_all, list_by_asset_class, instantiate, instantiate_all methods
- [x] **SFWK-03**: strategy_state table (strategy_id, timestamp, direction, strength, confidence, z_score, instruments JSON) with Alembic migration
- [x] **SFWK-04**: backtest_results v2 table with params_json, daily_returns_json, monthly_returns expanded fields

### Backtesting Engine v2

- [x] **BTST-01**: BacktestEngine v2 with portfolio-level backtesting — run_portfolio(strategies, weights) aggregating multiple strategies with risk allocation
- [x] **BTST-02**: Walk-forward validation — split period into train/test windows, optimize params in-sample, evaluate out-of-sample
- [x] **BTST-03**: Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014) adjusting for multiple testing
- [x] **BTST-04**: TransactionCostModel with per-instrument cost table (12 instruments: DI1, DDI, DOL, NDF, NTN-B, LTN, UST, ZN, ZF, ES, CDS_BR, IBOV_FUT)
- [x] **BTST-05**: Analytics functions: compute_sortino, compute_information_ratio, compute_tail_ratio, compute_turnover, compute_rolling_sharpe
- [x] **BTST-06**: generate_tearsheet producing complete dict for dashboard rendering (equity curve, drawdown chart, monthly heatmap, rolling sharpe, trade analysis)

### FX Strategies

- [x] **FXST-01**: FX-02 Carry-Adjusted Momentum — combine Selic-FFR carry z-score with 3M USDBRL momentum z-score, vol-adjusted sizing
- [x] **FXST-02**: FX-03 Flow-Based Tactical FX — operate USDBRL from BCB FX flow (40%), CFTC positioning (35%), B3 foreign flow (25%) with contrarian logic at |z|>2
- [x] **FXST-03**: FX-04 FX Vol Surface Relative Value — trade distortions in USDBRL vol surface (risk reversal, butterfly, term structure, implied-realized premium)
- [x] **FXST-04**: FX-05 Terms of Trade FX — commodity-weighted terms of trade index vs USDBRL for misalignment detection (soybean, iron ore, oil, sugar, coffee)

### Rates Strategies

- [x] **RTST-01**: RATES-03 BR-US Rate Spread — trade DI-UST spread adjusted for CDS, inflation differential, with z-score mean reversion at 2Y and 5Y tenors
- [x] **RTST-02**: RATES-04 Term Premium Extraction — estimate term premium as DI(n) minus Focus-implied expected short rate, trade when TP z-score extreme
- [x] **RTST-03**: RATES-05 FOMC Event Strategy — position around FOMC [-5,+2] days based on FFR implied vs Taylor Rule divergence
- [x] **RTST-04**: RATES-06 COPOM Event Strategy — position around COPOM [-5,+2] days based on DI-implied Selic vs Focus median divergence

### Inflation Strategies

- [x] **INST-01**: INF-02 IPCA Surprise Trade — trade NTN-Bs and breakevens around IPCA/IPCA-15 releases when model forecast diverges from Focus
- [x] **INST-02**: INF-03 Inflation Carry — long/short breakeven (DI_PRE minus NTN_B_REAL) based on comparison with target, current IPCA, and Focus expectations

### Cupom Cambial Strategies

- [x] **CPST-01**: CUPOM-02 Onshore-Offshore Spread — trade spread between DDI futuro (onshore) and NDF-implied rate (offshore) on z-score mean reversion

### Sovereign Credit Strategies

- [x] **SVST-01**: SOV-01 CDS Curve Trading — trade Brazil CDS 1Y/5Y/10Y slope and level based on fiscal agent output and z-scores
- [x] **SVST-02**: SOV-02 EM Sovereign Relative Value — cross-section regression of CDS vs fundamentals for 10 EM peers, trade Brazil residual
- [x] **SVST-03**: SOV-03 Rating Migration Anticipation — logistic model for upgrade/downgrade probability from fiscal, growth, external, political factors

### Cross-Asset Strategies

- [x] **CAST-01**: CROSS-01 Macro Regime Allocation — HMM-based regime classification (Goldilocks, Reflation, Stagflation, Deflation) with regime-dependent allocation map
- [x] **CAST-02**: CROSS-02 Global Risk Appetite — proprietary composite index from VIX, HY OAS, DXY, EM FX carry, CFTC S&P, IG-HY spread, S&P momentum, Gold

### Cross-Asset Agent v2

- [x] **CRSV-01**: CrossAssetView dataclass with regime, regime_probabilities, per-asset-class views, risk_appetite, tail_risk, narrative, key_trades, risk_warnings
- [x] **CRSV-02**: Enhanced regime classification with HMM fallback to rule-based, 4 regimes with probability output
- [x] **CRSV-03**: Cross-asset consistency checking (e.g., FX bull + rates higher = inconsistent)
- [x] **CRSV-04**: LLM-powered narrative generation for CrossAssetView with structured prompt and JSON output

### NLP Pipeline

- [x] **NLP-01**: COPOMScraper — scrape COPOM atas and comunicados from bcb.gov.br (2010-present)
- [x] **NLP-02**: FOMCScraper — scrape FOMC statements and minutes from federalreserve.gov (2010-present)
- [x] **NLP-03**: CentralBankSentimentAnalyzer — hawk/dove scoring [-1,+1] via term dictionary (PT+EN), optional LLM scoring, change_score vs previous document
- [x] **NLP-04**: NLPProcessor pipeline: clean → score → extract key phrases → compare vs previous → persist
- [x] **NLP-05**: nlp_documents table (document_type, institution, date, hawk_dove_score, change_score, key_phrases JSON) with Alembic migration

### Signal Aggregation v2

- [x] **SAGG-01**: Enhanced SignalAggregator with 3 methods: confidence-weighted average, rank-based (robust to outliers), Bayesian (regime prior + likelihood)
- [x] **SAGG-02**: Crowding penalty — reduce signal when >80% of strategies agree (contrarian discount)
- [x] **SAGG-03**: Staleness discount — reduce weight for signals based on stale data (>N business days old)
- [x] **SAGG-04**: SignalMonitor with check_signal_flips, check_conviction_surge, check_strategy_divergence, generate_daily_summary

### Risk Engine v2

- [x] **RSKV-01**: Monte Carlo VaR with t-Student marginals, Gaussian copula, Cholesky decomposition (10,000 simulations)
- [x] **RSKV-02**: Parametric VaR with Ledoit-Wolf shrinkage covariance estimation
- [x] **RSKV-03**: Marginal VaR and Component VaR decomposition by position
- [x] **RSKV-04**: Expanded stress scenarios: add BR Fiscal Crisis (teto de gastos) and Global Risk-Off (geopolitical) to existing 4 scenarios
- [x] **RSKV-05**: Reverse stress testing — find scenarios that produce a given max loss
- [x] **RSKV-06**: Historical replay stress test — replay actual returns from a crisis period
- [x] **RSKV-07**: RiskLimitsManager v2 with daily/weekly loss limits, risk budget tracking, available_risk_budget reporting
- [x] **RSKV-08**: API routes: GET /api/v1/risk/var, /risk/stress, /risk/limits, /risk/dashboard

### Portfolio Optimization

- [ ] **POPT-01**: Black-Litterman model — combine market equilibrium with agent views using confidence-weighted P/Q matrices
- [ ] **POPT-02**: Mean-variance optimization with configurable constraints via scipy.minimize
- [ ] **POPT-03**: PositionSizer with vol_target (target_vol/instrument_vol), fractional_kelly (f*=0.25), risk_budget_size methods
- [ ] **POPT-04**: portfolio_state table (timestamp, instrument, direction, notional, weight, entry_price, unrealized_pnl, strategy_attribution JSON) with Alembic migration
- [ ] **POPT-05**: Portfolio API: GET /api/v1/portfolio/current, /portfolio/target, /portfolio/rebalance-trades, /portfolio/attribution

### Production Orchestration (Dagster)

- [ ] **ORCH-01**: Dagster asset definitions for Bronze layer (6 connectors with cron schedules), Silver transforms, Agents (5 with dependency chain)
- [ ] **ORCH-02**: Dagster assets for Signals, Aggregated Signals, Portfolio Targets, Risk Metrics, Daily Report with full dependency graph
- [ ] **ORCH-03**: Dagster definitions module with all assets registered and dagster-webserver Docker Compose service (port 3001)
- [ ] **ORCH-04**: Makefile targets: make dagster, make dagster-run-all

### Monitoring & Alerting

- [ ] **MNTR-01**: Grafana Docker Compose service (port 3002) with TimescaleDB datasource provisioning
- [ ] **MNTR-02**: 4 provisioned Grafana dashboards JSON: pipeline_health, signal_overview, risk_dashboard, portfolio_performance
- [ ] **MNTR-03**: AlertManager with 10 rules (stale data, VaR breach/critical, drawdown warning/critical, limit breach, signal flip, conviction surge, pipeline failure, agent stale)
- [ ] **MNTR-04**: Monitoring API: GET /api/v1/monitoring/alerts, /pipeline-status, /system-health, POST /test-alert

### Dashboard v2 (React)

- [ ] **DSHV-01**: StrategiesPage — table of all strategies (ID, class, direction, confidence, z-score), expandable backtest metrics and equity curve
- [ ] **DSHV-02**: SignalsPage — aggregated signals by instrument (color-coded), heatmap strategies x classes, 30-day flip timeline
- [ ] **DSHV-03**: RiskPage — gauge meters (VaR 95/99, drawdown, leverage), stress test bar chart, limits table, concentration pie
- [ ] **DSHV-04**: PortfolioPage — positions with PnL/risk contribution, equity curve, monthly heatmap, attribution by strategy, suggested trades
- [ ] **DSHV-05**: AgentsPage — agent cards (signal, confidence, drivers, risks), Cross-Asset narrative display
- [ ] **DSHV-06**: App.tsx with React Router sidebar navigation, recharts + Tailwind CSS, API data fetching

### Daily Reporting

- [ ] **REPT-01**: DailyReportGenerator with sections: Market Snapshot, Regime Assessment, Agent Views, Signal Summary, Portfolio Status, Risk Metrics, Action Items
- [ ] **REPT-02**: Output formats: to_markdown, to_html, send_email, send_slack
- [ ] **REPT-03**: Report API: GET /api/v1/reports/daily, /reports/daily/latest, POST /reports/daily/send

### API Expansion & WebSocket

- [ ] **APIV-01**: Backtest API: POST /api/v1/backtest/run, GET /backtest/results, POST /backtest/portfolio, GET /backtest/comparison
- [ ] **APIV-02**: Strategy detail API: GET /api/v1/strategies/{id}, GET /strategies/{id}/signal/latest, GET /strategies/{id}/signal/history, PUT /strategies/{id}/params
- [ ] **APIV-03**: WebSocket ConnectionManager with 3 channels: ws://signals, ws://portfolio, ws://alerts
- [ ] **APIV-04**: Updated main.py with all routers and Swagger tags (Health, Macro, Curves, Market Data, Flows, Agents, Signals, Risk, Portfolio, Backtest, Strategies, Reports, Monitoring)

### Testing & Verification

- [ ] **TSTV-01**: Integration test: full pipeline E2E (DB → transforms → agents → strategies → signals → portfolio → risk → report)
- [ ] **TSTV-02**: Integration test: all API endpoints (v1 + v2 + v3) return 200 OK
- [ ] **TSTV-03**: CI/CD: updated .github/workflows/ci.yml with lint, unit tests, integration tests (with service containers)
- [ ] **TSTV-04**: Verification script (scripts/verify_phase2.py) validating all v3.0 components end-to-end with formatted report

## Out of Scope (v3.0)

| Feature | Reason |
|---------|--------|
| Live order execution / FIX protocol | Phase 3 — production deployment |
| Multi-user authentication | Solo user for now |
| Bloomberg/Refinitiv integration | Free data sources only |
| Kubernetes / Helm deployment | Phase 3 — production infrastructure |
| Real-time streaming execution | Phase 3 — live trading |
| Paper trading simulation | Phase 3 — requires execution engine |
| Mobile app / PWA | Web-first, desktop only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SFWK-01 | Phase 14 | Complete |
| SFWK-02 | Phase 14 | Complete |
| SFWK-03 | Phase 14 | Complete |
| SFWK-04 | Phase 14 | Complete |
| BTST-01 | Phase 14 | Complete |
| BTST-02 | Phase 14 | Complete |
| BTST-03 | Phase 14 | Complete |
| BTST-04 | Phase 14 | Complete |
| BTST-05 | Phase 14 | Complete |
| BTST-06 | Phase 14 | Complete |
| FXST-01 | Phase 15 | Complete |
| FXST-02 | Phase 15 | Complete |
| FXST-03 | Phase 15 | Complete |
| FXST-04 | Phase 15 | Complete |
| RTST-01 | Phase 15 | Complete |
| RTST-02 | Phase 15 | Complete |
| RTST-03 | Phase 15 | Complete |
| RTST-04 | Phase 15 | Complete |
| INST-01 | Phase 15 | Complete |
| INST-02 | Phase 15 | Complete |
| CPST-01 | Phase 15 | Complete |
| SVST-01 | Phase 15 | Complete |
| SVST-02 | Phase 15 | Complete |
| SVST-03 | Phase 15 | Complete |
| CAST-01 | Phase 15 | Complete |
| CAST-02 | Phase 15 | Complete |
| CRSV-01 | Phase 16 | Complete |
| CRSV-02 | Phase 16 | Complete |
| CRSV-03 | Phase 16 | Complete |
| CRSV-04 | Phase 16 | Complete |
| NLP-01 | Phase 16 | Complete |
| NLP-02 | Phase 16 | Complete |
| NLP-03 | Phase 16 | Complete |
| NLP-04 | Phase 16 | Complete |
| NLP-05 | Phase 16 | Complete |
| SAGG-01 | Phase 17 | Complete |
| SAGG-02 | Phase 17 | Complete |
| SAGG-03 | Phase 17 | Complete |
| SAGG-04 | Phase 17 | Complete |
| RSKV-01 | Phase 17 | Complete |
| RSKV-02 | Phase 17 | Complete |
| RSKV-03 | Phase 17 | Complete |
| RSKV-04 | Phase 17 | Complete |
| RSKV-05 | Phase 17 | Complete |
| RSKV-06 | Phase 17 | Complete |
| RSKV-07 | Phase 17 | Complete |
| RSKV-08 | Phase 17 | Complete |
| POPT-01 | Phase 17 | Pending |
| POPT-02 | Phase 17 | Pending |
| POPT-03 | Phase 17 | Pending |
| POPT-04 | Phase 17 | Pending |
| POPT-05 | Phase 17 | Pending |
| ORCH-01 | Phase 18 | Pending |
| ORCH-02 | Phase 18 | Pending |
| ORCH-03 | Phase 18 | Pending |
| ORCH-04 | Phase 18 | Pending |
| MNTR-01 | Phase 18 | Pending |
| MNTR-02 | Phase 18 | Pending |
| MNTR-03 | Phase 18 | Pending |
| MNTR-04 | Phase 18 | Pending |
| REPT-01 | Phase 18 | Pending |
| REPT-02 | Phase 18 | Pending |
| REPT-03 | Phase 18 | Pending |
| DSHV-01 | Phase 19 | Pending |
| DSHV-02 | Phase 19 | Pending |
| DSHV-03 | Phase 19 | Pending |
| DSHV-04 | Phase 19 | Pending |
| DSHV-05 | Phase 19 | Pending |
| DSHV-06 | Phase 19 | Pending |
| APIV-01 | Phase 19 | Pending |
| APIV-02 | Phase 19 | Pending |
| APIV-03 | Phase 19 | Pending |
| APIV-04 | Phase 19 | Pending |
| TSTV-01 | Phase 19 | Pending |
| TSTV-02 | Phase 19 | Pending |
| TSTV-03 | Phase 19 | Pending |
| TSTV-04 | Phase 19 | Pending |

**Coverage:**
- v3 requirements: 77 total (SFWK:4, BTST:6, FXST:4, RTST:4, INST:2, CPST:1, SVST:3, CAST:2, CRSV:4, NLP:5, SAGG:4, RSKV:8, POPT:5, ORCH:4, MNTR:4, DSHV:6, REPT:3, APIV:4, TSTV:4)
- Mapped to phases: 77
- Unmapped: 0

---
*Requirements defined: 2026-02-22*
*Traceability updated: 2026-02-22 after roadmap creation*
*Milestone: v3.0 Strategy Engine, Risk & Portfolio Management*
