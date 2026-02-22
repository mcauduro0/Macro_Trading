# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system
**Current focus:** Milestone v2.0: Quantitative Models & Agents

## Current Position

Phase: 13 — Pipeline, LLM, Dashboard, API & Tests (COMPLETE)
Plan: 4 of 4 complete (13-01, 13-02, 13-03, 13-04 done)
Status: Phase 13 complete — all 4 plans executed
Last activity: 2026-02-22 — Completed 13-04-PLAN.md (9 API v2 endpoints, 27 tests, verification script)

Progress: [################] 100%  (20/20 plans complete)

## Performance Metrics

**Velocity (from v1.0 + v2.0):**
- Total plans completed: 22
- Average duration: 9.8 min
- Total execution time: 3.24 hours

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 07 | 01 | 7 min | 2 | 5 |
| 07 | 02 | 12 min | 2 | 11 |
| 08 | 01 | 11 min | 2 | 4 |
| 08 | 02 | 14 min | 2 | 2 |
| 08 | 03 | 13 min | 2 | 4 |
| 09 | 01 | 11 min | 2 | 4 |
| 09 | 02 | 12 min | 2 | 4 |
| 10 | 01 | 9 min | 2 | 4 |
| 10 | 02 | 5 min | 2 | 6 |
| 10 | 03 | 6 min | 2 | 6 |
| 11 | 01 | 10 min | 2 | 7 |
| 11 | 02 | 10 min | 2 | 7 |
| 11 | 03 | 10 min | 2 | 7 |
| 12 | 01 | 12 min | 2 | 8 |
| 12 | 02 | 7 min | 2 | 6 |
| 12 | 03 | 10 min | 2 | 7 |
| 13 | 02 | 5 min | 2 | 7 |
| 13 | 01 | 9 min | 2 | 7 |
| 13 | 03 | 6 min | 2 | 5 |
| 13 | 04 | 8 min | 2 | 12 |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v1.0]: TimescaleDB with hypertables and compression — proven stable for all 250+ series
- [v1.0]: BaseConnector ABC pattern — consistent interface for all 11 connectors
- [v1.0]: ON CONFLICT DO NOTHING everywhere — safe idempotent inserts
- [v1.0]: Point-in-time via release_time — critical for backtesting integrity
- [v1.0]: BCB swap series for DI curve — free, reliable, 12 tenors daily
- [v1.0]: Composite PKs on hypertables — TimescaleDB requirement
- [v1.0]: Raw SQL for migration ops — no dialect dependency
- [v1.0]: Lazy singleton for ANBIMA/NYSE calendars — avoid load-time overhead
- [v1.0]: Redis ConnectionPool via connection_pool= param — avoid premature closure
- [v2.0-07-01]: Sync sessions for data loader — agents are batch processes, not concurrent web requests
- [v2.0-07-01]: Async bridge in _persist_signals using ThreadPoolExecutor when event loop is running
- [v2.0-07-01]: COALESCE(release_time, observation_date) for flow_data PIT filtering on nullable release_time
- [v2.0-07-01]: Dedup macro_series by observation_date keeping highest revision_number for PIT correctness
- [v2.0-07-02]: AgentReportRecord ORM (not AgentReport) to avoid name collision with dataclass in base.py
- [v2.0-07-02]: agent_reports as regular table (not hypertable) — low volume audit trail
- [v2.0-07-02]: Agents not in EXECUTION_ORDER appended alphabetically — extensible for future agents
- [v2.0-07-02]: run_all catches per-agent exceptions and continues — one failure does not abort pipeline
- [v2.0-08-01]: Compounded YoY via prod(1+mom/100)-1 — matches IBGE methodology vs simple sum
- [v2.0-08-01]: Private _raw_ols_data and _raw_components keys in features dict — model classes receive pre-assembled data
- [v2.0-08-01]: IBC-Br uses 10Y lookback (3650 days) — HP filter and 120M OLS window both need full history
- [v2.0-08-01]: USDBRL/CRB via get_market_data(), not get_macro_series() — FX/commodities are intraday not macro releases
- [v2.0-08-01]: IpcaBottomUpModel renormalizes IBGE weights to available components — partial coverage produces valid signal
- [v2.0-08-03]: TaylorRuleModel GAP_FLOOR=1.0 (100bps locked per CONTEXT.md); MODERATE for [1.0,1.5), STRONG for >=1.5
- [v2.0-08-03]: SelicPathModel direction: market > model -> SHORT (fade hike pricing); market < model -> LONG (hike risk)
- [v2.0-08-03]: MONETARY_BR_COMPOSITE weights: Taylor 50%, SelicPath 30%, TermPremium 20%; US Fed excluded from BR composite
- [v2.0-08-03]: Conflict dampening 0.70 when any active BR sub-signal disagrees with plurality direction
- [v2.0-08-03]: KalmanFilterRStar MIN_OBS=24, DEFAULT_R_STAR=3.0 — graceful degradation for historical backtesting
- [v2.0-08-03]: features/__init__.py uses conditional import for InflationFeatureEngine for wave-1 independence
- [v2.0-08-02]: InflationSurpriseModel direction: upside surprise (z>0) = LONG (hawkish); downside = SHORT — per CONTEXT.md
- [v2.0-08-02]: InflationSurpriseModel fires only when |z| >= Z_FIRE=1.0; flat/constant data returns NO_SIGNAL via zero-std guard
- [v2.0-08-02]: InflationPersistenceModel expectations anchoring: max(0, 100 - |focus-3.0|*20) — inverted, closer to 3% = higher
- [v2.0-08-02]: INFLATION_BR_COMPOSITE dampening at >=2 disagreements (not >=1); US trend excluded from BR composite
- [v2.0-09-01]: FiscalDominanceRisk substitutes 50 (neutral) for NaN subscores — partial signal still valuable
- [v2.0-09-01]: DSA uses baseline-as-primary approach for direction; scenarios provide confidence calibration
- [v2.0-09-01]: DSA confidence from scenario consensus: 4/4 stabilizing→1.0, 3/4→0.70, 2/4→0.40, 1/4→0.20, 0/4→0.05
- [v2.0-09-01]: FiscalImpulseModel: positive z (pb improving) = SHORT (fiscal contraction = BRL positive)
- [v2.0-09-01]: FISCAL_BR_COMPOSITE: equal 1/3 weights, 0.70 conflict dampening when any active signal disagrees
- [v2.0-09-02]: BeerModel uses same sm.add_constant() for prediction as training (avoids shape mismatch from statsmodels constant-dropping behavior)
- [v2.0-09-02]: FX_BR_COMPOSITE: locked weights BEER 40% + Carry 30% + Flow 20% + CIP 10%; 0.70 dampening when any active signal disagrees
- [v2.0-09-02]: CipBasisModel direction locked: positive basis = LONG USDBRL (capital flow friction, BRL less attractive)
- [v2.0-09-02]: FlowModel: NaN for one flow component falls back to single-source composite (not NO_SIGNAL)
- [v2.0-09-02]: FxFeatureEngine._build_beer_ols_data filters to 2010-present; only drops rows where log_usdbrl is NaN (other predictors with NaN kept for per-predictor availability check)
- [v2.0-10-01]: RegimeDetectionModel: composite = nanmean of 6 direction-corrected z-scores / 2.0, clipped to [-1,+1]; SHORT > +0.2, LONG < -0.2
- [v2.0-10-01]: CorrelationAnalysis: always NEUTRAL direction (regime-neutral alert); strength from max |z| across 5 pairs
- [v2.0-10-01]: RiskSentimentIndex: 6-component weighted index renormalized over available (non-NaN) components; WEIGHTS sum to 1.0
- [v2.0-10-01]: DI_UST correlation pair uses IBOV as proxy for DI daily history when unavailable
- [v2.0-10-01]: br_fiscal regime component = hy_oas_zscore * 0.3 as placeholder fiscal dominance proxy
- [v2.0-10-02]: Notional-based positions (not shares) — simplifies rebalancing, no price lookup for position access
- [v2.0-10-02]: Cash-position transfer on rebalance — cash decreases by trade_notional + cost to preserve total_equity invariant
- [v2.0-10-02]: BacktestRawResult namedtuple as interim return type until Plan 10-03 adds full BacktestResult dataclass
- [v2.0-10-02]: BacktestResultRecord ORM (not BacktestResult) to avoid collision with dataclass in metrics module
- [v2.0-10-03]: Zero-vol positive returns produce capped Sharpe of 99.99 (not 0.0) — monotonically increasing equity must show positive Sharpe
- [v2.0-10-03]: matplotlib Agg backend called before pyplot import — ensures headless PNG generation in CI/server
- [v2.0-10-03]: BacktestEngine.run() returns BacktestResult (replaces BacktestRawResult namedtuple from 10-02)
- [v2.0-11-01]: STRENGTH_MAP locked: STRONG=1.0, MODERATE=0.6, WEAK=0.3, NO_SIGNAL=0.0
- [v2.0-11-01]: Weight formula: strength_base * confidence * max_position_size with leverage proportional scaling
- [v2.0-11-01]: NEUTRAL signals produce 50% scale-down of existing position weight
- [v2.0-11-01]: RATES_BR_01 carry_threshold=1.5 default; confidence scales linearly to 2x threshold
- [v2.0-11-01]: RATES_BR_02 gap_threshold=100bps; Taylor r_star=4.5%, alpha=1.5, beta=0.5; 1Y tenor 50-day tolerance
- [v2.0-11-02]: RATES_BR_03 slope z-score uses rolling 252-day window; flattener for z > threshold regardless of easing/tightening cycle
- [v2.0-11-02]: RATES_BR_04 outer join with ffill for DI-UST holiday alignment; weekly UST change = ust[-1] - ust[-5] (5 biz days)
- [v2.0-11-02]: INF_BR_01 focuses on 2Y tenor as primary breakeven signal; divergence_threshold_bps=50 default
- [v2.0-11-02]: Confidence formulas vary by strategy: slope /(threshold*2.5), spillover /(threshold*2), breakeven /(threshold*3)
- [v2.0-11-03]: FX_BR_01 carry-to-risk uses tanh(carry_to_risk/2) normalization; 21-day annualized realized vol from USDBRL close returns
- [v2.0-11-03]: FX_BR_01 BEER uses 252-day rolling mean as simplified fair value; full BEER from FxEquilibriumAgent in Phase 9
- [v2.0-11-03]: FX_BR_01 regime adjustment: optional regime_score param scales position by 0.50 when < -0.3 (risk-off)
- [v2.0-11-03]: CUPOM_01 inner join for DI-UST history alignment; basis z-threshold=2.0 default (conservative mean reversion)
- [v2.0-11-03]: SOV_BR_01 fiscal risk = linear 60-100% GDP debt mapping + primary balance (deficit +20x, surplus -10x)
- [v2.0-11-03]: SOV_BR_01 produces 2 correlated positions (DI + USDBRL) for fiscal dominance risk trade
- [v2.0-11-03]: ALL_STRATEGIES uses type[BaseStrategy] values (not instances) for lazy instantiation by caller
- [v2.0-12-01]: DEFAULT_AGENT_WEIGHTS: cross_asset_agent highest for EQUITY_INDEX (0.45) and COMMODITY (0.55), monetary_agent highest for FIXED_INCOME (0.35)
- [v2.0-12-01]: Bilateral veto at |regime_score| > 0.7 reduces net_score by 50% for both extreme risk-off and euphoria/risk-on
- [v2.0-12-01]: Risk parity uses SLSQP with ftol=1e-12, Ledoit-Wolf covariance; falls back to equal weights with < 60 obs
- [v2.0-12-01]: Regime thresholds: > 0.3 = RISK_OFF (0.4x), < -0.3 = RISK_ON (1.0x), else NEUTRAL (0.7x)
- [v2.0-12-01]: Gradual regime transition: linear ramp over 3 days from previous to target scale
- [v2.0-12-01]: Conflict dampening locked at 0.60 within [0.50, 0.70] range
- [v2.0-12-01]: Constraint pipeline order: single position (25%) -> asset class (50%) -> leverage (3x) -> drift (5%)
- [v2.0-12-02]: Eigenvalue floor at 1e-8 for near-singular covariance matrices during Cholesky decomposition
- [v2.0-12-02]: Student-t fit fallback to normal (df=1e6) when asset has < 30 observations for MC VaR
- [v2.0-12-02]: Uniform clipping to [1e-6, 1-1e-6] before ppf to avoid infinities in Monte Carlo draws
- [v2.0-12-02]: Stress scenario prefix matching: startswith() for DI_PRE instrument family (DI_PRE_365 -> DI_PRE)
- [v2.0-12-02]: Stress tests are advisory only — no position modifications (locked CONTEXT.md decision)
- [v2.0-12-03]: L3_TRIGGERED immediately chains to COOLDOWN within same update() call (transient state)
- [v2.0-12-03]: AlertDispatcher uses stdlib urllib.request (no new dep), catches URLError/HTTPError/OSError, never crashes
- [v2.0-12-03]: Recovery scale: recovery_day / recovery_days (0.33, 0.66, 1.0 for 3-day default)
- [v2.0-12-03]: L1 recovery requires drawdown < l1_threshold * 0.5 to prevent whipsaw at boundary
- [v2.0-12-03]: Risk level: CRITICAL (breach) > HIGH (>80% util or >2% dd) > MODERATE (>1% dd) > LOW
- [v2.0-12-03]: Strategy/AssetClass loss trackers fire independently from portfolio DrawdownManager
- [v2.0-13-02]: Template fallback uses pure ASCII tables with no prose -- fast and scannable per CONTEXT.md decision
- [v2.0-13-02]: Anthropic SDK imported conditionally (try/except ImportError) so system runs without it installed
- [v2.0-13-02]: claude-sonnet-4-5 model for daily generation (cost-effective, fast)
- [v2.0-13-02]: Graceful fallback on any API error with source="template_fallback" to distinguish from deliberate template use
- [v2.0-13-03]: CDN-only dashboard (React 18 + Tailwind + Recharts + Babel) — no build step required
- [v2.0-13-03]: FileResponse for static HTML serving — simple, no template engine needed
- [v2.0-13-01]: Pipeline uses sync execution (batch script, not async) with sync SQLAlchemy sessions for DB persistence
- [v2.0-13-01]: Agent/strategy/portfolio/risk steps use try/except for graceful degradation; pipeline abort only on unrecoverable errors
- [v2.0-13-01]: Placeholder steps for ingest/quality when Docker services unavailable
- [v2.0-13-03]: Isolated test app fixture bypasses DB lifespan for pure HTML endpoint tests
- [v2.0-13-04]: Static AGENT_DEFINITIONS list for API stability (agents always listed even if registry empty)
- [v2.0-13-04]: backtest_run() for GET endpoints (no DB writes), run() for POST (persists signals)
- [v2.0-13-04]: Response envelope: {status: ok, data: ..., meta: {timestamp: ...}} for all v2 endpoints
- [v2.0-13-04]: risk_api delegates to portfolio_api._build_risk_report to avoid code duplication

### Pending Todos

None yet.

### Blockers/Concerns

- FRED API key required for backfill (free registration at fred.stlouisfed.org)
- Yahoo Finance (yfinance) is a scraper with known fragility — fallback considered
- Anthropic API key needed for LLM narrative generation (can use fallback templates without it)
- statsmodels confirmed installed and working (Phillips Curve OLS, HP filter)

## Session Continuity

Last session: 2026-02-22
Stopped at: Completed 13-04-PLAN.md — Phase 13 fully complete
Resume file: .planning/phases/13-pipeline-llm-dashboard-api-tests/13-04-SUMMARY.md
Resume action: Phase 13 complete. All 20/20 plans done. Project v2.0 milestone complete.
