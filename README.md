# Macro Trading System

A macro-directional trading platform covering FX, rates, inflation, sovereign credit, and cross-asset strategies across Brazil and US markets. Built on TimescaleDB with 11 data connectors, 250+ macro series, 24 trading strategies, 5 analytical agents, a risk engine (VaR, CVaR, stress testing), portfolio management system, and a FastAPI REST API.

## Architecture

```
  ┌───────────────────────────────────────────────────────────────────┐
  │                        FastAPI REST API                           │
  │  v1: /health /macro /curves /market /flows                       │
  │  v2: /signals /strategies /agents /backtest /risk /portfolio      │
  │  v3: /reports /monitoring /websocket                              │
  │  PMS: /trades /portfolio /risk /attribution /briefing /journal    │
  └──────────────────────────────┬────────────────────────────────────┘
                                 │
  ┌──────────────────────────────┼────────────────────────────────────┐
  │              │               │               │                    │
  ▼              ▼               ▼               ▼                    ▼
┌──────┐  ┌──────────┐  ┌────────────┐  ┌────────────┐  ┌───────────────┐
│ PMS  │  │ Portfolio │  │    Risk    │  │ Strategies │  │    Agents     │
│Trade │  │Constructor│  │VaR, CVaR  │  │ 24 macro   │  │5 analytical + │
│Mgmt  │  │Black-Lit. │  │Stress Test│  │ strategies │  │HMM regime     │
│Attrib│  │Cap Alloc  │  │Drawdown   │  │FX/Rates/Inf│  │detection      │
└──────┘  └──────────┘  └────────────┘  │Sov/Cross   │  └───────────────┘
                                        └────────────┘
                                              │
  ┌───────────────────────────────────────────┼───────────────────────┐
  │              │               │            │            │          │
  ▼              ▼               ▼            ▼            ▼          ▼
┌──────┐  ┌──────────┐  ┌────────────┐  ┌────────┐  ┌────────┐  ┌──────┐
│NLP   │  │Backtesting│  │ Transforms │  │Quality │  │Pipeline│  │Narr- │
│Senti-│  │Engine v2  │  │ (Silver)   │  │Checks  │  │Daily   │  │ative │
│ment  │  │Analytics  │  │curves/ret/ │  │PIT     │  │Orch.   │  │Gen.  │
│COPOM │  │Signals    │  │macro/vol   │  │        │  │        │  │      │
│FOMC  │  └──────────┘  └────────────┘  └────────┘  └────────┘  └──────┘
└──────┘
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

### v1: Data Layer (`/api/v1/`)

**Macro Data** (`/macro`)
- `GET /macro/dashboard` -- latest key indicators (BR + US + Market)
- `GET /macro/search?q=ipca&country=BRA` -- search series metadata
- `GET /macro/{series_code}?start=2020-01-01&pit=true` -- time series with point-in-time filtering

**Curves** (`/curves`)
- `GET /curves/available` -- list of available curve IDs
- `GET /curves/{curve_id}?date=2025-01-15` -- curve snapshot (all tenors)
- `GET /curves/{curve_id}/history?tenor=5Y&start=2020-01-01` -- single tenor history

**Market Data** (`/market-data`)
- `GET /market-data/latest?tickers=USDBRL,VIX,IBOVESPA` -- latest prices
- `GET /market-data/{ticker}?start=2024-01-01` -- OHLCV history

**Flows** (`/flows`)
- `GET /flows/positioning-summary` -- CFTC positioning with z-scores
- `GET /flows/{series_code}?start=2024-01-01` -- flow data history

### v2: Analytics & Strategy Layer (`/api/v2/`)

**Signals** (`/signals`) -- aggregated trading signals with confidence scores
**Strategies** (`/strategies`) -- 24 strategy configurations, performance, and live signals
**Agents** (`/agents`) -- analytical agent views (inflation, monetary, fiscal, FX, cross-asset)
**Backtest** (`/backtest`) -- backtesting engine with analytics and signal adapters
**Risk** (`/risk`) -- VaR, CVaR, stress testing, risk limits, drawdown monitoring
**Portfolio** (`/portfolio`) -- portfolio construction, Black-Litterman, capital allocation
**Dashboard** (`/dashboard`) -- consolidated dashboard with agent views and market overview

### v3: Reporting & Monitoring (`/api/v3/`)

**Reports** (`/reports`) -- generated strategy and portfolio reports
**Monitoring** (`/monitoring`) -- system health, pipeline status, signal monitoring
**WebSocket** (`/ws`) -- real-time signal and portfolio updates

### PMS: Portfolio Management System (`/api/pms/`)

**Trades** (`/trades`) -- trade entry, lifecycle management, blotter
**Portfolio** (`/portfolio`) -- position management, P&L, exposure
**Risk** (`/risk`) -- real-time risk monitoring, limit enforcement
**Attribution** (`/attribution`) -- performance attribution by strategy, factor, asset
**Briefing** (`/briefing`) -- morning pack generation, market overview
**Journal** (`/journal`) -- trade journal entries, strategy notes

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
│   │   └── routes/           # v1 (data), v2 (analytics), v3 (reports), PMS
│   ├── agents/               # 5 analytical agents + HMM regime detection
│   │   ├── base.py           # Agent framework base class
│   │   ├── inflation_agent.py
│   │   ├── monetary_agent.py
│   │   ├── fiscal_agent.py
│   │   ├── fx_agent.py
│   │   ├── cross_asset_agent.py
│   │   ├── hmm_regime.py     # Hidden Markov Model regime detection
│   │   └── registry.py       # Agent registry and orchestration
│   ├── strategies/           # 24 macro-directional strategies
│   │   ├── base.py           # Strategy base class
│   │   ├── registry.py       # Strategy registry
│   │   ├── fx_*.py           # 5 FX strategies (carry, momentum, flow, vol, ToT)
│   │   ├── rates_*.py        # 6 rates strategies (carry, Taylor, slope, spillover, term premium, events)
│   │   ├── inf_*.py          # 3 inflation strategies (breakeven, surprise, carry)
│   │   ├── sov_*.py          # 4 sovereign strategies (fiscal, CDS, EM RV, rating)
│   │   ├── cupom_*.py        # 2 cupom strategies (CIP basis, onshore-offshore)
│   │   └── cross_*.py        # 2 cross-asset strategies (regime, risk appetite)
│   ├── risk/                 # Risk management engine
│   │   ├── var_calculator.py # VaR and CVaR (parametric, historical, Monte Carlo)
│   │   ├── stress_tester.py  # Scenario-based stress testing
│   │   ├── drawdown_manager.py # Drawdown monitoring and circuit breakers
│   │   └── risk_limits.py    # Position and portfolio risk limits
│   ├── portfolio/            # Portfolio construction and optimization
│   │   ├── portfolio_constructor.py  # Portfolio assembly from signals
│   │   ├── black_litterman.py        # Black-Litterman model
│   │   ├── capital_allocator.py      # Capital allocation across strategies
│   │   ├── position_sizer.py         # Position sizing (Kelly, vol-target)
│   │   └── signal_aggregator.py      # Multi-agent signal aggregation
│   ├── pms/                  # Portfolio Management System
│   │   ├── trade_workflow.py # Trade lifecycle management
│   │   ├── position_manager.py # Position tracking and P&L
│   │   ├── attribution.py    # Performance attribution
│   │   ├── morning_pack.py   # Daily briefing generation
│   │   └── risk_monitor.py   # Real-time risk monitoring
│   ├── backtesting/          # Backtesting engine with PIT correctness
│   ├── nlp/                  # NLP pipeline (sentiment, COPOM/FOMC scraping)
│   ├── narrative/            # Report and narrative generation
│   ├── pipeline/             # Daily data pipeline orchestration
│   ├── monitoring/           # System monitoring
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
│   │   ├── models/           # SQLAlchemy ORM models
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
├── tests/                    # 1,383+ tests
│   ├── connectors/           # 162 connector tests (mocked HTTP)
│   ├── test_transforms/      # 96 transform tests
│   ├── test_agents/          # Agent framework tests
│   ├── test_strategies/      # 24 strategy tests
│   ├── test_risk/            # VaR, stress testing, drawdown, limits
│   ├── test_portfolio/       # Portfolio construction, allocation, signals
│   ├── test_pms/             # Trade workflow, attribution, morning pack
│   ├── test_integration/     # API v1/v2/v3, pipeline E2E
│   └── test_narrative/       # Report generation tests
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
make test           # Run all 1,383+ tests
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

## System Components by Phase

### Phase 0: Data Infrastructure (Complete)
11 data connectors, 250+ macro series (BR + US), TimescaleDB with 7 hypertables, silver-layer transforms (curves, returns, macro, vol surface), data quality framework with point-in-time checks, and FastAPI v1 endpoints for data access.

### Phase 1: Quantitative Models, Agents & Backtesting (Complete)
5 analytical agents (Inflation, Monetary Policy, Fiscal, FX Equilibrium, Cross-Asset) with HMM regime detection. Backtesting engine with point-in-time correctness. 8 initial trading strategies across FX, rates, inflation, and sovereign credit. Signal aggregation and multi-agent consensus framework.

### Phase 2: Strategy Engine, Risk & Portfolio Management (Complete)
Expanded to 24 macro-directional strategies. NLP pipeline for central bank communication (COPOM/FOMC scraping, sentiment analysis). Risk engine with VaR/CVaR (parametric, historical, Monte Carlo), stress testing, and drawdown management. Portfolio construction via Black-Litterman, capital allocation, and position sizing. Portfolio Management System (PMS) with trade lifecycle, attribution, and morning briefing pack. Narrative report generation.

### Phase 3: Production Infrastructure & Live Trading
Execution management system, FIX protocol connectivity, emergency stop mechanisms, authentication and security hardening, monitoring dashboards, and go-live checklist.
