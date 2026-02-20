# Macro Trading System

A data infrastructure platform for macro trading, tracking volatility signals and market sentiment across Brazil and US markets. Built on TimescaleDB with 11 data connectors, 250+ macro series, silver-layer transforms, and a FastAPI REST API.

## Architecture

```
                  ┌─────────────────────────────────────────────┐
                  │              FastAPI REST API                │
                  │  /health  /macro  /curves  /market  /flows  │
                  └──────────────────┬──────────────────────────┘
                                     │
          ┌──────────────────────────┼──────────────────────────┐
          │                          │                          │
  ┌───────▼───────┐        ┌─────────▼────────┐       ┌────────▼────────┐
  │   Transforms  │        │  Quality Checks  │       │  Data Quality   │
  │  (Silver)     │        │  (Completeness,  │       │  Alerts         │
  │  curves.py    │        │   Accuracy, PIT) │       │                 │
  │  returns.py   │        └──────────────────┘       └─────────────────┘
  │  macro.py     │
  │  vol_surface  │
  └───────▲───────┘
          │
  ┌───────┴──────────────────────────────────────────────────────┐
  │                     11 Data Connectors                       │
  │  BCB_SGS  FRED  BCB_FOCUS  BCB_PTAX  BCB_FX_FLOW           │
  │  IBGE_SIDRA  STN_FISCAL  B3_MARKET_DATA  TREASURY_GOV      │
  │  YAHOO_FINANCE  CFTC_COT                                    │
  └──────────────────────────┬───────────────────────────────────┘
                             │
  ┌──────────────────────────▼───────────────────────────────────┐
  │                     TimescaleDB (PG 16)                      │
  │  7 Hypertables: macro_series, market_data, curves,           │
  │                 flow_data, fiscal_data, vol_surfaces, signals │
  │  3 Metadata tables: instruments, series_metadata, data_src   │
  │  Compression policies + automatic chunking                   │
  └──────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url> && cd Macro_Trading
make setup            # copy .env, install deps, pull docker images

# 2. Start services
make up               # TimescaleDB, Redis, MongoDB, MinIO

# 3. Run migrations
make migrate          # create tables + hypertables + compression

# 4. Seed reference data
make seed             # instruments (25+) + series metadata (250+)

# 5. Backfill historical data
make backfill-fast    # BCB, FRED, Yahoo from 2020 (~15 min)
# or
make backfill         # all sources from 2010 (~60 min)

# 6. Start API
make api              # http://localhost:8000/docs

# 7. Verify everything
make verify           # full infrastructure check
```

## Docker Services

| Service      | Image                              | Port  | Purpose                        |
|-------------|---------------------------------------|-------|--------------------------------|
| TimescaleDB | `timescale/timescaledb:latest-pg16`   | 5432  | Time-series database           |
| Redis       | `redis:7-alpine`                      | 6379  | Cache and session store        |
| MongoDB     | `mongo:7`                             | 27017 | Document store                 |
| MinIO       | `minio/minio:latest`                  | 9000  | Object storage (S3 compatible) |
| Kafka*      | `confluentinc/cp-kafka:7.6.0`        | 9092  | Event streaming                |
| Zookeeper*  | `confluentinc/cp-zookeeper:7.6.0`    | 2181  | Kafka coordination             |

*Kafka/Zookeeper run under the `full` profile: `make up-full`

## Data Coverage

| Category       | Series | Source(s)                | Frequency        |
|---------------|--------|--------------------------|------------------|
| BR Inflation   | ~15    | BCB_SGS, IBGE_SIDRA      | Monthly          |
| BR Activity    | ~12    | BCB_SGS                  | Monthly/Daily    |
| BR Monetary    | ~12    | BCB_SGS                  | Daily            |
| BR External    | ~10    | BCB_SGS, BCB_PTAX        | Daily/Monthly    |
| BR Fiscal      | ~8     | BCB_SGS, STN_FISCAL      | Monthly          |
| BR Flows       | ~4     | BCB_FX_FLOW              | Weekly           |
| BR Expectations| ~10    | BCB_FOCUS                | Weekly           |
| US Inflation   | ~14    | FRED                     | Monthly/Daily    |
| US Activity    | ~20    | FRED                     | Monthly/Weekly   |
| US Monetary    | ~13    | FRED                     | Daily            |
| US Fiscal      | ~2     | FRED                     | Quarterly        |
| Curves         | ~24    | B3, TREASURY_GOV, BCB    | Daily            |
| Market Prices  | ~25    | YAHOO_FINANCE            | Daily            |
| Positioning    | ~48    | CFTC_COT                 | Weekly           |
| **Total**      | **250+** |                        |                  |

## API Endpoints

### Health
- `GET /health` -- liveness check with DB connectivity
- `GET /health/data-status` -- record counts per table

### Macro Data (`/api/v1/macro`)
- `GET /macro/dashboard` -- latest key indicators (BR + US + Market)
- `GET /macro/search?q=ipca&country=BRA` -- search series metadata
- `GET /macro/{series_code}?start=2020-01-01&pit=true` -- time series with point-in-time filtering

### Curves (`/api/v1/curves`)
- `GET /curves/available` -- list of available curve IDs
- `GET /curves/{curve_id}?date=2025-01-15` -- curve snapshot (all tenors)
- `GET /curves/{curve_id}/history?tenor=5Y&start=2020-01-01` -- single tenor history

### Market Data (`/api/v1/market-data`)
- `GET /market-data/latest?tickers=USDBRL,VIX,IBOVESPA` -- latest prices
- `GET /market-data/{ticker}?start=2024-01-01` -- OHLCV history

### Flows (`/api/v1/flows`)
- `GET /flows/positioning-summary` -- CFTC positioning with z-scores
- `GET /flows/{series_code}?start=2024-01-01` -- flow data history

Full Swagger docs at `http://localhost:8000/docs`.

## Silver Layer Transforms

| Module           | Functions                                                    |
|-----------------|--------------------------------------------------------------|
| `curves.py`     | Nelson-Siegel fitting, interpolation, breakeven inflation, forward rates, DV01, carry & roll-down |
| `returns.py`    | Log/simple returns, rolling volatility, z-scores, percentile rank, correlations, EMA, Sharpe, drawdowns |
| `macro.py`      | YoY from MoM, diffusion index, trimmed mean, surprise index, momentum |
| `vol_surface.py`| Smile reconstruction, IV/RV ratio, vol slope                 |

## Project Structure

```
Macro_Trading/
├── alembic/                  # Database migrations
│   └── versions/             # Migration scripts
├── scripts/
│   ├── seed_instruments.py   # Seed reference instruments
│   ├── seed_series_metadata.py # Seed series definitions
│   ├── backfill.py           # Historical data backfill orchestrator
│   └── verify_infrastructure.py # End-to-end verification
├── src/
│   ├── api/                  # FastAPI application
│   │   ├── main.py           # App entry point, CORS, lifespan
│   │   ├── deps.py           # Dependency injection (DB sessions)
│   │   └── routes/           # health, macro, curves, market_data, flows
│   ├── connectors/           # 11 data source connectors
│   │   ├── base.py           # Abstract BaseConnector
│   │   ├── bcb_sgs.py        # BCB SGS (50 BR macro series)
│   │   ├── fred.py           # FRED (50 US macro series)
│   │   ├── bcb_focus.py      # BCB Focus survey expectations
│   │   ├── bcb_ptax.py       # Official USDBRL rate
│   │   ├── bcb_fx_flow.py    # FX capital flows
│   │   ├── ibge_sidra.py     # IPCA by component (IBGE)
│   │   ├── stn_fiscal.py     # Fiscal data (Treasury)
│   │   ├── b3_market_data.py # DI curve, NTN-B, equities
│   │   ├── treasury_gov.py   # US Treasury yield curves
│   │   ├── yahoo_finance.py  # Market prices (FX, indices, commodities)
│   │   └── cftc_cot.py       # CFTC Commitment of Traders
│   ├── core/
│   │   ├── config.py         # Pydantic-settings configuration
│   │   ├── database.py       # SQLAlchemy async/sync engines
│   │   ├── redis_client.py   # Redis client singleton
│   │   ├── models/           # SQLAlchemy ORM models (10 tables)
│   │   ├── schemas/          # Pydantic shared schemas
│   │   └── utils/            # date_utils, logging, retry
│   ├── transforms/           # Silver layer computations
│   │   ├── curves.py         # Nelson-Siegel, interpolation, forward rates
│   │   ├── returns.py        # Returns, volatility, z-scores
│   │   ├── macro.py          # YoY, diffusion, trimmed mean
│   │   └── vol_surface.py    # Vol smile reconstruction
│   └── quality/              # Data quality framework
│       ├── checks.py         # Completeness, accuracy, PIT checks
│       └── alerts.py         # Log-based quality alerts
├── tests/                    # 319 tests
│   ├── connectors/           # 162 connector tests (mocked HTTP)
│   └── test_transforms/      # 96 transform tests
├── docker-compose.yml        # 6 services
├── pyproject.toml            # Python 3.11+, SQLAlchemy 2.0, FastAPI
├── Makefile                  # Common operations
└── alembic.ini               # Migration config
```

## Make Targets

```
make setup          # First-time setup (env, deps, docker pull)
make up             # Start Docker services
make down           # Stop Docker services
make migrate        # Run Alembic migrations
make seed           # Seed instruments + series metadata
make backfill       # Full historical backfill (all sources, 2010+)
make backfill-fast  # Quick backfill (BCB, FRED, Yahoo, 2020+)
make api            # Start FastAPI server (port 8000)
make test           # Run all 319 tests
make lint           # Run ruff linter
make verify         # Full infrastructure verification
make quality        # Run data quality checks
make psql           # Open psql shell on TimescaleDB
```

## Requirements

- Python 3.11+
- Docker + Docker Compose
- 16GB+ RAM, 50GB+ disk
- FRED API key (free: https://fred.stlouisfed.org/docs/api/api_key.html)

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable            | Default         | Description                    |
|--------------------|-----------------|--------------------------------|
| `POSTGRES_HOST`    | `localhost`     | TimescaleDB host               |
| `POSTGRES_PORT`    | `5432`          | TimescaleDB port               |
| `POSTGRES_DB`      | `macro_trading` | Database name                  |
| `POSTGRES_USER`    | `macro_user`    | Database user                  |
| `POSTGRES_PASSWORD`| `macro_pass`    | Database password              |
| `REDIS_HOST`       | `localhost`     | Redis host                     |
| `FRED_API_KEY`     | *(required)*    | FRED API key for US macro data |

## Next Phase

**Phase 1: Quantitative Models & Agents** -- 5 analytical agents (Inflation, Monetary Policy, Fiscal, FX Equilibrium, Cross-Asset), backtesting engine with point-in-time correctness, 8 initial trading strategies, signal aggregation, risk management, and web dashboard.
