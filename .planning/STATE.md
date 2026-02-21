# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system
**Current focus:** Milestone v2.0: Quantitative Models & Agents

## Current Position

Phase: 11 — Trading Strategies
Plan: 2 of 3 complete (11-01, 11-02 done)
Status: Executing Phase 11 — 5 strategies delivered (BR01-BR04 rates + INF01 breakeven)
Last activity: 2026-02-21 — Completed 11-02-PLAN.md (RATES_BR_03, RATES_BR_04, INF_BR_01, 85 tests total)

Progress: [#########-] 55%  (11/20 plans complete)

## Performance Metrics

**Velocity (from v1.0 + v2.0):**
- Total plans completed: 18
- Average duration: 10.0 min
- Total execution time: 2.78 hours

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

### Pending Todos

None yet.

### Blockers/Concerns

- FRED API key required for backfill (free registration at fred.stlouisfed.org)
- Yahoo Finance (yfinance) is a scraper with known fragility — fallback considered
- Anthropic API key needed for LLM narrative generation (can use fallback templates without it)
- statsmodels confirmed installed and working (Phillips Curve OLS, HP filter)

## Session Continuity

Last session: 2026-02-21
Stopped at: Completed 11-02-PLAN.md (RATES_BR_03 Slope, RATES_BR_04 Spillover, INF_BR_01 Breakeven, 85 total tests)
Resume action: Continue Phase 11 with 11-03-PLAN.md (final wave of strategies).
