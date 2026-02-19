# Requirements: Macro Fund Data Infrastructure

**Defined:** 2026-02-19
**Core Value:** Reliable, point-in-time-correct macro and market data flowing into a queryable system

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Infrastructure

- [ ] **INFRA-01**: Docker Compose stack runs with TimescaleDB, Redis, MongoDB, Kafka, MinIO — all healthy
- [ ] **INFRA-02**: SQLAlchemy 2.0 ORM models define 10 tables with type hints and async support
- [ ] **INFRA-03**: 7 TimescaleDB hypertables with compression policies (market_data, macro_series, curves, flow_data, fiscal_data, vol_surfaces, signals)
- [ ] **INFRA-04**: Alembic migration creates all tables, enables TimescaleDB extension, configures hypertables and compression
- [ ] **INFRA-05**: Configuration via pydantic-settings with .env file support for all service URLs and API keys
- [ ] **INFRA-06**: Async database engine (asyncpg) and sync engine (psycopg2) with session factories
- [ ] **INFRA-07**: Redis client singleton with connection pool

### Connectors

- [ ] **CONN-01**: Base connector abstract class with async HTTP (httpx), retry with backoff, rate limiting, structured logging
- [ ] **CONN-02**: BCB SGS connector fetches ~50 Brazilian macro series (inflation, activity, monetary, external, fiscal) with comma-decimal parsing
- [ ] **CONN-03**: FRED connector fetches ~50 US macro series (CPI, PCE, NFP, rates, credit, fiscal) with missing-value handling
- [ ] **CONN-04**: BCB Focus connector fetches market expectations (IPCA, Selic, GDP, FX) by horizon with OData pagination
- [ ] **CONN-05**: B3/Tesouro Direto connector fetches DI swap curve (BCB SGS #7805-7816) and NTN-B real rates from Tesouro Direto JSON API
- [ ] **CONN-06**: IBGE SIDRA connector fetches IPCA disaggregated by 9 components with weights
- [ ] **CONN-07**: STN Fiscal connector fetches primary balance, debt composition, revenue/expenditure from BCB SGS + Tesouro Transparente
- [ ] **CONN-08**: CFTC COT connector fetches disaggregated positioning for 12 contracts x 4 categories (48 series) from bulk CSV files
- [ ] **CONN-09**: US Treasury connector fetches daily nominal, real (TIPS), and breakeven yield curves from Treasury.gov CSV
- [ ] **CONN-10**: Yahoo Finance connector fetches daily OHLCV for 25+ tickers (FX, indices, commodities, ETFs) via yfinance
- [ ] **CONN-11**: BCB PTAX connector fetches official FX fixing rate (buy/sell) from OData API with MM-DD-YYYY date handling
- [ ] **CONN-12**: BCB FX Flow connector fetches commercial/financial flows and BCB swap stock from SGS series

### Data Integrity

- [ ] **DATA-01**: All macro_series records store release_time (when data was published) for point-in-time correctness
- [ ] **DATA-02**: Revision tracking via revision_number field — revised series store each vintage as separate row
- [ ] **DATA-03**: All database inserts use ON CONFLICT DO NOTHING for idempotent re-runs
- [ ] **DATA-04**: Business day calendar utilities for ANBIMA (BR) and NYSE (US) holidays (2015-2030)
- [ ] **DATA-05**: Tenor-to-days and tenor-to-date conversion with business day conventions

### Seed & Backfill

- [ ] **SEED-01**: Seed script populates instruments table with ~25 instruments (FX, indices, commodities, ETFs)
- [ ] **SEED-02**: Seed script populates series_metadata table with 150-200+ series definitions from all connectors
- [ ] **SEED-03**: Backfill orchestrator accepts CLI args (--source, --start-date, --end-date, --dry-run)
- [ ] **SEED-04**: Backfill executes all 11 connectors in dependency order with progress logging and error resilience
- [ ] **SEED-05**: Backfill produces summary report with record counts per source, timing, and status

### Transforms

- [ ] **XFORM-01**: Nelson-Siegel curve fitting (fit and interpolate to standard tenors)
- [ ] **XFORM-02**: Forward rate calculation from spot curves
- [ ] **XFORM-03**: DV01/duration calculation per curve point
- [ ] **XFORM-04**: Breakeven inflation curve (nominal DI - NTN-B real at matched tenors)
- [ ] **XFORM-05**: Carry and rolldown analytics (carry_bps, rolldown_bps, total_bps per tenor)
- [ ] **XFORM-06**: Returns calculation (log and arithmetic) from price series
- [ ] **XFORM-07**: Rolling volatility at multiple windows (5d, 21d, 63d, 252d), annualized
- [ ] **XFORM-08**: Z-score and percentile rank with configurable lookback window
- [ ] **XFORM-09**: Rolling correlation between any two series
- [ ] **XFORM-10**: YoY from MoM conversion for inflation series
- [ ] **XFORM-11**: IPCA diffusion index (% of components with positive variation, weighted)
- [ ] **XFORM-12**: Trimmed mean IPCA (trim extremes, re-weight remainder)
- [ ] **XFORM-13**: Macro surprise index (actual vs Focus median expectation, standardized)
- [ ] **XFORM-14**: Drawdown calculation (cumulative max, drawdown, drawdown %)

### API

- [ ] **API-01**: FastAPI app with CORS, lifespan handler, auto-generated Swagger docs at /docs
- [ ] **API-02**: GET /health returns database connectivity status and timestamp
- [ ] **API-03**: GET /health/data-status returns record counts per table, total instruments, total series
- [ ] **API-04**: GET /api/v1/macro/{series_id} returns time series with optional point-in-time filtering (pit=true)
- [ ] **API-05**: GET /api/v1/macro/dashboard returns latest values for key BR + US + market indicators
- [ ] **API-06**: GET /api/v1/macro/search returns series matching keyword and optional country filter
- [ ] **API-07**: GET /api/v1/curves/{curve_id} returns curve for a given date with all tenors
- [ ] **API-08**: GET /api/v1/curves/{curve_id}/history returns single-tenor history over date range
- [ ] **API-09**: GET /api/v1/market-data/{ticker} returns OHLCV history for instrument
- [ ] **API-10**: GET /api/v1/market-data/latest returns latest prices for multiple tickers
- [ ] **API-11**: GET /api/v1/flows/{series_id} returns flow/positioning data
- [ ] **API-12**: GET /api/v1/flows/positioning-summary returns CFTC positioning with z-scores

### Quality & Verification

- [ ] **QUAL-01**: Completeness check detects missing observations based on expected frequency (daily >3 BD stale, weekly >10d, monthly >45d)
- [ ] **QUAL-02**: Accuracy check validates ranges for key series and flags z-score outliers (|z|>5)
- [ ] **QUAL-03**: Curve integrity check validates minimum tenors, rate bounds, and reasonable monotonicity
- [ ] **QUAL-04**: Point-in-time integrity check validates release_time >= observation time for all macro_series
- [ ] **QUAL-05**: Run-all-checks produces summary with quality score 0-100 and PASS/WARN/FAIL status
- [ ] **QUAL-06**: Infrastructure verification script checks all services, tables, hypertables, compression, data freshness, API health

### Testing & CI

- [ ] **TEST-01**: Pytest test suite for transforms (curves, returns) with known-answer tests
- [ ] **TEST-02**: Pytest test suite for connectors with respx HTTP mocking
- [ ] **TEST-03**: Pytest conftest with database session fixture and sample date fixtures
- [ ] **TEST-04**: GitHub Actions CI workflow runs ruff lint + pytest (excluding integration tests)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Data

- **ADVD-01**: Vol surface reconstruction from delta-space quotes (requires FX option data)
- **ADVD-02**: ANBIMA ETTJ curve integration (requires ANBIMA API registration)
- **ADVD-03**: Snapshot-based BCB revision capture ("ALFRED for Brazil")
- **ADVD-04**: Data lineage and series catalog (provenance tracking)

### Infrastructure

- **ADVF-01**: Kafka streaming pipelines for real-time data ingestion
- **ADVF-02**: Multi-user authentication / API key middleware
- **ADVF-03**: Frontend React dashboard for data visualization
- **ADVF-04**: Airflow/Dagster orchestration for complex DAG scheduling
- **ADVF-05**: Tick-level / intraday data storage

## Out of Scope

| Feature | Reason |
|---------|--------|
| Bloomberg/Refinitiv integration | $24k+/year cost; free sources cover 90%+ of needs |
| Live order execution | Research/backtesting focus; execution is Phase 1+ |
| AI agents (Inflation, Monetary, Fiscal, FX) | Phase 1+ after data layer is proven |
| Trading strategies (~25) | Phase 1+ after agents produce signals |
| Risk management system | Phase 1+ after strategies exist |
| ETF/mutual fund trading | Investment focus is stocks only |
| G5 extension (EUR, GBP, JPY, CHF) | Phase 1+ after BR+US is complete |
| NLP corpus (central bank communications) | Phase 1+ when agents need text analysis |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 2 | Pending |
| INFRA-03 | Phase 2 | Pending |
| INFRA-04 | Phase 2 | Pending |
| INFRA-05 | Phase 1 | Pending |
| INFRA-06 | Phase 1 | Pending |
| INFRA-07 | Phase 1 | Pending |
| CONN-01 | Phase 3 | Pending |
| CONN-02 | Phase 3 | Pending |
| CONN-03 | Phase 3 | Pending |
| CONN-04 | Phase 4 | Pending |
| CONN-05 | Phase 4 | Pending |
| CONN-06 | Phase 4 | Pending |
| CONN-07 | Phase 4 | Pending |
| CONN-08 | Phase 4 | Pending |
| CONN-09 | Phase 4 | Pending |
| CONN-10 | Phase 3 | Pending |
| CONN-11 | Phase 3 | Pending |
| CONN-12 | Phase 4 | Pending |
| DATA-01 | Phase 2 | Pending |
| DATA-02 | Phase 2 | Pending |
| DATA-03 | Phase 2 | Pending |
| DATA-04 | Phase 3 | Pending |
| DATA-05 | Phase 3 | Pending |
| SEED-01 | Phase 5 | Pending |
| SEED-02 | Phase 5 | Pending |
| SEED-03 | Phase 5 | Pending |
| SEED-04 | Phase 5 | Pending |
| SEED-05 | Phase 5 | Pending |
| XFORM-01 | Phase 6 | Pending |
| XFORM-02 | Phase 6 | Pending |
| XFORM-03 | Phase 6 | Pending |
| XFORM-04 | Phase 6 | Pending |
| XFORM-05 | Phase 6 | Pending |
| XFORM-06 | Phase 6 | Pending |
| XFORM-07 | Phase 6 | Pending |
| XFORM-08 | Phase 6 | Pending |
| XFORM-09 | Phase 6 | Pending |
| XFORM-10 | Phase 6 | Pending |
| XFORM-11 | Phase 6 | Pending |
| XFORM-12 | Phase 6 | Pending |
| XFORM-13 | Phase 6 | Pending |
| XFORM-14 | Phase 6 | Pending |
| API-01 | Phase 7 | Pending |
| API-02 | Phase 7 | Pending |
| API-03 | Phase 7 | Pending |
| API-04 | Phase 7 | Pending |
| API-05 | Phase 7 | Pending |
| API-06 | Phase 7 | Pending |
| API-07 | Phase 7 | Pending |
| API-08 | Phase 7 | Pending |
| API-09 | Phase 7 | Pending |
| API-10 | Phase 7 | Pending |
| API-11 | Phase 7 | Pending |
| API-12 | Phase 7 | Pending |
| QUAL-01 | Phase 7 | Pending |
| QUAL-02 | Phase 7 | Pending |
| QUAL-03 | Phase 7 | Pending |
| QUAL-04 | Phase 7 | Pending |
| QUAL-05 | Phase 7 | Pending |
| QUAL-06 | Phase 7 | Pending |
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 3 | Pending |
| TEST-03 | Phase 3 | Pending |
| TEST-04 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 60 total
- Mapped to phases: 60
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-19*
*Last updated: 2026-02-19 after initial definition*
