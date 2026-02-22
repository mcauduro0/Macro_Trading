---
phase: 16-crossasset-nlp
plan: 03
subsystem: nlp
tags: [nlp, sentiment-analysis, hawk-dove, dictionary, copom, fomc, central-bank, pipeline]

# Dependency graph
requires:
  - phase: 16-crossasset-nlp
    provides: "ScrapedDocument dataclass, NlpDocumentRecord ORM, NLP package scaffold"
provides:
  - "CentralBankSentimentAnalyzer with dictionary-based hawk/dove scoring and optional LLM refinement"
  - "NLPProcessor pipeline: clean -> score -> extract -> compare -> persist"
  - "Portuguese hawk/dove dictionary (65 hawk + 65 dove terms) for COPOM"
  - "English hawk/dove dictionary (64 hawk + 70 dove terms) for FOMC"
  - "SentimentResult and ProcessedDocument dataclasses"
  - "Categorical change_score classification (5 levels)"
affects: [nlp-pipeline, signal-aggregation, cross-asset-scoring]

# Tech tracking
tech-stack:
  added: []
  patterns: [dictionary-term-matching, weighted-scoring, categorical-change-detection, pipeline-orchestration]

key-files:
  created:
    - src/nlp/dictionaries/__init__.py
    - src/nlp/dictionaries/hawk_dove_pt.py
    - src/nlp/dictionaries/hawk_dove_en.py
    - src/nlp/sentiment_analyzer.py
    - src/nlp/nlp_processor.py
    - tests/test_sentiment_analyzer.py
    - tests/test_nlp_processor.py
  modified: []

key-decisions:
  - "Dictionary-based scoring as primary method with 0.7 dict + 0.3 LLM blend when API key available"
  - "Term weights in [0.0, 1.0] range -- higher weight indicates stronger hawk/dove signal"
  - "Net score = hawk_weighted_sum/total - dove_weighted_sum/total, clipped to [-1, +1]"
  - "Change score thresholds: |delta| > 0.3 = major shift, > 0.1 = minor shift, else neutral"
  - "Key phrase extraction preserves 5-word surrounding context from normalized text"
  - "NLPProcessor batch processing sorts by date ascending for sequential change detection"

patterns-established:
  - "Dictionary-based NLP scoring: normalize text (NFD strip accents, lowercase, strip punctuation) then count weighted term occurrences"
  - "Pipeline pattern: clean -> score -> extract -> compare -> persist with optional steps"
  - "Categorical change classification: 5-level scale (major_hawkish_shift, hawkish_shift, neutral, dovish_shift, major_dovish_shift)"

requirements-completed: [NLP-03, NLP-04]

# Metrics
duration: 7min
completed: 2026-02-22
---

# Phase 16 Plan 03: Sentiment Scoring Pipeline Summary

**CentralBankSentimentAnalyzer with PT/EN hawk/dove dictionaries (264 terms total) producing [-1,+1] scores, and NLPProcessor pipeline orchestrating clean->score->extract->compare->persist workflow**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-22T22:43:12Z
- **Completed:** 2026-02-22T22:50:15Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- CentralBankSentimentAnalyzer with dictionary-based hawk/dove scoring produces net_score in [-1, +1]
- Portuguese dictionary: 65 hawk + 65 dove terms covering BCB monetary policy, inflation, risk jargon
- English dictionary: 64 hawk + 70 dove terms covering Fed tightening/easing, inflation, labor market
- NLPProcessor pipeline orchestrates clean -> score -> extract -> compare -> persist workflow
- Categorical change_score with 5 levels: major_hawkish_shift, hawkish_shift, neutral, dovish_shift, major_dovish_shift
- 37 comprehensive tests covering both languages, change scoring, edge cases, and pipeline operations

## Task Commits

Each task was committed atomically:

1. **Task 1: Hawk/dove dictionaries and CentralBankSentimentAnalyzer** - `ad33553` (feat)
2. **Task 2: NLPProcessor pipeline and comprehensive tests** - `7de7c64` (feat)

## Files Created/Modified
- `src/nlp/dictionaries/__init__.py` - Dictionary package init with exports
- `src/nlp/dictionaries/hawk_dove_pt.py` - 65 hawk + 65 dove Portuguese terms for COPOM analysis
- `src/nlp/dictionaries/hawk_dove_en.py` - 64 hawk + 70 dove English terms for FOMC analysis
- `src/nlp/sentiment_analyzer.py` - CentralBankSentimentAnalyzer with dictionary + optional LLM scoring
- `src/nlp/nlp_processor.py` - NLPProcessor pipeline orchestrator with ProcessedDocument/PipelineResult
- `tests/test_sentiment_analyzer.py` - 21 tests: PT/EN scoring, change_score, key phrases, edge cases
- `tests/test_nlp_processor.py` - 16 tests: process_document, batch, clean, detect, run_pipeline

## Decisions Made
- Dictionary-based scoring as primary method; LLM refinement uses 0.7/0.3 blend only when API key available
- Term weights range [0.0, 1.0] with higher values for stronger signals (e.g., "elevacao da selic" = 1.0)
- Text normalization: NFD decomposition to strip accents, lowercase, regex punctuation removal
- Change score thresholds: |delta| > 0.3 for major shifts, |delta| > 0.1 for minor shifts
- NLPProcessor persists via SQLAlchemy update WHERE on (source, doc_type, doc_date) natural key

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. Optional LLM refinement needs Anthropic API key but gracefully degrades to dictionary-only scoring.

## Next Phase Readiness
- Phase 16 NLP pipeline complete: scrapers (16-02) + sentiment scoring (16-03)
- CentralBankSentimentAnalyzer and NLPProcessor integrate with existing ScrapedDocument/NlpDocumentRecord
- Ready for integration into broader signal aggregation and cross-asset analysis workflows

## Self-Check: PASSED

All 7 files verified present on disk. Both commit hashes (ad33553, 7de7c64) verified in git log. 37 tests passing.

---
*Phase: 16-crossasset-nlp*
*Completed: 2026-02-22*
