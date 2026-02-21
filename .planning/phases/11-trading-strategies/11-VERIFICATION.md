---
phase: 11-trading-strategies
verified: 2026-02-21T22:00:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
gaps: []
---

# Phase 11: Trading Strategies Verification Report

**Phase Goal:** BaseStrategy abstraction and 8 initial trading strategies spanning rates, inflation, FX, cupom cambial, and sovereign risk — each consuming agent signals and producing tradeable positions
**Verified:** 2026-02-21T22:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | BaseStrategy ABC enforces StrategyConfig and generate_signals(as_of_date) contract on all subclasses | VERIFIED | `class BaseStrategy(abc.ABC)` with `@abc.abstractmethod generate_signals()`; StrategyConfig is `@dataclass(frozen=True)` with 9 fields; all 8 strategies implement the contract |
| 2 | signals_to_positions converts agent signals to StrategyPosition list respecting weight [-1,1], confidence [0,1], and position limits | VERIFIED | `signals_to_positions()` in `base.py` lines 134-208: clamps to max_position_size, scales by max_leverage; programmatic test confirms STRONG 0.8 confidence → weight=0.8 |
| 3 | RATES_BR_01 computes carry-to-risk at each DI curve tenor and goes long at optimal point when ratio exceeds threshold | VERIFIED | `rates_br_01_carry.py` lines 94-116: iterates adjacent tenor pairs, computes carry and annualized risk, selects optimal tenor by max ratio |
| 4 | RATES_BR_02 trades DI direction when gap between Taylor-implied rate and market pricing exceeds 100bps | VERIFIED | `rates_br_02_taylor.py` lines 122-155: computes Taylor rate = r_star + pi_e + alpha*(pi_e-pi_target) + beta*output_gap; gap_bps check at line 144 |
| 5 | Weight formula implements strength_base x confidence x max_size with STRONG=1.0, MODERATE=0.6, WEAK=0.3 | VERIFIED | `STRENGTH_MAP` in `base.py` lines 28-33; formula at line 176: `raw_weight = STRENGTH_MAP[strength] * signal.confidence * config.max_position_size` |
| 6 | NEUTRAL signals produce 50% scale-down of existing position weight | VERIFIED | `base.py` lines 170-174; programmatic test confirms existing_weight=0.6 → neutral_weight=0.3 |
| 7 | RATES_BR_03 trades DI 2Y-5Y slope (flattener/steepener) based on z-score vs rolling 252-day history | VERIFIED | `rates_br_03_slope.py`: computes 504d/1260d tenors, inner-joins histories, z-score at line 213, flattener/steepener logic at lines 280-295 |
| 8 | RATES_BR_04 fades DI-UST spread overshoot after large weekly UST moves via mean reversion | VERIFIED | `rates_br_04_spillover.py`: outer-join with ffill, weekly UST change at line 125 (`ust[-1] - ust[-5]`), spread z-score gating at lines 220-229 |
| 9 | INF_BR_01 trades breakeven inflation (DI_PRE minus NTN_B_REAL) when agent forecast diverges from market-implied inflation | VERIFIED | `inf_br_01_breakeven.py`: loads both curves, computes `nominal_rate - real_rate` at line 122, divergence_bps check at lines 208-218 |
| 10 | FX_BR_01 composites carry-to-risk (40%), BEER misalignment (35%), and flow score (25%) with regime adjustment | VERIFIED | `fx_br_01_carry_fundamental.py` lines 117-149: `composite = carry_score*0.40 + beer_score*0.35 + flow_score*0.25`; regime_scale at lines 147-149 |
| 11 | CUPOM_01 fades extreme z-scores in cupom cambial minus SOFR basis via mean reversion | VERIFIED | `cupom_01_cip_basis.py`: computes cupom = DI_1Y - UST_1Y, basis = cupom - sofr, z-score at line 161, mean reversion SHORT/LONG at lines 174-182 |
| 12 | SOV_BR_01 trades long-end DI and USDBRL based on fiscal dominance risk vs sovereign spread level | VERIFIED | `sov_br_01_fiscal_risk.py`: fiscal_risk score at `_compute_fiscal_risk()`, spread z-score at `_compute_spread_zscore()`, 2-position generation (DI + USDBRL) at lines 309-398 |
| 13 | ALL_STRATEGIES dict exports all 8 strategies by ID | VERIFIED | `__init__.py` lines 33-42: `ALL_STRATEGIES` with all 8 IDs; `python -c` check returns 8 entries and all IDs |
| 14 | All strategies handle missing data gracefully returning empty position lists | VERIFIED | Each strategy has early `return []` guard clauses for each missing data source; 136 tests passing including missing-data edge cases |

**Score:** 14/14 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/strategies/__init__.py` | Package exports and ALL_STRATEGIES registry | VERIFIED | 57 lines; exports all 8 strategy classes + base types + ALL_STRATEGIES |
| `src/strategies/base.py` | BaseStrategy ABC, StrategyConfig, StrategyPosition | VERIFIED | 225 lines; frozen StrategyConfig (9 fields), StrategyPosition dataclass, signals_to_positions engine |
| `src/strategies/rates_br_01_carry.py` | RATES_BR_01 Carry & Roll-Down strategy | VERIFIED | 177 lines; `RatesBR01CarryStrategy(BaseStrategy)` fully implemented |
| `src/strategies/rates_br_02_taylor.py` | RATES_BR_02 Taylor Rule Misalignment strategy | VERIFIED | 231 lines; `RatesBR02TaylorStrategy(BaseStrategy)` fully implemented |
| `src/strategies/rates_br_03_slope.py` | RATES_BR_03 Curve Slope strategy | VERIFIED | 339 lines; `RatesBR03SlopeStrategy(BaseStrategy)` fully implemented |
| `src/strategies/rates_br_04_spillover.py` | RATES_BR_04 US Rates Spillover strategy | VERIFIED | 274 lines; `RatesBR04SpilloverStrategy(BaseStrategy)` fully implemented |
| `src/strategies/inf_br_01_breakeven.py` | INF_BR_01 Breakeven Inflation Trade strategy | VERIFIED | 269 lines; `InfBR01BreakevenStrategy(BaseStrategy)` fully implemented |
| `src/strategies/fx_br_01_carry_fundamental.py` | FX_BR_01 Carry & Fundamental composite strategy | VERIFIED | 316 lines; `FxBR01CarryFundamentalStrategy(BaseStrategy)` fully implemented |
| `src/strategies/cupom_01_cip_basis.py` | CUPOM_01 CIP Basis Mean Reversion strategy | VERIFIED | 246 lines; `Cupom01CipBasisStrategy(BaseStrategy)` fully implemented |
| `src/strategies/sov_br_01_fiscal_risk.py` | SOV_BR_01 Fiscal Risk Premium strategy | VERIFIED | 402 lines; `SovBR01FiscalRiskStrategy(BaseStrategy)` fully implemented |
| `tests/test_strategies/test_base.py` | Tests for BaseStrategy ABC (min 60 lines) | VERIFIED | 404 lines; 27 tests covering frozen config, weight formula, clamping, leverage, ABC enforcement |
| `tests/test_strategies/test_rates_br_01.py` | Tests for RATES_BR_01 | VERIFIED | 8 tests: LONG/SHORT/neutral/edge cases/bounds |
| `tests/test_strategies/test_rates_br_02.py` | Tests for RATES_BR_02 | VERIFIED | 16 tests: SHORT/LONG/neutral/missing data/bounds/custom threshold/tenor finding |
| `tests/test_strategies/test_rates_br_03.py` | Tests for RATES_BR_03 (min 40 lines) | VERIFIED | 295 lines, 11 tests: flattener/steepener/neutral/missing data/bounds |
| `tests/test_strategies/test_rates_br_04.py` | Tests for RATES_BR_04 (min 40 lines) | VERIFIED | 224 lines, 9 tests: overshoot/undershoot/small UST move/missing data/bounds |
| `tests/test_strategies/test_inf_br_01.py` | Tests for INF_BR_01 (min 40 lines) | VERIFIED | 270 lines, 14 tests: long/short/neutral/missing data/bounds/custom threshold |
| `tests/test_strategies/test_fx_br_01.py` | Tests for FX_BR_01 (min 50 lines) | VERIFIED | 457 lines, 23 tests: carry/BEER/flow components, direction, regime, bounds, missing data |
| `tests/test_strategies/test_cupom_01.py` | Tests for CUPOM_01 (min 40 lines) | VERIFIED | 257 lines, 12 tests: short/long basis, neutral, missing data, bounds, config |
| `tests/test_strategies/test_sov_br_01.py` | Tests for SOV_BR_01 (min 40 lines) | VERIFIED | 318 lines, 16 tests: high/low risk+spread combos, neutral cases, fiscal risk scoring, bounds |

---

### Key Link Verification

All key links verified against actual codebase.

**Plan 01 Key Links:**

| From | To | Via | Status | Evidence |
|------|----|-----|--------|---------|
| `src/strategies/base.py` | `src/agents/base.py` | `from src.agents.base import AgentSignal` | WIRED | Line 22 of base.py; `AgentSignal` used throughout `signals_to_positions()` |
| `src/strategies/base.py` | `src/core/enums.py` | `from src.core.enums import AssetClass, Frequency, SignalDirection, SignalStrength` | WIRED | Line 23 of base.py; all four enums actively used |
| `src/strategies/rates_br_01_carry.py` | `src/strategies/base.py` | `class RatesBR01CarryStrategy(BaseStrategy)` | WIRED | Line 40 of rates_br_01_carry.py |
| `src/strategies/rates_br_02_taylor.py` | `src/strategies/base.py` | `class RatesBR02TaylorStrategy(BaseStrategy)` | WIRED | Line 42 of rates_br_02_taylor.py |

**Plan 02 Key Links:**

| From | To | Via | Status | Evidence |
|------|----|-----|--------|---------|
| `src/strategies/rates_br_03_slope.py` | `src/strategies/base.py` | `class RatesBR03SlopeStrategy(BaseStrategy)` | WIRED | Line 53 of rates_br_03_slope.py |
| `src/strategies/rates_br_04_spillover.py` | `src/strategies/base.py` | `class RatesBR04SpilloverStrategy(BaseStrategy)` | WIRED | Line 49 of rates_br_04_spillover.py |
| `src/strategies/inf_br_01_breakeven.py` | `src/strategies/base.py` | `class InfBR01BreakevenStrategy(BaseStrategy)` | WIRED | Line 51 of inf_br_01_breakeven.py |
| `src/strategies/rates_br_04_spillover.py` | `src/agents/data_loader.py` | `data_loader.get_curve_history` | WIRED | Lines 95 and 103 of rates_br_04_spillover.py |

**Plan 03 Key Links:**

| From | To | Via | Status | Evidence |
|------|----|-----|--------|---------|
| `src/strategies/fx_br_01_carry_fundamental.py` | `src/strategies/base.py` | `class FxBR01CarryFundamentalStrategy(BaseStrategy)` | WIRED | Line 48 of fx_br_01_carry_fundamental.py |
| `src/strategies/cupom_01_cip_basis.py` | `src/strategies/base.py` | `class Cupom01CipBasisStrategy(BaseStrategy)` | WIRED | Line 46 of cupom_01_cip_basis.py |
| `src/strategies/sov_br_01_fiscal_risk.py` | `src/strategies/base.py` | `class SovBR01FiscalRiskStrategy(BaseStrategy)` | WIRED | Line 45 of sov_br_01_fiscal_risk.py |
| `src/strategies/__init__.py` | all strategy modules | `ALL_STRATEGIES = {...}` | WIRED | Lines 33-42 of `__init__.py`; dict maps all 8 IDs to classes |

---

### Requirements Coverage

All 9 requirement IDs declared across the three plans are accounted for and satisfied.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| STRAT-01 | 11-01 | BaseStrategy ABC with StrategyConfig and generate_signals(as_of_date) → list[StrategyPosition] | SATISFIED | `base.py`: frozen StrategyConfig (9 fields), `@abc.abstractmethod generate_signals()`, StrategyPosition dataclass |
| STRAT-02 | 11-01 | RATES_BR_01 Carry & Roll-Down — carry-to-risk at optimal DI curve tenor | SATISFIED | `rates_br_01_carry.py`: tenor-by-tenor carry/risk computation, threshold-based LONG/SHORT |
| STRAT-03 | 11-01 | RATES_BR_02 Taylor Rule Misalignment — trade DI when Selic vs Taylor-implied gap exceeds threshold | SATISFIED | `rates_br_02_taylor.py`: full Taylor formula (r_star=4.5%, alpha=1.5, beta=0.5), 100bps threshold |
| STRAT-04 | 11-02 | RATES_BR_03 Curve Slope — flattener/steepener on DI 2Y-5Y based on monetary cycle | SATISFIED | `rates_br_03_slope.py`: 252d z-score, Selic cycle detection, flattener/steepener logic |
| STRAT-05 | 11-02 | RATES_BR_04 US Rates Spillover — fade DI-UST spread overshoot after large UST weekly moves | SATISFIED | `rates_br_04_spillover.py`: outer-join+ffill, 15bps weekly UST gate, spread z-score mean reversion |
| STRAT-06 | 11-02 | INF_BR_01 Breakeven Inflation — trade when agent forecast diverges from market-implied breakeven | SATISFIED | `inf_br_01_breakeven.py`: DI_PRE minus NTN_B_REAL, Focus IPCA vs breakeven, 50bps threshold |
| STRAT-07 | 11-03 | FX_BR_01 Carry & Fundamental — composite of carry (40%), BEER (35%), flow (25%) with regime | SATISFIED | `fx_br_01_carry_fundamental.py`: tanh-normalized carry, 252d rolling mean BEER, flow z-score, regime_scale |
| STRAT-08 | 11-03 | CUPOM_01 CIP Basis Mean Reversion — fade extreme cupom cambial minus SOFR z-scores | SATISFIED | `cupom_01_cip_basis.py`: DI_1Y - UST_1Y - SOFR basis, 252d rolling z-score, 2.0 threshold |
| STRAT-09 | 11-03 | SOV_BR_01 Fiscal Risk Premium — long-end DI and USDBRL based on fiscal dominance vs spread | SATISFIED | `sov_br_01_fiscal_risk.py`: debt-to-GDP + balance risk score, spread z-score, 1-2 positions |

**Orphaned requirements check:** REQUIREMENTS.md maps all STRAT-01 through STRAT-09 to Phase 11. No orphaned requirement IDs found.

---

### Anti-Patterns Found

Scan conducted on all 9 strategy source files.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| All strategy files | Various | `return []` in guard clauses | INFO | Legitimate: specified behavior for missing data, not stubs |

No TODO/FIXME/PLACEHOLDER/stub patterns detected. All `return []` occurrences are deliberate guard clauses for missing data scenarios, as required by the plan specification. No empty implementations detected.

---

### Human Verification Required

None. All observable truths for this phase can be verified programmatically:

- Strategy inheritance, weight formulas, and constraint enforcement were verified by running the test suite (136/136 passing).
- The ALL_STRATEGIES registry was confirmed via `python -c` import check.
- Key links were confirmed via grep against actual source files.
- Commits were confirmed in git history.

No visual UI, real-time behavior, or external service integration is required for this phase.

---

### Test Suite Summary

| Test File | Tests | Result |
|-----------|-------|--------|
| test_base.py | 27 | PASSED |
| test_rates_br_01.py | 8 | PASSED |
| test_rates_br_02.py | 16 | PASSED |
| test_rates_br_03.py | 11 | PASSED |
| test_rates_br_04.py | 9 | PASSED |
| test_inf_br_01.py | 14 | PASSED |
| test_fx_br_01.py | 23 | PASSED |
| test_cupom_01.py | 12 | PASSED |
| test_sov_br_01.py | 16 | PASSED |
| **Total** | **136** | **ALL PASSED** |

Lint check: `ruff check src/strategies/ tests/test_strategies/` → All checks passed (zero errors).

---

### Gaps Summary

No gaps. All must-haves from all three plans are verified. The phase goal is fully achieved:

- BaseStrategy ABC is implemented as a proper abstract base class — cannot be instantiated directly, enforces `generate_signals()` on subclasses.
- The signals_to_positions constraint engine implements the locked formula exactly as specified.
- All 8 trading strategies are implemented with substantive logic (not stubs), tested, and registered in ALL_STRATEGIES.
- The coverage spans the full required domain: BR rates (4 strategies), inflation (1), FX (1), cupom cambial cross-currency basis (1), and sovereign risk (1).

---

*Verified: 2026-02-21T22:00:00Z*
*Verifier: Claude (gsd-verifier)*
