# Phase 9: Fiscal & FX Equilibrium Agents - Research

**Researched:** 2026-02-21
**Domain:** Analytical agents — fiscal debt sustainability + FX equilibrium econometrics
**Confidence:** HIGH (based on direct codebase inspection + Phase 8 implementation patterns)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### DSA Scenario Assumptions
- **Baseline:** r = market-implied forward rates from real DI curve (5Y tenor); g = BCB/Focus consensus GDP forecast. Both update dynamically from existing data.
- **Stress:** baseline + 200bps on r, -1pp on g, -0.5pp on primary balance. IMF-standard shock.
- **Adjustment:** baseline with pb +1.5pp improvement (models successful fiscal consolidation, e.g., Lula fiscal framework adherence).
- **Tailwind:** baseline with g +1pp, r -100bps (commodity super-cycle + BCB easing).

#### Fiscal Dominance Risk Score
- **Components (4):** debt/GDP absolute level + r-g spread (real rate minus real growth) + 12M trend in primary balance/GDP + CB credibility proxy.
- **CB credibility proxy:** Focus survey inflation expectations 12M ahead vs 3.0% target, z-scored. Uses `|expectations_12M - 3.0|` — higher deviation = worse credibility = higher dominance risk. Consistent with `InflationPersistenceModel` logic.
- **Thresholds (signal mapping for FISCAL_BR_DOMINANCE_RISK):**
  - 0–33: LOW risk → SHORT USDBRL (BRL-positive fiscal conditions)
  - 33–66: MODERATE risk → NEUTRAL
  - 66–100: HIGH risk → LONG USDBRL (fiscal stress = BRL weakness)

#### BEER Model Calibration
- **Lookback window:** Full history 2010–present (~15 years). Maximizes statistical power; consistent with 10Y+ lookbacks in Phase 8.
- **Signal direction:** Symmetric ±5% misalignment threshold. Direction = sign of misalignment: `USDBRL > BEER_fair_value by 5%+` → BRL undervalued → SHORT USDBRL (mean reversion expected). Same logic applies in reverse.
- **Missing predictor handling:** Drop missing predictors, refit OLS with available variables. Return NO_SIGNAL if fewer than 2 predictors remain. No forward-fill.
- **CIP basis measure (FX_BR_CIP_BASIS):** Cupom cambial spread = DDI futures implied rate minus offshore USD LIBOR/SOFR equivalent. B3 DDI data via existing FX connector.

#### FX Composite & Carry-to-Risk
- **FX_BR_COMPOSITE:** Weighted composite: BEER 40% + Carry-to-risk 30% + Flow 20% + CIP basis 10%. Apply same conflict dampening pattern as Phase 8 agents (factor 0.70 when sub-signals disagree).
- **Carry-to-risk denominator:** 30-day realized USDBRL volatility (annualized) from daily PTAX data. No options implied vol.
- **FX_BR_CARRY_RISK signal:** Z-score of 12M rolling carry_ratio (carry/vol). |z| > 1.0 fires signal; direction = sign(z). Positive z (unusually attractive carry) → SHORT USDBRL; negative z → LONG USDBRL (carry unwind risk).
- **FX_BR_FLOW components:** BCB FX flow (trade + financial accounts) + CFTC BRL non-commercial positioning — equal-weight z-scores combined into composite flow signal. Both connectors already in system.

#### Phase 8 patterns to replicate
- `_tp_history`-style private raw data keys in features dict
- Conditional imports in `features/__init__.py` for wave independence
- Conflict dampening at 0.70 for composites

#### DSA formula (locked)
`d_{t+1} = d_t*(1+r)/(1+g) - pb` — no deviation from roadmap spec.

#### CIP basis direction (locked)
Positive basis (DDI implied > offshore USD) = capital flow friction = BRL less attractive = LONG USDBRL.

#### BEER symmetry (locked)
5% in both directions, no asymmetric adjustment for BRL.

### Claude's Discretion
- FISCAL_BR_DSA signal direction methodology (baseline-as-primary vs scenario-majority)
- FISCAL_BR_IMPULSE: cyclically-adjusted vs simple approach
- Exact composite aggregation formula for dominance risk 0-100 score
- MIN_OBS guards for DSA model (graceful degradation for early backtest dates)
- FiscalFeatureEngine and FxFeatureEngine internal feature key naming

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FISC-01 | FiscalAgent with FiscalFeatureEngine computing debt ratios, primary balance, r-g dynamics, debt composition, financing needs, market signals | FiscalFeatureEngine pattern mirrors InflationFeatureEngine/MonetaryFeatureEngine; fiscal_data table + macro_series provide inputs; data_loader.get_macro_series already works for BCB fiscal series via BGS codes |
| FISC-02 | DebtSustainabilityModel — IMF DSA projecting debt/GDP under 4 scenarios over 5Y horizon | DSA formula locked: `d_{t+1} = d_t*(1+r)/(1+g) - pb`; Forward rates from DI curve (5Y tenor); Focus GDP for g; uses existing get_curve() + get_macro_series() |
| FISC-03 | FiscalImpulseModel — cyclically-adjusted primary balance change as fiscal expansion/contraction indicator | Claude's discretion on CA approach; z-score of 12M primary balance change is defensible given Brazil's data; uses BCB-5793 series |
| FISC-04 | FiscalDominanceRisk — composite score (0-100) from 4 components with locked thresholds | Dominance components map to available series (gross debt, r-g spread, primary balance trend, Focus IPCA); 0-100 normalization follows Phase 8 InflationPersistenceModel pattern |
| FXEQ-01 | FxEquilibriumAgent with FxFeatureEngine computing BEER inputs, carry-to-risk, flows, CIP basis, CFTC positioning | FxFeatureEngine mirrors prior feature engine pattern; PTAX market_data for vol; get_flow_data() for BCB FX flow + CFTC; get_curve() for DI/DDI |
| FXEQ-02 | BeerModel — OLS USDBRL fair value with misalignment signal | OLS from statsmodels (same as PhillipsCurveModel); BEER inputs from macro_series; 2010–present history from existing connectors; ±5% threshold locked |
| FXEQ-03 | CarryToRiskModel — (BR_rate - US_rate) / vol signal | 30-day realized vol from PTAX daily data (USDBRL_PTAX market_data ticker); z-score of 12M rolling ratio fires at |z|>1.0 |
| FXEQ-04 | FlowModel — BCB FX flow z-score + CFTC BRL non-commercial z-score | Both data sources confirmed in system: get_flow_data("BR_FX_FLOW_TOTAL") + CFTC BRL series (CLP/6B_LEVERAGED_NET or equivalent) |
| FXEQ-05 | CipBasisModel — cupom cambial minus SOFR as CIP deviation signal | DDI futures via DI curve or separate DDI instrument; FRED-SOFR for offshore USD rate; positive basis = LONG USDBRL (locked direction) |
</phase_requirements>

---

## Summary

Phase 9 builds two analytical agents following the exact architecture established in Phase 8. The codebase pattern is completely clear: each agent has a `{Domain}FeatureEngine` (in `src/agents/features/`), a main agent file (in `src/agents/`), unit tests (in `tests/`), and the `features/__init__.py` updated with conditional imports.

**FiscalAgent** requires fiscal data from the `fiscal_data` table (populated by `StnFiscalConnector`) and macro series from BCB SGS (primary balance BCB-5793, gross debt BCB-13762, GDP BCB-22099). Critically, the `PointInTimeDataLoader` does NOT currently have a `get_fiscal_data()` method — it only handles `macro_series`, `market_data`, `flow_data`, and `curves`. The FiscalAgent must use `get_macro_series()` for fiscal series that flow through the macro_series pipeline (via BCB SGS connector), not the fiscal_data hypertable. This is the key architectural gap to resolve.

**FxEquilibriumAgent** relies on 4 sub-models (BEER via OLS, carry-to-risk, flow composite, CIP basis). All data sources are confirmed in the system: USDBRL daily from PTAX connector (`USDBRL_PTAX` ticker), BCB FX flows via `get_flow_data()`, CFTC BRL positioning via `get_flow_data()`, DI curve via `get_curve()`, SOFR via `get_macro_series("FRED-SOFR")`. The BEER OLS pattern is identical to PhillipsCurveModel — 15-year history, OLS on available predictors, graceful degradation to NO_SIGNAL.

**Primary recommendation:** Split into 3 plans (Wave 1: FiscalFeatureEngine + FiscalAgent models; Wave 1 parallel: FxFeatureEngine + FxEquilibriumAgent models; Wave 2: unit tests for both), each following the exact task structure of Phase 8 plans.

---

## Standard Stack

### Core (identical to Phase 8)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| statsmodels | installed | OLS regression (BEER model) | Same as PhillipsCurveModel — fits, predicts, returns coefficients |
| numpy | installed | Kalman filter, array ops, z-score | Same as Phase 8 models |
| pandas | installed | Time series manipulation, HP filter, rolling windows | Same as Phase 8 feature engines |
| structlog / logging | installed | Structured logging in agents | logging used in monetary_agent; structlog in base |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| statsmodels.tsa.filters.hp_filter | installed | HP filter for trend extraction | FiscalFeatureEngine needs cycle adjustment for impulse; already confirmed working in Phase 8 |
| scipy (optional) | installed | Stats utilities if needed | Only if HP filter via scipy needed; prefer statsmodels |

**Installation:** No new dependencies needed. All libraries already in use by Phase 8 agents.

---

## Architecture Patterns

### Established File Structure (replicate exactly)
```
src/agents/
├── features/
│   ├── __init__.py          # Updated to conditionally import FiscalFeatureEngine and FxFeatureEngine
│   ├── inflation_features.py  # Phase 8 - DO NOT MODIFY
│   ├── monetary_features.py   # Phase 8 - DO NOT MODIFY
│   ├── fiscal_features.py     # NEW: Phase 9 FiscalFeatureEngine
│   └── fx_features.py         # NEW: Phase 9 FxFeatureEngine
├── fiscal_agent.py            # NEW: FiscalAgent + 3 model classes
├── fx_agent.py                # NEW: FxEquilibriumAgent + 4 model classes
tests/
├── test_fiscal_agent.py       # NEW: unit tests, no DB required
└── test_fx_agent.py           # NEW: unit tests, no DB required
```

### Pattern 1: FeatureEngine Structure (replicate from InflationFeatureEngine)
**What:** Stateless `compute(data, as_of_date) -> dict` method. No DB access in feature class.
**When to use:** Both FiscalFeatureEngine and FxFeatureEngine follow this identically.
**Example (from src/agents/features/inflation_features.py):**
```python
class FiscalFeatureEngine:
    """Compute fiscal features from raw point-in-time data."""

    def compute(self, data: dict, as_of_date: date) -> dict[str, Any]:
        """Return a flat dict of all fiscal features."""
        features: dict[str, Any] = {}
        features.update(self._debt_dynamics(data))
        features.update(self._primary_balance(data))
        features.update(self._r_g_dynamics(data, features))
        features.update(self._credibility_proxy(data))
        # Private keys for model classes
        features["_dsa_raw_data"] = self._build_dsa_data(data, features)
        features["_pb_history"] = self._build_pb_history(data)
        return features
```

### Pattern 2: Agent Class Structure (replicate from MonetaryPolicyAgent)
**What:** `BaseAgent` subclass with AGENT_ID, AGENT_NAME, `__init__` instantiating models, fully implemented `load_data` / `compute_features` / `run_models` / `generate_narrative` / `_build_composite`.
**When to use:** Both FiscalAgent and FxEquilibriumAgent follow this exactly.
```python
class FiscalAgent(BaseAgent):
    AGENT_ID = "fiscal_agent"
    AGENT_NAME = "Fiscal Agent"

    def __init__(self, loader: PointInTimeDataLoader) -> None:
        super().__init__(self.AGENT_ID, self.AGENT_NAME)
        self.loader = loader
        self.feature_engine = FiscalFeatureEngine()
        self.dsa_model = DebtSustainabilityModel()
        self.impulse_model = FiscalImpulseModel()
        self.dominance_model = FiscalDominanceRisk()
```

### Pattern 3: Model Class Structure (replicate from TaylorRuleModel)
**What:** `SIGNAL_ID` constant, `run(features, as_of_date) -> AgentSignal` with `_no_signal()` helper.
**When to use:** All 7 new model classes (3 fiscal + 4 FX).
```python
class DebtSustainabilityModel:
    SIGNAL_ID = "FISCAL_BR_DSA"
    MIN_OBS = 12  # months of data required

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        def _no_signal(reason: str = "") -> AgentSignal:
            return AgentSignal(
                signal_id=self.SIGNAL_ID, agent_id="fiscal_agent",
                timestamp=datetime.utcnow(), as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL, strength=SignalStrength.NO_SIGNAL,
                confidence=0.0, value=0.0, horizon_days=252,
                metadata={"reason": reason},
            )
        # model logic...
```

### Pattern 4: Private Raw Data Keys in Features Dict
**What:** Feature engine assembles model-specific DataFrames as private keys (prefixed `_`). Models consume them without re-loading data.
**Critical keys to establish:**

FiscalFeatureEngine private keys:
- `features["_dsa_raw_data"]` — dict with `debt_gdp_series`, `primary_balance_series`, `r_series`, `g_series` (all pd.Series, monthly)
- `features["_pb_history"]` — pd.Series of monthly primary balance/GDP for impulse z-score and dominance trend
- `features["_as_of_date"]` — date (same as all Phase 8 agents)

FxFeatureEngine private keys:
- `features["_beer_ols_data"]` — DataFrame with columns: usdbrl, terms_of_trade, real_rate_diff, nfa_proxy, productivity_diff (monthly, 2010–present)
- `features["_ptax_daily"]` — pd.Series of daily USDBRL for 30D realized vol calculation
- `features["_carry_ratio_history"]` — pd.Series of monthly (selic-fed_funds)/30d_vol for 12M z-score
- `features["_flow_combined"]` — DataFrame with bcb_flow_zscore and cftc_zscore columns
- `features["_as_of_date"]` — date

### Pattern 5: Conditional Import in features/__init__.py (wave independence)
**What:** New feature engines imported with try/except so wave-1 plans can run in parallel.
**From src/agents/features/__init__.py (current):**
```python
from src.agents.features.monetary_features import MonetaryFeatureEngine

try:
    from src.agents.features.inflation_features import InflationFeatureEngine
    __all__ = ["MonetaryFeatureEngine", "InflationFeatureEngine"]
except ImportError:
    pass
```
**Phase 9 update pattern:**
```python
try:
    from src.agents.features.fiscal_features import FiscalFeatureEngine
    # Add to __all__
except ImportError:
    pass

try:
    from src.agents.features.fx_features import FxFeatureEngine
    # Add to __all__
except ImportError:
    pass
```

### Pattern 6: Composite Signal Builder (replicate from MonetaryPolicyAgent._build_composite)
**What:** Plurality vote + conflict dampening (0.70) on confidence.
**Locks:** FX_BR_COMPOSITE = BEER 40% + Carry 30% + Flow 20% + CIP 10%; dampening 0.70 if any sub-signal disagrees with plurality.
**The existing `_build_composite()` in monetary_agent.py is the exact template** — copy, update weights and signal_ids.

### Pattern 7: Safe Data Loading with try/except
**What:** Each `get_macro_series` / `get_market_data` / `get_flow_data` call wrapped in try/except, returning None on failure.
**From monetary_agent.py (verbatim pattern):**
```python
def _safe_load(key: str, loader_fn, *args, **kwargs) -> None:
    try:
        data[key] = loader_fn(*args, **kwargs)
    except Exception as exc:
        self.log.warning("data_load_failed", key=key, error=str(exc))
        data[key] = None
```

### Anti-Patterns to Avoid
- **Accessing fiscal_data hypertable directly:** The `PointInTimeDataLoader` has NO `get_fiscal_data()` method. Use `get_macro_series()` for BCB fiscal series that flow through the macro_series pipeline. The StnFiscalConnector writes to the `fiscal_data` table which is separate from `macro_series`. This is the most likely trap.
- **Using Focus series with year suffix for DSA:** Focus PIB (GDP) series follow the pattern `BR_FOCUS_PIB_{YEAR}_MEDIAN` where YEAR is the reference year (e.g., `BR_FOCUS_PIB_2025_MEDIAN`). The agent should use the current/next year's consensus. The `get_focus_expectations()` convenience wrapper uses `BR_FOCUS_{indicator}_CY_MEDIAN` format which may not match — use `get_macro_series()` directly with the correct series code.
- **Import-time DB connections:** Feature engines and model classes must not connect to DB at import time. All DB access via `PointInTimeDataLoader` inside `load_data()`.
- **Hard-failing on missing data:** Every computation must return `np.nan` (not raise) for missing series. NO_SIGNAL returned by models when insufficient data.
- **Modifying Phase 8 files:** Only `features/__init__.py` is modified in Phase 9. All Phase 8 agent/feature files are untouched.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OLS regression | Custom matrix inversion | `statsmodels.api.OLS` | Already used in PhillipsCurveModel; handles edge cases, collinearity, fit stats |
| HP filter | Custom smoothing | `statsmodels.tsa.filters.hp_filter.hpfilter` | Already in use; use lambda=1600 for monthly data (same as InflationFeatureEngine) |
| Z-score calculation | Manual mean/std | `pd.Series.rolling().mean()` and `.std()` | Handles NaN correctly with dropna(); already proven in Phase 8 |
| Numeric confidence scaling | Ad hoc formulas | `classify_strength(confidence)` from `src.agents.base` | Existing utility; ensures consistency with SignalStrength buckets |
| Signal construction | Ad hoc dict | `AgentSignal` dataclass | Typed, enforces required fields; `_no_signal()` helper pattern |
| DI forward rate interpolation | Custom interpolation | Linear interpolation between tenor points from `get_curve()` | Already implemented in MonetaryFeatureEngine `_di_implied_path` |

**Key insight:** All primitives (OLS, HP filter, Kalman, z-score, composite builder) are already implemented in Phase 8. Phase 9 is primarily about applying these patterns to new economic domains.

---

## Critical Data Access Findings

### Fiscal Data: Architecture Gap Requiring Decision

The `PointInTimeDataLoader` has these methods:
- `get_macro_series(series_code, as_of_date, lookback_days)` — queries `macro_series` table
- `get_market_data(ticker, as_of_date, lookback_days)` — queries `market_data` table
- `get_flow_data(series_code, as_of_date, lookback_days)` — queries `flow_data` table
- `get_curve(curve_id, as_of_date)` — queries `curve_data` table
- `get_curve_history(curve_id, tenor_days, as_of_date, lookback_days)`

**No `get_fiscal_data()` method exists.** The `FiscalData` (fiscal_data table) is populated by `StnFiscalConnector` but is not accessible via PointInTimeDataLoader.

**Resolution:** Use `get_macro_series()` for fiscal series that are ingested via `BcbSgsConnector` (which writes to `macro_series` table). Confirmed available series:
- `"BR_PRIMARY_BALANCE"` → BCB SGS 5793 (in macro_series via BcbSgsConnector)
- `"BR_GROSS_DEBT_GDP"` → BCB SGS 13762 (in macro_series via BcbSgsConnector)
- `"BR_NET_DEBT_GDP"` → BCB SGS 4513 (in macro_series via BcbSgsConnector)
- `"BR_GDP_QOQ"` → BCB SGS 22099 (quarterly GDP, in macro_series via BcbSgsConnector)

If `get_fiscal_data()` is needed for fiscal_data hypertable, the planner must add a `get_fiscal_data()` method to `PointInTimeDataLoader` first (as a task in Plan 09-01). However, given the BcbSgsConnector already loads the key fiscal series into `macro_series`, the simpler path is to use existing `get_macro_series()` calls.

### FX Data Access (all confirmed working)
- **USDBRL daily:** `self.loader.get_market_data("USDBRL_PTAX", as_of_date, lookback_days=756)` — returns DataFrame with `close`, `adjusted_close` columns
- **BCB FX flows:** `self.loader.get_flow_data("BR_FX_FLOW_COMMERCIAL", as_of_date)`, `"BR_FX_FLOW_FINANCIAL"`, `"BR_FX_FLOW_TOTAL"` — returns DataFrame with `value`, `flow_type` columns
- **BCB swap stock:** `self.loader.get_flow_data("BR_BCB_SWAP_STOCK", as_of_date)`
- **CFTC BRL positioning:** CFTC series follow pattern `"CFTC_{contract}_{category}_NET"`. For BRL: no direct BRL contract in `CftcCotConnector.CONTRACT_CODES` — closest proxy is `"CFTC_DX_LEVERAGED_NET"` (US Dollar Index) or we must use `"CFTC_6B_LEVERAGED_NET"` if GBP/USD is in registry. The DX (Dollar Index) leveraged non-commercial net is the most relevant proxy for USD strength vs BRL.

**CFTC BRL gap:** The `CftcCotConnector` tracks 12 contracts but does NOT include BRL (Brazilian Real futures, CME contract code 102741). The closest available proxies are:
1. `CFTC_DX_LEVERAGED_NET` — US Dollar Index non-commercial leveraged net (most direct USD strength proxy)
2. Use DX as BRL flow proxy until a dedicated BRL futures contract code is added to CftcCotConnector

This is an important finding the planner needs to know: the CONTEXT.md says "CFTC BRL non-commercial positioning" but the system's CFTC connector doesn't track BRL futures directly. The planner should either (a) use DX as proxy, or (b) add BRL futures code to CftcCotConnector as part of Plan 09-01 data setup. **Recommend option (b)** — add BRL futures (CME: `102741`) to `CftcCotConnector.CONTRACT_CODES` in Plan 09-01.

- **DI curve for r in DSA/CIP:** `self.loader.get_curve("DI", as_of_date)` returns `{tenor_days: rate}` dict
- **DI curve history for BEER real rate diff:** `self.loader.get_curve_history("DI", 1260, as_of_date, lookback_days=5475)` (5Y tenor = 1260 days, 15Y history)
- **Focus GDP (g for DSA):** `self.loader.get_macro_series("BR_FOCUS_PIB_{YEAR}_MEDIAN", as_of_date)` — note year-specific series code pattern from BcbFocusConnector

### Key Series Code Reference for Phase 9

**FiscalAgent load_data series:**
```python
# Debt and balance via get_macro_series()
"BR_GROSS_DEBT_GDP"   # BCB-13762: gross debt/GDP %
"BR_PRIMARY_BALANCE"  # BCB-5793: primary balance BRL_MM
"BR_NET_DEBT_GDP"     # BCB-4513: net debt/GDP %
"BR_GDP_QOQ"          # BCB-22099: quarterly GDP growth
"FOCUS-IPCA-12M"      # Focus IPCA 12M (for CB credibility proxy)
"BCB-432"             # Selic target (for r-g spread: real rate = selic - focus_ipca)
```

**FxEquilibriumAgent load_data series:**
```python
# BEER inputs via get_macro_series()
"BR_TRADE_BALANCE"    # BCB-22707: terms of trade proxy
"BCB-432"             # Selic target (BR rate for carry)
"FRED-DFF"            # Fed Funds (US rate for carry)
"FRED-SOFR"           # SOFR for CIP basis offshore rate
"BR_RESERVES"         # BCB-13621: FX reserves (NFA proxy)
# USDBRL daily via get_market_data()
"USDBRL_PTAX"         # Daily PTAX fixing for 30D vol + BEER
# FX flows via get_flow_data()
"BR_FX_FLOW_COMMERCIAL"   # series_code for BCB commercial flow
"BR_FX_FLOW_FINANCIAL"    # series_code for BCB financial flow
# DI curve via get_curve() and get_curve_history()
"DI"                  # DI curve for r, CIP DDI rates
```

---

## DSA Model Implementation Details

### Locked Formula
```python
# d_{t+1} = d_t * (1 + r) / (1 + g) - pb
# Where:
# d_t = debt/GDP ratio at time t (from BCB series, %)
# r = real interest rate on debt (nominal rate - inflation expectation)
# g = real GDP growth rate (from Focus consensus)
# pb = primary balance/GDP ratio (% of GDP)
```

### Scenario Construction (from CONTEXT.md, locked)
```python
# DSA scenario parameters
scenarios = {
    "baseline": {
        "r_adj": 0.0,     # market-implied forward rate from DI 5Y
        "g_adj": 0.0,     # Focus consensus GDP forecast
        "pb_adj": 0.0,    # no change from current primary balance
    },
    "stress": {
        "r_adj": +2.00,   # +200bps on r
        "g_adj": -1.00,   # -1pp on g
        "pb_adj": -0.50,  # -0.5pp on pb
    },
    "adjustment": {
        "r_adj": 0.0,
        "g_adj": 0.0,
        "pb_adj": +1.50,  # +1.5pp improvement in pb
    },
    "tailwind": {
        "r_adj": -1.00,   # -100bps on r
        "g_adj": +1.00,   # +1pp on g
        "pb_adj": 0.0,
    },
}
HORIZON = 5  # 5-year projection
```

### Signal Direction Recommendation (Claude's Discretion)
Use **baseline-as-primary** approach: run the baseline 5Y DSA, compare terminal debt/GDP to current level.
- If `baseline_terminal_debt - current_debt > +5pp` → debt is rising unsustainably → LONG USDBRL (fiscal stress signal)
- If `baseline_terminal_debt - current_debt < -5pp` → debt is declining → SHORT USDBRL (fiscal improvement signal)
- Else NEUTRAL
- Use scenario count (how many of 4 scenarios show stabilization) as confidence modifier: 4/4 stabilizing → confidence 1.0; 3/4 → 0.70; 2/4 → 0.40; 1/4 → 0.20; 0/4 → 0.0 but still directional from baseline
- Include in metadata: all 4 scenario terminal paths

This approach (baseline direction + scenario confidence modifier) is more interpretable than majority vote and gives the planner both a clear signal and a nuanced confidence.

---

## FiscalImpulseModel Implementation Details

### Recommendation (Claude's Discretion): Simple 12M change z-scored
Use **z-scored 12M change in primary balance/GDP** rather than full cyclical adjustment. Rationale:
1. Brazil lacks a published cyclically-adjusted primary balance series
2. The IBC-Br output gap is already computed; a simple regression on output gap would introduce estimation error
3. The z-score approach is consistent with InflationSurpriseModel and already established in the codebase
4. Signal direction: positive impulse (primary balance improving over 12M) → contractionary fiscal → SHORT USDBRL; negative impulse → expansionary → LONG USDBRL

```python
# 12M change in primary balance as % of GDP
# pb_change = pb_gdp_ratio[t] - pb_gdp_ratio[t-12]
# z = (pb_change - rolling_mean(36M)) / rolling_std(36M)
# |z| > 1.0 fires signal
```

---

## FiscalDominanceRisk Composite Implementation

### 0-100 Aggregation Formula (Claude's Discretion)
Mirror the `InflationPersistenceModel` pattern exactly — 4 components each mapped to 0-100 subscores, then weighted average:

```python
WEIGHTS = {
    "debt_level": 0.35,      # Gross debt/GDP absolute level (most direct)
    "r_g_spread": 0.30,      # r - g: destabilizing when positive and high
    "pb_trend": 0.20,        # 12M trend in primary balance (deteriorating = bad)
    "cb_credibility": 0.15,  # Focus IPCA deviation from target
}
```

Sub-score normalization:
- `debt_level`: 60% GDP = 50 score; 90% GDP = 100; 30% GDP = 0 (linear interpolation)
- `r_g_spread`: r-g=0 → 50; r-g=+5 → 100; r-g=-5 → 0 (linear, clamped)
- `pb_trend`: 12M improvement of 1pp GDP → 0; deterioration of 1pp → 100 (normalized by 2pp range)
- `cb_credibility`: |focus_12m - 3.0|=0 → 0; |deviation|=3pp → 100 (linear)

---

## BEER Model Implementation Details

### OLS Predictor Strategy
BEER (Behavioral Equilibrium Exchange Rate) standard specification:
```
log(USDBRL) = α + β1*log(ToT) + β2*r_diff + β3*NFA_proxy + β4*productivity_diff + ε
```

Data availability mapping:
- `log(USDBRL)`: `USDBRL_PTAX` daily resampled to monthly end → log transform
- `log(ToT)`: Use `BR_TRADE_BALANCE` / lagged 12M average as proxy for terms of trade improvement/deterioration (or commodity price proxy via CRB from InflationAgent data)
- `r_diff`: DI 5Y real rate (DI_5Y - focus_ipca_12m) minus UST_5Y (from `get_curve_history("DI", 1260)` and UST from macro_series)
- `NFA_proxy`: `BR_RESERVES` (BCB FX reserves) as level proxy for NFA (data since 2000+)
- `productivity_diff`: Use `BR_IBC_BR` trend / US ISM proxy or drop if insufficient (per locked decision: drop missing, refit)

2010-present lookback = ~180 monthly observations → robust OLS. If fewer than 2 predictors survive, return NO_SIGNAL.

### Misalignment Signal
```python
# fair_value_usdbrl = exp(predicted log USDBRL from OLS)
# misalignment_pct = (actual / fair_value - 1) * 100
# USDBRL > fair_value by 5%+ → BRL undervalued → SHORT USDBRL (mean reversion)
# USDBRL < fair_value by 5%+ → BRL overvalued → LONG USDBRL (mean reversion)
THRESHOLD = 5.0  # percent (locked)
```

---

## CIP Basis Implementation

### DDI Futures Availability
The `PointInTimeDataLoader.get_curve("DI", as_of_date)` provides DI pre rates. DDI futures (cupom cambial) are priced off DI pre + FX swap, not stored separately in the system. Two approaches:
1. **If DDI curve exists in curve_data:** Use `get_curve("DDI", as_of_date)` to get cupom cambial rates
2. **Proxy approach:** Use DI 1Y rate as approximate cupom cambial (domestic side), minus SOFR as the CIP basis

The proxy approach is defensible for signal generation. The planner should note this uncertainty. Use: `cip_basis = di_1y - (sofr + usdbrl_swap_cost_proxy)`. In practice for signal generation: `cip_basis ≈ di_1y_real - sofr` where `di_1y_real = di_1y - focus_ipca_12m` (strip out Brazilian inflation premium to get the dollar-equivalent cost).

A simpler defensible proxy: `cip_basis = di_1y - (fed_funds_rate + expected_usdbrl_depreciation_12m)` where expected depreciation is from Focus Câmbio series.

---

## Common Pitfalls

### Pitfall 1: Fiscal Data Table vs Macro Series Table
**What goes wrong:** Developer tries to query fiscal data but PointInTimeDataLoader has no `get_fiscal_data()` method; runtime error.
**Why it happens:** The `StnFiscalConnector` writes to `fiscal_data` table, but the `BcbSgsConnector` also loads overlapping series (primary balance, debt/GDP) into `macro_series`.
**How to avoid:** Use `get_macro_series()` with BCB SGS series codes. These are confirmed in `BcbSgsConnector.SERIES_REGISTRY`: `BR_GROSS_DEBT_GDP`, `BR_PRIMARY_BALANCE`, `BR_NET_DEBT_GDP`.
**Warning signs:** `AttributeError: 'PointInTimeDataLoader' object has no attribute 'get_fiscal_data'`

### Pitfall 2: CFTC BRL Futures Not in Connector
**What goes wrong:** `get_flow_data("CFTC_BRL_LEVERAGED_NET")` returns empty DataFrame because BRL futures are not in `CftcCotConnector.CONTRACT_CODES`.
**Why it happens:** The CFTC connector tracks 12 contracts (ES, NQ, YM, TY, US, FV, TU, ED, CL, GC, SI, DX) — none is BRL.
**How to avoid:** Either add BRL futures (`"6L": "102741"`) to CftcCotConnector in Plan 09-01, or use DX as USD strength proxy. Plan 09-01 should include adding BRL to CFTC registry before building FlowModel.
**Warning signs:** Empty DataFrame for CFTC BRL series; FlowModel returns NO_SIGNAL for CFTC component.

### Pitfall 3: Focus Series Naming Convention
**What goes wrong:** `get_macro_series("FOCUS-GDP-12M")` returns empty because Focus series use year-specific codes like `BR_FOCUS_PIB_2025_MEDIAN`.
**Why it happens:** BcbFocusConnector generates series keys as `BR_FOCUS_{INDICATOR}_{YEAR}_MEDIAN` — there is no rolling 12M GDP focus series. The `FOCUS-IPCA-12M` format is custom (used by InflationAgent for 12M rolling IPCA expectations which are stored differently).
**How to avoid:** For DSA baseline g, query multiple year-specific Focus PIB series and take the nearest-horizon value. Alternatively, use `BR_GDP_QOQ` from macro_series for realized growth and apply a simple trend projection.
**Warning signs:** Empty DataFrame from `get_macro_series("BR_FOCUS_PIB_CY_MEDIAN")`.

### Pitfall 4: DI 5Y Forward Rate for DSA r
**What goes wrong:** `get_curve("DI", as_of_date)` returns spot rates, not forward rates. Using the 5Y DI spot rate as `r` in DSA overstates the real cost of debt.
**Why it happens:** The DI pre curve gives yields-to-maturity, not forward rates. The nominal rate-implied 5Y is an acceptable proxy for expected average refinancing cost.
**How to avoid:** Use the DI 5Y spot rate as r_nominal, then subtract focus_ipca_12m as the best available inflation expectation to compute real r. This is consistent with how MonetaryFeatureEngine computes `di_1y_real`.
**Warning signs:** DSA showing implausibly extreme debt paths — check whether r is in real or nominal terms.

### Pitfall 5: Monthly Resampling for BEER OLS
**What goes wrong:** USDBRL_PTAX is daily; BEER inputs (trade balance, reserves) are monthly. Joining without resampling creates NaN-filled monthly DataFrame.
**Why it happens:** PTAX is stored as daily market_data; BCB macro series are monthly.
**How to avoid:** Resample PTAX to monthly last (`usdbrl_df.resample("ME").last()`) before joining. Same pattern as used in InflationFeatureEngine `_build_ols_data` for USDBRL.
**Warning signs:** BEER OLS has very few non-NaN rows; OLS raises insufficient data error.

### Pitfall 6: MIN_OBS Guard for DSA Early Backtest Dates
**What goes wrong:** Backtest starting in 2010 may have insufficient debt/GDP history for DSA model.
**Why it happens:** Some BCB series only go back to 2008-2010. DSA needs at least 12 months of debt/GDP history to compute meaningful projections.
**How to avoid:** Set MIN_OBS = 12 for DSA model (same pattern as `KalmanFilterRStar.MIN_OBS = 24`). Return NO_SIGNAL when data < MIN_OBS. Document in code.
**Warning signs:** KeyError or IndexError in DSA projection loop during historical backtest.

---

## Code Examples

### OLS BEER Model Pattern (from PhillipsCurveModel in inflation_agent.py)
```python
# Source: src/agents/inflation_agent.py (PhillipsCurveModel.run)
import statsmodels.api as sm

# Fit BEER OLS on available predictors
df = features["_beer_ols_data"].dropna()  # drop rows with any NaN
if len(df) < MIN_OBS:
    return _no_signal("insufficient_data")

y = df["log_usdbrl"]
available_predictors = [c for c in df.columns if c != "log_usdbrl" and df[c].notna().sum() > MIN_OBS]

if len(available_predictors) < 2:  # locked: NO_SIGNAL if < 2 predictors
    return _no_signal("insufficient_predictors")

X = sm.add_constant(df[available_predictors])
model = sm.OLS(y, X).fit()
predicted_log_usdbrl = model.predict(X).iloc[-1]
fair_value = np.exp(predicted_log_usdbrl)
actual_usdbrl = np.exp(y.iloc[-1])
misalignment_pct = (actual_usdbrl / fair_value - 1) * 100
```

### 30-Day Realized Volatility from PTAX Daily
```python
# Source: derived from InflationFeatureEngine._br_fx_passthrough pattern
# features["_ptax_daily"] is a pd.Series from get_market_data("USDBRL_PTAX")
ptax = features.get("_ptax_daily")
if ptax is not None and len(ptax) >= 30:
    daily_returns = ptax.pct_change().dropna()
    vol_30d = float(daily_returns.rolling(30).std().iloc[-1]) * np.sqrt(252) * 100
else:
    vol_30d = np.nan
```

### DSA 5-Year Projection Loop
```python
# Source: derived from locked formula d_{t+1} = d_t*(1+r)/(1+g) - pb
def _project_debt_path(d0, r, g, pb, horizon=5):
    """Project debt/GDP ratio for horizon years."""
    path = [d0]
    for _ in range(horizon):
        d_next = path[-1] * (1 + r/100) / (1 + g/100) - pb/100
        path.append(d_next)
    return path  # list of length horizon+1

# baseline_path = _project_debt_path(current_debt_gdp, r_nominal, g_real, pb_gdp)
# terminal_delta = baseline_path[-1] - baseline_path[0]
```

### Conflict Dampening Composite (exact copy from MonetaryPolicyAgent._build_composite)
```python
# Source: src/agents/monetary_agent.py (MonetaryPolicyAgent._build_composite)
# FX_BR_COMPOSITE weights (locked in CONTEXT.md):
base_weights = {"FX_BR_BEER": 0.40, "FX_BR_CARRY_RISK": 0.30,
                "FX_BR_FLOW": 0.20, "FX_BR_CIP_BASIS": 0.10}

# Filter to active (non-NO_SIGNAL, non-NEUTRAL) signals, renormalize weights
active = [(sig, w) for sig, w in zip(sub_signals, base_weights.values())
          if sig.strength != SignalStrength.NO_SIGNAL and sig.direction != SignalDirection.NEUTRAL]

total_w = sum(w for _, w in active)
norm_weights = [(sig, w/total_w) for sig, w in active]

# Plurality vote
long_w = sum(w for sig, w in norm_weights if sig.direction == SignalDirection.LONG)
short_w = sum(w for sig, w in norm_weights if sig.direction == SignalDirection.SHORT)
plurality = SignalDirection.LONG if long_w >= short_w else SignalDirection.SHORT

# Conflict dampening (0.70 when any sub-signal disagrees)
disagreements = sum(1 for sig, _ in norm_weights if sig.direction != plurality)
dampening = 0.70 if disagreements >= 1 else 1.0

composite_confidence = sum(sig.confidence * w for sig, w in norm_weights) * dampening
```

### Unit Test Pattern (from tests/test_monetary_agent.py)
```python
# Source: tests/test_monetary_agent.py
def make_signal(signal_id, direction, strength, confidence=0.7):
    return AgentSignal(
        signal_id=signal_id, agent_id="fiscal_agent",
        timestamp=datetime.utcnow(), as_of_date=date(2024,1,31),
        direction=direction, strength=strength, confidence=confidence,
        value=1.0, horizon_days=252,
    )

# Test pattern for model with synthetic features dict (no DB):
def test_dsa_model_rising_debt_long():
    features = {
        "_dsa_raw_data": {
            "debt_gdp": 85.0,   # current debt/GDP
            "r_nominal": 13.0,  # Selic ~nominal rate
            "g_real": 1.5,      # real GDP growth
            "pb_gdp": -0.5,     # primary deficit
        },
        "_as_of_date": date(2024, 1, 31),
    }
    signal = DebtSustainabilityModel().run(features, date(2024, 1, 31))
    assert signal.direction == SignalDirection.LONG  # rising debt = bearish BRL
```

---

## Wave Planning Recommendation

Based on Phase 8 structure (3 plans for 2 agents), Phase 9 should use 3 plans:

**Plan 09-01 (Wave 1, independent):** FiscalFeatureEngine + all 3 FiscalAgent models + FiscalAgent orchestration
- Optional: add BRL futures to CftcCotConnector if CFTC BRL data is needed
- Files: `src/agents/features/fiscal_features.py`, `src/agents/fiscal_agent.py`, `src/agents/features/__init__.py`

**Plan 09-02 (Wave 1, parallel with 09-01):** FxFeatureEngine + all 4 FxEquilibriumAgent models + FxEquilibriumAgent orchestration
- Files: `src/agents/features/fx_features.py`, `src/agents/fx_agent.py`, `src/agents/features/__init__.py`
- Note: Both 09-01 and 09-02 modify `features/__init__.py` — they must either be sequential or split the init update

**Revised recommendation:** Make 09-01 modify `features/__init__.py` for FiscalFeatureEngine, and 09-02 (depends on 09-01) handles FxFeatureEngine addition to init. This matches the Phase 8 pattern where 08-01 created `features/__init__.py` and 08-03 added `MonetaryFeatureEngine`.

**Plan 09-03 (Wave 2, depends on 09-01 + 09-02):** Unit tests for both agents
- Files: `tests/test_fiscal_agent.py`, `tests/test_fx_agent.py`

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Forward-fill missing BEER predictors | Drop missing, refit with available (locked) | Prevents lookahead bias in backtest |
| Simple primary balance level | 12M change z-score as fiscal impulse | Captures fiscal direction, not just level |
| Single-scenario DSA | 4-scenario fan chart with confidence weighting | More robust to economic uncertainty |
| Implied vol for carry-to-risk | 30D realized PTAX vol (locked) | Removes option data dependency |

---

## Open Questions

1. **DDI curve availability in curve_data table**
   - What we know: `get_curve("DI", as_of_date)` works for DI pre rates. DDI (cupom cambial) is a separate instrument.
   - What's unclear: Whether `curve_data` table contains DDI rates or if they must be derived from DI + FX swap.
   - Recommendation: In Plan 09-02, use proxy approach (DI 1Y minus SOFR as simplified CIP basis) with a comment noting full DDI would be preferred. This avoids blocking on data availability.

2. **CFTC BRL Futures Data Gap**
   - What we know: CftcCotConnector tracks 12 contracts, none being Brazilian Real futures.
   - What's unclear: Whether CFTC BRL data exists in the flow_data table from any other source.
   - Recommendation: Plan 09-01 includes adding BRL futures (CME code `102741`, short name "6L") to `CftcCotConnector.CONTRACT_CODES`. This is a 2-line change to the connector. The planner should include this as a task in Plan 09-02 (or a prereq task in 09-01).

3. **Focus GDP Series Code for DSA Baseline**
   - What we know: BcbFocusConnector creates year-specific series keys `BR_FOCUS_PIB_{YEAR}_MEDIAN`.
   - What's unclear: What year to query dynamically (e.g., 2025 vs 2026 depending on current date).
   - Recommendation: Load the current year + next year Focus PIB series and use the geometric mean as the g estimate. If unavailable, fall back to trailing 4-quarter average of `BR_GDP_QOQ`. Document in FiscalFeatureEngine.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection:
  - `src/agents/base.py` — BaseAgent, AgentSignal, AgentReport, classify_strength
  - `src/agents/data_loader.py` — PointInTimeDataLoader methods (get_macro_series, get_market_data, get_flow_data, get_curve, get_curve_history)
  - `src/agents/features/inflation_features.py` — InflationFeatureEngine implementation pattern
  - `src/agents/features/monetary_features.py` — MonetaryFeatureEngine implementation pattern
  - `src/agents/inflation_agent.py` — PhillipsCurveModel, IpcaBottomUpModel, InflationAgent
  - `src/agents/monetary_agent.py` — TaylorRuleModel, KalmanFilterRStar, composite builder
  - `src/agents/features/__init__.py` — conditional import pattern
  - `src/connectors/stn_fiscal.py` — StnFiscalConnector series registry, fiscal_data table
  - `src/connectors/bcb_fx_flow.py` — BcbFxFlowConnector, flow series codes
  - `src/connectors/cftc_cot.py` — CftcCotConnector CONTRACT_CODES (confirmed no BRL)
  - `src/connectors/bcb_ptax.py` — USDBRL_PTAX ticker name
  - `src/connectors/bcb_sgs.py` — BCB SGS fiscal series codes
  - `src/connectors/bcb_focus.py` — Focus series key generation pattern
  - `src/core/enums.py` — SignalDirection, SignalStrength
  - `src/core/models/fiscal_data.py` — FiscalData table schema
  - `src/core/models/flow_data.py` — FlowData table schema
  - `tests/test_monetary_agent.py` — Unit test patterns (MagicMock, synthetic features)
  - `.planning/phases/08-*/08-0[123]-PLAN.md` — Task format, wave structure, success criteria

### Secondary (MEDIUM confidence)
- IMF DSA methodology documentation (training knowledge): 4-scenario fan chart approach with baseline/stress/adjustment/tailwind — MEDIUM confidence (well-established IMF standard, consistent with locked CONTEXT.md decisions)
- BEER model literature (training knowledge): Behavioral Equilibrium Exchange Rate via OLS with ToT, r_diff, NFA, productivity as predictors — MEDIUM confidence (standard in FX literature)

### Tertiary (LOW confidence)
- CME BRL futures contract code `102741` for CFTC COT — LOW confidence (verify before adding to CftcCotConnector; CME codes occasionally change)
- DDI curve availability in `curve_data` table — LOW confidence (not confirmed by codebase inspection; depends on B3 connector implementation not reviewed)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed installed and in use in Phase 8
- Architecture patterns: HIGH — direct inspection of Phase 8 implementations that Phase 9 must replicate
- Data access patterns: HIGH for confirmed series; LOW for DDI curve availability and CFTC BRL
- Fiscal model economics: MEDIUM — DSA formula is locked; scenario parameters are locked; z-score approach for impulse is recommended but Claude's discretion
- FX model economics: MEDIUM — BEER OLS and carry-to-risk are standard; CIP basis proxy is an approximation

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (30 days — stable codebase, low churn expected)
