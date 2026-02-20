---
phase: 03-extended-connectors
plan: 04
subsystem: connectors
tags: [cftc, cot, positioning, futures, disaggregated, flow-data, zip, socrata, csv, respx]

# Dependency graph
requires:
  - phase: 02-connectors
    provides: BaseConnector ABC, _bulk_insert, FlowData model, test infrastructure
  - phase: 03-extended-connectors (plans 01-03)
    provides: BcbFxFlowConnector, BcbFocusConnector, B3MarketDataConnector, IbgeSidraConnector, StnFiscalConnector, TreasuryGovConnector
provides:
  - CftcCotConnector for disaggregated futures positioning (12 contracts x 4 categories = 48 series)
  - Complete connectors package with all 11 connectors exported from src/connectors/__init__.py
  - Phase 3 connector suite fully wired for backfill orchestration
affects: [04-seed-backfill, 06-api-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ZIP-in-memory extraction: zipfile.ZipFile(io.BytesIO(response.content)) for bulk CSV archives"
    - "Dual-source connector: historical from ZIP files, current from Socrata CSV API"
    - "asyncio.to_thread for pandas CSV parsing inside async connectors"
    - "Reverse contract map for code-to-name lookups in net position computation"

key-files:
  created:
    - src/connectors/cftc_cot.py
    - tests/connectors/test_cftc_cot.py
    - tests/fixtures/cftc_disagg_sample.csv
  modified:
    - src/connectors/__init__.py
    - tests/connectors/conftest.py

key-decisions:
  - "12 contracts selected: ES, NQ, YM, TY, US, FV, TU, ED, CL, GC, SI, DX (major equity, rates, commodity, FX futures)"
  - "4 disaggregated categories: DEALER, ASSETMGR, LEVERAGED, OTHER (covers all speculator/hedger segments)"
  - "Socrata CSV as current-week source (API is free, no auth, 5000 row limit sufficient)"
  - "Series key format CFTC_{CONTRACT}_{CATEGORY}_NET standardized for consistent flow_data storage"
  - "ZIP files downloaded with 120s timeout (large files) vs standard 30s for JSON APIs"

patterns-established:
  - "Bulk CSV connector stores to FlowData with _bulk_insert(FlowData, records, 'uq_flow_data_natural_key')"
  - "Socrata column normalization: handle both lowercase and capitalized variants"
  - "Reverse lookup map for CFTC contract codes: _reverse_contract_map = {v: k for k, v in CONTRACT_CODES.items()}"

requirements-completed: [CONN-08]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 3 Plan 4: CFTC COT Connector and Connectors Package Exports Summary

**CFTC COT disaggregated positioning for 12 futures contracts x 4 trader categories (48 series) with ZIP/Socrata dual-source, plus unified package exports for all 11 connectors**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T21:48:42Z
- **Completed:** 2026-02-19T21:53:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- CftcCotConnector downloads yearly disaggregated ZIP archives from cftc.gov and current-week CSV from Socrata, computes net positions (long - short) for DEALER, ASSETMGR, LEVERAGED, OTHER across 12 contracts
- 20 CFTC-specific tests covering net computation, contract filtering, ZIP extraction, Socrata fallback, missing columns, empty DataFrames, and registry validation
- Updated src/connectors/__init__.py with all 7 Phase 3 connectors -- `__all__` now has 16 entries (5 base + 4 Phase 2 + 7 Phase 3)
- Full connector test suite passes: 162 tests across all 11 connectors

## Task Commits

Each task was committed atomically:

1. **Task 1: CFTC COT disaggregated connector (CONN-08)** - `0bca6cc` (feat)
2. **Task 2: Update connectors package exports and test conftest** - `8c2e1e2` (feat)

## Files Created/Modified
- `src/connectors/cftc_cot.py` - CftcCotConnector: ZIP download, Socrata CSV, net position computation, flow_data storage for 48 series
- `tests/connectors/test_cftc_cot.py` - 20 tests with respx mocking for cftc.gov and publicreporting.cftc.gov
- `tests/fixtures/cftc_disagg_sample.csv` - Sample disaggregated CSV with 2 tracked contracts (ES, TY), 2 dates, 1 untracked contract (999999)
- `src/connectors/__init__.py` - Updated with Phase 3 connector imports and __all__ (16 entries total)
- `tests/connectors/conftest.py` - Added Phase 3 fixture loaders (_load_text helper, 7 new fixtures)

## Decisions Made
- Selected 12 key futures contracts spanning equities (ES, NQ, YM), rates (TY, US, FV, TU), energy (CL), metals (GC, SI), FX (DX), and legacy (ED) for broad macro coverage
- Used 4 disaggregated categories (DEALER, ASSETMGR, LEVERAGED, OTHER) matching CFTC report structure -- provides richer breakdown than legacy report
- Socrata CSV API chosen for current-week data: free, no authentication, reliable; falls back gracefully on error
- 120-second timeout for ZIP downloads (disaggregated CSV archives can be 10-20MB)
- Series key format `CFTC_{CONTRACT}_{CATEGORY}_NET` allows consistent querying and z-score computation across all 48 series

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 11 connectors complete and exported from src.connectors package
- Phase 3 (Extended Connectors) fully complete: 7 new data sources ready for ingestion
- Combined test suite: 162 tests across all connectors, all passing
- Ready for Phase 4 (Seed and Backfill): instruments seeding, series metadata, and historical data population
- CFTC positioning data feeds flow analysis, z-score computation, and API endpoints in later phases

## Self-Check: PASSED

All files verified present, all commits verified in git log:
- src/connectors/cftc_cot.py: FOUND
- tests/connectors/test_cftc_cot.py: FOUND
- tests/fixtures/cftc_disagg_sample.csv: FOUND
- src/connectors/__init__.py: FOUND
- tests/connectors/conftest.py: FOUND
- Commit 0bca6cc: FOUND
- Commit 8c2e1e2: FOUND

---
*Phase: 03-extended-connectors*
*Completed: 2026-02-19*
