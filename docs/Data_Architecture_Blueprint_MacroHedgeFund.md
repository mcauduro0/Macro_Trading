### MACRO HEDGE FUND AGENTIC AI SYSTEM

### DATA ARCHITECTURE &

### DATABASE INFRASTRUCTURE BLUEPRINT

Complete Catalog of Data Providers, Variables, Collection Frequencies,

Storage Architecture & Pipeline Design

### CONFIDENTIAL | February 2026

# TABLE OF CONTENTS

1. Data Architecture Overview & Design Principles

2. Database Technology Stack & Schema Design

3. Market Data - Prices, Curves & Surfaces (BR + US + G5)

4. Macroeconomic Data - Brasil

5. Macroeconomic Data - United States

6. Macroeconomic Data - G5 Extension (EUR, GBP, JPY, CHF)

7. Fiscal & Sovereign Risk Data

8. Flow & Positioning Data

9. Central Bank Communication & NLP Corpus

10. Alternative & High-Frequency Data

11. Reference & Static Data

12. Data Provider Matrix & Cost Estimates

13. Data Pipeline Architecture (ETL/ELT)

14. Data Quality, Governance & Monitoring

15. Storage Sizing & Infrastructure Requirements

# 1. DATA ARCHITECTURE OVERVIEW & DESIGN PRINCIPLES

The data infrastructure is the foundation upon which all analytical agents operate. The design follows principles established by leading quantitative hedge funds (Two Sigma, DE Shaw, Man AHL) and academic best practices in financial data engineering (Lopez de Prado, 2018; Dixon, Halperin & Bilokon, 2020).

### 1.1 Core Design Principles

- Single Source of Truth (SSOT): Each data variable has exactly one authoritative source, one canonical schema, and one point of ingestion. All agents read from the same database, eliminating inconsistencies.

- Immutability & Versioning: Raw data is never modified after ingestion. Corrections are appended as new records with timestamps. This enables full auditability and reproducibility of any historical analysis or backtest (point-in-time database).

- Point-in-Time Correctness: All queries can be executed 'as of' any historical date, seeing only data that was available at that time. This prevents look-ahead bias in backtesting - the most critical requirement for quantitative research (Harvey, Liu & Zhu, 2016).

- Separation of Raw, Processed & Derived: Three-layer architecture: (1) Bronze Layer (raw ingestion, exact copy from source); (2) Silver Layer (cleaned, validated, standardized); (3) Gold Layer (derived variables, model outputs, signals). Each layer has independent storage and access controls.

- Low-Latency Access: Frequently accessed data (last 2 years, daily frequency) is kept in hot storage with sub-100ms query time. Historical data is in warm/cold storage with higher latency tolerance.

- Schema-on-Read Flexibility: While core financial time series use structured schemas, unstructured data (central bank communications, news, filings) uses semi-structured storage with indexing for NLP processing.

### 1.2 Data Classification

| Category | Volume (est.) | Frequency | Latency Req. | Retention |
|---|---|---|---|---|
| Market Prices & Curves | ~50GB/year | Tick to Daily | <1 second | Full history (20+ years) |
| Macroeconomic Series | ~2GB/year | Daily to Quarterly | <1 hour | Full history (30+ years) |
| Fiscal & Sovereign | ~500MB/year | Daily to Monthly | <1 hour | Full history (20+ years) |
| Flow & Positioning | ~1GB/year | Daily to Weekly | <4 hours | Full history (15+ years) |
| Central Bank NLP Corpus | ~5GB total | Per event | <30 min | Full history (all available) |
| Alternative Data | ~10GB/year | Variable | Variable | Rolling 5 years |
| Reference / Static | ~100MB | On change | N/A | Current + history |
| Model Outputs & Signals | ~20GB/year | Daily | N/A | Full history |

# 2. DATABASE TECHNOLOGY STACK & SCHEMA DESIGN

### 2.1 Technology Selection

The database architecture uses a polyglot persistence approach, selecting the optimal database technology for each data type:

| Component | Technology | Purpose | Justification |
|---|---|---|---|
| Time Series DB | TimescaleDB (PostgreSQL extension) | All financial time series, curves, prices | SQL-compatible, hypertables with automatic partitioning, native time-series functions, compression (95%+), continuous aggregates. Benchmark: 10-100x faster than vanilla PostgreSQL for time-range queries. |
| Relational DB | PostgreSQL 16+ | Reference data, metadata, configurations, audit logs | ACID compliance, JSON support, mature ecosystem, seamless integration with TimescaleDB. |
| Document Store | MongoDB 7.0+ or Elasticsearch | Central bank communications, news articles, NLP corpus | Flexible schema for unstructured text, full-text search, vector search for semantic queries. |
| Cache Layer | Redis 7.0+ (with Redis TimeSeries) | Hot data cache, real-time prices, current positions | Sub-millisecond latency, pub/sub for real-time updates to agents, TTL-based expiration. |
| Object Storage | MinIO (S3-compatible) or AWS S3 | Raw file archives (PDFs, CSVs, XMLs from providers) | Cost-effective for large files, immutable storage, lifecycle policies. |
| Vector DB | pgvector (PostgreSQL extension) | Embeddings for NLP semantic search | Integrated with PostgreSQL, no separate infrastructure, HNSW indexing. |
| Message Queue | Apache Kafka | Real-time data streaming between ingestion and processing | Exactly-once semantics, high throughput, replay capability for reprocessing. |

### 2.2 Core Schema Design

The TimescaleDB schema follows a star-schema approach with hypertables for time series data and dimension tables for metadata.

### 2.2.1 Master Instrument Table

Every tradeable instrument and data series is registered in a master table:

- instrument_id (PK): UUID - unique identifier

- ticker: VARCHAR - Bloomberg/B3/CME ticker (e.g., 'DI1F26', 'USDBRL Curncy', 'ZN1')

- asset_class: ENUM - FX, RATES_BR, RATES_US, RATES_G5, INFLATION_BR, INFLATION_US, CUPOM_CAMBIAL, SOVEREIGN_CREDIT, COMMODITIES, EQUITY_INDEX

- instrument_type: ENUM - FUTURE, BOND, SWAP, OPTION, CDS, NDF, SPOT, INDEX, ETF

- currency: VARCHAR(3) - BRL, USD, EUR, etc.

- exchange: VARCHAR - B3, CME, EUREX, ICE, OTC

- maturity_date: DATE - for dated instruments

- contract_specs: JSONB - multiplier, tick size, margin, settlement type

- is_active: BOOLEAN

- created_at, updated_at: TIMESTAMPTZ

### 2.2.2 Time Series Hypertable (Prices)

- time: TIMESTAMPTZ (partition key) - observation timestamp

- instrument_id: UUID (FK) - reference to master table

- open, high, low, close: DOUBLE PRECISION

- volume: BIGINT

- open_interest: BIGINT (for futures)

- bid, ask: DOUBLE PRECISION (for OTC instruments)

- source: VARCHAR - data provider identifier

- ingestion_time: TIMESTAMPTZ - when the data was ingested (for point-in-time queries)

### 2.2.3 Curve Hypertable

- time: TIMESTAMPTZ - observation date

- curve_id: VARCHAR - identifier (e.g., 'DI_PRE', 'DDI_CUPOM', 'NTN_B_REAL', 'UST_NOMINAL')

- tenor: VARCHAR - maturity point (e.g., '3M', '1Y', '5Y', '10Y', or specific date 'Jan26')

- tenor_days: INTEGER - days to maturity (for continuous representation)

- rate: DOUBLE PRECISION - yield/rate at that point

- dv01: DOUBLE PRECISION - dollar value of 1bp

- source: VARCHAR

### 2.2.4 Volatility Surface Hypertable

- time: TIMESTAMPTZ

- underlying: VARCHAR - e.g., 'USDBRL', 'DI'

- expiry: DATE - option expiration

- strike_type: ENUM - DELTA, ABSOLUTE, MONEYNESS

- strike_value: DOUBLE PRECISION - e.g., 25 (for 25-delta), or absolute strike

- call_put: ENUM - CALL, PUT, STRADDLE

- implied_vol: DOUBLE PRECISION

- source: VARCHAR

### 2.2.5 Macroeconomic Series Hypertable

- time: TIMESTAMPTZ - reference period (e.g., month for CPI)

- release_time: TIMESTAMPTZ - actual publication time (critical for point-in-time)

- series_id: VARCHAR - unique series identifier (e.g., 'BR_IPCA_MOM', 'US_CPI_CORE_YOY')

- value: DOUBLE PRECISION

- revision_number: INTEGER - 0 for first release, 1 for first revision, etc.

- source: VARCHAR

### 2.2.6 NLP Document Store (MongoDB Schema)

- _id: ObjectId

- doc_type: ENUM - COPOM_ATA, COPOM_COMUNICADO, FOMC_STATEMENT, FOMC_MINUTES, SPEECH, PRESS_CONFERENCE

- institution: ENUM - BCB, FED, ECB, BOJ, BOE, SNB

- date: ISODate - event date

- title: String

- raw_text: String - full text content

- language: String - 'pt-BR', 'en-US'

- nlp_scores: Object - { hawkish_score, sentiment, uncertainty_index, key_phrases[] }

- embedding: Array<Float> - vector embedding (1536 dimensions for ada-002 or equivalent)

- metadata: Object - { meeting_number, vote_split, dissents[], signatories[] }

# 3. MARKET DATA - PRICES, CURVES & SURFACES

This section catalogs every market data variable required, organized by asset class. For each variable, we specify: the exact series/ticker, the source provider, collection frequency, and which agents consume the data.

## 3.1 BRAZIL - B3 / BCB / Bloomberg

### 3.1.1 DI Futures Curve (Curva Pre)

The DI1 futures curve is the backbone of Brazilian fixed income. Each contract settles on the first business day of the reference month at the CDI (Certificado de Deposito Interbancario) accumulated rate.

| Variable | Frequency | Source & Access Method |
|---|---|---|
| DI1 futures settlement prices (all active vertices ~30+) | Daily (EOD) | B3 Market Data (FTP/API) - file PUWEB. Also Bloomberg (DI1 <Govt> CT). |
| DI1 intraday prices (bid/ask/last) | Tick (real-time) | B3 UMDF feed (FIX protocol) or Bloomberg real-time. |
| DI1 open interest by contract | Daily | B3 Market Data - file CONTFUT. |
| DI1 volume by contract | Daily + Intraday | B3 Market Data + UMDF feed. |
| DI1 settlement curve (zero-coupon rates) | Daily | B3 calculates and publishes. ANBIMA also publishes 'Estrutura a Termo das Taxas de Juros' (ETTJ). |
| IDI options (opcoes sobre IDI) - prices, vol, greeks | Daily | B3 Market Data + Bloomberg. |

### 3.1.2 Cupom Cambial Curve (DDI / FRC)

| Variable | Frequency | Source & Access Method |
|---|---|---|
| DDI futures settlement prices (all active vertices) | Daily | B3 Market Data - file PUWEB. |
| FRC (FRA de Cupom Cambial) settlement prices | Daily | B3 Market Data. |
| DDI/FRC intraday prices | Tick | B3 UMDF feed. |
| DDI open interest and volume by contract | Daily | B3 Market Data - file CONTFUT. |
| Cupom Cambial zero-coupon curve | Daily | B3/ANBIMA ETTJ for cupom cambial. |
| Casado (spread spot vs. DOL futuro) | Intraday | B3 real-time calculation or Bloomberg. |

### 3.1.3 Inflation-Linked Bonds (NTN-B / Cupom de Inflacao)

| Variable | Frequency | Source & Access Method |
|---|---|---|
| NTN-B indicative rates (all active maturities ~15+) | Daily | ANBIMA (publishes reference rates) + B3 secondary market. |
| NTN-B secondary market prices (bid/ask/last) | Daily | Bloomberg (BZRFBMP Index for curves), dealers. |
| NTN-B DV01, duration, convexity by maturity | Daily | Calculated internally from ANBIMA rates + bond math. |
| Breakeven inflation (implicita) per vertex | Daily | Calculated: NTN-F rate - NTN-B real rate (Fisher equation). |
| LTN / NTN-F indicative rates (all maturities) | Daily | ANBIMA + B3 secondary market. |
| NTN-B accrual (VNA - Valor Nominal Atualizado) | Daily | B3 / STN publishes based on IPCA. |
| Inflation-linked curve (real zero-coupon rates) | Daily | ANBIMA ETTJ for NTN-B. |

### 3.1.4 FX - USDBRL

| Variable | Frequency | Source & Access Method |
|---|---|---|
| USDBRL spot rate (PTAX) | Daily (4 fixings) | BCB SGS (serie 1) - official PTAX rate (buy/sell). |
| USDBRL intraday spot | Tick | Bloomberg (BRL Curncy), Refinitiv, EBS. |
| DOL futures (dolar comercial futuro) settlement | Daily | B3 Market Data - PUWEB. |
| WDO (mini dolar) settlement | Daily | B3 Market Data. |
| DOL/WDO intraday prices | Tick | B3 UMDF feed. |
| DOL open interest and volume | Daily + Intraday | B3 Market Data + UMDF. |
| NDF USDBRL (offshore) 1M, 3M, 6M, 1Y | Daily | Bloomberg (BRL1M, BRL3M, etc.), Refinitiv, DTCC. |
| USDBRL options - vol surface (ATM, 25D, 10D RR, BF) | Daily | Bloomberg (USDBRLV surface), dealers. |
| USDBRL options - all listed strikes B3 | Daily | B3 Market Data. |
| USDBRL realized volatility (5d, 21d, 63d, 252d) | Daily | Calculated from spot returns. |
| USDBRL forward points (tom, 1W, 1M, 3M, 6M, 1Y) | Daily | Bloomberg, dealers. |

### 3.1.5 Sovereign Credit - Brazil

| Variable | Frequency | Source & Access Method |
|---|---|---|
| CDS Brazil 5Y (USD, ISDA standard) | Daily + Intraday | Bloomberg (CBRA1U5 Curncy), Markit, DTCC. |
| CDS Brazil 1Y, 2Y, 3Y, 7Y, 10Y | Daily | Bloomberg, Markit. |
| CDS Brazil recovery rate assumption | On change | Markit (standard 25% for EM sovereigns). |
| EMBI+ Brazil spread | Daily | JPMorgan (Bloomberg: JPMBRBRD Index). |
| Global bonds Brazil (USD) - prices all maturities | Daily | Bloomberg (BZSOVRN <Govt>), Refinitiv. |
| Global bonds Brazil - Z-spread, ASW spread | Daily | Bloomberg analytics. |
| Sovereign rating Brazil (Moody's, S&P, Fitch) | On change | Rating agencies, Bloomberg. |

## 3.2 UNITED STATES - CME / Treasury / Bloomberg

### 3.2.1 Treasury Curve & Futures

| Variable | Frequency | Source & Access Method |
|---|---|---|
| US Treasury yields (2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y) | Daily | FRED (DGS2, DGS5, DGS10, DGS30), Bloomberg, Treasury.gov. |
| US Treasury zero-coupon curve (Gurkaynak-Sack-Wright) | Daily | Federal Reserve (GSW parameters published on Fed website). |
| Treasury futures (ZT, ZF, ZN, ZB, UB) settlement | Daily | CME Group Market Data. |
| Treasury futures intraday | Tick | CME Globex, Bloomberg. |
| Treasury futures volume and open interest | Daily | CME Daily Bulletin. |
| TIPS yields (5Y, 7Y, 10Y, 20Y, 30Y) | Daily | FRED (DFII5, DFII10, etc.), Bloomberg. |
| US breakeven inflation (5Y, 10Y, 30Y) | Daily | FRED (T5YIE, T10YIE, T30YIEM), calculated. |
| Treasury auction results (yield, bid-to-cover, allocation) | Per auction (~weekly) | Treasury.gov TreasuryDirect, Bloomberg. |

### 3.2.2 Money Market & Fed Funds

| Variable | Frequency | Source & Access Method |
|---|---|---|
| Effective Federal Funds Rate (EFFR) | Daily | FRED (DFF), New York Fed. |
| SOFR (Secured Overnight Financing Rate) | Daily | FRED (SOFR), New York Fed. |
| SOFR futures (SR1, SR3) settlement prices | Daily | CME Group. |
| Fed Funds futures (ZQ) settlement prices | Daily | CME Group. |
| Fed Funds futures implied probabilities (all meetings) | Daily | Calculated from ZQ prices. CME FedWatch tool as validation. |
| SOFR futures open interest and volume | Daily | CME Daily Bulletin. |
| SOFR-FF spread (funding stress indicator) | Daily | Calculated. |
| FRA-OIS spread (credit/liquidity stress) | Daily | Bloomberg. |
| Reverse Repo Facility usage (ON RRP) | Daily | New York Fed. |
| Bank reserves at Federal Reserve | Weekly (H.4.1) | Federal Reserve Statistical Release. |

### 3.2.3 FX - G10 (Phase G5 Extension)

| Variable | Frequency | Source & Access Method |
|---|---|---|
| DXY (US Dollar Index) | Tick / Daily | ICE, Bloomberg (DXY Index). |
| EURUSD, USDJPY, GBPUSD, USDCHF spot | Tick / Daily | Bloomberg, Refinitiv, EBS. |
| G10 FX forward points (1M, 3M, 6M, 1Y) | Daily | Bloomberg, Refinitiv. |
| G10 FX options vol surfaces (ATM, 25D RR, 25D BF) | Daily | Bloomberg (e.g., EURUSDV), Refinitiv. |
| G10 FX realized vol (5d, 21d, 63d) | Daily | Calculated. |
| Cross-currency basis swaps (XCCY 3M, 1Y, 5Y) EUR, JPY, GBP, CHF vs. USD | Daily | Bloomberg, dealers. |

### 3.2.4 US Credit & Volatility Indices

| Variable | Frequency | Source & Access Method |
|---|---|---|
| VIX (CBOE Volatility Index) | Tick / Daily | CBOE, Bloomberg (VIX Index). |
| MOVE Index (Merrill Lynch Option Vol Estimate - rates) | Daily | Bloomberg (MOVE Index). |
| CDX.IG (US Investment Grade CDS Index) | Daily | Markit, Bloomberg. |
| CDX.EM (Emerging Markets CDS Index) | Daily | Markit, Bloomberg. |
| HY OAS (High Yield Option-Adjusted Spread) | Daily | FRED (BAMLH0A0HYM2), Bloomberg. |
| IG OAS (Investment Grade OAS) | Daily | FRED (BAMLC0A0CM), Bloomberg. |

## 3.3 COMMODITIES & GLOBAL RISK INDICATORS

| Variable | Frequency | Source & Access Method |
|---|---|---|
| CRB Index (Thomson Reuters/CoreCommodity) | Daily | Bloomberg (CRY Index), Refinitiv. |
| Iron Ore 62% Fe (Platts/SGX) | Daily | Bloomberg (IODBZ00 Index), Platts. |
| Soybean (CBOT ZS1) | Daily / Tick | CME Group, Bloomberg. |
| Corn (CBOT ZC1) | Daily / Tick | CME Group, Bloomberg. |
| Crude Oil WTI (CL1) and Brent (CO1) | Daily / Tick | CME/ICE, Bloomberg. |
| Gold (GC1) | Daily / Tick | CME/COMEX, Bloomberg. |
| Copper (HG1) | Daily / Tick | CME/COMEX, Bloomberg. |
| Terms of Trade Brazil (custom basket: iron ore, soy, oil) | Daily | Calculated from component prices. |
| Baltic Dry Index (BDI) | Daily | Bloomberg (BDIY Index). |
| Global PMI Composite (JPMorgan/S&P Global) | Monthly | Bloomberg, S&P Global. |
| VIX Term Structure (VX1-VX8) | Daily | CBOE, Bloomberg. |

# 4. MACROECONOMIC DATA - BRAZIL

All Brazilian macroeconomic data is sourced primarily from the BCB (Sistema Gerenciador de Series Temporais - SGS), IBGE, and the Ministry of Finance/STN. The BCB SGS system provides programmatic API access (JSON/XML) to over 40,000 time series. IBGE provides SIDRA API access.

### 4.1 Inflation

| Variable / Series | Frequency | Source | Details & SGS Code |
|---|---|---|---|
| IPCA headline (MoM, YoY) | Monthly | IBGE / BCB SGS | SGS #433 (MoM). ~15th of following month. Main inflation target metric. |
| IPCA by group (9 groups) | Monthly | IBGE SIDRA | Alimentacao, Habitacao, Artigos de Residencia, Vestuario, Transportes, Saude, Despesas Pessoais, Educacao, Comunicacao. |
| IPCA by subgroup (~50 subitems) | Monthly | IBGE SIDRA | Essential for bottom-up inflation model. Each subitem has weight and MoM variation. |
| IPCA Diffusion Index | Monthly | BCB / Calculated | % of subitems with positive variation. SGS #21379. |
| IPCA Core measures (5 measures) | Monthly | BCB | EX0 (excluding food & energy), EX3, MA (trimmed mean), DP (double weight), P55 (55% trimmed). SGS #11426, #11427, #27838, #27839, #4466. |
| IPCA-15 (preview) | Monthly | IBGE / BCB SGS | SGS #7478. Released ~2 weeks before IPCA. Key leading indicator. |
| IPC-S (weekly CPI, FGV) | Weekly | FGV / BCB SGS | SGS #7446. 4 weekly readings per month. Highest frequency CPI. |
| IPC-Fipe (Sao Paulo CPI) | Weekly | FIPE / BCB SGS | SGS #10764. Sao Paulo metropolitan area. Weekly readings. |
| IGP-M (General Price Index - Market) | Monthly | FGV / BCB SGS | SGS #189. Includes IPA (wholesale), IPC, INCC. Rent adjustment benchmark. |
| IGP-DI (General Price Index) | Monthly | FGV / BCB SGS | SGS #190. |
| IPA-M (Wholesale Price Index) | Monthly | FGV / BCB SGS | SGS #225. Leading indicator for CPI via pass-through. |
| INPC (National CPI) | Monthly | IBGE / BCB SGS | SGS #188. Used for minimum wage adjustment. |
| Inflation Expectations - Focus Survey (medians) | Weekly | BCB Focus | 12M, current year, next year, 2 years ahead, 3 years ahead. BCB publishes every Monday. |
| Inflation Expectations - Focus Survey (distribution) | Weekly | BCB Focus | Full distribution (percentiles) for disaggregated analysis. |
| Breakeven inflation market-implied (all vertices) | Daily | Calculated | From NTN-B vs. LTN/NTN-F rates. |

### 4.2 Economic Activity

| Variable / Series | Frequency | Source | Details & SGS Code |
|---|---|---|---|
| GDP (quarterly) | Quarterly | IBGE / BCB SGS | SGS #22099. Released ~60 days after quarter end. |
| IBC-Br (BCB Economic Activity Index) | Monthly | BCB SGS | SGS #24364. GDP monthly proxy. Key high-frequency indicator. |
| Industrial Production (PIM-PF) | Monthly | IBGE / BCB SGS | SGS #21859. Manufacturing output. |
| Retail Sales (PMC) | Monthly | IBGE / BCB SGS | SGS #1455 (core), #28473 (broad). |
| Services Sector Survey (PMS) | Monthly | IBGE / BCB SGS | SGS #23987. Revenue from services. |
| PMI Manufacturing (S&P Global) | Monthly | S&P Global / Bloomberg | Released first business day of month. Leading indicator. |
| PMI Services (S&P Global) | Monthly | S&P Global / Bloomberg | Released 3rd business day. |
| Consumer Confidence (ICC - FGV) | Monthly | FGV | SGS #4393. Leading indicator of consumption. |
| Business Confidence (ICE - FGV) | Monthly | FGV | SGS #7343. |
| Vehicle Production (ANFAVEA) | Monthly | ANFAVEA | Cars, trucks, buses. Proxy for industrial activity. |
| Electricity Consumption (ONS) | Daily / Weekly | ONS | High-frequency proxy for economic activity. |
| Toll Road Traffic (ABCR) | Monthly | ABCR | Economic activity proxy. |
| CAGED (Formal Employment) | Monthly | Min. Trabalho / BCB SGS | SGS #28763. Net formal job creation. |
| PNAD Continua (Unemployment Rate) | Quarterly (monthly available) | IBGE / BCB SGS | SGS #24369. Broad labor market. |
| Real Wage (PNAD) | Quarterly | IBGE | Average real earnings. |
| Output Gap estimate (BCB) | Quarterly | BCB Inflation Report | BCB's own estimate of output gap. |
| Capacity Utilization (CNI/FGV) | Monthly | CNI / FGV | SGS #1344. Inflationary pressure indicator. |

### 4.3 Monetary Policy & Credit

| Variable / Series | Frequency | Source | Details & SGS Code |
|---|---|---|---|
| SELIC Target Rate | Per COPOM meeting (8x/year) | BCB SGS | SGS #432. Official policy rate. |
| SELIC Effective Rate (daily) | Daily | BCB SGS | SGS #11. Actual overnight interbank rate. |
| CDI Rate (daily) | Daily | B3 / BCB SGS | SGS #12. Reference rate for DI market. |
| COPOM Minutes (Atas) | Per meeting + 6 business days | BCB website | Full text for NLP analysis. |
| COPOM Statement (Comunicado) | Per meeting (same day) | BCB website | Shorter, first release. NLP analysis. |
| BCB Inflation Report (Relatorio de Inflacao) | Quarterly | BCB website | Detailed projections, fan charts, scenarios. |
| Focus Survey - SELIC expectations | Weekly | BCB Focus | Median and distribution for current year + 1-3 years ahead. |
| Focus Survey - GDP expectations | Weekly | BCB Focus | SGS #4382 (current year), #4383 (next year). |
| Focus Survey - Exchange Rate expectations | Weekly | BCB Focus | SGS #4384 (current year). |
| Broad Credit (SFN) | Monthly | BCB SGS | SGS #20539. Total credit to GDP. Growth rate. |
| Credit Default Rate (inadimplencia) | Monthly | BCB SGS | SGS #21082 (individuals), #21083 (corporates). |
| Average Lending Rate (taxa media) | Monthly | BCB SGS | SGS #20714. Spread over SELIC. |
| Monetary Base (base monetaria) | Monthly | BCB SGS | SGS #1788. |
| M1, M2, M3, M4 Monetary Aggregates | Monthly | BCB SGS | SGS #1824 (M1), #1837 (M2), #1838 (M3), #1839 (M4). |

### 4.4 External Sector

| Variable / Series | Frequency | Source | Details & SGS Code |
|---|---|---|---|
| Trade Balance (monthly) | Monthly (daily preliminary) | MDIC/SECEX / BCB SGS | SGS #22707 (monthly). Daily flash available from SECEX. |
| Current Account Balance | Monthly | BCB SGS | SGS #22885. USD millions. |
| Current Account / GDP (%) | Monthly (12M rolling) | BCB SGS | SGS #22918. |
| Foreign Direct Investment (IDP) | Monthly | BCB SGS | SGS #22886. |
| Portfolio Investment (equity + debt) | Monthly | BCB SGS | SGS #22888 (equity), #22889 (debt). |
| International Reserves (total, USD) | Daily | BCB SGS | SGS #13621. BCB publishes daily. |
| Foreign Exchange Flow (commercial + financial) | Weekly | BCB | Published every Wednesday. Commercial flow + financial flow separately. |
| Foreign Exchange Flow - detailed (by type) | Monthly | BCB | Breakdown: trade, financial, intercompany, portfolio, etc. |
| External Debt (public + private) | Quarterly | BCB | Gross external debt by sector and maturity. |
| PTAX (official exchange rate, buy/sell) | Daily (4 fixings) | BCB SGS | SGS #1 (buy), #10813 (sell). Used for financial contract settlement. |
| BCB FX Intervention (swap cambial stock) | Daily | BCB | Outstanding notional of BCB FX swaps. Critical for cupom cambial model. |
| BCB FX Intervention (spot, repo, swap auctions) | Per event | BCB | Auction announcements, results, amounts. |

# 5. MACROECONOMIC DATA - UNITED STATES

US macroeconomic data is sourced primarily from FRED (Federal Reserve Economic Data - St. Louis Fed), which provides programmatic API access to over 800,000 time series. Additional sources include BLS, BEA, Census Bureau, and ISM.

### 5.1 Inflation

| Variable / Series | Frequency | Source | FRED Code / Details |
|---|---|---|---|
| CPI All Items (MoM, YoY, SA, NSA) | Monthly | BLS / FRED | CPIAUCSL (SA), CPIAUCNS (NSA). Released ~10-13th. |
| CPI Core (ex Food & Energy) | Monthly | BLS / FRED | CPILFESL. Fed's secondary target metric. |
| CPI by component (8 major groups) | Monthly | BLS | Food, Energy, Shelter, Apparel, Transportation, Medical, Recreation, Education. |
| CPI Shelter (OER + Rent) | Monthly | BLS / FRED | CUSR0000SEHC. Critical lagging component. |
| CPI Supercore (services ex shelter) | Monthly | BLS / Calculated | Fed's preferred measure of underlying inflation. |
| CPI Trimmed Mean (Cleveland Fed) | Monthly | Cleveland Fed / FRED | TRMMEANCPIM158SFRBCLE. 16% trimmed. |
| CPI Median (Cleveland Fed) | Monthly | Cleveland Fed / FRED | MEDCPIM158SFRBCLE. |
| CPI Sticky vs. Flexible (Atlanta Fed) | Monthly | Atlanta Fed / FRED | STICKCPIM157SFRBATL, FLEXCPIM157SFRBATL. |
| PCE Price Index (headline) | Monthly | BEA / FRED | PCEPI. Fed's primary inflation target. |
| PCE Core (ex food & energy) | Monthly | BEA / FRED | PCEPILFE. The metric the FOMC targets at 2%. |
| PPI (Producer Price Index) | Monthly | BLS / FRED | PPIACO. Leading indicator for CPI. |
| Import/Export Price Indices | Monthly | BLS / FRED | IR, IE. Pass-through channel. |
| Michigan Survey - Inflation Expectations (1Y, 5Y) | Monthly | U. Michigan / FRED | MICH (1Y), UMCSENT (5-10Y). |
| NY Fed Survey - Inflation Expectations (1Y, 3Y) | Monthly | NY Fed | Published monthly with full distribution. |
| TIPS Breakeven (5Y, 10Y, 30Y) | Daily | FRED / Calculated | T5YIE, T10YIE. Market-implied inflation. |
| 5Y5Y Forward Inflation Expectation | Daily | FRED | T5YIFR. Fed's preferred long-term measure. |

### 5.2 Economic Activity & Labor Market

| Variable / Series | Frequency | Source | FRED Code / Details |
|---|---|---|---|
| GDP (advance, second, third estimates) | Quarterly | BEA / FRED | GDP, GDPC1 (real). Released ~30d, 60d, 90d after quarter. |
| GDP Nowcast (Atlanta Fed GDPNow) | ~Weekly during quarter | Atlanta Fed | Real-time model estimate. Updated with each data release. |
| GDP Nowcast (NY Fed Nowcast) | Weekly | NY Fed | Alternative nowcast for cross-validation. |
| Nonfarm Payrolls (total + private) | Monthly | BLS / FRED | PAYEMS, USPRIV. Released first Friday. Most market-moving release. |
| Unemployment Rate (U3, U6) | Monthly | BLS / FRED | UNRATE (U3), U6RATE. |
| Average Hourly Earnings (MoM, YoY) | Monthly | BLS / FRED | CES0500000003. Wage inflation proxy. |
| Employment Cost Index (ECI) | Quarterly | BLS / FRED | ECIWAG. Broader wage measure. |
| JOLTS (Job Openings, Quits Rate) | Monthly | BLS / FRED | JTSJOL (openings), JTSQUR (quits rate). |
| Initial Jobless Claims (weekly) | Weekly | DOL / FRED | ICSA. High-frequency labor market indicator. |
| Continuing Claims | Weekly | DOL / FRED | CCSA. |
| ISM Manufacturing PMI | Monthly | ISM / Bloomberg | Released first business day. Key leading indicator. |
| ISM Services PMI | Monthly | ISM / Bloomberg | Released third business day. |
| ISM Prices Paid (Manufacturing) | Monthly | ISM / Bloomberg | Leading inflation indicator. |
| Industrial Production (IP) | Monthly | Federal Reserve / FRED | INDPRO. |
| Capacity Utilization | Monthly | Federal Reserve / FRED | TCU. Inflationary pressure gauge. |
| Retail Sales (advance + revised) | Monthly | Census Bureau / FRED | RSAFS (total), RSFSXMV (control group). |
| Housing Starts & Building Permits | Monthly | Census / FRED | HOUST, PERMIT. |
| Existing/New Home Sales | Monthly | NAR, Census / FRED | EXHOSLUSM495S, HSN1F. |
| Personal Income & Spending | Monthly | BEA / FRED | PI, PCE. |
| Consumer Confidence (Conf. Board) | Monthly | Conference Board / Bloomberg | CONCORD Index. |
| Michigan Consumer Sentiment | Monthly (prelim + final) | U. Michigan / FRED | UMCSENT. |
| Leading Economic Index (LEI) | Monthly | Conference Board / FRED | Leading, coincident, lagging indices. |
| Chicago Fed National Activity Index (CFNAI) | Monthly | Chicago Fed / FRED | CFNAI. 85-indicator composite. |

### 5.3 Monetary Policy & Financial Conditions

| Variable / Series | Frequency | Source | FRED Code / Details |
|---|---|---|---|
| FOMC Statement | Per meeting (8x/year) | Federal Reserve | Full text for NLP analysis. |
| FOMC Minutes | 3 weeks post-meeting | Federal Reserve | Full text for NLP. More detailed than statement. |
| FOMC Press Conference Transcript | Per meeting (same day video, transcript later) | Federal Reserve | Full text + video. NLP on Q&A section. |
| FOMC Dot Plot (Summary of Econ. Projections) | Quarterly (4 meetings) | Federal Reserve | Individual member rate projections. Published as PDF. |
| Fed Speeches (all FOMC members) | Ad hoc (~300/year) | Federal Reserve website | Full text. NLP for hawkish/dovish scoring. |
| Fed Balance Sheet (H.4.1) | Weekly | Federal Reserve / FRED | WALCL (total assets), WTREGEN (treasuries), WSHOMCB (MBS). |
| Treasury International Capital (TIC) | Monthly | Treasury.gov / FRED | Foreign holdings of US securities. 2-month lag. |
| Senior Loan Officer Survey (SLOOS) | Quarterly | Federal Reserve | Credit conditions survey. Published January, April, July, October. |
| Chicago Fed Financial Conditions Index | Weekly | Chicago Fed / FRED | NFCI, ANFCI (adjusted). Financial stress indicator. |
| Goldman Sachs Financial Conditions Index | Daily | Bloomberg | GS proprietary. Most widely followed. |
| Federal Reserve r* estimate (Laubach-Williams) | Quarterly | NY Fed | Published with methodological updates. |
| Wu-Xia Shadow Rate | Monthly | Atlanta Fed | Effective policy rate when at ZLB. |

# 6. MACROECONOMIC DATA - G5 EXTENSION

For the G5 rollout (Eurozone, UK, Japan, Switzerland), the following data is required per jurisdiction. The structure mirrors the US data but with jurisdiction-specific sources.

### 6.1 Data Per Jurisdiction

| Category | EUR (ECB/Eurostat) | GBP (BOE/ONS) | JPY (BOJ/Statistics Bureau) | CHF (SNB/FSO) |
|---|---|---|---|---|
| Policy Rate | MRO/Depo Rate | Bank Rate | Policy Rate / YCC target | Policy Rate |
| Inflation (headline) | HICP (Eurostat) | CPI (ONS) | CPI (MIC) | CPI (FSO) |
| Inflation (core) | HICP ex E&F | CPI ex E&F | CPI ex fresh food | CPI ex E&F |
| GDP | Eurostat flash + revised | ONS preliminary + revised | Cabinet Office QE | SECO quarterly |
| Employment | Eurostat unemployment | ONS LFS | Statistics Bureau LFS | SECO unemployment |
| PMI Manufacturing | S&P Global/HCOB | S&P Global | au Jibun Bank/S&P | procure.ch |
| Central Bank Minutes | ECB Account of Meeting | BOE MPC Minutes | BOJ Summary of Opinions | SNB Press Conference |
| Yield Curve | Bund curve (Bundesbank) | Gilt curve (BOE) | JGB curve (MOF) | Confederation bond curve |
| CDS Sovereign | Germany, France, Italy, Spain | UK | Japan | N/A (AAA) |
| Inflation-Linked Bonds | OATi (France), BTPi (Italy) | Index-Linked Gilts | JGBi | N/A |

Total additional series for G5 extension: approximately 200-300 time series per jurisdiction, or 800-1200 additional series total. Primary data providers: Eurostat, ECB Statistical Data Warehouse, ONS, BOE Statistical Database, Statistics Bureau of Japan, BOJ Time-Series Statistics, SNB Data Portal, BIS Statistics.

# 7. FISCAL & SOVEREIGN RISK DATA

### 7.1 Brazil Fiscal Data

| Variable | Frequency | Source | Details |
|---|---|---|---|
| Primary Balance (Central Government) | Monthly | STN (Resultado do Tesouro Nacional) | Released ~4th week of following month. Revenue, expenditure, primary result. |
| Primary Balance (Consolidated Public Sector) | Monthly | BCB SGS | SGS #5793. Includes states, municipalities, state-owned enterprises. |
| Nominal Deficit (including interest) | Monthly | BCB SGS | SGS #5727. Primary + nominal interest payments. |
| Net Public Sector Debt (DLSP) / GDP | Monthly | BCB SGS | SGS #4513 (BRL), #4503 (% GDP). Headline fiscal metric. |
| Gross Public Debt (DBGG) / GDP | Monthly | BCB SGS | SGS #13762 (% GDP). IMF-comparable metric. |
| Federal Domestic Debt Stock (DPMFi) | Monthly | STN | Total stock by instrument type. |
| Debt Composition (% Selic, % Pre, % IPCA, % Cambio) | Monthly | STN Relatorio Mensal da Divida | Critical for understanding interest rate sensitivity of debt. |
| Average Debt Maturity (ATM) | Monthly | STN | Weighted average time to maturity. |
| Gross Financing Needs (12M forward) | Monthly / Quarterly | STN / Calculated | Maturing debt + deficit. Rollover risk indicator. |
| Treasury Auction Results (all types) | Per auction (~3-4x/week) | STN | LTN, NTN-F, NTN-B, LFT auctions. Accepted rates, volumes, bid-to-cover. |
| Treasury Auction Calendar (PAF) | Annual / Quarterly revision | STN | Planned Borrowing Annual Plan. |
| Federal Revenue (Receita Federal) | Monthly | Receita Federal / STN | Tax revenue breakdown (IR, CSLL, PIS, COFINS, IOF, etc.). |
| Federal Expenditure (mandatory + discretionary) | Monthly | STN | Social security, personnel, investments, transfers. |
| Fiscal Framework Parameters (Arcabouco Fiscal) | Annual / On change | Min. Fazenda | Spending limits, primary balance targets, exclusions. |
| Social Security Deficit (RGPS + RPPS) | Monthly | INSS / STN | Largest single expenditure. Demographic pressures. |
| States and Municipalities Fiscal Data | Quarterly / Annual | STN (CAPAG/PAF) | Fiscal capacity rating of subnational entities. |
| Government Bimonthly Revenue/Expenditure Report | Bimonthly | Min. Fazenda | Official evaluation of fiscal compliance. Triggers contingenciamento. |

### 7.2 US Fiscal Data

| Variable | Frequency | Source | Details |
|---|---|---|---|
| Federal Budget Surplus/Deficit | Monthly | Treasury Monthly Statement / FRED | MTSDS133FMS. |
| Federal Debt Total (public) | Daily | Treasury.gov / FRED | GFDEBTN. |
| Federal Debt / GDP | Quarterly | FRED | GFDEGDQ188S. |
| CBO Budget Projections | Annual / Updated | CBO | 10-year projections. Baseline and alternative scenarios. |
| CBO Long-Term Budget Outlook | Annual | CBO | 30-year projections including Social Security, Medicare. |
| Treasury Auction Results | Per auction | Treasury.gov | All maturities. Yield, bid-to-cover, indirect bidders (proxy for foreign demand). |
| TIC Data (foreign holdings of Treasuries) | Monthly (2M lag) | Treasury.gov / FRED | By country. Japan and China as major holders. |
| OMB Budget of the US Government | Annual | OMB | Executive branch projections. |
| Interest Expense on Federal Debt | Monthly | Treasury / FRED | A091RC1Q027SBEA. Growing rapidly. |

### 7.3 EM Peer Fiscal Data (for SOV-02 Strategy)

For the EM Sovereign Relative Value strategy, the following data is required for each peer country (Mexico, Colombia, Chile, Peru, South Africa, Turkey, Indonesia, India, Poland, Hungary):

- Debt/GDP ratio (quarterly or annual) - IMF WEO, World Bank

- Fiscal balance / GDP (annual) - IMF WEO

- Current Account / GDP - IMF WEO, national central banks

- International Reserves / Short-Term External Debt - IMF IFS

- Sovereign credit rating (Moody's, S&P, Fitch) - rating agencies

- CDS spreads (1Y, 5Y, 10Y) - Bloomberg, Markit

- Commodity export exposure (% of exports) - UN Comtrade, national statistics

- Governance indicators (WGI) - World Bank (annual update)

- Primary source: IMF World Economic Outlook database (updated April and October), supplemented by national statistics offices and central banks.

# 8. FLOW & POSITIONING DATA

Flow and positioning data is critical for the Flow-Based Tactical FX strategy (FX-03), the CIP Basis Trade (CUPOM-01), and as supporting input for virtually all other strategies. Positioning data helps identify crowding risks.

### 8.1 Brazil Flows

| Variable | Frequency | Source | Details |
|---|---|---|---|
| FX Flow - Commercial (trade-related) | Weekly / Monthly detailed | BCB | Exports, imports receipts/payments. Published Wednesdays. |
| FX Flow - Financial | Weekly / Monthly detailed | BCB | Portfolio investments, loans, direct investment. Published Wednesdays. |
| Foreign Investors in B3 - Equities | Daily | B3 | Net buy/sell by foreign investors in equity market. |
| Foreign Investors in B3 - Futures/Derivatives | Daily | B3 | Position by investor type (foreign, institutional, individual, banks) for DI, DOL, DDI, IND. |
| Foreign Investors in Fixed Income (Renda Fixa) | Monthly | STN / BCB | Holdings by instrument type (LTN, NTN-F, NTN-B, LFT) by investor type. |
| BCB Swap Cambial Stock (outstanding) | Daily | BCB | Total notional of FX swap contracts. Net short USD position of BCB. |
| BCB Swap Cambial by Maturity | Monthly | BCB | Breakdown of swap stock by maturity date. |
| BCB FX Intervention Auctions | Per event | BCB | Spot auctions, repo auctions, swap auctions. Amounts and results. |
| B3 Open Interest by Investor Type | Daily | B3 Market Data | DI futures, DOL futures, DDI futures, options. Banks vs. foreign vs. funds vs. individuals. |
| ANBIMA Fund Flows (Renda Fixa, Multimercado) | Monthly | ANBIMA | Net flows into Brazilian fixed income and multimarket funds. |
| CVM Fund Holdings (quarterly, 90-day lag) | Quarterly | CVM | Detailed holdings of all registered funds. Delayed but comprehensive. |

### 8.2 US/Global Flows & Positioning

| Variable | Frequency | Source | Details |
|---|---|---|---|
| CFTC Commitment of Traders (COT) | Weekly (Friday data, released Monday) | CFTC | Positions by category (commercial, non-commercial, non-reportable) for all major futures. |
| CFTC COT - Disaggregated (futures + options) | Weekly | CFTC | More granular: dealer/intermediary, asset manager, leveraged fund, other. |
| CFTC COT - BRL futures (CME) | Weekly | CFTC | Specifically for BRL futures positioning. Key for FX strategies. |
| CFTC COT - Treasury futures (ZT, ZF, ZN, ZB) | Weekly | CFTC | Positioning in US rates market. |
| CFTC COT - Eurodollar/SOFR futures | Weekly | CFTC | Money market positioning. |
| DTCC CDS Trade Data (Sovereign) | Weekly | DTCC | Gross/net notional outstanding for sovereign CDS. |
| EPFR Fund Flows (EM Bond, EM Equity, DM Bond) | Weekly | EPFR Global | Flows into EM and DM fixed income and equity funds. Leading indicator of risk appetite. |
| IIF Capital Flows to EM | Monthly | IIF (Institute of International Finance) | Portfolio flows, bank lending, FDI to EM aggregate and by country. |
| BIS International Banking Statistics | Quarterly | BIS | Cross-border bank claims by country. Useful for XCCY basis analysis. |
| TIC Long-Term Securities Transactions | Monthly | US Treasury | Foreign purchases/sales of US securities. |
| Fed Primary Dealer Positioning | Weekly | NY Fed | Positions of primary dealers in Treasuries and agencies. |
| ETF Flows (TIP, TLT, EMB, HYG, LQD) | Daily | Bloomberg, ETF provider websites | Proxy for retail/institutional positioning in macro themes. |

# 9. CENTRAL BANK COMMUNICATION & NLP CORPUS

The NLP corpus is a structured database of all central bank communications used by the Monetary Policy Agent and the Orchestrator for sentiment analysis, hawkish/dovish scoring, and forward guidance detection. The corpus requires: (1) comprehensive historical collection; (2) real-time ingestion of new communications; (3) standardized parsing and metadata extraction.

### 9.1 Document Types & Sources

| Document Type | Institution | Frequency | Historical Depth | Language |
|---|---|---|---|---|
| COPOM Statement (Comunicado) | BCB | 8x/year | 1999-present (~200 docs) | Portuguese |
| COPOM Minutes (Ata) | BCB | 8x/year (6 BD after) | 1999-present (~200 docs) | Portuguese + English translation |
| Inflation Report | BCB | Quarterly | 1999-present (~100 docs) | Portuguese + English |
| BCB Speeches (all directors) | BCB | ~50-80/year | 2010-present | Portuguese (some English) |
| FOMC Statement | Fed | 8x/year | 1994-present (~250 docs) | English |
| FOMC Minutes | Fed | 8x/year (3 weeks after) | 1993-present (~250 docs) | English |
| FOMC Press Conference Transcript | Fed | 8x/year (since 2011) | 2011-present (~110 docs) | English |
| Summary of Economic Projections (SEP/Dot Plot) | Fed | 4x/year | 2012-present (~50 docs) | English (structured data) |
| Beige Book | Fed | 8x/year | 1970-present | English |
| Fed Speeches (all Governors + Presidents) | Fed | ~300/year | 2006-present | English |
| ECB Press Conference | ECB | 8x/year | 1999-present | English |
| ECB Account of Monetary Policy Meeting | ECB | 8x/year | 2015-present | English |
| BOE MPC Minutes | BOE | 8x/year | 1997-present | English |
| BOJ Summary of Opinions | BOJ | 8x/year | 2016-present | English (translated) |
| SNB Press Conference | SNB | 4x/year | 2000-present | English/French/German |

### 9.2 NLP Processing Pipeline

- Stage 1 - Ingestion: Automated scraping of central bank websites (BCB, Fed, ECB, BOE, BOJ, SNB) with change detection. PDF parsing via OCR when necessary.

- Stage 2 - Parsing: Extraction of structured metadata (date, institution, type, participants, vote results). Text cleaning and segmentation into paragraphs.

- Stage 3 - Translation: Portuguese documents translated to English via DeepL/GPT for cross-language consistency in NLP models.

- Stage 4 - Scoring: Hawkish/Dovish scoring via fine-tuned model (trained on labeled corpus of ~500 central bank documents). Output: continuous score [-1, +1] per document and per paragraph.

- Stage 5 - Change Detection: Diff analysis between consecutive documents (e.g., current vs. previous COPOM ata) to identify language changes. Output: list of changed phrases with significance scores.

- Stage 6 - Embedding: Vector embedding (1536-dim) of each document and paragraph for semantic search. Stored in pgvector.

- Stage 7 - Index: Full-text search index (Elasticsearch or PostgreSQL tsvector) for keyword queries.

# 10. ALTERNATIVE & HIGH-FREQUENCY DATA

Alternative data provides informational edge by offering higher frequency or unique perspectives on economic variables. These sources complement traditional macroeconomic releases.

| Variable | Frequency | Source | Use Case |
|---|---|---|---|
| Google Trends (economic keywords BR + US) | Weekly | Google Trends API | Nowcasting consumer confidence, unemployment claims, inflation expectations. |
| Satellite imagery (commodity storage, ports) | Weekly | Orbital Insight, Planet Labs | Commodity supply/demand estimation for terms of trade model. |
| Credit card transaction data (BR) | Weekly / Monthly | Aggregators (anonymized) | Real-time consumer spending proxy. PMC leading indicator. |
| Shipping/Port data (Santos, Paranagua) | Weekly | MarineTraffic, Kpler | Export volume leading indicator for trade balance. |
| Energy consumption (ONS grid data) | Daily | ONS (Operador Nacional do Sistema) | Economic activity high-frequency proxy. |
| Toll road traffic (ABCR) | Monthly | ABCR | Economic activity proxy. |
| Job postings (LinkedIn, Indeed BR + US) | Weekly | Proprietary scraping / APIs | Labor market leading indicator. |
| News sentiment (BR + US macro news) | Real-time | GDELT, RavenPack, or custom NLP | Event detection and market sentiment. |
| Social media sentiment (Twitter/X financial) | Real-time | Custom NLP pipeline | Crowd sentiment on policy decisions. |
| Brazilian government gazette (Diario Oficial) | Daily | Imprensa Nacional API | Regulatory changes, fiscal policy announcements. |
| US Congressional activity (bills, votes) | Daily | Congress.gov API | Fiscal policy and regulatory risk monitoring. |
| Climate/weather data (Brazil agriculture) | Daily | INMET, NOAA | Crop yield estimates for terms of trade. |

# 11. REFERENCE & STATIC DATA

Reference data provides the foundational context for interpreting time series data. It includes calendars, instrument specifications, and institutional data that changes infrequently but is critical for correct calculation.

| Category | Variables | Source | Update Frequency |
|---|---|---|---|
| Business Day Calendars | BR (ANBIMA holidays), US (NYSE, CME), EU (TARGET2), UK (BOE), JP (TSE) | ANBIMA, exchanges | Annual (published in advance) |
| COPOM Meeting Calendar | Dates of all scheduled meetings (8/year) | BCB | Annual (published December prior year) |
| FOMC Meeting Calendar | Dates of all scheduled meetings (8/year) + which have SEP | Federal Reserve | Annual |
| B3 Contract Specifications | Tick size, multiplier, margin, settlement rules for DI, DOL, DDI, WDO, all options | B3 Rules Manual | On change |
| CME Contract Specifications | Same for ZT, ZF, ZN, ZB, UB, ZQ, SR1, SR3, ES, GC, CL | CME Group | On change |
| NTN-B / LTN / NTN-F Bond Specifications | Coupon rates, maturity dates, VNA base dates, daycount conventions | STN | Per issuance |
| TIPS / Treasury Bond Specifications | Coupon, maturity, CPI reference dates, daycount | Treasury.gov | Per issuance |
| CDS Contract Specifications (ISDA) | Standard recovery rates, restructuring clauses, succession events | ISDA / Markit | On change |
| Country Reference Data | ISO codes, currency, central bank, rating, GDP (annual), population | IMF WEO, World Bank | Annual |
| IPCA Weights Table | Weights by group, subgroup, item for current IPCA methodology | IBGE | Annual (updated with POF base change) |
| CPI Weights Table (US) | Weights by component for CPI calculation | BLS | Biennial |
| Exchange Rate Regimes | Classification of FX regime by country (IMF AREAER) | IMF | Annual |
| STN Auction Calendar (PAF) | Planned auction dates, instrument types, volumes | STN | Annual with quarterly revisions |
| Sovereign Rating History | All rating actions (upgrades, downgrades, outlook changes) by agency | Moody's, S&P, Fitch / Bloomberg | On event |

# 12. DATA PROVIDER MATRIX & COST ESTIMATES

The table below consolidates all data providers, the data categories they cover, access methods, and estimated annual costs. The system requires a minimum of 2-3 primary providers plus free government data sources.

| Provider | Data Coverage | Access Method | Est. Annual Cost (USD) |
|---|---|---|---|
| Bloomberg Terminal + Data License | Market data (prices, curves, vol surfaces), macro data, CDS, news | Terminal API (BLPAPI), B-PIPE for real-time, Data License for bulk | $25,000-50,000 (terminal) + $50,000-200,000 (data license, depending on scope) |
| Refinitiv (LSEG) | Alternative to Bloomberg for market data, FX, fixed income | Eikon API, Tick History | $20,000-80,000 |
| B3 Market Data | All Brazilian exchange-traded instruments (DI, DOL, DDI, options, equities) | FTP daily files (free for basic), UMDF for real-time ($) | Free (EOD) to $5,000-20,000 (real-time feed) |
| BCB SGS (Sistema Gerenciador de Series) | Brazilian macro data (~40,000 series), monetary policy, external sector | REST API (JSON/XML) - free | Free |
| BCB Focus Survey | Market expectations (Selic, IPCA, GDP, FX) | REST API - free | Free |
| IBGE SIDRA | Brazilian national statistics (IPCA detailed, GDP, employment) | REST API - free | Free |
| STN (Secretaria do Tesouro Nacional) | Fiscal data, debt data, auction results | Website + PDFs (some structured data) | Free |
| ANBIMA | ETTJ curves, NTN-B reference rates, fund data | Debentures.com.br API, member access | Free (basic) to $5,000 (premium) |
| FRED (St. Louis Fed) | US macro data (800,000+ series) | REST API (free, API key required) | Free |
| CME Group Market Data | US futures and options data | CME DataMine (historical), CME Globex (real-time) | $5,000-30,000 |
| CFTC | Commitment of Traders (COT) positioning data | Bulk CSV download - free | Free |
| Treasury.gov | US fiscal data, TIC, auction results | APIs and bulk download - free | Free |
| BLS / BEA / Census | US economic statistics (CPI, GDP, employment) | APIs - free | Free |
| Markit (S&P Global) | CDS data, CDX indices, ISDA definitions | Markit API / data feed | $20,000-50,000 |
| EPFR Global | Fund flow data (EM/DM bond and equity) | Data feed | $15,000-40,000 |
| IIF (Institute of International Finance) | EM capital flows, research | Member access | $10,000-25,000 (membership) |
| IMF (WEO, IFS, GFSR) | Global macro, fiscal, financial stability data | IMF Data API - free | Free |
| World Bank (WDI, WGI) | Development indicators, governance indicators | API - free | Free |
| BIS Statistics | International banking, FX turnover, debt securities | BIS Statistical Warehouse - free | Free |
| RavenPack / GDELT | News sentiment, event detection | API subscription | $20,000-60,000 (RavenPack); Free (GDELT) |
| Orbital Insight / Planet Labs | Satellite imagery for commodity analysis | API subscription | $30,000-100,000 |

### 12.1 Estimated Total Annual Data Cost

| Scenario | Description | Est. Annual Cost (USD) |
|---|---|---|
| Minimum Viable | Bloomberg Terminal + B3 EOD + free government APIs + Markit basic | $80,000 - $120,000 |
| Production (BR + US) | Bloomberg Data License + B3 real-time + CME + Markit + EPFR | $200,000 - $400,000 |
| Full Scale (BR + US + G5) | Full Bloomberg + Refinitiv + all premium feeds + alt data | $400,000 - $800,000 |

# 13. DATA PIPELINE ARCHITECTURE (ETL/ELT)

The data pipeline follows an ELT (Extract-Load-Transform) architecture where raw data is loaded first into the Bronze layer, then transformed into Silver and Gold layers. This preserves raw data immutability while allowing flexible transformations.

### 13.1 Pipeline Technology Stack

- Orchestrator: Apache Airflow 2.x (or Dagster) - DAG-based scheduling with dependency management, retry logic, SLA monitoring.

- Streaming: Apache Kafka - real-time data ingestion from market feeds, with exactly-once semantics.

- Batch Processing: Python (pandas, polars) + SQL (dbt for transformations).

- Scheduling: Airflow DAGs triggered by: (1) time-based (daily EOD, weekly, monthly); (2) event-based (new data publication from BCB, IBGE, etc.); (3) dependency-based (transform runs after all inputs available).

- Monitoring: Grafana dashboards + PagerDuty alerts for pipeline failures, data quality issues, and SLA breaches.

### 13.2 Pipeline Stages

### Stage 1: Extract

- API Connectors: Custom Python connectors for each data source (BCB SGS, FRED, Bloomberg BLPAPI, B3 FTP, CME, IBGE SIDRA, etc.).

- Web Scrapers: For sources without APIs (STN PDFs, central bank speeches, CFTC CSVs).

- File Watchers: For FTP-based sources (B3 daily files land on FTP by 20:00 BRT).

- Streaming Consumers: Kafka consumers for real-time market data feeds.

### Stage 2: Load (Bronze Layer)

- Raw data is loaded exactly as received, with metadata: source, ingestion_timestamp, file_hash, schema_version.

- No transformations. Immutable storage. Retained indefinitely.

- Storage: TimescaleDB (structured) + MinIO/S3 (raw files).

### Stage 3: Transform (Silver Layer)

- Data validation: null checks, range checks, outlier detection (z-score > 5), stale data detection.

- Standardization: unified timezone (UTC), consistent naming conventions, currency normalization.

- Deduplication: remove duplicate records from overlapping data sources.

- Enrichment: calculate derived fields (returns, z-scores, moving averages) that are universally useful.

- Point-in-time tagging: ensure release_time is correctly populated for all macro series (critical for backtest integrity).

### Stage 4: Derive (Gold Layer)

- Model Inputs: pre-computed features consumed by agents (e.g., carry-to-risk ratio, BEER misalignment score, term premium estimates).

- Signals: output of each agent's models (directional signal, confidence, suggested sizing).

- Portfolio State: current positions, P&L, risk metrics, margin utilization.

- Audit Trail: every signal generation and trade decision logged with full input provenance.

### 13.3 Scheduling Matrix (Key DAGs)

| DAG Name | Schedule | SLA | Dependencies |
|---|---|---|---|
| ingest_b3_eod | Daily 20:30 BRT | 21:00 BRT | B3 FTP file availability |
| ingest_bcb_sgs | Daily 09:00 BRT | 09:30 BRT | BCB API availability |
| ingest_bcb_focus | Monday 09:00 BRT | 09:30 BRT | BCB Focus publication |
| ingest_bcb_fx_flow | Wednesday 14:00 BRT | 14:30 BRT | BCB FX flow publication |
| ingest_fred | Daily 08:00 EST | 08:30 EST | FRED API |
| ingest_bloomberg_eod | Daily 17:30 EST | 18:00 EST | Bloomberg Data License |
| ingest_cftc_cot | Monday 15:30 EST | 16:00 EST | CFTC file publication |
| ingest_stn_fiscal | Monthly ~25th | Within 4 hours | STN publication |
| ingest_ibge_ipca | Monthly ~10th | Within 1 hour | IBGE publication |
| transform_silver | After each Bronze ingest | 30 min after trigger | Corresponding Bronze DAG |
| compute_curves | Daily after ingest_b3_eod | 22:00 BRT | B3 + ANBIMA data |
| compute_signals | Daily after all Silver complete | 23:00 BRT / 19:00 EST | All Silver tables |
| compute_portfolio | Daily after signals | 23:30 BRT | Signals + Risk limits |
| ingest_nlp_cb_docs | Event-triggered (web scraper) | 30 min after publication | Central bank website change detection |

# 14. DATA QUALITY, GOVERNANCE & MONITORING

### 14.1 Data Quality Framework

Data quality is enforced at every pipeline stage using automated checks. The framework follows the dimensions defined by DAMA International (Data Management Body of Knowledge):

- Completeness: Every expected data point is present. Alert if >1% of expected records are missing in any daily batch. For macro releases, alert immediately if release is late (vs. published calendar).

- Accuracy: Values fall within expected ranges. Range checks per series (e.g., DI rate between 0% and 50%; USDBRL between 1.0 and 10.0). Outlier detection via z-score (|z| > 5 triggers review).

- Timeliness: Data arrives within SLA. Every DAG has a defined SLA. PagerDuty alert if breached.

- Consistency: Cross-source validation for critical series. E.g., DI curve from B3 vs. Bloomberg vs. ANBIMA must agree within 2bps. PTAX from BCB vs. Bloomberg must match exactly.

- Uniqueness: No duplicate records after deduplication stage.

- Validity: Data conforms to schema (correct types, formats, units). Schema enforcement at ingestion.

### 14.2 Point-in-Time Database Integrity

The most critical data quality requirement for a quantitative trading system is point-in-time (PIT) correctness. Every macroeconomic data point must have two timestamps:

- reference_date: The period the data refers to (e.g., January 2026 for January IPCA).

- release_timestamp: The exact moment the data became publicly available (e.g., February 12, 2026, 09:00 BRT for January IPCA).

For revised series (GDP, employment), each revision is stored as a separate record with its own release_timestamp and revision_number. This enables backtesting that uses only data available at the time, preventing look-ahead bias. This approach follows the CRSP/Compustat methodology used by academic finance and the practices documented by Lopez de Prado (2018) in 'Advances in Financial Machine Learning'.

### 14.3 Monitoring Dashboard

- Pipeline Health: DAG success/failure rates, execution times, SLA compliance (Grafana).

- Data Freshness: time since last update for each critical series. Alert if stale >2x expected frequency.

- Quality Scores: daily quality score per data domain (0-100%) based on completeness, accuracy, timeliness.

- Cross-Source Discrepancies: flagged differences between Bloomberg and primary source data.

- Storage Utilization: disk usage by database, table, and partition. Capacity planning alerts.

# 15. STORAGE SIZING & INFRASTRUCTURE REQUIREMENTS

### 15.1 Storage Estimates

| Database / Store | Estimated Size (Year 1) | Growth Rate | Compression |
|---|---|---|---|
| TimescaleDB (Market Data) | 50-80 GB | ~30 GB/year | 90-95% with native compression |
| TimescaleDB (Macro Series) | 2-5 GB | ~1 GB/year | 90-95% |
| TimescaleDB (Signals/Model Output) | 10-20 GB | ~15 GB/year | 80-90% |
| PostgreSQL (Reference/Metadata) | 500 MB | ~100 MB/year | N/A |
| MongoDB (NLP Corpus) | 5-10 GB | ~2 GB/year | 50-70% |
| MinIO/S3 (Raw File Archive) | 50-100 GB | ~30 GB/year | Stored as-is |
| Redis (Cache) | 2-5 GB (in-memory) | Stable (TTL-based) | N/A |
| Kafka (Message Retention) | 10-20 GB | Stable (7-day retention) | Snappy compression |
| Total (uncompressed equivalent) | ~200-400 GB | ~80 GB/year | - |
| Total (after compression) | ~30-60 GB | ~15 GB/year | 85-90% average |

### 15.2 Infrastructure Recommendations

| Component | Minimum Spec | Recommended Production Spec |
|---|---|---|
| Database Server | 8 vCPU, 32GB RAM, 500GB NVMe SSD | 16 vCPU, 64GB RAM, 2TB NVMe SSD (RAID 1), read replicas |
| Application Server (Agents) | 8 vCPU, 32GB RAM | 32 vCPU, 128GB RAM, GPU for ML models (NVIDIA A10 or similar) |
| Redis Cache | 4 vCPU, 16GB RAM | 8 vCPU, 32GB RAM (Redis Cluster for HA) |
| Kafka Cluster | 3 nodes, 4 vCPU, 16GB RAM each | 5 nodes, 8 vCPU, 32GB RAM each, dedicated disks |
| Object Storage | 1TB | 5TB with lifecycle policies |
| Network | 1 Gbps | 10 Gbps between components; low-latency colocation for real-time feeds |
| Backup | Daily snapshots to S3 | Continuous WAL archiving + daily full backups + cross-region replication |
| Disaster Recovery | RPO: 1 hour, RTO: 4 hours | RPO: 5 minutes, RTO: 30 minutes (hot standby) |

### 15.3 Total Variable Count Summary

The table below summarizes the total number of distinct data variables/series across the entire system:

| Category | BR | US | G5 (est.) | Total |
|---|---|---|---|---|
| Market Prices & Curves | ~150 | ~120 | ~300 | ~570 |
| Macroeconomic Series | ~180 | ~200 | ~800 | ~1,180 |
| Fiscal & Sovereign | ~60 | ~30 | ~80 | ~170 |
| Flow & Positioning | ~40 | ~50 | ~60 | ~150 |
| NLP Corpus (documents) | ~400 | ~1,200 | ~800 | ~2,400 |
| Alternative Data | ~30 | ~20 | ~20 | ~70 |
| Reference/Static | ~100 | ~80 | ~120 | ~300 |
| TOTAL SERIES | ~960 | ~1,700 | ~2,180 | ~4,840 |

### --- END OF DATA ARCHITECTURE DOCUMENT ---
