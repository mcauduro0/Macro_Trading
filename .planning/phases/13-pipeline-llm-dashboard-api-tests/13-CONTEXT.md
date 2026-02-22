# Phase 13: Pipeline, LLM, Dashboard, API & Tests - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

A complete daily orchestration pipeline from data ingestion to risk report, LLM-powered narrative generation via Claude API, a self-contained HTML dashboard with 4 tabs, 9 new API endpoints extending the existing FastAPI layer, and integration tests validating the full v2.0 system end-to-end. This is the capstone phase — no new models, agents, or strategies.

</domain>

<decisions>
## Implementation Decisions

### Daily Pipeline Behavior
- Step-by-step summary output: print each step name + duration + status (e.g., "✓ agents: 12.3s, 5 signals"). Clean and scannable
- Abort immediately on failure — later steps depend on earlier ones, no partial execution
- No external notifications — terminal output is sufficient
- `--dry-run` runs full computation (agents, strategies, risk) but skips all DB persistence. Validates logic end-to-end
- Full 8-step sequence only — no individual step isolation. Always run ingest → quality → agents → aggregate → strategies → portfolio → risk → report
- Persist run history to DB: new `pipeline_runs` table with run_id, date, status, duration, step timings. Track reliability over time
- Default `--date` is today (calendar date) — user is responsible for running on business days
- End-of-run summary includes key metrics: signal count, top positions, portfolio leverage, VaR, and any active risk alerts

### LLM Narrative Style
- Audience: layered — executive summary at top for portfolio managers, detailed signal breakdown below for quants/researchers
- Tone: internal trading desk — direct, first-person plural. "We're seeing hawkish signals." "Our regime model flipped to risk-off."
- Length: medium (800-1500 words). Summary + per-agent sections + portfolio implications + risk
- Template fallback (no API key): structured data dump — tables of signals, directions, confidences. No prose. Fast and scannable
- API keys stored via environment variables (`ANTHROPIC_API_KEY`, `FRED_API_KEY`) — never committed to code

### Dashboard Layout & UX
- Visual style: Bloomberg-inspired — dark background, dense data, green/red accents, monospace numbers. Professional terminal feel
- Tab organization: horizontal top tabs, all 4 tabs (Macro Dashboard, Agent Signals, Portfolio, Backtests) get equal prominence
- Signal visualization: color-coded arrows — green up-arrow (LONG), red down-arrow (SHORT), gray dash (NEUTRAL), with confidence bar underneath
- No auto-refresh — manual refresh only. Data changes once daily after pipeline runs

### API Response Design
- Consistent response envelope on all endpoints: `{"status": "ok", "data": {...}, "meta": {"timestamp": ...}}`
- Date parameter optional, defaults to latest: `?date=YYYY-MM-DD` for historical, omit for most recent pipeline run
- All new endpoints under existing `/api/v1/` namespace — no version split, one unified system

### Claude's Discretion
- Pagination strategy for list endpoints (signals, strategies, positions) — Claude picks based on expected data volumes
- Exact chart types for Macro Dashboard and Backtests tabs
- Dashboard responsive behavior and tab content density
- Error response format details (consistent with envelope pattern)
- Exact Makefile target names and help text

</decisions>

<specifics>
## Specific Ideas

- Pipeline output should feel like a CI build log — step-by-step with timing, clear pass/fail, summary at end
- Dashboard should feel like a Bloomberg terminal — information density over whitespace, monospace numbers, dark theme
- Narrative should read like an internal morning call note — "Here's what changed overnight, here's what we're watching"
- Template fallback should be immediately useful without LLM — no degraded prose, just clean signal tables

</specifics>

<deferred>
## Deferred Ideas

- API key values were shared during discussion — these must be stored as environment variables, not in committed files
- Webhook notifications for pipeline completion/failure — could be added later if automation needs arise
- Individual pipeline step execution — could be useful for debugging but adds complexity; revisit if needed
- Auto-refresh or event-driven dashboard updates — revisit when pipeline scheduling is implemented

</deferred>

---

*Phase: 13-pipeline-llm-dashboard-api-tests*
*Context gathered: 2026-02-22*
