# Architecture Research: Macro Trading Data Infrastructure

**Domain:** Global macro fund data infrastructure (Brazil-US axis)
**Researched:** 2026-02-19
**Confidence:** HIGH

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        GOLD LAYER (Serving)                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │  FastAPI REST  │  │  Redis Cache  │  │  Pydantic     │               │
│  │  Endpoints     │  │  (hot data)   │  │  Response DTOs│               │
│  └───────┬───────┘  └───────┬───────┘  └───────────────┘               │
│          │                  │                                           │
├──────────┴──────────────────┴───────────────────────────────────────────┤
│                        SILVER LAYER (Transforms)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │  Curve   │  │  Returns │  │  Macro   │  │  Vol     │               │
│  │  Fitting │  │  Z-Score │  │  Calc    │  │  Surface │               │
│  │  (NS)    │  │  Ranks   │  │  YoY/Dif │  │  Recon   │               │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘               │
│       │             │             │             │                       │
├───────┴─────────────┴─────────────┴─────────────┴───────────────────────┤
│                        BRONZE LAYER (Storage)                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                  TimescaleDB (Hypertables)                      │    │
│  │  market_data | macro_series | curves | flow_data | fiscal_data  │    │
│  │  vol_surfaces | signals | instruments | series_metadata         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌──────────┐  ┌──────────┐                                            │
│  │  MongoDB  │  │  MinIO   │                                           │
│  │  (docs)   │  │  (blobs) │                                           │
│  └──────────┘  └──────────┘                                            │
├─────────────────────────────────────────────────────────────────────────┤
│                     INGESTION LAYER (Connectors)                        │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐         │
│  │BCB SGS│ │BCB    │ │ FRED  │ │IBGE   │ │Yahoo  │ │CFTC   │         │
│  │BCB FX │ │Focus  │ │       │ │SIDRA  │ │Finance│ │COT    │         │
│  │BCB    │ │B3/    │ │       │ │STN    │ │       │ │US     │         │
│  │PTAX   │ │Tesouro│ │       │ │Fiscal │ │       │ │Treas  │         │
│  └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘         │
│      │         │         │         │         │         │               │
├──────┴─────────┴─────────┴─────────┴─────────┴─────────┴───────────────┤
│                     ORCHESTRATION LAYER                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐            │
│  │ Scheduler      │  │ Backfill       │  │ Data Quality   │            │
│  │ (daily/weekly) │  │ Orchestrator   │  │ Framework      │            │
│  └────────────────┘  └────────────────┘  └────────────────┘            │
├─────────────────────────────────────────────────────────────────────────┤
│                     INFRASTRUCTURE                                       │
│  Docker Compose: TimescaleDB | Redis | MongoDB | MinIO | (Kafka later)  │
│  Alembic migrations | Seed scripts | Health checks                      │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Connectors** (11+) | Fetch raw data from external APIs, normalize to common format, handle API quirks (date formats, decimal separators) | Abstract base class with `fetch()`, `parse()`, `store()` methods; one class per data source |
| **Bronze/TimescaleDB** | Durable storage of all time-series data in hypertables with compression; point-in-time correctness via `release_time` | 7 hypertables partitioned by timestamp; `ON CONFLICT DO NOTHING` for idempotency |
| **Bronze/MongoDB** | Store unstructured data: agent outputs, LLM responses, raw API responses for debugging | Document collections per data type; future use for agent system |
| **Bronze/MinIO** | Blob storage for large files: raw CSV downloads, CFTC reports, Tesouro Direto historical files, backfill snapshots | S3-compatible API; hybrid pattern (metadata in Postgres, blobs in MinIO) |
| **Silver/Transforms** | Derive analytics from raw data: curve fitting, returns, z-scores, macro calculations | Pure functions operating on DataFrames; no side effects; output written back to TimescaleDB |
| **Gold/FastAPI** | Serve processed data to downstream consumers (agents, dashboards, notebooks) via REST API | Async endpoints with Pydantic response models; dependency injection for DB sessions |
| **Gold/Redis** | Cache frequently-accessed query results; reduce DB load for repetitive API calls | Cache-aside pattern; hierarchical keys; TTL matched to data update frequency |
| **Orchestration** | Schedule daily/weekly data pulls, coordinate backfills, run data quality checks | Async task runner; no heavyweight orchestrator (Airflow) needed for this scale |
| **Infrastructure** | Docker Compose stack, migrations, seed data, health checks | Single `docker-compose.yml`; Alembic for schema; seed scripts for instruments/metadata |

## Recommended Project Structure

```
src/
├── connectors/              # Data ingestion layer (one module per source)
│   ├── base.py              # Abstract BaseConnector with fetch/parse/store interface
│   ├── bcb_sgs.py           # BCB SGS (~50 BR macro series)
│   ├── bcb_focus.py         # BCB Focus market expectations
│   ├── bcb_ptax.py          # Official FX fixing rate
│   ├── bcb_fx_flow.py       # Commercial/financial FX flows
│   ├── fred.py              # FRED (~50 US macro series)
│   ├── ibge_sidra.py        # IPCA disaggregated components
│   ├── stn_fiscal.py        # Primary balance, debt composition
│   ├── b3_tesouro.py        # DI curve proxies, NTN-B real rates
│   ├── anbima.py            # Placeholder (ETTJ curve, indicative rates)
│   ├── cftc.py              # COT positioning data
│   ├── us_treasury.py       # Nominal + real + breakeven curves
│   └── yahoo.py             # FX, indices, commodities, ETFs
├── core/                    # Shared foundation
│   ├── models/              # SQLAlchemy 2.0 ORM models
│   │   ├── base.py          # Declarative base, naming conventions
│   │   ├── instruments.py   # Instrument registry
│   │   ├── series.py        # Series metadata
│   │   ├── market_data.py   # Price/rate hypertable
│   │   ├── macro_series.py  # Macro data with release_time (PIT)
│   │   ├── curves.py        # Yield curve points
│   │   ├── flow_data.py     # FX/capital flows
│   │   ├── fiscal_data.py   # Fiscal metrics
│   │   ├── vol_surfaces.py  # Volatility surface data
│   │   └── signals.py       # Trading signals (future)
│   ├── database.py          # Async engine, session factory, get_db dependency
│   ├── config.py            # Settings via pydantic-settings (env vars)
│   ├── exceptions.py        # Domain exceptions
│   └── enums.py             # Shared enumerations (AssetClass, Frequency, etc.)
├── transforms/              # Silver layer: pure computation
│   ├── curves.py            # Nelson-Siegel fitting, forwards, carry/rolldown, DV01
│   ├── returns.py           # Returns, rolling vol, drawdowns
│   ├── statistics.py        # Z-scores, percentile ranks, correlations
│   ├── macro.py             # YoY from MoM, diffusion index, trimmed mean, surprise
│   └── vol_surface.py       # Vol surface reconstruction from delta-space
├── api/                     # Gold layer: FastAPI application
│   ├── main.py              # App factory, lifespan, middleware
│   ├── deps.py              # Dependency injection (db session, redis, auth)
│   ├── routers/
│   │   ├── macro.py         # /macro/* endpoints
│   │   ├── curves.py        # /curves/* endpoints
│   │   ├── market.py        # /market/* endpoints
│   │   ├── flows.py         # /flows/* endpoints
│   │   ├── dashboard.py     # /dashboard/* aggregated view
│   │   └── health.py        # /health endpoint
│   └── schemas/             # Pydantic response/request models
│       ├── macro.py
│       ├── curves.py
│       ├── market.py
│       └── common.py        # Pagination, date ranges, etc.
├── orchestration/           # Scheduling and coordination
│   ├── scheduler.py         # Daily/weekly job definitions
│   ├── backfill.py          # Historical backfill orchestrator (2010-present)
│   └── quality.py           # Data quality checks and alerts
├── cache/                   # Redis caching layer
│   ├── client.py            # Redis connection, pool management
│   ├── keys.py              # Hierarchical key generation
│   └── strategies.py        # TTL strategies per data type
└── seeds/                   # Initial data
    ├── instruments.py        # ~25 instruments
    └── series_metadata.py    # 150-200+ series definitions
```

### Structure Rationale

- **`connectors/`:** One file per data source keeps each connector self-contained. The abstract base class enforces a consistent interface (`fetch` -> `parse` -> `store`) while allowing source-specific quirks (BCB comma decimals, PTAX date format). This is the Factory pattern applied to data ingestion.

- **`core/models/`:** One file per hypertable maps directly to the bronze layer schema. Keeping models separate from business logic prevents circular imports and makes Alembic autogenerate work cleanly.

- **`transforms/`:** Pure functions that take DataFrames in and return DataFrames out. No database access, no side effects. This makes them independently testable and reusable. The caller (orchestration layer or API) handles persistence.

- **`api/`:** Router-per-domain organization mirrors the data model. Schemas (Pydantic) live next to routers for co-location. The `deps.py` module centralizes dependency injection (sessions, cache, config).

- **`orchestration/`:** Lightweight scheduling without Airflow. At this scale (11 connectors, daily/weekly cadence), a simple async scheduler with retry logic is sufficient. Backfill is a separate concern from daily ingestion because it has different requirements (idempotent bulk insert, progress tracking, date range iteration).

- **`cache/`:** Separated from API to allow cache strategies to evolve independently. Key generation is centralized to prevent naming collisions.

## Architectural Patterns

### Pattern 1: Abstract Connector with Template Method

**What:** Every data connector inherits from `BaseConnector` which defines the ingestion lifecycle: `fetch()` -> `parse()` -> `validate()` -> `store()`. Subclasses override specific steps.

**When to use:** Always, for all 11+ connectors. This is the backbone of the ingestion layer.

**Trade-offs:** Slightly more upfront code vs. massive consistency gains. Every connector behaves predictably, error handling is uniform, and adding new sources follows a known pattern.

**Example:**
```python
from abc import ABC, abstractmethod
from datetime import date
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

class BaseConnector(ABC):
    """Template method pattern for data ingestion."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def ingest(self, start: date, end: date) -> int:
        """Full ingestion lifecycle. Returns row count."""
        raw = await self.fetch(start, end)
        df = self.parse(raw)
        df = self.validate(df)
        count = await self.store(df)
        return count

    @abstractmethod
    async def fetch(self, start: date, end: date) -> dict | list:
        """Fetch raw data from external API."""
        ...

    @abstractmethod
    def parse(self, raw: dict | list) -> pd.DataFrame:
        """Parse raw response into normalized DataFrame."""
        ...

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Default validation: drop nulls, check types. Override for custom rules."""
        return df.dropna(subset=["timestamp"])

    @abstractmethod
    async def store(self, df: pd.DataFrame) -> int:
        """Upsert into TimescaleDB. Must be idempotent (ON CONFLICT DO NOTHING)."""
        ...
```

### Pattern 2: Point-in-Time Correctness via release_time

**What:** Every row in `macro_series` stores both the `observation_date` (what period the data describes) and the `release_time` (when that value became known). Revised data creates new rows with updated `release_time`, not updates to existing rows. Queries filter by `release_time <= as_of_date` to reconstruct the information state at any historical point.

**When to use:** All macro series that get revised (NFP, GDP, CPI, IPCA). Critical for backtesting.

**Trade-offs:** More storage (multiple vintages per observation). More complex queries. But prevents look-ahead bias, which is fatal for backtesting credibility.

**Example:**
```python
# Model
class MacroSeries(Base):
    __tablename__ = "macro_series"

    id = Column(BigInteger, primary_key=True)
    series_id = Column(Integer, ForeignKey("series_metadata.id"), nullable=False)
    observation_date = Column(Date, nullable=False)
    value = Column(Float, nullable=False)
    release_time = Column(DateTime(timezone=True), nullable=False)
    revision_number = Column(SmallInteger, default=0)

    __table_args__ = (
        UniqueConstraint("series_id", "observation_date", "revision_number"),
        # TimescaleDB hypertable on observation_date
    )

# Point-in-time query
async def get_series_as_of(
    session: AsyncSession,
    series_id: int,
    as_of: datetime,
) -> list[MacroSeries]:
    """Get the latest known value for each observation as of a given datetime."""
    subq = (
        select(
            MacroSeries.observation_date,
            func.max(MacroSeries.release_time).label("max_release")
        )
        .where(MacroSeries.series_id == series_id)
        .where(MacroSeries.release_time <= as_of)
        .group_by(MacroSeries.observation_date)
        .subquery()
    )
    query = (
        select(MacroSeries)
        .join(subq, and_(
            MacroSeries.observation_date == subq.c.observation_date,
            MacroSeries.release_time == subq.c.max_release,
        ))
        .where(MacroSeries.series_id == series_id)
        .order_by(MacroSeries.observation_date)
    )
    result = await session.execute(query)
    return result.scalars().all()
```

### Pattern 3: Idempotent Upsert for Safe Re-runs

**What:** All inserts use `ON CONFLICT DO NOTHING` (or `DO UPDATE` where appropriate). Running the same ingestion twice produces identical results with no duplicates.

**When to use:** Every single write path. Connectors, backfills, transforms.

**Trade-offs:** Requires unique constraints on natural keys (not just surrogate IDs). Slightly slower than raw inserts due to conflict detection. But eliminates an entire class of bugs around duplicate data.

**Example:**
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

async def upsert_market_data(session: AsyncSession, df: pd.DataFrame) -> int:
    """Idempotent insert of market data rows."""
    records = df.to_dict("records")
    stmt = pg_insert(MarketData).values(records)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["instrument_id", "timestamp", "frequency"]
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount
```

### Pattern 4: Layered Caching with TTL by Data Volatility

**What:** Redis sits in front of TimescaleDB for API reads. TTL is matched to how often the underlying data changes. Historical data gets long TTLs (hours); live macro data gets short TTLs (minutes); curve data gets medium TTLs.

**When to use:** All Gold layer API endpoints.

**Trade-offs:** Adds complexity (cache invalidation logic). But reduces DB load dramatically for repeated queries, which matters when agents or dashboards poll frequently.

**Example:**
```python
# TTL strategy per data domain
TTL_STRATEGIES = {
    "macro_latest":   300,    # 5 min  - macro dashboard, changes on release dates
    "macro_history": 3600,    # 1 hour - historical series, rarely changes
    "curves_latest":  600,    # 10 min - yield curves update daily
    "curves_history": 3600,   # 1 hour - historical curves
    "market_latest":   60,    # 1 min  - market prices change frequently
    "market_history": 3600,   # 1 hour - historical market data
    "flows":          1800,   # 30 min - flow data updates daily
    "dashboard":       300,   # 5 min  - aggregated dashboard view
}

# Hierarchical key pattern
def cache_key(domain: str, entity: str, params: dict) -> str:
    """Generate hierarchical Redis key."""
    param_str = ":".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"macro:{domain}:{entity}:{param_str}"

# Example: "macro:curves:di_curve:date=2026-02-19"
```

### Pattern 5: Async Engine Singleton with Request-Scoped Sessions

**What:** A single `AsyncEngine` is created at app startup (lifespan event) and shared across all requests. Each request gets its own `AsyncSession` via FastAPI dependency injection with `yield`.

**When to use:** All database access in the FastAPI application.

**Trade-offs:** Standard, well-proven pattern. The engine manages the connection pool; sessions scope transactions to individual requests. Must configure `autoflush=False` and `expire_on_commit=False` for async compatibility.

**Example:**
```python
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from contextlib import asynccontextmanager

# Singleton engine (created once at startup)
engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)

# Request-scoped session via FastAPI dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

## Data Flow

### Daily Ingestion Flow

```
[External APIs] ──(HTTP)──> [Connectors]
                                │
                          fetch() → raw JSON/CSV
                          parse() → normalized DataFrame
                          validate() → cleaned DataFrame
                          store() → idempotent upsert
                                │
                                ▼
                        [TimescaleDB Bronze]
                        (hypertables: market_data,
                         macro_series, curves, etc.)
                                │
                                ▼
                        [Transforms Silver]
                        (curve fitting, returns,
                         z-scores, macro calcs)
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            [TimescaleDB]            [Redis Cache]
            (derived tables          (invalidated on
             or same tables)          new data arrival)
                    │                       │
                    └───────────┬───────────┘
                                ▼
                          [FastAPI Gold]
                          (REST endpoints)
                                │
                                ▼
                        [Consumers]
                        (Agents, notebooks,
                         dashboards - future)
```

### Historical Backfill Flow

```
[Backfill Orchestrator]
    │
    ├── For each connector:
    │     ├── Determine date range (2010 → present)
    │     ├── Chunk into manageable windows (monthly)
    │     ├── For each chunk:
    │     │     ├── connector.ingest(start, end)
    │     │     ├── ON CONFLICT DO NOTHING (safe re-run)
    │     │     └── Log progress + checkpoint
    │     └── Verify completeness (gap detection)
    │
    └── After all connectors complete:
          ├── Run transforms on full historical range
          ├── Run data quality checks
          └── Report summary (rows ingested, gaps found)
```

### API Request Flow

```
[Client Request]
    │
    ▼
[FastAPI Router]
    │
    ├── Depends(get_db)      → AsyncSession injected
    ├── Depends(get_redis)   → Redis client injected
    │
    ▼
[Cache Check]
    │
    ├── HIT  → Return cached response (< 1ms)
    │
    └── MISS → [Query TimescaleDB]
                    │
                    ▼
               [Transform/Format]
                    │
                    ├── Store in Redis (with TTL)
                    └── Return response
```

### Key Data Flows

1. **Macro series ingestion:** BCB/FRED API -> Connector.fetch() -> parse (handle comma decimals, date formats) -> validate (null check, type check) -> upsert with release_time into macro_series hypertable -> transforms compute YoY, z-scores -> cached in Redis -> served via /macro/* endpoints.

2. **Yield curve construction:** B3/Tesouro API -> fetch swap rates at 12 tenors -> store raw points in curves hypertable -> Nelson-Siegel fitting produces continuous curve -> forward rates, carry/rolldown, DV01 derived -> served via /curves/* endpoints.

3. **Point-in-time query:** Client requests macro series "as of" a specific date -> API filters macro_series by `release_time <= as_of` -> returns the information state that would have been available at that point -> critical for agent backtesting.

4. **Dashboard aggregation:** /dashboard endpoint -> queries latest values across macro_series, market_data, curves -> computes key indicators (BR + US) -> caches full response with 5-min TTL -> served as single payload.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **Solo user, development** (now) | Docker Compose on local machine. Single TimescaleDB instance. No Kafka. Redis optional (can query DB directly). Focus on correctness, not throughput. |
| **Solo user, production** (Phase 0 target) | Same Docker Compose but with proper resource limits. Enable TimescaleDB compression (90%+ savings for data older than 30 days). Redis caching enabled for API endpoints. MinIO for raw file archival. |
| **Small team, 2-5 users** (Phase 1+) | Add connection pooling limits. Consider read replicas for TimescaleDB if query load grows. Introduce Kafka for decoupling connectors from transforms (event-driven). Add authentication to API. |
| **Production fund** (Phase 2+) | Kafka becomes the event backbone. Separate compute for transforms. Monitoring/alerting on data freshness. Consider managed TimescaleDB (Timescale Cloud) for reliability. Multi-node MinIO for durability. |

### Scaling Priorities

1. **First bottleneck: TimescaleDB query performance.** As data volume grows (200+ series x 15 years x daily = ~1M+ rows), unoptimized queries slow down. **Fix:** Enable compression on chunks older than 30 days. Create continuous aggregates for common query patterns (daily/weekly/monthly rollups). Add composite indexes on (series_id, observation_date) for all hypertables.

2. **Second bottleneck: Connector throughput during backfill.** Fetching 15 years of data from 11+ APIs takes hours. **Fix:** Parallelize connectors with asyncio.gather(). Chunk date ranges. Add checkpointing so failed backfills can resume. Rate-limit per API to avoid bans.

3. **Third bottleneck: API response time under concurrent load.** Multiple agents querying simultaneously. **Fix:** Redis caching eliminates repeated DB hits. Connection pooling (pool_size=20, max_overflow=10) prevents connection exhaustion.

## Anti-Patterns

### Anti-Pattern 1: Fat Connectors That Do Everything

**What people do:** Put parsing, validation, transformation, caching, and error handling all inside a single connector class that grows to 500+ lines.

**Why it's wrong:** Untestable. Changes to parsing break storage. Changes to one API affect error handling for all APIs. Violates single responsibility.

**Do this instead:** Connectors only fetch, parse, and store raw data (bronze). Transforms are a separate layer. Caching is a separate layer. Error handling is in the base class. Each connector stays under 150 lines.

### Anti-Pattern 2: Mutable Updates Instead of Append-Only

**What people do:** When macro data gets revised, they UPDATE the existing row with the new value.

**Why it's wrong:** Destroys point-in-time correctness. Backtests become impossible because you no longer know what value was available when. This is the number one cause of look-ahead bias in macro trading systems.

**Do this instead:** Always INSERT new rows with a new `release_time`. Query with `release_time <= as_of` to reconstruct historical information states. Accept the storage cost (it is small relative to the value of correct backtests).

### Anti-Pattern 3: Using Airflow/Dagster for 11 Daily Jobs

**What people do:** Install a full orchestration platform (Airflow, Dagster, Prefect) to schedule 11 data connectors that run once a day.

**Why it's wrong:** Massive operational overhead for a simple scheduling need. Airflow alone requires a metadata database, scheduler process, webserver, and workers. For a solo user with 11 cron-like jobs, this is overkill that consumes 2-4GB of RAM and adds significant complexity.

**Do this instead:** Use APScheduler or a simple async scheduler with retry logic. Define jobs as async functions. Add logging and error notifications. If the system grows to 50+ jobs with complex dependencies, then consider Airflow. Not before.

### Anti-Pattern 4: Premature Kafka Introduction

**What people do:** Set up Kafka from day one because "we might need event streaming later."

**Why it's wrong:** Kafka adds significant operational complexity: Zookeeper (or KRaft), topic management, consumer groups, offset management, monitoring. For batch ingestion of daily macro data, it provides zero value. The connectors can write directly to TimescaleDB.

**Do this instead:** Build connectors that write directly to the database. Design them so the storage step can be swapped later (dependency injection). When you actually need event-driven processing (real-time signal propagation between agents in Phase 1+), introduce Kafka then. The Docker Compose file can include Kafka in comments or as a disabled service.

### Anti-Pattern 5: Shared Database Sessions Across Connectors

**What people do:** Create one database session and pass it to all connectors during a batch run. If one connector fails, the rollback affects all previously ingested data.

**Why it's wrong:** One connector failure corrupts the entire batch. Partial progress is lost. Debugging becomes impossible because you cannot tell which connector caused the issue.

**Do this instead:** Each connector gets its own session. Each connector commits independently. Failed connectors are logged and retried without affecting others. The orchestrator tracks per-connector status.

## Integration Points

### External Services (Data Sources)

| Service | Integration Pattern | Rate Limits / Gotchas |
|---------|---------------------|----------------------|
| BCB SGS | REST/JSON, `api.bcb.gov.br` | No auth required. Comma decimal separator ("1.234,56"). Date format DD/MM/YYYY. |
| BCB PTAX | REST/OData, `olinda.bcb.gov.br` | No auth required. Date format MM-DD-YYYY (different from SGS). |
| BCB Focus | REST/OData, `olinda.bcb.gov.br` | No auth required. Published weekly (Mondays). Paginated results. |
| FRED | REST/JSON, `api.stlouisfed.org` | Requires free API key. 120 requests/minute limit. |
| IBGE SIDRA | REST/JSON, `apisidra.ibge.gov.br` | No auth required. Complex query parameter syntax. |
| STN Fiscal | REST/JSON or CSV | No auth required. Data format varies by endpoint. |
| B3/Tesouro | REST/JSON, Tesouro Direto API | No auth required. Historical data via CSV downloads. |
| CFTC | CSV download from cftc.gov | Weekly release (Fridays). Large files. Disaggregated report format. |
| US Treasury | REST/XML or CSV | No auth required. yield.xml endpoint for daily curves. |
| Yahoo Finance | yfinance library (unofficial) | No auth. Throttling possible. Data quality varies. Not an official API. |
| ANBIMA | TBD (placeholder) | May require institutional access for full data. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Connectors -> TimescaleDB | Direct async SQLAlchemy writes | Each connector manages its own session; idempotent upserts |
| Transforms -> TimescaleDB | Read raw data, write derived data | Pure functions; reads from bronze tables, writes to same or separate derived tables |
| API -> TimescaleDB | Async queries via session dependency | Read-only from API perspective; connection pooling critical |
| API -> Redis | Direct async redis client | Cache-aside pattern; cache populated on first miss |
| Orchestrator -> Connectors | Direct function calls | Orchestrator instantiates connectors, calls `ingest()`, handles errors |
| Orchestrator -> Transforms | Direct function calls | Orchestrator calls transform functions after ingestion completes |
| Orchestrator -> Quality | Direct function calls | Quality checks run after transforms complete |

### Future Integration (Phase 1+)

| Boundary | Communication | When |
|----------|---------------|------|
| Connectors -> Kafka | Publish raw data events | When real-time signal propagation needed for agents |
| Kafka -> Transforms | Subscribe to data events, compute on arrival | When transforms need to be event-driven |
| Kafka -> Agents | Subscribe to signal events | When AI agents need real-time macro data |
| API -> Auth middleware | JWT/API key validation | When team access is required |

## Build Order (Dependencies)

The build order is driven by data flow: you cannot transform what you have not ingested, and you cannot serve what you have not transformed.

```
Phase 0a: Foundation
    Infrastructure (Docker Compose, TimescaleDB, Redis)
    Core models (SQLAlchemy ORM, Alembic migrations)
    Seed data (instruments, series metadata)
        │
        ▼
Phase 0b: Ingestion
    BaseConnector abstract class
    First 3-4 connectors (BCB SGS, FRED, Yahoo, BCB PTAX)
    Backfill orchestrator (basic: date range iteration, checkpointing)
        │
        ▼
Phase 0c: Remaining Connectors + Bronze Complete
    Remaining connectors (Focus, IBGE, STN, B3, CFTC, US Treasury, FX Flow)
    Data quality framework (completeness checks, gap detection)
        │
        ▼
Phase 0d: Transforms (Silver Layer)
    Curve fitting (Nelson-Siegel)
    Returns, vol, z-scores, percentile ranks
    Macro calculations (YoY, diffusion, surprise)
    Vol surface reconstruction
        │
        ▼
Phase 0e: API + Caching (Gold Layer)
    FastAPI application with routers
    Redis caching layer
    Dashboard endpoint
    Health check / verification script
```

**Rationale for this order:**

1. **Foundation first** because everything depends on the database schema and Docker stack. You cannot write connectors without tables to write into.

2. **Ingestion before transforms** because transforms consume raw data. There is nothing to transform until connectors populate the bronze layer.

3. **A few connectors first, then the rest** because the first 3-4 connectors validate the BaseConnector pattern and the upsert logic. Once the pattern is proven, remaining connectors are largely mechanical (same pattern, different API).

4. **Transforms after all connectors** because some transforms require data from multiple sources (e.g., breakeven inflation = nominal curve - real curve, which needs both US Treasury and B3/Tesouro data).

5. **API last** because it serves data that must exist first. Building the API before the data exists leads to mocking and disconnects. Building it after means every endpoint can be tested against real data immediately.

## Sources

- [Macrobond: The critical role of Point-in-Time data](https://www.macrobond.com/insights/blogs/the-critical-role-of-point-in-time-data-in-economic-forecasting-and-quant-trading) -- PIT architecture for macro data (MEDIUM confidence)
- [FactSet: Accurately Backtesting Financial Models](https://insight.factset.com/hubfs/Resources%20Section/White%20Papers/ID11996_point_in_time.pdf) -- PIT correctness whitepaper (MEDIUM confidence)
- [QLib: Point-in-Time Database](https://qlib.readthedocs.io/en/latest/advanced/PIT.html) -- PIT implementation reference (HIGH confidence, official docs)
- [Macrosynergy: Macroeconomic data and systematic trading](https://macrosynergy.com/research/macroeconomic-data-and-systematic-trading-strategies/) -- Macro-quantamental system design (MEDIUM confidence)
- [Timescale Docs: About Hypertables](https://docs.timescale.com/use-timescale/latest/hypertables/about-hypertables/) -- Hypertable architecture (HIGH confidence, official docs)
- [Timescale: Best Practices for Hypertables](https://docs-dev.timescale.com/docs-tutorial-lambda-cd/timescaledb/tutorial-lambda-cd/how-to-guides/hypertables/best-practices/) -- Chunk intervals, indexing (HIGH confidence, official docs)
- [Leapcell: Building High-Performance Async APIs with FastAPI, SQLAlchemy 2.0, and Asyncpg](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg) -- Async stack patterns (MEDIUM confidence)
- [Databricks: What is a Medallion Architecture?](https://www.databricks.com/glossary/medallion-architecture) -- Bronze/Silver/Gold layer pattern (HIGH confidence, official docs)
- [Start Data Engineering: Data Pipeline Design Patterns](https://www.startdataengineering.com/post/code-patterns/) -- Factory pattern, idempotency (MEDIUM confidence)
- [AWS: Redis vs Kafka comparison](https://aws.amazon.com/compare/the-difference-between-kafka-and-redis/) -- Messaging architecture decision (HIGH confidence, official docs)
- [Better Stack: Redis vs Kafka 2026](https://betterstack.com/community/comparisons/redis-vs-kafka/) -- Small team messaging guidance (MEDIUM confidence)
- [Redis Docs: Time Series](https://redis.io/docs/latest/develop/data-types/timeseries/) -- Redis time series caching (HIGH confidence, official docs)
- [Medium: Redis Cache for Financial APIs](https://medium.com/@digvijay17july/increase-financial-api-response-time-using-redis-cache-techniques-and-ttl-97098b5721c6) -- TTL strategies (LOW confidence, single source)
- [python-bcb PyPI](https://pypi.org/project/python-bcb/) -- BCB SGS Python library (HIGH confidence, official package)
- [nelson-siegel-svensson PyPI](https://pypi.org/project/nelson-siegel-svensson/) -- Curve fitting library (HIGH confidence, official package)
- [Alembic Discussion #1465: TimescaleDB hypertable index conflicts](https://github.com/sqlalchemy/alembic/discussions/1465) -- Migration pitfall (HIGH confidence, official repo)
- [sqlalchemy-timescaledb PyPI](https://pypi.org/project/sqlalchemy-timescaledb/) -- TimescaleDB dialect for SQLAlchemy (HIGH confidence, official package)
- [MinIO: Building an S3-Compliant Stock Market Data Lake](https://blog.min.io/building-an-s3-compliant-stock-market-data-lake-with-minio/) -- Object storage for financial data (MEDIUM confidence)
- [MDPI: Engineering Sustainable Data Architectures for Modern Financial Institutions](https://www.mdpi.com/2079-9292/14/8/1650) -- Four-layer financial data architecture (MEDIUM confidence, peer-reviewed)

---
*Architecture research for: Macro Trading Data Infrastructure*
*Researched: 2026-02-19*
