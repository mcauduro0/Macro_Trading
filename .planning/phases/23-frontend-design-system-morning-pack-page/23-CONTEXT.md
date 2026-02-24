# Phase 23: Frontend Design System & Morning Pack Page - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

PMS frontend foundation — a cohesive design system (colors, components, layout) and the Morning Pack page as the first operational screen, giving the manager a complete daily overview before markets open. All PMS frontend components use CDN-loaded React + Tailwind consistent with v3.0 dashboard approach. PMS navigation integrates with existing React dashboard sidebar, adding PMS section with 7 sub-pages.

</domain>

<decisions>
## Implementation Decisions

### Visual Identity & Density
- **Bloomberg-dense style** — maximum data density, dark background, small text, every pixel shows information. Professional trading desk feel.
- **Dark theme only** — dark background (navy/charcoal), light text. No light mode toggle. Classic trading terminal aesthetic, easier on eyes for long sessions.
- **Classic red/green P&L colors** — red for losses/bearish, green for gains/bullish. Universal trading convention.
- **Traffic light risk colors** — green (OK) → yellow (warning) → red (breach). Intuitive 3-tier risk level system.

### Morning Pack Layout
- **Section order: alerts → context → actions** — sticky alert banner at top, then market overview, then agent summaries, then trade proposals at bottom.
- **Dashboard grid layout** — cards arranged in a 2-3 column grid. Bloomberg-style, see everything at once, minimal scrolling.
- **Compact ticker strip for market overview** — small, dense cards with ticker/value/change. Fit 10-15 indicators in one row (DI, IBOV, USD/BRL, VIX, etc.).
- **Sticky top alert banner** — fixed banner at very top of the page, always visible, auto-dismisses when acknowledged. Color-coded by severity (traffic light colors).
- **One card per agent** — each of the 5 analytical agents gets its own card showing signal direction, confidence score, key metric, and one-line rationale.

### Trade Proposal Cards
- **Hybrid approve/reject flow** — inline quick-approve for high-confidence proposals directly on Morning Pack cards. Click-through to detail panel for anything flagged or lower confidence.
- **Full context inline** — each card shows: ticker, direction, size, conviction score, expected P&L, one-line rationale. Dense but complete.
- **Numeric conviction score** — display as number (e.g., 0.85) with color coding. Precise, Bloomberg-style. No bar gauges.
- **Grouped by agent** — trade proposals organized by agent source (Vol Agent proposals, Macro Agent proposals, etc.), not by conviction or risk impact.

### PMS Navigation
- **Mode switch architecture** — top-level mode switch between "Dashboard" (v3.0) and "PMS". Sidebar completely changes content based on mode. Not nested sections.
- **Sidebar header toggle** — prominent icon-based toggle in the sidebar header area with clear labels "Dashboard" / "PMS".
- **Daily workflow page order** — Morning Pack first (daily use), then Portfolio, Risk, Trade Blotter, Attribution, Strategies, Settings.
- **Morning Pack as default landing** — switching to PMS mode always opens Morning Pack. Most time-sensitive page.

### Claude's Discretion
- Exact dark theme color values (navy vs charcoal shades)
- Typography choices (font family, sizes, weights for dense layout)
- Component library internals (card borders, table cell padding, badge shapes)
- Responsive breakpoints and grid column behavior
- Loading states and skeleton designs
- Error state handling
- Exact spacing between grid sections
- Alert banner animation and dismiss behavior
- Agent card internal layout arrangement
- Trade proposal detail panel/modal design when clicking through

</decisions>

<specifics>
## Specific Ideas

- Bloomberg Terminal is the reference benchmark for information density and dark theme aesthetic
- The ticker strip should feel like a real-time market data ribbon
- Agent cards should be visually distinct from trade proposal cards (different card treatment) so the PM can instantly differentiate "analysis" from "action items"
- The mode switch should make PMS feel like a separate application within the same shell, not just more pages bolted onto v3.0
- Conviction scores displayed as precise numbers (0.85) not rounded categories (High/Medium/Low)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 23-frontend-design-system-morning-pack-page*
*Context gathered: 2026-02-24*
