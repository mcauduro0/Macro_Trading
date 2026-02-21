# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system
**Current focus:** Milestone v2.0: Quantitative Models & Agents

## Current Position

Phase: 9 — Fiscal & FX Equilibrium Agents (COMPLETE)
Plan: 2 of 2 complete (09-01 done, 09-02 done)
Status: Phase 9 complete — FiscalAgent and FxEquilibriumAgent both built and tested
Last activity: 2026-02-21 — Completed 09-02-PLAN.md (FxEquilibriumAgent, FxFeatureEngine, 4 FX models, 20 unit tests)

Progress: [#######   ] 35%  (7/20 plans complete)

## Performance Metrics

**Velocity (from v1.0 + v2.0):**
- Total plans completed: 14
- Average duration: 10.5 min
- Total execution time: 2.21 hours

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 07 | 01 | 7 min | 2 | 5 |
| 07 | 02 | 12 min | 2 | 11 |
| 08 | 01 | 11 min | 2 | 4 |
| 08 | 02 | 14 min | 2 | 2 |
| 08 | 03 | 13 min | 2 | 4 |
| 09 | 01 | 11 min | 2 | 4 |
| 09 | 02 | 12 min | 2 | 4 |

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

### Pending Todos

None yet.

### Blockers/Concerns

- FRED API key required for backfill (free registration at fred.stlouisfed.org)
- Yahoo Finance (yfinance) is a scraper with known fragility — fallback considered
- Anthropic API key needed for LLM narrative generation (can use fallback templates without it)
- statsmodels confirmed installed and working (Phillips Curve OLS, HP filter)

## Session Continuity

Last session: 2026-02-21
Stopped at: Completed 09-02-PLAN.md (FxEquilibriumAgent, FxFeatureEngine, 4 FX models, 20 unit tests)
Resume action: Continue to Phase 10 — cross-asset agent
