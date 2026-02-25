---
phase: 23-frontend-design-system-morning-pack-page
plan: 01
subsystem: ui
tags: [react, design-system, pms, bloomberg, dark-theme, navigation, components]

# Dependency graph
requires:
  - phase: 19-dashboard-frontend-multi-page
    provides: "HashRouter SPA with 5 page routes, Sidebar, CDN-only Babel+React architecture"
  - phase: 22-morning-pack-risk-monitor-attribution
    provides: "PMS backend APIs (briefing, risk monitor, attribution)"
provides:
  - "PMS_COLORS semantic color tokens for P&L, risk, direction, conviction, agent accents"
  - "PMS_TYPOGRAPHY Bloomberg-dense monospace font stack"
  - "PMS_SPACING compact spacing scale"
  - "7 helper functions (pnlColor, riskColor, directionColor, convictionColor, formatPnL, formatPercent, formatNumber)"
  - "8 reusable PMS components (PMSCard, PMSTable, PMSBadge, PMSGauge, PMSLayout, PMSMetricCard, PMSSkeleton, PMSAlertBanner)"
  - "Dashboard/PMS mode switch in sidebar header"
  - "7 PMS nav items and routes (Morning Pack, Portfolio, Risk, Trade Blotter, Attribution, Strategies, Settings)"
affects: [23-02, 24-position-book-trade-blotter, 25-risk-monitor-attribution-pages, 26-pms-settings-integration]

# Tech tracking
tech-stack:
  added: [JetBrains Mono font from Google Fonts CDN]
  patterns: [window.PMS_THEME global design tokens, inline styles for PMS dark theme, mode-aware sidebar with conditional nav items, AppContent inner component for useNavigate inside HashRouter]

key-files:
  created:
    - src/api/static/js/pms/components.jsx
  modified:
    - src/api/static/js/pms/theme.jsx
    - src/api/static/js/Sidebar.jsx
    - src/api/static/js/App.jsx
    - src/api/static/dashboard.html

key-decisions:
  - "PMS components use inline styles referencing PMS_COLORS, not Tailwind color classes, for Bloomberg-dense dark theme consistency"
  - "AppContent inner component pattern enables useNavigate hook inside HashRouter context"
  - "MorningPackPage lazy resolution from window.MorningPackPage for plan 23-02 integration"
  - "Alert badge shown on Risk item in both Dashboard and PMS modes"

patterns-established:
  - "PMS design token access: window.PMS_THEME.PMS_COLORS/PMS_TYPOGRAPHY/PMS_SPACING"
  - "PMS component pattern: inline styles with PMS_COLORS, exposed on window for CDN/Babel"
  - "Mode switch pattern: pmsMode boolean prop flows from App -> Layout -> Sidebar"
  - "PMS route pattern: /pms/{page-name} with PMSPlaceholder for unbuilt pages"

requirements-completed: [PMS-FE-DS-01, PMS-FE-DS-02, PMS-FE-MP-03]

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 23 Plan 01: PMS Design System Foundation Summary

**Bloomberg-dense PMS design tokens (semantic P&L/risk/direction colors, monospace typography), 8-component UI library, and Dashboard/PMS mode-switch sidebar with 7 PMS navigation routes**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24T22:07:27Z
- **Completed:** 2026-02-24T22:12:06Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- PMS_COLORS semantic color palette covering P&L (green/red), risk levels (traffic light), signal directions, conviction scale, and per-agent accent colors
- 8 reusable PMS components (PMSCard, PMSTable, PMSBadge, PMSGauge, PMSLayout, PMSMetricCard, PMSSkeleton, PMSAlertBanner) all Bloomberg-dense dark styled
- Sidebar header mode toggle switching between Dashboard (5 nav items) and PMS (7 nav items) with distinct navigation sets
- 7 PMS routes with placeholder pages ready for implementation in plans 23-02, 24, 25, 26

## Task Commits

Each task was committed atomically:

1. **Task 1: PMS design tokens and reusable component library** - `0d24a70` (feat)
2. **Task 2: Mode-switch sidebar, PMS routes, and dashboard.html integration** - `ab4f150` (feat)

## Files Created/Modified
- `src/api/static/js/pms/theme.jsx` - PMS design tokens: colors, typography, spacing, 7 helper functions
- `src/api/static/js/pms/components.jsx` - 8 reusable PMS UI components with Bloomberg-dense styling
- `src/api/static/js/Sidebar.jsx` - Mode switch toggle, PMS_NAV_ITEMS (7 items), 4 new SVG icons
- `src/api/static/js/App.jsx` - PMS mode state, AppContent pattern, 7 PMS routes, PMSPlaceholder
- `src/api/static/dashboard.html` - JetBrains Mono font, PMS script loading, Tailwind pms colors

## Decisions Made
- PMS components use inline styles referencing PMS_COLORS for Bloomberg-dense consistency (not Tailwind color classes for PMS-specific colors)
- AppContent inner component pattern used to enable useNavigate() hook inside HashRouter context
- MorningPackPage resolved lazily from window.MorningPackPage with fallback to PMSPlaceholder
- Alert badge shown on Risk nav item in both Dashboard (/risk) and PMS (/pms/risk) modes
- PMS mode auto-detected from URL on initial load (location.pathname.startsWith('/pms/'))

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Design system foundation complete: theme.jsx and components.jsx ready for import by all PMS pages
- Plan 23-02 can build MorningPackPage using PMSCard, PMSTable, PMSLayout, PMSMetricCard, PMSBadge, and PMS_THEME helpers
- Plans 24-26 have placeholder routes ready for replacement with actual page implementations
- All existing v3.0 Dashboard functionality preserved when in Dashboard mode

## Self-Check: PASSED

All 5 created/modified files verified present on disk. Both task commits (0d24a70, ab4f150) verified in git log.

---
*Phase: 23-frontend-design-system-morning-pack-page*
*Completed: 2026-02-24*
