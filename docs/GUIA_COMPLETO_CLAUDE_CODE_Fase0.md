# ════════════════════════════════════════════════════════════════════
# MACRO HEDGE FUND AI SYSTEM — GUIA COMPLETO CLAUDE CODE
# ════════════════════════════════════════════════════════════════════
# FASE 0: INFRAESTRUTURA DE DADOS (15 ETAPAS)
# ════════════════════════════════════════════════════════════════════
#
# COMO USAR:
# 1. Cada ETAPA é um prompt independente para o Claude Code
# 2. Copie o bloco entre as linhas "═══ INÍCIO DO PROMPT ═══" e "═══ FIM DO PROMPT ═══"
# 3. Cole no Claude Code e aguarde execução completa
# 4. Valide o resultado antes de ir para a próxima etapa
# 5. Se houver erro, cole o erro no Claude Code e peça correção
#
# PRÉ-REQUISITOS:
# - Docker + Docker Compose instalados
# - Python 3.11+ instalado
# - Node.js 18+ instalado
# - Git instalado
# - 16GB+ RAM, 50GB+ disco livre
# - API key FRED (grátis: https://fred.stlouisfed.org/docs/api/api_key.html)
#
# TEMPO TOTAL ESTIMADO: 6-10 horas de trabalho
# ════════════════════════════════════════════════════════════════════


################################################################################
##                                                                            ##
##  ETAPA 1 — SCAFFOLD DO PROJETO & DOCKER COMPOSE                           ##
##  Tempo: ~20 min | Cria a estrutura completa do monorepo                    ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 1 ═══

Estou construindo um sistema de trading agêntico para um global macro hedge fund focado em Brasil e EUA. O sistema terá ~25 estratégias operando FX, juros, inflação, cupom cambial e risco soberano, alimentadas por agentes de IA especializados (Inflation Agent, Monetary Policy Agent, Fiscal Agent, FX Equilibrium Agent, Cross-Asset Agent).

Nesta primeira etapa, preciso que você crie a estrutura completa do projeto. Siga estas instruções com precisão:

## 1. Crie o monorepo `macro-fund-system` com esta estrutura:

```
macro-fund-system/
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── alembic.ini
│
├── infrastructure/
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── .gitkeep
│   └── scripts/
│       ├── init_timescaledb.sql
│       └── init_kafka_topics.sh
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── redis_client.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── instruments.py
│   │   │   ├── market_data.py
│   │   │   ├── curves.py
│   │   │   ├── macro_series.py
│   │   │   ├── vol_surfaces.py
│   │   │   ├── fiscal_data.py
│   │   │   ├── flow_data.py
│   │   │   ├── signals.py
│   │   │   └── series_metadata.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── common.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── date_utils.py
│   │       ├── logging_config.py
│   │       └── retry.py
│   │
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── bcb_sgs.py
│   │   ├── bcb_focus.py
│   │   ├── bcb_ptax.py
│   │   ├── bcb_fx_flow.py
│   │   ├── b3_market_data.py
│   │   ├── anbima.py
│   │   ├── ibge_sidra.py
│   │   ├── stn_fiscal.py
│   │   ├── fred.py
│   │   ├── treasury_gov.py
│   │   ├── cftc_cot.py
│   │   ├── yahoo_finance.py
│   │   └── commodities.py
│   │
│   ├── transforms/
│   │   ├── __init__.py
│   │   ├── curves.py
│   │   ├── returns.py
│   │   ├── macro.py
│   │   └── vol_surface.py
│   │
│   ├── quality/
│   │   ├── __init__.py
│   │   ├── checks.py
│   │   └── alerts.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── deps.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py
│   │       ├── market_data.py
│   │       ├── curves.py
│   │       ├── macro.py
│   │       └── flows.py
│   │
│   ├── agents/
│   │   └── __init__.py
│   ├── strategies/
│   │   └── __init__.py
│   └── risk/
│       └── __init__.py
│
├── scripts/
│   ├── seed_instruments.py
│   ├── seed_series_metadata.py
│   ├── backfill.py
│   └── verify_infrastructure.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_connectors/
│   │   ├── __init__.py
│   │   └── test_bcb_sgs.py
│   └── test_transforms/
│       ├── __init__.py
│       └── test_curves.py
│
└── notebooks/
    ├── exploration/
    └── backtests/
```

## 2. docker-compose.yml com estes serviços:

**timescaledb:**
- Image: `timescale/timescaledb:latest-pg16`
- Port: 5432
- Environment: POSTGRES_DB=macrofund, POSTGRES_USER=macrofund, POSTGRES_PASSWORD=macrofund_dev
- Volume persistente: `timescaledb_data:/var/lib/postgresql/data`
- Health check: `pg_isready -U macrofund`

**redis:**
- Image: `redis:7-alpine`
- Port: 6379
- Volume persistente: `redis_data:/data`
- Command: `redis-server --appendonly yes`

**mongodb:**
- Image: `mongo:7`
- Port: 27017
- Environment: MONGO_INITDB_ROOT_USERNAME=macrofund, MONGO_INITDB_ROOT_PASSWORD=macrofund_dev
- Volume persistente: `mongodb_data:/data/db`

**zookeeper:**
- Image: `confluentinc/cp-zookeeper:7.6.0`
- Port: 2181
- Environment: ZOOKEEPER_CLIENT_PORT=2181

**kafka:**
- Image: `confluentinc/cp-kafka:7.6.0`
- Port: 9092
- Depends on: zookeeper
- Environment: KAFKA_BROKER_ID=1, KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181, KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092, KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1

**minio:**
- Image: `minio/minio:latest`
- Ports: 9000 (API), 9001 (console)
- Command: `server /data --console-address ":9001"`
- Volume persistente: `minio_data:/data`

Declare todos os volumes no final do docker-compose.yml.

## 3. .env.example:

```env
# Database
DATABASE_URL=postgresql+asyncpg://macrofund:macrofund_dev@localhost:5432/macrofund
DATABASE_URL_SYNC=postgresql://macrofund:macrofund_dev@localhost:5432/macrofund

# Redis
REDIS_URL=redis://localhost:6379/0

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# MongoDB
MONGODB_URL=mongodb://macrofund:macrofund_dev@localhost:27017

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=macrofund
MINIO_SECRET_KEY=macrofund_dev_secret

# Data Providers
FRED_API_KEY=your_fred_api_key_here
BCB_SGS_BASE_URL=https://api.bcb.gov.br/dados/serie/bcdata.sgs
FRED_BASE_URL=https://api.stlouisfed.org/fred

# Application
LOG_LEVEL=INFO
ENVIRONMENT=development
```

## 4. pyproject.toml com dependências:

```toml
[project]
name = "macro-fund-system"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "psycopg2-binary>=2.9",
    "alembic>=1.13",
    "pydantic>=2.5",
    "pydantic-settings>=2.1",
    "fastapi>=0.109",
    "uvicorn[standard]>=0.27",
    "httpx>=0.26",
    "pandas>=2.1",
    "numpy>=1.26",
    "polars>=0.20",
    "redis>=5.0",
    "structlog>=24.1",
    "python-dotenv>=1.0",
    "tenacity>=8.2",
    "beautifulsoup4>=4.12",
    "lxml>=5.1",
    "openpyxl>=3.1",
    "yfinance>=0.2",
    "scipy>=1.12",
    "aiohttp>=3.9",
    "python-dateutil>=2.8",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "ruff>=0.2",
    "respx>=0.20",
]
```

## 5. Makefile com targets:

```makefile
.PHONY: setup up down migrate seed backfill test lint api psql verify

setup:
	cp -n .env.example .env || true
	pip install -e ".[dev]"
	docker compose pull

up:
	docker compose up -d
	@echo "Waiting for services..."
	@sleep 5
	@docker compose ps

down:
	docker compose down

migrate:
	alembic upgrade head

seed:
	python scripts/seed_instruments.py
	python scripts/seed_series_metadata.py

backfill:
	python scripts/backfill.py --source all --start-date 2010-01-01

backfill-fast:
	python scripts/backfill.py --source bcb_sgs,fred,yahoo --start-date 2020-01-01

test:
	pytest tests/ -v --cov=src

lint:
	ruff check src/

api:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

psql:
	docker exec -it macro-fund-system-timescaledb-1 psql -U macrofund

verify:
	python scripts/verify_infrastructure.py

quality:
	python -c "from src.quality.checks import run_all_checks; run_all_checks()"
```

## 6. config.py usando pydantic-settings:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str
    database_url_sync: str
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    # MongoDB
    mongodb_url: str = "mongodb://macrofund:macrofund_dev@localhost:27017"
    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "macrofund"
    minio_secret_key: str = "macrofund_dev_secret"
    # Data Providers
    fred_api_key: str = ""
    bcb_sgs_base_url: str = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"
    fred_base_url: str = "https://api.stlouisfed.org/fred"
    # App
    log_level: str = "INFO"
    environment: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

## 7. database.py:

SQLAlchemy 2.0 com async engine (asyncpg) e sync engine (psycopg2). Session factory para ambos. Context managers para uso em `async with get_async_session() as session:`.

## 8. redis_client.py:

Redis client singleton usando redis-py com connection pool.

## 9. README.md:

Documentação clara com: descrição do projeto, Quick Start (clone, setup, up, migrate, seed, backfill, api), arquitetura de alto nível, lista de serviços Docker.

## 10. .gitignore:

Python, Node, Docker, .env, __pycache__, .pytest_cache, *.pyc, .venv, notebooks/.ipynb_checkpoints, data/, *.log

Crie TODOS os arquivos com conteúdo funcional. Todos os __init__.py devem existir. Use type hints em todos os arquivos Python. Use async/await onde aplicável. Garanta que todos os imports estejam corretos.

═══ FIM DO PROMPT 1 ═══

# VERIFICAÇÃO PÓS-ETAPA 1:
# □ Todos os diretórios foram criados
# □ docker-compose.yml tem 6 serviços
# □ .env.example tem todas as variáveis
# □ pyproject.toml tem todas as dependências
# □ Executar: docker compose up -d && docker compose ps (todos healthy)


################################################################################
##                                                                            ##
##  ETAPA 2 — SQLALCHEMY MODELS + ALEMBIC MIGRATIONS + TIMESCALEDB           ##
##  Tempo: ~25 min | Cria todos os schemas do banco de dados                  ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 2 ═══

No projeto macro-fund-system, implemente todos os SQLAlchemy ORM models e a migration Alembic com TimescaleDB. Use SQLAlchemy 2.0 mapped_column style.

## MODELS — Implemente cada arquivo em src/core/models/:

### base.py
DeclarativeBase com UUID mixin, timestamp mixin (created_at, updated_at).

### instruments.py — Tabela `instruments`
```
id: UUID, PK, server_default=gen_random_uuid()
ticker: String(50), unique, not null, indexed
name: String(200)
asset_class: String(30) — valores: FX, RATES_BR, RATES_US, RATES_G5, INFLATION_BR, INFLATION_US, CUPOM_CAMBIAL, SOVEREIGN_CREDIT, COMMODITIES, EQUITY_INDEX, MONEY_MARKET
instrument_type: String(20) — valores: FUTURE, BOND, SWAP, OPTION, CDS, NDF, SPOT, INDEX, ETF, FRA
currency: String(3), not null
exchange: String(20) — B3, CME, EUREX, ICE, OTC, BCB
maturity_date: Date, nullable
contract_specs: JSON, nullable (multiplier, tick_size, margin, settlement_type)
is_active: Boolean, default True
created_at: DateTime(timezone=True), server_default=now()
updated_at: DateTime(timezone=True), onupdate=now()
```

### market_data.py — Tabela `market_data` (hypertable)
```
time: DateTime(timezone=True), PK part 1, NOT NULL
instrument_id: UUID, FK instruments.id, PK part 2
open: Float, nullable
high: Float, nullable
low: Float, nullable
close: Float, NOT NULL
volume: BigInteger, nullable
open_interest: BigInteger, nullable
bid: Float, nullable
ask: Float, nullable
source: String(50), NOT NULL
ingestion_time: DateTime(timezone=True), server_default=now()
```
Composite PK: (time, instrument_id). Index: (instrument_id, time DESC).

### curves.py — Tabela `curves` (hypertable)
```
time: DateTime(timezone=True), PK part 1
curve_id: String(30), PK part 2 — valores: DI_PRE, DDI_CUPOM, NTN_B_REAL, UST_NOM, UST_REAL, UST_BEI
tenor: String(10), PK part 3 — valores: 1M, 2M, 3M, 6M, 9M, 1Y, 18M, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y
tenor_days: Integer, NOT NULL
rate: Float, NOT NULL (decimal: 0.1350 = 13.50%)
dv01: Float, nullable
source: String(50), NOT NULL
ingestion_time: DateTime(timezone=True), server_default=now()
```
Index: (curve_id, time DESC).

### macro_series.py — Tabela `macro_series` (hypertable)
```
time: DateTime(timezone=True), PK part 1 (reference period)
series_id: String(50), PK part 2
value: Float, NOT NULL
release_time: DateTime(timezone=True), NOT NULL (when published — CRITICAL for point-in-time)
revision_number: Integer, default 0, PK part 3
source: String(50), NOT NULL
ingestion_time: DateTime(timezone=True), server_default=now()
```
Index: (series_id, time DESC).

### vol_surfaces.py — Tabela `vol_surfaces` (hypertable)
```
time: DateTime(timezone=True), PK part 1
underlying: String(20), PK part 2 (USDBRL, DI, EURUSD)
expiry: Date, PK part 3
strike_type: String(15) — DELTA, ABSOLUTE, MONEYNESS
strike_value: Float, PK part 4
call_put: String(10) — CALL, PUT, STRADDLE
implied_vol: Float, NOT NULL
source: String(50), NOT NULL
ingestion_time: DateTime(timezone=True), server_default=now()
```

### fiscal_data.py — Tabela `fiscal_data` (hypertable)
```
time: DateTime(timezone=True), PK part 1
series_id: String(50), PK part 2
value: Float, NOT NULL
release_time: DateTime(timezone=True), nullable
source: String(50), NOT NULL
metadata_json: JSON, nullable
ingestion_time: DateTime(timezone=True), server_default=now()
```

### flow_data.py — Tabela `flow_data` (hypertable)
```
time: DateTime(timezone=True), PK part 1
series_id: String(50), PK part 2
value: Float, NOT NULL
release_time: DateTime(timezone=True), nullable
source: String(50), NOT NULL
ingestion_time: DateTime(timezone=True), server_default=now()
```

### signals.py — Tabela `signals` (hypertable)
```
time: DateTime(timezone=True), PK part 1
signal_id: String(50), PK part 2
value: Float, NOT NULL
confidence: Float, nullable (0.0 to 1.0)
metadata_json: JSON, nullable
agent_id: String(30), nullable
ingestion_time: DateTime(timezone=True), server_default=now()
```

### series_metadata.py — Tabela `series_metadata`
```
series_id: String(50), PK
name: String(200), NOT NULL
description: Text, nullable
country: String(3) — BRA, USA, EUR, GBR, JPN, CHE
category: String(30) — INFLATION, ACTIVITY, LABOR, MONETARY, FISCAL, EXTERNAL, FLOW, POSITIONING, CREDIT, SENTIMENT
frequency: String(15) — TICK, DAILY, WEEKLY, BIWEEKLY, MONTHLY, QUARTERLY, ANNUAL
unit: String(30) — percent, index, brl_millions, usd_billions, ratio, level, rate
seasonal_adjustment: Boolean, default False
source_provider: String(50) — BCB_SGS, FRED, IBGE, ANBIMA, B3, STN, CFTC, TREASURY_GOV, YAHOO
source_code: String(100) — e.g., "SGS #433", "FRED CPIAUCSL"
expected_release_lag_days: Integer, nullable
is_revised: Boolean, default False
created_at: DateTime(timezone=True), server_default=now()
```

### __init__.py:
Import ALL models so Alembic autogenerate can detect them.

## ALEMBIC SETUP:

1. Configure alembic.ini to read DATABASE_URL_SYNC from .env
2. Configure env.py to import all models from src.core.models
3. Generate initial migration with `alembic revision --autogenerate -m "initial_schema"`

## TIMESCALEDB SETUP:

After the Alembic table creation, the migration must execute raw SQL:

```sql
-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Convert to hypertables
SELECT create_hypertable('market_data', 'time', chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE);
SELECT create_hypertable('curves', 'time', chunk_time_interval => INTERVAL '3 months', if_not_exists => TRUE);
SELECT create_hypertable('macro_series', 'time', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);
SELECT create_hypertable('vol_surfaces', 'time', chunk_time_interval => INTERVAL '3 months', if_not_exists => TRUE);
SELECT create_hypertable('fiscal_data', 'time', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);
SELECT create_hypertable('flow_data', 'time', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);
SELECT create_hypertable('signals', 'time', chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE);

-- Compression policies
ALTER TABLE market_data SET (timescaledb.compress, timescaledb.compress_segmentby = 'instrument_id', timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('market_data', INTERVAL '30 days');

ALTER TABLE curves SET (timescaledb.compress, timescaledb.compress_segmentby = 'curve_id', timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('curves', INTERVAL '90 days');

ALTER TABLE macro_series SET (timescaledb.compress, timescaledb.compress_segmentby = 'series_id', timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('macro_series', INTERVAL '365 days');

ALTER TABLE vol_surfaces SET (timescaledb.compress, timescaledb.compress_segmentby = 'underlying', timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('vol_surfaces', INTERVAL '90 days');

ALTER TABLE fiscal_data SET (timescaledb.compress, timescaledb.compress_segmentby = 'series_id', timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('fiscal_data', INTERVAL '365 days');

ALTER TABLE flow_data SET (timescaledb.compress, timescaledb.compress_segmentby = 'series_id', timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('flow_data', INTERVAL '365 days');

ALTER TABLE signals SET (timescaledb.compress, timescaledb.compress_segmentby = 'signal_id', timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('signals', INTERVAL '30 days');
```

Put this SQL in the upgrade() function of the migration using op.execute() AFTER the table creation.

The downgrade() should drop all tables in reverse dependency order.

═══ FIM DO PROMPT 2 ═══

# VERIFICAÇÃO PÓS-ETAPA 2:
# □ Executar: make migrate (ou alembic upgrade head)
# □ Executar: make psql
# □ No psql: \dt (listar tabelas — deve ter 9 tabelas)
# □ No psql: SELECT * FROM timescaledb_information.hypertables; (deve ter 7)
# □ No psql: SELECT * FROM timescaledb_information.compression_settings; (deve ter 7)


################################################################################
##                                                                            ##
##  ETAPA 3 — BASE CONNECTOR + UTILITIES                                     ##
##  Tempo: ~15 min | Classe abstrata para todos os conectores de dados        ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 3 ═══

No projeto macro-fund-system, implemente as classes base e utilitários que todos os conectores de dados utilizarão.

## 1. src/connectors/base.py — BaseConnector

Classe abstrata com:

**Abstract methods:**
- `async def fetch_latest(self) -> dict`: buscar dados mais recentes
- `async def fetch_historical(self, start_date: date, end_date: date) -> dict`: buscar range histórico
- `def get_series_registry(self) -> dict[str, Any]`: retornar o registry de séries deste connector

**Concrete methods:**

```python
async def _make_request(self, url: str, params: dict = None, headers: dict = None) -> dict | list:
    """HTTP GET with retry, timeout, logging. Uses httpx async."""
    # 3 attempts, exponential backoff (1s, 2s, 4s)
    # Timeout: 30 seconds
    # Log: request URL, status code, elapsed time
    # Raise on 4xx/5xx after all retries

def _save_to_db_sync(self, records: list[dict], table_name: str):
    """Bulk insert to TimescaleDB using sync engine.
    Uses INSERT ... ON CONFLICT DO NOTHING for idempotency.
    Log: number of records inserted, table name."""

def _log_ingestion(self, connector_name: str, series_count: int, records_count: int, elapsed: float):
    """Structured log: 'Ingestion complete: {connector_name} | {series_count} series | {records_count} records | {elapsed:.1f}s'"""
```

**Properties:**
- `source_name: str` — identifier (e.g., "BCB_SGS", "FRED")
- `base_url: str` — base API URL
- `rate_limit_seconds: float` — minimum seconds between requests (default 1.0)

## 2. src/core/utils/date_utils.py

```python
def get_br_holidays(year: int) -> list[date]:
    """Return all ANBIMA holidays for a given year (2015-2030).
    Include: Ano Novo, Carnaval (Mon+Tue), Sexta-Feira Santa, Tiradentes,
    Dia do Trabalho, Corpus Christi, Independência, Nossa Senhora Aparecida,
    Finados, Proclamação da República, Consciência Negra (SP), Natal,
    Dia 31/dez (bancário)."""

def get_us_holidays(year: int) -> list[date]:
    """Return all NYSE holidays for a given year (2015-2030).
    Include: New Year, MLK Day, Presidents Day, Good Friday, Memorial Day,
    Juneteenth, Independence Day, Labor Day, Thanksgiving, Christmas."""

def is_business_day(dt: date, calendar: str = 'BR') -> bool
def previous_business_day(dt: date, calendar: str = 'BR') -> date
def next_business_day(dt: date, calendar: str = 'BR') -> date
def business_days_between(start: date, end: date, calendar: str = 'BR') -> int
def tenor_to_days(tenor: str) -> int:
    """Convert tenor string to approximate days: 1M->30, 3M->90, 6M->180, 1Y->365, 2Y->730, etc."""
def tenor_to_date(tenor: str, from_date: date, calendar: str = 'BR') -> date:
    """Convert tenor to actual date using business day convention (modified following)."""
```

## 3. src/core/utils/logging_config.py

Configure structlog with:
- JSON output format
- Timestamps (ISO 8601)
- Log level from LOG_LEVEL env var
- Function: `get_logger(name: str) -> structlog.BoundLogger`

## 4. src/core/utils/retry.py

Decorator `@retry_with_backoff(max_attempts=3, base_wait=1.0)` using tenacity. Log each retry attempt with warning level.

## 5. tests/test_connectors/test_bcb_sgs.py — skeleton

Create a test file skeleton that uses pytest fixtures and respx (for httpx mocking).

## 6. tests/conftest.py

Pytest fixtures:
- `db_session`: create a test database connection (can use SQLite for unit tests or connect to the Docker TimescaleDB for integration)
- `sample_dates`: return common test date ranges

Write pytest tests for date_utils covering:
- BR holidays detection (Carnaval 2025, Corpus Christi 2025)
- US holidays detection
- business_days_between for a known range
- tenor_to_days for all standard tenors

═══ FIM DO PROMPT 3 ═══

# VERIFICAÇÃO PÓS-ETAPA 3:
# □ pytest tests/test_transforms/test_curves.py (ou o teste de date_utils) — deve passar
# □ Verificar que BaseConnector tem todos os métodos abstratos


################################################################################
##                                                                            ##
##  ETAPA 4 — CONECTOR BCB SGS (PRINCIPAL FONTE BRASIL)                      ##
##  Tempo: ~30 min | ~50 séries macroeconômicas brasileiras                   ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 4 ═══

No projeto macro-fund-system, implemente src/connectors/bcb_sgs.py — o conector para o Sistema Gerenciador de Séries Temporais do Banco Central do Brasil.

## API Info:
- Base URL: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados`
- Params: `formato=json&dataInicial=DD/MM/YYYY&dataFinal=DD/MM/YYYY`
- Response: `[{"data": "DD/MM/YYYY", "valor": "1234,56"}, ...]`
- Nota: o campo "valor" usa vírgula como separador decimal (formato brasileiro)
- Rate limit: ~200 req/min (usar 1 segundo entre requests por segurança)
- Não requer API key

## Classe BcbSgsConnector(BaseConnector)

### REGISTRY COMPLETO de séries (dict: our_series_id -> bcb_sgs_code):

```python
SERIES_REGISTRY = {
    # ══════ INFLAÇÃO ══════
    "BR_IPCA_MOM": 433,            # IPCA variação mensal (%)
    "BR_IPCA_YOY": 13522,          # IPCA acumulado 12 meses (%)
    "BR_IPCA_CORE_EX0": 11426,     # Núcleo EX0 (exclusão)
    "BR_IPCA_CORE_EX3": 27838,     # Núcleo EX3
    "BR_IPCA_CORE_MA": 11427,      # Núcleo médias aparadas
    "BR_IPCA_CORE_DP": 27839,      # Núcleo dupla ponderação
    "BR_IPCA_CORE_P55": 4466,      # Núcleo P55
    "BR_IPCA_DIFFUSION": 21379,    # Índice de difusão IPCA
    "BR_IPCA15_MOM": 7478,         # IPCA-15 variação mensal
    "BR_INPC_MOM": 188,            # INPC mensal
    "BR_IGP_M_MOM": 189,           # IGP-M mensal
    "BR_IGP_DI_MOM": 190,          # IGP-DI mensal
    "BR_IPA_M_MOM": 225,           # IPA-M mensal (atacado)
    "BR_IPC_S_WEEKLY": 7446,       # IPC-S semanal (FGV)
    "BR_IPC_FIPE_WEEKLY": 10764,   # IPC-Fipe semanal

    # ══════ ATIVIDADE ECONÔMICA ══════
    "BR_GDP_QOQ": 22099,           # PIB trimestral
    "BR_IBC_BR": 24364,            # IBC-Br (proxy mensal PIB)
    "BR_INDUSTRIAL_PROD": 21859,   # Produção industrial
    "BR_RETAIL_CORE": 1455,        # PMC varejo restrito
    "BR_RETAIL_BROAD": 28473,      # PMC varejo ampliado
    "BR_SERVICES_REV": 23987,      # PMS receita de serviços
    "BR_CONSUMER_CONF": 4393,      # ICC confiança consumidor
    "BR_BUSINESS_CONF": 7343,      # ICE confiança empresarial
    "BR_CAPACITY_UTIL": 1344,      # Utilização capacidade
    "BR_CAGED_NET": 28763,         # CAGED emprego formal
    "BR_UNEMPLOYMENT": 24369,      # PNAD desemprego

    # ══════ POLÍTICA MONETÁRIA & CRÉDITO ══════
    "BR_SELIC_TARGET": 432,        # Meta Selic
    "BR_SELIC_DAILY": 11,          # Selic efetiva diária
    "BR_CDI_DAILY": 12,            # CDI diário
    "BR_CREDIT_GDP": 20539,        # Crédito total / PIB
    "BR_DEFAULT_PF": 21082,        # Inadimplência PF
    "BR_DEFAULT_PJ": 21083,        # Inadimplência PJ
    "BR_AVG_LENDING": 20714,       # Taxa média empréstimos
    "BR_M1": 1824,                 # Base monetária M1
    "BR_M2": 1837,                 # M2
    "BR_M3": 1838,                 # M3
    "BR_M4": 1839,                 # M4
    "BR_MONETARY_BASE": 1788,      # Base monetária

    # ══════ SETOR EXTERNO ══════
    "BR_TRADE_BALANCE": 22707,     # Balança comercial (USD mi)
    "BR_CURRENT_ACCOUNT": 22885,   # Saldo transações correntes
    "BR_CA_GDP": 22918,            # Conta corrente / PIB
    "BR_FDI": 22886,               # Invest. direto no país
    "BR_PORT_EQUITY": 22888,       # Inv. carteira ações
    "BR_PORT_DEBT": 22889,         # Inv. carteira renda fixa
    "BR_RESERVES": 13621,          # Reservas internacionais (USD mi)
    "BR_PTAX_BUY": 1,              # PTAX compra
    "BR_PTAX_SELL": 10813,         # PTAX venda

    # ══════ FISCAL ══════
    "BR_PRIMARY_BALANCE": 5793,    # Resultado primário consolidado
    "BR_NOMINAL_DEFICIT": 5727,    # Resultado nominal
    "BR_NET_DEBT_GDP": 4513,       # DLSP / PIB (%)
    "BR_GROSS_DEBT_GDP": 13762,    # DBGG / PIB (%)
}
```

### MÉTODOS:

```python
async def fetch_series(self, bcb_code: int, start_date: date, end_date: date) -> list[dict]:
    """
    Fetch single series from BCB SGS.
    - URL: {base_url}.{bcb_code}/dados?formato=json&dataInicial={}&dataFinal={}
    - Parse response: convert "data" from DD/MM/YYYY to datetime
    - Parse "valor": replace '.' (thousands) with '' and ',' (decimal) with '.'
    - Handle empty responses and "valor": "-" gracefully
    - Return: [{"time": datetime, "value": float}, ...]
    """

async def fetch_all_series(self, start_date: date, end_date: date) -> dict[str, list[dict]]:
    """
    Iterate over SERIES_REGISTRY, fetch each series.
    - Sleep self.rate_limit_seconds between requests
    - Log progress: "Fetching {i}/{total}: {series_id} (SGS #{code})"
    - Skip on error, log warning, continue
    - Return: {series_id: [records]}
    """

def save_series_to_db(self, series_id: str, records: list[dict]):
    """
    Insert into macro_series table.
    - time = record time
    - series_id = our series_id
    - value = record value
    - release_time = for historical data, use time + estimated publication lag;
      for recent data (<90 days), use now()
    - revision_number = 0
    - source = "BCB_SGS"
    - ON CONFLICT (time, series_id, revision_number) DO NOTHING
    """

async def fetch_latest(self) -> dict:
    """Fetch last 60 days for all series, insert only new records."""

async def fetch_historical(self, start_date: date, end_date: date) -> dict:
    """Full historical backfill. Split into 5-year batches to avoid timeout."""
```

### ADDITIONAL:
- Add `if __name__ == "__main__":` block that fetches 3 test series (BR_SELIC_TARGET, BR_IPCA_MOM, BR_PTAX_BUY) for last 30 days and prints results
- Use the logger from logging_config
- All methods must have type hints and docstrings
- Write a test with respx mocking the BCB API response

═══ FIM DO PROMPT 4 ═══

# VERIFICAÇÃO PÓS-ETAPA 4:
# □ Executar: python -m src.connectors.bcb_sgs (deve baixar 3 séries de teste)
# □ Verificar no psql: SELECT COUNT(*) FROM macro_series WHERE source = 'BCB_SGS';


################################################################################
##                                                                            ##
##  ETAPA 5 — CONECTOR FRED (PRINCIPAL FONTE USA)                             ##
##  Tempo: ~25 min | ~50 séries macroeconômicas americanas                    ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 5 ═══

No projeto macro-fund-system, implemente src/connectors/fred.py — conector para o Federal Reserve Economic Data.

## API Info:
- Base URL: `https://api.stlouisfed.org/fred/series/observations`
- Params: `series_id={code}&api_key={key}&file_type=json&observation_start=YYYY-MM-DD&observation_end=YYYY-MM-DD`
- Response: `{"observations": [{"date": "YYYY-MM-DD", "value": "123.456"}, ...]}`
- Nota: "value" = "." quando dado é missing (tratar como None)
- Rate limit: 120 req/min
- Requer API key (env var FRED_API_KEY)

## Classe FredConnector(BaseConnector)

### REGISTRY COMPLETO:

```python
SERIES_REGISTRY = {
    # ══════ INFLATION ══════
    "US_CPI_ALL_SA": "CPIAUCSL",
    "US_CPI_ALL_NSA": "CPIAUCNS",
    "US_CPI_CORE": "CPILFESL",
    "US_CPI_TRIMMED": "TRMMEANCPIM158SFRBCLE",
    "US_CPI_MEDIAN": "MEDCPIM158SFRBCLE",
    "US_CPI_STICKY": "STICKCPIM157SFRBATL",
    "US_CPI_FLEXIBLE": "FLEXCPIM157SFRBATL",
    "US_PCE_HEADLINE": "PCEPI",
    "US_PCE_CORE": "PCEPILFE",
    "US_PPI_ALL": "PPIACO",
    "US_MICHIGAN_INF_1Y": "MICH",
    "US_BEI_5Y": "T5YIE",
    "US_BEI_10Y": "T10YIE",
    "US_FWD_INF_5Y5Y": "T5YIFR",

    # ══════ ACTIVITY & LABOR ══════
    "US_GDP_REAL": "GDPC1",
    "US_NFP_TOTAL": "PAYEMS",
    "US_NFP_PRIVATE": "USPRIV",
    "US_UNEMP_U3": "UNRATE",
    "US_UNEMP_U6": "U6RATE",
    "US_AVG_HOURLY_EARN": "CES0500000003",
    "US_JOLTS_OPENINGS": "JTSJOL",
    "US_JOLTS_QUITS": "JTSQUR",
    "US_INITIAL_CLAIMS": "ICSA",
    "US_CONT_CLAIMS": "CCSA",
    "US_INDPRO": "INDPRO",
    "US_CAP_UTIL": "TCU",
    "US_RETAIL_TOTAL": "RSAFS",
    "US_RETAIL_CONTROL": "RSFSXMV",
    "US_HOUSING_STARTS": "HOUST",
    "US_BUILDING_PERMITS": "PERMIT",
    "US_PERSONAL_INCOME": "PI",
    "US_PERSONAL_SPENDING": "PCE",
    "US_CONSUMER_SENT": "UMCSENT",
    "US_CFNAI": "CFNAI",

    # ══════ MONETARY & RATES ══════
    "US_FED_FUNDS": "DFF",
    "US_SOFR": "SOFR",
    "US_UST_2Y": "DGS2",
    "US_UST_5Y": "DGS5",
    "US_UST_10Y": "DGS10",
    "US_UST_30Y": "DGS30",
    "US_TIPS_5Y": "DFII5",
    "US_TIPS_10Y": "DFII10",
    "US_FED_TOTAL_ASSETS": "WALCL",
    "US_FED_TREASURIES": "WTREGEN",
    "US_FED_MBS": "WSHOMCB",
    "US_ON_RRP": "RRPONTSYD",
    "US_NFCI": "NFCI",

    # ══════ CREDIT ══════
    "US_HY_OAS": "BAMLH0A0HYM2",
    "US_IG_OAS": "BAMLC0A0CM",

    # ══════ FISCAL ══════
    "US_FED_DEBT": "GFDEBTN",
    "US_DEBT_GDP": "GFDEGDQ188S",
}
```

### MÉTODOS:

Mesma estrutura do BCB SGS connector:
- `async def fetch_series(self, fred_code: str, start_date: date, end_date: date) -> list[dict]`
- `async def fetch_all_series(self, start_date: date, end_date: date) -> dict`
- `def save_series_to_db(self, series_id: str, records: list[dict])` — save to macro_series table
- `async def fetch_latest(self)` — last 90 days
- `async def fetch_historical(self, start_date, end_date)` — full range (FRED supports large ranges in one request)
- `if __name__ == "__main__":` — test with US_FED_FUNDS, US_CPI_ALL_SA, US_UST_10Y

Handle FRED-specific quirks:
- "value" = "." means missing → skip record
- Some series update daily (DFF, DGS10), others monthly (CPI, NFP), others quarterly (GDP)
- For point-in-time: use FRED's `realtime_start` and `realtime_end` params if available, otherwise use heuristic release_time based on series frequency

Write tests with respx mocking.

═══ FIM DO PROMPT 5 ═══

# VERIFICAÇÃO PÓS-ETAPA 5:
# □ Editar .env com FRED_API_KEY real (obter em fred.stlouisfed.org)
# □ Executar: python -m src.connectors.fred
# □ Verificar: SELECT COUNT(*) FROM macro_series WHERE source = 'FRED';


################################################################################
##                                                                            ##
##  ETAPA 6 — BCB FOCUS (EXPECTATIVAS DE MERCADO)                            ##
##  Tempo: ~20 min | Survey semanal de projeções do mercado                   ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 6 ═══

No projeto macro-fund-system, implemente src/connectors/bcb_focus.py — conector para a pesquisa Focus do Banco Central (expectativas de mercado).

## API Info:
- Base URL: `https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/`
- Protocolo OData. Params: `$filter`, `$top`, `$skip`, `$orderby`, `$format=json`
- Sem API key
- Rate limit: conservador, 2 segundos entre requests

## Endpoints:

1. **ExpectativasMercadoAnuais** — Expectativas anuais (IPCA, Selic, PIB, Câmbio, IGP-M)
   - Filter: `Indicador eq 'IPCA' and Data ge '2020-01-01'`
   - Fields: Data, Indicador, DataReferencia, Mediana, Media, DesvioPadrao, Minimo, Maximo, numeroRespondentes

2. **ExpectativasMercadoMensais** — Expectativas mensais (IPCA mensal)
   - Filter: `Indicador eq 'IPCA' and Data ge '2020-01-01'`
   - Fields: Data, Indicador, DataReferencia (YYYY-MM format), Mediana, Media, etc.

3. **ExpectativasMercadoTop5Anuais** — Top 5 forecasters
   - Filter: `Indicador eq 'IPCA' and tipoCalculo eq 'C' and Data ge '2020-01-01'`

4. **ExpectativasMercadoSelic** — Expectativas Selic por reunião
   - Filter: `Data ge '2020-01-01'`
   - Fields: Data, Reuniao, Mediana, Media, etc.

## Classe BcbFocusConnector(BaseConnector)

### MÉTODOS:

```python
async def fetch_annual_expectations(
    self, indicator: str, start_date: date, end_date: date
) -> pd.DataFrame:
    """
    Fetch annual expectations for indicator (IPCA, Selic, PIB, Câmbio, IGP-M).
    Paginate with $top=1000 and $skip.
    Return DataFrame: [date, indicator, reference_year, median, mean, std, min, max, n_respondents]
    """

async def fetch_monthly_expectations(
    self, indicator: str, start_date: date, end_date: date
) -> pd.DataFrame:
    """Fetch monthly expectations (e.g., IPCA month-by-month forecasts)."""

async def fetch_selic_meetings(
    self, start_date: date, end_date: date
) -> pd.DataFrame:
    """Fetch Selic expectations per COPOM meeting."""

async def fetch_top5(
    self, indicator: str, calc_type: str, start_date: date, end_date: date
) -> pd.DataFrame:
    """Fetch Top-5 forecasters expectations. calc_type: 'C' (curto) or 'L' (longo)."""

async def fetch_all(self, start_date: date, end_date: date):
    """
    Fetch ALL Focus data and save to macro_series table.
    
    Series generated:
    - BR_FOCUS_IPCA_{YEAR}_MEDIAN (e.g., BR_FOCUS_IPCA_2025_MEDIAN, BR_FOCUS_IPCA_2026_MEDIAN)
    - BR_FOCUS_SELIC_{YEAR}_MEDIAN
    - BR_FOCUS_GDP_{YEAR}_MEDIAN
    - BR_FOCUS_FX_{YEAR}_MEDIAN
    - BR_FOCUS_IGPM_{YEAR}_MEDIAN
    - BR_FOCUS_IPCA_12M_MEDIAN (rolling 12-month-ahead, computed from monthly)
    - BR_FOCUS_SELIC_MTG_NEXT_MEDIAN (next meeting expectation)
    
    Each record: time = Data (publication date), value = Median,
    release_time = Data (Focus published every Monday),
    source = "BCB_FOCUS"
    """

async def fetch_latest(self):
    """Fetch last 60 days of Focus data."""

async def fetch_historical(self, start_date: date, end_date: date):
    """Full historical. Focus available from ~2001."""
```

Add `if __name__ == "__main__":` that fetches IPCA annual expectations for last 90 days.

═══ FIM DO PROMPT 6 ═══

# VERIFICAÇÃO:
# □ python -m src.connectors.bcb_focus
# □ SELECT DISTINCT series_id FROM macro_series WHERE source='BCB_FOCUS' LIMIT 20;


################################################################################
##                                                                            ##
##  ETAPA 7 — B3 / ANBIMA / TESOURO DIRETO (CURVAS E TÍTULOS)                ##
##  Tempo: ~35 min | Curvas DI, NTN-B, DOL, dados de títulos públicos        ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 7 ═══

No projeto macro-fund-system, implemente src/connectors/b3_market_data.py e src/connectors/anbima.py — conectores para dados de mercado brasileiro (curvas de juros, títulos públicos, câmbio).

Como NÃO temos Bloomberg, usaremos fontes gratuitas combinadas.

## FONTE 1: Tesouro Direto API (preços de títulos públicos)

URL JSON: `https://www.tesourodireto.com.br/json/br/com/b3/tesourodireto/service/api/treasurebond/all`
Retorna: todos os títulos com preço unitário, taxa, vencimento.
Formato: JSON array com objetos contendo TrsrBd.nm (nome), TrsrBd.mtrtyDt (vencimento), TrsrBd.untrRedVal (PU resgate), TrsrBd.anulInvstmtRate (taxa anual).

Para histórico: `https://www.tesourodireto.com.br/titulos/historico-de-precos-e-taxas.htm`
CSVs por tipo de título disponíveis para download.

## FONTE 2: BCB SGS (complementar para taxas)

Séries de swap DI x Pré por vencimento:
- SGS 7805: Swap DI x Pré 30d
- SGS 7806: Swap DI x Pré 60d
- SGS 7807: Swap DI x Pré 90d
- SGS 7808: Swap DI x Pré 120d
- SGS 7809: Swap DI x Pré 150d
- SGS 7810: Swap DI x Pré 180d
- SGS 7811: Swap DI x Pré 210d
- SGS 7812: Swap DI x Pré 240d
- SGS 7813: Swap DI x Pré 270d
- SGS 7814: Swap DI x Pré 300d
- SGS 7815: Swap DI x Pré 330d
- SGS 7816: Swap DI x Pré 360d

Estas séries são publicadas diariamente pelo BCB e representam a curva DI de forma proxy.

## FONTE 3: Yahoo Finance (USDBRL, Ibovespa)

- BRL=X: USDBRL spot
- ^BVSP: Ibovespa
- EWZ: iShares MSCI Brazil ETF

## Classe B3MarketDataConnector(BaseConnector)

```python
DI_SWAP_REGISTRY = {
    "DI_SWAP_30D": 7805,
    "DI_SWAP_60D": 7806,
    "DI_SWAP_90D": 7807,
    "DI_SWAP_120D": 7808,
    "DI_SWAP_150D": 7809,
    "DI_SWAP_180D": 7810,
    "DI_SWAP_210D": 7811,
    "DI_SWAP_240D": 7812,
    "DI_SWAP_270D": 7813,
    "DI_SWAP_300D": 7814,
    "DI_SWAP_330D": 7815,
    "DI_SWAP_360D": 7816,
}
```

### MÉTODOS:

```python
async def fetch_di_curve_from_bcb(self, start_date: date, end_date: date) -> pd.DataFrame:
    """
    Fetch all 12 swap DI x Pré series from BCB SGS.
    Construct DI_PRE curve: for each date, create curve with tenors 1M through 12M.
    Save to 'curves' table: curve_id='DI_PRE', tenor='1M' through '12M',
    tenor_days=30 through 360, rate=value/100 (BCB gives in %, we store as decimal).
    """

async def fetch_tesouro_direto_current(self) -> pd.DataFrame:
    """
    Fetch current prices/rates from Tesouro Direto JSON API.
    Extract NTN-B (Tesouro IPCA+) rates for all maturities.
    Save to 'curves' table: curve_id='NTN_B_REAL', tenor based on maturity.
    Also save LTN and NTN-F rates for nominal curve extension.
    """

async def fetch_tesouro_direto_historical(self) -> pd.DataFrame:
    """
    Download historical CSVs from Tesouro Direto.
    Parse and save to curves table for NTN-B and NTN-F.
    This gives us 10+ years of NTN-B real rate history.
    """

async def fetch_usdbrl_yahoo(self, start_date: date, end_date: date) -> pd.DataFrame:
    """
    Use yfinance to fetch USDBRL OHLCV data.
    Save to market_data table with instrument ticker='USDBRL'.
    """

async def fetch_equity_indices(self, start_date: date, end_date: date):
    """
    Fetch ^BVSP (Ibovespa), EWZ via yfinance.
    Save to market_data.
    """

def construct_breakeven_curve(self, date_val: date) -> dict:
    """
    For a given date, compute breakeven inflation = NTN-F rate - NTN-B real rate
    at matching maturities. Save to curves table: curve_id='BR_BEI'.
    """

async def fetch_latest(self):
    """Fetch last 5 trading days of all data."""

async def fetch_historical(self, start_date, end_date):
    """Full historical backfill."""
```

## Classe AnbimaConnector(BaseConnector) — Placeholder

For now, create a placeholder class that documents:
- ANBIMA ETTJ would provide more granular curve data (Nelson-Siegel parameters)
- ANBIMA NTN-B indicative rates (more precise than Tesouro Direto)
- Access requires ANBIMA membership (free registration at debentures.com.br)
- Future enhancement: implement when ANBIMA API access is obtained

For the MVP, the BCB swap series + Tesouro Direto provide adequate curve data.

═══ FIM DO PROMPT 7 ═══

# VERIFICAÇÃO:
# □ python -m src.connectors.b3_market_data (deve buscar curva DI e USDBRL)
# □ SELECT * FROM curves WHERE curve_id='DI_PRE' ORDER BY time DESC LIMIT 20;
# □ SELECT * FROM market_data WHERE instrument_id IN (SELECT id FROM instruments WHERE ticker='USDBRL') LIMIT 10;


################################################################################
##                                                                            ##
##  ETAPA 8 — IBGE SIDRA (IPCA DESAGREGADO) + STN FISCAL                     ##
##  Tempo: ~25 min | Inflação por componente + dados fiscais detalhados       ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 8 ═══

No projeto macro-fund-system, implemente 2 conectores:

## 1. src/connectors/ibge_sidra.py — IPCA desagregado por componente

### API Info:
- Base URL: `https://apisidra.ibge.gov.br/values`
- Path format: `/t/{tabela}/n1/all/v/{variavel}/p/{periodo}/c315/{classificacao}`
- Sem API key. Rate limit: ~60 req/min (usar 2s entre requests).

### Tabela 7060 — IPCA mensal:
- Variável 63: variação mensal (%)
- Variável 66: variação acumulada 12 meses (%)
- Variável 2265: peso mensal
- Período: YYYYMM (ex: 202401)
- Classificação 315 — Grupos (nível 1):
  - 7169: Alimentação e bebidas
  - 7170: Habitação
  - 7445: Artigos de residência
  - 7171: Vestuário
  - 7432: Transportes
  - 7172: Saúde e cuidados pessoais
  - 7173: Despesas pessoais
  - 7174: Educação
  - 7175: Comunicação

### Classe IbgeSidraConnector(BaseConnector):

```python
IPCA_GROUPS = {
    "BR_IPCA_FOOD": 7169,
    "BR_IPCA_HOUSING": 7170,
    "BR_IPCA_HOUSEHOLD": 7445,
    "BR_IPCA_CLOTHING": 7171,
    "BR_IPCA_TRANSPORT": 7432,
    "BR_IPCA_HEALTH": 7172,
    "BR_IPCA_PERSONAL": 7173,
    "BR_IPCA_EDUCATION": 7174,
    "BR_IPCA_COMMUNICATION": 7175,
}

async def fetch_ipca_by_group(self, start_period: str, end_period: str) -> pd.DataFrame:
    """
    Fetch IPCA variation (variable 63) for all 9 groups.
    Period format: YYYYMM (e.g., "202001" to "202412").
    URL example: /t/7060/n1/all/v/63/p/202001-202412/c315/7169,7170,7445,7171,7432,7172,7173,7174,7175
    Parse response (first row is header).
    Save to macro_series: series_id = 'BR_IPCA_{GROUP}_MOM', value = variation.
    Also fetch weights (variable 2265) and save as 'BR_IPCA_{GROUP}_WEIGHT'.
    """

async def fetch_ipca15_by_group(self, start_period: str, end_period: str) -> pd.DataFrame:
    """Same structure but table 7062 (IPCA-15)."""

async def fetch_latest(self):
    """Last 6 months of IPCA by group."""

async def fetch_historical(self, start_date: date, end_date: date):
    """Historical from 2006. Convert dates to period format YYYYMM."""
```

## 2. src/connectors/stn_fiscal.py — Dados fiscais do Tesouro Nacional

### Fontes:

A) BCB SGS (already partially covered, but add specific fiscal series):
```python
FISCAL_BCB_SERIES = {
    "BR_PRIMARY_CG_MONTHLY": 5364,    # Resultado primário Governo Central mensal
    "BR_REVENUE_TOTAL": 21864,        # Receita total Governo Central
    "BR_EXPENDITURE_TOTAL": 21865,    # Despesa total Governo Central
    "BR_SOCIAL_SEC_DEFICIT": 7620,    # Resultado previdenciário RGPS
}
```

B) Tesouro Transparente API:
- URL: `https://apidatalake.tesouro.gov.br/ords/sadipem/tt/`
- Endpoint: `divida_publica` — composição da dívida por indexador
- Endpoint: `resultado_primario` — resultado primário detalhado
- Format: JSON, sem autenticação

### Classe StnFiscalConnector(BaseConnector):

```python
async def fetch_fiscal_bcb_series(self, start_date: date, end_date: date):
    """Fetch the 4 additional fiscal BCB SGS series above."""

async def fetch_debt_composition(self, start_date: date = None) -> pd.DataFrame:
    """
    Try Tesouro Transparente API for debt composition.
    If not available, use BCB SGS proxies.
    Generate series:
    - BR_DEBT_SELIC_PCT: % dívida indexada à Selic
    - BR_DEBT_IPCA_PCT: % dívida indexada a IPCA
    - BR_DEBT_PREFIXED_PCT: % dívida pré-fixada
    - BR_DEBT_FX_PCT: % dívida indexada ao câmbio
    Save to fiscal_data table.
    """

async def fetch_latest(self):
    """Fetch latest fiscal data."""

async def fetch_historical(self, start_date: date, end_date: date):
    """Historical fiscal data."""
```

═══ FIM DO PROMPT 8 ═══

# VERIFICAÇÃO:
# □ python -m src.connectors.ibge_sidra
# □ SELECT DISTINCT series_id FROM macro_series WHERE source='IBGE_SIDRA';
# □ python -m src.connectors.stn_fiscal


################################################################################
##                                                                            ##
##  ETAPA 9 — CONECTORES RESTANTES (CFTC, TREASURY, YAHOO, COMMODITIES)      ##
##  Tempo: ~30 min | Completa a cobertura de dados                            ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 9 ═══

No projeto macro-fund-system, implemente os 5 conectores restantes:

## 1. src/connectors/cftc_cot.py — CFTC Commitment of Traders

### API Info:
- Current year data: `https://www.cftc.gov/dea/newcot/deafut.txt` (futures only, current year)
- Disaggregated: `https://www.cftc.gov/dea/newcot/f_disagg.txt`
- Historical: `https://www.cftc.gov/files/dea/history/deafut{YYYY}.zip`
- CSV format, semicolon or comma separated depending on version

### Contratos a monitorar (CFTC contract codes):
```python
CONTRACTS = {
    "BRL": "095741",         # Brazilian Real (CME)
    "EUR": "099741",         # Euro (CME)
    "JPY": "097741",         # Japanese Yen (CME)
    "GBP": "096742",         # British Pound (CME)
    "CHF": "092741",         # Swiss Franc (CME)
    "UST_BOND": "020601",    # US Treasury Bonds (CBOT)
    "UST_10Y": "043602",     # 10-Year T-Note (CBOT)
    "UST_5Y": "044601",      # 5-Year T-Note (CBOT)
    "UST_2Y": "042601",      # 2-Year T-Note (CBOT)
    "GOLD": "088691",        # Gold (COMEX)
    "OIL_WTI": "067651",     # Crude Oil WTI (NYMEX)
    "VIX": "1170E1",         # VIX Futures (CFE)
}
```

### Séries geradas (save to flow_data table):
For each contract, calculate net positions by category:
- `CFTC_{NAME}_DEALER_NET` = Dealer Long - Dealer Short
- `CFTC_{NAME}_ASSETMGR_NET` = Asset Manager Long - Asset Manager Short
- `CFTC_{NAME}_LEVERAGED_NET` = Leveraged Funds Long - Leveraged Funds Short
- `CFTC_{NAME}_TOTAL_OI` = Open Interest
- Total: ~48 series (12 contracts × 4 categories)

Also compute z-scores (52-week window) for each net position series.

### Métodos:
- `async def download_current_report() -> pd.DataFrame`
- `async def download_historical(year: int) -> pd.DataFrame`
- `def parse_cot_report(raw_data: str, report_type: str) -> pd.DataFrame`
- `def calculate_net_positions(df: pd.DataFrame) -> pd.DataFrame`
- `async def fetch_latest()` — download current week
- `async def fetch_historical(start_date, end_date)` — download yearly zips

## 2. src/connectors/treasury_gov.py — US Treasury Yields & Auction Data

### Fontes:
A) Daily Treasury Yield Curve:
   URL: `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/{YYYY}?type=daily_treasury_yield_curve&field_tdr_date_value={YYYY}&page&_format=csv`
   Columns: Date, 1 Mo, 2 Mo, 3 Mo, 4 Mo, 6 Mo, 1 Yr, 2 Yr, 3 Yr, 5 Yr, 7 Yr, 10 Yr, 20 Yr, 30 Yr

B) Daily Treasury Real Yield Curve (TIPS):
   Same URL with `type=daily_treasury_real_yield_curve`
   Columns: Date, 5 Yr, 7 Yr, 10 Yr, 20 Yr, 30 Yr

### Métodos:
- `async def fetch_nominal_curve(year: int) -> pd.DataFrame` — save to curves: curve_id='UST_NOM'
- `async def fetch_real_curve(year: int) -> pd.DataFrame` — save to curves: curve_id='UST_REAL'
- `def compute_breakeven_curve(nominal, real) -> pd.DataFrame` — save: curve_id='UST_BEI'
- `async def fetch_latest()` — current year
- `async def fetch_historical(start_date, end_date)` — year by year

## 3. src/connectors/yahoo_finance.py — Fallback for Market Prices

Use yfinance library. Fetch OHLCV daily data.

### Tickers:
```python
TICKERS = {
    # FX
    "USDBRL": "BRL=X",
    "EURUSD": "EURUSD=X",
    "USDJPY": "JPY=X",
    "GBPUSD": "GBPUSD=X",
    "USDCHF": "CHF=X",
    "DXY": "DX-Y.NYB",
    
    # Equity Indices
    "IBOVESPA": "^BVSP",
    "SP500": "^GSPC",
    "VIX": "^VIX",
    
    # Commodities
    "GOLD": "GC=F",
    "OIL_WTI": "CL=F",
    "OIL_BRENT": "BZ=F",
    "SOYBEAN": "ZS=F",
    "CORN": "ZC=F",
    "COPPER": "HG=F",
    "IRON_ORE_PROXY": "VALE3.SA",  # Vale as proxy
    
    # ETFs (for flow proxies)
    "EWZ": "EWZ",           # Brazil ETF
    "TIP_ETF": "TIP",       # TIPS ETF
    "TLT_ETF": "TLT",       # Long Treasury ETF
    "HYG_ETF": "HYG",       # High Yield ETF
    "EMB_ETF": "EMB",       # EM Bond ETF
    "LQD_ETF": "LQD",       # IG Bond ETF
}
```

### Métodos:
- `async def fetch_ticker(ticker_yahoo: str, start: date, end: date) -> pd.DataFrame`
- `async def fetch_all(start: date, end: date)` — all tickers, save to market_data table
- Instruments must exist in instruments table (create if missing)
- `async def fetch_latest()` — last 10 days
- `async def fetch_historical(start, end)` — full range

## 4. src/connectors/bcb_ptax.py — PTAX Diário

### API:
URL: `https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarPeriodo(dataInicial=@di,dataFinalCotacao=@df)?@di='MM-DD-YYYY'&@df='MM-DD-YYYY'&$format=json`
Response: `{"value": [{"cotacaoCompra": 5.1234, "cotacaoVenda": 5.1256, "dataHoraCotacao": "2024-01-15 13:07:03.490"}, ...]}`

Save to market_data (USDBRL_PTAX instrument) with bid=cotacaoCompra, ask=cotacaoVenda.

## 5. src/connectors/bcb_fx_flow.py — Fluxo Cambial

### BCB SGS series for FX flow:
```python
FX_FLOW_SERIES = {
    "BR_FX_FLOW_COMMERCIAL": 22704,   # Fluxo cambial comercial (USD mi)
    "BR_FX_FLOW_FINANCIAL": 22705,    # Fluxo cambial financeiro (USD mi)
    "BR_FX_FLOW_TOTAL": 22706,        # Fluxo total
    "BR_BCB_SWAP_STOCK": 12070,       # Estoque swaps cambiais BCB (USD mi)
}
```

Save to flow_data table. Implement using BCB SGS API (same as bcb_sgs.py connector).

═══ FIM DO PROMPT 9 ═══

# VERIFICAÇÃO:
# □ python -m src.connectors.treasury_gov
# □ python -m src.connectors.yahoo_finance
# □ python -m src.connectors.cftc_cot
# □ SELECT COUNT(*) FROM curves WHERE curve_id='UST_NOM';
# □ SELECT COUNT(*) FROM market_data; (deve ter dados de ~25 tickers)
# □ SELECT DISTINCT series_id FROM flow_data WHERE source='CFTC';


################################################################################
##                                                                            ##
##  ETAPA 10 — SEED DATA (INSTRUMENTOS E METADADOS)                          ##
##  Tempo: ~20 min | Popular tabelas de referência                            ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 10 ═══

No projeto macro-fund-system, implemente os scripts de seed data:

## 1. scripts/seed_instruments.py

Popular a tabela `instruments` com todos os instrumentos do sistema. O script deve ser idempotente (ON CONFLICT DO NOTHING).

```python
INSTRUMENTS = [
    # ══════ FX SPOT ══════
    {"ticker": "USDBRL", "name": "US Dollar / Brazilian Real Spot", "asset_class": "FX", "instrument_type": "SPOT", "currency": "BRL", "exchange": "OTC"},
    {"ticker": "USDBRL_PTAX", "name": "PTAX Official Rate", "asset_class": "FX", "instrument_type": "SPOT", "currency": "BRL", "exchange": "BCB"},
    {"ticker": "EURUSD", "name": "Euro / US Dollar Spot", "asset_class": "FX", "instrument_type": "SPOT", "currency": "USD", "exchange": "OTC"},
    {"ticker": "USDJPY", "name": "US Dollar / Japanese Yen Spot", "asset_class": "FX", "instrument_type": "SPOT", "currency": "JPY", "exchange": "OTC"},
    {"ticker": "GBPUSD", "name": "British Pound / US Dollar Spot", "asset_class": "FX", "instrument_type": "SPOT", "currency": "USD", "exchange": "OTC"},
    {"ticker": "USDCHF", "name": "US Dollar / Swiss Franc Spot", "asset_class": "FX", "instrument_type": "SPOT", "currency": "CHF", "exchange": "OTC"},
    {"ticker": "DXY", "name": "US Dollar Index", "asset_class": "FX", "instrument_type": "INDEX", "currency": "USD", "exchange": "ICE"},

    # ══════ EQUITY INDICES ══════
    {"ticker": "IBOVESPA", "name": "Ibovespa Index", "asset_class": "EQUITY_INDEX", "instrument_type": "INDEX", "currency": "BRL", "exchange": "B3"},
    {"ticker": "SP500", "name": "S&P 500 Index", "asset_class": "EQUITY_INDEX", "instrument_type": "INDEX", "currency": "USD", "exchange": "CME"},
    {"ticker": "VIX", "name": "CBOE Volatility Index", "asset_class": "EQUITY_INDEX", "instrument_type": "INDEX", "currency": "USD", "exchange": "CBOE"},

    # ══════ COMMODITIES ══════
    {"ticker": "GOLD", "name": "Gold Futures (front month)", "asset_class": "COMMODITIES", "instrument_type": "FUTURE", "currency": "USD", "exchange": "CME"},
    {"ticker": "OIL_WTI", "name": "WTI Crude Oil Futures", "asset_class": "COMMODITIES", "instrument_type": "FUTURE", "currency": "USD", "exchange": "CME"},
    {"ticker": "OIL_BRENT", "name": "Brent Crude Oil Futures", "asset_class": "COMMODITIES", "instrument_type": "FUTURE", "currency": "USD", "exchange": "ICE"},
    {"ticker": "SOYBEAN", "name": "Soybean Futures", "asset_class": "COMMODITIES", "instrument_type": "FUTURE", "currency": "USD", "exchange": "CME"},
    {"ticker": "CORN", "name": "Corn Futures", "asset_class": "COMMODITIES", "instrument_type": "FUTURE", "currency": "USD", "exchange": "CME"},
    {"ticker": "COPPER", "name": "Copper Futures", "asset_class": "COMMODITIES", "instrument_type": "FUTURE", "currency": "USD", "exchange": "CME"},
    {"ticker": "IRON_ORE_PROXY", "name": "Iron Ore (Vale proxy)", "asset_class": "COMMODITIES", "instrument_type": "ETF", "currency": "BRL", "exchange": "B3"},

    # ══════ ETFs ══════
    {"ticker": "EWZ", "name": "iShares MSCI Brazil ETF", "asset_class": "EQUITY_INDEX", "instrument_type": "ETF", "currency": "USD", "exchange": "NYSE"},
    {"ticker": "TIP_ETF", "name": "iShares TIPS Bond ETF", "asset_class": "INFLATION_US", "instrument_type": "ETF", "currency": "USD", "exchange": "NYSE"},
    {"ticker": "TLT_ETF", "name": "iShares 20+ Year Treasury Bond ETF", "asset_class": "RATES_US", "instrument_type": "ETF", "currency": "USD", "exchange": "NYSE"},
    {"ticker": "HYG_ETF", "name": "iShares iBoxx HY Corporate Bond ETF", "asset_class": "SOVEREIGN_CREDIT", "instrument_type": "ETF", "currency": "USD", "exchange": "NYSE"},
    {"ticker": "EMB_ETF", "name": "iShares JP Morgan EM Bond ETF", "asset_class": "SOVEREIGN_CREDIT", "instrument_type": "ETF", "currency": "USD", "exchange": "NYSE"},
    {"ticker": "LQD_ETF", "name": "iShares iBoxx IG Corporate Bond ETF", "asset_class": "SOVEREIGN_CREDIT", "instrument_type": "ETF", "currency": "USD", "exchange": "NYSE"},
]
```

Log: "Seeded {n} instruments."

## 2. scripts/seed_series_metadata.py

Popular a tabela `series_metadata` com TODAS as séries usadas por todos os conectores.

Organize por fonte:

```python
METADATA = [
    # ══════ BCB SGS SERIES ══════
    {"series_id": "BR_IPCA_MOM", "name": "IPCA Variação Mensal", "country": "BRA", "category": "INFLATION", "frequency": "MONTHLY", "unit": "percent", "source_provider": "BCB_SGS", "source_code": "SGS #433", "expected_release_lag_days": 15, "is_revised": False},
    {"series_id": "BR_IPCA_YOY", "name": "IPCA Acumulado 12 Meses", "country": "BRA", "category": "INFLATION", "frequency": "MONTHLY", "unit": "percent", "source_provider": "BCB_SGS", "source_code": "SGS #13522"},
    # ... (include ALL ~50 BCB SGS series from Etapa 4 registry)
    
    {"series_id": "BR_SELIC_TARGET", "name": "Meta Selic", "country": "BRA", "category": "MONETARY", "frequency": "DAILY", "unit": "percent", "source_provider": "BCB_SGS", "source_code": "SGS #432"},
    {"series_id": "BR_CDI_DAILY", "name": "CDI Diário", "country": "BRA", "category": "MONETARY", "frequency": "DAILY", "unit": "percent", "source_provider": "BCB_SGS", "source_code": "SGS #12"},
    {"series_id": "BR_RESERVES", "name": "Reservas Internacionais", "country": "BRA", "category": "EXTERNAL", "frequency": "DAILY", "unit": "usd_millions", "source_provider": "BCB_SGS", "source_code": "SGS #13621"},
    
    # ══════ FRED SERIES ══════
    {"series_id": "US_CPI_ALL_SA", "name": "CPI All Items SA", "country": "USA", "category": "INFLATION", "frequency": "MONTHLY", "unit": "index", "source_provider": "FRED", "source_code": "CPIAUCSL", "expected_release_lag_days": 13, "is_revised": True},
    {"series_id": "US_PCE_CORE", "name": "PCE Core Price Index", "country": "USA", "category": "INFLATION", "frequency": "MONTHLY", "unit": "index", "source_provider": "FRED", "source_code": "PCEPILFE"},
    {"series_id": "US_NFP_TOTAL", "name": "Nonfarm Payrolls", "country": "USA", "category": "LABOR", "frequency": "MONTHLY", "unit": "thousands", "source_provider": "FRED", "source_code": "PAYEMS", "expected_release_lag_days": 5, "is_revised": True},
    {"series_id": "US_FED_FUNDS", "name": "Effective Federal Funds Rate", "country": "USA", "category": "MONETARY", "frequency": "DAILY", "unit": "percent", "source_provider": "FRED", "source_code": "DFF"},
    {"series_id": "US_UST_10Y", "name": "Treasury 10Y Yield", "country": "USA", "category": "MONETARY", "frequency": "DAILY", "unit": "percent", "source_provider": "FRED", "source_code": "DGS10"},
    # ... (include ALL ~50 FRED series from Etapa 5 registry)
    
    # ══════ BCB FOCUS SERIES ══════
    {"series_id": "BR_FOCUS_IPCA_CY_MEDIAN", "name": "Focus IPCA Current Year Median", "country": "BRA", "category": "INFLATION", "frequency": "WEEKLY", "unit": "percent", "source_provider": "BCB_FOCUS"},
    {"series_id": "BR_FOCUS_SELIC_CY_MEDIAN", "name": "Focus Selic Year-End Median", "country": "BRA", "category": "MONETARY", "frequency": "WEEKLY", "unit": "percent", "source_provider": "BCB_FOCUS"},
    
    # ══════ IBGE SERIES ══════
    {"series_id": "BR_IPCA_FOOD_MOM", "name": "IPCA Alimentação MoM", "country": "BRA", "category": "INFLATION", "frequency": "MONTHLY", "unit": "percent", "source_provider": "IBGE"},
    {"series_id": "BR_IPCA_HOUSING_MOM", "name": "IPCA Habitação MoM", "country": "BRA", "category": "INFLATION", "frequency": "MONTHLY", "unit": "percent", "source_provider": "IBGE"},
    {"series_id": "BR_IPCA_TRANSPORT_MOM", "name": "IPCA Transportes MoM", "country": "BRA", "category": "INFLATION", "frequency": "MONTHLY", "unit": "percent", "source_provider": "IBGE"},
    # ... (all 9 IPCA groups)
    
    # ══════ CFTC SERIES ══════
    {"series_id": "CFTC_BRL_LEVERAGED_NET", "name": "CFTC BRL Leveraged Funds Net Position", "country": "USA", "category": "POSITIONING", "frequency": "WEEKLY", "unit": "contracts", "source_provider": "CFTC"},
    {"series_id": "CFTC_BRL_ASSETMGR_NET", "name": "CFTC BRL Asset Manager Net Position", "country": "USA", "category": "POSITIONING", "frequency": "WEEKLY", "unit": "contracts", "source_provider": "CFTC"},
    {"series_id": "CFTC_UST_10Y_LEVERAGED_NET", "name": "CFTC 10Y Treasury Leveraged Net", "country": "USA", "category": "POSITIONING", "frequency": "WEEKLY", "unit": "contracts", "source_provider": "CFTC"},
    # ... (all CFTC contract × category combinations)
    
    # ══════ FLOW SERIES ══════
    {"series_id": "BR_FX_FLOW_COMMERCIAL", "name": "BCB FX Flow Commercial", "country": "BRA", "category": "FLOW", "frequency": "WEEKLY", "unit": "usd_millions", "source_provider": "BCB_SGS", "source_code": "SGS #22704"},
    {"series_id": "BR_FX_FLOW_FINANCIAL", "name": "BCB FX Flow Financial", "country": "BRA", "category": "FLOW", "frequency": "WEEKLY", "unit": "usd_millions", "source_provider": "BCB_SGS", "source_code": "SGS #22705"},
    {"series_id": "BR_BCB_SWAP_STOCK", "name": "BCB FX Swap Stock", "country": "BRA", "category": "FLOW", "frequency": "DAILY", "unit": "usd_millions", "source_provider": "BCB_SGS", "source_code": "SGS #12070"},
]
```

IMPORTANT: Include ALL series from ALL connectors. The total should be 150-200+ series.
Generate the complete list by programmatically reading the SERIES_REGISTRY from each connector class.

Script must be idempotent. Log: "Seeded {n} series metadata entries."

═══ FIM DO PROMPT 10 ═══

# VERIFICAÇÃO:
# □ make seed
# □ SELECT COUNT(*) FROM instruments; (deve ser ~25+)
# □ SELECT COUNT(*) FROM series_metadata; (deve ser 150+)
# □ SELECT category, COUNT(*) FROM series_metadata GROUP BY category;


################################################################################
##                                                                            ##
##  ETAPA 11 — BACKFILL HISTÓRICO                                            ##
##  Tempo: ~20 min (código) + 30-60 min (execução)                           ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 11 ═══

No projeto macro-fund-system, implemente scripts/backfill.py — orquestrador de backfill histórico.

## Requisitos:
- Idempotente (ON CONFLICT DO NOTHING em todos os inserts)
- Argparse para CLI
- Executa conectores na ordem correta
- Log de progresso detalhado
- Error handling robusto (se uma fonte falha, continua com as outras)
- Relatório final com contagem de records por fonte

## Interface CLI:

```bash
python scripts/backfill.py --source all --start-date 2010-01-01
python scripts/backfill.py --source bcb_sgs,fred,yahoo --start-date 2020-01-01
python scripts/backfill.py --source bcb_sgs --dry-run
```

Arguments:
- `--source`: comma-separated ou 'all'. Opções: bcb_sgs, fred, bcb_focus, ibge, b3, treasury, yahoo, cftc, bcb_ptax, bcb_fx_flow, stn
- `--start-date`: YYYY-MM-DD (default: 2010-01-01)
- `--end-date`: YYYY-MM-DD (default: today)
- `--dry-run`: mostra o que faria sem executar

## Ordem de Execução:

```python
SOURCES = [
    ("bcb_sgs",     "BCB SGS (50 macro series BR)",      BcbSgsConnector),
    ("fred",        "FRED (50 macro series US)",          FredConnector),
    ("bcb_focus",   "BCB Focus (market expectations)",    BcbFocusConnector),
    ("bcb_ptax",    "BCB PTAX (official FX rate)",        BcbPtaxConnector),
    ("bcb_fx_flow", "BCB FX Flow (capital flows)",        BcbFxFlowConnector),
    ("ibge",        "IBGE SIDRA (IPCA by component)",     IbgeSidraConnector),
    ("stn",         "STN Fiscal (fiscal data)",           StnFiscalConnector),
    ("b3",          "B3/Tesouro (DI curve, NTN-B)",       B3MarketDataConnector),
    ("treasury",    "Treasury.gov (US yield curves)",     TreasuryGovConnector),
    ("yahoo",       "Yahoo Finance (market prices)",      YahooFinanceConnector),
    ("cftc",        "CFTC COT (positioning)",             CftcCotConnector),
]
```

## Implementação:

Para cada source:
1. Instanciar o connector
2. Chamar fetch_historical(start_date, end_date)
3. Capturar tempo de execução e contagem de records
4. Se falhar, logar o erro e continuar

BCB SGS específico: dividir em batches de 5 anos para evitar timeout.
CFTC: download de zip files anuais.
Treasury: download de CSV por ano.

## Output esperado:

```
════════════════════════════════════════════════════
 MACRO FUND — HISTORICAL BACKFILL
 Sources: all | Range: 2010-01-01 to 2026-02-19
════════════════════════════════════════════════════

[1/11] BCB SGS (50 macro series BR)...
  Fetching 1/50: BR_IPCA_MOM (SGS #433)... 192 records
  Fetching 2/50: BR_SELIC_TARGET (SGS #432)... 5840 records
  ...
  Done: 50 series, 42,531 records, 298s

[2/11] FRED (50 macro series US)...
  ...

════════════════════════════════════════════════════
 SUMMARY
════════════════════════════════════════════════════
 Source         | Series | Records  | Time  | Status
 BCB SGS       |   50   |  42,531  | 298s  | OK
 FRED          |   50   |  35,456  |  92s  | OK
 BCB Focus     |   20   |  11,345  | 165s  | OK
 BCB PTAX      |    2   |   3,890  |  12s  | OK
 BCB FX Flow   |    4   |     832  |   8s  | OK
 IBGE SIDRA    |   18   |   2,160  | 220s  | OK
 STN Fiscal    |    6   |   1,056  |  35s  | OK
 B3/Tesouro    |   15   |  16,720  | 105s  | OK
 Treasury.gov  |    2   |   7,200  |  28s  | OK
 Yahoo Finance |   25   |  82,500  |  55s  | OK
 CFTC COT      |   48   |  40,200  |  85s  | OK
 TOTAL         |  240   | 243,890  |1103s  | ALL OK
════════════════════════════════════════════════════
```

Implement the complete script with all the above. Use asyncio.run() for the main entry point.

═══ FIM DO PROMPT 11 ═══

# VERIFICAÇÃO:
# □ make backfill-fast (5 anos, ~10-15 min)
# □ SELECT COUNT(*) FROM macro_series;
# □ SELECT COUNT(*) FROM curves;
# □ SELECT COUNT(*) FROM market_data;
# □ SELECT COUNT(*) FROM flow_data;


################################################################################
##                                                                            ##
##  ETAPA 12 — TRANSFORMS (SILVER LAYER)                                     ##
##  Tempo: ~25 min | Cálculos derivados, construção de curvas                 ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 12 ═══

No projeto macro-fund-system, implemente os transforms em src/transforms/:

## 1. src/transforms/curves.py

```python
import numpy as np
from scipy.optimize import minimize
from scipy.interpolate import CubicSpline

def nelson_siegel(tau: np.ndarray, beta0: float, beta1: float, beta2: float, lam: float) -> np.ndarray:
    """Nelson-Siegel formula: y(τ) = β0 + β1*[(1-e^(-τ/λ))/(τ/λ)] + β2*[(1-e^(-τ/λ))/(τ/λ) - e^(-τ/λ)]
    τ in years. Returns rates in decimal."""

def fit_nelson_siegel(tenors_years: np.ndarray, rates: np.ndarray) -> tuple:
    """Fit NS params using scipy minimize. Returns (beta0, beta1, beta2, lambda)."""

def interpolate_curve(observed_tenors_days: list[int], observed_rates: list[float],
                      target_tenors_days: list[int] = None, method: str = "nelson_siegel") -> dict[int, float]:
    """Interpolate to standard tenors: 30,60,90,180,365,730,1095,1825,2555,3650 days.
    Methods: nelson_siegel, cubic_spline, linear."""

def compute_breakeven_inflation(nominal: dict[int, float], real: dict[int, float]) -> dict[int, float]:
    """BEI = nominal - real at matching tenors."""

def compute_forward_rate(curve: dict[int, float], t1_days: int, t2_days: int) -> float:
    """Forward rate between t1 and t2."""

def compute_dv01(rate: float, maturity_years: float, coupon: float = 0, notional: float = 100) -> float:
    """Dollar value of 1bp."""

def compute_carry_rolldown(curve: dict[int, float], tenor_days: int, horizon_days: int = 21) -> dict:
    """Returns: {"carry_bps", "rolldown_bps", "total_bps"}"""
```

## 2. src/transforms/returns.py

```python
def compute_returns(prices: pd.Series, method: str = "log") -> pd.Series
def compute_rolling_volatility(returns: pd.Series, windows: list[int] = [5,21,63,252]) -> pd.DataFrame
def compute_z_score(series: pd.Series, window: int = 252) -> pd.Series
def compute_percentile_rank(series: pd.Series, window: int = 252) -> pd.Series
def compute_rolling_correlation(s1: pd.Series, s2: pd.Series, window: int = 63) -> pd.Series
def compute_ema(series: pd.Series, span: int = 20) -> pd.Series
def compute_rolling_sharpe(returns: pd.Series, window: int = 252, rf: float = 0) -> pd.Series
def compute_drawdown(prices: pd.Series) -> pd.DataFrame  # cummax, dd, dd_pct
def compute_realized_vol(prices: pd.Series, window: int = 21) -> pd.Series  # annualized
```

## 3. src/transforms/macro.py

```python
def yoy_from_mom(mom_series: pd.Series) -> pd.Series:
    """YoY = product(1 + MoM_i/100, i=1..12) - 1, times 100."""
def compute_diffusion_index(components_df: pd.DataFrame) -> pd.Series
def compute_trimmed_mean(components_df: pd.DataFrame, trim_pct: float = 0.20) -> pd.Series
def compute_surprise_index(actual: pd.Series, expected: pd.Series) -> pd.Series
def compute_momentum(series: pd.Series, periods: list[int] = [1,3,6,12]) -> pd.DataFrame
```

## 4. src/transforms/vol_surface.py

```python
def reconstruct_smile(atm: float, rr25: float, bf25: float, rr10: float = None, bf10: float = None) -> dict:
    """Call_25d = ATM + 0.5*RR + BF; Put_25d = ATM - 0.5*RR + BF"""
def compute_iv_rv_ratio(implied: float, realized: float) -> float
def compute_vol_slope(short: float, long: float) -> float
```

## 5. Write pytest tests:

tests/test_transforms/test_curves.py:
- Test nelson_siegel with known parameters, verify output matches analytical solution
- Test fit_nelson_siegel roundtrip: generate curve from known params, fit, verify recovery
- Test breakeven = nominal - real
- Test forward rate calculation

tests/test_transforms/test_returns.py:
- Test log returns sum property
- Test z_score mean ~0, std ~1 for large random sample

═══ FIM DO PROMPT 12 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_transforms/ -v (todos devem passar)


################################################################################
##                                                                            ##
##  ETAPA 13 — FASTAPI BACKEND                                               ##
##  Tempo: ~25 min | API REST para servir dados                               ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 13 ═══

No projeto macro-fund-system, implemente a API REST em src/api/:

## src/api/main.py
FastAPI app com CORS (allow all for dev), routers, lifespan handler (test DB on startup).

## src/api/deps.py
- get_db_session(): async generator para SQLAlchemy AsyncSession
- get_sync_session(): sync session

## src/api/routes/health.py

GET /health → {"status":"ok", "database":"connected", "timestamp":"..."}

GET /health/data-status → contagem de records por tabela, total instrumentos, total séries

## src/api/routes/macro.py

GET /api/v1/macro/{series_id}?start=2020-01-01&end=2026-02-19&pit=false
→ Lista de {time, value, release_time, revision}
Se pit=true: retorna só dados onde release_time <= end (point-in-time query)

GET /api/v1/macro/dashboard
→ JSON com últimos valores de indicadores-chave organizados em blocos:
  brazil: {selic_target, ipca_yoy, ipca_mom, ibc_br, unemployment, trade_balance, reserves, net_debt_gdp, gross_debt_gdp}
  us: {fed_funds, cpi_yoy, pce_core_yoy, nfp, unemployment, ust_10y, debt_gdp}
  market: {usdbrl, dxy, vix, ibovespa, sp500, gold, oil_wti}
  Cada campo: {value, date}
  O dashboard puxa o último valor de cada indicador do banco.

GET /api/v1/macro/search?q=ipca&country=BRA
→ Busca em series_metadata por keyword

## src/api/routes/curves.py

GET /api/v1/curves/{curve_id}?date=2026-02-18
→ {curve_id, date, points: [{tenor, tenor_days, rate, dv01}]}

GET /api/v1/curves/{curve_id}/history?tenor=5Y&start=2020-01-01&end=2026-02-19
→ Lista de {date, rate}

GET /api/v1/curves/available
→ Lista de curve_ids disponíveis no banco

## src/api/routes/market_data.py

GET /api/v1/market-data/{ticker}?start=2024-01-01&end=2026-02-19
→ Lista de {time, open, high, low, close, volume}

GET /api/v1/market-data/latest?tickers=USDBRL,IBOVESPA,VIX
→ Dict com último preço por ticker

## src/api/routes/flows.py

GET /api/v1/flows/{series_id}?start=2024-01-01
→ Lista de {time, value}

GET /api/v1/flows/positioning-summary
→ Resumo do CFTC positioning com z-scores para contratos principais

Use Pydantic v2 response models. Swagger em /docs.

═══ FIM DO PROMPT 13 ═══

# VERIFICAÇÃO:
# □ make api
# □ Abrir http://localhost:8000/docs
# □ Testar GET /health, /api/v1/macro/dashboard, /api/v1/curves/DI_PRE


################################################################################
##                                                                            ##
##  ETAPA 14 — DATA QUALITY + SCRIPT DE VERIFICAÇÃO                          ##
##  Tempo: ~20 min                                                            ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 14 ═══

No projeto macro-fund-system, implemente:

## 1. src/quality/checks.py

Classe DataQualityChecker com métodos:

check_completeness(): Para cada série ativa em series_metadata, verifica se existe dado recente. DAILY stale se >3 business days, WEEKLY >10 days, MONTHLY >45 days. Retorna lista com series_id, last_date, is_stale, days_behind.

check_accuracy(): Validação de range para séries-chave (BR_SELIC_TARGET: [0,50], BR_IPCA_MOM: [-3,5], US_FED_FUNDS: [0,20], etc.). Z-score check (|z|>5 em janela 252d). Retorna lista com flagged values.

check_curve_integrity(): Verifica mínimo 5 tenors por curva/data, sem rates negativos (exceto UST_REAL), monotonicidade razoável.

check_point_in_time(): Verifica que release_time >= time para todas as macro_series.

run_all_checks(): Roda todos e retorna summary com score 0-100 e status PASS/WARN/FAIL.

## 2. scripts/verify_infrastructure.py

Script que verifica TODO o sistema e imprime relatório formatado:

```
════════════════════════════════════════════════════
 MACRO FUND — INFRASTRUCTURE VERIFICATION
════════════════════════════════════════════════════

 Database:          ✅ Connected (PostgreSQL 16 + TimescaleDB)
 Tables:            ✅ 10/10 exist
 Hypertables:       ✅ 7/7 configured
 Compression:       ✅ 7/7 policies active
 Redis:             ✅ Connected

 Instruments:       ✅ {n} registered
 Series Metadata:   ✅ {n} registered

 Data Volume:
   macro_series:    ✅ {n} records (latest: {date})
   market_data:     ✅ {n} records (latest: {date})
   curves:          ✅ {n} records (latest: {date})
   flow_data:       ✅ {n} records (latest: {date})
   fiscal_data:     ✅ {n} records (latest: {date})

 Data Quality:      ✅ Score: {score}/100

 API (if running):
   GET /health:           ✅ 200 OK
   GET /macro/dashboard:  ✅ 200 OK
   GET /curves/DI_PRE:    ✅ 200 OK

════════════════════════════════════════════════════
 STATUS: ✅ PASS
 Ready for Phase 1 (Quantitative Models)
════════════════════════════════════════════════════
```

Deve fazer queries reais ao banco para obter números. Exit code 0 se PASS, 1 se FAIL.

═══ FIM DO PROMPT 14 ═══

# VERIFICAÇÃO:
# □ make verify
# □ make quality


################################################################################
##                                                                            ##
##  ETAPA 15 — GIT + README FINAL                                            ##
##  Tempo: ~10 min                                                            ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 15 ═══

No projeto macro-fund-system, finalize:

1. Atualize o README.md com documentação completa: overview, quick start (clone, setup, up, migrate, seed, backfill, api, verify), architecture diagram em ASCII, lista de endpoints, tabela de data coverage por categoria com contagem de séries e fontes, estrutura de diretórios, e seção "Next Phase" mencionando Fase 1 (Quant Models & Agents).

2. Inicialize git:
```bash
git init
git add .
git commit -m "Phase 0: Complete data infrastructure - 11 connectors, 200+ series, TimescaleDB, FastAPI"
```

3. Crie .github/workflows/ci.yml com GitHub Actions básico: Python 3.11, install deps, ruff check, pytest (excluindo integration tests).

═══ FIM DO PROMPT 15 ═══

# VERIFICAÇÃO FINAL:
# □ git log (1 commit)
# □ make verify (PASS)
# □ http://localhost:8000/docs (Swagger funcional)


################################################################################
##                                                                            ##
##  ═══════════════════════════════════════════════════════════════════        ##
##  FIM DA FASE 0 — DATA INFRASTRUCTURE COMPLETA                              ##
##  ═══════════════════════════════════════════════════════════════════        ##
##                                                                            ##
##  CONSTRUÍDO:                                                               ##
##  ✅ TimescaleDB com 10 tabelas e 7 hypertables com compressão              ##
##  ✅ 200+ séries macroeconômicas (BR + US)                                  ##
##  ✅ 11 conectores de dados funcionais                                      ##
##  ✅ Dados históricos de 10-15 anos                                         ##
##  ✅ Silver Layer transforms (curvas, retornos, vol, macro)                  ##
##  ✅ FastAPI REST API com 12+ endpoints                                     ##
##  ✅ Data quality framework automatizado                                    ##
##  ✅ Docker Compose stack completo                                          ##
##  ✅ Verificação end-to-end                                                 ##
##                                                                            ##
##  PRÓXIMO: Fase 1 — Quantitative Models & Agents                            ##
##  - Inflation Agent (Phillips Curve, IPCA bottom-up)                        ##
##  - Monetary Policy Agent (Taylor Rule + Kalman Filter)                     ##
##  - Fiscal Agent (DSA model)                                                ##
##  - FX Equilibrium Agent (BEER model)                                       ##
##  - Backtesting Engine + primeiras 8 estratégias                            ##
##  - Frontend Dashboard (React)                                              ##
##                                                                            ##
################################################################################
