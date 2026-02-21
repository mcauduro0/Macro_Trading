---
phase: 03-extended-connectors
plan: 03
subsystem: connectors
tags: [bcb-sgs, tesouro-direto, treasury-gov, yield-curves, breakeven-inflation, respx, pandas]

# Dependency graph
requires:
  - phase: 02-connectors
    provides: BaseConnector ABC, parsing utilities, test infrastructure
provides:
  - B3MarketDataConnector for DI swap curve (DI_PRE, 12 tenors) and NTN-B real rates (NTN_B_REAL)
  - TreasuryGovConnector for nominal (UST_NOM), real (UST_REAL), and breakeven (UST_BEI) yield curves
  - Breakeven inflation computation (nominal - real at matching tenors)
affects: [04-seed-backfill, 05-transforms]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Curve connector pattern: fetch CSV/JSON -> parse tenors -> divide rate by 100 -> CurveData records -> _bulk_insert"
    - "Year-by-year CSV fetching with asyncio.to_thread for pandas parsing"
    - "Breakeven computation as static method matching on (curve_date, tenor_label)"
    - "Best-effort data sources with graceful empty-list fallback on errors"

key-files:
  created:
    - src/connectors/b3_market_data.py
    - tests/connectors/test_b3_market_data.py
    - tests/fixtures/tesouro_direto_sample.json
    - src/connectors/treasury_gov.py
    - tests/connectors/test_treasury_gov.py
    - tests/fixtures/treasury_yield_sample.csv
  modified: []

key-decisions:
  - "BCB SGS as primary DI curve source (series #7805-7816) rather than B3 direct feed -- free, reliable, covers 12 tenors"
  - "Tesouro Direto JSON as best-effort NTN-B source with empty-list fallback on any error (403/404/timeout)"
  - "Treasury CSV parsed via pd.read_csv in asyncio.to_thread to avoid blocking the event loop"
  - "Unknown CSV columns (e.g., '1.5 Mo' added by Treasury in Feb 2025) silently skipped via TENOR_MAP lookup"
  - "Breakeven as static method _compute_breakeven() for easy unit testing without HTTP mocking"

patterns-established:
  - "Curve connector stores to CurveData with _bulk_insert(CurveData, records, 'uq_curves_natural_key')"
  - "Rate conversion from percentage to decimal (divide by 100) at parsing time, not storage time"
  - "Date range chunking for BCB SGS (10-year max per request)"

requirements-completed: [CONN-05, CONN-09]

# Metrics
duration: 18min
completed: 2026-02-19
---

# Phase 3 Plan 3: B3/Tesouro Direto and US Treasury Yield Curve Connectors Summary

**DI swap curve (12 tenors from BCB SGS), NTN-B real rates from Tesouro Direto, and US Treasury nominal/real/breakeven yield curves (13 tenors) with full test coverage**

## Performance

- **Duration:** 18 min
- **Started:** 2026-02-19T21:21:00Z
- **Completed:** 2026-02-19T21:39:31Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- B3MarketDataConnector fetches DI swap curve from 12 BCB SGS series (#7805-7816, 30d-360d) with rate/100 conversion, and NTN-B real rates from Tesouro Direto JSON with graceful fallback
- TreasuryGovConnector fetches nominal and TIPS yield curves from Treasury.gov CSV by year, computes breakeven inflation (nominal - real), handles N/A values and dynamic columns
- 26 tests total (14 B3 + 12 Treasury) all passing with respx HTTP mocking

## Task Commits

Each task was committed atomically:

1. **Task 1: B3/Tesouro Direto connector (CONN-05)** - `19c6a98` (feat)
2. **Task 2: US Treasury yield curve connector (CONN-09)** - `06063b0` (feat)

## Files Created/Modified
- `src/connectors/b3_market_data.py` - B3MarketDataConnector: DI swap curve (DI_PRE) from BCB SGS + NTN-B real rates (NTN_B_REAL) from Tesouro Direto
- `tests/connectors/test_b3_market_data.py` - 14 tests covering DI rate conversion, NTN-B parsing, 404 fallback, registry validation, combined fetch
- `tests/fixtures/tesouro_direto_sample.json` - Sample Tesouro Direto JSON with 6 bonds (3 IPCA+, 1 IPCA+ com Juros, 1 Prefixado, 1 Selic)
- `src/connectors/treasury_gov.py` - TreasuryGovConnector: nominal (UST_NOM), real (UST_REAL), breakeven (UST_BEI) yield curves from Treasury.gov CSV
- `tests/connectors/test_treasury_gov.py` - 12 tests covering CSV parsing, N/A handling, breakeven computation, date filtering, error handling
- `tests/fixtures/treasury_yield_sample.csv` - Sample Treasury CSV with 3 dates, N/A values, empty cells, and unknown "1.5 Mo" column

## Decisions Made
- Used BCB SGS as the DI swap curve source (series #7805-7816) rather than B3 direct feed -- free, reliable, covers all 12 standard tenors
- Tesouro Direto JSON is a best-effort source: returns empty list on any error (403/404/timeout) rather than blocking the connector
- Treasury CSV parsing wrapped in asyncio.to_thread to prevent blocking the event loop during pandas operations
- Unknown CSV columns like "1.5 Mo" (added by Treasury in Feb 2025) are silently skipped by only processing columns present in TENOR_MAP
- Breakeven computation implemented as a static method for easy unit testing without HTTP mocking

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed respx url__contains not supported in test_treasury_gov.py**
- **Found during:** Task 2 (US Treasury connector tests)
- **Issue:** respx 0.22.0 does not support `url__contains` lookup pattern. Tests using `mock.get(url__contains="daily_treasury_yield_curve")` raised `NotImplementedError`.
- **Fix:** Created helper functions `_nominal_path(year)` and `_real_path(year)` that build exact URL paths from the connector's URL template constants, then used `mock.get(_nominal_path(2025)).respond(...)` for exact path matching.
- **Files modified:** tests/connectors/test_treasury_gov.py
- **Verification:** All 12 tests pass after the fix
- **Committed in:** `06063b0` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary fix for test compatibility with installed respx version. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DI swap curve (DI_PRE) and NTN-B real rate (NTN_B_REAL) data available for Brazilian curve analytics
- US Treasury yield curves (UST_NOM, UST_REAL, UST_BEI) available for US rate analytics and breakeven inflation
- Both connectors ready for backfill orchestrator in Phase 4
- Curve data feeds Nelson-Siegel fitting, carry/rolldown, and breakeven transforms in Phase 5

---
*Phase: 03-extended-connectors*
*Completed: 2026-02-19*
