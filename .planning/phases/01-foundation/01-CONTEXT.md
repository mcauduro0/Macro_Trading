# Phase 1: Foundation - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a running infrastructure stack (Docker Compose with TimescaleDB, Redis, MongoDB, Kafka, MinIO), a complete point-in-time-correct database schema (10 tables: 7 hypertables + 3 metadata), Alembic migrations, async/sync database engines, Redis client, and pydantic-settings configuration. This foundation must support all downstream connectors and transforms writing into it.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All implementation decisions for Phase 1 are at Claude's discretion. The user trusts the builder's technical judgment for this infrastructure phase. Key areas where Claude will decide:

**Project Structure:**
- Package naming and directory layout
- Where models, config, connectors, and other modules live
- Import path conventions

**Schema Conventions:**
- Table and column naming style (snake_case expected for PostgreSQL)
- Metadata table design (instruments, series_metadata, + 1 more)
- Enum definitions (AssetClass, Frequency, Country, etc.)
- Column types, nullable/non-nullable choices

**Docker Stack Profiles:**
- Whether to use dev/prod profiles or run all services always
- Kafka inclusion strategy (the research flags premature Kafka as an anti-pattern — Claude should consider including it as a disabled/optional service per INFRA-01 requirement)
- Resource limits and volume persistence configuration

**Development Workflow:**
- Makefile or script-based workflow
- First-time bootstrap process
- Migration workflow conventions
- .env template structure

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The research documents (ARCHITECTURE.md, PITFALLS.md) provide detailed guidance that should be followed:

- Use `TIMESTAMPTZ` exclusively (never naive TIMESTAMP) per Pitfall 6
- Set `segmentby='series_id'` and generous `compress_after` per Pitfall 4
- Use 1-year chunk intervals for daily macro data per Performance Traps research
- Follow the recommended `src/` project structure from ARCHITECTURE.md
- Configure compression policies in Phase 1 but actual compression activates after backfill in Phase 4

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-02-19*
