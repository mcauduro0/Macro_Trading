---
phase: 02-connectors
plan: 01
subsystem: connectors
tags: [httpx, tenacity, bizdays, exchange_calendars, structlog, pytest, baseconnector]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "SQLAlchemy async_session_factory, ORM models, Settings singleton"
provides:
  - "BaseConnector ABC with async HTTP, retry, rate limiting, idempotent _bulk_insert"
  - "parse_numeric_value for period and comma decimal formats"
  - "Business day calendar utilities for ANBIMA (BR) and NYSE (US)"
  - "Tenor parsing and conversion (parse_tenor, tenor_to_date, tenor_to_business_days)"
  - "pytest test infrastructure with conftest fixtures and sample JSON data"
affects: [02-connectors, 03-backfill, 04-transforms]

# Tech tracking
tech-stack:
  added: [httpx, tenacity, yfinance, bizdays, exchange_calendars, python-dateutil, respx, pytest-cov]
  patterns: [AsyncRetrying for instance-scoped retry, bizdays Calendar lazy singleton, exchange_calendars lazy singleton, ON CONFLICT DO NOTHING bulk insert]

key-files:
  created:
    - src/connectors/base.py
    - src/core/utils/logging_config.py
    - src/core/utils/parsing.py
    - src/core/utils/calendars.py
    - src/core/utils/tenors.py
    - tests/conftest.py
    - tests/connectors/conftest.py
    - tests/utils/test_parsing.py
    - tests/utils/test_calendars.py
    - tests/utils/test_tenors.py
    - tests/fixtures/bcb_sgs_sample.json
    - tests/fixtures/fred_sample.json
    - tests/fixtures/ptax_sample.json
    - tests/fixtures/yahoo_sample.json
  modified:
    - pyproject.toml
    - src/connectors/__init__.py

key-decisions:
  - "AsyncRetrying pattern instead of decorator for instance-scoped retry config (MAX_RETRIES accessible at runtime)"
  - "Lazy singleton pattern for ANBIMA and NYSE calendars to avoid load-time overhead"
  - "ON CONFLICT DO NOTHING via SQLAlchemy pg_insert for idempotent bulk inserts across all connectors"

patterns-established:
  - "BaseConnector: async context manager pattern for HTTP client lifecycle"
  - "Semaphore-based rate limiting (RATE_LIMIT_PER_SECOND class attribute)"
  - "_bulk_insert: reusable pg_insert ON CONFLICT DO NOTHING helper"
  - "Lazy calendar singletons for ANBIMA and NYSE"
  - "parse_numeric_value: decimal_sep parameter for multi-format parsing"

requirements-completed: [CONN-01, DATA-03, DATA-04, DATA-05, TEST-03]

# Metrics
duration: 11min
completed: 2026-02-19
---

# Phase 2 Plan 1: Base Connector + Utilities Summary

**BaseConnector ABC with async HTTP retry/rate-limiting, number parsing for BR/intl formats, ANBIMA/NYSE calendar utilities, and tenor conversion functions with 60 passing tests**

## Performance

- **Duration:** 11 min
- **Started:** 2026-02-19T19:05:19Z
- **Completed:** 2026-02-19T19:16:46Z
- **Tasks:** 2
- **Files modified:** 20

## Accomplishments
- BaseConnector ABC with httpx async client, tenacity retry (exponential backoff + jitter), semaphore rate limiting, and _bulk_insert with ON CONFLICT DO NOTHING
- Exception hierarchy: ConnectorError, RateLimitError, DataParsingError, FetchError
- parse_numeric_value handling both period-decimal (international) and comma-decimal (Brazilian) formats
- Business day calendars for ANBIMA (Brazil) and NYSE (US) with lazy loading
- Tenor utilities: parse_tenor, tenor_to_calendar_days, tenor_to_date, tenor_to_business_days
- Full pytest infrastructure with conftest fixtures, sample JSON data, and 60 passing tests
- 8 new Python packages installed (httpx, tenacity, yfinance, bizdays, exchange_calendars, python-dateutil, respx, pytest-cov)

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies and create BaseConnector ABC with exception hierarchy** - `c53987f` (feat)
2. **Task 2: Create data utilities (parsing, calendars, tenors) with tests and test infrastructure** - `3f485a0` (feat)

## Files Created/Modified
- `pyproject.toml` - Added 6 runtime + 2 dev dependencies for Phase 2
- `src/connectors/base.py` - BaseConnector ABC with async HTTP, retry, rate limiting, _bulk_insert
- `src/connectors/__init__.py` - Re-exports BaseConnector and exception classes
- `src/core/utils/__init__.py` - Package init
- `src/core/utils/logging_config.py` - structlog configuration with get_logger()
- `src/core/utils/parsing.py` - parse_numeric_value for multi-format numbers
- `src/core/utils/calendars.py` - ANBIMA and NYSE business day calendar functions
- `src/core/utils/tenors.py` - Tenor parsing and date/business-day conversion
- `tests/__init__.py` - Test package init
- `tests/conftest.py` - Root conftest with sample_dates and load_fixture
- `tests/connectors/__init__.py` - Connector tests package init
- `tests/connectors/conftest.py` - Connector-specific fixtures (bcb_sgs, fred, ptax)
- `tests/utils/__init__.py` - Utils tests package init
- `tests/utils/test_parsing.py` - 18 tests for parse_numeric_value
- `tests/utils/test_calendars.py` - 21 tests for BR and US calendar functions
- `tests/utils/test_tenors.py` - 21 tests for tenor parsing and conversion
- `tests/fixtures/bcb_sgs_sample.json` - BCB SGS API sample response
- `tests/fixtures/fred_sample.json` - FRED API sample response
- `tests/fixtures/ptax_sample.json` - PTAX API sample response
- `tests/fixtures/yahoo_sample.json` - Yahoo Finance sample data

## Decisions Made
- Used AsyncRetrying pattern (not decorator) for tenacity retry so MAX_RETRIES is accessible from self at runtime
- Lazy singleton pattern for ANBIMA and NYSE calendars to avoid load-time overhead
- ON CONFLICT DO NOTHING via SQLAlchemy pg_insert for idempotent bulk inserts -- reusable across all connectors
- structlog configured with ConsoleRenderer for dev; can switch to JSON for production later

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed NYSE business day count test expectation**
- **Found during:** Task 2 (test_calendars.py)
- **Issue:** Test assumed Jan 9, 2025 was a NYSE session, but it was the National Day of Mourning for President Carter
- **Fix:** Changed expected count from 6 to 5 for Jan 2-10 range
- **Files modified:** tests/utils/test_calendars.py
- **Verification:** All 60 tests pass
- **Committed in:** 3f485a0 (Task 2 commit)

**2. [Rule 3 - Blocking] Upgraded setuptools to build multitasking wheel**
- **Found during:** Task 1 (dependency installation)
- **Issue:** multitasking (yfinance dependency) failed to build with old setuptools due to install_layout attribute error
- **Fix:** Upgraded setuptools, pip, and wheel to latest versions
- **Files modified:** None (system packages only)
- **Verification:** pip install -e ".[dev]" succeeded with all 8 new packages
- **Committed in:** N/A (build environment only)

---

**Total deviations:** 2 auto-fixed (1 bug in test data, 1 blocking build issue)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BaseConnector ABC ready for subclassing by BCB SGS, FRED, Yahoo, and PTAX connectors
- All utility functions available for concrete connector implementations
- Test infrastructure ready with fixtures and conftest for connector integration tests
- Concern: yfinance depends on multitasking which required setuptools upgrade -- may need monitoring

## Self-Check: PASSED

All 20 created files verified on disk. Both task commits (c53987f, 3f485a0) confirmed in git log.

---
*Phase: 02-connectors*
*Completed: 2026-02-19*
