# Domain Pitfalls: v2.0 Quantitative Models & Agents

**Domain:** Global macro fund -- analytical agents, backtesting, strategies, risk management
**Researched:** 2026-02-20
**Confidence:** HIGH (pitfalls verified across academic literature, practitioner post-mortems, official documentation, and codebase inspection)

## Critical Pitfalls

Mistakes that cause rewrites, invalid backtests, or dangerous production behavior.

### Pitfall 1: Look-Ahead Bias in Agent Computations

**What goes wrong:** Agent models accidentally use data that was not available at the as_of_date. This is the single most destructive error in quantitative trading systems.

**Why it happens:**
- Developer queries `macro_series` by `observation_date` column instead of filtering on `release_time`
- Feature computation uses pandas operations that look forward (e.g., `shift(-1)`, future-dated rolling windows)
- Agent loads "latest" data without checking publication lag
- Brazilian macro data has variable release lags: IPCA ~15 days, GDP ~90 days, Focus survey is weekly but published Monday for the prior week
- The v1.0 `_bulk_insert` in `src/connectors/base.py` (line 277) uses `ON CONFLICT DO NOTHING`, which silently drops revised data points. If a series is revised (GDP, employment), only the first-seen revision persists. The agent then uses a stale value without knowing a revision exists.

**Codebase-specific risk:** The `MacroSeries` model (`src/core/models/macro_series.py`) correctly has `release_time` (TIMESTAMPTZ) and `revision_number` columns. However, no v1.0 code enforces PIT queries -- there is no `PointInTimeDataLoader` class yet. Every v2.0 agent MUST use a centralized data loader that enforces `WHERE release_time <= :as_of_date AND revision_number = (SELECT MAX(revision_number) ... WHERE release_time <= :as_of_date)`.

**Consequences:** Backtests show fantasy returns. Strategies appear profitable because they "knew" inflation/GDP numbers before publication. Real trading produces opposite results.

**Prevention:**
1. ALL data access goes through `PointInTimeDataLoader` -- the single enforcement point
2. Every query includes `WHERE release_time <= :as_of_date`
3. Integration test: run agent for date X, then verify no data with `release_time > X` was loaded
4. For revised series, use `MAX(revision_number) WHERE release_time <= :as_of_date` (the latest revision known at that time)
5. Change `_bulk_insert` to use `ON CONFLICT DO UPDATE` for macro_series so revised data replaces stale data when `revision_number` is higher

**Detection:** Backtest Sharpe ratio > 2.0 for a macro strategy is a red flag. Real macro strategies rarely exceed Sharpe 1.0-1.5 out-of-sample.

### Pitfall 2: Kalman Filter Convergence Failures

**What goes wrong:** The Laubach-Williams r-star Kalman Filter fails to converge, produces exploding parameter estimates, or generates nonsensical neutral rate values.

**Why it happens:**
- **No official Python implementation.** The NY Fed provides R code only. Python translation introduces bugs in matrix operations.
- **Matrix positive-definiteness errors.** The covariance matrix P can lose positive-definiteness during the update step due to floating point arithmetic, causing `np.linalg.cholesky` to fail.
- **Exploding parameters.** If the process noise Q is too large relative to observation noise R, the filter "trusts" noisy observations too much and r-star oscillates wildly.
- **COVID shock sensitivity.** The 2020 GDP collapse produces extreme output gap values that dominate the MUE (Median Unbiased Estimator) three-stage procedure, distorting r-star for years.
- **End-point instability.** Kalman filter estimates are most uncertain at the end of the sample -- exactly where you need them for trading decisions. The NY Fed itself notes a +/-2.5pp confidence interval on r-star.
- **MUE three-stage misspecification.** The Laubach-Williams model uses a three-stage estimation procedure where errors compound: stage 1 estimates feed stage 2, which feeds stage 3.

**Consequences:** Taylor Rule produces wrong implied rate. Monetary agent gives confident but incorrect signals. Strategies based on "policy gap" trade in the wrong direction.

**Prevention:**
1. **Start with fixed r-star.** Use r* = 4.5% for Brazil (BCB consensus) and r* = 0.5% for US (pre-COVID median estimate). Only upgrade to Kalman Filter if fixed r* signals are validated out-of-sample.
2. **Joseph stabilized Kalman Filter.** Force P matrix symmetry after each update: `P = (P + P.T) / 2`. Add small epsilon to diagonal: `P += 1e-8 * np.eye(n)`.
3. **Bound r-star output.** Clamp to [1%, 8%] for Brazil, [-1%, 4%] for US. Values outside these ranges are almost certainly estimation artifacts.
4. **Exclude COVID period.** Either dummy-variable the 2020 Q2-Q4 observations or exclude them from the estimation window entirely.
5. **Use `statsmodels.tsa.statespace.UnobservedComponents`** rather than manual Kalman Filter implementation. It handles numerical stability internally.

**Detection:** r-star estimate jumping by >100bps between adjacent quarters, or values outside economically plausible ranges.

### Pitfall 3: HMM Regime Detection Instability

**What goes wrong:** The Hidden Markov Model produces unstable regime classifications that flip frequently, overfit to in-sample data, or produce meaningless labels.

**Why it happens:**
- **Label switching problem.** HMM states are arbitrary (State 0, State 1, ...). After each re-estimation, "State 0" may correspond to a different regime than before. hmmlearn does NOT solve this automatically.
- **Overfitting with too many states.** Using 4 states (Goldilocks, Reflation, Stagflation, Deflation) when the data only supports 2-3 regimes. BIC/AIC model selection often favors fewer states for macro time series.
- **No ground truth.** Unlike supervised learning, there is no "correct" regime label. The HMM finds statistical patterns that may not correspond to economically meaningful regimes.
- **Sensitive to initialization.** Different random seeds produce different regime assignments.
- **Filtered vs Viterbi probabilities.** `predict()` returns Viterbi (globally optimal) labels, but for real-time use you need forward-filtered probabilities. The Viterbi path can change retroactively when new data arrives -- this is a form of look-ahead bias in backtests.
- **Short training window.** Macro data at monthly frequency gives ~120-180 observations for 10-15 years. This is barely sufficient for estimating 4-state HMM parameters (4 means + 4 variances + 12 transition probabilities = 20 parameters from 180 observations).

**Consequences:** Position sizing based on unstable regime labels whipsaws between max risk and zero risk. Backtest looks smooth because Viterbi retroactively picks the "right" regimes.

**Prevention:**
1. **Start with rule-based regime detection.** Use z-scores of VIX, credit spreads, DXY, and yield curve slope. Score each -1 to +1, weighted average. Thresholds: >0.3 = risk-on, <-0.3 = risk-off, else transition. This is transparent, stable, and debuggable.
2. **If using HMM, use 2 states first** (risk-on / risk-off). Only add states if 2-state model clearly misses important dynamics.
3. **Fix label switching.** After fitting, sort states by mean return (State 0 = lowest mean = risk-off). Re-sort every time you re-estimate.
4. **Use filtered probabilities, not Viterbi.** `model.predict_proba(X)` gives forward-filtered state probabilities. Use these as continuous regime weights, not hard labels.
5. **Re-estimate infrequently.** Re-fit HMM quarterly, not daily. Use fixed parameters for daily regime scoring.
6. **Parallel fallback.** Always compute the rule-based z-score regime alongside HMM. If they disagree strongly, flag it as low confidence.

**Detection:** Regime flipping more than once per month. Backtest Sharpe of regime-overlay strategy drops >50% when switching from Viterbi to filtered probabilities.

### Pitfall 4: Overfitting Agent Models to In-Sample Data

**What goes wrong:** Agent models (Phillips Curve, BEER, DSA) are calibrated on the same data used for backtesting, producing inflated performance metrics.

**Why it happens:**
- **Parsimony principle violation.** Using 8+ regressors in a Phillips Curve when 3-4 suffice. The OLS R-squared looks great in-sample but the model has no predictive power out-of-sample.
- **Rolling window too short.** A 2-year rolling window for OLS regression gives only 24 monthly observations for 4+ parameters. The estimates are highly unstable.
- **No out-of-sample validation.** Running backtest on 2015-2025 with models trained on 2015-2025 is not a real test.
- **Data snooping across 25 strategies.** Testing 25 strategy variants and selecting those with best Sharpe. Harvey, Liu & Zhu (2016) show that with 300+ tested factors in academic finance, the probability of finding a spurious Sharpe > 1.0 by chance approaches 100%. With 25 strategies, the false discovery rate is still significant.
- **BEER model structural breaks.** The BRL-to-fundamentals relationship broke down in 2024 when BRL depreciated 27% despite record terms of trade -- a fiscal regime shift invalidated the equilibrium. Rolling OLS cannot capture this.

**Consequences:** Strategies based on overfit agent signals generate strong backtest returns but fail in production. Worse, overfit models can give confidently wrong signals.

**Prevention:**
1. **Parsimony first.** Start with the simplest model specification (2-3 features). Add complexity only if it improves out-of-sample performance.
2. **10-year rolling windows for OLS.** This gives 120+ monthly observations, which is adequate for 3-4 parameter models. For Brazil-specific models with data from 2006+, use maximum available history.
3. **Walk-forward validation.** Train on 2010-2018, test on 2019. Then train on 2010-2019, test on 2020. Compare in-sample and out-of-sample Sharpe.
4. **Deflated Sharpe Ratio.** Apply Bailey & Lopez de Prado (2014) haircut based on number of strategy variants tested. A backtest Sharpe of 0.8 after deflation is more valuable than 1.5 before deflation.
5. **Sanity-check model coefficients.** Phillips Curve: inflation should be positively correlated with output gap. BEER: BRL should appreciate when terms of trade improve. If signs are wrong, the model is overfit.

**Detection:** In-sample Sharpe > 2x out-of-sample Sharpe. Model coefficients changing sign between rolling windows. R-squared > 0.6 for a macro model (suspiciously high).

### Pitfall 5: DI Curve Day Count Convention Errors (BUS/252 vs ACT/365)

**What goes wrong:** Brazilian fixed income uses business-day/252 convention for rate annualization and discounting, but the codebase uses calendar-day/365 convention throughout, producing incorrect curve interpolation, carry calculations, forward rates, and DV01 values.

**Codebase evidence:**
- `src/transforms/curves.py` line 45: `obs_years = np.array(observed_tenors_days) / 365.0` -- should be BUS/252 for DI curves
- `src/transforms/curves.py` line 75: `y1 = t1_days / 365.0` in forward rate calculation -- wrong for DI
- `src/transforms/curves.py` line 98: `carry_bps = ... * (horizon_days / 365.0)` -- wrong for DI carry
- `src/transforms/returns.py` line 18: `returns.rolling(w).std() * np.sqrt(252)` -- uses 252 for annualization but this is hardcoded and may be wrong for instruments that trade fewer days (ANBIMA calendar has ~249 business days per year)
- `src/transforms/returns.py` line 52: Rolling Sharpe also hardcodes `* 252` and `* np.sqrt(252)`

**Why it matters:** A 1-year DI future at 13.50% annual rate:
- With BUS/252: price = 100,000 / (1.1350)^(252/252) = 88,106
- With ACT/365: price = 100,000 / (1.1350)^(365/365) = 88,106 (same at 1Y by coincidence)
- But at 6 months: BUS/252 with 126 bus days vs ACT/365 with 182 calendar days produces different prices, DV01s, and carry calculations.

**Additionally:** The `compute_forward_rate` function uses simple compounding (line 77: `(r2*y2 - r1*y1) / (y2-y1)`) instead of the Brazilian convention of exponential compounding: `f = [(1+r2)^y2 / (1+r1)^y1]^(1/(y2-y1)) - 1`.

**Prevention:**
1. Create separate curve functions for Brazilian instruments (`compute_di_forward_rate_bus252`) and US instruments (`compute_ust_forward_rate_act365`)
2. The `interpolate_curve` function should accept a `day_count` parameter: `"BUS252"` or `"ACT365"`
3. Tenor-to-year conversion should use a business day calendar for Brazilian instruments, not a fixed divisor
4. Store the day count convention in `series_metadata` or `instruments` table and look it up at computation time

**Detection:** Carry/rolldown calculations for DI futures are off by 5-15% compared to Bloomberg or B3 official values.

### Pitfall 6: LLM Hallucination in Narrative Generation

**What goes wrong:** Claude API generates plausible-sounding but factually incorrect macro analysis. The narrative contradicts the actual signals, invents data points, or provides analysis that doesn't follow from the inputs.

**Why it happens:**
- LLMs are trained to produce fluent text, not to accurately represent structured data. Research (2024-2025) shows financial LLM hallucination rates of 17-41% without grounding.
- The prompt may not include sufficient context for the model to generate accurate analysis
- The model may "fill in" details that seem reasonable but are not in the data
- Temperature > 0 introduces randomness that can flip conclusions
- LLMs have a known tendency to generate plausible numbers that are not sourced from input data

**Consequences:** Misleading daily brief that contradicts the quantitative signals. If a human reads the narrative and overrides the model, the LLM became a negative-value component.

**Prevention:**
1. **Template-based fallback is the primary output.** Build a complete rule-based narrative generator that fills in blanks from signal values. This is the default.
2. **LLM is enhancement, not replacement.** If Claude API is available, use it to improve prose quality on top of the template output. Never let LLM generate numbers or signal directions.
3. **Verify LLM output against signals.** Post-process: check that the narrative's directional language matches the actual signal directions. Reject if contradictory.
4. **Low temperature (0.2-0.3).** Reduce randomness in factual generation.
5. **Structured prompt with explicit data.** Pass exact signal values, directions, and confidence scores in the prompt. Instruct: "Base your analysis ONLY on the provided data. Do not invent numbers."
6. **Never call LLM during backtesting.** LLM calls are non-deterministic, slow, and expensive. The backtest loop must use only deterministic signal generation.

**Detection:** Narrative says "inflation is falling" when INFLATION_BR_COMPOSITE direction is SHORT (meaning inflation is rising/hawkish). Any number in the narrative that doesn't match the input data.

**Cost management:** Claude Haiku is $0.80/MTok input for daily narrative generation. Use prompt caching (90% cost reduction for repeated system prompts). Budget ~$15-30/month for daily narratives. Sonnet ($3/MTok) only for weekly deep-dive reports.

## Moderate Pitfalls

### Pitfall 7: Backtest Transaction Cost Underestimation

**What goes wrong:** Backtests assume negligible or uniform transaction costs for macro instruments that actually have heterogeneous and time-varying bid-ask spreads, particularly in Brazil.

**Why it matters:** Brazilian OTC instruments (NTN-B, NTN-F) have 3-5x wider spreads than exchange-traded DI futures. A strategy that looks profitable at 2bps round-trip may be unprofitable at the real 10-15bps for NTN-B OTC trades.

**Instrument-specific costs (approximate):**

| Instrument | Spread (bps) | Commission | Total One-Way | Notes |
|-----------|-------------|-----------|--------------|-------|
| DI1 futures (B3) | 0.5-1.0 | 0.3 | 1.0-1.5 | Liquid front months |
| DDI futures (B3) | 1.0-2.0 | 0.3 | 1.5-2.5 | Less liquid |
| USDBRL NDF (OTC) | 2.0-3.0 | 0.0 | 2.0-3.0 | Dealer spread |
| NTN-B (OTC) | 3.0-5.0 | 0.0 | 3.0-5.0 | Illiquid long-end |
| DOL futures (B3) | 0.3-0.5 | 0.3 | 0.8-1.0 | Very liquid |
| CDS Brazil (OTC) | 5.0-10.0 | 0.0 | 5.0-10.0 | Illiquid |

**Prevention:**
- Use instrument-specific cost models, not a single flat rate
- Default to 5 bps round-trip for exchange-traded, 10 bps for OTC
- Add 2 bps market impact/slippage on top of spread
- Strategies with monthly rebalancing are less sensitive to cost assumptions than daily/weekly strategies
- Validate cost assumptions against real execution data when available

### Pitfall 8: Feature Engineering Data Leakage

**What goes wrong:** Feature computation inadvertently uses future data through pandas operations, separate from the PIT data loading issue (Pitfall 1). Even with correct PIT data loading, the feature engineering step itself can introduce look-ahead.

**Common leakage patterns:**
- `df.fillna(method='bfill')` -- fills missing values with FUTURE values
- `df.interpolate()` -- default linear interpolation uses both past and future
- `rolling().mean()` is safe (backward-looking), but `shift(-N)` is NOT safe
- `z_score = (x - rolling_mean) / rolling_std` is safe only if the rolling window is fully backward-looking and the window parameter does not use `center=True`
- Normalizing features by full-sample mean/std (should be expanding-window or rolling-window only)
- Using `df.pct_change()` followed by `dropna()` shifts the index, causing alignment errors with other features

**Prevention:**
- Never use `bfill`, `shift(-N)`, or `center=True` in any feature computation
- Test: compute features for date X, then verify that no input data has date > X
- Use `expanding()` instead of full-sample statistics for normalization
- Every feature function should take an explicit `as_of_date` parameter

### Pitfall 9: Agent Signal Correlation Causing Portfolio Concentration

**What goes wrong:** All 5 agents produce correlated signals because they share underlying macro data (e.g., IPCA feeds both InflationAgent and MonetaryPolicyAgent; USDBRL feeds both FxAgent and CrossAssetAgent). The portfolio concentrates in one direction without diversification.

**Why it is worse than it appears:** In normal markets, signal correlation is moderate (0.3-0.5). During crises, correlations spike toward 1.0 -- exactly when diversification is needed most. The portfolio goes from "diversified 5 signals" to "one bet, 5x leveraged."

**Codebase-specific risk:** The v1.0 `Signal` model (`src/core/models/signals.py` line 44) has `confidence: Mapped[Optional[float]]` -- confidence is nullable. If an agent fails to compute confidence and stores NULL, the signal aggregation layer cannot properly weight it. NULL confidence should never be allowed for v2.0 signals; it must default to 0.0 (no signal) or the agent must not emit the signal.

**Prevention:**
- Signal aggregation applies crowding penalty when >80% of strategies agree (reduce position sizes 30-50%)
- CrossAssetAgent explicitly monitors agent agreement and flags when all signals point the same way
- Portfolio construction enforces max position weights (25% single instrument, 50% single asset class)
- Schema migration: make `confidence` NOT NULL with DEFAULT 0.0 for v2.0 signals table
- Add `agent_id` and `horizon_days` columns to signals table for v2.0 agent framework

### Pitfall 10: Confusion Between Nominal and Real Rates

**What goes wrong:** Mixing nominal DI rates with real NTN-B rates in calculations. Computing breakeven inflation incorrectly. Comparing Brazilian % rates (annualized, BUS/252 convention) with US % rates (annualized, ACT/360 or ACT/365 convention).

**Specific errors:**
- Breakeven inflation = DI_PRE - NTN_B_REAL is only valid at MATCHING tenors. If tenors do not align, rates must be interpolated first. The `compute_breakeven_inflation` function in `src/transforms/curves.py` (line 63-66) correctly handles matching tenors, but does not interpolate when tenors mismatch.
- Brazilian rate convention: `(1 + annual_rate) = (1 + daily_rate)^252`. This is exponential compounding. US Treasury uses semi-annual compounding for bond yields and continuous compounding for some derivatives.
- Comparing "13.50% Selic" with "5.25% Fed Funds" is misleading without adjusting for inflation differential. The real rate comparison is what matters.

**Prevention:**
- All rates stored in database as decimal (0.1350 = 13.50%)
- Day count conventions documented per instrument in code comments
- Breakeven = nominal - real at MATCHING tenors (interpolate if needed)
- Add a `compounding_convention` field to instruments table: `"BUS252_EXPONENTIAL"`, `"ACT365_SIMPLE"`, `"SEMI_ANNUAL"`
- Brazilian rate convention: `(1 + annual_rate) = (1 + daily_rate)^252`

### Pitfall 11: COPOM Meeting Calendar Hardcoding

**What goes wrong:** COPOM meets 8 times per year on non-fixed dates (unlike the FOMC which has a more predictable schedule). Hardcoding meeting dates that change year-to-year causes the Selic Path Model and event strategies to trigger on wrong dates.

**Why it matters for v2.0:** The MonetaryPolicyAgent Selic Path Model extracts meeting-by-meeting implied Selic from the DI curve. If the meeting dates are wrong, the extraction assigns rates to wrong dates, and the "policy surprise" signal fires when there is no meeting.

**Prevention:**
- BCB publishes the annual COPOM calendar in December for the following year
- Store meeting dates in a config file or database table, updated annually
- The MonetaryPolicyAgent should load meeting dates dynamically, not hardcode them
- For FOMC: similarly use the published Fed calendar, not hardcoded dates
- Validate: if today is in the COPOM window [-5, +2] days, verify by checking the calendar table

### Pitfall 12: VaR Underestimation During Regime Changes

**What goes wrong:** Historical VaR computed during calm periods dramatically underestimates tail risk. The 504-day (2-year) lookback window may not contain a crisis period, producing falsely low VaR that encourages overleveraging.

**Why it matters:** Brazilian assets exhibit fat tails and volatility clustering. USDBRL realized vol ranges from 8% (calm) to 35% (crisis). A VaR model calibrated during calm period will be 3-4x too optimistic.

**Prevention:**
- Use 504-day window (2 years) as minimum to capture at least one stress episode
- Supplement with stress VaR: always compute VaR under historical stress scenarios (2015 BR crisis, 2020 COVID, 2022 rate shock) even when recent history is calm
- Use GARCH(1,1) or EWMA for volatility to give more weight to recent observations
- Consider DCC (Dynamic Conditional Correlation) instead of static correlation for multi-asset VaR
- Set VaR limits conservatively: if VaR(95%, 1d) limit is 2% of NAV, the actual tail loss in a crisis will be 3-5x that

## Minor Pitfalls

### Pitfall 13: Matplotlib Thread Safety in FastAPI

**What goes wrong:** BacktestReport generates matplotlib charts. If multiple API requests trigger chart generation simultaneously, matplotlib's global state causes crashes or corrupted images.

**Prevention:** Use `matplotlib.use('Agg')` (non-interactive backend) at import time. Generate charts in a thread-safe manner: create new figure per request, close immediately after saving to bytes. Consider switching to Plotly for API-served charts (JSON serializable, no global state).

### Pitfall 14: Agent Report Narrative Encoding

**What goes wrong:** Portuguese characters in BCB Focus series names or IPCA component names (e.g., "Alimentacao e bebidas", "Habitacao") cause encoding errors when persisting to database or generating JSON responses.

**Prevention:** All strings UTF-8. Database columns use `Text` type (no length limit). FastAPI default JSON serialization handles Unicode correctly. Test with actual Portuguese-character series names.

### Pitfall 15: Backtest Date Range Off-by-One

**What goes wrong:** Backtest starts on 2015-01-01 (a holiday -- Confraternizacao Universal). First rebalance date is wrong, or the engine skips January entirely.

**Prevention:** Use `next_business_day()` from the existing `date_utils.py` to snap start/end dates to valid business days. The BR+US combined holiday calendar from v1.0 already handles this. The backtest engine must also handle the case where a rebalance date falls on a BR holiday but not a US holiday (or vice versa) -- use the union of both calendars.

## Codebase-Specific Issues for v2.0

Issues found in v1.0 code that will cause problems when building v2.0 agents, backtesting, and strategies.

| File | Line(s) | Issue | Impact | Fix |
|------|---------|-------|--------|-----|
| `src/transforms/curves.py` | 45, 47, 75, 98 | Uses `/ 365.0` for year fractions | Wrong DI curve math, carry, forwards | Add `day_count` parameter; use BUS/252 for Brazilian instruments |
| `src/transforms/curves.py` | 77 | Simple compounding for forward rates | Wrong for DI (exponential compounding) | Implement `(1+r2)^y2 / (1+r1)^y1` formula |
| `src/transforms/returns.py` | 18, 52, 67 | Hardcoded `np.sqrt(252)` annualization | ~1% error for ANBIMA calendar (249 biz days) | Parameterize annualization factor; use calendar-aware count |
| `src/core/models/signals.py` | 44 | `confidence` is `Optional[float]` (nullable) | Signal aggregation breaks on NULL confidence | Make NOT NULL, DEFAULT 0.0; add `agent_id`, `horizon_days` columns |
| `src/connectors/base.py` | 277 | `ON CONFLICT DO NOTHING` for all inserts | Silently drops data revisions (GDP, employment) | Use `ON CONFLICT DO UPDATE` for macro_series when revision_number is higher |
| `src/core/models/signals.py` | 47-51 | Natural key is `(signal_type, signal_date, instrument_id)` | v2.0 needs `agent_id` in the key (same signal_type from different agents) | Add `agent_id` to unique constraint |
| `src/transforms/curves.py` | 63-66 | Breakeven only at matching tenors | Mismatched NTN-B / DI tenors produce no BEI | Interpolate both curves to common tenor grid before computing BEI |

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Severity | Mitigation |
|-------------|---------------|----------|------------|
| Agent Framework (Phase 7) | PIT enforcement gaps in DataLoader | CRITICAL | Integration test: verify no future data leaks for every agent |
| Agent Framework (Phase 7) | Signal schema missing `agent_id`, `horizon_days` | MODERATE | Schema migration before building agents |
| Inflation Agent (Phase 7) | Phillips Curve overfitting with 8+ regressors | CRITICAL | Start with 3 features, 10-year window, validate coefficient signs |
| Inflation Agent (Phase 7) | IPCA component weights from IBGE change yearly | MODERATE | Load weights from database, not hardcoded |
| Monetary Agent (Phase 8) | Kalman Filter divergence for r-star | CRITICAL | Start with fixed r*=4.5% (BR), add KF only if validated OOS |
| Monetary Agent (Phase 8) | COPOM calendar hardcoding | MODERATE | Store in config/database, load dynamically |
| FX Agent (Phase 8) | BEER model coefficient instability / regime breaks | CRITICAL | Rolling OLS with 10-year window, check sign stability; add fiscal dummy |
| Cross-Asset Agent (Phase 8) | HMM label switching / overfitting | CRITICAL | Start rule-based, add HMM as parallel check only |
| Backtesting (Phase 9) | Look-ahead bias in backtest loop | CRITICAL | Verify: strategy never sees data after as_of_date |
| Backtesting (Phase 9) | DI curve BUS/252 vs ACT/365 in carry calculation | MODERATE | Fix curves.py before backtesting DI strategies |
| Strategies (Phase 10) | Signal correlation / portfolio concentration | MODERATE | Crowding penalty + position limits in aggregation |
| Strategies (Phase 10) | 25 strategies data-snooped, inflated Sharpe | CRITICAL | Deflated Sharpe Ratio for all reported metrics |
| Risk Management (Phase 11) | VaR underestimation in calm periods | MODERATE | Use 504-day window + stress VaR + GARCH vol |
| Daily Pipeline (Phase 12) | Pipeline failure cascading to stale signals | MODERATE | Each step independent; partial failures logged but don't block |
| Dashboard (Phase 12) | LLM narrative hallucination in daily brief | MODERATE | Template fallback primary; LLM enhancement only; verify against signals |

## Recovery Strategies

| Failure | Severity | Recovery | Estimated Fix Time |
|---------|----------|----------|-------------------|
| Kalman Filter diverges | HIGH | Fall back to fixed r*; log warning; do not emit signal | Immediate (fallback) |
| HMM fit fails | HIGH | Fall back to rule-based z-score regime; log warning | Immediate (fallback) |
| Agent produces NaN signal | MEDIUM | Skip signal; log error; other agents continue | Immediate (skip) |
| BEER model coefficients wrong sign | HIGH | Reject model; use prior window coefficients; flag for review | 1-2 hours (manual) |
| Backtest produces negative Sharpe | LOW | Not an error -- some strategies lose money in some periods | N/A |
| LLM API timeout | LOW | Fall back to template narrative; log warning | Immediate (fallback) |
| LLM narrative contradicts signals | MEDIUM | Reject LLM output; use template; log for review | Immediate (fallback) |
| All agents agree (crowding) | MEDIUM | Reduce position sizes 30-50%; flag in risk report | Immediate (auto) |
| Circuit breaker Level 2+ | HIGH | Halt strategy execution; require manual review to resume | 2-4 hours (manual) |
| Data revision missed (ON CONFLICT DO NOTHING) | HIGH | Re-ingest with ON CONFLICT DO UPDATE; re-run affected agents | 30-60 minutes |

## Sources

**Academic:**
- Bailey, D.H. & Lopez de Prado, M. (2014) "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality"
- Harvey, C.R., Liu, Y. & Zhu, H. (2016) "...and the Cross-Section of Expected Returns" -- multiple testing / data snooping
- Laubach, T. & Williams, J. (2003) "Measuring the Natural Rate of Interest" -- Kalman filter r-star
- Hamilton, J.D. (1989) "A New Approach to the Economic Analysis of Nonstationary Time Series" -- HMM regime switching
- Clark, P.B. & MacDonald, R. (1998) "Exchange Rates and Economic Fundamentals: A Methodological Comparison of BEERs and FEERs" -- BEER model
- Almgren, R. & Chriss, N. (2000) "Optimal Execution of Portfolio Transactions" -- market impact / slippage
- Burnside, C. et al. (2011) "Carry Trades and Currency Crashes" -- FX carry risks

**Official Documentation:**
- statsmodels -- `UnobservedComponents`, state-space numerical stability
- hmmlearn -- `GaussianHMM`, `predict_proba` vs `predict` (Viterbi)
- NY Fed -- Holston-Laubach-Williams r-star methodology and R code
- BCB -- Inflation targeting framework, COPOM calendar, Focus survey methodology
- ANBIMA -- Business day calendar, DI futures day count convention (BUS/252)

**Web Research (2026):**
- "Kalman Filter r-star Python implementation pitfalls 2026" -- matrix stability, COVID sensitivity, MUE misspecification
- "HMM regime detection overfitting label switching macro 2026" -- label switching, filtered vs Viterbi, state count selection
- "point-in-time backtesting macro strategies common mistakes 2026" -- look-ahead bias, survivorship, transaction costs, data snooping
- "Python macro trading agent framework design patterns 2026" -- parsimony principle, simple OLS outperforms complex models
- "LLM hallucination financial analysis grounding 2025" -- 17-41% error rate without grounding, HybridRAG mitigation
- "Brazilian DI futures day count convention BUS 252 2026" -- ANBIMA convention, B3 settlement rules

**Codebase Inspection:**
- `src/transforms/curves.py` -- day count convention errors (lines 45, 75, 98), simple vs exponential compounding
- `src/transforms/returns.py` -- hardcoded annualization factor (lines 18, 52, 67)
- `src/core/models/signals.py` -- nullable confidence, missing agent_id column
- `src/core/models/macro_series.py` -- PIT schema correct but no enforcement layer
- `src/connectors/base.py` -- ON CONFLICT DO NOTHING drops revisions (line 277)
