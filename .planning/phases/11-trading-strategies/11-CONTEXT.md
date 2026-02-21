# Phase 11: Trading Strategies - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a BaseStrategy ABC and 8 initial trading strategies spanning rates (4), inflation (1), FX (1), cupom cambial (1), and sovereign risk (1). Each strategy consumes agent signals from the registry and produces tradeable StrategyPosition outputs. Portfolio construction and risk management are Phase 12.

</domain>

<decisions>
## Implementation Decisions

### Signal-to-Position Mapping

- Position weight formula: `position = strength_base × confidence × max_size`
  - STRONG base = 1.0, MODERATE base = 0.6, WEAK base = 0.3
  - Confidence (0–1) scales the position proportionally (e.g., STRONG at 0.7 confidence → 0.70 × max_size)
- NEUTRAL signal behavior: **50% scale-down** — reduce the existing position by half; new signals can rebuild it
- Order placement timing: **bar-close trigger** — orders placed at next open after bar close (no lookahead bias)

### Claude's Discretion (Signal-to-Position)
- Exact STRONG/MODERATE/WEAK base values (tiered approach recommended; values above are starting point)

### Regime Adjustment Behavior

- On regime change: **partial flush** — scale all existing positions down by a regime-change factor (50%), then let new signals rebuild under the new regime
- Directional constraint: **size scaling only** — strategies may go long or short in any regime, but position sizes are scaled (e.g., reduced in unfavorable regimes); no hard directional cap
- Regime-change trigger: **majority vote** — >50% of active agents must report a new regime before the system switches
- Regime evaluation frequency: **same as data updates** (daily, matching data ingestion cadence)

### Instrument & Tenor Choices

- Instrument types: **individual equities, index futures/proxies, options on equities, and FX/rates instruments** — full multi-asset scope
- Primary timeframe: **daily (D1) only** — all strategies operate on daily bars (close-to-close), consistent with Phase 10 backtesting engine
- Universe management: **dynamic filtered universe** — universe is screened daily based on liquidity, market cap, and sector criteria
- Geographic scope: **Brazil (B3) + US equities** — both markets are in scope

### Strategy Interaction Rules

- Cross-strategy signal combination: **fully independent** — each strategy trades its own capital allocation with no shared position ledger or cross-strategy awareness
- Capital allocation across strategies: **performance-weighted (dynamic, rolling Sharpe)** — capital shifts toward strategies with better recent risk-adjusted performance
- Drawdown behavior: **per-strategy pause** — a strategy hitting its max drawdown limit pauses only itself; other strategies are unaffected
- Concurrency: **unlimited** — no cap on simultaneously running strategies; only stop is per-strategy drawdown

</decisions>

<specifics>
## Specific Ideas

- The 8 strategies are defined in the roadmap plans:
  - RATES_BR_01: Carry & Roll-Down (DI curve, long at optimal tenor when carry-to-risk exceeds threshold)
  - RATES_BR_02: Taylor Rule Misalignment (DI direction when gap > 100bps vs Taylor-implied rate)
  - RATES_BR_03: Curve Slope (flattener/steepener trades)
  - RATES_BR_04: US Rates Spillover (spread mean reversion)
  - INF_BR_01: Breakeven Inflation Trade
  - FX_BR_01: Carry & Fundamental (carry-to-risk 40% + BEER misalignment 35% + flow score 25%, regime-adjusted)
  - CUPOM_01: CIP Basis Mean Reversion
  - SOV_BR_01: Fiscal Risk Premium
- FX_BR_01 weights are explicitly locked: 40% carry-to-risk, 35% BEER, 25% flow
- ALL_STRATEGIES dict must export all 8 strategies by ID for backtesting and pipeline integration
- StrategyPosition outputs: weight in [-1, 1], confidence in [0, 1], respecting configured position limits

</specifics>

<deferred>
## Deferred Ideas

- None raised during discussion — discussion stayed within Phase 11 scope

</deferred>

---

*Phase: 11-trading-strategies*
*Context gathered: 2026-02-21*
