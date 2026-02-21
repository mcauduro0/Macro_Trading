# Phase 9: Fiscal & FX Equilibrium Agents - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Two analytical agents — FiscalAgent (debt sustainability analysis, fiscal impulse, fiscal dominance risk) and FxEquilibriumAgent (BEER fair value, carry-to-risk, FX flows, CIP basis) — completing 4 of 5 agents in the pipeline. FiscalAgent produces 3 signals; FxEquilibriumAgent produces 4 sub-signals plus 1 composite. Strategy integration and portfolio construction are separate phases.

</domain>

<decisions>
## Implementation Decisions

### DSA Scenario Assumptions

- **Baseline:** r = market-implied forward rates from real DI curve (5Y tenor); g = BCB/Focus consensus GDP forecast. Both update dynamically from existing data.
- **Stress:** baseline + 200bps on r, -1pp on g, -0.5pp on primary balance. IMF-standard shock.
- **Adjustment:** baseline with pb +1.5pp improvement (models successful fiscal consolidation, e.g., Lula fiscal framework adherence).
- **Tailwind:** baseline with g +1pp, r -100bps (commodity super-cycle + BCB easing).
- **Signal direction (FISCAL_BR_DSA):** Claude's discretion — use whichever approach (baseline-as-primary vs scenario majority) produces the most interpretable trading signal.

### Fiscal Dominance Risk Score

- **Components (4):** debt/GDP absolute level + r-g spread (real rate minus real growth) + 12M trend in primary balance/GDP + CB credibility proxy.
- **CB credibility proxy:** Focus survey inflation expectations 12M ahead vs 3.0% target, z-scored. Uses `|expectations_12M - 3.0|` — higher deviation = worse credibility = higher dominance risk. Consistent with `InflationPersistenceModel` logic.
- **Thresholds (signal mapping for FISCAL_BR_DOMINANCE_RISK):**
  - 0–33: LOW risk → SHORT USDBRL (BRL-positive fiscal conditions)
  - 33–66: MODERATE risk → NEUTRAL
  - 66–100: HIGH risk → LONG USDBRL (fiscal stress = BRL weakness)
- **Fiscal impulse (FISCAL_BR_IMPULSE):** Claude's discretion — use whichever cyclical adjustment approach (full CA-PB or simpler 12M change in primary balance/GDP z-scored) is most defensible given Brazil's data availability.

### BEER Model Calibration

- **Lookback window:** Full history 2010–present (~15 years). Maximizes statistical power; consistent with 10Y+ lookbacks in Phase 8.
- **Signal direction:** Symmetric ±5% misalignment threshold. Direction = sign of misalignment: `USDBRL > BEER_fair_value by 5%+` → BRL undervalued → SHORT USDBRL (mean reversion expected). Same logic applies in reverse.
- **Missing predictor handling:** Drop missing predictors, refit OLS with available variables. Return NO_SIGNAL if fewer than 2 predictors remain. No forward-fill.
- **CIP basis measure (FX_BR_CIP_BASIS):** Cupom cambial spread = DDI futures implied rate minus offshore USD LIBOR/SOFR equivalent. B3 DDI data via existing FX connector.

### FX Composite & Carry-to-Risk

- **FX_BR_COMPOSITE:** Yes — weighted composite: BEER 40% + Carry-to-risk 30% + Flow 20% + CIP basis 10%. Apply same conflict dampening pattern as Phase 8 agents (factor 0.70 when sub-signals disagree).
- **Carry-to-risk denominator:** 30-day realized USDBRL volatility (annualized) from daily PTAX data. No options implied vol.
- **FX_BR_CARRY_RISK signal:** Z-score of 12M rolling carry_ratio (carry/vol). |z| > 1.0 fires signal; direction = sign(z). Positive z (unusually attractive carry) → SHORT USDBRL; negative z → LONG USDBRL (carry unwind risk).
- **FX_BR_FLOW components:** BCB FX flow (trade + financial accounts) + CFTC BRL non-commercial positioning — equal-weight z-scores combined into composite flow signal. Both connectors already in system.

### Claude's Discretion

- FISCAL_BR_DSA signal direction methodology (baseline-primary vs scenario-majority)
- FISCAL_BR_IMPULSE: cyclically-adjusted vs simple approach
- Exact composite aggregation formula for dominance risk 0-100 score
- MIN_OBS guards for DSA model (graceful degradation for early backtest dates)
- FiscalFeatureEngine and FxFeatureEngine internal feature key naming

</decisions>

<specifics>
## Specific Ideas

- Phase 8 patterns to replicate: `_tp_history`-style private raw data keys in features dict; conditional imports in `features/__init__.py` for wave independence; conflict dampening at 0.70 for composites.
- DSA formula fixed: `d_{t+1} = d_t*(1+r)/(1+g) - pb` — no deviation from roadmap spec.
- CIP basis direction: positive basis (DDI implied > offshore USD) = capital flow friction = BRL less attractive = LONG USDBRL.
- BEER symmetry: 5% in both directions, no asymmetric adjustment for BRL.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 09-fiscal-fx-equilibrium-agents*
*Context gathered: 2026-02-21*
