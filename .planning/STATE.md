# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system
**Current focus:** Phase 27 in progress -- Redis Cache, Dagster PMS, Go-Live Verification

## Current Position

Phase: 27 of 27 (Redis Cache, Dagster PMS, Go-Live Verification)
Plan: 2 of 4 in current phase (27-02 Dagster PMS Pipeline complete)
Status: Phase 27 in progress
Last activity: 2026-02-26 — Completed 27-02 Dagster PMS Pipeline

Progress: [##############################] 97% (27/27 phases, plan 2/4)

## Performance Metrics

**Velocity (from v1.0 + v2.0):**
- Total plans completed: 22
- Average duration: 9.8 min
- Total execution time: 3.24 hours

**v3.0 Estimate (22 plans):**
- Estimated at ~9.8 min/plan: ~3.6 hours total

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 07-13 (v2.0) | 20 | 3.0 hrs | 9 min |
| 14-19 (v3.0) | 22 | TBD | TBD |

*Updated after each plan completion*
| Phase 14 P01 | 7min | 3 tasks | 11 files |
| Phase 14 P02 | 6min | 2 tasks | 4 files |
| Phase 14 P03 | 7min | 2 tasks | 3 files |
| Phase 15 P01 | 9min | 2 tasks | 6 files |
| Phase 15 P02 | 14min | 2 tasks | 6 files |
| Phase 15 P03 | 7min | 2 tasks | 4 files |
| Phase 15 P04 | 14min | 2 tasks | 7 files |
| Phase 15 P05 | 4min | 2 tasks | 2 files |
| Phase 16 P01 | 10min | 2 tasks | 9 files |
| Phase 16 P02 | 8min | 2 tasks | 9 files |
| Phase 16 P03 | 7min | 2 tasks | 7 files |
| Phase 17 P01 | 8min | 2 tasks | 4 files |
| Phase 17 P02 | 6min | 2 tasks | 5 files |
| Phase 17 P03 | 6min | 2 tasks | 5 files |
| Phase 17 P04 | 7min | 2 tasks | 9 files |
| Phase 18 P01 | 7min | 2 tasks | 8 files |
| Phase 18 P03 | 5min | 2 tasks | 7 files |
| Phase 18 P02 | 5min | 2 tasks | 5 files |
| Phase 18 P04 | 8min | 2 tasks | 10 files |
| Phase 19 P01 | 5min | 2 tasks | 6 files |
| Phase 19 P03 | 5min | 2 tasks | 4 files |
| Phase 19 P04 | 10min | 2 tasks | 6 files |
| Phase 19 P02 | 6min | 2 tasks | 6 files |
| Phase 20 P01 | 4min | 2 tasks | 4 files |
| Phase 20 P02 | 11min | 2 tasks | 6 files |
| Phase 21 P01 | 5min | 2 tasks | 3 files |
| Phase 21 P02 | 3min | 1 tasks | 4 files |
| Phase 21 P03 | 4min | 2 tasks | 3 files |
| Phase 22 P02 | 6min | 1 tasks | 4 files |
| Phase 22 P03 | 6min | 2 tasks | 7 files |
| Phase 22 P01 | 9min | 2 tasks | 4 files |
| Phase 23 P01 | 4min | 2 tasks | 5 files |
| Phase 23 P02 | 5min | 2 tasks | 3 files |
| Phase 24 P01 | 5min | 2 tasks | 3 files |
| Phase 24 P02 | 5min | 2 tasks | 3 files |
| Phase 25 P01 | 4min | 1 tasks | 1 files |
| Phase 25 P02 | 5min | 2 tasks | 3 files |
| Phase 27 P02 | 3min | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.0]: 8 strategies in flat files with ALL_STRATEGIES dict registry -- being replaced by StrategyRegistry
- [v2.0]: CDN-only dashboard (React 18 + Tailwind + Recharts + Babel) -- being enhanced to multi-page React app
- [v3.0]: Enhance not replace -- build on existing v2.0 code
- [v3.0]: Coexisting strategies -- new FX-02 etc. alongside existing FX_BR_01 etc.
- [v3.0]: Dagster over custom pipeline -- scheduling, retry, monitoring UI
- [14-01]: Auto-register existing 8 strategies in StrategyRegistry via __init__.py for backward compat
- [14-01]: Extract asset_class metadata from module-level StrategyConfig constants for registry filtering
- [14-01]: Add backtest_results v2 columns as nullable to preserve existing data
- [14-02]: Portfolio equity = weighted sum of individual strategy equity curves, aligned to common DatetimeIndex
- [14-02]: Walk-forward overfit ratio = mean OOS Sharpe / mean IS Sharpe, < 0.5 warns
- [14-02]: TransactionCostModel uses instance-level default_bps for customizable fallback cost
- [14-03]: deflated_sharpe uses Euler-Mascheroni approximation for expected max SR from i.i.d. trials
- [14-03]: generate_tearsheet uses 63-day rolling window for quarterly rolling Sharpe
- [14-03]: All analytics functions use ddof=0 for std to handle small samples gracefully
- [15-01]: FX-02 vol-adjusted sizing: min(1.0, target_vol/realized_vol) * base_size
- [15-01]: FX-03 contrarian threshold at |z|>2.0 inverts signal direction for extreme positioning
- [15-01]: FX-04 implied vol proxy from mean absolute deviation when no direct IV series
- [15-01]: FX-05 commodity weights: soy 30%, iron 25%, oil 20%, sugar 15%, coffee 10%
- [15-01]: Updated __init__.py to import new strategies for automatic StrategyRegistry population
- [15-03]: INF-02 uses IPCA-15 as primary model forecast with seasonal average fallback
- [15-03]: INF-03 composite z-score: average of 3 z-scores vs BCB target, IPCA 12M, Focus
- [15-03]: CUPOM-02 uses DI - UST as CIP basis proxy for onshore-offshore spread
- [15-02]: RATES-03 uses 2Y as primary signal with 5Y confirmation boost
- [15-02]: RATES-05/06 use hardcoded FOMC/COPOM date lists for event window detection
- [15-02]: BCB reaction function: IPCA vs 4.5%/3.0% bands -> hike/cut/neutral at 25bps
- [15-02]: Taylor Rule: r_star=2.5 + CPI + 0.5*(CPI-2.0) + 0.5*output_gap_proxy
- [15-02]: Market pricing only for expectation baselines (DI1 for COPOM, UST for FOMC)
- [15-04]: SOV-02 OLS via Gaussian elimination (no numpy) for 6-variable cross-section across 10 EM peers
- [15-04]: CROSS-01 rule-based regime (Goldilocks/Reflation/Stagflation/Deflation); Phase 16 adds HMM
- [15-04]: CROSS-02 uses only market indicators (VIX, CDS, vol, corr, funding, momentum) -- no flow/positioning
- [15-04]: Regime modulates sizing (0.5x multiplier), never hard-suppresses (locked decision)
- [15-05]: Duck-typing detection (hasattr) for signal adapter instead of strict isinstance
- [15-05]: Multiple signals targeting same instrument have weights summed, not overwritten
- [15-05]: Portfolio-level trade count uses individual strategy aggregation
- [16-01]: HMM features mapped from CrossAssetFeatureEngine z-scores to 6-column DataFrame
- [16-01]: Rule-based fallback assigns 0.7 to classified regime, 0.1 to each other
- [16-01]: Tail risk composite = 30% VIX_z + 30% credit_z + 40% regime_transition_prob
- [16-01]: CrossAssetView narrative generated inline (template) in agent, LLM path in NarrativeGenerator
- [16-02]: ScrapedDocument dataclass shared between COPOM and FOMC scrapers for uniform output
- [16-02]: HTML extraction via stdlib html.parser (no BeautifulSoup dependency)
- [16-02]: Cache files named {source}_{doc_type}_{YYYY-MM-DD}.json for deterministic lookup
- [16-02]: Sync httpx.Client (not async) for scraper simplicity -- async not needed for batch scraping
- [16-03]: Dictionary-based scoring as primary method with 0.7 dict + 0.3 LLM blend when API key available
- [16-03]: Change score thresholds: |delta| > 0.3 = major shift, > 0.1 = minor shift, else neutral
- [16-03]: NLPProcessor batch processing sorts by date ascending for sequential change detection
- [16-03]: Term weights in [0.0, 1.0] range with higher values for stronger hawk/dove signals
- [17-01]: Bayesian default method with flat prior when no regime context available
- [17-01]: Regime tilts shift WHICH strategies to trust, not overall conviction level
- [17-01]: Crowding penalty is gentle 20% reduction at >80% agreement threshold
- [17-01]: Staleness linear decay over 5 business days (weekday-only counting)
- [17-01]: Signal flip = any sign change; conviction surge = absolute >0.3; divergence = >0.5 within asset class
- [17-02]: Component VaR tolerance 2% vs total parametric VaR (Ledoit-Wolf shrinkage vs sample variance)
- [17-02]: Default lookback updated 252->756 days (3-year window) for both min_historical_obs and Monte Carlo
- [17-02]: Historical replay reports worst cumulative drawdown point, not final-day P&L
- [17-02]: Reverse stress binary search [0.01, 5.0x] with feasibility flag for unexposed scenarios
- [17-03]: Daily/weekly loss breach uses absolute value comparison against positive limit thresholds
- [17-03]: Risk budget can_add_risk threshold at 5% headroom (available > 0.05)
- [17-03]: check_all_v2 overall_status has three levels: OK, WARNING (>80%), BREACHED
- [17-03]: API endpoints use deterministic sample data (seed=42) for consistent testing
- [17-04]: size_portfolio uses raw unclamped sizing then applies conviction-based limit (soft override at >0.8)
- [17-04]: Rebalance dual-threshold: signal_change > 0.15 OR max position drift > 0.05
- [17-04]: portfolio_state hypertable compressed after 30 days with instrument segmentby
- [17-04]: Portfolio API endpoints use sample data for demo; live integration deferred
- [18-01]: Removed from __future__ import annotations from Dagster asset modules -- incompatible with Dagster runtime type introspection
- [18-01]: Silver assets use ImportError fallback for transform modules -- graceful degradation
- [18-01]: Agent assets use _ensure_agents_registered() lazy pattern to avoid circular imports
- [18-01]: Docker dagster profile keeps dagster-webserver opt-in, not started by default
- [18-03]: Grafana under 'monitoring' Docker profile so it does not start with default docker compose up
- [18-03]: Datasource UID 'timescaledb' referenced directly in all dashboard panels for consistent provisioning
- [18-03]: All 4 dashboards auto-refresh every 15 minutes per user decision
- [18-03]: Pipeline health as default home dashboard via GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH
- [18-02]: All downstream assets use same RetryPolicy and DailyPartitionsDefinition as upstream layers
- [18-02]: Bronze-only ingest job enables selective data refresh without full pipeline run
- [18-04]: All alerts dispatch to both Slack and email per user decision
- [18-04]: 30-minute cooldown per alert type prevents notification flooding
- [18-04]: DailyReportGenerator uses sample data when no pipeline context for standalone demos
- [18-04]: HTML report uses inline CSS for email compatibility
- [18-04]: Slack gets condensed summary with link to full report, not inline
- [19-01]: Placeholder page components defined inline in dashboard.html, replaced by .jsx files in 19-02
- [19-01]: ReactRouterDOM loaded from unpkg CDN, consistent with CDN-only approach
- [19-01]: StaticFiles mount at /static in main.py after all router includes
- [19-01]: WebSocket URL built from window.location for protocol-agnostic ws/wss support
- [19-03]: Backtest endpoints use asyncio.to_thread() for CPU-bound BacktestEngine.run() calls
- [19-03]: All API endpoints gracefully fallback to sample/placeholder data when DB or engine unavailable
- [19-03]: ConnectionManager uses module-level singleton pattern for cross-module broadcast access
- [19-03]: WebSocket routes mounted at root (no /api/v1 prefix) for ws:// protocol compatibility
- [19-03]: Signal history endpoint uses seeded random for deterministic sample data per strategy_id
- [19-04]: Noop lifespan pattern with starlette TestClient for DB-independent API integration testing
- [19-04]: AgentRegistry verified via EXECUTION_ORDER (static), not runtime registry (requires manual registration)
- [19-04]: CI/CD lint job must pass before test job runs (needs: lint dependency)
- [19-02]: SVG-based GaugeChart component for VaR/CVaR semi-circular gauges (no external gauge library)
- [19-02]: CSS grid with inline backgroundColor for heatmap cells (Recharts has no native heatmap)
- [19-02]: ComposedChart with dual Y-axes for equity curve + drawdown overlay in PortfolioPage
- [19-02]: Per-agent sequential fetch for latest reports (not parallel) to avoid server overload
- [19-02]: Seeded PRNG for sample equity curve and monthly returns for deterministic demo data
- [Phase 20]: Models follow Mapped[] type hints pattern consistent with existing portfolio_state.py
- [Phase 20]: PositionPnLHistory uses 90-day chunk interval with 60-day compression policy
- [Phase 20]: DecisionJournal immutability enforced at DB level via PostgreSQL trigger on is_locked=TRUE rows
- [Phase 20]: No FK from position_pnl_history to portfolio_positions for hypertable compatibility
- [20-02]: Dict-based positions decoupled from ORM -- caller handles session management and persistence
- [20-02]: Direct file-level import of TransactionCostModel via importlib.util to avoid backtesting.__init__ chain
- [20-02]: Simplified VaR contribution via notional-proportional allocation (full Component VaR deferred to Phase 22)
- [20-02]: CDS spread returned as-is for price (spread-quoted instrument); P&L from spread changes
- [21-01]: In-memory _proposals list (same pattern as PositionManager._positions) for decoupled dict-based storage
- [21-01]: Template-based rationale as primary, LLM (Claude API) as optional enhancement with full fallback
- [21-01]: Flip detection at conviction >= 0.60 against opposite open position on same instrument
- [21-01]: Conviction min 0.55, max 5 proposals per call, sorted by conviction descending
- [21-01]: REJECT journal entries created directly with content_hash for immutability
- [Phase 21]: Duplicate lazy singleton pattern in pms_trades.py per plan spec (not shared import)
- [21-03]: Journal stats/decision-analysis endpoint placed before /{entry_id} to avoid FastAPI path conflict
- [21-03]: Test fixture injects shared TradeWorkflowService across all 3 router module singletons for state coherence
- [22-01]: Action-first ordering: action_items and trade_proposals appear before context sections in briefing
- [22-01]: Template-based narrative as primary fallback; LLM (Claude API) as optional enhancement
- [22-01]: Factor attribution splits P&L equally across factors when a position maps to multiple factors
- [22-01]: Sub-period buckets: weekly if range <= 90 days, monthly if > 90 days
- [22-01]: Additive attribution: each dimension independently sums to total_pnl_brl
- [22-02]: Two-tier alerts: WARNING at 80% utilization, BREACH at 100% for all limit types
- [22-02]: RiskMonitorService graceful degradation: each optional component (VaRCalculator, StressTester, RiskLimitsManager) can be None
- [22-02]: Parametric VaR from P&L history (>=20 obs); MC VaR requires >=30 obs and VaRCalculator
- [22-02]: Drawdown computed from cumulative daily P&L via HWM method against AUM
- [22-03]: Route ordering: /history before /{briefing_date} to avoid FastAPI path parameter conflict
- [22-03]: Lazy singleton per router module (same pattern as pms_trades.py and pms_journal.py)
- [22-03]: Attribution date serialization: convert date objects to ISO strings for JSON response compatibility
- [23-01]: PMS components use inline styles referencing PMS_COLORS (not Tailwind color classes) for Bloomberg-dense dark theme consistency
- [23-01]: AppContent inner component pattern enables useNavigate hook inside HashRouter context
- [23-01]: MorningPackPage resolved lazily from window.MorningPackPage with fallback to PMSPlaceholder
- [23-01]: Alert badge shown on Risk nav item in both Dashboard and PMS modes
- [23-01]: PMS mode auto-detected from URL on initial load via location.pathname.startsWith('/pms/')
- [23-02]: All 4 Morning Pack sections in single MorningPackPage.jsx (709 lines) for code coherence
- [23-02]: Trade proposal cards use tertiary bg without left accent border (visually distinct from agent cards)
- [23-02]: Quick-approve button only for conviction >= 0.70; reject uses window.prompt (modal in Phase 24)
- [23-02]: 60-second polling interval for morning-pack, risk/live, and proposals endpoints
- [23-02]: Sample data fallback for all 3 API endpoints ensures page always renders without backend
- [24-01]: Inline P&L summary cards (not PMSMetricCard) for dense horizontal layout control in Position Book
- [24-01]: SVG polyline spark chart in expanded row detail (no Recharts for inline sparklines)
- [24-01]: Close dialog uses sample-data fallback -- closes in UI even when API unavailable
- [24-01]: CDI benchmark as dashed gray line using 13.75% annual rate compounded daily over 252 trading days
- [Phase 24]: Slide-out right panel (400px fixed) for approval form instead of modal dialog
- [Phase 24]: Inline reject flow with text input + confirm/cancel instead of window.prompt
- [Phase 24]: Batch approve uses default execution values for quick bulk approval scenarios
- [Phase 24]: Client-side pagination with Load More (20 per page) for trade history tab
- [25-01]: SVG gauge with needle indicator (line + circle center) for precise VaR visualization
- [25-01]: CSS @keyframes pulse-breach injected via IIFE for breach bar animation
- [25-01]: Custom div-based limit utilization bars (not PMSGauge) for click-to-expand capability
- [25-01]: Historical VaR chart uses ReferenceLine for dashed limit thresholds
- [25-01]: Stress test bar color: green (positive), amber (-5% to 0%), red (< -5%)
- [25-02]: Waterfall chart uses stacked BarChart with transparent invisible base + colored value bar for floating-bar effect
- [25-02]: Inline magnitude bars in attribution table use proportional width against maxAbsPnl
- [25-02]: Period selector builds dynamic fetch URL with useMemo; custom dates trigger re-fetch via URL param change
- [25-02]: Dimension switcher is state toggle -- all dimensions in same AttributionResponse, no re-fetch needed
- [26-01]: Date groups use short format (e.g., "Feb 25") for compact timeline display
- [26-01]: IntersectionObserver threshold at 0.1 for early infinite scroll trigger
- [26-01]: Filters apply client-side for multi-type selection, server-side for single type
- [26-02]: Sequential agent fetch (not parallel) per Phase 19 pattern to avoid server overload
- [26-02]: Sparkline data from sinusoidal seed when no historical data available
- [26-02]: Confidence bar uses agent accent color matching card border
- [26-03]: Hash verification uses pipe-delimited content assembly for SHA-256 computation via Web Crypto API
- [26-03]: Sample data entries without stored hash auto-marked "verified"
- [26-03]: Sidebar replaces Strategies/Settings placeholders with Journal/AgentIntel/Compliance
- [27-02]: PMS assets use sync wrappers with asyncio.run() for Redis cache warming (matching assets_bronze pattern)
- [27-02]: Pre-open schedule offset 30 min from daily_pipeline (09:30 vs 09:00 UTC) to avoid contention
- [27-02]: Attribution is EOD-only; pre-open job includes MTM + proposals + morning pack (3 assets)

### Pending Todos

None yet.

### Blockers/Concerns

- Dagster requires dagster>=1.6 + dagster-webserver -- new dependency (RESOLVED in 18-01)
- Grafana Docker container added to docker-compose.yml (RESOLVED in 18-03)
- React dashboard may need Node.js 18+ for build tooling (or continue CDN approach)
- Anthropic API key needed for LLM narrative generation (fallback templates available)

## Session Continuity

Last session: 2026-02-26
Stopped at: Completed 27-02-PLAN.md (Dagster PMS Pipeline)
Resume file: .planning/phases/27-redis-cache-dagster-pms-go-live-verification/27-02-SUMMARY.md
Resume action: /gsd:execute-phase 27 (continue with 27-03)
