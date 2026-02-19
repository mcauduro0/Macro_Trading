# Stack Research: Macro Trading Data Infrastructure

## Recommended Stack (2025/2026)

### Core Database Layer

| Component | Technology | Version | Confidence | Rationale |
|-----------|-----------|---------|------------|-----------|
| Time-Series DB | **TimescaleDB** (PostgreSQL extension) | latest-pg16 | HIGH | SQL-compatible, hypertables with automatic partitioning, native time-series functions, 95%+ compression, continuous aggregates. 10-100x faster than vanilla PostgreSQL for time-range queries. Polyglot persistence with same PostgreSQL engine. |
| Relational DB | **PostgreSQL 16+** | 16 | HIGH | ACID compliance, JSON support, mature ecosystem, seamless integration with TimescaleDB. Reference data, metadata, configurations. |
| Document Store | **MongoDB 7.0** | 7 | MEDIUM | Flexible schema for unstructured NLP corpus (central bank communications, speeches). Full-text search. Not critical for Phase 0 but needed for agent phases. |
| Cache Layer | **Redis 7.0** (Alpine) | 7-alpine | HIGH | Sub-millisecond latency, pub/sub for real-time updates, TTL-based expiration. Connection pool with appendonly persistence. |
| Object Storage | **MinIO** (S3-compatible) | latest | MEDIUM | Cost-effective for raw file archives (PDFs, CSVs). Not critical path for Phase 0, but good to have in stack. |
| Message Queue | **Apache Kafka** (Confluent) | 7.6.0 | MEDIUM | Exactly-once semantics, high throughput, replay capability. Not critical for Phase 0 batch ingestion, but essential for future real-time streaming. |

### Python Application Layer

| Component | Library | Version | Confidence | Rationale |
|-----------|---------|---------|------------|-----------|
| ORM | **SQLAlchemy 2.0** (async) | >=2.0 | HIGH | Mapped_column style, native async support with asyncpg. Industry standard for Python database access. |
| Async Driver | **asyncpg** | >=0.29 | HIGH | Fastest PostgreSQL driver for Python. Native async, binary protocol. |
| Sync Driver | **psycopg2-binary** | >=2.9 | HIGH | Needed for Alembic migrations and sync operations. |
| Migrations | **Alembic** | >=1.13 | HIGH | Standard SQLAlchemy migration tool. Autogenerate from models. |
| Validation | **Pydantic v2** | >=2.5 | HIGH | Data validation, settings management, API schemas. Significant performance improvements over v1. |
| Settings | **pydantic-settings** | >=2.1 | HIGH | Environment variable management, .env file support. |
| API Framework | **FastAPI** | >=0.109 | HIGH | Async, auto-generated OpenAPI docs, Pydantic integration, high performance. |
| ASGI Server | **uvicorn** (standard) | >=0.27 | HIGH | Standard ASGI server for FastAPI. |
| HTTP Client | **httpx** | >=0.26 | HIGH | Async HTTP client for all data connectors. Superior to aiohttp for API consumption — cleaner API, better timeout handling. |
| Data Processing | **pandas** | >=2.1 | HIGH | Standard for tabular data manipulation. Required by many data sources. |
| Data Processing | **polars** | >=0.20 | MEDIUM | Faster alternative for large datasets. Use for performance-critical transforms. |
| Numeric | **numpy** | >=1.26 | HIGH | Foundation for all numeric computation. |
| Scientific | **scipy** | >=1.12 | HIGH | Nelson-Siegel curve fitting (minimize), interpolation (CubicSpline). |
| Caching | **redis** (python) | >=5.0 | HIGH | Redis client with connection pool. |
| Logging | **structlog** | >=24.1 | HIGH | Structured JSON logging. Superior to stdlib logging for production systems. |
| Retry | **tenacity** | >=8.2 | HIGH | Retry decorator with exponential backoff. All API calls need this. |
| HTML Parsing | **beautifulsoup4** + **lxml** | >=4.12 / >=5.1 | HIGH | Needed for parsing CFTC reports, STN pages, Tesouro Direto. |
| Excel | **openpyxl** | >=3.1 | MEDIUM | Reading Excel files from some Brazilian data sources. |
| Market Data | **yfinance** | >=0.2 | MEDIUM | Yahoo Finance wrapper for FX, equities, commodities. Free, no API key. Limitations: delayed data, occasional API changes. |
| HTTP (async alt) | **aiohttp** | >=3.9 | LOW | Backup async HTTP. httpx preferred for new code. |
| Date Utils | **python-dateutil** | >=2.8 | HIGH | Date parsing, relative deltas. Essential for date handling. |
| Environment | **python-dotenv** | >=1.0 | HIGH | .env file loading. |

### Development Tools

| Component | Library | Version | Rationale |
|-----------|---------|---------|-----------|
| Testing | **pytest** | >=7.4 | Standard Python testing framework. |
| Async Testing | **pytest-asyncio** | >=0.23 | Async test support for connector tests. |
| Coverage | **pytest-cov** | >=4.1 | Code coverage reporting. |
| Linting | **ruff** | >=0.2 | Fast Python linter + formatter. Replaces flake8, black, isort. |
| HTTP Mocking | **respx** | >=0.20 | Mock httpx requests in tests. |

### Infrastructure

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Containerization | **Docker Compose** | Local development stack. 6 services: TimescaleDB, Redis, MongoDB, Kafka (+ Zookeeper), MinIO. |
| Python Version | **3.11+** | Required for modern async features, performance improvements, better error messages. |
| Package Management | **pyproject.toml** + pip | Standard Python packaging. No need for Poetry/PDM complexity for this project. |

## What NOT to Use

| Technology | Why Not |
|-----------|---------|
| InfluxDB | No SQL interface, separate query language (Flux), poor JOIN support. TimescaleDB offers same time-series features with full PostgreSQL compatibility. |
| QuestDB | Immature ecosystem, limited Python tooling, no SQLAlchemy support. |
| ClickHouse | Overkill for this scale (~200GB). Analytical focus doesn't match OLTP needs for point-in-time queries. |
| Django ORM | Too opinionated, doesn't support async natively as well as SQLAlchemy 2.0. |
| Celery | Too heavy for task scheduling. Simple asyncio + cron is sufficient for batch ingestion. |
| Airflow/Dagster | Overkill for Phase 0. Python scripts with asyncio are simpler. Consider for Phase 1+ if pipeline complexity grows. |
| Poetry/PDM | Unnecessary complexity for a monorepo. pyproject.toml + pip is sufficient. |
| aiohttp (as primary) | httpx has cleaner API, better timeout handling, sync/async dual support. Use httpx for all new connectors. |

## Brazilian Data Source Libraries

| Library | Purpose | Notes |
|---------|---------|-------|
| **python-bcb** (v0.3.3) | BCB SGS, PTAX, Focus, interest rates | Comprehensive wrapper. Consider using OR building custom httpx connectors for more control over error handling and rate limiting. |
| **cot-reports** | CFTC COT data download | Downloads bulk files from CFTC. Alternative: custom connector with direct URL access. |
| Direct API (httpx) | BCB SGS, BCB Focus, IBGE SIDRA, Tesouro Direto | Recommended approach: custom connectors with httpx for full control over retry logic, rate limiting, and error handling. |

## Key Architecture Notes

1. **Async everywhere**: All connectors should use async httpx. Sync operations only for database bulk inserts (SQLAlchemy sync engine).
2. **Rate limiting built-in**: Each connector must respect source API limits (BCB: ~200 req/min, FRED: 120 req/min, IBGE: ~60 req/min).
3. **Idempotent inserts**: All database writes use ON CONFLICT DO NOTHING. Safe to re-run backfills.
4. **Point-in-time via release_time**: Macro series must track when data was published, not just what period it covers.
5. **Hypertable chunk intervals**: Market data (1 month), curves/vol surfaces (3 months), macro/fiscal/flow (1 year) — matching query patterns.
6. **Compression policies**: Automatic compression after data cools (30 days for market, 90 days for curves, 365 days for macro).

---
*Research completed: 2026-02-19*
*Confidence: HIGH for core stack, MEDIUM for infrastructure services (Kafka, MongoDB, MinIO not critical for Phase 0)*
