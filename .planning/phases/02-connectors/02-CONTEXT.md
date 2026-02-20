# Phase 2: Core Connectors - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a proven ingestion pattern with a BaseConnector abstract class, 4 working connectors (BCB SGS, FRED, Yahoo Finance, BCB PTAX), data integrity utilities (business day calendars, tenor conversions), and test infrastructure (pytest fixtures, respx HTTP mocking). Must validate Brazilian format handling, point-in-time tracking, revision storage, and idempotent writes.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All implementation decisions for Phase 2 are at Claude's discretion. The user trusts the builder's technical judgment for this connector phase. Key areas where Claude will decide:

**BaseConnector Pattern:**
- Abstract class design (methods, properties, lifecycle hooks)
- HTTP client management (httpx async, connection pooling)
- Retry and backoff strategy (tenacity vs custom)
- Rate limiting approach
- Structured logging integration (structlog)
- Error handling and exception hierarchy

**Connector Implementation:**
- Method signatures and return types for each connector
- API response parsing strategy per source
- Brazilian number format handling (1.234,56 -> 1234.56)
- Date format handling per API (YYYY-MM-DD, DD/MM/YYYY, MM-DD-YYYY)
- How connectors map API responses to ORM model instances
- Batch vs single-record insert strategy

**Data Integrity Utilities:**
- Business day calendar implementation (ANBIMA BR + NYSE US)
- Holiday data storage approach (hardcoded, file-based, or package)
- Tenor-to-days and tenor-to-date conversion logic

**Test Infrastructure:**
- pytest conftest structure and fixture design
- respx mock patterns for each API
- Sample data fixtures and test data strategy
- Integration vs unit test boundaries

</decisions>

<specifics>
## Specific Ideas

No specific requirements beyond the roadmap and requirements. Follow the Phase 1 patterns:

- Use the existing ORM models from Phase 1 (macro_series, market_data tables)
- Use the async database engine from Phase 1 for writes
- Use pydantic-settings config for API keys (FRED_API_KEY already in .env.example)
- Follow structlog patterns established in Phase 1
- ON CONFLICT DO NOTHING via SQLAlchemy's `insert().on_conflict_do_nothing()`

</specifics>

<deferred>
## Deferred Ideas

None — all connector-related work stays within phase scope

</deferred>

---

*Phase: 02-connectors*
*Context gathered: 2026-02-19*
