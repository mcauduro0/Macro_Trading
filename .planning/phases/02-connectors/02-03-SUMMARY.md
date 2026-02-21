---
phase: 02-connectors
plan: 03
subsystem: connectors
tags: [yfinance, yahoo-finance, bcb-ptax, odata, fx, ohlcv, asyncio, respx]

# Dependency graph
requires:
  - phase: 02-connectors-01
    provides: "BaseConnector ABC with retry, rate limiting, bulk insert"
provides:
  - "YahooFinanceConnector with 27 tickers (FX, indices, commodities, ETFs)"
  - "BcbPtaxConnector for official PTAX FX fixing rates via OData API"
  - "Instrument auto-creation pattern via ON CONFLICT DO NOTHING"
  - "DataFrame-to-record parsing with NaN->None conversion"
affects: [04-backfill, 05-transforms, api-layer]

# Tech tracking
tech-stack:
  added: [yfinance, zoneinfo]
  patterns: [asyncio-to-thread-wrapping, batch-download-with-delays, odata-api-consumption, closing-bulletin-filtering]

key-files:
  created:
    - src/connectors/yahoo_finance.py
    - src/connectors/bcb_ptax.py
    - tests/connectors/test_yahoo_finance.py
    - tests/connectors/test_bcb_ptax.py
  modified:
    - src/connectors/__init__.py

key-decisions:
  - "asyncio.to_thread() wrapping for yfinance since it uses synchronous HTTP internally"
  - "PTAX cotacaoCompra mapped to open (buy rate), cotacaoVenda mapped to close (sell rate) within OHLCV schema"
  - "dataHoraCotacao parsed with America/Sao_Paulo timezone for point-in-time correctness"
  - "Batch size of 5 tickers per yf.download() call with 1-2 second random delays"
  - "PTAX date ranges split into 1-year chunks for API safety"

patterns-established:
  - "asyncio.to_thread pattern: wrap synchronous library calls for event-loop-safe connectors"
  - "Instrument auto-creation: pg_insert with on_conflict_do_nothing before bulk data insert"
  - "DataFrame parsing: handle single vs multi-ticker yfinance response shapes"
  - "Closing bulletin filter: tipoBoletim=='Fechamento' for official PTAX rate"

requirements-completed: [CONN-10, CONN-11, DATA-01, DATA-03]

# Metrics
duration: 7min
completed: 2026-02-19
---

# Phase 2 Plan 3: Yahoo Finance & BCB PTAX Connectors Summary

**Yahoo Finance connector with 27 tickers (FX/indices/commodities/ETFs) via asyncio.to_thread and BCB PTAX connector with MM-DD-YYYY OData API, closing bulletin filter, and Sao Paulo timezone handling**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-19T19:19:41Z
- **Completed:** 2026-02-19T19:27:39Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- YahooFinanceConnector with 27 tickers from Fase0 guide covering FX, equity indices, commodities, and ETFs
- BcbPtaxConnector fetching official PTAX FX fixing with correct MM-DD-YYYY date format and closing bulletin filter
- Both connectors write to market_data table via ON CONFLICT DO NOTHING for idempotent ingestion
- 30 tests total (16 Yahoo + 14 PTAX) covering registry, batching, parsing, NaN handling, date format, bulletin filtering, timezone
- Complete test suite: 100 tests passing (including all prior phase tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Yahoo Finance connector with 25+ tickers, async wrapping, and tests** - `e70a9c6` (feat)
2. **Task 2: BCB PTAX connector with MM-DD-YYYY date handling, closing bulletin filter, and tests** - `abbcb33` (feat)

## Files Created/Modified
- `src/connectors/yahoo_finance.py` - YahooFinanceConnector with 27 tickers, batch downloading, DataFrame parsing, NaN handling (449 lines)
- `src/connectors/bcb_ptax.py` - BcbPtaxConnector for PTAX OData API with closing bulletin filter and SP timezone (247 lines)
- `tests/connectors/test_yahoo_finance.py` - 16 tests: registry, batching, record format, NaN->None, UTC timestamps, async fetch (275 lines)
- `tests/connectors/test_bcb_ptax.py` - 14 tests: MM-DD-YYYY format, bulletin filtering, buy/sell mapping, timezone, empty response (316 lines)
- `src/connectors/__init__.py` - Added YahooFinanceConnector and BcbPtaxConnector exports

## Decisions Made
- **asyncio.to_thread() for yfinance:** yfinance uses synchronous HTTP internally; wrapping with asyncio.to_thread() prevents event loop blocking while keeping the library's native DataFrame return
- **PTAX rate mapping to OHLCV:** cotacaoCompra (buy) mapped to `open`, cotacaoVenda (sell) mapped to `close`; pragmatic mapping since MarketData model lacks dedicated bid/ask columns
- **Sao Paulo timezone for PTAX:** dataHoraCotacao parsed with ZoneInfo("America/Sao_Paulo") for point-in-time correctness of the fixing rate
- **Batch size 5 with random delays:** Balances throughput vs rate limiting risk for yfinance
- **1-year chunks for PTAX:** Splits long date ranges to avoid potential API timeout or response size issues

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Skipped BcbSgsConnector and FredConnector from __init__.py exports**
- **Found during:** Task 2 (updating __init__.py)
- **Issue:** Plan specified exporting BcbSgsConnector and FredConnector, but these modules are from Plan 02-02 which has not been committed to the branch yet
- **Fix:** Only exported the connectors that exist (YahooFinanceConnector, BcbPtaxConnector). Plan 02-02 will add its own exports when executed.
- **Files modified:** src/connectors/__init__.py
- **Verification:** Import test passes, no ImportError
- **Committed in:** abbcb33 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor adjustment to avoid importing non-existent modules. No scope creep.

## Issues Encountered
None -- both connectors implemented and tested without issues.

## User Setup Required
None - no external service configuration required. Yahoo Finance (yfinance) is a public scraper library. BCB PTAX is a public API with no authentication.

## Next Phase Readiness
- All Phase 2 market data connectors (Yahoo Finance, BCB PTAX) are complete and tested
- BaseConnector pattern proven with two additional connector types (library wrapper + REST OData)
- Instrument auto-creation pattern established for future connectors
- Ready for Phase 4 (seed/backfill) to populate historical data
- Note: yfinance is known to be fragile (scraper-based); may need fallback source if it breaks during backfill

---
*Phase: 02-connectors*
*Completed: 2026-02-19*
