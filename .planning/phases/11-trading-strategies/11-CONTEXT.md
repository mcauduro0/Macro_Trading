# Phase 11: Trading Strategies — Context

## Decisions (Locked)

### Signal-to-Position Mapping
- Weight = strength_base x confidence x max_size (STRONG=1.0, MODERATE=0.6, WEAK=0.3)
- NEUTRAL -> 50% scale-down of existing position
- Orders placed at next open (bar-close trigger, no lookahead bias)

### Regime Adjustment
- On regime change: partial flush (50% scale-down) then signals rebuild
- Direction unconstrained — only position sizes are scaled in unfavorable regimes
- Trigger: >50% of active agents must agree (majority vote)
- Evaluated daily (same cadence as data)

### Instruments & Tenor
- All instrument types in scope: individual equities, index futures, options, FX/rates
- Daily bars (D1) only — consistent with the Phase 10 backtesting engine
- Dynamic filtered universe (daily liquidity/market cap screen)
- Brazil (B3) + US equities in scope

### Strategy Interactions
- Fully independent — no shared position ledger
- Capital allocation: performance-weighted (rolling Sharpe, dynamic)
- Drawdown pause is per-strategy only — others unaffected
- Unlimited concurrent strategies

## Claude's Discretion

- Internal implementation details of each strategy (helper functions, data structures)
- Test fixture design and mock data approach
- File organization within the strategies module

## Deferred Ideas

- None specified
