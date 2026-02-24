---
phase: 20-pms-database-position-manager
plan: 02
subsystem: pms
tags: [position-manager, mark-to-market, pricing, b3-di, pnl, risk-metrics, dv01]

# Dependency graph
requires:
  - phase: 20-pms-database-position-manager
    plan: 01
    provides: "5 PMS SQLAlchemy models (PortfolioPosition, TradeProposal, DecisionJournal, DailyBriefing, PositionPnLHistory)"
  - phase: 14-strategy-framework
    provides: "TransactionCostModel for per-instrument cost computation"
provides:
  - "PositionManager with open/close/MTM/book/pnl_timeseries operations"
  - "MarkToMarketService with instrument-aware price sourcing, MTM computation, DV01, VaR contribution"
  - "Pricing module with 8 pure functions (rate_to_pu, pu_to_rate, compute_dv01_from_pu, ntnb_yield_to_price, cds_spread_to_price, compute_fx_delta, compute_pnl_brl, compute_pnl_usd)"
  - "48 comprehensive tests covering all PMS core operations"
affects: [21-trade-workflow, 22-morning-pack, 23-pms-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dict-based position representation decoupled from SQLAlchemy ORM for testability"
    - "Instrument-aware P&L: RATES uses PU-based quantity pricing, FX/general uses percentage return"
    - "Direct file-level import (importlib.util) to avoid heavy __init__.py transitive chains"
    - "SHA256 content hash on all journal entries for audit integrity"
    - "Dual-currency P&L (BRL primary + USD derived via current FX rate)"
    - "Price sourcing cascade: manual override -> DB lookup (placeholder) -> entry price fallback with staleness detection"

key-files:
  created:
    - src/pms/__init__.py
    - src/pms/pricing.py
    - src/pms/mtm_service.py
    - src/pms/position_manager.py
    - tests/test_pms/__init__.py
    - tests/test_pms/test_position_manager.py
  modified: []

key-decisions:
  - "Dict-based positions decoupled from ORM -- caller handles session management and persistence"
  - "Direct file-level import of TransactionCostModel via importlib.util to avoid backtesting.__init__ chain (agents, database, asyncpg)"
  - "Relative imports within src/pms/ package for internal module references"
  - "Simplified VaR contribution via notional-proportional allocation (full Component VaR from Phase 17 integration deferred to Phase 22)"
  - "CDS spread returned as-is for price (spread-quoted instrument); P&L from spread changes"

patterns-established:
  - "PositionManager in-memory store pattern: _positions, _journal, _pnl_history lists for DB-free testing"
  - "Journal entry pattern: auto-created on open/close with content_hash and is_locked=True"
  - "Price override pattern: dict[str, float] passed to MTM for manual marks"
  - "Pricing module as pure stateless functions -- no class, no I/O"

requirements-completed: [PMS-PM-01, PMS-PM-02, PMS-PM-03, PMS-PM-04, PMS-MTM-01, PMS-MTM-02]

# Metrics
duration: 11min
completed: 2026-02-24
---

# Phase 20 Plan 02: PositionManager & MarkToMarketService Summary

**PositionManager with open/close/MTM/book lifecycle, MarkToMarketService with B3 DI PU-convention pricing, dual BRL/USD P&L, and 48 tests passing without DB dependency**

## Performance

- **Duration:** 11 min
- **Started:** 2026-02-24T02:16:15Z
- **Completed:** 2026-02-24T02:27:25Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- PositionManager fully implements open_position (with risk metrics DV01/delta, auto-journal with SHA256 hash, transaction cost, dual notional), close_position (realized P&L in BRL+USD, exit cost, journal entry), mark_to_market (instrument-aware pricing with manual overrides, DV01 recomputation, P&L snapshot persistence), get_book (AUM/leverage/P&L summary, positions list, by_asset_class breakdown, closed_today), and get_pnl_timeseries (per-position and portfolio-level aggregation)
- MarkToMarketService handles price sourcing with manual override cascade, staleness detection (3-day threshold), position MTM computation, DV01 calculation, and proportional VaR contribution allocation
- 8 pure pricing functions implementing B3 DI PU convention (rate_to_pu, pu_to_rate, compute_dv01_from_pu), NTN-B real yield pricing, CDS spread, FX delta, and instrument-aware P&L (RATES vs FX vs general)
- 48 comprehensive pytest tests covering all methods, edge cases, and error paths -- all passing in 0.3s without any DB dependency

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pricing module and MarkToMarketService** - `49f3908` (feat)
2. **Task 2: Create PositionManager service with open/close/MTM/book and comprehensive tests** - `a6ab8ea` (feat)

## Files Created/Modified
- `src/pms/__init__.py` - Package init exporting PositionManager and MarkToMarketService
- `src/pms/pricing.py` - 8 pure pricing functions (B3 DI PU, NTN-B, CDS, FX, P&L BRL/USD)
- `src/pms/mtm_service.py` - MarkToMarketService with price sourcing, MTM, DV01, VaR contribution
- `src/pms/position_manager.py` - PositionManager with open/close/MTM/book/pnl_timeseries
- `tests/test_pms/__init__.py` - Test package init
- `tests/test_pms/test_position_manager.py` - 48 comprehensive tests (16 pricing, 8 open, 7 close, 5 MTM, 5 book, 2 timeseries, 5 MTM service)

## Decisions Made
- Dict-based positions decoupled from ORM: PositionManager operates on plain dicts, not SQLAlchemy objects. The caller (API layer or Dagster pipeline) handles session management. This enables pure in-memory testing.
- Direct file-level import of TransactionCostModel: Used importlib.util.spec_from_file_location to load costs.py directly, avoiding the heavy backtesting.__init__ import chain that pulls in agents, database, asyncpg, and requires a running PostgreSQL instance.
- Simplified VaR contribution: Proportional allocation by notional weight as placeholder. Full Component VaR integration with Phase 17 risk engine deferred to Phase 22.
- CDS spread as price: For CDS instruments, the spread in basis points IS the price since CDS is spread-quoted. P&L comes from spread movements.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing numpy, scipy, pandas, pydantic dependencies**
- **Found during:** Task 1 (MTM service import verification)
- **Issue:** TransactionCostModel import chain through backtesting.__init__ required numpy, scipy, pandas, pydantic
- **Fix:** pip install of missing packages + switched to direct file-level import via importlib.util to break the heavy __init__ chain
- **Files modified:** src/pms/mtm_service.py, src/pms/position_manager.py (import strategy)
- **Verification:** All imports succeed, 48 tests pass
- **Committed in:** 49f3908, a6ab8ea

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Import strategy changed to avoid heavy transitive dependency chain. No scope creep.

## Issues Encountered
- The `src.backtesting.__init__` triggers a deep import chain (backtesting -> engine -> agents -> database -> asyncpg) requiring a running database. Resolved by using importlib.util.spec_from_file_location to load just the costs.py module file directly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- PositionManager and MarkToMarketService ready for use by trade workflow (Phase 21)
- All pricing functions available for MorningPack (Phase 22) and PMS API (Phase 23)
- In-memory store pattern ready for DB wiring in Phase 21 (swap _positions list for DB queries)
- 48 tests provide regression coverage for any future changes

## Self-Check: PASSED

All 6 claimed files verified to exist on disk. Both task commit hashes (49f3908, a6ab8ea) verified in git log.

---
*Phase: 20-pms-database-position-manager*
*Completed: 2026-02-24*
