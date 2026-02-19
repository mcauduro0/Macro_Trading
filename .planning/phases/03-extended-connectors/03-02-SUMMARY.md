---
phase: 03-extended-connectors
plan: 02
subsystem: connectors
tags: [ibge-sidra, bcb-focus, odata, ipca-components, market-expectations, respx]

# Dependency graph
requires:
  - phase: 02-connectors
    provides: "BaseConnector ABC, MacroSeries ORM model, _bulk_insert pattern, test infrastructure with respx"
provides:
  - "IbgeSidraConnector fetching IPCA disaggregated by 9 components (MoM + weight) from Table 7060"
  - "BcbFocusConnector fetching market expectations (IPCA, Selic, GDP, FX, IGP-M) with OData pagination"
  - "_normalize_indicator_name utility for accent/hyphen removal in series keys"
affects: [04-seed-backfill, 05-transforms]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "OData pagination with $top/$skip and MAX_PAGES safety limit"
    - "Path-based SIDRA API with header-row skip (data[0])"
    - "Unicode NFKD normalization for indicator names in series keys"
    - "Period YYYYMM to first-of-month date conversion"

key-files:
  created:
    - src/connectors/ibge_sidra.py
    - tests/connectors/test_ibge_sidra.py
    - tests/fixtures/ibge_sidra_sample.json
    - src/connectors/bcb_focus.py
    - tests/connectors/test_bcb_focus.py
    - tests/fixtures/bcb_focus_sample.json
  modified: []

key-decisions:
  - "IBGE SIDRA uses _CODE_TO_NAME reverse map at class level for O(1) group code lookup"
  - "BCB Focus normalizes indicator names via unicodedata NFKD + strip non-alnum for accent-safe series keys"
  - "BCB Focus uses all 5 indicators with ExpectativasMercadoAnuais entity set (simplified from mixed entity sets)"
  - "Series keys encode reference year for horizon disambiguation: BR_FOCUS_{INDICATOR}_{YEAR}_MEDIAN"

patterns-established:
  - "OData pagination: accumulate pages until len(items) < PAGE_SIZE or MAX_PAGES reached"
  - "SIDRA path-based URL: /values/t/{table}/n1/all/v/{var}/p/{start}-{end}/c315/{codes}"
  - "First-of-month date convention for monthly YYYYMM periods"

requirements-completed: [CONN-06, CONN-04]

# Metrics
duration: 11min
completed: 2026-02-19
---

# Phase 03 Plan 02: IBGE SIDRA and BCB Focus Connectors Summary

**IBGE SIDRA connector for 9 IPCA components (MoM + weight) and BCB Focus connector for market expectations with OData pagination, both storing to macro_series via BaseConnector pattern**

## Performance

- **Duration:** 11 min
- **Started:** 2026-02-19T21:29:49Z
- **Completed:** 2026-02-19T21:40:26Z
- **Tasks:** 2
- **Files created:** 6

## Accomplishments
- IBGE SIDRA connector fetches IPCA disaggregated by 9 consumption groups (Food, Housing, Transport, etc.) with both MoM change (variable 63) and weight (variable 2265) from Table 7060
- BCB Focus connector fetches market consensus expectations for 5 indicators (IPCA, IGP-M, Selic, PIB, Cambio) with OData $top/$skip pagination and MAX_PAGES safety limit
- 34 tests passing (16 IBGE SIDRA + 18 BCB Focus) covering pagination, normalization, date parsing, field validation, and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: IBGE SIDRA connector for IPCA components (CONN-06)** - `46b9864` (feat)
2. **Task 2: BCB Focus connector with OData pagination (CONN-04)** - `1661531` (feat)

## Files Created/Modified
- `src/connectors/ibge_sidra.py` (370 lines) - IbgeSidraConnector with 9 IPCA groups, _CODE_TO_NAME reverse map, _fetch_variable for path-based SIDRA API, header-row skip, YYYYMM period parsing
- `tests/connectors/test_ibge_sidra.py` (279 lines) - 16 tests: registry validation, period parsing, header skip, invalid value skip, series key patterns, required fields, both variables
- `tests/fixtures/ibge_sidra_sample.json` (107 lines) - Sample SIDRA response with header row + 6 data rows (3 valid, 3 invalid values)
- `src/connectors/bcb_focus.py` (351 lines) - BcbFocusConnector with OData pagination, 5 indicators, unicode normalization, reference year encoding in series keys
- `tests/connectors/test_bcb_focus.py` (394 lines) - 18 tests: normalization (accents, hyphens, uppercase), constants, pagination (partial/multi/max/empty), series key encoding, observation_date, required fields, Mediana extraction, None skip, timezone
- `tests/fixtures/bcb_focus_sample.json` (43 lines) - Sample OData response with 3 IPCA items across 2 reference years

## Decisions Made
- IBGE SIDRA uses `_CODE_TO_NAME` reverse map built at class level from `IPCA_GROUPS` dict for O(1) lookup during response parsing
- BCB Focus normalizes indicator names via `unicodedata.normalize("NFKD")` + strip combining chars + strip non-alnum + uppercase -- handles "Cambio" -> "CAMBIO" and "IGP-M" -> "IGPM"
- All 5 BCB Focus indicators use `ExpectativasMercadoAnuais` entity set (simplified from mixed entity sets in plan spec) -- Selic meetings data can be added later if needed
- Series keys encode reference year: `BR_FOCUS_{INDICATOR}_{YEAR}_MEDIAN` for horizon disambiguation (e.g., `BR_FOCUS_IPCA_2025_MEDIAN` vs `BR_FOCUS_IPCA_2026_MEDIAN`)
- Release time set to 8:30 AM Sao Paulo timezone (Focus survey publication time) for point-in-time correctness

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_cambio_normalized_to_cambio respx mock leak**
- **Found during:** Task 2 (BCB Focus test verification)
- **Issue:** Test registered a respx mock route but only called `_normalize_indicator_name()` directly without making HTTP requests, causing respx to error about uncalled routes
- **Fix:** Rewrote test to actually call `conn.fetch()` with cambio mock data and verify series keys contain "CAMBIO" and "BR_FOCUS_CAMBIO_2025_MEDIAN"
- **Files modified:** tests/connectors/test_bcb_focus.py
- **Verification:** All 18 tests pass
- **Committed in:** 1661531 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test bug fix was necessary for test correctness. No scope creep.

## Issues Encountered
None beyond the test fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- IBGE SIDRA and BCB Focus connectors ready for seed/backfill in Phase 4
- Both connectors follow established BaseConnector pattern, compatible with backfill orchestrator
- Remaining Phase 3 plans: 03-03 (B3/Tesouro + US Treasury curves) and 03-04 (CFTC COT + exports update)

## Self-Check: PASSED

All 6 files verified present. Both commits (46b9864, 1661531) verified in git log. Line count minimums met (ibge_sidra.py: 370 >= 120, bcb_focus.py: 351 >= 180).

---
*Phase: 03-extended-connectors*
*Completed: 2026-02-19*
