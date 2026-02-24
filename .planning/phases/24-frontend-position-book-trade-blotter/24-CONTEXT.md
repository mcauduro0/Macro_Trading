# Phase 24: Frontend Position Book & Trade Blotter - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Two core operational PMS frontend pages: Position Book shows live portfolio with P&L and risk metrics; Trade Blotter provides the approval workflow interface for reviewing and acting on system-generated trade proposals. Both pages consume existing PMS API endpoints (Phase 21-22) and use the PMS design system (Phase 23).

</domain>

<decisions>
## Implementation Decisions

### Position Book table design
- Collapsible asset class sections (FX, Rates, Inflation, Cupom Cambial, Sovereign, Cross-Asset) with subtotals per group -- Bloomberg PORT screen style
- Balanced column order: Instrument -> Direction -> Size -> Entry Price -> Current Price -> Unrealized P&L -> DV01/Delta -> VaR Contribution -> Daily P&L -> Holding Days
- Expandable rows: clicking a position row reveals strategy attribution, entry date, stop/target levels, journal link, and recent P&L history spark chart
- Inline close button on each position row with confirmation dialog -- manager can close positions directly from Position Book

### P&L summary & equity curve
- P&L summary cards at Claude's discretion (horizontal strip or hero cards -- choose what fits Bloomberg-dense style best)
- Equity curve shows three layers: cumulative P&L line + drawdown shaded overlay + CDI benchmark comparison line (dual-axis, consistent with v3.0 PortfolioPage ComposedChart pattern)
- YTD default time range, with buttons for 1M, 3M, 6M, YTD, 1Y, All
- Chart positioned full-width below P&L cards and above positions table -- prominent visual anchor

### Trade Blotter approval flow
- Slide-out right panel for approval form: clicking approve opens a right-side panel with execution fields (price, notional, thesis, target, stop, time horizon) while staying on the blotter page
- Expandable risk detail: compact inline summary (conviction, expected P&L, one-line risk impact) visible by default; click to expand full risk context (portfolio VaR before/after, concentration impact, correlated positions)
- Batch actions supported: checkboxes per proposal + "Approve Selected" / "Reject Selected" buttons at top of the pending proposals list
- Modify-and-approve: manager can override size, price, stop/target directly in the approval form fields before confirming -- no separate modify step

### Trade history & status display
- Tab navigation within Trade Blotter: two tabs at top -- "Pending Proposals" and "History"
- Outcome-focused columns: Instrument -> Direction -> Status (badge) -> Conviction -> Proposed Date -> Decision Date -> Realized P&L (if executed)
- Status filtering + date range picker (covers 90% of use cases -- keep it minimal)
- Color-coded status badges using PMS design system: Green APPROVED, Red REJECTED, Gray EXPIRED, Blue EXECUTED

### Claude's Discretion
- P&L summary card layout style (horizontal strip vs hero cards with sparklines)
- Exact sorting behavior for positions table (default sort order, multi-column sort)
- Rejection flow UX (inline notes field vs prompt)
- Pagination or virtual scroll for trade history with many entries
- Exact spark chart implementation for expanded position rows

</decisions>

<specifics>
## Specific Ideas

- Position Book should feel like a Bloomberg PORT screen with asset class grouping and subtotals
- Equity curve follows the same dual-axis ComposedChart pattern from v3.0 PortfolioPage (Phase 19-02) but adds CDI benchmark
- Slide-out panel for approval keeps context visible (manager can see the proposal list while filling in execution details)
- Batch approve is important for morning workflow: manager reviews all proposals, checks the high-conviction ones, approves in bulk

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 24-frontend-position-book-trade-blotter*
*Context gathered: 2026-02-24*
