# Project Research Summary

**Project:** Macro Trading Data Infrastructure
**Domain:** Quantitative macro trading data platform (Brazil-US axis)
**Researched:** 2026-02-19
**Confidence:** HIGH

## Executive Summary

This is a research-grade macro trading data infrastructure designed to support 25+ downstream quantitative strategies and AI agents across Brazilian and US markets. Experts build this type of system around three non-negotiable principles: **point-in-time correctness** (tracking when data was released, not just what it measures), **multi-source ingestion** (combining 11+ free data sources with different formats and conventions), and **layered storage** (bronze raw data, silver transforms, gold serving APIs). The recommended approach uses TimescaleDB hypertables for time-series storage, async Python connectors for 11+ sources (BCB, FRED, CFTC, IBGE, etc.), and a medallion architecture with FastAPI serving layer.

The critical insight from research is that **the hardest technical challenge is not data volume or API complexity — it's maintaining point-in-time correctness for revisable macro series**. GDP, CPI, NFP, and IPCA all get revised 2-3 times after initial release. Systems that overwrite revisions with new values create look-ahead bias that silently corrupts all backtesting. This requires designing the schema with `release_time` tracking from day one. The second major risk is **Brazilian data format confusion**: BCB uses comma decimals (`1.234,56`), DD/MM/YYYY dates, and PTAX has different date formats across endpoints. A parser that treats `01/02/2024` as January 2nd (US format) when it means February 1st (BR format) produces silently wrong data. Both issues require prevention at the schema and ingestion layer — retrofitting is effectively a full rewrite.

The recommended build sequence is: **Foundation (schema, Docker) → Core Connectors (4 sources) → Full Ingestion (11 sources) → Transforms (curves, returns, z-scores) → API + Caching**. This order ensures data exists before transforms consume it, and transforms exist before the API serves them. The system is designed for a solo user doing research and backtesting, so heavyweight infrastructure (Kafka streaming, Airflow orchestration, authentication) is deferred to Phase 1+ when AI agents and live trading requirements become real.

## Key Findings

### Recommended Stack

**Core decision: TimescaleDB over InfluxDB/QuestDB/ClickHouse** because it provides time-series optimizations (hypertables, compression, continuous aggregates) while remaining fully SQL-compatible. This matters for point-in-time queries, which require complex JOINs and subqueries that are painful or impossible in InfluxDB's Flux language. The stack is Python 3.11+ throughout with async everywhere (asyncpg, httpx, FastAPI).

**Core technologies:**

- **TimescaleDB (PostgreSQL 16 + extension):** Time-series storage with automatic partitioning, 90%+ compression, continuous aggregates. Handles 7 hypertables (market_data, macro_series, curves, flow_data, fiscal_data, vol_surfaces, signals) with point-in-time queries via `release_time` filtering.

- **SQLAlchemy 2.0 async + asyncpg:** Async ORM with native PostgreSQL binary protocol. Provides type safety, migration support (Alembic), and compatibility with FastAPI async ecosystem.

- **FastAPI + uvicorn:** Async API framework for serving data to agents/dashboards. Auto-generated OpenAPI docs, Pydantic validation, and request-scoped sessions via dependency injection.

- **httpx (not aiohttp):** Async HTTP client for all 11+ data connectors. Cleaner API, better timeout handling, and dual sync/async support vs aiohttp.

- **Redis 7.0 Alpine:** Sub-millisecond cache layer with TTL matched to data update frequency (5 min for live macro, 1 hour for historical). Cache-aside pattern reduces DB load for repeated queries.

- **Nelson-Siegel curve fitting:** Extract level/slope/curvature from yield curves. Required for carry/rolldown analytics and breakeven inflation calculation (DI nominal - NTN-B real).

- **Pydantic v2 + pydantic-settings:** Data validation, API schemas, and environment variable management. v2 provides significant performance improvements.

**What NOT to use:**
- **Airflow/Dagster:** Overkill for 11 daily jobs. Simple async scheduler is sufficient.
- **Kafka:** Macro data updates daily/weekly, not real-time. Batch-first architecture defers Kafka to Phase 1+ if needed.
- **Poetry/PDM:** Unnecessary complexity. pyproject.toml + pip is sufficient for a monorepo.
- **Bloomberg/Refinitiv:** $24k+/year cost. Free sources (BCB, FRED, Yahoo Finance) cover 90%+ of needed data.

### Expected Features

**Must have (table stakes):**

Users (downstream strategies and agents) expect these features to exist. The system is useless without them.

- **TS-1: Multi-source data ingestion (11+ connectors):** BCB SGS (~50 BR macro series), FRED (~50 US macro), BCB Focus (market expectations), B3/Tesouro Direto (DI curve, NTN-B real rates), IBGE SIDRA (IPCA components), STN Fiscal, CFTC COT (positioning), US Treasury (yield curves), Yahoo Finance (FX, indices, commodities), BCB PTAX (FX fixing), BCB FX Flow. Each connector must handle source-specific quirks (BCB comma decimals, PTAX date format, CFTC contract name changes).

- **TS-2: Storage layer (TimescaleDB hypertables):** 7 hypertables with compression policies. Chunk intervals matched to query patterns: 1 month for market_data, 3 months for curves, 1 year for macro. Compression after data cools (30 days for market, 90 days for curves, 365 days for macro).

- **TS-3: Point-in-time correctness:** Every macro observation stores `observation_date` (what period), `release_time` (when published), and `value`. Revisions create new rows with new `release_time`, not UPDATEs. Queries filter by `release_time <= as_of_date` to reconstruct historical information states.

- **TS-4: Historical backfill (2010-present):** Parameterized orchestrator with date range chunking, idempotent upserts, rate limiting per API, resumable on failure.

- **TS-5: Core transforms (returns, vol, z-scores, YoY/MoM):** Basic building blocks for signal generation. Every strategy needs returns and normalized indicators.

- **TS-6: Curve construction:** Nelson-Siegel fitting, forward rates, carry/rolldown, DV01, breakeven inflation (DI nominal - NTN-B real).

- **TS-7: Data serving API:** FastAPI endpoints for macro, curves, market data, flows. Point-in-time query support via `as_of` parameter. Macro dashboard endpoint.

- **TS-8: Data quality framework:** Completeness checks, freshness monitoring, curve integrity validation, cross-source consistency.

**Should have (competitive advantage):**

Features that elevate this from "a bunch of CSV files" to a research-grade platform.

- **D-1: Macro surprise index:** (actual - expected) / historical_std. Requires joining BCB Focus expectations to IBGE/BCB actuals.
- **D-2: IPCA diffusion index:** Breadth of inflation pressure. % of 9 components accelerating, weighted by IBGE weights.
- **D-3: Trimmed mean IPCA:** Core inflation proxy. Sort components by MoM, trim extremes, re-weight.
- **D-5: Carry/rolldown analytics:** Pre-computed carry and rolldown for DI and UST curves. Core signal for rates strategies.
- **D-8: Snapshot-based BCB revision capture:** Daily snapshots enable building "ALFRED for Brazil." Unique — no public source offers this for Brazilian data.

**Defer (v2+):**

Anti-features that would derail Phase 0.

- **Real-time streaming (Kafka):** Macro data updates daily/weekly. Real-time adds complexity for zero value. Defer to Phase 1+ if live trading requires sub-minute latency.
- **Full feature store (Feast/Hopsworks):** Overkill for solo user with ~200 series. PIT correctness achievable with `release_time` filtering.
- **Frontend dashboard (React):** Separate project. Use Jupyter notebooks for Phase 0.
- **Bloomberg terminal integration:** $24k+/year. Free sources cover 90%+ of needed data.
- **Tick/intraday data:** Macro strategies operate on daily/weekly/monthly frequencies. Tick data = 100-1000x storage.

### Architecture Approach

**Medallion architecture (bronze/silver/gold)** with separation of concerns: connectors own ingestion, transforms own computation, API owns serving. Each layer is independently testable. The Abstract Connector pattern enforces consistent lifecycle (`fetch()` → `parse()` → `validate()` → `store()`), so adding new sources follows a known template. Point-in-time correctness is baked into the schema as `release_time` columns and append-only inserts, not bolt-on query logic. All database writes use `ON CONFLICT DO NOTHING` for idempotency — safe to re-run backfills.

**Major components:**

1. **Connectors (11+ classes):** One per data source. Inherit from `BaseConnector` abstract class. Handle API quirks (BCB comma decimals, PTAX date format). Async httpx for all HTTP calls. Rate limiting built-in (BCB: ~200 req/min, FRED: 120 req/min).

2. **Bronze/TimescaleDB:** 7 hypertables for time-series data (market_data, macro_series, curves, flow_data, fiscal_data, vol_surfaces, signals) + 3 relational metadata tables (instruments, series_metadata, data_sources). Compression policies on chunks older than 30-365 days. `segmentby=series_id` for efficient DML on compressed data.

3. **Silver/Transforms:** Pure functions operating on DataFrames. No database access, no side effects. Curve fitting (Nelson-Siegel), returns, rolling stats, macro calculations (YoY, diffusion, surprise). Output written back to TimescaleDB or served directly.

4. **Gold/FastAPI + Redis:** Async REST endpoints with Pydantic response models. Redis cache-aside pattern with TTL matched to data volatility (5 min for live macro, 1 hour for historical). Connection pooling (pool_size=20, max_overflow=10).

5. **Orchestration:** Lightweight async scheduler for daily/weekly data pulls. Backfill orchestrator with date range chunking, checkpointing, progress logging. No Airflow — simple is better for 11 daily jobs.

**Key architectural patterns:**

- **Template Method (BaseConnector):** Abstract class defines `ingest(start, end)` lifecycle. Subclasses override `fetch()`, `parse()`, `store()`. Uniform error handling and logging.
- **Point-in-Time via release_time:** Never UPDATE macro data. Always INSERT new rows with new `release_time`. Query with `release_time <= as_of` to reconstruct historical states.
- **Idempotent Upsert:** All writes use `ON CONFLICT DO NOTHING` on natural keys (series_id, observation_date, release_time). Safe re-runs.
- **Layered Caching with TTL:** Redis TTL matched to data update frequency. Macro latest: 5 min, macro history: 1 hour, market latest: 1 min.
- **Async Engine Singleton:** Single AsyncEngine at app startup. Request-scoped AsyncSession via FastAPI dependency injection.

### Critical Pitfalls

Research identified 7 critical pitfalls that cause data corruption or rewrites. Top 5:

1. **Look-ahead bias from missing point-in-time discipline:** Storing only the latest revised value for GDP, NFP, CPI creates silent look-ahead bias. Backtests "know" revised numbers before the market did. **How to avoid:** Use ALFRED vintage dates for FRED series. Store every revision as a separate row with `release_time`. Build `get_as_of(series, as_of_date)` query function. For BCB (which lacks native revision tracking), record `ingestion_timestamp` and never overwrite. **Must be in Phase 1 schema** — retrofitting is a full rewrite.

2. **Free API fragility causing silent data gaps:** Yahoo Finance has no official API — yfinance is a scraper that breaks with 429 errors. CFTC changes CSV formats without notice. BCB SGS can be slow. Pipeline returns partial data and nobody notices until signals break weeks later. **How to avoid:** Per-source health checks (row count, staleness, value bounds). `data_quality_log` table for every ingestion run. Alerting when series goes stale. For Yahoo: cache aggressively, exponential backoff, fallback source (EODHD, Finnhub). **Address in Phase 2 (Ingestion)** alongside first connectors.

3. **Brazilian data format misinterpretation:** BCB uses comma decimals (`1.234,56` = 1234.56), DD/MM/YYYY dates. PTAX uses MM-DD-YYYY in some endpoints. Parser that treats `01/02/2024` as January 2nd (US) when it means February 1st (BR) produces silently wrong data. `1.234` treated as 1.234 (US) when it means 1234 (BR) is off by 1000x. **How to avoid:** `BrazilianDataParser` utility enforcing `decimal=','` and `thousands='.'`. Explicit date format strings (`%d/%m/%Y`), never infer. Tag every source with locale (`pt_BR` vs `en_US`). Round-trip tests on known BR-format files. **Address in Phase 1 (locale registry) and Phase 2 (parsers).**

4. **TimescaleDB compression destroying backfill capability:** Aggressive compression policies (compress after 7 days) prevent INSERT/UPDATE on compressed chunks. In TimescaleDB <2.11, impossible without manual decompression. Even in 2.16+, bulk modifications require decompression (10-14x disk bloat). **How to avoid:** Use TimescaleDB 2.16+. Set `segmentby=series_id` and `orderby=time ASC`. Set `compress_after` to generous delay (90 days for monthly macro). Run 2010 backfill BEFORE enabling compression. Leave 20-30% disk headroom. **Address in Phase 1 (config) and Phase 3 (backfill ordering).**

5. **Curve construction from proxy data without acknowledging the approximation:** Building DI curve from BCB swap series (not exchange-traded DI futures) with naive linear interpolation produces arbitrage-violating curves with discontinuous forward rates. **How to avoid:** Use monotone convex interpolation (Hagan & West method, adopted by US Treasury 2020). Integrate interpolation into bootstrap loop iteratively. Validate against ANBIMA indicative rates. Document the proxy nature (`curve_source_type=proxy_bcb_swap`). Use PYield or QuantLib for Brazilian conventions (BUS/252, ANBIMA holidays). **Address in Phase 4 (Derived Data / Curve Construction).**

Additional critical pitfalls:
- **Timezone and calendar misalignment:** Use `TIMESTAMPTZ` exclusively. Store all timestamps in UTC. Maintain `release_timezone` metadata. Use IANA timezone identifiers, never hardcoded offsets (Brazil abolished DST in 2019, historical data needs DST-aware conversion). Separate ANBIMA and NYSE holiday calendars.
- **Non-idempotent backfill creating duplicates:** Use UPSERT with composite natural key `(series_id, observation_date, vintage_date)`. Accept explicit `--start-date`/`--end-date` parameters. Chunk by year/month. Log every backfill run in audit table.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 0a: Foundation
**Rationale:** Cannot ingest data without tables to write into. Schema design must include `release_time` for point-in-time correctness from day one — retrofitting is a full rewrite.

**Delivers:**
- Docker Compose stack (TimescaleDB, Redis, MongoDB placeholder, MinIO placeholder)
- SQLAlchemy 2.0 async ORM models (10 tables: 7 hypertables + 3 metadata)
- Alembic migrations
- Seed data (instruments, series metadata with locale tags)
- TimescaleDB hypertable configuration (`segmentby=series_id`, chunk intervals)
- Compression policies (disabled initially, enabled after backfill)

**Addresses:**
- TS-2: Storage layer
- TS-3: Point-in-time schema design (`release_time` column)
- Pitfall #1 prevention (PIT schema design)
- Pitfall #3 prevention (locale registry in series_metadata)
- Pitfall #4 prevention (compression config)
- Pitfall #6 prevention (TIMESTAMPTZ columns, timezone metadata)

**Avoids:**
- Look-ahead bias (PIT schema)
- Brazilian format confusion (locale registry)
- Compression blocking backfill (correct config + delayed activation)

**Research flag:** Standard patterns. TimescaleDB schema design is well-documented. Skip `/gsd:research-phase`.

---

### Phase 0b: Ingestion Layer (Core Connectors)
**Rationale:** Prove the ingestion pattern with 3-4 connectors before building all 11. Validates BaseConnector abstraction, UPSERT logic, and Brazilian format handling.

**Delivers:**
- `BaseConnector` abstract class (template method pattern)
- BCB SGS connector (~50 BR macro series) — tests Brazilian format parsing
- FRED connector (~50 US macro series) — tests ALFRED vintage date handling
- Yahoo Finance connector (FX, indices, commodities) — tests rate limit handling
- BCB PTAX connector (FX fixing) — tests PTAX date format quirk (MM-DD-YYYY)
- `BrazilianDataParser` utility
- Per-connector health checks
- `data_quality_log` table

**Uses:**
- httpx async HTTP client
- tenacity retry decorator with exponential backoff
- structlog for structured logging
- python-bcb library for BCB SGS/PTAX (handles date format conversion)
- fredapi with ALFRED vintage support

**Implements:**
- Ingestion layer architecture
- Abstract Connector pattern
- Idempotent upsert pattern

**Addresses:**
- TS-1 (partial): 4 core connectors
- Pitfall #2 prevention (health checks, quality log)
- Pitfall #3 prevention (Brazilian parser, locale-aware parsing)
- Pitfall #7 prevention (UPSERT pattern)

**Avoids:**
- Free API fragility (health checks, retry logic)
- Brazilian format misparse (explicit parsers, round-trip tests)
- Non-idempotent backfill (UPSERT pattern)

**Research flag:** Moderate research. BCB SGS/PTAX quirks need documentation review. ALFRED vintage handling needs testing. Estimated 1 day research during planning.

---

### Phase 0c: Full Connector Suite
**Rationale:** Once the BaseConnector pattern is proven, remaining connectors are largely mechanical (same pattern, different APIs).

**Delivers:**
- BCB Focus connector (market expectations) — enables macro surprise index (D-1)
- B3/Tesouro Direto connector (DI curve proxy, NTN-B) — enables curve construction (Phase 0d)
- IBGE SIDRA connector (IPCA components) — enables diffusion/trimmed mean (D-2, D-3)
- STN Fiscal connector (primary balance, debt composition)
- CFTC COT connector (positioning) — needs contract code stability handling
- US Treasury connector (yield curves)
- BCB FX Flow connector (capital flows)

**Uses:**
- cot_reports library for CFTC data
- PYield library for B3/Tesouro validation (Brazilian bond conventions)
- beautifulsoup4 + lxml for STN HTML/CSV parsing
- openpyxl for Brazilian Excel files

**Addresses:**
- TS-1 (remaining): 7 more connectors
- TS-8: Data quality framework (completeness, freshness, cross-source consistency)
- Pitfall #2: CFTC contract name instability (use contract codes, not names)

**Avoids:**
- CFTC format changes (use official API + cot_reports library)
- STN scraping fragility (validate against known values)

**Research flag:** Low research. APIs are documented. CFTC contract code mapping may need 0.5 day research.

---

### Phase 0d: Historical Backfill
**Rationale:** Must complete BEFORE enabling compression policies. Validates idempotent UPSERT pattern and date range chunking.

**Delivers:**
- Backfill orchestrator (accepts `--start-date`/`--end-date`, chunked by month)
- Progress logging and checkpointing
- Completeness verification (gap detection)
- `backfill_runs` audit table
- ANBIMA + NYSE holiday calendars
- 2010-present data for all 11 connectors

**Uses:**
- pandas_market_calendars or exchange_calendars for holiday calendars
- anbima_calendar for Brazilian business days

**Addresses:**
- TS-4: Historical backfill
- Pitfall #4: Run backfill before compression enabled
- Pitfall #6: Holiday calendar handling
- Pitfall #7: Idempotent backfill (UPSERT, chunking, audit)

**Avoids:**
- Compression blocking backfill (backfill completes first)
- Calendar misalignment (ANBIMA vs NYSE)
- Duplicate rows on re-run (UPSERT pattern)

**Research flag:** Low research. Backfill patterns are well-documented. Calendar libraries exist.

---

### Phase 0e: Transforms (Silver Layer)
**Rationale:** Requires data to exist first (depends on Phase 0d backfill). Some transforms require multiple data sources (breakeven = DI nominal - NTN-B real).

**Delivers:**
- Curve construction: Nelson-Siegel fitting, forward rates, DV01, breakeven inflation
- Returns: daily/weekly/monthly, log/arithmetic
- Rolling statistics: vol, z-score, percentile rank
- Macro calculations: YoY/MoM conversions, correlations
- Advanced indicators: macro surprise index (D-1), IPCA diffusion (D-2), trimmed mean (D-3)
- Carry/rolldown analytics (D-5)

**Uses:**
- nelson_siegel_svensson library for curve fitting
- scipy for interpolation (CubicSpline)
- numpy for numeric computation
- pandas/polars for DataFrame transforms

**Addresses:**
- TS-5: Core transforms
- TS-6: Curve construction
- D-1, D-2, D-3, D-5: Differentiator features
- Pitfall #5 prevention (monotone convex interpolation, validate against ANBIMA)

**Avoids:**
- Curve construction errors (Hagan & West method, integrated bootstrap)
- Discontinuous forward rates (monotone convex interpolation)

**Research flag:** High research for curve construction. Nelson-Siegel fitting is standard but BCB swap-to-DI-curve mapping needs validation. Estimated 2 days research during planning. Other transforms are standard (low research).

---

### Phase 0f: API + Caching (Gold Layer)
**Rationale:** Serves data that must exist first. Building API before data exists leads to mocking and disconnects. Building after means every endpoint tests against real data.

**Delivers:**
- FastAPI application with routers (macro, curves, market, flows, dashboard, health)
- Pydantic response schemas
- Point-in-time query support (`as_of` query parameter)
- Redis caching layer with TTL strategies
- Macro dashboard endpoint (aggregated BR + US indicators)
- Infrastructure health check script (D-10)

**Uses:**
- FastAPI with uvicorn
- Pydantic v2 for schemas
- Redis 7.0 with connection pool
- Request-scoped AsyncSession via dependency injection

**Implements:**
- Gold layer architecture
- Cache-aside pattern
- Async engine singleton with request-scoped sessions

**Addresses:**
- TS-7: Data serving API
- D-10: Infrastructure health check

**Avoids:**
- Slow API response under load (Redis caching, connection pooling)

**Research flag:** Standard patterns. FastAPI + Pydantic + Redis is well-documented. Skip `/gsd:research-phase`.

---

### Phase Ordering Rationale

- **Foundation (0a) must come first** because all other phases depend on the database schema. Point-in-time correctness cannot be retrofitted — it must be in the initial schema design.

- **Core Connectors (0b) before Full Suite (0c)** because the first 3-4 connectors validate the BaseConnector pattern and Brazilian format handling. Once proven, remaining connectors are mechanical.

- **Full Connectors (0c) before Backfill (0d)** because backfill uses the connectors. But connectors can be built and tested incrementally with small date ranges before running the full 2010-present backfill.

- **Backfill (0d) before Compression** because TimescaleDB compression policies must be disabled during bulk historical INSERT. Compression is enabled AFTER backfill completes and verifies.

- **Transforms (0e) after Backfill (0d)** because transforms consume raw data. Breakeven inflation requires both DI and NTN-B data to exist. Macro surprise requires both expectations and actuals.

- **API (0f) last** because it serves data that must exist first. Every endpoint can be tested against real data immediately, with no mocking.

This order **avoids critical pitfalls:**
- PIT schema prevents look-ahead bias (Pitfall #1)
- Brazilian parsers prevent format confusion (Pitfall #3)
- Backfill-then-compression prevents chunk conflicts (Pitfall #4)
- Idempotent UPSERT prevents duplicates (Pitfall #7)
- Health checks prevent silent gaps (Pitfall #2)

### Research Flags

**Phases needing deeper research during planning:**

- **Phase 0b (Core Connectors):** BCB SGS/PTAX quirks, ALFRED vintage handling. Estimated 1 day.
- **Phase 0c (Full Suite):** CFTC contract code mapping. Estimated 0.5 day.
- **Phase 0e (Transforms/Curves):** Nelson-Siegel fitting, BCB swap-to-DI-curve validation against ANBIMA. Estimated 2 days.

**Phases with standard patterns (skip research-phase):**

- **Phase 0a (Foundation):** TimescaleDB schema design, SQLAlchemy 2.0 async patterns. Well-documented.
- **Phase 0d (Backfill):** Idempotent backfill patterns, chunking strategies. Well-documented.
- **Phase 0f (API + Caching):** FastAPI + Pydantic + Redis. Well-documented.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | TimescaleDB, FastAPI, SQLAlchemy 2.0, httpx are well-documented. Multiple authoritative sources confirm stack choices. Kafka/Airflow/MongoDB correctly deferred. |
| Features | HIGH | Feature landscape well-understood. Table stakes (11 connectors, PIT, backfill, transforms, API) vs differentiators (surprise index, diffusion, carry/rolldown) vs anti-features (real-time, auth, frontend) clearly delineated. MVP definition (v0.1) is minimal but complete. |
| Architecture | HIGH | Medallion architecture (bronze/silver/gold) is standard. Abstract Connector pattern proven. Point-in-time via `release_time` is well-documented. Idempotent upsert pattern is standard. Build order (foundation → ingestion → backfill → transforms → API) is dependency-driven. |
| Pitfalls | HIGH | Top 7 critical pitfalls extensively documented across multiple authoritative sources. Look-ahead bias, Brazilian format confusion, compression conflicts, curve construction errors, timezone misalignment, non-idempotent backfill, free API fragility are all well-known domain-specific issues with proven prevention strategies. |

**Overall confidence:** HIGH

Research is comprehensive and converges across multiple authoritative sources (official docs, academic papers, community libraries, real-world bug reports). The domain (macro trading data infrastructure) is mature with established patterns. The specific challenges (Brazilian data, point-in-time correctness, free API fragility) are well-documented.

### Gaps to Address

**Gaps that need validation during implementation:**

- **BCB swap series as DI curve proxy:** Research confirms this is a known approximation, but the specific mapping from BCB series #7805-7816 to a DI curve needs validation against ANBIMA indicative rates during Phase 0e. The PYield library provides reference implementations but focuses on NTN-B (government bonds), not DI swaps.

- **ANBIMA ETTJ access terms:** Research flags that ANBIMA's full historical indicative rates may require institutional access or subscription. The free online portal provides only the last 5 business days. During Phase 0e curve construction, validate whether BCB swap series are sufficient or whether ANBIMA access is needed. If ANBIMA requires subscription, document the BCB proxy limitation and defer ANBIMA integration to v1.0+ (D-6).

- **BCB SGS revision history:** BCB does not provide native revision tracking like FRED/ALFRED. The snapshot-based approach (D-8) requires daily capture over time to build a vintage dataset. This is a long-term investment — value accrues the longer it runs. During Phase 0b, implement basic snapshot capture but defer full vintage reconstruction tooling to v0.2+.

- **Yahoo Finance fallback source:** yfinance fragility is well-documented. Research suggests EODHD or Finnhub as fallbacks, but their free tier limits need validation. During Phase 0b, implement yfinance with retry logic and caching. Identify fallback source during Phase 0c if yfinance proves unreliable in practice.

- **CFTC contract code stability:** Research confirms contract names change but contract codes are stable. During Phase 0c, build a `cftc_contract_registry` table mapping codes to human-readable names with effective date ranges. Use the cot_reports library which handles this but verify continuity for the 12 target contracts.

**How to handle:**
- **Curve validation:** Add ANBIMA indicative rate comparison as a required test during Phase 0e planning. If ANBIMA access is blocked, document the limitation and proceed with BCB proxy + PYield validation.
- **BCB revisions:** Start daily snapshot capture in Phase 0b (low cost, high long-term value). Defer vintage query tooling to v0.2.
- **Yahoo fallback:** Validate EODHD/Finnhub free tier during Phase 0c planning. If fallback is insufficient, accept yfinance risk for Phase 0 (solo user, research focus) and revisit for Phase 1 (production).
- **CFTC contracts:** Use cot_reports library + build contract registry during Phase 0c. Verify historical continuity in backfill.

## Sources

### Primary (HIGH confidence)

**Official documentation:**
- TimescaleDB Documentation (Hypertables, Compression, Best Practices)
- FRED API Documentation + ALFRED Vintage Data
- FastAPI Official Docs
- SQLAlchemy 2.0 Documentation
- PostgreSQL 16 Documentation
- Redis Time Series Documentation

**Official Python libraries:**
- python-bcb (v0.3.3) on PyPI + GitHub — BCB SGS/PTAX/Focus wrapper
- fredapi on PyPI + GitHub — FRED/ALFRED Python client
- nelson_siegel_svensson on PyPI + GitHub — Curve fitting
- cot_reports on GitHub — CFTC COT data parsing
- PYield on PyPI + GitHub — Brazilian fixed income conventions

**Government sources:**
- CFTC Historical Compressed Data + Special Announcements
- Philadelphia Fed Real-Time Data Set (macro vintages methodology)
- US Treasury Yield Curve Methodology Change (monotone convex adoption 2020)
- ANBIMA Calendar Documentation

### Secondary (MEDIUM confidence)

**Research papers and whitepapers:**
- Hagan & West (2006) "Interpolation Methods for Curve Construction" — Bootstrap/interpolation coupling
- FactSet "Accurately Backtesting Financial Models" — PIT methodology whitepaper
- Macrosynergy "Macroeconomic data and systematic trading strategies" — Macro-quantamental system design
- MDPI "Engineering Sustainable Data Architectures for Modern Financial Institutions" — Four-layer financial data architecture

**Authoritative blogs and guides:**
- Macrobond "The critical role of Point-in-Time data in economic forecasting and quant trading"
- Refinitiv "Using Point-in-Time Data to Avoid Bias"
- QLib Documentation (PIT Database implementation)
- Databricks Medallion Architecture (Bronze/Silver/Gold pattern)
- Leapcell "Building High-Performance Async APIs with FastAPI, SQLAlchemy 2.0, and Asyncpg"
- Start Data Engineering "Data Pipeline Design Patterns" (Factory pattern, idempotency)

**Community best practices:**
- ml4devs "Backfilling Historical Data" — Idempotent backfill patterns
- Towards Data Engineering "Building Idempotent Data Pipelines at Scale" — UPSERT, dedup, audit
- TimeStored "UTC for Trading Infrastructure" — Financial timezone best practices
- Portfolio Optimization Book "Seven Sins of Quantitative Investing" — Survivorship bias, data snooping

### Tertiary (LOW confidence — used for directional guidance, needs validation)

- Quant 2.0 Architecture (modern trading stack overview)
- Arcesium Macro Hedge Fund Strategies (data platform requirements)
- MinIO "Building an S3-Compliant Stock Market Data Lake"
- yfinance GitHub Issues (#2125, #2128, #2422) — Rate limiting documentation
- awesome-quant curated library list
- QuantStart Securities Master Databases (database design patterns)
- rb3 R Package (B3 yield curve fetching — R reference, not Python)

---
*Research completed: 2026-02-19*
*Ready for roadmap: yes*
