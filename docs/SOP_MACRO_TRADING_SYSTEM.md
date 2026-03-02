# Standard Operating Procedures (SOP)
# Macro Trading System — Global Macro Hedge Fund

> **Version:** 1.0
> **Date:** 2026-03-02
> **Classification:** Internal — Confidential
> **Owner:** Portfolio Management Team

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture & Technology Stack](#2-architecture--technology-stack)
3. [Infrastructure Services](#3-infrastructure-services)
4. [Environment Setup & Configuration](#4-environment-setup--configuration)
5. [Data Pipeline Operations](#5-data-pipeline-operations)
6. [Analytical Agents](#6-analytical-agents)
7. [Trading Strategies](#7-trading-strategies)
8. [Risk Management Engine](#8-risk-management-engine)
9. [Portfolio Management System (PMS)](#9-portfolio-management-system-pms)
10. [Daily Operating Routine](#10-daily-operating-routine)
11. [Morning Pack Workflow](#11-morning-pack-workflow)
12. [Trade Proposal & Approval Workflow](#12-trade-proposal--approval-workflow)
13. [Decision Journal & Audit Trail](#13-decision-journal--audit-trail)
14. [Emergency Stop Procedure](#14-emergency-stop-procedure)
15. [Monitoring & Alerting](#15-monitoring--alerting)
16. [Backup & Disaster Recovery](#16-backup--disaster-recovery)
17. [API Reference Summary](#17-api-reference-summary)
18. [Troubleshooting Guide](#18-troubleshooting-guide)
19. [Appendix A: Make Commands Quick Reference](#appendix-a-make-commands-quick-reference)
20. [Appendix B: Database Schema Reference](#appendix-b-database-schema-reference)
21. [Appendix C: Data Source Catalog](#appendix-c-data-source-catalog)

---

## 1. System Overview

### 1.1 Purpose

The Macro Trading System is an institutional-grade platform for **global macro directional trading** focused on Brazil and the United States. It combines automated data collection, quantitative analysis via AI-powered agents, 25+ trading strategies, and a human-in-the-loop Portfolio Management System (PMS).

### 1.2 Investment Universe

| Asset Class | Instruments | Markets |
|---|---|---|
| **FX** | USDBRL spot, futures, options, NDFs, DXY, G10 pairs | B3, BM&F, OTC |
| **Rates (Brazil)** | DI futures (30+ tenors), cupom cambial, NTN-B, LTN | B3 |
| **Rates (US)** | Treasuries (2Y-30Y), TIPS, SOFR, Fed Funds futures | CME, ICE |
| **Inflation** | IPCA breakevens, CPI breakevens, inflation swaps | OTC |
| **Sovereign Credit** | CDS 5Y, EMBI+, global bonds, credit indices (CDX) | OTC |
| **Cross-Asset** | VIX, MOVE index, commodities (iron ore, soy, oil, gold, copper) | Various |

### 1.3 Core Design Principles

| Principle | Description |
|---|---|
| **Human-in-the-Loop** | System generates proposals; the portfolio manager approves or rejects. No automated execution. |
| **Point-in-Time Correctness** | All data queries respect release timestamps. Prevents look-ahead bias in backtests. |
| **Immutable Audit Trail** | Every decision (open, close, modify, reject) is logged with hash checksums. Records are locked. |
| **Graceful Degradation** | Each service component fails independently. Morning pack generates with partial data. |
| **Three-Layer Data Pipeline** | Bronze (raw) → Silver (cleaned) → Gold (derived). Raw data is never modified. |

---

## 2. Architecture & Technology Stack

### 2.1 System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          MACRO TRADING SYSTEM                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐           │
│  │  DATA SOURCES    │   │  DATA SOURCES    │   │  DATA SOURCES    │           │
│  │  (Brazil)        │   │  (USA)           │   │  (Global)        │           │
│  │  BCB SGS/Focus   │   │  FRED            │   │  Yahoo Finance   │           │
│  │  B3 Market Data  │   │  Treasury.gov    │   │  CFTC CoT        │           │
│  │  ANBIMA          │   │  FMP             │   │  OECD SDMX       │           │
│  │  IBGE SIDRA      │   │                  │   │                  │           │
│  │  STN Fiscal      │   │                  │   │                  │           │
│  └───────┬─────────┘   └───────┬──────────┘   └───────┬──────────┘          │
│          │                      │                       │                     │
│          ▼                      ▼                       ▼                     │
│  ┌──────────────────────────────────────────────────────────────┐            │
│  │                    15 DATA CONNECTORS                         │            │
│  │  bcb_sgs · bcb_focus · bcb_ptax · bcb_fx_flow · b3           │            │
│  │  anbima · ibge_sidra · stn_fiscal · fred · treasury_gov      │            │
│  │  fmp_treasury · yahoo_finance · cftc_cot · oecd_sdmx         │            │
│  │  te_di_curve                                                  │            │
│  └──────────────────────────┬───────────────────────────────────┘            │
│                              │                                               │
│                    ┌─────────▼──────────┐                                    │
│                    │  BRONZE LAYER       │                                    │
│                    │  (Raw Ingestion)    │                                    │
│                    └─────────┬──────────┘                                    │
│                              │                                               │
│                    ┌─────────▼──────────┐                                    │
│                    │  SILVER LAYER       │                                    │
│                    │  (Clean/Validate)   │                                    │
│                    └─────────┬──────────┘                                    │
│                              │                                               │
│              ┌───────────────┼───────────────┐                               │
│              ▼               ▼               ▼                               │
│  ┌───────────────┐ ┌─────────────┐ ┌──────────────┐                         │
│  │  5 ANALYTICAL  │ │ 25 TRADING  │ │ NLP PIPELINE │                         │
│  │  AGENTS        │ │ STRATEGIES  │ │ COPOM/FOMC   │                         │
│  └───────┬───────┘ └──────┬──────┘ └──────┬───────┘                         │
│          │                │               │                                  │
│          └────────────────┼───────────────┘                                  │
│                           ▼                                                  │
│              ┌──────────────────────┐                                        │
│              │  SIGNAL AGGREGATION   │                                        │
│              │  + PORTFOLIO          │                                        │
│              │    CONSTRUCTION       │                                        │
│              └──────────┬───────────┘                                        │
│                         │                                                    │
│          ┌──────────────┼───────────────┐                                    │
│          ▼              ▼               ▼                                     │
│  ┌──────────────┐ ┌──────────┐ ┌────────────────┐                            │
│  │ RISK ENGINE   │ │ PMS      │ │ REPORTING      │                            │
│  │ VaR/CVaR      │ │ Positions│ │ Morning Pack   │                            │
│  │ Stress Tests  │ │ Blotter  │ │ Daily Reports  │                            │
│  │ Limits        │ │ Journal  │ │ Attribution    │                            │
│  └──────────────┘ └──────────┘ └────────────────┘                            │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE                                                              │
│  TimescaleDB · Redis · MongoDB · Kafka · MinIO · Grafana · Dagster          │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Component | Technology | Version | Purpose |
|---|---|---|---|
| **Time Series DB** | TimescaleDB (PostgreSQL) | 2.18.0 / PG16 | All financial time series with hypertables, compression, point-in-time queries |
| **Cache** | Redis | 7 Alpine | Hot data cache, sub-ms latency, pub/sub for real-time updates |
| **Document Store** | MongoDB | 8.0 | NLP corpus (COPOM/FOMC minutes), flexible schema documents |
| **Message Queue** | Kafka (KRaft mode) | 7.8.0 | Real-time streaming, event replay, exactly-once semantics |
| **Object Store** | MinIO | 2025-02 | Raw file archives (PDFs, CSVs), immutable storage |
| **Monitoring** | Grafana | 11.4.0 | Dashboards for pipeline health, VaR trends, system metrics |
| **Orchestration** | Dagster | Latest | DAG-based pipeline scheduling, dependency management, retries |
| **API** | FastAPI | Latest | REST API with OpenAPI docs, rate limiting, CORS, WebSocket |
| **Language** | Python | 3.11+ | Core application, all services |
| **ORM** | SQLAlchemy 2.0 | Async | Database models, migrations via Alembic |

---

## 3. Infrastructure Services

### 3.1 Service Topology

| Service | Container | Port | Health Check | Profile |
|---|---|---|---|---|
| TimescaleDB | `macro_timescaledb` | `127.0.0.1:5432` | `pg_isready` | default |
| Redis | `macro_redis` | `127.0.0.1:6379` | `redis-cli ping` | default |
| MongoDB | `macro_mongodb` | `127.0.0.1:27017` | `mongosh ping` | default |
| Kafka | `macro_kafka` | `127.0.0.1:9092` | `kafka-broker-api-versions` | `full` |
| MinIO | `macro_minio` | `127.0.0.1:9000` (API), `9001` (Console) | `mc ready local` | default |
| Grafana | `macro_grafana` | `0.0.0.0:3000` | — | `monitoring` |
| Dagster Web | `macro_dagster` | `0.0.0.0:3001` | — | `dagster` |
| Dagster Daemon | `macro_dagster_daemon` | — | — | `dagster` |
| FastAPI | `macro_api` | `0.0.0.0:8000` | `curl http://localhost:8000/health` | default |

### 3.2 Service Start/Stop Commands

```bash
# Start core services (TimescaleDB, Redis, MongoDB, MinIO, API)
make up

# Start all services including Kafka
make up-full

# Start with monitoring (adds Grafana)
docker compose --profile monitoring up -d

# Start with orchestration (adds Dagster)
make dagster

# Stop all services (preserves data)
make down

# Stop and DELETE all data volumes (destructive!)
make down-clean

# Check running services
make ps

# Follow logs
make logs
```

### 3.3 Persistent Volumes

| Volume | Service | Content |
|---|---|---|
| `timescaledb_data` | TimescaleDB | All time series, instruments, signals, positions |
| `redis_data` | Redis | Cache data (AOF persistence) |
| `mongodb_data` | MongoDB | NLP corpus, central bank documents |
| `kafka_data` | Kafka | Event log, topic data |
| `minio_data` | MinIO | Raw file archives |
| `grafana_data` | Grafana | Dashboard configs, alerting state |

---

## 4. Environment Setup & Configuration

### 4.1 Prerequisites

- Docker & Docker Compose v2+
- Python 3.11+
- 16GB+ RAM (recommended)
- FRED API key (required for US macro data)
- ANBIMA credentials (optional, for Brazilian bond data)

### 4.2 First-Time Setup

```bash
# 1. Clone the repository
git clone <repo-url> && cd Macro_Trading

# 2. Run automated setup (copies .env, installs deps, pulls images)
make setup

# 3. Edit .env with real credentials
vim .env

# 4. Start infrastructure
make up

# 5. Run database migrations
make migrate

# 6. Seed reference data
make seed

# 7. Verify everything is healthy
make verify
```

### 4.3 Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `POSTGRES_PASSWORD` | Yes | TimescaleDB password |
| `REDIS_PASSWORD` | Yes | Redis authentication |
| `MONGO_PASSWORD` | Yes | MongoDB root password |
| `MINIO_SECRET_KEY` | Yes | MinIO storage secret |
| `FRED_API_KEY` | Yes | Federal Reserve Economic Data API |
| `ANTHROPIC_API_KEY` | No | For LLM-powered narrative generation |
| `ANBIMA_CLIENT_ID` | No | ANBIMA Data API (OAuth2) |
| `ANBIMA_CLIENT_SECRET` | No | ANBIMA Data API (OAuth2) |
| `JWT_SECRET_KEY` | Yes | API authentication signing key |
| `FMP_API_KEY` | No | Financial Modeling Prep (Treasury data) |
| `TE_API_KEY` | No | Trading Economics (DI curve) |

### 4.4 Configuration File

All settings are managed in `src/core/config.py` via Pydantic Settings. The `Settings` class reads from `.env` and provides computed connection URLs:

- `settings.async_database_url` — Async PostgreSQL URL (asyncpg)
- `settings.sync_database_url` — Sync PostgreSQL URL (psycopg2, Alembic)
- `settings.redis_url` — Redis connection string
- `settings.mongo_url` — MongoDB connection string

---

## 5. Data Pipeline Operations

### 5.1 Pipeline Architecture

The daily pipeline follows an 8-step sequential execution:

```
ingest → quality → agents → aggregate → strategies → portfolio → risk → report
```

Each step is timed and produces CI-style formatted output. On failure, the pipeline aborts immediately (no partial execution).

### 5.2 Data Connectors

The system includes **15 data connectors** organized by source:

| # | Connector | Module | Source | Data |
|---|---|---|---|---|
| 1 | BCB SGS | `connectors/bcb_sgs.py` | Banco Central do Brasil | 200+ macro series (SELIC, CDI, credit, employment) |
| 2 | BCB Focus | `connectors/bcb_focus.py` | BCB Focus Survey | Market expectations (IPCA, SELIC, GDP, FX) |
| 3 | BCB PTAX | `connectors/bcb_ptax.py` | BCB | Official USDBRL exchange rate |
| 4 | BCB FX Flow | `connectors/bcb_fx_flow.py` | BCB | Capital flows (commercial, financial) |
| 5 | B3 | `connectors/b3_market_data.py` | B3 Exchange | Futures, options, market data |
| 6 | ANBIMA | `connectors/anbima.py` | ANBIMA | Bond curves, NTN-B, inflation-linked |
| 7 | IBGE SIDRA | `connectors/ibge_sidra.py` | IBGE | IPCA, industrial production, retail sales |
| 8 | STN Fiscal | `connectors/stn_fiscal.py` | Tesouro Nacional | Fiscal data, debt dynamics |
| 9 | FRED | `connectors/fred.py` | Federal Reserve | 800k+ US macro series (CPI, NFP, GDP) |
| 10 | Treasury.gov | `connectors/treasury_gov.py` | US Treasury | Yield curves, TIC flows |
| 11 | FMP Treasury | `connectors/fmp_treasury.py` | Financial Modeling Prep | Treasury rates, real-time |
| 12 | Yahoo Finance | `connectors/yahoo_finance.py` | Yahoo | Equity indices, commodities, FX |
| 13 | CFTC CoT | `connectors/cftc_cot.py` | CFTC | Commitment of Traders positioning |
| 14 | OECD SDMX | `connectors/oecd_sdmx.py` | OECD | International macro data |
| 15 | TE DI Curve | `connectors/te_di_curve.py` | Trading Economics | DI futures curve |

### 5.3 Running the Pipeline

```bash
# Run daily pipeline for today
make daily

# Dry run (no DB writes — useful for validation)
make daily-dry

# Run for a specific date
make daily-date DATE=2025-12-15

# Full historical backfill (all sources, from 2010)
make backfill

# Fast backfill (key sources only, from 2020)
make backfill-fast
```

### 5.4 Pipeline Output: PipelineResult

Each pipeline run produces a `PipelineResult` with:

| Field | Description |
|---|---|
| `run_id` | UUID for the run |
| `date` | As-of date |
| `status` | `SUCCESS` or `FAILED` |
| `duration_seconds` | Total wall-clock time |
| `step_timings` | Per-step duration breakdown |
| `signal_count` | Total signals from all agents |
| `position_count` | Strategy positions generated |
| `regime` | Detected market regime (e.g., `"RISK_ON"`, `"NEUTRAL"`, `"CRISIS"`) |
| `leverage` | Portfolio leverage ratio |
| `var_95` | 95th percentile Value-at-Risk |
| `risk_alerts` | Active risk limit breaches |

### 5.5 Data Quality Checks

```bash
# Run data quality validation
make quality
```

The `DataQualityChecker` validates:
- **Completeness**: Missing values, gaps in time series
- **Outliers**: Z-score > 5 on daily changes
- **Staleness**: Data not updated within expected SLA
- **Revisions**: Tracking data revisions vs. original releases
- **Release timing**: Point-in-time correctness validation

### 5.6 Dagster Orchestration

For production scheduling, the system uses Dagster with asset-based DAGs:

```bash
# Start Dagster UI + daemon
make dagster

# Materialize all assets in dependency order
make dagster-run-all
```

**Dagster Asset Groups** (`src/orchestration/`):

| Module | Assets |
|---|---|
| `assets_bronze.py` | Raw data ingestion from all connectors |
| `assets_silver.py` | Cleaned/validated data transformations |
| `assets_agents.py` | Analytical agent runs |
| `assets_signals.py` | Signal aggregation |
| `assets_portfolio.py` | Portfolio construction |
| `assets_risk.py` | Risk calculations |
| `assets_pms.py` | PMS operations (MTM, proposals, briefing) |
| `assets_report.py` | Report generation |

Access the Dagster UI at `http://<server>:3001`.

---

## 6. Analytical Agents

### 6.1 Agent Framework

All agents inherit from `BaseAgent` (Template Method pattern):

```
BaseAgent.run()
  ├── load_data()        # Fetch required data series
  ├── compute_features() # Calculate derived features
  ├── run_models()       # Execute quantitative models
  └── generate_narrative() # Produce textual analysis
```

**Agent outputs are standardized via:**

- **`AgentSignal`**: direction (`LONG`/`SHORT`/`NEUTRAL`), strength (`STRONG`/`MODERATE`/`WEAK`/`NO_SIGNAL`), confidence (0.0–1.0), z-score, metadata
- **`AgentReport`**: Collection of signals + narrative analysis + diagnostics

### 6.2 The Five Agents

| # | Agent | Module | Domain | Key Models |
|---|---|---|---|---|
| 1 | **InflationAgent** | `agents/inflation_agent.py` | Inflation dynamics | Phillips Curve, IPCA bottom-up decomposition, expectations anchoring |
| 2 | **MonetaryPolicyAgent** | `agents/monetary_agent.py` | Central bank policy | Taylor Rule, Kalman Filter neutral rate, reaction functions |
| 3 | **FiscalAgent** | `agents/fiscal_agent.py` | Fiscal sustainability | Debt Sustainability Analysis (DSA), fiscal impulse, debt dynamics |
| 4 | **FxEquilibriumAgent** | `agents/fx_agent.py` | Currency fair value | Behavioral Equilibrium Exchange Rate (BEER), carry analysis |
| 5 | **CrossAssetAgent** | `agents/cross_asset_agent.py` | Market regimes | HMM regime detection, correlation matrices, cross-asset momentum |

### 6.3 Agent Registry

Agents self-register via `AgentRegistry` on application startup:

```python
from src.agents.registry import AgentRegistry

# List all registered agents
agents = AgentRegistry.list_agents()

# Run a specific agent
report = AgentRegistry.get("inflation_agent").run(as_of_date=date.today())
```

### 6.4 Feature Engineering

Each agent has dedicated feature modules in `agents/features/`:

- `inflation_features.py` — IPCA components, core inflation, expectations gap
- `monetary_features.py` — Taylor gap, DI-SELIC spread, slope dynamics
- `fiscal_features.py` — Primary balance, debt/GDP trajectory, fiscal impulse
- `fx_features.py` — Real effective rate, terms of trade, carry vs. vol
- `cross_asset_features.py` — VIX regime, cross-correlation, risk appetite index

### 6.5 Strength Classification

| Confidence | Strength | Weight Multiplier |
|---|---|---|
| >= 0.75 | `STRONG` | 1.0 |
| >= 0.50 | `MODERATE` | 0.6 |
| >= 0.25 | `WEAK` | 0.3 |
| < 0.25 | `NO_SIGNAL` | 0.0 |

---

## 7. Trading Strategies

### 7.1 Strategy Framework

All strategies inherit from `BaseStrategy` and implement `generate_signals(as_of_date)`.

Strategy output is a `StrategySignal` with: direction, strength, z-score, entry/stop/take-profit levels, suggested position size.

Sizing formula: `raw_weight = STRENGTH_MAP[strength] * confidence * max_position_size`

### 7.2 Complete Strategy Catalog

#### FX Strategies (6)

| ID | Name | Module | Description |
|---|---|---|---|
| FX_BR_01 | Carry Fundamental | `fx_br_01_carry_fundamental.py` | USDBRL carry vs. fundamentals |
| FX_02 | Carry Momentum | `fx_02_carry_momentum.py` | G10 carry with momentum filter |
| FX_03 | Flow Tactical | `fx_03_flow_tactical.py` | BCB FX flow-based positioning |
| FX_04 | Vol Surface RV | `fx_04_vol_surface_rv.py` | Relative value on vol surface |
| FX_05 | Terms of Trade | `fx_05_terms_of_trade.py` | Commodity terms of trade signal |

#### Rates Strategies — Brazil (7)

| ID | Name | Module | Description |
|---|---|---|---|
| RATES_BR_01 | DI Carry | `rates_br_01_carry.py` | DI curve carry extraction |
| RATES_BR_02 | Taylor Rule | `rates_br_02_taylor.py` | Taylor gap vs. DI pricing |
| RATES_BR_03 | Slope | `rates_br_03_slope.py` | DI curve slope mean reversion |
| RATES_BR_04 | Spillover | `rates_br_04_spillover.py` | US rates spillover to Brazil |
| RATES_03 | BR-US Spread | `rates_03_br_us_spread.py` | Rate differential dynamics |
| RATES_04 | Term Premium | `rates_04_term_premium.py` | Term premium extraction |

#### Rates Strategies — Event (2)

| ID | Name | Module | Description |
|---|---|---|---|
| RATES_05 | FOMC Event | `rates_05_fomc_event.py` | Pre/post FOMC positioning |
| RATES_06 | COPOM Event | `rates_06_copom_event.py` | Pre/post COPOM positioning |

#### Inflation Strategies (3)

| ID | Name | Module | Description |
|---|---|---|---|
| INF_BR_01 | Breakeven | `inf_br_01_breakeven.py` | IPCA breakeven fair value |
| INF_02 | IPCA Surprise | `inf_02_ipca_surprise.py` | IPCA release surprise trade |
| INF_03 | Inflation Carry | `inf_03_inflation_carry.py` | NTN-B carry vs. nominal |

#### Cupom Cambial Strategies (2)

| ID | Name | Module | Description |
|---|---|---|---|
| CUPOM_01 | CIP Basis | `cupom_01_cip_basis.py` | Covered interest parity basis |
| CUPOM_02 | Onshore-Offshore | `cupom_02_onshore_offshore.py` | Onshore vs. offshore spread |

#### Sovereign Credit Strategies (4)

| ID | Name | Module | Description |
|---|---|---|---|
| SOV_BR_01 | Fiscal Risk | `sov_br_01_fiscal_risk.py` | Fiscal trajectory vs. CDS |
| SOV_01 | CDS Curve | `sov_01_cds_curve.py` | CDS curve shape signals |
| SOV_02 | EM Relative Value | `sov_02_em_relative_value.py` | Brazil vs. EM peers |
| SOV_03 | Rating Migration | `sov_03_rating_migration.py` | Rating upgrade/downgrade signal |

#### Cross-Asset Strategies (2)

| ID | Name | Module | Description |
|---|---|---|---|
| CROSS_01 | Regime Allocation | `cross_01_regime_allocation.py` | HMM regime-based allocation |
| CROSS_02 | Risk Appetite | `cross_02_risk_appetite.py` | Global risk appetite signal |

### 7.3 Strategy Registry

```python
from src.strategies import ALL_STRATEGIES
from src.strategies.registry import StrategyRegistry

# List all available strategies
for strategy in ALL_STRATEGIES:
    print(f"{strategy.config.strategy_id}: {strategy.config.strategy_name}")
```

---

## 8. Risk Management Engine

### 8.1 VaR/CVaR Calculator

Located in `src/risk/var_calculator.py`. Three methodologies:

| Method | Description | Parameters |
|---|---|---|
| **Historical** | Empirical quantile of portfolio return series | 756-day lookback |
| **Parametric** | Gaussian assumption with Ledoit-Wolf shrinkage | Analytical CVaR |
| **Monte Carlo** | Student-t marginals with Gaussian copula (Cholesky) | 10,000 simulations |

Both VaR and CVaR are computed at **95%** and **99%** confidence levels.

**Decomposition**: Marginal VaR and Component VaR per instrument.

### 8.2 Stress Testing

Located in `src/risk/stress_tester.py`.

| Scenario Type | Examples |
|---|---|
| **Historical** | 2008 GFC, 2013 Taper Tantrum, 2015 Brazil Recession, 2020 COVID, 2022 Rate Shock |
| **Hypothetical** | SELIC +300bp shock, USDBRL +20% devaluation, US 10Y +150bp, EM credit spread +200bp |
| **Reverse** | "What scenario causes a 5% portfolio loss?" |

### 8.3 Risk Limits

Located in `src/risk/risk_limits.py` and `risk_limits_v2.py`.

| Limit Type | Example Thresholds |
|---|---|
| **Portfolio VaR** | Max 2% of AUM at 95% confidence |
| **Gross Leverage** | Max 5x |
| **Net Leverage** | Max 2x |
| **Single Position** | Max 15% of AUM |
| **Asset Class Concentration** | Max 40% per asset class |
| **Strategy Concentration** | Max 25% per strategy |
| **Drawdown** | Max 8% from peak |
| **Daily Loss** | Max 1.5% of AUM |

### 8.4 Drawdown Manager

Located in `src/risk/drawdown_manager.py`.

Tracks running drawdown from equity peak. When drawdown exceeds thresholds, the system:
1. Issues alerts to the portfolio manager
2. Reduces position sizing multiplier automatically
3. At maximum threshold, triggers position freeze (no new trades)

### 8.5 Risk Monitor

Located in `src/risk/risk_monitor.py`.

Continuously monitors all risk metrics and publishes alerts via Redis pub/sub for real-time dashboard updates.

---

## 9. Portfolio Management System (PMS)

### 9.1 PMS Architecture

The PMS is the command center for the portfolio manager, providing:

| Component | Module | Responsibility |
|---|---|---|
| **PositionManager** | `pms/position_manager.py` | Open/close positions, MTM, P&L, risk metrics |
| **TradeWorkflow** | `pms/trade_workflow.py` | Generate proposals, approve/reject workflow |
| **MorningPack** | `pms/morning_pack.py` | Daily briefing with actionable intelligence |
| **Attribution** | `pms/attribution.py` | Multi-dimensional P&L attribution |
| **RiskMonitor** | `pms/risk_monitor.py` | Real-time risk limits monitoring |
| **MTM Service** | `pms/mtm_service.py` | Mark-to-market pricing |
| **Pricing** | `pms/pricing.py` | DV01, delta, P&L calculations |
| **DB Loader** | `pms/db_loader.py` | Database persistence for PMS entities |
| **Cache** | `cache/pms_cache.py` | Redis caching for hot PMS data |

### 9.2 Position Lifecycle

```
PROPOSED → APPROVED → OPEN → (MTM daily) → CLOSE_REQUESTED → CLOSED
                 ↓
              REJECTED
                 ↓
              MODIFIED → APPROVED → OPEN
```

### 9.3 Core PMS Database Tables

| Table | Type | Purpose |
|---|---|---|
| `portfolio_positions` | Regular | Live position book with Greeks |
| `trade_proposals` | Regular | System-generated trade ideas |
| `decision_journal` | Immutable | Audit log with hash checksums |
| `daily_briefings` | Regular | Morning pack archives |
| `position_pnl_history` | Hypertable | Daily P&L time series per position |
| `portfolio_state` | Regular | End-of-day portfolio snapshots |

---

## 10. Daily Operating Routine

### 10.1 Daily Timeline

| Time (BRT) | Activity | Responsible | Command/Action |
|---|---|---|---|
| **06:00** | Dagster triggers daily pipeline | Automated | Dagster schedule |
| **06:30** | Pipeline complete: data ingested, agents run | System | — |
| **07:00** | Morning Pack generated | System | `make morning-pack` |
| **07:15** | PM reviews Morning Pack | Portfolio Manager | API: `GET /api/v1/pms/briefing/latest` |
| **07:30** | PM reviews Trade Proposals | Portfolio Manager | API: `GET /api/v1/pms/trades/proposals` |
| **08:00** | PM approves/rejects proposals | Portfolio Manager | API: `POST /api/v1/pms/trades/proposals/{id}/decide` |
| **08:30** | Market open — execution begins | PM / Execution | Manual execution |
| **09:00–17:00** | Intraday monitoring | PM | Dashboard / WebSocket |
| **17:30** | End-of-day MTM update | System | Dagster EOD job |
| **18:00** | Risk report generated | System | `GET /api/v1/pms/risk/live` |
| **18:15** | PM reviews daily P&L and risk | Portfolio Manager | Dashboard |
| **18:30** | PM records decision notes | Portfolio Manager | `POST /api/v1/pms/journal/entry` |

### 10.2 Running the Pipeline Manually

```bash
# Standard daily run
python scripts/daily_run.py

# Dry run (validate without DB writes)
python scripts/daily_run.py --dry-run

# Run for a specific date
python scripts/daily_run.py --date 2025-12-15
```

### 10.3 Verification Commands

```bash
# Full infrastructure verification
make verify

# Quick verification (skip data quality)
make verify-quick

# PMS-specific verification
make verify-pms

# Full system verification (all phases)
make verify-all
```

---

## 11. Morning Pack Workflow

### 11.1 Overview

The Morning Pack is the daily command center for the portfolio manager. It consolidates all system intelligence into a single briefing.

### 11.2 Morning Pack Sections

| # | Section | Content |
|---|---|---|
| 1 | **Action Items** | Pending trade proposals, risk limit breaches, data quality alerts |
| 2 | **Market Snapshot** | Key prices at market open (SELIC, USDBRL, DI curve, Treasury curve, VIX) |
| 3 | **Agent Views** | Latest signal from each of the 5 agents with direction, strength, and narrative |
| 4 | **Regime Detection** | Current market regime (HMM) and regime transition probabilities |
| 5 | **Top Signals** | Strongest signals across all 25+ strategies, ranked by conviction |
| 6 | **Signal Changes** | Delta vs. previous day (new signals, flipped signals, removed signals) |
| 7 | **Portfolio State** | Open positions, total P&L, gross/net exposure, asset class breakdown |
| 8 | **Risk Metrics** | VaR (95/99%), CVaR, stress test results, limit utilization |
| 9 | **Trade Proposals** | System-generated trade ideas with full rationale and pre-trade risk |
| 10 | **Macro Narrative** | LLM-generated analysis tying together agent views and market context |

### 11.3 Generating Morning Pack

```bash
# Command line
make morning-pack

# API endpoint
GET /api/v1/pms/briefing/latest

# Retrieve historical briefing
GET /api/v1/pms/briefing/{date}
```

### 11.4 Graceful Degradation

If any dependency is unavailable (e.g., risk engine down), the corresponding section shows:
```json
{"status": "unavailable", "reason": "Risk engine connection timeout"}
```

The rest of the briefing generates normally.

---

## 12. Trade Proposal & Approval Workflow

### 12.1 Proposal Generation

Trade proposals are automatically generated daily based on:
- Agent signals (5 agents)
- Strategy signals (25+ strategies)
- Signal aggregation (weighted fusion)
- Portfolio construction (Black-Litterman optimization)

Each proposal includes:
- **Instrument** and direction (LONG/SHORT)
- **Macro context**: Why this trade makes sense given current environment
- **Risk factors**: Key risks to the thesis
- **Conviction level**: Based on signal strength and confidence
- **Pre-trade risk analysis**: VaR impact, leverage impact, concentration impact
- **Entry, stop-loss, and take-profit levels**
- **Expiration**: Valid for N days

### 12.2 Approval Workflow

```
SYSTEM generates proposal
        │
        ▼
PM receives in Morning Pack or Trade Blotter
        │
        ├──► APPROVE  → Position opened → Journal entry created
        │
        ├──► REJECT   → Reason recorded → Journal entry created
        │
        └──► MODIFY   → Adjust size/levels → Re-submit → Approve/Reject
```

### 12.3 API Endpoints

```
GET  /api/v1/pms/trades/proposals          # List pending proposals
GET  /api/v1/pms/trades/proposals/{id}     # Get proposal detail
POST /api/v1/pms/trades/proposals/{id}/decide  # Approve/Reject/Modify
GET  /api/v1/pms/trades/history            # Historical proposals
```

---

## 13. Decision Journal & Audit Trail

### 13.1 Purpose

Every decision is recorded immutably:
- **OPEN** a position
- **CLOSE** a position
- **MODIFY** an existing position
- **REJECT** a trade proposal

### 13.2 Journal Entry Structure

| Field | Description |
|---|---|
| `entry_id` | UUID |
| `decision_type` | OPEN, CLOSE, MODIFY, REJECT |
| `instrument` | Ticker / instrument name |
| `direction` | LONG or SHORT |
| `manager_thesis` | PM's written rationale |
| `target_price` | Expected target |
| `stop_loss` | Maximum loss level |
| `time_horizon` | Expected holding period |
| `macro_snapshot` | Snapshot of key indicators at decision time |
| `portfolio_snapshot` | Portfolio state at decision time |
| `risk_snapshot` | VaR, leverage, concentration at decision time |
| `hash_checksum` | SHA-256 hash for immutability verification |
| `locked` | Boolean — locked after creation |

### 13.3 Ex-Post Review

After a position is closed, the journal entry is enriched with:
- Realized P&L
- Holding period
- Outcome vs. thesis
- Lessons learned (PM narrative)

### 13.4 API Endpoints

```
GET  /api/v1/pms/journal/entries          # List journal entries
GET  /api/v1/pms/journal/entries/{id}     # Get entry detail
POST /api/v1/pms/journal/entry            # Create new entry
GET  /api/v1/pms/journal/stats            # Aggregated decision statistics
```

---

## 14. Emergency Stop Procedure

### 14.1 Philosophy

> "In a genuine crisis, automatic liquidation can amplify losses (bad fills, liquidity shocks). The emergency stop ensures the human has full visibility and control."

The system **does NOT** automatically close positions. It:
1. **MARKS** all positions for urgent close with priority ranking
2. **FREEZES** new proposal generation
3. **ALERTS** the portfolio manager with a detailed position report

### 14.2 Procedure

```
┌──────────────────────────────────────────────────────────┐
│                    EMERGENCY STOP                         │
│                                                           │
│  STEP 1: Trigger emergency stop                          │
│          POST /api/v1/compliance/emergency-stop           │
│                                                           │
│  STEP 2: System response:                                │
│          ✓ All proposals FROZEN                           │
│          ✓ All positions MARKED for close                 │
│          ✓ Priority ranking generated                     │
│          ✓ Alert sent to PM + risk team                   │
│                                                           │
│  STEP 3: PM reviews position report:                     │
│          - Each position listed with:                     │
│            · Instrument, direction, notional              │
│            · Unrealized P&L                               │
│            · Close priority (1 = highest)                 │
│            · Suggested action                             │
│                                                           │
│  STEP 4: PM manually closes positions                    │
│          - In priority order                              │
│          - Each close logged in Decision Journal          │
│                                                           │
│  STEP 5: PM confirms all-clear                           │
│          POST /api/v1/compliance/emergency-stop/clear     │
│          - System resumes normal operations               │
│          - Incident report auto-generated                 │
└──────────────────────────────────────────────────────────┘
```

### 14.3 Trigger Conditions

Emergency stop should be triggered when:
- Portfolio drawdown exceeds maximum threshold
- Multiple risk limits breached simultaneously
- Market dislocation event (flash crash, liquidity crisis)
- Data quality catastrophic failure (wrong prices feeding models)
- System integrity concern (suspected erroneous signals)

---

## 15. Monitoring & Alerting

### 15.1 Grafana Dashboards

Access at `http://<server>:3000` (default: admin / macro_grafana)

| Dashboard | Metrics |
|---|---|
| **Pipeline Health** | Step durations, success/failure rates, data freshness |
| **VaR Trends** | Historical VaR 95/99%, CVaR, component VaR |
| **Portfolio Overview** | Leverage, exposure, P&L, position count |
| **Data Quality** | Completeness scores, stale series, outlier counts |
| **System Health** | DB connections, Redis memory, API latency |

### 15.2 Alert Rules

Located in `src/monitoring/alert_rules.py`:

| Alert | Condition | Severity |
|---|---|---|
| VaR Breach | VaR 95% > limit | CRITICAL |
| Leverage Breach | Gross leverage > 5x | CRITICAL |
| Drawdown Warning | Drawdown > 5% | HIGH |
| Data Staleness | Key series > 2 hours stale | MEDIUM |
| Pipeline Failure | Any step fails | HIGH |
| API Latency | P99 > 5 seconds | MEDIUM |
| Disk Usage | > 80% | LOW |

### 15.3 WebSocket Real-Time Feed

```
ws://<server>:8000/ws/portfolio    # Live portfolio updates
ws://<server>:8000/ws/risk         # Real-time risk metrics
ws://<server>:8000/ws/signals      # Signal changes
ws://<server>:8000/ws/alerts       # Alert notifications
```

---

## 16. Backup & Disaster Recovery

### 16.1 Backup Procedure

```bash
# Run database backup
make backup
# Invokes: scripts/backup.sh
# Creates: backups/<timestamp>/macro_trading_<timestamp>.pgdump
```

### 16.2 Restore Procedure

```bash
# Restore from backup file
make restore FILE=backups/2026-03-01_1800/macro_trading_2026-03-01_1800.pgdump
# Invokes: scripts/restore.sh
```

### 16.3 Backup Schedule (Recommended)

| Frequency | Type | Retention |
|---|---|---|
| **Hourly** | TimescaleDB continuous aggregate refresh | N/A |
| **Daily** | Full `pg_dump` of TimescaleDB | 30 days |
| **Daily** | MongoDB `mongodump` | 30 days |
| **Weekly** | Full system backup (all volumes) | 90 days |
| **Monthly** | Offsite backup to MinIO/S3 | 1 year |

### 16.4 Disaster Recovery Priority

| Priority | Service | RTO | RPO |
|---|---|---|---|
| 1 | TimescaleDB (positions, signals) | 30 min | 1 hour |
| 2 | Redis (cache — can be rebuilt) | 15 min | N/A |
| 3 | MongoDB (NLP corpus) | 1 hour | 24 hours |
| 4 | Grafana (dashboards) | 2 hours | 24 hours |

---

## 17. API Reference Summary

### 17.1 Base URL

```
http://<server>:8000
```

### 17.2 Documentation

- **Swagger UI**: `http://<server>:8000/docs`
- **ReDoc**: `http://<server>:8000/redoc`

### 17.3 Endpoint Groups

| Group | Prefix | Description |
|---|---|---|
| **Health** | `/health` | Health checks, data status |
| **Macro** | `/api/v1/macro` | Macroeconomic series |
| **Curves** | `/api/v1/curves` | Yield curves, DI, cupom |
| **Market Data** | `/api/v1/market-data` | Prices, indices |
| **Flows** | `/api/v1/flows` | Capital flows, positioning |
| **Agents** | `/api/v1/agents` | Agent reports, signals |
| **Signals** | `/api/v1/signals` | Aggregated trading signals |
| **Strategies** | `/api/v1/strategies` | Strategy management |
| **Portfolio** | `/api/v1/portfolio` | Portfolio construction |
| **Risk** | `/api/v1/risk` | VaR, stress tests |
| **Backtest** | `/api/v1/backtests` | Strategy backtesting |
| **Reports** | `/api/v1/reports` | Daily reports |
| **Monitoring** | `/api/v1/monitoring` | System monitoring |
| **Auth** | `/api/v1/auth` | JWT authentication |
| **PMS Portfolio** | `/api/v1/pms/portfolio` | Position book |
| **PMS Trades** | `/api/v1/pms/trades` | Trade proposals |
| **PMS Journal** | `/api/v1/pms/journal` | Decision journal |
| **PMS Briefing** | `/api/v1/pms/briefing` | Morning pack |
| **PMS Risk** | `/api/v1/pms/risk` | Risk monitor |
| **PMS Attribution** | `/api/v1/pms/attribution` | P&L attribution |
| **PMS Pipeline** | `/api/v1/pms/pipeline` | Pipeline operations |
| **Dashboard** | `/dashboard` | HTML dashboard |
| **WebSocket** | `/ws/*` | Real-time channels |

### 17.4 Authentication

JWT-based authentication:
```
POST /api/v1/auth/login    → Returns JWT token
Authorization: Bearer <token>   → Use in subsequent requests
```

### 17.5 Rate Limiting

Default: **100 requests per minute** per IP address (configurable via SlowAPI).

---

## 18. Troubleshooting Guide

### 18.1 Service Won't Start

| Symptom | Likely Cause | Fix |
|---|---|---|
| TimescaleDB fails to start | Missing `POSTGRES_PASSWORD` | Set in `.env` file |
| Redis connection refused | Wrong password | Check `REDIS_PASSWORD` in `.env` |
| MongoDB auth failure | Wrong credentials | Check `MONGO_USER`/`MONGO_PASSWORD` |
| API fails to start | DB not ready | Wait for healthcheck: `make ps` |
| Port already in use | Another process | `lsof -i :<port>` and kill |

### 18.2 Pipeline Failures

| Symptom | Likely Cause | Fix |
|---|---|---|
| FRED connector fails | Invalid API key | Update `FRED_API_KEY` in `.env` |
| BCB connector timeout | Rate limiting | Wait 5 min, retry |
| Quality checks fail | Stale data | Run `make backfill-fast` |
| Agent errors | Missing features | Check data availability for date range |
| Risk engine NaN | Insufficient history | Need 756 days for VaR calculation |

### 18.3 Database Issues

```bash
# Open direct database shell
make psql

# Check table sizes
SELECT tablename, pg_size_pretty(pg_total_relation_size(quote_ident(tablename)))
FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(quote_ident(tablename)) DESC;

# Check hypertable compression
SELECT * FROM timescaledb_information.compressed_hypertable_stats;

# Run migrations
make migrate
```

### 18.4 Common Commands

```bash
# Check system health
curl http://localhost:8000/health

# Check data status
curl http://localhost:8000/health/data-status

# View API docs
open http://localhost:8000/docs

# Check Docker logs for a specific service
docker logs macro_timescaledb --tail 100
docker logs macro_api --tail 100

# Restart a single service
docker compose restart api

# Full system restart
make down && make up && make migrate
```

---

## Appendix A: Make Commands Quick Reference

| Command | Description |
|---|---|
| `make setup` | First-time setup (copy .env, install deps, pull images) |
| `make up` | Start core services |
| `make up-full` | Start all services (including Kafka) |
| `make down` | Stop all services (keep data) |
| `make down-clean` | Stop all services and delete data volumes |
| `make ps` | Show running services |
| `make logs` | Follow service logs |
| `make migrate` | Run database migrations |
| `make seed` | Seed reference data |
| `make backfill` | Full historical backfill (from 2010) |
| `make backfill-fast` | Fast backfill (key sources, from 2020) |
| `make daily` | Run daily pipeline |
| `make daily-dry` | Dry-run daily pipeline |
| `make daily-date DATE=YYYY-MM-DD` | Run pipeline for specific date |
| `make api` | Start FastAPI server (dev mode) |
| `make test` | Run test suite |
| `make test-all` | Run all tests with coverage |
| `make lint` | Run linter |
| `make verify` | Full infrastructure verification |
| `make verify-pms` | PMS verification |
| `make verify-all` | Complete system verification |
| `make dagster` | Start Dagster UI + daemon |
| `make dagster-run-all` | Materialize all Dagster assets |
| `make backup` | Database backup |
| `make restore FILE=<path>` | Database restore |
| `make morning-pack` | Generate morning pack manually |
| `make psql` | Open database shell |
| `make quality` | Run data quality checks |
| `make pms-dev` | Start PMS development (Docker + API) |

---

## Appendix B: Database Schema Reference

### Hypertables (Time Series — TimescaleDB)

| Table | Time Column | Key Columns | Purpose |
|---|---|---|---|
| `prices` | `timestamp` | instrument_id, open, high, low, close, volume | Market OHLCV data |
| `curves` | `reference_date` | curve_type, tenor, rate, dv01 | Yield curves (DI, cupom, Treasury) |
| `vol_surfaces` | `timestamp` | instrument_id, expiry, strike, delta, vol | Options volatility surfaces |
| `macro_series` | `reference_date` | series_code, value, release_time | Macroeconomic data (IPCA, SELIC, CPI) |
| `position_pnl_history` | `date` | position_id, price, unrealized_pnl, daily_pnl | Position P&L tracking |

### Regular Tables

| Table | Purpose |
|---|---|
| `instruments` | Master instrument catalog (ticker, asset class, specs) |
| `series_metadata` | Metadata for macro series (source, frequency, unit) |
| `data_sources` | Data provider registry and SLA tracking |
| `agent_reports` | Audit trail for agent runs |
| `signals` | Generated signals with metadata |
| `strategy_state` | Strategy configuration and state |
| `backtest_results` | Backtest results with equity curves |
| `portfolio_positions` | Live position book |
| `trade_proposals` | System trade ideas and workflow |
| `decision_journal` | Immutable decision audit log |
| `daily_briefings` | Morning pack archives |
| `portfolio_state` | End-of-day portfolio snapshots |
| `pipeline_runs` | Pipeline run metadata and timings |
| `nlp_documents` | Central bank communication metadata |

---

## Appendix C: Data Source Catalog

### Brazil — Monetary & Inflation

| Series | Source | Frequency | Connector |
|---|---|---|---|
| SELIC target | BCB SGS (432) | Meeting dates | `bcb_sgs` |
| SELIC effective | BCB SGS (4189) | Daily | `bcb_sgs` |
| CDI | BCB SGS (12) | Daily | `bcb_sgs` |
| IPCA (headline) | IBGE | Monthly | `ibge_sidra` |
| IPCA (groups) | IBGE | Monthly | `ibge_sidra` |
| IPCA-15 | IBGE | Monthly | `ibge_sidra` |
| Focus expectations | BCB Focus | Weekly | `bcb_focus` |
| COPOM minutes | BCB | Meeting dates | NLP scraper |

### Brazil — Activity & Labor

| Series | Source | Frequency | Connector |
|---|---|---|---|
| GDP | IBGE | Quarterly | `ibge_sidra` |
| IBC-Br | BCB SGS | Monthly | `bcb_sgs` |
| Industrial production | IBGE | Monthly | `ibge_sidra` |
| Retail sales | IBGE | Monthly | `ibge_sidra` |
| Unemployment rate | IBGE | Monthly | `ibge_sidra` |
| CAGED (formal employment) | BCB SGS | Monthly | `bcb_sgs` |

### Brazil — External & Fiscal

| Series | Source | Frequency | Connector |
|---|---|---|---|
| PTAX (USDBRL) | BCB | Daily | `bcb_ptax` |
| FX flows | BCB | Daily | `bcb_fx_flow` |
| Trade balance | BCB SGS | Monthly | `bcb_sgs` |
| Current account | BCB SGS | Monthly | `bcb_sgs` |
| International reserves | BCB SGS | Daily | `bcb_sgs` |
| Primary fiscal balance | STN | Monthly | `stn_fiscal` |
| Gross debt / GDP | BCB SGS | Monthly | `bcb_sgs` |

### Brazil — Market Data

| Series | Source | Frequency | Connector |
|---|---|---|---|
| DI futures curve (30+ tenors) | B3 / TE | Daily | `b3_market_data` / `te_di_curve` |
| Cupom cambial | B3 | Daily | `b3_market_data` |
| NTN-B rates (ANBIMA) | ANBIMA | Daily | `anbima` |
| Ibovespa | Yahoo | Daily | `yahoo_finance` |
| Brazil CDS 5Y | Yahoo / FMP | Daily | `yahoo_finance` |

### United States — Macro

| Series | Source | Frequency | Connector |
|---|---|---|---|
| CPI (headline/core) | FRED | Monthly | `fred` |
| PCE (headline/core) | FRED | Monthly | `fred` |
| Nonfarm payrolls | FRED | Monthly | `fred` |
| Unemployment (U3/U6) | FRED | Monthly | `fred` |
| GDP | FRED | Quarterly | `fred` |
| Retail sales | FRED | Monthly | `fred` |
| ISM Manufacturing | FRED | Monthly | `fred` |
| FOMC statements/minutes | Fed | Meeting dates | NLP scraper |

### United States — Market Data

| Series | Source | Frequency | Connector |
|---|---|---|---|
| Treasury curve (2Y-30Y) | Treasury.gov / FMP | Daily | `treasury_gov` / `fmp_treasury` |
| TIPS rates | FRED | Daily | `fred` |
| Fed Funds rate | FRED | Daily | `fred` |
| SOFR | FRED | Daily | `fred` |
| S&P 500 | Yahoo | Daily | `yahoo_finance` |
| VIX | Yahoo | Daily | `yahoo_finance` |
| DXY | Yahoo | Daily | `yahoo_finance` |

### Global — Flows & Positioning

| Series | Source | Frequency | Connector |
|---|---|---|---|
| CFTC Commitment of Traders | CFTC | Weekly | `cftc_cot` |
| OECD macro indicators | OECD | Monthly/Quarterly | `oecd_sdmx` |

### Commodities

| Series | Source | Frequency | Connector |
|---|---|---|---|
| Iron ore | Yahoo | Daily | `yahoo_finance` |
| Soybean | Yahoo | Daily | `yahoo_finance` |
| Corn | Yahoo | Daily | `yahoo_finance` |
| WTI Crude | Yahoo | Daily | `yahoo_finance` |
| Brent Crude | Yahoo | Daily | `yahoo_finance` |
| Gold | Yahoo | Daily | `yahoo_finance` |
| Copper | Yahoo | Daily | `yahoo_finance` |

---

> **Document Control**
> This SOP should be reviewed and updated quarterly or after any significant system change.
> For questions, contact the Portfolio Management Technology team.
