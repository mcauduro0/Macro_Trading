# Phase 22: Morning Pack, Risk Monitor & Attribution - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Three backend services that power the operational frontend: MorningPackService (daily briefing generation consolidating all system intelligence), RiskMonitorService (real-time risk dashboard data with limit monitoring), and PerformanceAttributionEngine (multi-dimensional P&L attribution). Frontend pages that consume these services are Phase 23-26. API endpoints for these services are included.

</domain>

<decisions>
## Implementation Decisions

### Morning Pack content & structure
- **Action-first ordering**: Lead with action items and trade proposals, then supporting context (regime, signals, portfolio). Manager sees what to DO first
- **Full agent summaries**: Each of the 5 agents includes signal direction, conviction, all key drivers, risks, and narrative excerpt. Comprehensive, not abbreviated
- **Broad action items**: Include trade proposals, risk limit breaches, signal flips, conviction surges, stale data warnings, expiring positions, and regime changes. Full operational checklist — everything notable
- **Analytical brief narrative**: LLM-generated macro narrative is 4-5 paragraphs, research note style. Explains WHY, connects dots across agents, gives conviction. ~400 words. Uses Claude API with template fallback

### Risk Monitor scope
- **Daily snapshot refresh**: Risk data computed once daily, aligned with Dagster pipeline run. Not real-time streaming or periodic refresh
- **All existing limits surfaced**: Surface everything from RiskLimitsManager v2: daily loss, weekly loss, position size, concentration, gross exposure, risk budget. Full visibility
- **Two-tier alert severity**: Warning at 80% utilization, Breach at 100%. Matches existing RiskLimitsManager check_all_v2 pattern (OK / WARNING / BREACHED)
- **Current + 30-day trend**: Include trailing 30-day history for VaR, stress test results, and limit utilization. Shows direction of risk, not just current level

### Attribution dimensions
- **5 decomposition axes**: Strategy, asset class, instrument, time period, AND factor-based attribution (carry, momentum, mean-reversion, event-driven, etc.)
- **Tag-based factor mapping**: Each strategy gets manual factor tags (e.g., FX-02 = carry + momentum). Attribution sums P&L by tag. Simple, transparent, no regression
- **Extended periods + custom range**: Daily, WTD, MTD, QTD, YTD, Since Inception, plus arbitrary from/to date range. Maximum flexibility
- **Additive attribution (no cross-terms)**: Each dimension sums to total P&L independently. No Brinson-style interaction terms. Simple and auditable for a macro fund

### Service integration
- **Graceful degradation**: Return partial results with 'unavailable' markers for missing sections. Morning Pack generates with whatever data is available. Never fail completely
- **Direct import, not API calls**: Import v3 classes (SignalAggregator, RiskEngine, agents, etc.) and invoke directly. In-process, no HTTP overhead. Monolith pattern
- **No demo mode in services**: Sample data lives in test fixtures only. Services require real components. Cleaner separation than v3 endpoint pattern
- **Auto-persist briefings**: Every MorningPackService.generate() call writes to DailyBriefing table automatically. Historical record of all briefings. Matches daily pipeline flow

### Claude's Discretion
- Internal data structure design for each service
- Exact API endpoint paths and response shapes (following existing PMS router conventions)
- Error handling specifics within graceful degradation
- Factor tag taxonomy (which tags to use for each strategy)
- VaR computation method selection when both parametric and Monte Carlo are available

</decisions>

<specifics>
## Specific Ideas

- Morning Pack should feel like a Brevan Howard/Bridgewater daily morning briefing — but structured action-first so the manager knows what needs attention before reading the macro context
- Factor tags should cover the main strategy styles present in the system: carry, momentum, mean-reversion, event-driven, relative-value, macro-discretionary
- 30-day risk trend data enables the frontend (Phase 25) to show historical VaR charts without additional backend work

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 22-morning-pack-risk-monitor-attribution*
*Context gathered: 2026-02-24*
