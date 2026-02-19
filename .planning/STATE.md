# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system
**Current focus:** Phase 3: Extended Connectors

## Current Position

Phase: 3 of 6 (Extended Connectors)
Plan: 3 of 4 in current phase
Status: In Progress
Last activity: 2026-02-19 -- Completed 03-03 (B3/Tesouro Direto + US Treasury yield curve connectors)

Progress: [█████████░] 90%

## Performance Metrics

**Velocity:**
- Total plans completed: 9
- Average duration: 11 min
- Total execution time: 1.62 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 3 | 16 min | 5 min |
| 02-connectors | 3 | 34 min | 11 min |
| 03-extended-connectors | 3 | 38 min | 13 min |

**Recent Trend:**
- Last 5 plans: 02-03 (11 min), 03-01 (9 min), 03-02 (11 min), 03-03 (18 min)
- Trend: Curve connectors take longer (CSV/JSON parsing, breakeven computation, multiple data sources per connector)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 6 phases derived from 65 requirements following data flow (foundation -> connectors -> backfill -> transforms -> API)
- [Roadmap]: Core connectors (BCB SGS, FRED, Yahoo, PTAX) split from extended connectors to prove BaseConnector pattern first
- [Roadmap]: Seed/backfill as separate phase to ensure all connectors exist before historical population
- [Roadmap]: Compression policies configured in Phase 1 but backfill runs in Phase 4 before compression activates on old chunks
- [01-01]: Kafka behind Docker Compose 'full' profile to avoid premature complexity
- [01-01]: Pydantic-settings singleton with computed URL fields for all service connections
- [01-01]: str-Enum mixin pattern for all enumerations (DB + JSON serializable)
- [01-02]: Raw SQL via op.execute() for all TimescaleDB operations (no dialect dependency)
- [01-02]: Composite primary keys (id, time_col) on all 7 hypertable models per TimescaleDB requirement
- [01-02]: Manual migration to control TimescaleDB operation ordering (extension -> tables -> hypertables -> compression -> policies)
- [01-02]: Compression delays: market_data 30d, fiscal_data 180d, others 90d
- [01-03]: Redis ConnectionPool passed via connection_pool= param (not from_pool()) to avoid premature closure
- [01-03]: Sync engine pool_size=5 (smaller than async 20) since only used for Alembic/scripts
- [01-03]: Verification script uses WARN for missing hypertables in basic mode to tolerate parallel plan execution
- [02-01]: AsyncRetrying pattern (not decorator) for tenacity retry so MAX_RETRIES is instance-accessible
- [02-01]: Lazy singleton pattern for ANBIMA and NYSE calendars to avoid load-time overhead
- [02-01]: ON CONFLICT DO NOTHING via pg_insert for idempotent bulk inserts across all connectors
- [03-01]: BcbFxFlowConnector uses flat SERIES_REGISTRY + separate FLOW_TYPE_MAP for flow_type lookup
- [03-01]: StnFiscalConnector uses tuple-valued SERIES_REGISTRY dict[str, tuple[int, str, str]] for per-series fiscal_metric and unit
- [03-01]: Expanded STN Fiscal to 6 series (added BR_TOTAL_EXPENDITURE and BR_SOCIAL_SEC_DEFICIT for completeness)
- [03-01]: Tesouro Transparente API skipped per research -- BCB SGS is sole source for fiscal data
- [03-02]: IBGE SIDRA table 7060 with period-range fetching (YYYYMM format) and percentage weights from variable 2265
- [03-02]: BCB Focus OData pagination with $top=1000/$skip for large result sets, weekly Monday releases
- [03-03]: BCB SGS as primary DI curve source (series #7805-7816) rather than B3 direct feed -- free, reliable, covers 12 tenors
- [03-03]: Tesouro Direto JSON as best-effort NTN-B source with empty-list fallback on any error (403/404/timeout)
- [03-03]: Treasury CSV parsed via pd.read_csv in asyncio.to_thread to avoid blocking the event loop
- [03-03]: Unknown CSV columns (e.g., '1.5 Mo' added by Treasury in Feb 2025) silently skipped via TENOR_MAP lookup
- [03-03]: Breakeven as static method _compute_breakeven() for easy unit testing without HTTP mocking

### Pending Todos

None yet.

### Blockers/Concerns

- FRED API key required before backfill (free registration at fred.stlouisfed.org)
- Yahoo Finance (yfinance) is a scraper with known fragility -- fallback considered during Phase 2 implementation

## Session Continuity

Last session: 2026-02-19
Stopped at: Completed 03-03-PLAN.md (B3/Tesouro Direto + US Treasury yield curve connectors)
Resume file: .planning/phases/03-extended-connectors/ (Phase 3, Plan 4 next)
