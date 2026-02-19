# Roadmap: Macro Fund Data Infrastructure

## Overview

This roadmap delivers the complete data infrastructure for an agentic macro trading system covering Brazil and the US. The build follows the data flow: foundation (schema, Docker) enables connectors (ingestion), connectors enable seed/backfill (population), populated data enables transforms (silver layer), and everything converges at the API and quality layer (gold layer). Each phase delivers a coherent, verifiable capability that unblocks the next. Point-in-time correctness and Brazilian data format handling are baked in from Phase 1, not bolted on later.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Docker stack, ORM models, hypertables, migrations, config, and database engines
- [ ] **Phase 2: Core Connectors** - Base connector pattern, 4 core data sources (BCB SGS, FRED, Yahoo, PTAX), data integrity utilities, and test infrastructure
- [ ] **Phase 3: Extended Connectors** - Remaining 7 data sources (Focus, B3/Tesouro, IBGE, STN, CFTC, US Treasury, FX Flow)
- [ ] **Phase 4: Seed and Backfill** - Instrument/series metadata seeding, backfill orchestrator, and historical data population (2010-present)
- [ ] **Phase 5: Transforms** - Curve construction, returns/vol/z-scores, macro calculations, and advanced indicators (silver layer)
- [ ] **Phase 6: API and Quality** - FastAPI serving layer, all endpoints, data quality framework, verification, and CI pipeline (gold layer)

## Phase Details

### Phase 1: Foundation
**Goal**: A running infrastructure stack with a complete, point-in-time-correct database schema that all connectors and transforms can write into
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07
**Success Criteria** (what must be TRUE):
  1. `docker compose up` brings up TimescaleDB, Redis, MongoDB, Kafka, and MinIO with all services reporting healthy
  2. Running Alembic migrations creates all 10 tables (7 hypertables + 3 metadata) with TimescaleDB extension enabled and compression policies configured
  3. Python application connects to TimescaleDB (async via asyncpg) and Redis (via connection pool) and can execute queries
  4. Configuration loads from .env file via pydantic-settings with all service URLs and API keys resolved
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Project scaffolding, Docker Compose stack, and pydantic-settings configuration
- [ ] 01-02-PLAN.md — SQLAlchemy 2.0 ORM models and Alembic migration with hypertables and compression
- [ ] 01-03-PLAN.md — Database engines (async/sync), Redis client singleton, and connectivity verification

### Phase 2: Core Connectors
**Goal**: A proven ingestion pattern with 4 working connectors that validate the BaseConnector abstraction, Brazilian format handling, point-in-time tracking, and idempotent writes
**Depends on**: Phase 1
**Requirements**: CONN-01, CONN-02, CONN-03, CONN-10, CONN-11, DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. BCB SGS connector fetches Brazilian macro series with correct comma-decimal parsing (1.234,56 becomes 1234.56) and stores observations with release_time populated
  2. FRED connector fetches US macro series with revision tracking (each vintage stored as separate row with distinct release_time)
  3. Yahoo Finance connector fetches daily OHLCV for FX, indices, and commodities with retry logic handling rate limits
  4. BCB PTAX connector fetches official FX fixing rates with correct MM-DD-YYYY date handling
  5. All connectors use ON CONFLICT DO NOTHING and can be re-run without creating duplicates
**Plans**: 3 plans

Plans:
- [ ] 02-01-PLAN.md — BaseConnector ABC, data utilities (parsing, calendars, tenors), test infrastructure, and dependency installation
- [ ] 02-02-PLAN.md — BCB SGS connector (~50 BR macro series) and FRED connector (~50 US macro series) with tests
- [ ] 02-03-PLAN.md — Yahoo Finance connector (25+ tickers) and BCB PTAX connector (FX fixing rates) with tests

### Phase 3: Extended Connectors
**Goal**: Complete ingestion coverage across all 11 data sources, enabling the full 200+ series universe
**Depends on**: Phase 2
**Requirements**: CONN-04, CONN-05, CONN-06, CONN-07, CONN-08, CONN-09, CONN-12
**Success Criteria** (what must be TRUE):
  1. BCB Focus connector fetches market expectations (IPCA, Selic, GDP, FX) with OData pagination and stores by horizon
  2. B3/Tesouro Direto connector fetches DI swap curve (12 tenors from BCB SGS #7805-7816) and NTN-B real rates from Tesouro Direto JSON API
  3. IBGE SIDRA connector fetches IPCA disaggregated by 9 components with correct weights
  4. CFTC COT connector fetches disaggregated positioning for 12 contracts x 4 categories (48 series) from bulk CSV files
  5. US Treasury, STN Fiscal, and BCB FX Flow connectors each fetch and store their respective data series correctly
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

### Phase 4: Seed and Backfill
**Goal**: Database populated with all instrument definitions, series metadata, and historical data from 2010 to present across all 11 sources
**Depends on**: Phase 3
**Requirements**: SEED-01, SEED-02, SEED-03, SEED-04, SEED-05
**Success Criteria** (what must be TRUE):
  1. Seed script populates ~25 instruments and 150-200+ series metadata entries that match the connector definitions
  2. Backfill orchestrator accepts --source, --start-date, --end-date, --dry-run CLI args and executes connectors in dependency order
  3. Full backfill (2010-present) completes for all 11 sources with progress logging, error resilience, and a summary report showing record counts, timing, and status per source
  4. Re-running backfill produces zero duplicate rows (idempotent inserts verified)
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD
- [ ] 04-03: TBD

### Phase 5: Transforms
**Goal**: Silver layer producing all derived analytics -- curve construction, returns, volatility, z-scores, macro calculations, and advanced indicators -- from the populated raw data
**Depends on**: Phase 4
**Requirements**: XFORM-01, XFORM-02, XFORM-03, XFORM-04, XFORM-05, XFORM-06, XFORM-07, XFORM-08, XFORM-09, XFORM-10, XFORM-11, XFORM-12, XFORM-13, XFORM-14, TEST-01
**Success Criteria** (what must be TRUE):
  1. Nelson-Siegel curve fitting produces level/slope/curvature parameters from DI and UST spot curves, and interpolates to standard tenors with forward rates that are continuous (no jumps)
  2. Returns (log and arithmetic), rolling volatility (5d/21d/63d/252d), z-scores, percentile ranks, and rolling correlations compute correctly against known-answer test cases
  3. Macro transforms produce YoY from MoM conversions, IPCA diffusion index (weighted % of positive components), trimmed mean IPCA, and macro surprise index (actual vs Focus median)
  4. Breakeven inflation curve (DI nominal - NTN-B real) and carry/rolldown analytics (carry_bps, rolldown_bps, total_bps per tenor) compute from real populated data
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD
- [ ] 05-03: TBD

### Phase 6: API and Quality
**Goal**: A queryable gold layer serving all data through documented REST endpoints with point-in-time support, caching, data quality monitoring, and automated testing in CI
**Depends on**: Phase 5
**Requirements**: API-01, API-02, API-03, API-04, API-05, API-06, API-07, API-08, API-09, API-10, API-11, API-12, QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05, QUAL-06, TEST-04
**Success Criteria** (what must be TRUE):
  1. FastAPI app serves Swagger docs at /docs, and /health returns database connectivity status
  2. Macro endpoints return time series with point-in-time filtering (pit=true), dashboard aggregation of key BR+US+market indicators, and series search by keyword/country
  3. Curve, market data, and flow endpoints return correct data (curve by date with tenors, single-tenor history, OHLCV by ticker, latest prices, flow data, CFTC positioning with z-scores)
  4. Data quality framework produces a 0-100 quality score checking completeness (stale series detection), accuracy (range/outlier validation), curve integrity (tenor count, monotonicity), and point-in-time integrity (release_time >= observation_date)
  5. Infrastructure verification script validates all services, tables, hypertables, compression, data freshness, and API health end-to-end
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD
- [ ] 06-03: TBD
- [ ] 06-04: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete | 2026-02-19 |
| 2. Core Connectors | 1/3 | In Progress | - |
| 3. Extended Connectors | 0/3 | Not started | - |
| 4. Seed and Backfill | 0/3 | Not started | - |
| 5. Transforms | 0/3 | Not started | - |
| 6. API and Quality | 0/4 | Not started | - |
