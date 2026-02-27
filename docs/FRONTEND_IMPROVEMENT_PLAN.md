# Frontend Improvement Plan: Macro Trading System
**Created:** 2026-02-27
**Based on:** FRONTEND_DELIVERY_REVIEW.md
**Target:** PMS-only frontend with all missing features and fixes

---

## Overview

This plan addresses **15 issues** and **7 missing features** identified in the delivery review.
Organized into **6 phases** in priority order, each phase is independently deployable.

**Estimated total:** ~3,500 LOC of changes across 20+ files.

---

## Phase 1: Production Access & Critical Fixes
**Priority:** P0 (Production Blocking)
**Estimated changes:** ~80 LOC

### Task 1.1: Fix CORS for Production IP

**File:** `src/api/main.py` (lines 117-125)

**Current:**
```python
_allowed_origins = ["http://localhost:3000", "http://localhost:8000"]
if settings.debug:
    _allowed_origins = ["*"]
```

**Target:**
```python
_allowed_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://157.230.187.3:8000",
]
# Also support ALLOWED_ORIGINS from environment
if settings.allowed_origins:
    _allowed_origins.extend(settings.allowed_origins.split(","))
if settings.debug:
    _allowed_origins = ["*"]
```

**Also update:** `src/core/config.py` — Add `allowed_origins: str = ""` field to Settings class.

### Task 1.2: Add Production Host Configuration

**File:** `src/core/config.py`

Add a new field:
```python
allowed_origins: str = ""  # Comma-separated list of allowed CORS origins
```

### Task 1.3: Add Sample Data Indicator to PMS

**Files to modify (8 PMS pages):**
- `src/api/static/js/pms/components.jsx` — Add new `PMSSampleDataBanner` component
- All 8 PMS page files — Add banner when using fallback data

**New component in `components.jsx`:**
```jsx
function PMSSampleDataBanner() {
  return (
    <div style={{
      backgroundColor: '#d29922',
      color: '#0d1117',
      padding: '4px 12px',
      fontSize: '0.625rem',
      fontFamily: PMS_TYPOGRAPHY.fontFamily,
      fontWeight: 600,
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      textAlign: 'center',
      position: 'sticky',
      top: 0,
      zIndex: 25,
    }}>
      SAMPLE DATA — API unavailable, displaying demo data
    </div>
  );
}
```

**Integration pattern for each page:**
Each PMS page already has a pattern like:
```jsx
const bookData = (book.data && book.data.summary) ? book.data : SAMPLE_BOOK;
```

Add a `usingSampleData` boolean and render banner:
```jsx
const usingSampleData = !(book.data && book.data.summary);
// ...
{usingSampleData && <PMSSampleDataBanner />}
```

### Task 1.4: Verify Server Binding

**Check:** Ensure uvicorn is started with `--host 0.0.0.0` not `--host 127.0.0.1`.
**File:** `docker-compose.yml` or startup script — verify the command.

---

## Phase 2: Remove Dashboard, Unify to PMS-Only
**Priority:** P1 (Quality)
**Estimated changes:** ~400 LOC modified, ~1,500 LOC removed

### Task 2.1: Add Signals Page to PMS

**New file:** `src/api/static/js/pms/pages/SignalsPage.jsx` (~350 LOC)

Migrate the signal heatmap and flip timeline from the Dashboard's `SignalsPage.jsx`, but rewrite using the PMS design system:

- Use `PMSCard` containers instead of Tailwind utility classes
- Use `PMS_COLORS` for heatmap cell coloring
- Use `PMSBadge` for direction badges
- Use `PMS_TYPOGRAPHY.fontFamily` (JetBrains Mono) consistently
- Add a section header "SIGNAL HEATMAP" using PMS uppercase label style
- Increase heatmap cell minimum height from 18px to 24px for readability
- Add click-to-drill-down on heatmap cells (show strategy detail modal)

**Sections:**
1. Signal Heatmap (30 days x strategies) — enlarged cells, PMS colors
2. Signal Flip Timeline — using `PMSTable` component
3. Consensus Summary — using `PMSMetricCard` components

### Task 2.2: Update Sidebar — Remove Dashboard Toggle

**File:** `src/api/static/js/Sidebar.jsx`

**Changes:**
1. Remove `NAV_ITEMS` array (Dashboard navigation)
2. Remove `pmsMode` toggle button from header
3. Remove `onModeChange` prop handling
4. Always render PMS navigation items
5. Add new "Signals" nav item to `PMS_NAV_ITEMS`:

```jsx
const PMS_NAV_ITEMS = [
  { to: "/pms/morning-pack", label: "Morning Pack",      Icon: IconSunrise },
  { to: "/pms/portfolio",    label: "Position Book",     Icon: IconBriefcase },
  { to: "/pms/blotter",      label: "Trade Blotter",     Icon: IconList },
  { to: "/pms/signals",      label: "Signals",           Icon: IconActivity },  // NEW
  { to: "/pms/risk",         label: "Risk Monitor",      Icon: IconShield },
  { to: "/pms/attribution",  label: "Attribution",       Icon: IconPieChart },
  { to: "/pms/journal",      label: "Decision Journal",  Icon: IconBook },
  { to: "/pms/agents",       label: "Agent Intel",       Icon: IconCpu },
  { to: "/pms/compliance",   label: "Compliance",        Icon: IconClipboardCheck },
];
```

6. Always use Bloomberg dark background (`#0d1117`)
7. Update logo area — remove toggle, show "MACRO TRADING PMS" text when expanded

### Task 2.3: Update App.jsx — Remove Dashboard Routes

**File:** `src/api/static/js/App.jsx`

**Changes:**
1. Remove Dashboard route definitions (lines 174-179)
2. Remove `pmsMode` state and `handleModeChange` function
3. Update default redirect: `<Navigate to="/pms/morning-pack" />`
4. Add Signals route: `<Route path="/pms/signals" element={<SignalsPage />} />`
5. Remove `PMSPlaceholder` component
6. Always apply PMS background styling
7. Simplify `Layout` — no conditional styling

### Task 2.4: Remove Dashboard Page Files

**Files to delete:**
- `src/api/static/js/pages/StrategiesPage.jsx`
- `src/api/static/js/pages/SignalsPage.jsx`
- `src/api/static/js/pages/RiskPage.jsx`
- `src/api/static/js/pages/PortfolioPage.jsx`
- `src/api/static/js/pages/AgentsPage.jsx`

### Task 2.5: Update dashboard.html — Remove Dashboard Script Tags

**File:** `src/api/static/dashboard.html`

Remove `<script>` tags for the 5 deleted Dashboard page files.
Add `<script>` tag for new `pms/pages/SignalsPage.jsx`.

### Task 2.6: Add Backtest Metrics to Attribution Page

**File:** `src/api/static/js/pms/pages/PerformanceAttributionPage.jsx`

Add a new dimension tab "By Backtest" to the `DimensionSwitcher`:
- Fetches from `/api/v1/backtest/results`
- Shows backtest metrics grid (7 metrics: Ann. Return, Sharpe, Sortino, Max DD, Win Rate, Trades, Profit Factor)
- Shows equity curve per strategy (reusable from old StrategiesPage)

### Task 2.7: Add Circuit Breaker to Risk Monitor Page

**File:** `src/api/static/js/pms/pages/RiskMonitorPage.jsx`

Add a section below the 4-quadrant grid:
- Circuit breaker status bar (state, scale, drawdown percentage)
- Use `PMSBadge` for state indicator (NORMAL/WARNING/TRIGGERED)
- Fetch from existing `/api/v1/risk/dashboard` endpoint

---

## Phase 3: Missing Feature — Trade Workflow Enhancements
**Priority:** P1 (Quality)
**Estimated changes:** ~500 LOC

### Task 3.1: Implement Modify-and-Approve Workflow

**File:** `src/api/static/js/pms/pages/TradeBlotterPage.jsx`

**Current state:** Only approve/reject buttons exist.

**Add:**
1. "Modify & Approve" button next to approve on each pending proposal
2. Clicking opens a slide-out panel (side drawer) with editable fields:
   - `execution_notional_brl` — pre-filled with `suggested_notional_brl`, editable
   - `execution_price` — empty, user enters
   - `notes` — textarea for manager notes
3. "Confirm Modified Approval" button submits to:
   ```
   POST /api/v1/pms/trades/proposals/{id}/modify-approve
   Body: { execution_notional_brl, execution_price, notes }
   ```
4. On success, update proposal status to "MODIFIED" in UI with green border
5. On error, show inline error message

**Slide-out panel design:**
- 400px wide panel sliding from right edge
- Dark background overlay (rgba 0,0,0,0.5)
- Header: "Modify Proposal — {instrument}"
- Uses PMS form styling (dark inputs, PMS colors)
- Cancel and Confirm buttons at bottom

### Task 3.2: Replace window.prompt() with Rejection Modal

**File:** `src/api/static/js/pms/pages/TradeBlotterPage.jsx`

**Current:** `const reason = window.prompt('Rejection reason (optional):');`

**Replace with:** A proper modal component similar to `ClosePositionDialog`:
- Modal overlay with dark backdrop
- Title: "Reject Proposal"
- Subtitle: "{instrument} | {direction} | {notional}"
- Textarea: "Rejection reason (optional)"
- Buttons: Cancel (gray outline) + Confirm Reject (red)
- Posts to: `POST /api/v1/pms/trades/proposals/{id}/reject`

### Task 3.3: Add Pre-Trade Risk Analysis Panel

**File:** `src/api/static/js/pms/pages/TradeBlotterPage.jsx`

On each pending proposal, add an expandable "Risk Impact" section:
- **Current VaR vs Post-Trade VaR** — two horizontal gauges side by side
- **Concentration Impact** — percentage bar showing asset class concentration after trade
- **Correlated Positions** — list of existing positions that would be affected
- **Marginal VaR Contribution** — the incremental VaR from this position

Data source: Already available in sample data's `risk_impact` field:
```json
{
  "var_before": 1.42,
  "var_after": 1.58,
  "concentration_impact": 32.1,
  "correlated_positions": ["NTN-B 2035", "DI1 Jan26"]
}
```

For live data, use: `POST /api/v1/pms/risk/pre-trade` endpoint (already exists in backend).

**Visual design:**
- Collapsible section with arrow toggle
- VaR gauges using `PMSGauge` component
- Concentration bar with threshold line at limit
- Correlated positions as clickable badges

---

## Phase 4: Missing Feature — Attribution Enhancements
**Priority:** P2 (Polish)
**Estimated changes:** ~600 LOC

### Task 4.1: Add Rolling Metrics Section

**File:** `src/api/static/js/pms/pages/PerformanceAttributionPage.jsx`

**New section:** "Rolling Metrics" below the time-series decomposition chart.

- 3 rolling metric charts side-by-side:
  1. Rolling Sharpe Ratio (21d, 63d, 126d windows)
  2. Rolling Volatility (annualized, 21d and 63d)
  3. Rolling Return (cumulative, 21d)
- Each as a `ComposedChart` with multiple `Line` components (one per window)
- Window selector: radio buttons for 21d/63d/126d
- Data from: `GET /api/v1/pms/attribution/rolling?metric=sharpe&window=63`

### Task 4.2: Add Benchmark Comparison Section

**File:** `src/api/static/js/pms/pages/PerformanceAttributionPage.jsx`

**New section:** "Benchmark Comparison" tab in the DimensionSwitcher.

- Equity curve chart overlaid with benchmark lines (CDI, IMA-B, IHFA)
- Relative performance chart (portfolio return - benchmark return)
- Summary table: Alpha, Tracking Error, Information Ratio per benchmark
- Data from: `GET /api/v1/pms/attribution/benchmark?benchmarks=CDI,IMA_B,IHFA`

**Visual design:**
- Portfolio line: blue (#58a6ff)
- CDI: gray dashed (#8b949e)
- IMA-B: purple dashed (#a371f7)
- IHFA: orange dashed (#f0883e)

### Task 4.3: Add Best/Worst Trades Section

**File:** `src/api/static/js/pms/pages/PerformanceAttributionPage.jsx`

**New section:** "Top Trades" below rolling metrics.

- Two-column layout:
  - Left: "Best 10 Trades" (green accent, sorted by P&L desc)
  - Right: "Worst 10 Trades" (red accent, sorted by P&L asc)
- Each entry: instrument, direction badge, P&L, holding days, strategy
- Data from: `GET /api/v1/pms/attribution/best-worst?n=10`

### Task 4.4: Add Monthly Returns Heatmap (Migrated from Dashboard)

**File:** `src/api/static/js/pms/pages/PerformanceAttributionPage.jsx`

Migrate the monthly returns heatmap from the old Dashboard's `PortfolioPage.jsx`:
- Rewrite using PMS design system (inline styles, PMS_COLORS)
- Connect to real API: `GET /api/v1/pms/pnl/monthly-heatmap`
- Keep the green/red intensity-based cell coloring

---

## Phase 5: Missing Feature — Risk Monitor Enhancements
**Priority:** P2 (Polish)
**Estimated changes:** ~400 LOC

### Task 5.1: Add Ad-Hoc Stress Test Input

**File:** `src/api/static/js/pms/pages/RiskMonitorPage.jsx`

**New section:** "Custom Stress Test" panel below the 4-quadrant grid.

- Form with scenario parameter inputs:
  - Scenario name (text)
  - Asset class shocks (sliders or number inputs):
    - FX shock (%)
    - Rates shock (bps)
    - Equity shock (%)
    - Credit spread shock (bps)
    - Volatility shock (%)
  - "Run Stress Test" button
- Results displayed as:
  - Portfolio P&L impact (large number with color)
  - Position-level impact table (which positions are most affected)
  - Comparison bar added to existing stress test chart

- API: `POST /api/v1/pms/risk/stress-test`
  ```json
  {
    "scenario_name": "Custom Scenario",
    "shocks": {
      "fx_pct": -5.0,
      "rates_bps": 100,
      "equity_pct": -10.0,
      "credit_bps": 50,
      "vol_pct": 30.0
    }
  }
  ```

### Task 5.2: Add Drawdown History Chart

**File:** `src/api/static/js/pms/pages/RiskMonitorPage.jsx`

Below the historical VaR chart, add:
- Drawdown underwater chart (area chart showing % drawdown below 0)
- Reference line at -5% (drawdown limit)
- Color: red area with darker fill as drawdown deepens
- Data from: `GET /api/v1/pms/risk/drawdown-history` (endpoint exists)

---

## Phase 6: Code Quality & Technical Debt
**Priority:** P2 (Polish)
**Estimated changes:** ~300 LOC modified

### Task 6.1: Consolidate Duplicated Utilities

**File:** `src/api/static/js/pms/theme.jsx`

Move these functions into `theme.jsx` (currently duplicated in 3-4 files):

1. `formatPnLShort(value)` — add to `window.PMS_THEME` exports
2. `formatSize(value)` — add to `window.PMS_THEME` exports
3. `seededRng(seed)` — add to `window.PMS_THEME` exports
4. `dirBadgeVariant(dir)` — add to `window.PMS_THEME` exports

Then update all PMS page files to use `window.PMS_THEME.formatPnLShort` etc. instead of local definitions.

**Files to update:**
- `PositionBookPage.jsx` — remove local `formatSize`, `formatPnLShort`, `seededRng`, `dirBadgeVariant`
- `RiskMonitorPage.jsx` — remove local `formatPnLShort`, `seededRng`
- `PerformanceAttributionPage.jsx` — remove local `formatPnLShort`, `formatSize`, `seededRng`
- `TradeBlotterPage.jsx` — remove local duplicates
- `MorningPackPage.jsx` — remove local `formatNotional`, `formatExpectedPnL` (or consolidate)

### Task 6.2: Fix Sequential Agent Fetching

**File:** `src/api/static/js/pms/pages/AgentIntelPage.jsx` (and Dashboard's AgentsPage if still present)

**Current:** Sequential `for` loop with `await fetch()` for each agent.

**Fix:** Use `Promise.all()` for parallel fetching:
```jsx
async function fetchReports() {
  const promises = agents.map(async (agent) => {
    try {
      const res = await fetch("/api/v1/agents/" + agent.agent_id + "/latest");
      if (res.ok) {
        const json = await res.json();
        return { id: agent.agent_id, data: json.data };
      }
    } catch (e) { /* skip */ }
    return null;
  });

  const results = await Promise.all(promises);
  const newReports = {};
  results.filter(Boolean).forEach(r => { newReports[r.id] = r.data; });
  if (!cancelled) {
    setReports(newReports);
    setReportsLoading(false);
  }
}
```

### Task 6.3: Add Basic Responsive Breakpoints

**File:** `src/api/static/js/pms/components.jsx`

Update `PMSLayout` grid to handle narrower screens:
```jsx
function PMSLayout({ children, minColWidth }) {
  const colMin = minColWidth || '300px';
  const layoutStyle = {
    display: 'grid',
    gridTemplateColumns: `repeat(auto-fit, minmax(${colMin}, 1fr))`,
    gap: PMS_SPACING.md,
    padding: PMS_SPACING.sm,
    fontFamily: PMS_TYPOGRAPHY.fontFamily,
  };
  return <div style={layoutStyle}>{children}</div>;
}
```

Add a CSS `@media` block in `dashboard.html` for tablets:
```css
@media (max-width: 1024px) {
  .ml-56 { margin-left: 4rem !important; }
}
```

Update PMS page inline styles that use fixed column counts to use `auto-fit` with `minmax()`.

### Task 6.4: Connect Real API Data to Position Book Equity Curve

**File:** `src/api/static/js/pms/pages/PositionBookPage.jsx`

**Current:** Uses `generateSampleEquityCurve()` as fallback.

**Fix:** The page already fetches from `/api/v1/pms/pnl/equity-curve` — but the fallback check is too aggressive. Ensure the real API data is preferred, and only fall back to sample when the fetch actually fails (not just when format differs).

Update:
```jsx
const equityData = useMemo(() => {
  if (equityCurve.data) {
    // Handle both array and object response formats
    const raw = Array.isArray(equityCurve.data) ? equityCurve.data : equityCurve.data.data;
    if (raw && raw.length > 0) return raw;
  }
  return SAMPLE_EQUITY_CURVE;
}, [equityCurve.data]);
```

---

## Phase Execution Order

```
Phase 1: Production Access & Critical Fixes     [IMMEDIATE - Day 1]
   ├─ 1.1 Fix CORS
   ├─ 1.2 Add config field
   ├─ 1.3 Sample data banner
   └─ 1.4 Verify server binding

Phase 2: Remove Dashboard, Unify to PMS-Only    [Day 1-2]
   ├─ 2.1 Create PMS Signals page
   ├─ 2.2 Update Sidebar
   ├─ 2.3 Update App.jsx
   ├─ 2.4 Delete Dashboard pages
   ├─ 2.5 Update dashboard.html
   ├─ 2.6 Add backtest to Attribution
   └─ 2.7 Add circuit breaker to Risk Monitor

Phase 3: Trade Workflow Enhancements            [Day 2-3]
   ├─ 3.1 Modify-and-approve workflow
   ├─ 3.2 Rejection modal
   └─ 3.3 Pre-trade risk panel

Phase 4: Attribution Enhancements               [Day 3-4]
   ├─ 4.1 Rolling metrics charts
   ├─ 4.2 Benchmark comparison
   ├─ 4.3 Best/worst trades
   └─ 4.4 Monthly heatmap migration

Phase 5: Risk Monitor Enhancements              [Day 4]
   ├─ 5.1 Ad-hoc stress test
   └─ 5.2 Drawdown history chart

Phase 6: Code Quality & Tech Debt               [Day 4-5]
   ├─ 6.1 Consolidate duplicated utilities
   ├─ 6.2 Fix sequential agent fetching
   ├─ 6.3 Responsive breakpoints
   └─ 6.4 Connect real API to equity curve
```

---

## Verification Criteria

### Phase 1 Complete When:
- [ ] `curl http://157.230.187.3:8000/health` returns 200
- [ ] Browser at `http://157.230.187.3:8000/dashboard` loads the SPA
- [ ] When API is down, yellow "SAMPLE DATA" banner appears on PMS pages

### Phase 2 Complete When:
- [ ] No Dashboard/PMS toggle in sidebar
- [ ] Default route goes to `/pms/morning-pack`
- [ ] 9 PMS nav items in sidebar (including Signals)
- [ ] Signals page shows heatmap and flip timeline with PMS design
- [ ] Old Dashboard page files are deleted
- [ ] All routes use `/pms/*` prefix

### Phase 3 Complete When:
- [ ] "Modify & Approve" button visible on pending proposals
- [ ] Clicking opens slide-out panel with editable fields
- [ ] Rejection uses a proper modal (not window.prompt)
- [ ] Risk impact section expandable on each proposal
- [ ] VaR before/after gauges displayed

### Phase 4 Complete When:
- [ ] Rolling Sharpe/vol/return charts visible in Attribution
- [ ] Benchmark comparison tab with CDI, IMA-B, IHFA overlay
- [ ] Best/worst 10 trades displayed in two-column layout
- [ ] Monthly returns heatmap shows in Attribution page

### Phase 5 Complete When:
- [ ] Custom stress test form accepts shock parameters
- [ ] "Run Stress Test" returns and displays results
- [ ] Drawdown underwater chart visible below VaR history

### Phase 6 Complete When:
- [ ] `formatPnLShort`, `seededRng`, `formatSize` only defined once (in theme.jsx)
- [ ] All PMS pages import from `window.PMS_THEME`
- [ ] Agent reports fetch in parallel (Promise.all)
- [ ] Position Book equity curve uses real API data when available

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| Removing Dashboard breaks bookmarked URLs | Add redirect routes: `/strategies` → `/pms/morning-pack`, etc. |
| API endpoints return different format than expected | Each page already has sample data fallback; add format normalization |
| CDN outage breaks app | P3 future work: bundle dependencies locally |
| Babel Standalone performance | P3 future work: add esbuild/Vite build step |
| Mobile users | Phase 6.3 adds basic tablet support; full mobile is out of scope |

---

## Files Modified Summary

| Phase | New Files | Modified Files | Deleted Files |
|-------|-----------|---------------|---------------|
| 1 | 0 | 3 (main.py, config.py, components.jsx) + 8 PMS pages | 0 |
| 2 | 1 (PMS SignalsPage.jsx) | 3 (Sidebar.jsx, App.jsx, dashboard.html) + 2 (Attribution, RiskMonitor) | 5 (Dashboard pages) |
| 3 | 0 | 1 (TradeBlotterPage.jsx) | 0 |
| 4 | 0 | 1 (PerformanceAttributionPage.jsx) | 0 |
| 5 | 0 | 1 (RiskMonitorPage.jsx) | 0 |
| 6 | 0 | 6 (theme.jsx + 5 PMS pages) | 0 |
| **Total** | **1** | **~20** | **5** |
