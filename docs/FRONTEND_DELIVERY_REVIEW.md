# Frontend Delivery Review: Macro Trading System
**Date:** 2026-02-27
**Reviewer:** Claude Opus 4.6
**URL:** http://157.230.187.3:8000/dashboard
**Branch:** claude/review-frontend-delivery-25Qwe

---

## 1. Executive Summary

The frontend delivery consists of **two distinct interfaces** sharing a single SPA (Single Page Application):

| Mode | Pages | LOC | Design Language |
|------|-------|-----|-----------------|
| **Dashboard** (Phase 1-2) | 5 pages | ~1,484 | Tailwind CSS dark theme |
| **PMS** (Phase 3) | 8 pages | ~6,577 | Custom Bloomberg-dense design system |

**Total:** 13 pages, ~8,061 LOC of React JSX, served from a single `dashboard.html` entry point.

### Verdict: PMS Should Be the Only Interface

The Dashboard mode is a **redundant, lower-quality version** of what the PMS already delivers. The PMS covers every Dashboard function with significantly more depth, better design consistency, and operational workflows. The Dashboard should be removed entirely.

---

## 2. Production Access Issue (CRITICAL)

The server at `157.230.187.3:8000` returns **"Host not allowed"** (HTTP 403) for all external requests. This is likely caused by:

1. **Uvicorn `--host` binding** combined with a reverse proxy or firewall rule
2. **No `TrustedHostMiddleware`** is configured in `src/api/main.py`
3. The CORS configuration only allows `localhost:3000` and `localhost:8000` in non-debug mode

**Impact:** The frontend is only accessible from within the server itself or via SSH tunnel. No external user can view the dashboard.

**Fix Required:**
- Add `157.230.187.3` to `_allowed_origins` in `src/api/main.py`
- Or set `settings.debug = True` for the production environment (not recommended)
- Or properly configure a reverse proxy (nginx) with correct `Host` header forwarding

---

## 3. Architecture Review

### 3.1 Tech Stack Assessment

| Component | Choice | Assessment |
|-----------|--------|------------|
| React 18 | CDN (unpkg) | **Acceptable** for MVP, but fragile for production. CDN outage = dead app |
| Babel Standalone | Browser-side JSX transpilation | **Red flag.** Every page load re-transpiles JSX. Performance hit, no minification, no tree-shaking |
| Tailwind CSS | CDN | **Acceptable** for Dashboard but conflicts with PMS inline styles |
| Recharts | CDN | **Good.** Solid charting library for financial data |
| React Router | HashRouter via CDN | **Acceptable.** HashRouter is correct for static file serving |
| Font | JetBrains Mono (Google Fonts) | **Excellent.** Perfect for Bloomberg-dense financial UI |

### 3.2 Module System

All components use `window.*` globals for cross-file communication (e.g., `window.StrategiesPage`, `window.PMS_THEME`). This is a **significant architectural weakness:**

- No module isolation or encapsulation
- Risk of name collisions across 13+ JSX files
- No dependency tree, no dead code elimination
- Load order in `dashboard.html` is fragile (scripts must be in exact order)

**Recommendation:** Migrate to Vite + ES modules for production. This would eliminate Babel Standalone, enable minification, tree-shaking, and proper imports.

### 3.3 Data Fetching

| Feature | Implementation | Assessment |
|---------|---------------|------------|
| REST polling | `useFetch()` with 30s interval | **Good.** Clean implementation with loading/error states |
| WebSocket | `useWebSocket()` with exponential backoff | **Good.** Robust reconnection logic |
| Fallback data | Every PMS page has `SAMPLE_*` constants | **Mixed.** Good for demo, but sample data should be clearly labeled in the UI |

---

## 4. Dashboard Mode (5 Pages) — Detailed Review

### 4.1 Strategies Page (`StrategiesPage.jsx`, 258 LOC)

**What it does:**
- Table of 24 strategies with ID, asset class, signal direction, Sharpe ratio, max drawdown
- Asset class filter tabs (All, FX, Rates, Inflation, Cupom, Sovereign, Cross-Asset)
- Expandable rows with backtest metrics grid (7 metrics) and equity curve chart

**Visual/Aesthetic:**
- Clean dark table with gray-800 borders
- Color-coded signals (green LONG, red SHORT, gray NEUTRAL)
- Asset class badges in gray-700 pills
- Skeleton loading state (pulsing gray rows)

**Functional Issues:**
- Backtest detail panel makes separate API call per strategy (could be slow with 24 strategies)
- Expandable row collapse animation is instant (no transition)
- Filter state resets `expandedId` correctly
- Strategy count footer is a nice touch

**Rating:** 7/10 — Solid table view, but lacks sorting, search, or column customization

---

### 4.2 Signals Page (`SignalsPage.jsx`, 246 LOC)

**What it does:**
- 30-day signal heatmap (strategies x dates, color = direction, intensity = conviction)
- Signal flip timeline (chronological list of direction changes)
- Consensus summary (LONG/SHORT/NEUTRAL agreement ratios)

**Visual/Aesthetic:**
- Heatmap uses CSS grid with 8px font and vertical date labels — very dense
- Green/red/gray color mapping with conviction-based opacity
- Hover effect scales cells 1.3x with blue border
- Legend at bottom with color swatches

**Functional Issues:**
- Heatmap cells are extremely small (18px min-height) — may be unreadable on lower resolutions
- No click-to-drill-down on heatmap cells
- Signal flip timeline is capped at 50 entries
- Consensus section only shows if API returns `data.consensus` field

**Rating:** 6/10 — Heatmap concept is excellent but readability suffers from extreme density

---

### 4.3 Risk Page (`RiskPage.jsx`, 346 LOC)

**What it does:**
- 3 SVG semi-circular gauge widgets (VaR 95%, VaR 99%, CVaR 95%)
- Stress test horizontal bar chart (Recharts)
- Limits status table with utilization percentages and OK/WARN/BREACH badges
- Concentration pie chart (donut with labels)
- Circuit breaker status bar

**Visual/Aesthetic:**
- Gauges are custom SVG with green/amber/red coloring by severity thresholds
- Stress test bars use red/green for negative/positive P&L
- Limits table is well-structured with color-coded utilization
- Pie chart uses 7-color palette

**Functional Issues:**
- 3-column layout for gauges may break on narrow screens (no responsive fallback)
- Concentration data falls back to hardcoded defaults if API doesn't return positions
- Circuit breaker section only shows conditionally

**Rating:** 7/10 — Good risk overview, but gauges could be more visually polished

---

### 4.4 Portfolio Page (`PortfolioPage.jsx`, 314 LOC)

**What it does:**
- 2x2 grid: Positions table, Equity curve + drawdown, Monthly return heatmap, Strategy attribution
- Positions table with instrument, direction badge, weight, asset class
- ComposedChart with equity line and drawdown area overlay
- Monthly heatmap using inline background colors

**Visual/Aesthetic:**
- Clean 2x2 layout with consistent card styling
- Equity curve uses blue (#3b82f6) with red drawdown area overlay
- Monthly heatmap uses green/red opacity scaling — intuitive
- Attribution bar chart with green/red per strategy

**Functional Issues:**
- **Equity curve uses hardcoded generated data** (`generateEquityCurve()` with seeded PRNG) — not real data
- **Monthly returns are also hardcoded** (`generateMonthlyReturns()`) — not real data
- This means the Portfolio page is essentially **a static mockup**, not a live dashboard
- Positions table has max-height scroll with small viewport (max-h-52)

**Rating:** 5/10 — Visually good but fundamentally **not connected to real data** for 2 of 4 sections

---

### 4.5 Agents Page (`AgentsPage.jsx`, 320 LOC)

**What it does:**
- 5 agent cards in responsive 3-column grid
- Each card: name, emoji icon, signal direction badge, confidence bar, key drivers, risks
- Cross-Asset Agent spans 2 columns with regime badge and LLM narrative blockquote
- Individual agent report fetch (`/api/v1/agents/{id}/latest`)

**Visual/Aesthetic:**
- Emoji icons add visual warmth (chart, bank, stats, dollar, globe)
- Confidence bar with direction-aware coloring (green for LONG, red for SHORT)
- Cross-Asset narrative uses left-bordered italic blockquote — elegant
- Cards have consistent gray-800 background with gray-700 borders

**Functional Issues:**
- Sequential agent report fetching (one by one, not parallel) — slow
- No refresh mechanism beyond 30s polling
- Regime colors are well-mapped (goldilocks=green, reflation=amber, stagflation=red, deflation=blue)

**Rating:** 7/10 — Best Dashboard page. Good card design, good information hierarchy

---

## 5. PMS Mode (8 Pages) — Detailed Review

### 5.1 Design System (`theme.jsx` + `components.jsx`, ~360 LOC)

**Color Palette:**
- Background: `#0d1117` → `#161b22` → `#21262d` → `#30363d` (4-layer depth)
- Text: `#e6edf3` (primary) → `#8b949e` (secondary) → `#484f58` (muted)
- P&L: `#3fb950` (green) / `#f85149` (red) — GitHub's semantic colors
- Agent accents: 5 distinct colors per agent (orange, purple, green, blue, yellow)

**Typography:**
- JetBrains Mono at compact sizes (0.625rem to 1.5rem)
- Dense spacing scale starting at 0.25rem

**Component Library (8 components):**
1. `PMSCard` — Cards with optional left-accent borders (agent color coding)
2. `PMSTable` — Dense tables with alternating row backgrounds and hover states
3. `PMSBadge` — Semantic pills (positive/negative/warning/neutral/info)
4. `PMSGauge` — Horizontal utilization bars with percentage labels
5. `PMSLayout` — Auto-fit CSS grid
6. `PMSMetricCard` — Compact ticker-strip metrics with change arrows
7. `PMSSkeleton` — Loading placeholders with pulse animation
8. `PMSAlertBanner` — Sticky top banner for risk alerts

**Assessment:** **Excellent.** The design system is well-structured, semantic, and consistent. The Bloomberg-dense aesthetic is appropriate for professional trading UI. The 4-layer background hierarchy creates clear visual depth.

**Rating:** 9/10

---

### 5.2 Morning Pack Page (`MorningPackPage.jsx`, 709 LOC)

**What it does:**
1. **Alert Banner** (sticky) — VaR warnings, limit breaches, merged from risk + briefing endpoints
2. **Market Overview Ticker Strip** — Horizontal scrollable with 12 market tickers (DI1F26, IBOV, USD/BRL, VIX, etc.)
3. **Agent Intelligence Grid** — 5 agent cards with signal badges, confidence scores, key metrics, rationale
4. **Trade Proposals** — Grouped by agent, with approve/reject workflow, conviction scores, expected P&L

**Visual/Aesthetic:**
- Ticker strip uses `PMSMetricCard` components with up/down arrows and P&L coloring
- Agent cards use accent-colored left borders per agent
- Trade proposal cards use tertiary background with inline approve/reject buttons
- "Quick Approve" button appears only for high-confidence (>70%) proposals — smart UX

**Functional Issues:**
- Approve/reject actions call real API endpoints with proper error handling
- Falls back to sample data gracefully when API unavailable
- Alert banner is dismissible per-alert
- Date and time are displayed in header

**Planned vs Delivered:**
| Feature | Planned | Delivered |
|---------|---------|-----------|
| Alert banner | Yes | Yes |
| Market snapshot tickers | Yes (macro indicators) | Yes (12 tickers) |
| Agent intelligence cards | Yes (5 agents) | Yes (5 agents with accent colors) |
| Trade proposals with approval | Yes (approve/reject/modify) | Partially (approve/reject, no modify) |
| LLM-generated narrative | Yes | Falls back to sample data |

**Rating:** 8/10 — Comprehensive morning briefing. Missing "modify" workflow on proposals.

---

### 5.3 Position Book Page (`PositionBookPage.jsx`, 1,041 LOC)

**What it does:**
1. **P&L Summary Cards** — 5 horizontal cards: Today P&L, MTD, YTD, Unrealized P&L, AUM/Leverage
2. **Equity Curve Chart** — ComposedChart with cumulative P&L (blue line), CDI benchmark (dashed gray), drawdown overlay (red area), time range buttons (1M/3M/6M/YTD/1Y/All)
3. **Positions Table** — Collapsible asset class groups (6 classes), 11 columns including DV01/Delta, VaR contribution, daily P&L, holding days. Expandable detail rows with strategy IDs, target/stop levels, sparkline P&L trend
4. **Close Position Dialog** — Modal with price input, notes textarea, confirm/cancel buttons

**Visual/Aesthetic:**
- P&L cards use semantic green/red coloring with abbreviated notation ("+245K", "+1.8M")
- Equity curve has professional range selector buttons with active state styling
- Position table has collapsible groups with arrow indicators and subtotals
- Detail rows show SVG sparklines for P&L trend — excellent information density
- Close dialog has proper modal overlay with dark backdrop

**Functional Issues:**
- Equity curve falls back to seeded PRNG generated data (252 points) — not real
- CDI benchmark line is mathematically generated (13.75% annual)
- Close position calls real API endpoint with fallback behavior
- Group collapse/expand uses Set state management — correct
- Position count and timestamp in header

**Planned vs Delivered:**
| Feature | Planned | Delivered |
|---------|---------|-----------|
| P&L summary cards (Today/MTD/YTD) | Yes | Yes |
| Equity curve with CDI benchmark | Yes | Yes (sample data fallback) |
| Position table with grouping | Yes (by asset class) | Yes (6 classes, collapsible) |
| Expandable detail rows | Yes (DV01, delta, strategies) | Yes (+ sparklines, target/stop) |
| Close position dialog | Yes | Yes (modal with price + notes) |
| Time range selector | Yes | Yes (1M/3M/6M/YTD/1Y/All) |

**Rating:** 9/10 — Most complete PMS page. Bloomberg PORT-quality position viewer.

---

### 5.4 Trade Blotter Page (`TradeBlotterPage.jsx`, 1,178 LOC)

**What it does:**
1. **Two-tab Interface** — "Pending Proposals" and "History"
2. **Pending Tab** — Proposal cards with instrument, direction badge, conviction, rationale, risk impact panel (VaR before/after, concentration impact, correlated positions), approve/reject inline flow
3. **History Tab** — Filterable table with status badges (APPROVED/EXECUTED/REJECTED/EXPIRED), date range picker, pagination

**Visual/Aesthetic:**
- Tab switcher with active blue underline
- Proposal cards with expand/collapse for risk detail
- Risk impact panel shows VaR delta, concentration %, correlated positions
- Status badges use semantic colors (green=APPROVED, blue=EXECUTED, red=REJECTED, gray=EXPIRED)
- History table has zebra striping and hover states

**Functional Issues:**
- Approve flow calls API with execution price and notes
- Reject flow uses `window.prompt()` for reason — **should be a proper modal** (UX issue)
- History supports status filtering and date range (not date picker, just presets)
- Pagination controls at bottom
- Sample data has 6 pending + 15 history entries for demo

**Rating:** 8/10 — Strong approval workflow. The `window.prompt()` for rejection is a UX regression.

---

### 5.5 Risk Monitor Page (`RiskMonitorPage.jsx`, 974 LOC)

**What it does:**
1. **Alert Summary Bar** — Breach/warning counts with color-coded badges
2. **4-Quadrant Grid:**
   - Top-Left: 4 VaR gauges (Parametric 95/99%, Monte Carlo 95/99%) as SVG semi-circular arcs
   - Top-Right: Stress test horizontal bar chart (6 scenarios)
   - Bottom-Left: Limit utilization bars with click-to-expand detail
   - Bottom-Right: Concentration pie chart (asset class allocation)
3. **Historical VaR Chart** — Time-series with trailing window selector

**Visual/Aesthetic:**
- SVG gauges with green/amber/red threshold coloring
- Stress scenarios sorted by severity (most negative first)
- Limit bars use `PMSGauge` component with semantic coloring
- Concentration donut uses 6-color agent palette

**Planned vs Delivered:**
| Feature | Planned | Delivered |
|---------|---------|-----------|
| VaR gauges (4 methods) | Yes | Yes |
| Stress test chart | Yes | Yes |
| Limit utilization bars | Yes (click-to-expand) | Yes |
| Concentration pie | Yes | Yes |
| Historical VaR chart | Yes (time-series) | Yes |
| Alert summary bar | Yes | Yes |

**Rating:** 8/10 — Comprehensive risk dashboard matching Bloomberg PORT Risk.

---

### 5.6 Performance Attribution Page (`PerformanceAttributionPage.jsx`, 920 LOC)

**What it does:**
1. **Period Selector** — Daily/MTD/QTD/YTD/Custom
2. **Dimension Switcher** — By Strategy / By Asset Class / By Instrument (tabbed)
3. **Waterfall Chart** — Floating-bar P&L contribution chart
4. **Attribution Table** — Dense data with inline magnitude bars
5. **Time Series Decomposition** — Daily P&L bars + cumulative P&L line

**Rating:** 8/10 — Multi-dimensional attribution matching institutional-grade tools.

---

### 5.7 Decision Journal Page (`DecisionJournalPage.jsx`, 725 LOC)

**What it does:**
- Vertical timeline of all trading decisions (OPEN, CLOSE, REJECT, NOTE)
- Expandable detail cards with full context
- Filter bar (type, asset class, date range presets)
- Outcome tracking (record P&L outcome post-close)
- Decision analysis stats

**Rating:** 7/10 — Good audit trail. Could benefit from search and better date range controls.

---

### 5.8 Agent Intelligence Page (`AgentIntelPage.jsx`, 451 LOC)

**What it does:**
- 5 agent cards with sparkline confidence history (30 data points)
- Direction indicators with semantic coloring
- Key drivers and risk factors listed per agent
- Cross-Asset agent has LLM narrative section

**Rating:** 7/10 — Clean agent overview with sparklines. Lighter than Morning Pack agent section.

---

### 5.9 Compliance Audit Page (`ComplianceAuditPage.jsx`, 579 LOC)

**What it does:**
- Audit trail log viewer with SHA-256 hash integrity verification (Web Crypto API)
- CSV/JSON export buttons
- Compliance-focused filtering (type, date range)
- Hash verification status per entry (green checkmark or red warning)

**Rating:** 7/10 — Unique compliance feature with cryptographic integrity checks. Good for regulatory requirements.

---

## 6. Dashboard vs PMS: Functional Overlap Analysis

### Direct Overlap Map

| Function | Dashboard Page | PMS Page | PMS Advantage |
|----------|---------------|----------|---------------|
| Strategy performance | Strategies | (Morning Pack + Attribution) | PMS has multi-dimensional attribution, waterfall charts |
| Signal monitoring | Signals | Morning Pack + Agent Intel | PMS has agent intelligence cards with actionable proposals |
| Risk overview | Risk | Risk Monitor | PMS has 4 VaR methods, historical VaR chart, pre-trade risk |
| Portfolio positions | Portfolio | Position Book | PMS has P&L summary, equity curve with CDI, close dialog, DV01/delta |
| Agent views | Agents | Agent Intel + Morning Pack | PMS has sparklines, cross-asset narrative, trade proposals |

### What Dashboard Has That PMS Doesn't

| Feature | Dashboard Exclusive? |
|---------|---------------------|
| Signal heatmap (30-day grid) | Yes, but it's a niche visualization |
| Asset class filter tabs on strategies | Yes, but PMS attribution does this better |
| Backtest expansion per strategy | Yes, but this belongs in a Backtesting module |

### What PMS Has That Dashboard Doesn't

| Feature | PMS Exclusive |
|---------|---------------|
| Morning Pack (daily briefing) | Yes |
| Trade approval workflow | Yes |
| Close position dialog | Yes |
| Decision journal (audit trail) | Yes |
| Compliance audit with SHA-256 | Yes |
| P&L summary cards (Today/MTD/YTD) | Yes |
| CDI benchmark on equity curve | Yes |
| Time range selectors | Yes |
| Collapsible asset class groups | Yes |
| Agent accent colors & sparklines | Yes |
| Alert banner (sticky) | Yes |
| Period/dimension switching for attribution | Yes |

---

## 7. Recommendation: Remove Dashboard, Keep Only PMS

### Reasons to Remove Dashboard

1. **90% functional overlap** — Every Dashboard page has a superior PMS equivalent
2. **Design inconsistency** — Dashboard uses Tailwind utility classes; PMS uses a structured design system with semantic tokens. Having both creates visual confusion when switching modes
3. **Sample data problem** — Dashboard's Portfolio page generates fake data via PRNG. PMS at least falls back to well-structured sample data that labels itself
4. **No operational value** — Dashboard is view-only. PMS enables action (approve/reject trades, close positions, log decisions)
5. **Maintenance burden** — 1,484 LOC of Dashboard code that duplicates PMS functionality
6. **User confusion** — The mode switch (Dashboard/PMS toggle) forces users to understand when to use which mode. There's no clear distinction

### What to Migrate from Dashboard to PMS

1. **Signal Heatmap** — The 30-day signal heatmap from `SignalsPage.jsx` is unique and useful. Add it as a section within the Morning Pack page or create a dedicated "Signals" tab in PMS
2. **Backtest Detail** — The expandable backtest metrics from `StrategiesPage.jsx` are useful. Integrate them into the Performance Attribution page as a "Strategy Backtest" tab
3. **Circuit Breaker Status** — The circuit breaker bar from `RiskPage.jsx` should be added to the PMS Risk Monitor page

### After Removal

The PMS sidebar would have **9 tabs** (adding Signals):

```
Morning Pack
Position Book
Trade Blotter
Signals (migrated from Dashboard)
Risk Monitor
Attribution
Decision Journal
Agent Intel
Compliance
```

---

## 8. Visual & Aesthetic Assessment

### Color Consistency

| Aspect | Dashboard | PMS | Winner |
|--------|-----------|-----|--------|
| Background | `#0a0a0f` (Tailwind gray-950) | `#0d1117` (GitHub dark) | PMS — slightly warmer, less harsh |
| Text hierarchy | 2 levels (gray-100, gray-400) | 4 levels (primary, secondary, muted, inverse) | PMS — proper hierarchy |
| P&L colors | `#22c55e` / `#ef4444` (Tailwind) | `#3fb950` / `#f85149` (GitHub semantic) | Tie — both are standard |
| Borders | `gray-800` / `gray-700` Tailwind | `#30363d` / `#21262d` | PMS — more subtle gradation |
| Agent identity | None (emoji icons) | Accent colors per agent | PMS — professional agent branding |

### Typography

| Aspect | Dashboard | PMS | Winner |
|--------|-----------|-----|--------|
| Font family | System sans-serif (Apple, Segoe UI) | JetBrains Mono (monospace) | PMS — appropriate for financial data |
| Size scale | Tailwind defaults (text-sm, text-xs) | Custom compact scale (0.625rem - 1.5rem) | PMS — denser, more information |
| Data formatting | Ad hoc (`.toFixed()`) | Centralized helpers (`formatPnL`, `formatPercent`) | PMS — consistent formatting |

### Layout Density

| Aspect | Dashboard | PMS |
|--------|-----------|-----|
| Spacing | `p-6` content area | `p-4` content area |
| Table padding | `px-4 py-3` | `3px 6px` (compact) to `5px 10px` |
| Card padding | `p-4` | `8px 12px` |
| Information per screen | Medium | High (Bloomberg-dense) |

### Loading States

| Aspect | Dashboard | PMS |
|--------|-----------|-----|
| Skeleton UI | Basic gray pulsing divs | `PMSSkeleton` component with configurable dimensions |
| Error handling | Red banner with message | Same pattern, but more consistent |
| Empty states | "No data" text | "No data available" in muted text |

**Overall Aesthetic Rating:**
- Dashboard: **6/10** — Clean but generic. Looks like any Tailwind dark theme admin panel
- PMS: **8.5/10** — Professional, information-dense, purpose-built for trading. Distinctive Bloomberg-inspired identity

---

## 9. Technical Issues Found

### 9.1 Critical

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | **Server returns 403 "Host not allowed"** for external requests | Production server config | No external user can access the frontend |
| 2 | **CORS only allows localhost** in non-debug mode | `src/api/main.py:117-119` | API calls fail from external browsers |
| 3 | **Babel Standalone in production** — browser-side JSX transpilation | `dashboard.html:16` | Performance penalty, no minification, ~500KB unnecessary JS |

### 9.2 High

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 4 | **Portfolio page uses fake generated data** (not API) | `PortfolioPage.jsx:48-95` | Equity curve and monthly returns are hardcoded mockups |
| 5 | **Variable name collisions** across JSX files | Multiple files redefine `_C`, `_T`, `_S` | Works due to Babel scope, but fragile |
| 6 | **CDN dependency chain** — 10 external CDN scripts | `dashboard.html:12-29` | Single CDN failure breaks entire app |
| 7 | **No build step** — no minification, no tree-shaking | Architecture | ~8K LOC served raw to browser |

### 9.3 Medium

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 8 | **window.prompt() for rejection reason** | `TradeBlotterPage.jsx` | Poor UX, should be proper modal |
| 9 | **Sequential agent report fetching** | `AgentsPage.jsx:226-248` | Slow — should use `Promise.all()` |
| 10 | **Heatmap cells too small** (18px) | `SignalsPage.jsx:159` | Unreadable on standard displays |
| 11 | **No responsive breakpoints in PMS** | PMS pages use inline styles | PMS is desktop-only, breaks on tablet |
| 12 | **Sample data not labeled as sample** | All PMS pages | Users may think sample data is real |

### 9.4 Low

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 13 | `DirectionBadge` component defined in 3 files | Signals, Portfolio, Agents pages | Code duplication (should be shared) |
| 14 | `formatPnLShort()` duplicated in 3 PMS files | PositionBook, RiskMonitor, Attribution | Should be in theme.jsx |
| 15 | `seededRng()` duplicated in 4 PMS files | PositionBook, RiskMonitor, Attribution, Agents | Should be a shared utility |

---

## 10. Planned vs Delivered: Compliance Matrix

### Phase 3 PMS Guide (20 Etapas)

| Etapa | Description | Frontend Relevant? | Delivered? |
|-------|-------------|-------------------|------------|
| 1 | Database schemas (5 tables) | Backend | Yes |
| 2-3 | Service layer (Position Manager, Trade Workflow, MTM) | Backend | Yes |
| 4 | API endpoints (20+) | Backend | Yes |
| 5 | Morning Pack service | Backend | Yes |
| 6 | Risk Monitor service | Backend | Yes |
| 7 | Performance Attribution engine | Backend | Yes |
| 8 | PMS Design System + Component Library | Frontend | **Yes** (theme.jsx + components.jsx) |
| 9 | Morning Pack Page | Frontend | **Yes** (709 LOC) |
| 10 | Position Book Page | Frontend | **Yes** (1,041 LOC) |
| 11 | Trade Blotter Page | Frontend | **Yes** (1,178 LOC) |
| 12 | Risk Monitor Page | Frontend | **Yes** (974 LOC) |
| 13 | Performance Attribution Page | Frontend | **Yes** (920 LOC) |
| 14 | Decision Journal + Agent Intel Pages | Frontend | **Yes** (725 + 451 LOC) |
| 15 | Compliance Audit Page (BONUS) | Frontend | **Yes** (579 LOC) — exceeded plan |
| 16-20 | Dagster pipelines, integration tests, E2E | Backend/Ops | Partial |

**Frontend Compliance: 100%** — All 7 planned screens + 1 bonus screen delivered.

### Missing Features (Gaps)

| Feature | Planned | Status |
|---------|---------|--------|
| Modify-and-approve workflow | Etapa 11 | Not implemented (approve/reject only) |
| Ad-hoc stress test (custom scenario input) | Etapa 12 | Not implemented (display only) |
| Pre-trade risk analysis panel | Etapa 12 | Not implemented |
| Benchmark comparison (CDI, IMA-B, IHFA) | Etapa 13 | Only CDI benchmark in Position Book |
| Rolling metrics (Sharpe/vol/return windows) | Etapa 13 | Not implemented |
| Best/worst trades view | Etapa 13 | Not implemented |
| LLM-generated macro narrative (live Claude API) | Etapa 5 | Falls back to sample text |

---

## 11. Final Scores

| Category | Dashboard | PMS |
|----------|-----------|-----|
| **Visual Design** | 6/10 | 8.5/10 |
| **Information Density** | 5/10 | 9/10 |
| **Functional Completeness** | 6/10 | 8/10 |
| **Code Quality** | 6/10 | 7/10 |
| **Operational Value** | 3/10 | 9/10 |
| **Design Consistency** | 5/10 | 9/10 |
| **Production Readiness** | 4/10 | 6/10 |
| **Overall** | **5/10** | **8/10** |

---

## 12. Action Items (Priority Order)

### P0 — Must Fix (Production Blocking)

1. **Fix server access** — External requests return 403 "Host not allowed"
2. **Fix CORS for production IP** — Add `http://157.230.187.3:8000` to allowed origins
3. **Label sample/fallback data clearly** — Add "[SAMPLE DATA]" indicator when using fallback

### P1 — Should Fix (Quality)

4. **Remove Dashboard mode entirely** — Merge signal heatmap into PMS
5. **Replace Babel Standalone** — Add a minimal build step (Vite, esbuild, or even simple bundling)
6. **Implement modify-and-approve** workflow in Trade Blotter
7. **Replace `window.prompt()`** with proper rejection modal

### P2 — Nice to Have (Polish)

8. **Consolidate duplicated code** (`formatPnLShort`, `seededRng`, `DirectionBadge`)
9. **Add responsive breakpoints** for tablet viewing
10. **Implement missing Attribution features** (rolling metrics, benchmark comparison, best/worst trades)
11. **Add pre-trade risk analysis** panel to Trade Blotter proposals
12. **Connect Portfolio equity curve** to real API data (replace PRNG generation)
