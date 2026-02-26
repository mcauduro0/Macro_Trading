---
phase: 24-frontend-position-book-trade-blotter
plan: 01
subsystem: ui
tags: [react, recharts, pms, position-book, bloomberg, equity-curve, cdi-benchmark]

# Dependency graph
requires:
  - phase: 23-frontend-design-system-morning-pack-page
    provides: PMS design tokens (PMS_COLORS, PMS_TYPOGRAPHY), reusable components (PMSCard, PMSBadge, PMSSkeleton), MorningPackPage pattern
provides:
  - PositionBookPage.jsx with P&L summary cards, equity curve chart, collapsible positions table, close position dialog
  - Route wiring for /pms/portfolio pointing to PositionBookPage
  - Script loading in dashboard.html for PositionBookPage
affects: [24-02-trade-blotter, 25-frontend-risk-monitor, 26-frontend-attribution]

# Tech tracking
tech-stack:
  added: []
  patterns: [collapsible-asset-class-groups, expandable-detail-rows, inline-svg-sparkline, time-range-filtered-chart, close-position-dialog]

key-files:
  created:
    - src/api/static/js/pms/pages/PositionBookPage.jsx
  modified:
    - src/api/static/js/App.jsx
    - src/api/static/dashboard.html

key-decisions:
  - "Inline P&L summary cards (not PMSMetricCard) for dense layout control with 5 horizontal cards"
  - "SVG polyline spark chart in expanded row detail (no Recharts for inline sparklines)"
  - "Close dialog uses sample-data fallback -- closes in UI even when API unavailable"
  - "CDI benchmark as dashed gray line using 13.75% annual rate compounded daily"

patterns-established:
  - "Collapsible asset class groups: expandedGroups Set with toggle, ASSET_CLASS_ORDER for sort"
  - "Expandable detail row: single expandedRowId state, click row to toggle"
  - "Time range filter: useState for range, useMemo to slice data array by date"

requirements-completed: [PMS-FE-PB-01, PMS-FE-PB-02, PMS-FE-PB-03]

# Metrics
duration: 5min
completed: 2026-02-25
---

# Phase 24 Plan 01: Position Book Page Summary

**Bloomberg PORT-style position viewer with P&L summary cards, equity curve + CDI benchmark chart, collapsible asset-class-grouped table with expandable detail rows, and inline close dialog**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T00:42:04Z
- **Completed:** 2026-02-25T00:47:43Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created 1037-line PositionBookPage.jsx with all 4 sections (P&L cards, equity chart, positions table, close dialog)
- 12 sample positions across 6 asset classes (FX, Rates, Inflation, Cupom Cambial, Sovereign, Cross-Asset) with deterministic data
- Equity curve with ComposedChart dual Y-axes (cumulative P&L + drawdown), CDI benchmark, 6 time range buttons
- Wired /pms/portfolio route and dashboard.html script loading in correct dependency order

## Task Commits

Each task was committed atomically:

1. **Task 1: Create PositionBookPage.jsx with all sections** - `337e52d` (feat)
2. **Task 2: Wire PositionBookPage into App.jsx routes and dashboard.html** - `4955206` (feat)

## Files Created/Modified
- `src/api/static/js/pms/pages/PositionBookPage.jsx` - Complete Position Book page (1037 lines) with P&L summary cards, equity curve chart, collapsible positions table, expandable detail rows, close dialog
- `src/api/static/js/App.jsx` - Added PositionBookPage window resolution and replaced PMSPlaceholder route
- `src/api/static/dashboard.html` - Added PositionBookPage.jsx script tag after MorningPackPage, before Sidebar

## Decisions Made
- Used inline P&L summary cards (not PMSMetricCard) for more control over dense horizontal layout
- SVG polyline spark chart in expanded row detail avoids loading Recharts for tiny inline charts
- Close dialog gracefully handles API errors by closing position in UI (sample data fallback)
- CDI benchmark line uses 13.75% annual rate compounded daily (252 trading days) as dashed gray line
- Group headers use colSpan split (6+4) to show asset class name on left and subtotal P&L on right

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Position Book page complete, ready for Phase 24 Plan 02 (Trade Blotter)
- All PMS page patterns established (MorningPackPage, PositionBookPage) for consistent future pages

---
*Phase: 24-frontend-position-book-trade-blotter*
*Completed: 2026-02-25*
