---
phase: 16-crossasset-nlp
plan: 02
subsystem: nlp
tags: [nlp, scraping, httpx, copom, fomc, central-bank, bcb, fed, caching]

# Dependency graph
requires:
  - phase: 14-strategy-framework
    provides: "ORM Base class and models __init__.py pattern"
provides:
  - "COPOMScraper for BCB atas and comunicados scraping with incremental cache"
  - "FOMCScraper for Fed statements and minutes scraping with incremental cache"
  - "NlpDocumentRecord ORM model for central bank document storage"
  - "Alembic migration 007 for nlp_documents table"
  - "ScrapedDocument dataclass for scraper output"
  - "src/nlp package scaffold"
affects: [16-03-sentiment-scoring, nlp-pipeline]

# Tech tracking
tech-stack:
  added: [respx]
  patterns: [incremental-caching, on-conflict-do-nothing, lazy-imports, html-text-extraction]

key-files:
  created:
    - src/nlp/__init__.py
    - src/nlp/scrapers/__init__.py
    - src/nlp/scrapers/copom_scraper.py
    - src/nlp/scrapers/fomc_scraper.py
    - src/core/models/nlp_documents.py
    - alembic/versions/007_create_nlp_documents_table.py
    - tests/test_copom_scraper.py
    - tests/test_fomc_scraper.py
  modified:
    - src/core/models/__init__.py

key-decisions:
  - "ScrapedDocument dataclass shared between COPOM and FOMC scrapers for uniform output"
  - "HTML extraction via stdlib html.parser (no BeautifulSoup dependency) -- strips nav/footer/script tags"
  - "Cache files named {source}_{doc_type}_{YYYY-MM-DD}.json for deterministic lookup"
  - "Sync httpx.Client (not async) for scraper simplicity -- async not needed for batch scraping"

patterns-established:
  - "Incremental cache pattern: check cache_dir for existing JSON files, only fetch uncached dates"
  - "persist_documents with ON CONFLICT DO NOTHING via pg_insert for idempotent bulk insertion"
  - "Lazy __getattr__ imports in scrapers __init__.py to avoid circular dependencies"

requirements-completed: [NLP-01, NLP-02, NLP-05]

# Metrics
duration: 8min
completed: 2026-02-22
---

# Phase 16 Plan 02: NLP Document Scrapers Summary

**COPOMScraper and FOMCScraper with incremental caching for BCB/Fed central bank document retrieval, backed by NlpDocumentRecord ORM and migration 007**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-22T22:28:26Z
- **Completed:** 2026-02-22T22:37:07Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- NlpDocumentRecord ORM model with unique constraint on (source, doc_type, doc_date) for dedup
- COPOMScraper retrieves COPOM atas and comunicados from bcb.gov.br with incremental JSON file caching
- FOMCScraper retrieves FOMC statements and minutes from federalreserve.gov with incremental caching
- Alembic migration 007 creates nlp_documents table with composite index on (source, doc_date)
- 29 comprehensive tests with mocked HTTP -- all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: NLP document model, migration, and scraper package scaffold** - `921f09e` (feat)
2. **Task 2: COPOMScraper, FOMCScraper with incremental caching and tests** - `bda7f00` (feat)

## Files Created/Modified
- `src/nlp/__init__.py` - NLP package init
- `src/nlp/scrapers/__init__.py` - Scrapers package with lazy imports for COPOMScraper, FOMCScraper
- `src/nlp/scrapers/copom_scraper.py` - COPOMScraper: scrapes BCB atas and comunicados with incremental cache
- `src/nlp/scrapers/fomc_scraper.py` - FOMCScraper: scrapes Fed statements and minutes with incremental cache
- `src/core/models/nlp_documents.py` - NlpDocumentRecord ORM with source/doc_type/doc_date/raw_text/scores/key_phrases
- `src/core/models/__init__.py` - Added NlpDocumentRecord to model exports
- `alembic/versions/007_create_nlp_documents_table.py` - Migration 007 with unique constraint and composite index
- `tests/test_copom_scraper.py` - 15 tests for COPOMScraper (init, scraping, caching, persist, errors)
- `tests/test_fomc_scraper.py` - 14 tests for FOMCScraper (init, scraping, caching, persist, errors)

## Decisions Made
- Used sync httpx.Client (not async) for scraper simplicity -- batch scraping doesn't benefit from async
- HTML extraction via stdlib html.parser to avoid adding BeautifulSoup dependency
- ScrapedDocument dataclass shared between both scrapers for uniform output format
- Cache files named `{source}_{doc_type}_{YYYY-MM-DD}.json` for deterministic O(1) lookup
- Rate limiting at 2 seconds between requests to avoid overloading central bank sites

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- NLP document storage and scraping infrastructure complete
- Ready for Plan 16-03: hawk/dove sentiment scoring pipeline
- ScrapedDocument dataclass and NlpDocumentRecord provide the input/output interface for sentiment analysis

## Self-Check: PASSED

All 9 files verified present on disk. Both commit hashes (921f09e, bda7f00) verified in git log. 29 tests passing.

---
*Phase: 16-crossasset-nlp*
*Completed: 2026-02-22*
