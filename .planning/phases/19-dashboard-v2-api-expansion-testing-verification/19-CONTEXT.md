# Phase 19 Context: Dashboard v2, API Expansion, Testing & Verification

## Dashboard Architecture

### Build Approach
- **CDN-only** — no build tooling (Vite, CRA, etc.)
- Continue using React 18, Tailwind CSS, Recharts 2, and Babel Standalone via CDN
- ReactRouterDOM loaded via CDN for hash-based routing (`HashRouter`)

### File Structure
- **Split into ~8-10 .jsx files** loaded by a shell HTML file
- `src/api/static/dashboard.html` — shell that loads all script tags
- `src/api/static/js/App.jsx` — Router + layout
- `src/api/static/js/Sidebar.jsx` — Collapsible sidebar navigation
- `src/api/static/js/hooks.jsx` — useFetch, useWebSocket custom hooks
- `src/api/static/js/pages/StrategiesPage.jsx`
- `src/api/static/js/pages/SignalsPage.jsx`
- `src/api/static/js/pages/RiskPage.jsx`
- `src/api/static/js/pages/PortfolioPage.jsx`
- `src/api/static/js/pages/AgentsPage.jsx`

### Charting
- **Recharts only** — no additional charting libraries
- Covers: line (equity curves), bar (stress scenarios), area (VaR bands), pie (concentration), custom cells (heatmap)

### Navigation
- **Collapsible left sidebar** — icons + labels, can collapse to icon-only
- Active page highlighted
- Fixed position, content area fills remaining width
- Collapse toggle at bottom of sidebar

---

## Page Behavior

### Strategies Page
- **Expandable rows** — table with one row per strategy (24+)
- Click row to expand inline: shows equity curve chart, backtest metrics (Ann.Ret, Sharpe, Sortino, MaxDD, Win Rate, Trades, Turnover)
- **Filter by asset class** tabs/buttons: All | FX | Rates | Inflation | Cupom | Sovereign | Cross-Asset
- Columns: Strategy ID, Asset Class, Current Signal, Sharpe, MaxDD

### Signals Page
- **Heatmap** — strategies on Y-axis, time (last 30 days) on X-axis
- Color encodes direction and conviction (green = long, red = short, intensity = conviction strength)
- **Signal flip timeline** below heatmap — chronological list of recent signal changes with direction, conviction
- Asset class grouping on Y-axis

### Risk Page
- **Dense single-view** — all visible without scrolling
- Top row: VaR gauges (95% VaR, 99% VaR, CVaR) — circular or semi-circular gauge widgets
- Left column: Stress test bar chart (6+ scenarios, horizontal bars showing P&L impact)
- Right column: Limits status panel (Leverage, VaR, Drawdown, Concentration — OK/WARN/BREACH)
- Bottom: Concentration pie chart by asset class

### Portfolio Page
- Per roadmap: positions table, equity curve chart, monthly return heatmap, strategy attribution breakdown
- Equity curve = line chart with drawdown overlay
- Monthly heatmap = grid (months x years) with color intensity for returns

### Agents Page
- Per roadmap: cards for each of the 5 agents
- Each card shows: agent name, current signal direction, confidence level, key drivers
- Cross-Asset Agent card includes the LLM narrative (or template fallback)

---

## Data Refresh Strategy

### Polling
- **30-second interval** for all page data via REST API
- All pages auto-refresh when active
- Manual refresh button available as override

### WebSocket (alerts/events only)
- 3 separate WebSocket channels:
  - `ws://host/ws/signals` — signal_update, signal_flip events
  - `ws://host/ws/portfolio` — position_update, rebalance events
  - `ws://host/ws/alerts` — limit_breach, pipeline_status, conviction_surge, var_warning

### WebSocket Architecture
- **Broadcast to all connected clients** — no per-client subscription filtering
- `ConnectionManager` class tracks `active: dict[str, set[WebSocket]]` (channel -> clients)
- `broadcast(channel, message)` sends to all clients on that channel

### Disconnection Handling
- **Auto-reconnect** with exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (cap)
- During disconnection: fall back to 30s polling (same as normal)
- On reconnect: stop polling, resume WebSocket
- **Connection status indicator** visible in UI

### Alert Display
- **Corner toast notifications** stacking in bottom-right
- Auto-dismiss after 10 seconds
- Click toast to navigate to relevant page
- **Sidebar badge count** on Risk item for unread alerts

---

## API Expansion

### Backtest API (new v3 routes)
- `POST /api/v1/backtest/run` — trigger backtest for a strategy
- `GET /api/v1/backtest/results` — retrieve backtest results
- `POST /api/v1/backtest/portfolio` — portfolio-level backtest
- `GET /api/v1/backtest/comparison` — compare strategy backtests side by side

### Strategy Detail API (new v3 routes)
- `GET /api/v1/strategies/{id}` — full strategy detail (params, metadata)
- `GET /api/v1/strategies/{id}/signal/latest` — latest signal for strategy
- `GET /api/v1/strategies/{id}/signal/history` — signal history (for heatmap)
- `PUT /api/v1/strategies/{id}/params` — update strategy parameters

### WebSocket Endpoints
- `ws://host/ws/signals`
- `ws://host/ws/portfolio`
- `ws://host/ws/alerts`

---

## Testing & Verification

### Integration Tests

#### Full Pipeline E2E
- Test chain: DB -> transforms -> agents -> strategies -> signals -> portfolio -> risk -> report
- Uses test database with fixture data (seeded)
- **External APIs mocked**: FRED, BCB, Yahoo -> fixture JSON files; LLM API -> template fallback
- Asserts: each step produces non-empty, valid output
- Located in `tests/integration/`

#### API Endpoint Tests
- Uses `httpx.AsyncClient(app=app)` (FastAPI TestClient)
- Grouped by API version:
  - `test_api_v1.py` — health, macro/dashboard, agents, signals, portfolio/current, portfolio/risk
  - `test_api_v2.py` — risk/var, risk/stress, risk/limits, portfolio/target, portfolio/rebalance-trades, portfolio/attribution, reports/daily
  - `test_api_v3.py` — backtest/run, backtest/results, backtest/portfolio, backtest/comparison, strategies/{id}, strategies/{id}/signal/latest, strategies/{id}/signal/history, ws/signals, ws/portfolio, ws/alerts
- Assertions: status code (200/202), response schema validation, key data field presence
- No real database — dependency injection with mock/fixture data

### CI/CD Pipeline

#### GitHub Actions
- Trigger: `on: [push, pull_request]`
- **Lint job**: ruff check, black --check
- **Test job**:
  - Service containers: `timescale/timescaledb` (5432), `redis:7` (6379)
  - `pytest tests/unit/`
  - `pytest tests/integration/`
- **PR gate**: all jobs must pass before merge
- Config: `.github/workflows/ci.yml`

### Verification Script

#### `scripts/verify_phase2.py`
- Comprehensive component checklist for all v3.0 features
- Checks (at minimum):
  1. 24+ strategies registered in StrategyRegistry
  2. 5 agents produce valid reports
  3. Signal aggregation works (3 methods: confidence-weighted, rank-based, Bayesian)
  4. Monte Carlo VaR computes
  5. 6+ stress scenarios run
  6. Black-Litterman optimizer produces weights
  7. Dagster has 22 asset definitions
  8. 4 Grafana dashboard JSONs exist
  9. 10 alert rules configured
  10. Dashboard HTML serves (200 OK)
  11. All API endpoints respond (v1 + v2 + v3)
  12. 3 WebSocket channels accept connections
- Output: formatted table with PASS/FAIL per component
- Exit code: 0 if all pass, 1 if any fail

---

## Deferred Ideas

None surfaced during discussion.

---

## Decisions Summary

| Area | Decision | Rationale |
|------|----------|-----------|
| Build tooling | CDN-only (no Vite/CRA) | Consistency with existing approach, no Node.js build dependency |
| File structure | Split ~8-10 .jsx files | Manageable file sizes (~150-300 lines each), clear separation |
| Charting | Recharts only | Already in use, covers all chart types needed |
| Navigation | Collapsible sidebar | Professional look, maximizes chart space when collapsed |
| Strategies page | Expandable rows | Data-dense, no navigation away from list, inline detail |
| Signals page | Heatmap + flip timeline | Shows both current state and historical pattern |
| Risk page | Dense single-view | All risk metrics visible without scrolling |
| Data refresh | 30s polling + WS for alerts | Batch-oriented system doesn't need sub-second updates |
| WebSocket channels | 3 separate (signals, portfolio, alerts) | Clean separation of concerns per domain |
| WS architecture | Broadcast to all | Simple, no per-client state management |
| WS failure | Auto-reconnect + poll fallback | Never lose data visibility |
| Alert display | Corner toasts + sidebar badge | Non-intrusive, actionable (click to navigate) |
| E2E test scope | Full pipeline with mocked externals | Validates data flow across all layers |
| API tests | TestClient + schema validation | Catches both connectivity and data correctness issues |
| CI/CD | GitHub Actions + service containers | Automated, gates PR merges on all tests passing |
| Verification | Comprehensive component checklist | Validates all v3.0 features with formatted pass/fail output |
