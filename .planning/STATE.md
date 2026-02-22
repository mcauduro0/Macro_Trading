# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system
**Current focus:** Phase 16: Cross-Asset Agent v2 & NLP Pipeline (v3.0)

## Current Position

Phase: 16 of 19 (Cross-Asset Agent v2 & NLP Pipeline)
Plan: 3 of 3 complete in current phase
Status: Phase 16 complete -- ready for Phase 17
Last activity: 2026-02-22 — Completed 16-03 (Sentiment Scoring Pipeline)

Progress: [##########################....] 84% (16/19 phases complete)

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

### Pending Todos

None yet.

### Blockers/Concerns

- Dagster requires dagster>=1.6 + dagster-webserver -- new dependency
- Grafana requires Docker container addition to docker-compose.yml
- React dashboard may need Node.js 18+ for build tooling (or continue CDN approach)
- Anthropic API key needed for LLM narrative generation (fallback templates available)

## Session Continuity

Last session: 2026-02-22
Stopped at: Completed 16-03-PLAN.md (Sentiment Scoring Pipeline) -- Phase 16 complete
Resume file: .planning/phases/
Resume action: Begin Phase 17 planning/execution
