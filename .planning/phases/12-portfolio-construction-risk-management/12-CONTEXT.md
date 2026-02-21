# Phase 12: Portfolio Construction & Risk Management - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Signal aggregation across agents and strategies, portfolio construction with risk-budget scaling, and a complete risk management engine with VaR, stress testing, limits, and circuit breakers. This phase takes the 5 agent signals (Phases 8-10) and 8 trading strategies (Phase 11) and wires them into a portfolio that manages itself — aggregating signals, sizing positions, enforcing risk limits, and protecting capital.

</domain>

<decisions>
## Implementation Decisions

### Signal conflict resolution
- **Aggregation method:** Weighted vote — each agent has a fixed weight, the weighted sum determines net direction. Conflicting signals partially cancel out.
- **Agent weights:** Domain-tuned per asset class. E.g., for DI rates: MonetaryPolicy gets highest weight, Inflation second, etc. Weights are NOT equal — each agent's relevance varies by asset class. Claude to determine sensible default weight matrices during implementation.
- **CrossAsset veto:** CrossAssetAgent has veto power to reduce/flatten positions when its regime score is extreme (e.g., < -0.7). Other agents cannot veto.
- **Intra-asset-class conflicts:** When strategies within the same asset class conflict (e.g., RATES_BR_01 says LONG but RATES_BR_02 says SHORT), flag the conflict in the risk report AND dampen the net position size (reduce by 30-50%) as a penalty for low conviction.

### Position sizing & regime scaling
- **Base methodology:** Risk parity + conviction overlay. Risk parity as the base allocation (each position sized to contribute equally to portfolio risk), then scaled up/down by signal conviction.
- **Regime scaling:** 3 discrete regimes — Risk-On (100% allocation), Neutral (70%), Risk-Off (40%). Sharp steps, easy to reason about.
- **Regime transitions:** Gradual adjustment over 2-3 days when regime changes (e.g., 50% of adjustment day 1, 100% by day 3). Avoids market impact and whipsaw.
- **Max position concentration:** No single position can exceed 20% of portfolio risk budget.
- **Rebalancing trigger:** Threshold-triggered — rebalance only when positions drift beyond thresholds (e.g., >5% deviation from target). Only trades when needed, no fixed daily schedule.

### Circuit breaker behavior
- **Drawdown response:** Tiered de-risking. At -5% drawdown, reduce exposure by 50%. At -10%, flatten all positions. Clear escalation path. (Note: roadmap specifies 3 levels at -3%/-5%/-8% — Claude to reconcile these during planning, using the user's intent of tiered escalation.)
- **Re-entry conditions:** Automatic re-entry after a cooldown period (5 trading days) if drawdown recovers above -3%. Gradual ramp-up to full exposure over 3 days.
- **Loss limit granularity:** Three layers of circuit breakers — portfolio-level drawdown, per-strategy daily loss, and per-asset-class loss. Each can fire independently.
- **Alerting:** Log to monitoring system + send real-time alert (webhook/email). Every circuit breaker event is logged with full context (positions, P&L, signals at time of trigger).

### Stress scenario design
- **Scenario type:** Historical replay only — replaying actual market moves from real crises. No hypothetical/synthetic scenarios in this phase.
- **Stress test impact:** Advisory only — stress results are reported but don't automatically change positions. Risk manager reviews and decides.
- **VaR methodology:** Monte Carlo simulation with fitted distributions. Most flexible, captures complex portfolio interactions.
- **Computation frequency:** Daily VaR/CVaR calculations + weekly full stress scenario replays. Balances computational cost with timeliness.

### Claude's Discretion
- Exact domain-tuned weight matrices per agent per asset class (within the weighted vote framework)
- Monte Carlo simulation parameters (number of simulations, distribution fitting approach)
- Historical stress scenario selection (roadmap suggests Taper Tantrum 2013, BR Crisis 2015, COVID 2020, Rate Shock 2022 — Claude may adjust)
- Exact drift thresholds for rebalancing trigger
- Cooldown period fine-tuning
- Risk report format and content layout
- Damping factor for intra-asset-class conflicts (within 30-50% range)

</decisions>

<specifics>
## Specific Ideas

- Regime transitions should be gradual (2-3 days) to avoid whipsaw from transient regime shifts
- CrossAsset veto is the only override mechanism — all other agents contribute proportionally via weights
- Circuit breaker alerts must include full context (positions, P&L, signal state) for post-mortem analysis
- Stress tests are informational/advisory in this phase — they inform the risk report but don't block trades
- VaR uses Monte Carlo, not historical simulation — user prefers the flexibility of fitted distributions

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-portfolio-construction-risk-management*
*Context gathered: 2026-02-21*
