# Phase 27: Redis Cache, Dagster PMS, Go-Live & Verification - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Production hardening for the Portfolio Management System -- Redis caching for PMS query performance, Dagster integration for automated daily PMS pipeline (MTM, proposals, briefings, attribution), go-live checklist with disaster recovery, and comprehensive verification script validating all system components. This is the final phase of v4.0.

</domain>

<decisions>
## Implementation Decisions

### Redis Caching Strategy
- Cache all four major PMS endpoints: position book, morning pack briefing, risk monitor snapshot, and performance attribution
- Write-through + invalidate pattern: on each write operation (approve, close, MTM update), write to DB then immediately update cache with fresh data (not just delete)
- Cache invalidation is proactive, not lazy -- after writes the cache is immediately refreshed

### Dagster PMS Pipeline
- Two scheduled runs: EOD run (after market close) for MTM + attribution, pre-open run (06:00 BRT) for morning pack + proposals
- Each pipeline step writes results to Redis after DB persistence -- ensures cache is always warm after pipeline runs

### Claude's Discretion
- **Redis TTL strategy**: Claude picks appropriate TTLs per endpoint based on data volatility (e.g., tiered: shorter for volatile book/risk data, longer for generated briefings)
- **Redis infrastructure**: Claude decides whether to reuse existing Redis container with PMS key prefix or add dedicated instance, based on current docker-compose.yml setup
- **Dagster integration pattern**: Claude decides whether to extend existing Dagster Definitions graph or create separate PMS job, based on Phase 18 Dagster structure
- **Dagster error handling**: Claude picks per-step error policy based on criticality (e.g., retry for transient failures, alert on persistent ones)
- **Go-live deliverables**: Claude determines right mix of markdown docs and executable scripts (backup/restore, health checks, smoke tests)
- **Monitoring integration**: Claude decides whether to extend v3.0 Grafana dashboards + AlertManager or create dedicated PMS monitoring, based on existing Phase 18 setup
- **Backup scope**: Claude picks between full database dump/restore or PMS-tables-only based on operational needs
- **Operational doc structure**: Claude decides single runbook vs separate docs (daily ops, incident response, DR)
- **Verification check depth**: Claude picks appropriate depth per component -- imports for stable parts, smoke tests for critical paths
- **Verification output format**: Claude follows existing verify_phase2.py pattern for consistency, extending as needed
- **Verification organization**: Claude picks whether to organize by etapa (20 steps) or by component group

</decisions>

<specifics>
## Specific Ideas

- Verification script must validate the **full system (v1 through v4)**, not just PMS -- ensures nothing has regressed across all 27 phases
- Named `scripts/verify_phase3.py` per roadmap spec (covering v4.0 PMS milestone)
- All 20 etapas from the PMS guide (docs/GUIA_COMPLETO_CLAUDE_CODE_Fase3_PMS.md) must be verified
- Pipeline cache warming ensures the manager sees fresh data on first morning login without cold-cache latency

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 27-redis-cache-dagster-pms-go-live-verification*
*Context gathered: 2026-02-25*
