# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system
**Current focus:** Milestone v2.0: Quantitative Models & Agents

## Current Position

Phase: 8 — Inflation & Monetary Policy Agents (IN PROGRESS)
Plan: 1 of 3 complete
Status: Plan 08-01 complete — ready for Plan 08-02
Last activity: 2026-02-21 — Completed 08-01-PLAN.md (InflationFeatureEngine, PhillipsCurveModel, IpcaBottomUpModel)

Progress: [###       ] 15%  (3/20 plans complete)

## Performance Metrics

**Velocity (from v1.0 + v2.0):**
- Total plans completed: 13
- Average duration: 10.3 min
- Total execution time: 1.99 hours

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 07 | 01 | 7 min | 2 | 5 |
| 07 | 02 | 12 min | 2 | 11 |
| 08 | 01 | 11 min | 2 | 4 |

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

### Pending Todos

None yet.

### Blockers/Concerns

- FRED API key required for backfill (free registration at fred.stlouisfed.org)
- Yahoo Finance (yfinance) is a scraper with known fragility — fallback considered
- Anthropic API key needed for LLM narrative generation (can use fallback templates without it)
- statsmodels confirmed installed and working (Phillips Curve OLS, HP filter)

## Session Continuity

Last session: 2026-02-21
Stopped at: Completed 08-01-PLAN.md (InflationFeatureEngine, PhillipsCurveModel, IpcaBottomUpModel)
Resume action: Begin Plan 08-02 (orchestrate InflationAgent, add remaining sub-models)
