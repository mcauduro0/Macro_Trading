# Phase 17: Signal Aggregation v2, Risk Engine v2 & Portfolio Optimization - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Quantitative core of portfolio management: aggregate 24+ strategy signals into portfolio targets using Bayesian methods with regime priors and anti-crowding protection, measure portfolio risk with Monte Carlo VaR (copula dependence) and reverse stress testing, and optimize positions using Black-Litterman with agent views and Kelly sizing. Includes signal monitoring for flips, surges, and divergence.

</domain>

<decisions>
## Implementation Decisions

### Signal Aggregation Behavior
- Default aggregation method: **Bayesian with flat prior** when no regime context is available
- All 3 methods available (confidence-weighted average, rank-based, Bayesian with regime prior) — Bayesian is the default
- Crowding penalty: **gentle 20% reduction** when >80% of strategies agree on a direction — consensus is noted but not heavily penalized
- Staleness decay: **linear decay to zero over 5 days** — signal weight drops 20% per day of staleness (simple, predictable)
- Regime prior feeds into Bayesian by **tilting asset-class weights** — e.g., Stagflation prior boosts inflation strategy weights, reduces equity strategy weights. Regime determines WHICH strategies to trust, not overall conviction level

### Risk Model Calibration
- Monte Carlo VaR lookback window: **3 years (756 days)** — captures more tail events and produces more robust distribution fits, even if less responsive to recent regime shifts
- 10,000 simulations with t-Student marginals and Gaussian copula (from requirements)
- New stress scenarios (BR Fiscal Crisis + Global Risk-Off) calibrated to **historical replay severity** — BR Fiscal = 2015 crisis magnitude, Global Risk-Off = 2020 COVID shock. Use actual historical magnitudes, not inflated worst-cases
- Reverse stress testing loss threshold: **configurable, default -10%** — user can set per run, but standard reporting uses 10% portfolio loss target
- **Always report both VaR and CVaR** (Expected Shortfall) at 95% and 99% confidence — VaR for the threshold, CVaR for expected loss beyond it

### Portfolio Construction
- Black-Litterman view confidence: **regime-adjusted** — agent confidence * regime clarity. High HMM probability + confident agent = tight view distribution. Uncertain regime discounts even confident agents
- Kelly sizing: **half Kelly (0.5x)** as the fixed fraction — industry standard balance between growth and drawdown control
- Rebalancing trigger: **daily check + signal-driven threshold** — run optimization daily at close, but only execute trades if aggregate signal change exceeds threshold OR position drift > X% from target. Minimizes unnecessary turnover
- Position limits: **soft limits with risk override** — limits trigger warnings but can be exceeded by a fixed margin (e.g., 20%) when conviction is very high. Not hard caps

### Signal Monitoring Rules
- Conviction surge: **absolute jump >0.3** change in aggregate conviction in one day (on -1 to +1 scale). Pure magnitude, does not adapt to recent volatility
- Signal flips: **any sign change is flagged** (long-to-short or vice versa) + **weekly flip count tracked**. Too many flips per week indicates unstable signals worth investigating
- Daily signal summary: **full report** — all active signals grouped by asset class, regime context, and all triggered alerts. Comprehensive dashboard-style report, not abbreviated
- Strategy divergence: **pairwise within asset class** — flag when any 2 strategies in the same asset class disagree by >0.5 (on -1 to +1 scale). Names the specific conflicting strategies

### Claude's Discretion
- Exact Bayesian prior formulation and posterior update mechanics
- Ledoit-Wolf shrinkage parameters for parametric VaR covariance
- Gaussian copula calibration approach
- Mean-variance optimization solver choice
- Exact signal change threshold and position drift % for rebalancing trigger
- Risk override margin percentage (suggested 20% but can adjust)
- Internal data structures and class hierarchies

</decisions>

<specifics>
## Specific Ideas

- Regime tilting is the key innovation for aggregation — the Cross-Asset Agent's HMM regime probabilities should meaningfully shift which strategies get heard
- VaR + CVaR always together — the fund needs both the "threshold" and "what happens beyond" for proper tail risk awareness
- Historical replay for stress scenarios keeps things grounded — no hypothetical 2x worst-case inflated numbers
- Full daily summary report reflects a PM who wants comprehensive signal visibility, not just alerts

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-signal-aggregation-v2-risk-engine-v2-portfolio-optimization*
*Context gathered: 2026-02-22*
