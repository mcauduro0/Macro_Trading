# Macro Fund System — Data Infrastructure

## What This Is

A comprehensive data infrastructure for an agentic macro trading system serving a global macro hedge fund focused on Brazil and the US. The system ingests, stores, transforms, and serves 200+ macroeconomic and market data series from 11+ data sources, providing the foundation for AI-driven trading agents and ~25 quantitative strategies operating across FX, interest rates, inflation, cupom cambial, and sovereign risk.

## Core Value

Reliable, point-in-time-correct macro and market data flowing into a queryable system — the foundation everything else (agents, strategies, risk) depends on. If the data layer doesn't work, nothing works.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Docker Compose stack with TimescaleDB, Redis, MongoDB, Kafka, MinIO
- [ ] SQLAlchemy 2.0 ORM models with 10 tables including 7 TimescaleDB hypertables with compression
- [ ] BCB SGS connector (~50 Brazilian macro series: inflation, activity, monetary, external, fiscal)
- [ ] FRED connector (~50 US macro series: CPI, PCE, NFP, rates, credit, fiscal)
- [ ] BCB Focus connector (market expectations: IPCA, Selic, GDP, FX by horizon)
- [ ] B3/Tesouro Direto connector (DI curve from swap series, NTN-B real rates, breakeven)
- [ ] ANBIMA connector placeholder (future: ETTJ curve, indicative rates)
- [ ] IBGE SIDRA connector (IPCA disaggregated by 9 components with weights)
- [ ] STN Fiscal connector (primary balance, debt composition by indexer)
- [ ] CFTC COT connector (positioning for 12 contracts × 4 categories = 48 series)
- [ ] US Treasury connector (nominal + real + breakeven yield curves)
- [ ] Yahoo Finance connector (25+ tickers: FX, indices, commodities, ETFs)
- [ ] BCB PTAX connector (official FX fixing rate)
- [ ] BCB FX Flow connector (commercial/financial flows, swap stock)
- [ ] Seed scripts for instruments (~25) and series metadata (150-200+)
- [ ] Historical backfill orchestrator with idempotent inserts (2010-present)
- [ ] Transforms: Nelson-Siegel curve fitting, forward rates, carry/rolldown, DV01
- [ ] Transforms: returns, rolling vol, z-scores, percentile ranks, correlations, drawdowns
- [ ] Transforms: macro (YoY from MoM, diffusion index, trimmed mean, surprise index)
- [ ] Transforms: vol surface reconstruction from delta-space quotes
- [ ] FastAPI REST API with endpoints for macro, curves, market data, flows
- [ ] Point-in-time query support (release_time filtering for macro series)
- [ ] Macro dashboard endpoint (latest values for key indicators: BR + US + market)
- [ ] Data quality framework (completeness, accuracy, curve integrity, PIT validation)
- [ ] Infrastructure verification script (end-to-end health check)

### Out of Scope

- AI agents (Inflation, Monetary Policy, Fiscal, FX Equilibrium, Cross-Asset) — Phase 1+
- Trading strategies (~25 strategies) — Phase 1+
- Risk management system — Phase 1+
- Live order execution — research/backtesting focus first
- Frontend dashboard (React) — Phase 1+
- Multi-user access / authentication — solo user for now
- Bloomberg terminal integration — using free data sources only
- ETFs, mutual funds as investment instruments — stocks only per project constraints

## Context

**Domain**: Global macro trading, focused on Brazil-US axis. The system needs to capture the full picture of both economies — inflation dynamics, monetary policy, fiscal health, external accounts, positioning, and cross-asset flows.

**Data Architecture**: Bronze/Silver/Gold layer pattern:
- Bronze: Raw data from connectors → TimescaleDB hypertables (market_data, macro_series, curves, flow_data, fiscal_data, vol_surfaces, signals)
- Silver: Transforms layer (curve interpolation, returns, z-scores, macro calculations)
- Gold: API endpoints serving processed data to agents and strategies

**Key Design Decisions from Spec**:
- TimescaleDB for time-series (hypertables with compression policies)
- Point-in-time correctness via release_time tracking on macro_series (critical for backtesting)
- Revision tracking for revised data series (NFP, GDP)
- BCB swap DI x Pré series (SGS #7805-7816) as proxy for DI curve in absence of Bloomberg
- Tesouro Direto JSON API for NTN-B real rates
- CFTC disaggregated report for positioning (Dealer, Asset Manager, Leveraged Funds)
- Idempotent inserts everywhere (ON CONFLICT DO NOTHING) for safe re-runs

**Brazilian Specifics**:
- BCB SGS values use comma as decimal separator ("1.234,56")
- PTAX uses MM-DD-YYYY date format (different from DD/MM/YYYY for SGS)
- Business day calendar: ANBIMA holidays differ from NYSE
- Focus survey published weekly (Mondays)
- IPCA released ~15 days after reference month

## Constraints

- **Tech Stack**: Python 3.11+, SQLAlchemy 2.0 async, FastAPI, Docker Compose — per project spec
- **Data Sources**: Free APIs only (BCB, FRED, IBGE, Tesouro Direto, Yahoo Finance, CFTC) — no Bloomberg
- **FRED API Key**: Required — free registration at fred.stlouisfed.org
- **Infrastructure**: Docker (TimescaleDB, Redis, MongoDB, Kafka, MinIO) — 16GB+ RAM, 50GB+ disk
- **Investment Focus**: Stocks only, no ETFs or mutual funds as trading instruments
- **LLM Preference**: Claude Opus 4.5, GPT-5.2 Pro, Gemini 3 Pro for agent phases
- **Real Data Only**: No mock data in production — all connectors must hit real APIs

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| TimescaleDB over InfluxDB | SQLAlchemy compatibility, SQL interface, compression, hypertables | — Pending |
| BCB swap series for DI curve | Free alternative to Bloomberg DI futures; 12 standard tenors daily | — Pending |
| Tesouro Direto for NTN-B rates | Free JSON API with current prices; historical CSVs available | — Pending |
| MongoDB for unstructured data | Agent outputs, LLM responses, document storage | — Pending |
| Kafka for event streaming | Future: real-time signal propagation between agents | — Pending |
| Point-in-time via release_time | Prevents look-ahead bias in backtesting — critical for macro data | — Pending |
| Monorepo structure | All components in one repo for now; split later if needed | — Pending |

---
*Last updated: 2026-02-19 after initialization*
