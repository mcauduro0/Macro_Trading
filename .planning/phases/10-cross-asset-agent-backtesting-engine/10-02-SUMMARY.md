---
phase: 10-cross-asset-agent-backtesting-engine
plan: "02"
subsystem: backtesting
tags: [backtesting, portfolio, notional-positions, PIT, alembic, ORM, hypertable, strategy-protocol]

# Dependency graph
requires:
  - phase: 07-agent-framework-data-loader
    provides: "PointInTimeDataLoader for PIT-correct market data access"
  - phase: 07-agent-framework-data-loader
    provides: "AgentReportRecord ORM pattern and migration 003 revision chain"
provides:
  - "BacktestConfig frozen dataclass with cost/leverage parameters"
  - "BacktestEngine event loop with PIT enforcement and rebalance date generation"
  - "Portfolio class with notional-based positions, mark-to-market, and rebalance with transaction costs"
  - "StrategyProtocol for type-safe strategy interface"
  - "BacktestResultRecord ORM for persisting backtest results"
  - "Alembic migration 004: strategy_signals hypertable + backtest_results table"
affects: [10-cross-asset-agent-backtesting-engine, strategies, metrics, reporting]

# Tech tracking
tech-stack:
  added: [pandas.bdate_range, collections.namedtuple]
  patterns: [notional-based-portfolio, event-driven-backtesting, frozen-dataclass-config, strategy-protocol]

key-files:
  created:
    - src/backtesting/__init__.py
    - src/backtesting/engine.py
    - src/backtesting/portfolio.py
    - src/core/models/backtest_results.py
    - alembic/versions/004_add_strategy_signals_backtest.py
  modified:
    - src/core/models/__init__.py

key-decisions:
  - "Notional-based positions (not shares) -- simplifies rebalancing, no price lookup for position access"
  - "Cash-position transfer on rebalance -- cash decreases by trade_notional + cost to preserve total_equity invariant"
  - "BacktestRawResult namedtuple as interim return type until Plan 10-03 adds full BacktestResult dataclass with metrics"
  - "Price gap filling via _last_known_prices cache -- forward-fills prices when loader returns empty for a ticker"
  - "Alembic migration not runnable in current environment (alembic CLI not installed) -- will run when DB is available"

patterns-established:
  - "StrategyProtocol: all strategies implement strategy_id + generate_signals(as_of_date) -> dict[str, float]"
  - "BacktestEngine passes as_of_date to strategy -- PIT enforcement delegated to PointInTimeDataLoader"
  - "Portfolio._rebalance_date set by engine before calling rebalance() -- avoids date parameter threading"
  - "BacktestResultRecord naming convention (not BacktestResult) to avoid collision with dataclass"

requirements-completed: [BACK-01, BACK-02, BACK-03, BACK-05, BACK-08]

# Metrics
duration: 5min
completed: 2026-02-21
---

# Phase 10 Plan 02: Backtesting Engine Core Summary

**Event-driven BacktestEngine with notional-based Portfolio, frozen BacktestConfig, StrategyProtocol, BacktestResultRecord ORM, and Alembic migration 004 for strategy_signals/backtest_results tables**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-21T19:15:28Z
- **Completed:** 2026-02-21T19:20:19Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- BacktestEngine event loop iterates business-day rebalance dates (daily/weekly/monthly), calls strategy.generate_signals(as_of_date) with PIT enforcement via PointInTimeDataLoader
- Portfolio class with notional-based positions, mark-to-market price adjustments, leverage enforcement, transaction cost + slippage deduction, and round-trip PnL tracking
- BacktestResultRecord ORM with 19 columns (metrics, JSONB equity_curve/monthly_returns) plus Alembic migration 004 creating strategy_signals hypertable and backtest_results regular table

## Task Commits

Each task was committed atomically:

1. **Task 1: BacktestConfig, BacktestEngine, and Portfolio class** - `2168fc8` (feat)
2. **Bug fix: Portfolio.rebalance() cash-position transfer** - `281c557` (fix)
3. **Task 2: BacktestResultRecord ORM, models/__init__.py, migration 004** - `ccf5735` (feat)

## Files Created/Modified
- `src/backtesting/__init__.py` - Package init re-exporting BacktestEngine, BacktestConfig, Portfolio
- `src/backtesting/engine.py` - BacktestConfig frozen dataclass, BacktestEngine event loop with PIT, StrategyProtocol
- `src/backtesting/portfolio.py` - Portfolio class with notional positions, mark_to_market(), rebalance() with costs
- `src/core/models/backtest_results.py` - BacktestResultRecord ORM (19 columns, JSONB fields)
- `src/core/models/__init__.py` - Added BacktestResultRecord import and __all__ entry
- `alembic/versions/004_add_strategy_signals_backtest.py` - Migration 004: strategy_signals hypertable + backtest_results table

## Decisions Made
- Notional-based positions: simplifies rebalancing (no share count, no price lookup for position value)
- Cash-position transfer on rebalance: cash decreases by trade_notional + cost to preserve total_equity == cash + sum(positions) invariant
- BacktestRawResult namedtuple as interim return type -- Plan 10-03 will replace with full BacktestResult dataclass
- Price gap filling via _last_known_prices cache for tickers where loader returns empty data
- standard logging (not structlog) for engine -- matches Python stdlib pattern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Portfolio.rebalance() cash-position transfer**
- **Found during:** Task 1 (BacktestConfig, BacktestEngine, and Portfolio class)
- **Issue:** Plan's rebalance() code only deducted transaction costs from cash but did not transfer the trade_notional between cash and position, violating the total_equity == cash + sum(positions) invariant. Allocating weight=1.0 would double-count equity.
- **Fix:** Changed `self.cash -= cost` to `self.cash -= trade_notional + cost` for buys, and `self.cash -= cost` to `self.cash += current_notional - cost` for exits
- **Files modified:** src/backtesting/portfolio.py
- **Verification:** Portfolio with weight=1.0 now has cash=-700 (cost only) + position=1M = total 999,300 (correct)
- **Committed in:** 281c557

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Critical fix for portfolio accounting correctness. Without this fix, all backtesting results would show inflated equity.

## Issues Encountered
- Alembic CLI not available in this environment (`alembic` command not found, module not directly executable). Migration file is correctly structured and will run when DB infrastructure is available. Verified migration file contents programmatically.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BacktestEngine scaffold ready for Plan 10-03 to add metrics computation (Sharpe, Sortino, Calmar, drawdown), BacktestResult dataclass, and result persistence
- StrategyProtocol ready for strategy implementations to plug into BacktestEngine.run()
- BacktestResultRecord ORM ready for Plan 10-03 to persist computed metrics

## Self-Check: PASSED

All 6 created/modified files verified on disk. All 3 commit hashes (2168fc8, 281c557, ccf5735) verified in git log.

---
*Phase: 10-cross-asset-agent-backtesting-engine*
*Completed: 2026-02-21*
