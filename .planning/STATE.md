# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system
**Current focus:** Phase 14: Backtesting Engine v2 & Strategy Framework (v3.0)

## Current Position

Phase: 14 of 19 (Backtesting Engine v2 & Strategy Framework) -- COMPLETE
Plan: 3 of 3 in current phase (ALL COMPLETE)
Status: Phase 14 complete, ready for Phase 15
Last activity: 2026-02-22 — Completed 14-03-PLAN.md (Analytics & Tearsheet)

Progress: [######################........] 74% (14/19 phases complete)

## Performance Metrics

**Velocity (from v1.0 + v2.0):**
- Total plans completed: 22
- Average duration: 9.8 min
- Total execution time: 3.24 hours

**v3.0 Estimate (22 plans):**
- Estimated at ~9.8 min/plan: ~3.6 hours total

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 07-13 (v2.0) | 20 | 3.0 hrs | 9 min |
| 14-19 (v3.0) | 22 | TBD | TBD |

*Updated after each plan completion*
| Phase 14 P01 | 7min | 3 tasks | 11 files |
| Phase 14 P02 | 6min | 2 tasks | 4 files |
| Phase 14 P03 | 7min | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.0]: 8 strategies in flat files with ALL_STRATEGIES dict registry -- being replaced by StrategyRegistry
- [v2.0]: CDN-only dashboard (React 18 + Tailwind + Recharts + Babel) -- being enhanced to multi-page React app
- [v3.0]: Enhance not replace -- build on existing v2.0 code
- [v3.0]: Coexisting strategies -- new FX-02 etc. alongside existing FX_BR_01 etc.
- [v3.0]: Dagster over custom pipeline -- scheduling, retry, monitoring UI
- [14-01]: Auto-register existing 8 strategies in StrategyRegistry via __init__.py for backward compat
- [14-01]: Extract asset_class metadata from module-level StrategyConfig constants for registry filtering
- [14-01]: Add backtest_results v2 columns as nullable to preserve existing data
- [14-02]: Portfolio equity = weighted sum of individual strategy equity curves, aligned to common DatetimeIndex
- [14-02]: Walk-forward overfit ratio = mean OOS Sharpe / mean IS Sharpe, < 0.5 warns
- [14-02]: TransactionCostModel uses instance-level default_bps for customizable fallback cost
- [14-03]: deflated_sharpe uses Euler-Mascheroni approximation for expected max SR from i.i.d. trials
- [14-03]: generate_tearsheet uses 63-day rolling window for quarterly rolling Sharpe
- [14-03]: All analytics functions use ddof=0 for std to handle small samples gracefully

### Pending Todos

None yet.

### Blockers/Concerns

- Dagster requires dagster>=1.6 + dagster-webserver -- new dependency
- Grafana requires Docker container addition to docker-compose.yml
- React dashboard may need Node.js 18+ for build tooling (or continue CDN approach)
- Anthropic API key needed for LLM narrative generation (fallback templates available)

## Session Continuity

Last session: 2026-02-22
Stopped at: Completed 14-03-PLAN.md (Phase 14 COMPLETE)
Resume file: .planning/phases/
Resume action: Start Phase 15 planning/execution
