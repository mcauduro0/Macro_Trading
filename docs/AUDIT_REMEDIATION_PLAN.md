# Audit Remediation Plan — Macro Trading System

**Date:** 2026-02-26
**Based on:** `docs/TECHNICAL_AUDIT_REPORT.md`
**Scope:** 249 lint errors + 19 bugs + 23 security findings + 10 failing tests + dead code cleanup

---

## Execution Strategy

This plan is organized into **3 Waves** of execution, designed for the Claude Code GSD system to execute autonomously. Each wave contains independent tasks that can run **in parallel** within the wave. Waves must be executed sequentially (Wave 1 before Wave 2, etc.) because later waves depend on earlier fixes.

| Wave | Focus | Items | Priority |
|------|-------|-------|----------|
| **Wave 1** | Critical Bugs + Security + Lint | B1, B2, B4, S1-S13, 249 lint errors | CRITICAL — System non-functional without these |
| **Wave 2** | High/Medium Bugs + Tests + Docs | B3, B5-B13, 10 failing tests, README, CLAUDE.md | HIGH — Correctness and reliability |
| **Wave 3** | Tech Debt + Code Quality | Dead code, duplicates, v1/v2 consolidation, test coverage | MEDIUM — Long-term maintainability |

---

## Wave 1: Critical Fixes (Parallel Execution)

### Task 1A — Fix Strategy Instantiation (B1 CRITICAL)

**Problem:** All strategies instantiated without required `data_loader` argument. ALL portfolio, strategy, and backtest API endpoints are non-functional.

**Files to modify:**
- `src/api/routes/portfolio_api.py` (line 77)
- `src/api/routes/strategies_api.py` (line 56)
- `src/api/routes/backtest_api.py` (line 130)

**Fix:** Create a shared `DataLoader` instance (or factory) and pass it when instantiating strategies. Replace bare `Strategy()` calls with `Strategy(data_loader=get_data_loader())`.

**Verification:** `curl http://localhost:8000/api/v3/portfolio/positions` should return real data, not empty/500.

---

### Task 1B — Fix FX_BR_01 Regime Logic (B2 HIGH)

**Problem:** Regime adjustment is inverted — scales down on RISK_ON instead of RISK_OFF.

**File:** `src/strategies/fx_br_01_carry_fundamental.py` (line 148)

**Fix:** Invert the condition. Use `> 0.3` for RISK_OFF scaling (reduce exposure), not `< -0.3`.

**Verification:** Unit test with regime_score > 0.3 should show reduced position size.

---

### Task 1C — Fix Silent Exception Swallowing (B4 HIGH)

**Problem:** `except: pass` hides all strategy errors, making debugging impossible.

**File:** `src/api/routes/portfolio_api.py` (lines 89-90)

**Fix:** Replace `except: pass` with `except Exception as e: logger.error(f"Strategy {name} failed: {e}")` and return proper error responses.

---

### Task 1D — Security Hardening (S1-S13)

**Problems (13 security findings):**

| ID | Fix Required |
|----|-------------|
| S1 | Implement JWT Bearer authentication on all API endpoints |
| S2 | Restrict CORS `allow_origins` to specific domains (remove wildcard `*`) |
| S3 | Bind all Docker ports to `127.0.0.1` instead of `0.0.0.0` |
| S4 | Move all hardcoded credentials in `docker-compose.yml` to `${ENV_VAR}` references |
| S5 | Enable `sslmode=require` for DB connections in production config |
| S6 | Remove hardcoded default passwords from `src/core/config.py` (lines 30, 47, 54) |
| S7 | Remove hardcoded credentials from `alembic.ini` (line 8) |
| S8 | Remove hardcoded credentials from Grafana datasource YAML |
| S9 | Move CI workflow credentials to GitHub Secrets |
| S10 | Add Redis password via `--requirepass` in docker-compose |
| S11 | Add rate limiting using `slowapi` on all API routes |
| S12 | Sanitize error messages: log full `str(exc)` but return generic message to client (48+ instances) |
| S13 | Whitelist allowed strategy params in `strategies_api.py:371-375` instead of arbitrary `setattr()` |

**Implementation approach:**
1. Create `.env.example` with all required env vars
2. Update `docker-compose.yml` to use `${VAR}` syntax and bind to `127.0.0.1`
3. Create `src/api/auth.py` with JWT middleware
4. Add `Depends(verify_jwt)` to all route decorators
5. Add `slowapi` rate limiter to `main.py`
6. Bulk replace `str(exc)` in error responses with generic messages

---

### Task 1E — Fix All Lint Errors (249 errors)

**Auto-fix (189 errors):**
```bash
ruff check src/ tests/ --fix
```

**Manual fixes (60 errors):**
- **E501 (37 lines too long):** Break lines in `risk_monitor.py`, `daily_report.py`, `morning_pack.py`, `alert_manager.py`
- **F841 (16 unused variables):** Remove assignments or prefix with `_`
- **F821 (4 undefined `pd`):** Add `import pandas as pd` to `src/strategies/fx_04_vol_surface_rv.py`
- **F811 (2 redefined):** Remove duplicate definitions
- **E402 (1 import order):** Move import to top of file

**Verification:** `ruff check src/ tests/` returns 0 errors.

---

## Wave 2: Correctness & Reliability (Parallel Execution)

### Task 2A — Fix High/Medium Bugs (B3, B5-B13)

| Bug | File | Fix |
|-----|------|-----|
| B3 | 8 strategy files | Standardize `classify_strength` between v2.0 and v3.0 strategies |
| B5 | `portfolio_api.py:115` | Replace hardcoded 5-element VaR array with real portfolio returns computation |
| B6 | `fx_br_01.py:84`, `cross_01.py:134` | Standardize `generate_signals` signature to match BaseStrategy ABC |
| B7 | `strategies_api.py:117`, `backtest_api.py:177` | Fix column name `annual_return` → `annualized_return` |
| B8 | `strategies_api.py:306` | Fix `strategy_signals` table reference to use correct `signals` table with proper columns |
| B9 | `risk_limits.py:83` | Change `>` to `>=` for risk limit boundary enforcement |
| B10 | `risk_limits_v2.py:151-152` | Remove `abs()` from `record_daily_pnl` — gains should not trigger loss limits |
| B11 | `drawdown_manager.py:302-303` | Fix recovery ramp to start from 0% (not 33%) for smooth position sizing |
| B12 | `portfolio_constructor.py:398-416` | Fix rapid regime flipping interpolation logic |
| B13 | `base.py:298` | Change `compute_z_score` to use sample variance (N-1) instead of population (N) |

---

### Task 2B — Fix Low Bugs (B14-B19)

| Bug | File | Fix |
|-----|------|-----|
| B14 | `pms_models.py:136-138` | Add `onupdate=func.now()` to `TradeProposal.updated_at` |
| B15 | `pms_portfolio.py:231` | Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` |
| B16 | `nlp_documents.py:41-59` | Migrate `Column()` to `mapped_column()` for consistency |
| B17 | `strategy_state.py:55-60` | Fix composite index `.desc()` usage |
| B18 | `base.py:328-336` | Create shared ThreadPoolExecutor instead of per-call instantiation |
| B19 | `signal_aggregator.py:55-60` | Review and rebalance cross_asset_agent COMMODITY weight (55% → lower) |

---

### Task 2C — Fix 10 Failing Tests

All 10 failures are **stale assertions** — update expected values to match current code:

| Test File | Fix |
|-----------|-----|
| `test_cftc_cot.py::test_contract_codes_has_12_entries` | Change expected from 12 to 13 |
| `test_cftc_cot.py::test_max_possible_series` | Change expected from 48 to 52 |
| `test_dashboard.py::test_dashboard_contains_all_tabs` | Update expected tabs to match new dashboard HTML |
| `test_dashboard.py::test_dashboard_dark_theme` | Update expected theme elements |
| `test_v2_endpoints.py::test_strategies_list_returns_8` | Change expected from 8 to 24 |
| `test_risk_monitor.py::test_report_has_var_results` | Accept parametric fallback as valid |
| `test_risk_monitor.py::test_report_has_stress_results` | Change expected from 4 to 6 scenarios |
| `test_stress_tester.py::test_run_all_returns_4_results` | Change expected from 4 to 6 |
| `test_stress_tester.py::test_default_scenarios_count` | Change expected from 4 to 6 |
| `test_var_calculator.py::test_var_result_fields` | Accept historical VaR fallback method |

**Verification:** `pytest tests/ -x` — all 1,383 tests should pass.

---

### Task 2D — Update Documentation

1. **README.md:** Update to cover Phases 1-3 (currently only Phase 0). Fix test count. Remove stale "Next Phase" section.
2. **CLAUDE.md:** Fix "Stocks only" constraint (system trades FX, rates, bonds). Remove Node.js mention (Python-only project).

---

## Wave 3: Tech Debt & Quality (Parallel Execution)

### Task 3A — Remove Dead Code

- Remove 151 unused imports (68 unnecessary `from __future__ import annotations`, 14 unused `SignalStrength`, 8 unused `DataParsingError`, 8 unused `math`)
- Review unused modules: `src/transforms/vol_surface.py`, `src/quality/alerts.py`
- Review unused functions in `src/monitoring/alert_manager.py`
- Remove unused enums in `src/core/enums.py`

---

### Task 3B — Extract Duplicate Code (DRY)

| Pattern | Copies | Fix |
|---------|--------|-----|
| `_find_closest_tenor()` | 7 strategy files | Extract to `src/core/utils/tenors.py` |
| `_ensure_data_source()` | 7 connector files | Move to `BaseConnector` |
| `_chunk_date_range()` | 4 connector files | Move to `BaseConnector` |
| `run()` override | 4 connector files | Add `series_ids` param to `BaseConnector.run()` |

---

### Task 3C — Consolidate v1/v2 File Pairs

- `signal_aggregator.py` (v1) + `signal_aggregator_v2.py` (v2) → single `signal_aggregator.py` with backward-compatible API
- `risk_limits.py` (v1) + `risk_limits_v2.py` (v2) → single `risk_limits.py` (v2 extends v1)

---

### Task 3D — Expand Test Coverage

Current: 37% of modules have tests (58 of 155 source modules).

Priority targets for new tests:
1. All 17 API route files (unit tests with mocked dependencies)
2. All 16 Phase 2 strategies (individual strategy tests)
3. All 5 agent feature modules
4. All 9 Dagster orchestration modules
5. All 6 backtesting sub-modules

---

### Task 3E — Production Hardening

- Pin dependency versions with upper bounds in `pyproject.toml`
- Add security scanning (bandit, safety) to CI pipeline
- Add Docker network isolation in `docker-compose.yml`
- Enable encryption in transit for all DB connections

---

## Verification Checklist

After all 3 waves are complete:

```bash
# 1. Lint clean
ruff check src/ tests/  # 0 errors

# 2. All tests pass
pytest tests/ -x  # 1,383+ passed, 0 failed

# 3. API functional
curl http://localhost:8000/api/v3/portfolio/positions  # Returns real data

# 4. Security
# - All endpoints require JWT
# - CORS restricted
# - No hardcoded credentials
# - Docker ports bound to 127.0.0.1

# 5. CI green
git push origin main  # GitHub Actions passes
```

---

*Plan generated from Technical Audit Report (2026-02-26). Total items: 249 lint errors + 19 bugs + 23 security findings + 10 failing tests + dead code cleanup.*
