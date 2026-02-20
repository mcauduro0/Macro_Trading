# Macro Hedge Fund AI System — Requirements

## System Requirements
- **Language:** Python 3.11+ (primary), Node.js 18+ (dashboard)
- **Database:** TimescaleDB (PostgreSQL 16), Redis 7, MongoDB 7
- **Messaging:** Kafka (Confluent 7.6)
- **Storage:** MinIO
- **Investment Focus:** Stocks only (no ETFs, mutual funds in strategy universe)
- **LLM:** Claude API for narrative generation
- **Data:** Real data only in production (no mocks)
- **Stack:** Python-based with open-source libraries

## Hardware Requirements
- 16GB+ RAM, 50GB+ disk
- Docker + Docker Compose installed

## External Dependencies
- FRED API key (free: https://fred.stlouisfed.org/docs/api/api_key.html)
- BCB SGS API (no key needed)
- BCB Focus/PTAX OData API (no key needed)
- IBGE SIDRA API (no key needed)
- Yahoo Finance via yfinance (no key needed)
- CFTC public data (no key needed)
- US Treasury public CSV data (no key needed)
- Anthropic API key (optional, for LLM narratives)

## Data Coverage
- **Brazil:** IPCA (headline + 9 components + cores), GDP, IBC-Br, industrial production, retail, services, employment, Selic, CDI, credit, monetary aggregates, trade balance, current account, FDI, reserves, PTAX, fiscal (primary balance, debt/GDP)
- **USA:** CPI (all + core + trimmed + sticky), PCE, PPI, GDP, NFP, unemployment, wages, JOLTS, claims, industrial production, retail, housing, consumer sentiment, Fed Funds, SOFR, UST yields (2Y-30Y), TIPS, Fed balance sheet, financial conditions, credit spreads
- **Market Data:** USDBRL, EURUSD, USDJPY, GBPUSD, DXY, Ibovespa, S&P 500, VIX, Gold, Oil (WTI+Brent), Soybeans, Corn, Copper, Iron Ore proxy, ETFs (EWZ, TIP, TLT, HYG, EMB, LQD)
- **Curves:** DI Pre (1M-12M), NTN-B real rates, UST nominal, UST real (TIPS), Breakeven inflation
- **Positioning:** CFTC COT (12 contracts x 4 categories = 48 series)
- **Flows:** BCB FX flows (commercial + financial), BCB swap stock
- **Expectations:** Focus survey (IPCA, Selic, GDP, FX, IGP-M — annual + monthly + per meeting)

## Key Constraints
- Point-in-time correctness: all historical queries must respect release_time
- Idempotent operations: all inserts use ON CONFLICT DO NOTHING
- Rate limiting: respect API limits for each data provider
- Brazilian date conventions: DD/MM/YYYY, comma decimal separator
- Business day calendars: BR (ANBIMA) and US (NYSE) holiday calendars
