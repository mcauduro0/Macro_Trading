# Phase 26: Frontend Decision Journal, Agent Intel & Compliance - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Three operational PMS frontend pages: Decision Journal for reviewing all trading decisions with outcome tracking, Agent Intelligence Hub for viewing agent signals and AI narratives, and a Compliance & Audit page for audit trail viewing, hash integrity verification, and data export. All pages follow the existing PMS design system (inline styles, PMS_COLORS tokens, CDN React + Recharts).

</domain>

<decisions>
## Implementation Decisions

### Decision Journal - Timeline Layout
- Vertical timeline with date markers on the left, decision cards on the right (Bloomberg event log / git history style)
- Cards show headline only before expanding: decision type (OPEN/CLOSE/REJECT/NOTE), instrument, date, and P&L outcome -- compact, ~10 entries visible per screen
- Expanded cards show full decision context: manager rationale, macro snapshot at time of decision, portfolio state, strategy source, conviction, risk impact -- everything stored in DecisionJournal
- Decision types visually distinguished by color-coded badges: OPEN = blue, CLOSE = green/red (by P&L sign), REJECT = amber, NOTE = gray

### Agent Intelligence Hub - Card Grid
- 5 agent cards in a responsive 2-3 column grid layout
- Cross-Asset agent gets a wider/featured card position within the grid
- Each card shows at a glance: agent name, overall signal direction (bullish/bearish/neutral), confidence score, and top 3 key drivers from latest report
- Cross-Asset narrative (LLM-generated) displayed via expandable section within the Cross-Asset card ("Read full narrative" expand button reveals text inline)
- Mini sparkline on each card showing last 30 days of confidence/signal evolution

### Compliance & Audit - Separate Page
- Compliance & Audit as its own dedicated page in the PMS sidebar (not a tab within Decision Journal)
- Audit trail displayed as a log viewer, newest entries first -- each row shows timestamp, action, user, hash snippet, verification status
- Hash integrity verification runs automatically on page load -- green checkmark or red warning per visible entry, no manual action needed
- Export supports CSV + JSON formats (CSV for human review, JSON for programmatic ingestion)

### Search, Filter & Navigation
- Top filter bar (horizontal) above content on both Decision Journal and Compliance pages -- same filter bar component shared between pages
- Filter controls: date range dropdown, decision type multi-select (OPEN/CLOSE/REJECT/NOTE), asset class dropdown, text search for instrument
- Date range presets aligned with trading periods: Today, This Week, MTD, QTD, YTD, Custom date picker
- Decision Journal uses infinite scroll for loading more entries (auto-load as user scrolls near bottom)

### Claude's Discretion
- Exact spacing, typography, and card dimensions
- Loading skeleton design for all three pages
- Sparkline implementation approach (SVG polyline vs Recharts mini chart)
- Empty state messaging when no journal entries match filters
- How many audit log entries to auto-verify on initial load (all visible vs first N)
- Agent card expand/collapse animation

</decisions>

<specifics>
## Specific Ideas

- Vertical timeline evokes Bloomberg event log / git history feel -- date markers as anchors, decision cards as events
- Filter presets use trading calendar periods (MTD, QTD, YTD) consistent with the Performance Attribution page period selector
- Compliance page is deliberately separate from Decision Journal -- different audience (compliance officer vs portfolio manager) even though data overlaps
- Infinite scroll chosen for Journal (vs Load More on Trade Blotter history) because Journal is a primary review tool where continuous scrolling supports narrative reading

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 26-frontend-decision-journal-agent-intel-compliance*
*Context gathered: 2026-02-25*
