# Phase 25: Frontend Risk Monitor & Performance Attribution - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Two operational frontend pages for daily risk oversight: Risk Monitor (VaR gauges, stress tests, limit utilization, concentration) and Performance Attribution (P&L waterfall, strategy/asset attribution, time-series decomposition). Backend services (RiskMonitorService, PerformanceAttributionEngine) already exist from Phase 22. This phase builds the visual layer consuming those APIs.

</domain>

<decisions>
## Implementation Decisions

### Risk visualization layout
- 4-quadrant grid layout (Bloomberg PORT dense style): top-left VaR gauges, top-right stress test bars, bottom-left limit utilization bars, bottom-right concentration pie chart
- VaR displayed as semi-circular gauges (reuse SVG GaugeChart pattern from v3 RiskPage): 4 gauges in a row (Parametric 95%, Parametric 99%, MC 95%, MC 99%) with needle showing current vs limit
- Stress test results as horizontal bar chart: each scenario as a horizontal bar showing portfolio impact in BRL, sorted by severity, color-coded green/yellow/red by magnitude
- Historical VaR time-series chart placed below the 4-quadrant grid (full width), showing parametric VaR over time with 95%/99% lines and limit thresholds

### Attribution chart style
- P&L waterfall: classic floating-bar waterfall chart -- each strategy as a floating bar showing its P&L contribution, positive bars go up from cumulative baseline, negative go down, final bar shows total
- Asset class attribution table: standard table rows (asset class, P&L, % contribution, position count) with small inline horizontal bar showing relative contribution magnitude
- Time-series P&L: dual chart with daily P&L bars (color-coded) and cumulative P&L line overlaid on second Y-axis (ComposedChart pattern consistent with existing equity curve)
- Dimension switcher: tabbed approach (By Strategy | By Asset Class | By Instrument) -- each tab shows waterfall + table for that dimension. Keeps page clean, one dimension at a time.

### Alert & breach presentation
- Breach indicators inline on limit utilization bars -- each bar turns red/yellow when breached and pulses briefly, alert details appear via expandable click detail
- Two severity tiers matching backend RiskMonitorService: WARNING (amber at 80% utilization) and BREACH (red at 100%)
- Global visibility: nav badge on Risk sidebar item (extends existing Phase 23 alert badge pattern) plus summary line at top of Risk Monitor page ("2 warnings, 1 breach")
- Click a breached limit bar to expand: limit name, current value, threshold, % utilization, when last OK, trend (improving/worsening)

### Period selection & interaction
- Attribution page: button group selector (Daily | MTD | QTD | YTD | Custom) with Custom opening a date range picker
- Single shared period selector at top of Attribution page -- changing period updates waterfall, table, and time-series charts simultaneously
- Risk Monitor: no global period selector; VaR chart has its own trailing window selector only (30d | 60d | 90d | 1Y); rest of Risk Monitor always shows current snapshot
- Default Attribution period on page load: MTD (month-to-date)

### Claude's Discretion
- Attribution dimension switcher implementation (tabbed vs all-visible) -- Claude picks based on data volume and page density. User deferred this decision.
- Exact spacing, typography, and responsive breakpoints within the 4-quadrant grid
- Loading skeleton and error state design for both pages
- Custom date range picker component choice
- VaR historical chart trailing window default (30d vs 90d)

</decisions>

<specifics>
## Specific Ideas

- VaR gauges should reuse the SVG GaugeChart component pattern already built in Phase 19 (19-02) for the v3 RiskPage
- Stress test horizontal bars reference: Bloomberg SRSK screen style, sorted by severity
- P&L waterfall follows standard finance waterfall convention (floating bars, not stacked)
- Time-series decomposition uses the same ComposedChart dual Y-axis pattern as the equity curve overlay in PortfolioPage
- Limit bars pulse briefly on breach for visual attention, then settle to static color
- Alert badge on Risk nav item extends the existing Phase 23 pattern (already implemented)
- Bloomberg PORT-like dense 4-quadrant layout for risk monitor -- all key metrics visible at a glance without scrolling

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 25-frontend-risk-monitor-performance-attribution*
*Context gathered: 2026-02-25*
