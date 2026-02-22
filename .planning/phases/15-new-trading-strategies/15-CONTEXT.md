# Phase 15: New Trading Strategies - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

16 new trading strategies spanning FX (4), rates (4), inflation (2), cupom cambial (1), sovereign (3), and cross-asset (2). Each strategy produces StrategySignal outputs compatible with the Phase 14 framework (StrategyRegistry, enhanced StrategySignal dataclass, BacktestEngine v2). Strategies register via @StrategyRegistry.register and pass backtesting with TransactionCostModel. New data connectors are built as needed within each plan.

</domain>

<decisions>
## Implementation Decisions

### Signal conviction & thresholds
- Z-score thresholds and entry criteria: Claude's discretion per strategy — calibrate based on each signal's characteristics and economic rationale
- Stop-loss and take-profit levels: Claude's discretion per strategy — pick volatility-based or fixed-percentage approach depending on asset class and signal type
- Conviction scale: Claude's discretion — fit to the existing StrategySignal dataclass from Phase 14
- Holding periods: Primarily medium-term (1-4 weeks) across all strategies. Event strategies may be shorter but should default toward this range

### Event strategy behavior (RATES-05 FOMC, RATES-06 COPOM)
- Positioning covers both phases: pre-event positioning based on mispricing AND post-event adjustment based on actual outcome vs. expectations
- Post-event exit: adaptive — hold until the mispricing signal (z-score) reverts below threshold, not a fixed number of days
- Position sizing around events: Claude's discretion on whether to scale with surprise potential
- Market expectation baseline: market pricing only — DI1 curve for COPOM, Fed Funds futures for FOMC. No survey data (Focus) in the expectation baseline

### Cross-asset regime logic (CROSS-01, CROSS-02)
- Regime interaction with individual strategies: modulate sizing, not override. Regime-misaligned strategies get reduced sizing but are never hard-suppressed
- CROSS-02 risk appetite inputs: market-based indicators only — VIX, credit spreads (CDS BR), FX implied vol, equity-bond correlation, funding spreads. No positioning/flow data
- Cross-asset strategies produce both regime/risk-appetite scores AND explicit trade recommendations (e.g., in Reflation: long equities, short rates)
- Regime framework: full 4-state classification (Goldilocks, Reflation, Stagflation, Deflation) from the start. Phase 16 adds HMM classifier on top but the 4 states are defined now

### Data gaps & fallback logic
- Missing data handling: skip signal generation entirely — return no signal (None/NaN) for that date. No forward-filling, no degraded models. Clean missing is better than noisy signal
- Data availability: build real connectors for all required data sources. Full strategy code with proper interfaces AND real data loaders — no stubs, no placeholders. Every strategy must be active with real data
- New connectors built within each strategy plan (15-01 through 15-04), co-located with the strategies that need them
- Lookback windows for z-scores: Claude's discretion per strategy based on signal characteristics

### Claude's Discretion
- Z-score entry/exit thresholds per strategy
- Stop-loss/take-profit method per strategy (vol-based vs fixed)
- Conviction normalization approach
- Lookback window selection per strategy
- Event strategy position sizing logic
- Specific data sources for vol surface, CDS curves, and rating migration data

</decisions>

<specifics>
## Specific Ideas

- Event strategies should capture the full event lifecycle: build pre-event positions when model expectations diverge from market pricing, then adjust post-event based on actual outcomes
- Cross-asset regime allocation should produce actionable trades, not just scores — the user wants CROSS-01/02 to be strategies in their own right, not just advisory inputs
- All 16 strategies must work with real data from real connectors — no synthetic data, no mocks, no stubs. Build the data pipeline as part of the strategy delivery
- Medium-term holding (1-4 weeks) is the default orientation — this is a macro fund, not a day-trading operation

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-new-trading-strategies*
*Context gathered: 2026-02-22*
