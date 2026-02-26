# Macro Trading System -- Technical Audit Report

**Date:** 2026-02-26
**Scope:** Full codebase review (Phases 0-3)
**Codebase:** 155 source files, ~37,000 LOC (src/) + 92 test files, ~18,000 LOC (tests/)

---

## Executive Summary

The Macro Trading System is a production-grade quantitative trading platform with 24 strategies, 5 analytical agents, full risk management, NLP pipeline, Dagster orchestration, and a complete Portfolio Management System (PMS). The codebase is well-structured and largely conformant with the phase specifications.

**Key Metrics:**
- **Test Results:** 1,362 passed, 10 failed, 11 skipped
- **Requirement Conformity:** ~95% (backend fully implemented; React frontend missing)
- **Critical Bugs:** 1 (strategy instantiation fails on all API endpoints)
- **Security Issues:** 5 CRITICAL, 8 HIGH (no auth, CORS wildcard, exposed ports, hardcoded creds)

| Category | Grade | Details |
|----------|-------|---------|
| Requirement Conformity | **A-** | 95% backend implemented; React frontend missing |
| Code Quality | **B+** | Well-structured but has DRY violations, 63% test gap |
| Bugs & Logic | **B-** | 1 CRITICAL, 4 HIGH, 8 MEDIUM bugs found |
| Security | **D** | No API auth, wildcard CORS, hardcoded creds, exposed ports |
| Documentation | **B+** | Excellent docstrings; README outdated; CLAUDE.md minor errors |
| Dead Code | **B** | 151 unused imports, duplicated utilities, v1/v2 file pairs |

---

## 1. Requirement Conformity

### Phase 0: Data Infrastructure -- COMPLETE

| Requirement | Status | Notes |
|-------------|--------|-------|
| Docker Compose (6 services) | [x] | 7 services (added Grafana, Dagster); Kafka upgraded to KRaft |
| TimescaleDB + Alembic (9 migrations) | [x] | 10 tables, 7 hypertables with compression |
| 11+ Data Connectors | [x] | 12 functional + 1 placeholder (ANBIMA) |
| 200+ Macro Series | [x] | 250+ series across 14 categories |
| Transforms (Silver Layer) | [x] | curves, returns, macro, vol_surface |
| FastAPI + 12 endpoints | [x] | 23 route files with 30+ endpoints |
| Data Quality Framework | [x] | checks.py, alerts.py, verify_infrastructure.py |
| Seeds + Backfill Scripts | [x] | seed_instruments, seed_series_metadata, backfill |
| CI/CD (GitHub Actions) | [x] | ci.yml with lint + test stages |

**Missing:** `commodities.py` connector, `infrastructure/` directory, `notebooks/` directory

### Phase 1: Agents & Backtesting -- COMPLETE

| Requirement | Status | Notes |
|-------------|--------|-------|
| 5 Analytical Agents | [x] | Inflation, Monetary, Fiscal, FX, Cross-Asset |
| Agent Features (5 modules) | [x] | All 5 feature sets implemented |
| HMM Regime Detection | [x] | hmm_regime.py |
| 8 Trading Strategies | [x] | All 8 Phase 1 strategies implemented |
| Backtesting Engine | [x] | engine, portfolio, analytics, costs, metrics, report |
| Signal Aggregator | [x] | signal_aggregator.py |
| Portfolio Constructor | [x] | portfolio_constructor.py, capital_allocator.py |
| Risk Management | [x] | VaR, limits, drawdown, monitor |
| Daily Pipeline | [x] | daily_pipeline.py (8-step orchestration) |
| Narrative Generator | [x] | LLM-powered narrative generation |

### Phase 2: Strategy Engine & Risk -- COMPLETE

| Requirement | Status | Notes |
|-------------|--------|-------|
| 16 Additional Strategies | [x] | 24 total registered in ALL_STRATEGIES |
| NLP Pipeline (COPOM/FOMC) | [x] | Scrapers, sentiment analyzer, dictionaries |
| Risk Engine (VaR/CVaR/Stress) | [x] | 3 VaR methods, 6 stress scenarios, 9 limits |
| Portfolio Optimization | [x] | Risk Parity, Black-Litterman, Mean-Variance |
| Dagster Orchestration | [x] | 26 assets, 4 jobs, 3 schedules |
| Grafana (4 dashboards) | [x] | pipeline_health, risk, signals, portfolio |
| Signal Aggregator v2 | [x] | Crowding penalty, staleness discount |
| WebSocket API | [x] | 3 channels (signals, portfolio, risk) |

### Phase 3: PMS & Go-Live -- MOSTLY COMPLETE

| Requirement | Status | Notes |
|-------------|--------|-------|
| PMS Database Schema | [x] | Migration 009: positions, trades, journal, briefings |
| 7 PMS Services | [x] | Position, MTM, Trade Workflow, Morning Pack, Attribution, Risk Monitor, Pricing |
| 6 PMS API Route Groups | [x] | Portfolio, Trades, Risk, Attribution, Briefing, Journal |
| PMS Dagster Integration | [x] | 4 PMS assets, 2 PMS-specific jobs |
| Redis Cache Layer | [x] | pms_cache.py |
| Backup/Restore Scripts | [x] | backup.sh, restore.sh |
| Go-Live Checklist | [x] | GOLIVE_CHECKLIST.md |
| Operational Runbook | [x] | OPERATIONAL_RUNBOOK.md |
| **React Frontend (7 screens)** | **[ ]** | **All API endpoints ready, but no UI exists** |

---

## 2. Bugs & Logic Errors (19 found)

### CRITICAL (1)

| # | Bug | File | Impact |
|---|-----|------|--------|
| B1 | All strategies instantiated without required `data_loader` argument | `src/api/routes/portfolio_api.py:77`, `strategies_api.py:56`, `backtest_api.py:130` | ALL portfolio, strategy, and backtest API endpoints are non-functional. They either return empty/placeholder data or 500 errors |

### HIGH (4)

| # | Bug | File | Impact |
|---|-----|------|--------|
| B2 | FX_BR_01 regime adjustment inverted -- scales down on RISK_ON instead of RISK_OFF | `src/strategies/fx_br_01_carry_fundamental.py:148` | FX carry strategy reduces exposure during favorable conditions |
| B3 | `classify_strength` inconsistency between v2.0 and v3.0 strategies | 8 strategy files | Position sizing differs across strategy cohorts |
| B4 | Silent exception swallowing hides all strategy errors | `src/api/routes/portfolio_api.py:89-90` | All failures hidden; debugging impossible |
| B5 | Risk report uses hardcoded 5-element array for VaR | `src/api/routes/portfolio_api.py:115` | `/portfolio/risk` returns meaningless risk metrics |

### MEDIUM (8)

| # | Bug | File | Impact |
|---|-----|------|--------|
| B6 | `generate_signals` signature mismatch vs BaseStrategy ABC | `fx_br_01_carry_fundamental.py:84`, `cross_01_regime_allocation.py:134` | CROSS_01 returns wrong type; FX_BR_01 never gets regime_score via API |
| B7 | `backtest_results` table queried with wrong column name (`annual_return` vs `annualized_return`) | `strategies_api.py:117`, `backtest_api.py:177` | Backtest retrieval fails silently |
| B8 | `strategy_signals` table does not exist; `signals` table has no `conviction` column | `strategies_api.py:306` | Signal history returns random placeholder data |
| B9 | Risk limit boundary: strict `>` instead of `>=` | `src/risk/risk_limits.py:83` | Limit not enforced at exact boundary value |
| B10 | `RiskLimitsManager.record_daily_pnl` uses `abs()` -- gains trigger loss breach | `src/risk/risk_limits_v2.py:151-152` | Large positive returns falsely trigger loss limits |
| B11 | Drawdown recovery scale jumps from 0% to 33% instead of ramping smoothly | `src/risk/drawdown_manager.py:302-303` | Abrupt position sizing change on recovery |
| B12 | Rapid regime flipping produces incorrect transition scaling | `src/portfolio/portfolio_constructor.py:398-416` | Wrong interpolation when regimes change rapidly |
| B13 | `compute_z_score` uses population variance (N) instead of sample variance (N-1) | `src/strategies/base.py:298` | Z-scores systematically ~0.2% too high |

### LOW (6)

| # | Bug | File | Impact |
|---|-----|------|--------|
| B14 | `TradeProposal.updated_at` missing `onupdate=func.now()` | `src/core/models/pms_models.py:136-138` | Stale timestamps on modifications |
| B15 | `update_price` uses deprecated `datetime.utcnow()` | `src/api/routes/pms_portfolio.py:231` | Timezone-naive datetime in timezone-aware column |
| B16 | `NlpDocumentRecord` uses legacy SQLAlchemy `Column()` instead of `mapped_column` | `src/core/models/nlp_documents.py:41-59` | Style inconsistency; type checker issues |
| B17 | `StrategyStateRecord` composite index uses `.desc()` at class level | `src/core/models/strategy_state.py:55-60` | Fragile; could break under Alembic migration |
| B18 | ThreadPoolExecutor created per signal persistence call | `src/agents/base.py:328-336` | Performance overhead |
| B19 | Signal aggregator: cross_asset_agent has 55% weight for COMMODITY | `src/portfolio/signal_aggregator.py:55-60` | Risk concentration in signal layer |

---

## 3. Test Results

```
Total:   1,383 tests
Passed:  1,362 (98.5%)
Failed:  10 (0.7%)
Skipped: 11 (0.8%)
```

### Failing Tests (10)

| Test File | Test | Root Cause |
|-----------|------|------------|
| `test_cftc_cot.py` | `test_contract_codes_has_12_entries` | Code has 13 contracts, test expects 12 |
| `test_cftc_cot.py` | `test_max_possible_series` | 52 series vs expected 48 |
| `test_dashboard.py` | `test_dashboard_contains_all_tabs` | Dashboard HTML changed, test not updated |
| `test_dashboard.py` | `test_dashboard_dark_theme` | Dashboard HTML changed, test not updated |
| `test_v2_endpoints.py` | `test_strategies_list_returns_8` | 24 strategies registered, test expects 8 |
| `test_risk_monitor.py` | `test_report_has_var_results` | Historical VaR falls back to parametric (insufficient data) |
| `test_risk_monitor.py` | `test_report_has_stress_results` | 6 stress scenarios now vs test expecting 4 |
| `test_stress_tester.py` | `test_run_all_returns_4_results` | 6 scenarios vs expected 4 |
| `test_stress_tester.py` | `test_default_scenarios_count` | 6 scenarios vs expected 4 |
| `test_var_calculator.py` | `test_var_result_fields` | Historical VaR fallback method mismatch |

**Root Cause:** All 10 failures are **stale test assertions** -- the code evolved (more strategies, more stress scenarios, dashboard redesign) but tests were not updated to match.

---

## 4. Security Findings (23 issues)

### CRITICAL (5)

| # | Finding | File | Recommended Fix |
|---|---------|------|-----------------|
| S1 | **No authentication on any API endpoint** | All `src/api/routes/` | Implement JWT Bearer tokens + role-based authorization |
| S2 | **Wildcard CORS with credentials** | `src/api/main.py:98-104` | Restrict `allow_origins` to specific domains |
| S3 | **All database ports exposed to 0.0.0.0** | `docker-compose.yml:9,25,42,58,92-93` | Bind to `127.0.0.1` only |
| S4 | **Hardcoded credentials in docker-compose.yml** | `docker-compose.yml:8,41,96,114,137` | Use `${VARIABLE}` references to `.env` |
| S5 | **No encryption in transit for DB connections** | `config.py`, Grafana datasource | Enable `sslmode=require` in production |

### HIGH (8)

| # | Finding | File |
|---|---------|------|
| S6 | Hardcoded default passwords in config.py | `src/core/config.py:30,47,54` |
| S7 | Hardcoded credentials in alembic.ini | `alembic.ini:8` |
| S8 | Hardcoded credentials in Grafana datasource | `monitoring/grafana/provisioning/datasources/timescaledb.yml` |
| S9 | Credentials in CI workflow (should use GitHub Secrets) | `.github/workflows/ci.yml:28-29,48-49` |
| S10 | Redis has no authentication | `docker-compose.yml:28` |
| S11 | No rate limiting on API endpoints | All route files |
| S12 | Verbose error messages leak internal details (48+ instances of `str(exc)`) | All route files |
| S13 | Arbitrary `setattr()` via strategy params API | `src/api/routes/strategies_api.py:371-375` |

### MEDIUM (6)

| # | Finding | File |
|---|---------|------|
| S14 | f-string in SQL table name (controlled but dangerous pattern) | `src/api/routes/health.py:44` |
| S15 | `ilike` with user input allows wildcard abuse | `src/api/routes/macro.py:167` |
| S16 | WebSocket endpoints unauthenticated | `src/api/routes/websocket_api.py:106-152` |
| S17 | OpenAPI/Swagger docs exposed without auth | `src/api/main.py:88-89` |
| S18 | Unpinned dependency versions in pyproject.toml | `pyproject.toml:11-33` |
| S19 | Full source code mounted in Dagster container | `docker-compose.yml:132` |

### LOW (4)

| # | Finding | File |
|---|---------|------|
| S20 | No security scanning in CI pipeline | `.github/workflows/ci.yml` |
| S21 | No Docker network isolation | `docker-compose.yml` |
| S22 | Mock secret naming pattern in test | `tests/connectors/test_fred.py:184` |
| S23 | `__import__("numpy")` usage | `src/pms/risk_monitor.py:309` |

---

## 5. Documentation & Comments

| Area | Rating | Key Finding |
|------|--------|-------------|
| **README.md** | ADEQUATE | Excellent Phase 0 docs but not updated for Phases 1-3; wrong test count; stale "Next Phase" section |
| **CLAUDE.md** | ADEQUATE | Good structure but inaccurate constraint ("Stocks only" when system trades FX, rates, bonds); mentions Node.js but project is Python-only |
| **Module Docstrings** | GOOD | 96%+ coverage; only 4 files missing (all in `transforms/`) |
| **Class Docstrings** | GOOD | 100% coverage on key classes; Attributes documented; design patterns named |
| **Function Docstrings** | GOOD | Thorough Args/Returns/Raises; `transforms/` module is the weak spot |
| **Type Hints** | GOOD | Modern Python typing throughout |
| **Inline Comments** | GOOD | Mathematical models well-commented; formulas included inline |
| **API Documentation** | GOOD | OpenAPI tags defined; some endpoints return raw `dict` instead of Pydantic response models |

---

## 6. Dead Code & Quality

### Unused Imports (151 instances across 95 files)
- 68 files import `from __future__ import annotations` unnecessarily
- 14 strategy files import `SignalStrength` without using it
- 8 connectors import `DataParsingError` without using it
- 8 strategy files import `math` without using it

### Duplicate Code (4 critical patterns)
| Pattern | Copies | Location | Fix |
|---------|--------|----------|-----|
| `_find_closest_tenor()` | 7 | Strategy files | Extract to `src/core/utils/tenors.py` |
| `_ensure_data_source()` | 7 | Connector files | Move to `BaseConnector` |
| `_chunk_date_range()` | 4 | Connector files | Move to `BaseConnector` |
| `run()` override | 4 | Connector files | Add `series_ids` param to `BaseConnector.run()` |

### Unused Modules/Functions
- `src/transforms/vol_surface.py` -- all 4 functions unused
- `src/quality/alerts.py` -- all 5 alert functions unused
- `src/monitoring/alert_manager.py` -- `enable_rule()`, `disable_rule()`, `update_threshold()` unused
- `src/core/enums.py` -- `CurveType`, `FlowType`, `FiscalMetric` enums unused

### Tech Debt: v1/v2 File Pairs
- `signal_aggregator.py` (v1) and `signal_aggregator_v2.py` (v2) -- both actively used by different callers
- `risk_limits.py` (v1) and `risk_limits_v2.py` (v2) -- v2 extends v1

### Test Coverage Gaps
- **97 of 155 source modules (63%) have no corresponding test file**
- All 5 agent feature modules untested
- All 17 API route files untested at unit level
- All 16 Phase 2 strategies untested individually
- All 9 Dagster orchestration modules untested
- All 6 backtesting sub-modules untested individually

### Large Files (>500 lines, 18 files)
Largest: `inflation_agent.py` (1,157 lines), `monetary_agent.py` (855 lines), `fiscal_agent.py` (828 lines)

---

## 7. Priority Action Items

### Immediate (Before Any Production Use)

- [ ] **FIX B1:** Provide `data_loader` when instantiating strategies in API routes
- [ ] **FIX B2:** Invert FX_BR_01 regime condition (`> 0.3` for RISK_OFF, not `< -0.3`)
- [ ] **FIX B4:** Replace `except: pass` with proper logging in portfolio_api
- [ ] **FIX S1:** Implement API authentication (JWT recommended)
- [ ] **FIX S2:** Restrict CORS origins
- [ ] **FIX S3:** Bind Docker ports to `127.0.0.1`
- [ ] **FIX S4:** Move all credentials to environment variables
- [ ] **FIX S10:** Add Redis password

### Short-Term (Before Production Deployment)

- [ ] **FIX B5:** Use real portfolio returns for VaR computation
- [ ] **FIX B7:** Correct column name `annual_return` -> `annualized_return`
- [ ] **FIX B8:** Fix `strategy_signals` table reference
- [ ] **FIX B10:** Remove `abs()` from loss limit check (gains should not trigger)
- [ ] **FIX S11:** Add rate limiting (slowapi)
- [ ] **FIX S12:** Sanitize error messages (log full exc, return generic message)
- [ ] **FIX S13:** Whitelist allowed strategy params
- [ ] Update 10 failing tests to match current code
- [ ] Update README.md to cover Phases 1-3
- [ ] Fix CLAUDE.md inaccuracies ("Stocks only", Node.js)

### Medium-Term (Production Hardening)

- [ ] **FIX B6:** Standardize `generate_signals` signature across all strategies
- [ ] **FIX B9:** Use `>=` instead of `>` for risk limit boundary
- [ ] **FIX B11:** Fix drawdown recovery ramp (start from 0, not 1/3)
- [ ] Extract duplicate code (`_find_closest_tenor`, `_ensure_data_source`, `_chunk_date_range`)
- [ ] Consolidate v1/v2 file pairs (signal_aggregator, risk_limits)
- [ ] Remove 151 unused imports
- [ ] Add unit tests for untested 63% of source modules
- [ ] Pin dependency versions with upper bounds
- [ ] Add security scanning to CI pipeline
- [ ] Implement React frontend for PMS (7 screens)

---

## 8. Final Checklist

### Architecture & Design
- [x] Layered architecture (connectors -> transforms -> agents -> strategies -> portfolio -> risk -> API)
- [x] Abstract base classes (BaseAgent, BaseConnector, BaseStrategy)
- [x] Registry pattern for agents and strategies
- [x] Event-driven backtesting engine
- [x] Point-in-time data correctness
- [x] Bronze/Silver/Gold data pipeline
- [x] Human-in-the-loop trade workflow
- [~] DRY principle (4 critical duplicate patterns)
- [ ] Frontend implementation

### Data Infrastructure
- [x] 12 functional data connectors
- [x] TimescaleDB with hypertables and compression
- [x] 9 database migrations
- [x] Seed scripts and backfill orchestrator
- [x] Data quality checks framework
- [~] ANBIMA connector (placeholder only)
- [ ] Commodities connector (missing)

### Quantitative Models
- [x] 5 analytical agents with 20+ quantitative models
- [x] 24 trading strategies across 6 asset classes
- [x] Signal aggregation (confidence-weighted, crowding penalty, staleness discount)
- [x] Portfolio optimization (Risk Parity, Black-Litterman, Mean-Variance)
- [x] Risk management (3 VaR methods, 6 stress scenarios, circuit breakers)
- [x] NLP pipeline (COPOM/FOMC scrapers, hawk-dove scoring)

### Production Readiness
- [x] Dagster orchestration (26 assets, 4 jobs, 3 schedules)
- [x] Grafana monitoring (4 dashboards)
- [x] Alert management (10 rules)
- [x] Daily reporting pipeline
- [x] CI/CD pipeline (GitHub Actions)
- [x] Backup/restore scripts
- [x] Go-live checklist and operational runbook
- [ ] API authentication
- [ ] Rate limiting
- [ ] Credential management (secrets not hardcoded)
- [ ] Network security (port binding)
- [ ] Encryption in transit

### Code Quality
- [x] Consistent naming conventions (snake_case throughout)
- [x] No commented-out code
- [x] No TODO/FIXME markers
- [x] No unreachable code
- [x] Comprehensive docstrings (96%+ coverage)
- [x] Modern Python type hints
- [~] Test coverage (37% of modules have tests)
- [~] 10 failing tests (stale assertions)
- [ ] 151 unused imports to clean up
- [ ] Duplicate utility functions to extract

---

*Report generated by comprehensive technical audit using 7 parallel analysis agents covering: codebase structure, Phase 0-3 requirements, bugs/logic, security, documentation, dead code, and test execution.*
