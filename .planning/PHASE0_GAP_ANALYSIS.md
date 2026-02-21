# Phase 0 Gap Analysis: Data Architecture Blueprint vs. Implementation

> **Date**: 2026-02-20
> **Scope**: Compare the Data Architecture Blueprint with the current Phase 0 codebase
> **Goal**: Identify everything still needed to complete Phase 0 data infrastructure

---

## Executive Summary

Phase 0 has a solid foundation with **11 connectors**, **10 ORM models** (3 metadata + 7 hypertables), **4 transforms**, **5 API routes**, and **319 tests**. However, significant gaps remain when compared against the Data Architecture Blueprint, the GUIA Phase 0 spec (15 ETAPAs), and the research documents (ARCHITECTURE.md, FEATURES.md, PITFALLS.md).

**Key Metrics:**
| Metric | Blueprint Target | Current Implementation | Gap |
|--------|-----------------|----------------------|-----|
| Total series (macro_series + flow + fiscal) | ~200 (Phase 0 scope) | ~117 (seed_metadata) | ~83 series |
| Instruments | 25+ | 29 | OK |
| Connectors | 11 + anbima stub | 11 (no anbima) | 1 missing |
| Tables | 10 | 10 | OK |
| Hypertables | 7 | 7 | OK |
| Compression policies | 7 | 7 | OK |
| API endpoints | 12+ | 5 routes (~12 endpoints) | Verify completeness |
| Tests | Comprehensive | 319 (18 files) | Check coverage gaps |

---

## SECTION 1: DATABASE SCHEMA GAPS

### 1.1 Instruments Table

**Blueprint (Section 2.2.1) specifies:**
```
- id: UUID with gen_random_uuid()
- ticker: VARCHAR(50) UNIQUE NOT NULL
- name: VARCHAR(200)
- asset_class: ENUM ('FX', 'RATES_BR', 'RATES_US', 'RATES_G5', 'INFLATION_BR', 'INFLATION_US', 'CUPOM_CAMBIAL', 'SOVEREIGN_CREDIT', 'COMMODITIES', 'EQUITY_INDEX', 'MONEY_MARKET')
- instrument_type: ENUM ('FUTURE', 'BOND', 'SWAP', 'OPTION', 'CDS', 'NDF', 'SPOT', 'INDEX', 'ETF', 'FRA')
- currency: VARCHAR(3)
- exchange: VARCHAR(20)
- maturity_date: DATE nullable
- contract_specs: JSONB (multiplier, tick_size, margin, settlement_type)
- is_active: BOOLEAN
- created_at, updated_at
```

**Current Implementation (instruments.py):**
```
- id: Integer (autoincrement) ← NOT UUID
- ticker: String(50) unique
- name: String(200)
- asset_class: String(50) ← NOT ENUM, no instrument_type-specific values
- country: String(10) ← EXTRA (not in Blueprint)
- currency: String(10)
- exchange: Optional String(50)
- is_active: Boolean
- created_at, updated_at
```

**GAPS:**
- [ ] **CRITICAL**: Missing `instrument_type` column (FUTURE, BOND, SWAP, etc.)
- [ ] **CRITICAL**: Missing `contract_specs` JSONB column (multiplier, tick_size, margin, settlement_type)
- [ ] **MEDIUM**: Missing `maturity_date` DATE column
- [ ] **LOW**: ID is Integer, not UUID (functional but differs from Blueprint)
- [ ] **LOW**: `asset_class` values don't match Blueprint enum (current: generic, Blueprint: domain-specific like RATES_BR, CUPOM_CAMBIAL, etc.)
- [ ] **LOW**: `country` column exists in implementation but not Blueprint (useful, keep it)

### 1.2 Market Data (Prices) Hypertable

**Blueprint specifies:**
```
- instrument_id: UUID FK
- ts: TIMESTAMPTZ (time column)
- open/high/low/close: DOUBLE PRECISION
- volume: BIGINT
- open_interest: BIGINT nullable
- bid/ask: DOUBLE PRECISION nullable
- source: VARCHAR(50)
- ingestion_ts: TIMESTAMPTZ DEFAULT now()
```

**Current Implementation:**
```
- instrument_id: Integer FK
- timestamp: DateTime(timezone=True) (time column)
- frequency: String(20) ← EXTRA
- open/high/low/close: Float nullable
- volume: Float nullable
- adjusted_close: Float nullable ← EXTRA
- source: String(50)
```

**GAPS:**
- [ ] **MEDIUM**: Missing `open_interest` (BigInteger) - needed for futures
- [ ] **MEDIUM**: Missing `bid`/`ask` columns - needed for PTAX and FX
- [ ] **MEDIUM**: Missing `ingestion_ts` column for pipeline monitoring
- [ ] **LOW**: `close` is nullable (Blueprint says NOT NULL)
- [ ] **LOW**: `volume` is Float (Blueprint says BIGINT)

### 1.3 Curves Hypertable

**Blueprint specifies:**
```
- curve_id: VARCHAR(30) -- DI_PRE, DDI_CUPOM, NTN_B_REAL, UST_NOM, UST_REAL, UST_BEI
- ts: TIMESTAMPTZ
- tenor: VARCHAR(10) -- 1M, 2M, ..., 30Y
- tenor_days: INTEGER
- rate: DOUBLE PRECISION (decimal: 0.1350 = 13.50%)
- dv01: DOUBLE PRECISION nullable
- source: VARCHAR(50)
- ingestion_ts: TIMESTAMPTZ
```

**Current Implementation:**
```
- curve_id: String(50)
- curve_date: Date (not TIMESTAMPTZ)
- tenor_days: Integer
- tenor_label: String(20)
- rate: Float
- curve_type: String(20) ← EXTRA
- source: String(50)
```

**GAPS:**
- [ ] **MEDIUM**: Missing `dv01` column - needed by strategies for DV01-neutral trades
- [ ] **MEDIUM**: Missing `ingestion_ts` column
- [ ] **LOW**: `curve_date` is Date, not TIMESTAMPTZ (adequate for daily curves)

### 1.4 Vol Surfaces Hypertable

**Blueprint specifies:**
```
- underlying: VARCHAR(20) (USDBRL, DI, EURUSD)
- expiry: DATE
- strike_type: ENUM (DELTA, ABSOLUTE, MONEYNESS)
- strike_value: DOUBLE PRECISION
- call_put: ENUM (CALL, PUT, STRADDLE)
- implied_vol: DOUBLE PRECISION
```

**Current Implementation:**
```
- instrument_id: Integer FK (instead of underlying VARCHAR)
- surface_date: Date
- delta: Float (only delta, no strike_type)
- tenor_days: Integer (instead of expiry DATE)
- implied_vol: Float
- call_put: String(4)
```

**GAPS:**
- [ ] **MEDIUM**: Uses `instrument_id` FK instead of `underlying` VARCHAR - less flexible but still functional
- [ ] **MEDIUM**: Missing `strike_type` ENUM - only supports delta strikes, not absolute or moneyness
- [ ] **MEDIUM**: Uses `tenor_days` instead of `expiry` Date - different but functionally equivalent
- [ ] **LOW**: Missing `ingestion_ts`

### 1.5 Macro Series Hypertable - OK with minor gaps

**Current implementation matches Blueprint well:**
- Has `series_id`, `observation_date`, `value`, `release_time` (PIT!), `revision_number`, `source`
- [ ] **LOW**: Missing `ingestion_ts` (ingestion_time in Blueprint)

### 1.6 Missing Table: `data_quality_log`

**Blueprint (Section 14) envisions a data quality tracking table:**
```
- run_id, check_type, table_name, records_checked, issues_found, score, run_time
```

- [ ] **MEDIUM**: No `data_quality_log` table for tracking ingestion run results

### 1.7 Enums Module

**Current `src/core/enums.py` has:**
- AssetClass: FX, EQUITY_INDEX, COMMODITY, FIXED_INCOME, CRYPTO
- Frequency: DAILY, WEEKLY, MONTHLY, QUARTERLY, ANNUAL
- Country: BR, US
- CurveType: NOMINAL, REAL, BREAKEVEN, SWAP
- FlowType: COMMERCIAL, FINANCIAL, SWAP_STOCK, NET
- FiscalMetric: PRIMARY_BALANCE, NOMINAL_BALANCE, GROSS_DEBT, NET_DEBT, REVENUE, EXPENDITURE

**Blueprint asset_class values:**
- FX, RATES_BR, RATES_US, RATES_G5, INFLATION_BR, INFLATION_US, CUPOM_CAMBIAL, SOVEREIGN_CREDIT, COMMODITIES, EQUITY_INDEX, MONEY_MARKET

**GAPS:**
- [ ] **MEDIUM**: AssetClass enum missing domain-specific values (RATES_BR, INFLATION_BR, CUPOM_CAMBIAL, SOVEREIGN_CREDIT, MONEY_MARKET)
- [ ] **LOW**: Missing InstrumentType enum (FUTURE, BOND, SWAP, OPTION, CDS, NDF, SPOT, INDEX, ETF, FRA)
- [ ] **LOW**: Frequency missing TICK, BIWEEKLY
- [ ] **LOW**: Country missing EUR, GBR, JPN, CHE (needed for G5 extension)

---

## SECTION 2: CONNECTOR GAPS

### 2.1 Connector Inventory

| Connector | File | Status | Series Count | Blueprint Target |
|-----------|------|--------|-------------|-----------------|
| BCB SGS | bcb_sgs.py | Implemented | ~50 | ~50 |
| FRED | fred.py | Implemented | ~50 | ~50 |
| BCB Focus | bcb_focus.py | Implemented | ~20 | ~20 |
| BCB PTAX | bcb_ptax.py | Implemented | 2 | 2 |
| BCB FX Flow | bcb_fx_flow.py | Implemented | 4 | 4 |
| IBGE SIDRA | ibge_sidra.py | Implemented | 9 groups | 9 groups |
| STN Fiscal | stn_fiscal.py | Implemented | 6 | 6 |
| B3 Market Data | b3_market_data.py | Implemented | 12 (DI swaps) | 12+ |
| Treasury.gov | treasury_gov.py | Implemented | 2 curves | 2 curves |
| Yahoo Finance | yahoo_finance.py | Implemented | ~25 tickers | ~25 |
| CFTC COT | cftc_cot.py | Implemented | ~12 contracts | ~12 |
| **ANBIMA** | **MISSING** | **Not implemented** | 0 | **Placeholder** |
| **Commodities** | **MISSING** | **Not implemented** | 0 | **In Blueprint** |

### 2.2 Missing Connectors

- [ ] **MEDIUM**: `src/connectors/anbima.py` - Blueprint and GUIA Etapa 7 both call for at least a **placeholder** class documenting ANBIMA ETTJ, indicative NTN-B rates, and future access plans. This file was never created.
- [ ] **LOW**: `src/connectors/commodities.py` - Referenced in GUIA structure but specific commodity data is currently handled via Yahoo Finance. Not critical.

### 2.3 Series Coverage Gaps

**BCB SGS (bcb_sgs.py):**
The GUIA Etapa 4 specifies exactly 50 series. Current implementation appears to have ~50. Need to verify:
- [ ] All inflation series (IPCA cores: EX0, EX3, MA, DP, P55, diffusion)
- [ ] All activity series (GDP, IBC-Br, industrial prod, retail, services, consumer/business conf, capacity util, CAGED, unemployment)
- [ ] All monetary series (Selic target, Selic daily, CDI, credit/GDP, defaults PF/PJ, lending rate, M1-M4, monetary base)
- [ ] All external sector series (trade balance, current account, CA/GDP, FDI, portfolio equity/debt, reserves, PTAX buy/sell)
- [ ] All fiscal series (primary balance, nominal deficit, net debt/GDP, gross debt/GDP)

**FRED (fred.py):**
GUIA Etapa 5 specifies ~50 series. Need to verify:
- [ ] All inflation series (CPI variants, PCE, PPI, Michigan, BEI, forward inflation)
- [ ] All activity/labor series (GDP, NFP, unemployment, hourly earnings, JOLTS, claims, industrial prod, retail, housing, consumer sentiment, CFNAI)
- [ ] All monetary/rates series (Fed Funds, SOFR, UST 2/5/10/30Y, TIPS, Fed balance sheet, ON RRP, NFCI)
- [ ] Credit series (HY OAS, IG OAS)
- [ ] Fiscal (Fed debt, debt/GDP)

**BCB Focus (bcb_focus.py):**
GUIA Etapa 6 specifies annual expectations (IPCA, Selic, PIB, Cambio, IGP-M), monthly expectations, Selic per meeting, Top-5 forecasters. Verify all 4 endpoints implemented.

**IBGE SIDRA (ibge_sidra.py):**
GUIA Etapa 8 specifies 9 IPCA groups (table 7060) + IPCA-15 (table 7062). Current has 9 groups.
- [ ] Verify IPCA-15 by group is implemented (table 7062)
- [ ] Verify both variation (variable 63) AND weights (variable 2265) are fetched

**B3 Market Data (b3_market_data.py):**
GUIA Etapa 7 specifies:
- [ ] 12 DI swap series from BCB SGS (7805-7816)
- [ ] Tesouro Direto current prices (JSON API)
- [ ] Tesouro Direto historical CSVs
- [ ] USDBRL via yfinance
- [ ] Equity indices (IBOVESPA, EWZ)
- [ ] Breakeven inflation curve construction (NTN-F - NTN-B)

**CFTC COT (cftc_cot.py):**
GUIA Etapa 9 specifies 12 contracts x 4 categories = ~48 net position series + z-scores.
- [ ] Verify all 12 contracts (BRL, EUR, JPY, GBP, CHF, UST_BOND, UST_10Y, UST_5Y, UST_2Y, GOLD, OIL_WTI, VIX)
- [ ] Verify disaggregated categories (Dealer, AssetMgr, Leveraged, Total_OI)
- [ ] Verify z-score computation (52-week window)

### 2.4 Seed Data Gaps

**seed_instruments.py (29 instruments):**
GUIA Etapa 10 specifies 25+ instruments. Current has 29. Check that all from the GUIA list are present.

**seed_series_metadata.py (117 series):**
GUIA Etapa 10 says "150-200+ series". Current has only **117**.
- [ ] **CRITICAL**: Need ~33-83 more series metadata entries to match GUIA target
- [ ] Verify all BCB SGS (~50), FRED (~50), Focus (~20), IBGE (~18), CFTC (~48), Flow (~4), Fiscal (~6) are represented
- [ ] The CFTC series alone should be ~48 (12 contracts x 4 categories) - likely underrepresented

---

## SECTION 3: TRANSFORM (SILVER LAYER) GAPS

### 3.1 Current Transforms

| File | Functions | Status |
|------|-----------|--------|
| curves.py | Nelson-Siegel, interpolate, breakeven, forward rate, DV01, carry/rolldown | Implemented |
| returns.py | Returns, rolling vol, z-score, percentile, correlation, EMA, Sharpe, drawdown, realized vol | Implemented |
| macro.py | YoY from MoM, diffusion, trimmed mean, surprise index, momentum | Implemented |
| vol_surface.py | Smile reconstruction, IV/RV ratio, vol slope | Implemented |

### 3.2 Missing Transforms

- [ ] **LOW**: `src/transforms/statistics.py` - Referenced in ARCHITECTURE.md recommended structure (rolling stats, seasonal decomposition)
- [ ] **LOW**: Missing test for vol_surface transforms (`test_vol_surface.py` not found in tests/)

---

## SECTION 4: API GAPS

### 4.1 Current API Routes

| Route File | Endpoints | Status |
|-----------|-----------|--------|
| health.py | GET /health, GET /health/data-status | Implemented |
| macro.py | GET /api/v1/macro/{series_id}, GET /api/v1/macro/dashboard, GET /api/v1/macro/search | Implemented |
| curves.py | GET /api/v1/curves/{curve_id}, GET /api/v1/curves/{curve_id}/history, GET /api/v1/curves/available | Implemented |
| market_data.py | GET /api/v1/market-data/{ticker}, GET /api/v1/market-data/latest | Implemented |
| flows.py | GET /api/v1/flows/{series_id}, GET /api/v1/flows/positioning-summary | Implemented |

### 4.2 API Gaps per Blueprint/GUIA

- [ ] **MEDIUM**: Missing `src/api/schemas/` directory - No Pydantic v2 response models (GUIA Etapa 13 requires Pydantic v2 response models)
- [ ] **MEDIUM**: Verify `point_in_time` query parameter on macro endpoint (GUIA: `?pit=true` for PIT queries)
- [ ] **LOW**: Missing Swagger tags organization (GUIA Etapa 13)

---

## SECTION 5: INFRASTRUCTURE GAPS

### 5.1 Docker Compose

**Current (5 services):** timescaledb, redis, mongodb, kafka, minio

**Blueprint/GUIA (6 services):** timescaledb, redis, mongodb, **zookeeper**, kafka, minio

**Differences:**
- Current Kafka uses KRaft mode (no Zookeeper needed) - this is actually **better** than the GUIA spec which uses Zookeeper. KRaft is the modern approach. No gap.
- Kafka has `profiles: [full]` - only starts with `docker compose --profile full up`. This is good for development.

### 5.2 Missing Infrastructure Files

- [ ] **LOW**: `infrastructure/scripts/init_timescaledb.sql` - Referenced in GUIA but TimescaleDB init is in Alembic migration (acceptable)
- [ ] **LOW**: `infrastructure/scripts/init_kafka_topics.sh` - Referenced in GUIA (Phase 0 doesn't use Kafka topics yet - Anti-Feature)

### 5.3 Missing Project Files

- [ ] **MEDIUM**: `src/core/exceptions.py` - Custom exception classes (DataIngestionError, StaleDataError, ConnectorError, etc.)
- [ ] **LOW**: `src/api/schemas/` directory - Pydantic response/request models
- [ ] **LOW**: `src/cache/` directory - Redis caching layer (Anti-Feature for Phase 0 per FEATURES.md, but ARCHITECTURE.md recommends it)
- [ ] **LOW**: `src/orchestration/` directory - Scheduler (Anti-Feature for Phase 0)

---

## SECTION 6: DATA QUALITY & GOVERNANCE GAPS

### 6.1 Current Quality Module

`quality/checks.py` implements:
- Completeness check (staleness by frequency)
- Accuracy check (range validation for ~17 series)
- Curve integrity check
- Point-in-time correctness check
- Composite score

`quality/alerts.py` exists.

### 6.2 Blueprint Quality Framework (Section 14)

**Missing checks:**
- [ ] **MEDIUM**: Z-score anomaly detection (|z| > 5 in 252d window) - GUIA Etapa 14 specifies this
- [ ] **MEDIUM**: Cross-source consistency (e.g., BCB PTAX vs Yahoo USDBRL should be within 0.1%)
- [ ] **MEDIUM**: `data_quality_log` table for tracking ingestion run results
- [ ] **LOW**: Timeliness check per provider SLA
- [ ] **LOW**: Uniqueness/duplicate detection
- [ ] **LOW**: Data lineage tracking

---

## SECTION 7: SCRIPT GAPS

### 7.1 Current Scripts

| Script | Purpose | Status |
|--------|---------|--------|
| seed_instruments.py | Seed instruments table | Implemented |
| seed_series_metadata.py | Seed series metadata | Implemented (117 series, target: 150+) |
| backfill.py | Historical data ingestion | Implemented |
| verify_infrastructure.py | System verification | Implemented |
| verify_connectivity.py | API connectivity test | Implemented |

### 7.2 Missing/Incomplete Scripts

- [ ] **MEDIUM**: `seed_series_metadata.py` needs 33-83 more series entries (currently 117, GUIA says 150-200+)
- [ ] **LOW**: Verify `backfill.py` handles all 11 connectors with proper error handling and summary report

---

## SECTION 8: PITFALLS CHECKLIST (from PITFALLS.md)

### 8.1 Critical Pitfalls - Verification Status

| # | Pitfall | Status | Verification |
|---|---------|--------|-------------|
| P-1 | Point-in-time look-ahead bias | OK | `release_time` column exists in macro_series, flow_data, fiscal_data |
| P-2 | Free API fragility | OK | BaseConnector has retry logic, rate limiting |
| P-3 | Brazilian data format misinterpretation | VERIFY | BCB uses comma decimal, DD/MM/YYYY dates - check parsing |
| P-4 | TimescaleDB compression destroying backfill | OK | Compression policies have generous delays (30-180 days) |
| P-5 | Curve construction from proxy data | VERIFY | DI swap proxies (SGS 7805-7816) documented as approximation |
| P-6 | Timezone misalignment | VERIFY | Check that all TIMESTAMPTZ columns handle BRT/EST correctly |
| P-7 | Non-idempotent backfill | OK | ON CONFLICT DO NOTHING / unique constraints on all tables |

### 8.2 "Looks Done But Isn't" Checklist

- [ ] **VERIFY**: Are all 50 BCB SGS series actually fetching data correctly?
- [ ] **VERIFY**: Are all 50 FRED series saving with correct release_time?
- [ ] **VERIFY**: Is revision_number being used for revisable series (GDP, NFP, PCE)?
- [ ] **VERIFY**: Does backfill.py split BCB requests into 5-year batches?
- [ ] **VERIFY**: Does CFTC connector download and parse zip files correctly?
- [ ] **VERIFY**: Does Treasury.gov connector handle CSV format correctly?

---

## SECTION 9: WHAT'S EXPLICITLY OUT OF SCOPE (Anti-Features)

Per FEATURES.md, these are **NOT** needed for Phase 0:

- No Kafka streaming pipelines (Kafka container exists but no producers/consumers)
- No MongoDB schemas (container exists but no collections)
- No MinIO pipelines (container exists but no buckets/objects)
- No feature store (Feast/Hopsworks)
- No authentication/authorization
- No React frontend dashboard
- No Bloomberg/Refinitiv connectors
- No tick data ingestion
- No execution system
- No Airflow/Dagster orchestration (simple scripts suffice)
- No pgvector/embeddings
- No NLP pipeline
- No G5 extension data (EUR, GBP, JPY, CHF central banks)
- No alternative data (Google Trends, satellite, etc.)

---

## SECTION 10: PRIORITIZED ACTION PLAN

### Priority 1 - CRITICAL (Must fix before Phase 1)

1. **Add `instrument_type` and `contract_specs` to instruments table**
   - Create Alembic migration
   - Update ORM model
   - Update seed_instruments.py with instrument_type for all 29 instruments
   - Impact: Phase 1 strategies need instrument_type to distinguish futures vs spot vs ETF

2. **Expand seed_series_metadata.py to 150+ entries**
   - Add missing CFTC series (~48: 12 contracts x 4 categories)
   - Add missing Focus derived series
   - Add all IBGE group series (MoM + weights)
   - Target: match GUIA Etapa 10 specification

3. **Create ANBIMA connector placeholder**
   - `src/connectors/anbima.py` with placeholder class
   - Document ANBIMA ETTJ access plans
   - Per GUIA Etapa 7 requirement

### Priority 2 - MEDIUM (Should fix for robustness)

4. **Add missing columns to market_data table**
   - `open_interest` (BigInteger) for futures
   - `bid`/`ask` (Float) for FX (PTAX uses these)
   - `ingestion_ts` (DateTime) for pipeline monitoring
   - Create Alembic migration

5. **Add `dv01` column to curves table**
   - Needed by Rate strategies for DV01-neutral positioning
   - Create Alembic migration

6. **Enhance enums.py**
   - Add domain-specific asset classes (RATES_BR, INFLATION_BR, CUPOM_CAMBIAL, SOVEREIGN_CREDIT)
   - Add InstrumentType enum
   - Add TICK, BIWEEKLY to Frequency

7. **Create `src/core/exceptions.py`**
   - DataIngestionError, StaleDataError, ConnectorError, QualityCheckError
   - Used by connectors and quality module

8. **Create `src/api/schemas/` directory**
   - Pydantic v2 response models for all endpoints
   - Improve API documentation in Swagger

9. **Enhance quality checks**
   - Add z-score anomaly detection (|z| > 5)
   - Add cross-source consistency check
   - Add data_quality_log table

10. **Add `maturity_date` to instruments table**
    - Needed for futures contract roll logic

### Priority 3 - LOW (Nice to have)

11. Add `ingestion_ts` to all hypertables
12. Add `strike_type` to vol_surfaces
13. Create `src/transforms/statistics.py`
14. Add vol_surface transform tests
15. Create infrastructure SQL/shell scripts
16. Verify Brazilian data format parsing in all connectors

---

## APPENDIX A: File Inventory

### Source Files (44 Python files)
```
src/api/         - 6 files (main.py, deps.py, 4 routes)
src/connectors/  - 12 files (base.py + 11 connectors)
src/core/        - 16 files (config, database, redis, enums, 10 models, 4 utils)
src/quality/     - 2 files (checks.py, alerts.py)
src/transforms/  - 4 files (curves, returns, macro, vol_surface)
```

### Test Files (18 files, 319 tests)
```
tests/connectors/  - 12 files (conftest + 11 connector tests)
tests/test_transforms/ - 3 files (curves, returns, macro)
tests/utils/       - 3 files (calendars, parsing, tenors)
```

### Scripts (5 files)
```
scripts/seed_instruments.py
scripts/seed_series_metadata.py
scripts/backfill.py
scripts/verify_infrastructure.py
scripts/verify_connectivity.py
```

### Infrastructure
```
alembic/versions/001_initial_schema.py
docker-compose.yml (5 services)
pyproject.toml
Makefile
.env.example
.gitignore
README.md
```
