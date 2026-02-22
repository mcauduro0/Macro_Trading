# Phase 16 Context: Cross-Asset Agent v2 & NLP Pipeline

## Decisions (LOCKED)

### Area 1: Regime Model Inputs

| Decision | Choice | Rationale |
|---|---|---|
| HMM features | 6 features: growth_z, inflation_z, VIX_z, credit_spread_z, FX_vol_z, equity_momentum_z | Full cross-asset observable set for comprehensive regime detection |
| Training window | Expanding (all available data from 2010 to as_of_date) | More stable parameters, longer history captures rare regime events |
| Probability consumption | Probability-weighted blending — strategies receive full probability vector and blend allocation weights proportionally | E.g., 60% Goldilocks + 30% Reflation = blended allocation |
| Fallback behavior | Rule-based + risk_warning entry when HMM fails to converge | Strategies still execute, but CrossAssetView metadata shows warning |

### Area 2: Consistency Checking & CrossAssetView

| Decision | Choice | Rationale |
|---|---|---|
| Check scope | Agent + strategy signals | Check both agent signals AND individual strategy signals for contradictions |
| Rules approach | Extensible rule list — structured dict-based rules, easy to add more | Clear, auditable, and extensible |
| Action on contradiction | Warning + 0.5x sizing penalty on affected instruments | Consistent with existing regime sizing multiplier pattern |
| CrossAssetView type | Frozen dataclass + builder pattern | CrossAssetViewBuilder collects data, .build() returns frozen view |

### Area 3: NLP Pipeline Architecture

| Decision | Choice | Rationale |
|---|---|---|
| Scraper approach | HTTP + incremental cache — first run scrapes, subsequent runs check for new documents only | Self-contained, persistent, incremental |
| Sentiment method | Dictionary (PT+EN hawk/dove terms) + optional LLM refinement when API key available | Dictionary as primary, LLM refines nuance |
| Document storage | Single nlp_documents table via Alembic — id, source, doc_type, date, raw_text, hawk_score, dove_score, change_score, key_phrases, created_at | Simple, all columns inline |
| Change score | Categorical + magnitude — hawkish_shift, dovish_shift, neutral, major_hawkish_shift, major_dovish_shift | More interpretable for downstream strategies |

### Area 4: LLM Narrative & Integration

| Decision | Choice | Rationale |
|---|---|---|
| Narrative scope | Both — short 3-5 sentence regime narrative in CrossAssetAgent + full section in NarrativeGenerator | Standalone + daily brief integration |
| NLP integration | DB-mediated (loose coupling) — NLP pipeline stores to DB, CrossAssetAgent reads from nlp_documents table | Clean separation, independent scheduling |
| Key trades | Top-3 by conviction — highest conviction strategy signals, formatted as structured recommendations | Simple, actionable |
| Tail risk | Market composite + regime transition probability — VIX, credit spreads, correlation breaks + P(transitioning to Stagflation/Deflation) | Comprehensive tail risk assessment |

## Claude's Discretion

- HMM library choice (hmmlearn vs custom implementation)
- Exact number of consistency rules (5-10 recommended)
- Scraper HTML parsing specifics (CSS selectors, URL patterns)
- PT hawk/dove dictionary term count (50-100 terms per language recommended)
- Change score magnitude thresholds (e.g., |delta| > 0.3 for "major")
- CrossAssetView per-asset-class view structure details
- NarrativeGenerator cross-asset section prompt wording

## Deferred Ideas

- TF-IDF weighted sentiment (keep dictionary simple for now)
- Two-table storage for NLP documents
- Language similarity in change score
- Regime-aligned key trade selection (use conviction only)
