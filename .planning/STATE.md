# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system
**Current focus:** Milestone v2.0: Quantitative Models & Agents

## Current Position

Phase: 7 — Agent Framework & Data Loader
Plan: 2 of 2 (07-01 complete, 07-02 pending)
Status: Executing — plan 07-01 complete
Last activity: 2026-02-20 — Completed 07-01-PLAN.md (BaseAgent ABC, data loader, enums, deps)

Progress: [#         ] 5%  (1/20 plans complete)

## Performance Metrics

**Velocity (from v1.0 + v2.0):**
- Total plans completed: 11
- Average duration: 10.5 min
- Total execution time: 1.80 hours

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 07 | 01 | 7 min | 2 | 5 |

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

### Pending Todos

None yet.

### Blockers/Concerns

- FRED API key required for backfill (free registration at fred.stlouisfed.org)
- Yahoo Finance (yfinance) is a scraper with known fragility — fallback considered
- Anthropic API key needed for LLM narrative generation (can use fallback templates without it)
- statsmodels / sklearn needed for quantitative models (Phillips Curve OLS, Kalman Filter)

## Session Continuity

Last session: 2026-02-20
Stopped at: Completed 07-01-PLAN.md
Resume action: Continue executing phase 7 (07-02 pending)
