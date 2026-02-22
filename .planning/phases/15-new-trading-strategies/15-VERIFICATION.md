---
phase: 15-new-trading-strategies
verified: 2026-02-22T17:40:32Z
status: gaps_found
score: 4/5 success criteria verified
re_verification: false
gaps:
  - truth: "Each strategy backtests without error over 2+ years of historical data and produces a valid tearsheet with Sharpe, drawdown, and trade statistics"
    status: failed
    reason: "New strategies return list[StrategySignal] but BacktestEngine.run() expects dict[str, float] from generate_signals(). The engine's try/except silently swallows an AttributeError ('list' object has no attribute 'keys') every step, producing tearsheets with 0 trades and no real backtest. This is confirmed by observing backtest_step_failed warnings at every rebalance date."
    artifacts:
      - path: "src/backtesting/engine.py"
        issue: "Line 113: calls list(target_weights.keys()) where target_weights is list[StrategySignal]; .keys() does not exist on list; exception is caught silently in the except block"
      - path: "src/strategies/fx_02_carry_momentum.py"
        issue: "generate_signals returns list[StrategySignal] (correct for v3 framework) but incompatible with BacktestEngine StrategyProtocol which declares dict[str, float] return type"
    missing:
      - "BacktestEngine needs a signal adapter that converts list[StrategySignal] to dict[str, float] target weights (extracting instrument -> suggested_size from each signal)"
      - "Alternatively, new strategies need a signals_to_weights() method that BacktestEngine can call, OR BacktestEngine.run() needs to detect and handle list[StrategySignal] returns"
      - "Integration tests that actually verify non-zero trades are produced when data is present"
human_verification:
  - test: "Verify strategy signal quality on real data"
    expected: "Each strategy produces StrategySignal objects with non-None z_score, and appropriate entry/stop/take-profit levels for tradeable instruments"
    why_human: "Cannot run against real database (DB not seeded in test env); tests use mocks"
  - test: "Confirm tearsheet output against real 2-year backtest"
    expected: "After fixing the BacktestEngine adapter, each strategy produces a BacktestResult with non-zero total_trades and valid Sharpe/drawdown metrics"
    why_human: "Requires real historical data and the adapter fix to be implemented first"
---

# Phase 15: New Trading Strategies Verification Report

**Phase Goal:** 16 new trading strategies spanning all major asset classes -- FX (4), rates (4), inflation (2), cupom cambial (1), sovereign (3), and cross-asset (2) -- each producing StrategySignal outputs compatible with the enhanced framework
**Verified:** 2026-02-22T17:40:32Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths (from Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can list all strategies by asset class and see 24+ strategies total (8 existing + 16 new) across FX, rates, inflation, cupom cambial, sovereign, and cross-asset categories | VERIFIED | `StrategyRegistry.list_all()` returns 24 IDs; FX:5, RATES_BR:3, RATES_US:1, INFLATION_BR:2, CUPOM_CAMBIAL:1, SOVEREIGN_CREDIT:3, CROSS_ASSET:2, FIXED_INCOME:7 |
| 2 | FX strategies produce valid signals: FX-02 (carry-adjusted momentum combining Selic-FFR spread with USDBRL momentum), FX-03 (flow-based from BCB/CFTC/B3 with contrarian logic at `|z|>2`), FX-04 (vol surface relative value), FX-05 (terms of trade misalignment) | VERIFIED | All 4 FX strategies implement correct composite logic with contrarian threshold `_CONTRARIAN_THRESHOLD = 2.0` in FX-03, 5-commodity weighted ToT index in FX-05, implied-realized+skew+kurtosis components in FX-04 |
| 3 | Rates strategies produce valid signals: RATES-03 (BR-US spread adjusted for CDS), RATES-04 (term premium extraction from DI vs Focus), RATES-05 (FOMC event positioning), RATES-06 (COPOM event positioning) | VERIFIED | RATES-05 has `FOMC_DATES` list covering 2015-2026 with `_is_fomc_window()` method; RATES-06 has `COPOM_DATES` with `_is_copom_window()` method; RATES-03 adjusts spread by CDS; RATES-04 uses Focus expectations |
| 4 | All 16 new strategies register via `@StrategyRegistry.register`, populate z_score/entry_level/stop_loss/take_profit in StrategySignal, and pass backtesting with the TransactionCostModel | FAILED | Registry decoration: verified. z_score/entry_level/stop_loss/take_profit fields: verified (Optional[float], None acceptable per schema). Backtesting: FAILED -- `generate_signals()` returns `list[StrategySignal]` but `BacktestEngine.run()` calls `.keys()` on the result (expects `dict[str, float]`); every step silently fails with `AttributeError: 'list' object has no attribute 'keys'`; tearsheets produce 0 trades |
| 5 | Each strategy backtests without error over 2+ years of historical data and produces a valid tearsheet with Sharpe, drawdown, and trade statistics | FAILED | Strategies "backtest without error" only because `BacktestEngine` wraps each step in `try/except Exception` and logs `backtest_step_failed` silently; confirmed by observing 502 `backtest_step_failed` warnings for a 2-year run of FX-02; `BacktestResult` exists with correct schema (Sharpe, max_drawdown, total_trades fields) but will always show total_trades=0 |

**Score:** 3/5 truths fully verified (Truths 1, 2, 3 pass; Truths 4, 5 fail on backtesting compatibility)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/strategies/fx_02_carry_momentum.py` | FX-02 Carry-Adjusted Momentum strategy with `@StrategyRegistry.register` | VERIFIED | 276 lines; registered as FX_02; Selic-FFR carry + 63-day USDBRL momentum composite |
| `src/strategies/fx_03_flow_tactical.py` | FX-03 Flow-Based Tactical FX with `@StrategyRegistry.register` | VERIFIED | 270 lines; registered as FX_03; BCB 40%/CFTC 35%/B3 25% with contrarian at |z|>2.0 |
| `src/strategies/fx_04_vol_surface_rv.py` | FX-04 Vol Surface RV with `@StrategyRegistry.register` | VERIFIED | 324 lines; registered as FX_04; IV-RV premium + term structure + skew + kurtosis |
| `src/strategies/fx_05_terms_of_trade.py` | FX-05 Terms of Trade with `@StrategyRegistry.register` | VERIFIED | 277 lines; registered as FX_05; soybean 30%, iron ore 25%, oil 20%, sugar 15%, coffee 10% |
| `src/strategies/rates_03_br_us_spread.py` | RATES-03 BR-US Rate Spread with `@StrategyRegistry.register` | VERIFIED | 274 lines; registered as RATES_03; DI-UST spread with CDS adjustment |
| `src/strategies/rates_04_term_premium.py` | RATES-04 Term Premium Extraction with `@StrategyRegistry.register` | VERIFIED | 231 lines; registered as RATES_04; DI vs Focus Selic expectation |
| `src/strategies/rates_05_fomc_event.py` | RATES-05 FOMC Event with `@StrategyRegistry.register` | VERIFIED | 343 lines; registered as RATES_05 (AssetClass.RATES_US); FOMC_DATES list 2015-2026 |
| `src/strategies/rates_06_copom_event.py` | RATES-06 COPOM Event with `@StrategyRegistry.register` | VERIFIED | 384 lines; registered as RATES_06 (AssetClass.RATES_BR); COPOM_DATES list |
| `src/strategies/inf_02_ipca_surprise.py` | INF-02 IPCA Surprise Trade with `@StrategyRegistry.register` | VERIFIED | 353 lines; registered as INF_02; seasonal model + Focus divergence |
| `src/strategies/inf_03_inflation_carry.py` | INF-03 Inflation Carry with `@StrategyRegistry.register` | VERIFIED | 290 lines; registered as INF_03; DI-NTN_B breakeven vs 3 benchmarks |
| `src/strategies/cupom_02_onshore_offshore.py` | CUPOM-02 Onshore-Offshore Spread with `@StrategyRegistry.register` | VERIFIED | 268 lines; registered as CUPOM_02; DI vs UST+FX forward spread z-score |
| `src/strategies/sov_01_cds_curve.py` | SOV-01 CDS Curve Trading with `@StrategyRegistry.register` | VERIFIED | 276 lines; registered as SOV_01; CDS level + slope + fiscal composite |
| `src/strategies/sov_02_em_relative_value.py` | SOV-02 EM Relative Value with `@StrategyRegistry.register` | VERIFIED | 368 lines; registered as SOV_02; 10-peer OLS cross-section regression |
| `src/strategies/sov_03_rating_migration.py` | SOV-03 Rating Migration with `@StrategyRegistry.register` | VERIFIED | 316 lines; registered as SOV_03; logistic model with fiscal/growth/external/political factors |
| `src/strategies/cross_01_regime_allocation.py` | CROSS-01 Macro Regime Allocation with `@StrategyRegistry.register` | VERIFIED | 305 lines; registered as CROSS_01; 4-regime classification (Goldilocks/Reflation/Stagflation/Deflation) with allocation map |
| `src/strategies/cross_02_risk_appetite.py` | CROSS-02 Global Risk Appetite with `@StrategyRegistry.register` | VERIFIED | 409 lines; registered as CROSS_02; 6 market-only indicators (VIX, CDS, FX vol, eq-bond corr, funding spreads, equity momentum) |
| `tests/test_strategies/test_fx_new.py` | Unit tests for all 4 new FX strategies (min 100 lines) | VERIFIED | 667 lines; 108 total tests across all 4 test files; all 108 pass |
| `tests/test_strategies/test_rates_new.py` | Unit tests for all 4 new rates strategies (min 120 lines) | VERIFIED | 496 lines |
| `tests/test_strategies/test_inf_cupom_new.py` | Unit tests for INF-02, INF-03, CUPOM-02 (min 80 lines) | VERIFIED | 530 lines |
| `tests/test_strategies/test_sov_cross_new.py` | Unit tests for SOV-01/02/03 and CROSS-01/02 (min 140 lines) | VERIFIED | 744 lines |
| `src/strategies/__init__.py` | Updated with all 16 new strategies, ALL_STRATEGIES dict with 24 entries | VERIFIED | ALL_STRATEGIES has 24 entries; all 16 new classes imported in organized Plan groups; `__all__` updated |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/strategies/fx_02_carry_momentum.py` | StrategyRegistry | `@StrategyRegistry.register("FX_02", ...)` | WIRED | Line 70 |
| `src/strategies/fx_03_flow_tactical.py` | StrategyRegistry | `@StrategyRegistry.register("FX_03", ...)` | WIRED | Line 75 |
| `src/strategies/fx_04_vol_surface_rv.py` | StrategyRegistry | `@StrategyRegistry.register("FX_04", ...)` | WIRED | Line 74 |
| `src/strategies/fx_05_terms_of_trade.py` | StrategyRegistry | `@StrategyRegistry.register("FX_05", ...)` | WIRED | Line 80 |
| `src/strategies/rates_05_fomc_event.py` | PointInTimeDataLoader | `self.data_loader.get_curve("UST_NOM", ...)` | WIRED | Line 195 |
| `src/strategies/rates_06_copom_event.py` | PointInTimeDataLoader | `self.data_loader.get_curve("DI_PRE", ...)` | WIRED | Line 195 |
| `src/strategies/inf_02_ipca_surprise.py` | PointInTimeDataLoader | `self.data_loader.get_macro_series(...)`, `get_focus_expectations(...)` | WIRED | 5 data_loader calls |
| `src/strategies/cupom_02_onshore_offshore.py` | PointInTimeDataLoader | `self.data_loader.get_curve("DI_PRE", ...)` | WIRED | 4 data_loader calls |
| `src/strategies/cross_01_regime_allocation.py` | PointInTimeDataLoader | `self.data_loader.get_macro_series(...)`, `get_market_data(...)` | WIRED | Multiple calls |
| `src/strategies/cross_02_risk_appetite.py` | PointInTimeDataLoader | `self.data_loader.get_market_data(...)` | WIRED | Multiple market data calls |
| `src/strategies/__init__.py` | All 16 new strategy classes | Import + ALL_STRATEGIES dict | WIRED | All 16 imported and added to ALL_STRATEGIES |
| New strategies (`list[StrategySignal]`) | BacktestEngine (`dict[str, float]`) | `engine.run(strategy)` call | NOT_WIRED | Type mismatch: `BacktestEngine.run()` calls `.keys()` on return value of `generate_signals()`, but `list` has no `.keys()` method; `try/except` silently hides this |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FXST-01 | Plan 01 | FX-02 Carry-Adjusted Momentum | SATISFIED | `fx_02_carry_momentum.py` implements Selic-FFR carry z-score + USDBRL momentum composite |
| FXST-02 | Plan 01 | FX-03 Flow-Based Tactical FX | SATISFIED | `fx_03_flow_tactical.py` implements BCB 40%/CFTC 35%/B3 25% with contrarian at |z|>2 |
| FXST-03 | Plan 01 | FX-04 Vol Surface Relative Value | SATISFIED | `fx_04_vol_surface_rv.py` implements IV-RV premium, term structure, skew, kurtosis |
| FXST-04 | Plan 01 | FX-05 Terms of Trade FX | SATISFIED | `fx_05_terms_of_trade.py` with soybean/iron ore/oil/sugar/coffee weights |
| RTST-01 | Plan 02 | RATES-03 BR-US Rate Spread | SATISFIED | `rates_03_br_us_spread.py` with CDS adjustment and inflation differential |
| RTST-02 | Plan 02 | RATES-04 Term Premium Extraction | SATISFIED | `rates_04_term_premium.py` with Focus Selic expectations |
| RTST-03 | Plan 02 | RATES-05 FOMC Event Strategy | SATISFIED | `rates_05_fomc_event.py` with FOMC_DATES list and Taylor Rule |
| RTST-04 | Plan 02 | RATES-06 COPOM Event Strategy | SATISFIED | `rates_06_copom_event.py` with COPOM_DATES list and BCB reaction function |
| INST-01 | Plan 03 | INF-02 IPCA Surprise Trade | SATISFIED | `inf_02_ipca_surprise.py` with IPCA release window and seasonal model |
| INST-02 | Plan 03 | INF-03 Inflation Carry | SATISFIED | `inf_03_inflation_carry.py` comparing breakeven to target/IPCA/Focus |
| CPST-01 | Plan 03 | CUPOM-02 Onshore-Offshore Spread | SATISFIED | `cupom_02_onshore_offshore.py` with DI vs UST+FX forward spread z-score |
| SVST-01 | Plan 04 | SOV-01 CDS Curve Trading | SATISFIED | `sov_01_cds_curve.py` with level, slope, fiscal factor composite |
| SVST-02 | Plan 04 | SOV-02 EM Sovereign Relative Value | SATISFIED | `sov_02_em_relative_value.py` with 10-peer OLS cross-section (Poland substitutes Russia) |
| SVST-03 | Plan 04 | SOV-03 Rating Migration Anticipation | SATISFIED | `sov_03_rating_migration.py` with sigmoid logistic model, 4 weighted factors |
| CAST-01 | Plan 04 | CROSS-01 Macro Regime Allocation | SATISFIED | `cross_01_regime_allocation.py` with 4-state rule-based regime + allocation map |
| CAST-02 | Plan 04 | CROSS-02 Global Risk Appetite | SATISFIED | `cross_02_risk_appetite.py` with 6 market-only indicators, explicit trade recommendations |

All 16 requirement IDs declared across Plans 01-04 are satisfied at the individual strategy implementation level. The gap is in backtesting integration (success criteria 4-5), which is not captured by a requirement ID.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/strategies/cross_01_regime_allocation.py` | 199-201 | `entry_level=None, stop_loss=None, take_profit=None` | Info | Acceptable -- fields are `Optional[float]` per SFWK-01 schema; CROSS asset positions are percentage allocations, not price levels |
| `src/backtesting/engine.py` | 113 | `list(target_weights.keys())` fails silently when strategy returns `list[StrategySignal]` | Blocker | Prevents goal criterion 4-5 from being achieved; backtest produces 0 trades with no visible error to user |

### Human Verification Required

#### 1. Strategy Signal Quality on Real Data

**Test:** Run each strategy with a live database seeded with 2+ years of historical data; check that signals are generated (non-empty list) at appropriate market conditions.
**Expected:** FX-02 produces SHORT USDBRL signal when Selic-FFR spread is historically elevated; RATES-05 produces UST position signal within 5 business days of a FOMC date.
**Why human:** Cannot verify without a seeded TimescaleDB instance; all tests use mocks.

#### 2. Tearsheet Quality After BacktestEngine Fix

**Test:** After fixing the BacktestEngine-StrategySignal adapter, run FX-02 and RATES-03 over 2023-2024 data and verify the BacktestResult output.
**Expected:** `total_trades > 0`, `sharpe_ratio` is a finite float, `max_drawdown` is negative, `equity_curve` has 504+ points.
**Why human:** Requires the adapter fix and a real data environment.

### Gaps Summary

**Root cause:** The new 16 strategies use a different signal return type (`list[StrategySignal]`) than what `BacktestEngine` expects (`dict[str, float]`). This causes silent failures at every backtest step. The strategies are well-implemented and satisfy all 16 requirement IDs at the signal generation level, but the backtesting integration loop is broken.

**What is working:**
- All 16 strategy files exist, are substantive (230-410 lines each), and register correctly in StrategyRegistry
- All 16 strategies use `@StrategyRegistry.register` decorator correctly
- `StrategySignal` outputs include `z_score`, `entry_level` (or None), `stop_loss` (or None), `take_profit` (or None) per the dataclass schema
- 108 unit tests across 4 test files all pass
- Total strategy count in registry is 24 (8 existing + 16 new)
- `__init__.py` is properly organized with imports in Plan-grouped blocks

**What is broken:**
- `BacktestEngine.run()` calls `.keys()` on the `generate_signals()` return value; new strategies return `list[StrategySignal]` which has no `.keys()` method; the engine's `try/except` catches and logs this silently as `backtest_step_failed`
- No integration test verifies that actual trades are generated during backtesting
- Without the adapter fix, success criteria 4 ("pass backtesting with TransactionCostModel") and 5 ("backtests without error... produces a valid tearsheet") are not met in the meaningful sense

**Recommended fix:** Add a `_signals_to_weights(signals: list[StrategySignal]) -> dict[str, float]` method in `BacktestEngine` that converts `list[StrategySignal]` to `dict[instrument, suggested_size * direction_sign]` target weights. This single fix would unblock all 16 strategies for actual backtesting.

---

_Verified: 2026-02-22T17:40:32Z_
_Verifier: Claude (gsd-verifier)_
