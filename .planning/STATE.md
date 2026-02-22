# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system
**Current focus:** Milestone v3.0: Strategy Engine, Risk & Portfolio Management

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-02-22 — Milestone v3.0 started

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
- [v2.0]: Template Method for agents — BaseAgent.run() orchestrates load->features->models->narrative
- [v2.0]: 8 strategies in flat files with ALL_STRATEGIES dict registry
- [v2.0]: Risk parity with SLSQP + Ledoit-Wolf covariance; fallback to equal weights
- [v2.0]: 3-level circuit breakers (L1 -3%, L2 -5%, L3 -8%)
- [v2.0]: CDN-only dashboard (React 18 + Tailwind + Recharts + Babel) — no build step
- [v2.0]: Claude claude-sonnet-4-5 for daily narrative generation
- [v2.0]: Response envelope {status, data, meta} for all v2 API endpoints
- [v3.0]: Enhance not replace — build on existing v2.0 code
- [v3.0]: Coexisting strategies — new FX-02 etc. alongside existing FX_BR_01 etc.

### Pending Todos

None yet.

### Blockers/Concerns

- FRED API key required for backfill (free registration at fred.stlouisfed.org)
- Yahoo Finance (yfinance) is a scraper with known fragility — fallback considered
- Anthropic API key needed for LLM narrative generation (can use fallback templates without it)
- Dagster requires dagster>=1.6 + dagster-webserver — new dependency
- Grafana requires Docker container addition to docker-compose.yml
- React dashboard may need Node.js 18+ for build tooling (or continue CDN approach)

## Session Continuity

Last session: 2026-02-22
Stopped at: Starting milestone v3.0 — defining requirements
Resume file: .planning/PROJECT.md
Resume action: Continue requirement definition for v3.0
