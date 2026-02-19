---
phase: 03-extended-connectors
plan: 01
subsystem: connectors
tags: [bcb-sgs, fx-flow, fiscal, flow_data, fiscal_data, respx, timescaledb]

# Dependency graph
requires:
  - phase: 02-connectors
    provides: "BaseConnector ABC, parsing utils, test infrastructure with respx"
provides:
  - "BcbFxFlowConnector: 4 BCB SGS series -> flow_data table"
  - "StnFiscalConnector: 6 BCB SGS series -> fiscal_data table"
affects: [04-seed-backfill, 06-api-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FLOW_TYPE_MAP dict pattern for per-series column mapping"
    - "Tuple-valued SERIES_REGISTRY for multi-field metadata (code, metric, unit)"

key-files:
  created:
    - src/connectors/bcb_fx_flow.py
    - tests/connectors/test_bcb_fx_flow.py
    - tests/fixtures/bcb_fx_flow_sample.json
    - src/connectors/stn_fiscal.py
    - tests/connectors/test_stn_fiscal.py
    - tests/fixtures/stn_fiscal_sample.json
  modified: []

key-decisions:
  - "BcbFxFlowConnector uses flat dict SERIES_REGISTRY + separate FLOW_TYPE_MAP for flow_type lookup"
  - "StnFiscalConnector uses tuple-valued SERIES_REGISTRY dict[str, tuple[int, str, str]] carrying fiscal_metric and unit alongside BCB code"
  - "6 fiscal series instead of 4: added BR_TOTAL_EXPENDITURE (21865) and BR_SOCIAL_SEC_DEFICIT (7620) for completeness"
  - "Tesouro Transparente API skipped per research -- BCB SGS is sole source for fiscal data"

patterns-established:
  - "FLOW_TYPE_MAP pattern: separate dict mapping series_key to target-table-specific column value"
  - "Tuple registry pattern: SERIES_REGISTRY values as (code, metric, unit) tuples when store() needs per-series metadata"

requirements-completed: [CONN-12, CONN-07]

# Metrics
duration: 9min
completed: 2026-02-19
---

# Phase 3 Plan 01: BCB FX Flow and STN Fiscal Connectors Summary

**BCB FX Flow connector (4 series to flow_data) and STN Fiscal connector (6 series to fiscal_data), both using BCB SGS API with respx-mocked tests**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-19T21:29:31Z
- **Completed:** 2026-02-19T21:38:13Z
- **Tasks:** 2
- **Files created:** 6

## Accomplishments
- BcbFxFlowConnector fetches 4 FX flow/swap series from BCB SGS and stores to flow_data with per-series flow_type mapping
- StnFiscalConnector fetches 6 fiscal series from BCB SGS and stores to fiscal_data with per-series fiscal_metric and unit from tuple registry
- 31 new tests (15 + 16) all passing with respx HTTP mocking, covering parsing, edge cases, registry validation, date chunking, and inheritance

## Task Commits

Each task was committed atomically:

1. **Task 1: BCB FX Flow connector (CONN-12)** - `6d553eb` (feat)
2. **Task 2: STN Fiscal connector (CONN-07)** - `30bf812` (feat)

## Files Created/Modified
- `src/connectors/bcb_fx_flow.py` - BcbFxFlowConnector with 4 series (22704, 22705, 22706, 12070), FLOW_TYPE_MAP, stores to FlowData
- `tests/connectors/test_bcb_fx_flow.py` - 15 tests: parsing, empty/invalid handling, flow_type mapping, fetch all/subset, date chunking, registry
- `tests/fixtures/bcb_fx_flow_sample.json` - Sample BCB SGS response with valid, empty, and dash values
- `src/connectors/stn_fiscal.py` - StnFiscalConnector with 6 series as (code, fiscal_metric, unit) tuples, stores to FiscalData
- `tests/connectors/test_stn_fiscal.py` - 16 tests: parsing, empty/invalid handling, fiscal_metric mapping, fetch all/subset, date chunking, registry tuple structure
- `tests/fixtures/stn_fiscal_sample.json` - Sample BCB SGS response with valid, empty, and dash values

## Decisions Made
- BcbFxFlowConnector uses flat `dict[str, int]` for SERIES_REGISTRY (code only) plus separate FLOW_TYPE_MAP dict, since flow_data needs a `flow_type` column but unit is always "USD_MM"
- StnFiscalConnector uses `dict[str, tuple[int, str, str]]` for SERIES_REGISTRY carrying (code, fiscal_metric, unit) per series, since fiscal_data needs both `fiscal_metric` and `unit` columns which vary by series
- Expanded STN Fiscal from 4 to 6 series: added BR_TOTAL_EXPENDITURE (21865) and BR_SOCIAL_SEC_DEFICIT (7620) for more complete fiscal coverage
- Corrected series code assignments: BR_NET_DEBT_GDP_CENTRAL uses 4513 (net debt/GDP), BR_TOTAL_REVENUE uses 21864, BR_TOTAL_EXPENDITURE uses 21865

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BCB FX Flow and STN Fiscal connectors ready for backfill in Phase 4
- Both connectors follow BaseConnector pattern, compatible with backfill orchestrator
- Remaining Phase 3 plans (03-02 through 03-04) can proceed independently

## Self-Check: PASSED

All 6 files verified present. Both commit hashes (6d553eb, 30bf812) verified in git log.

---
*Phase: 03-extended-connectors*
*Completed: 2026-02-19*
