# Macro Fund System — Strategy Engine, Risk & Portfolio Management

## What This Is

A comprehensive macro trading system for a global macro hedge fund focused on Brazil and the US. The system integrates real-time market data APIs (11 connectors, 250+ series), 5 AI-driven analytical agents with quantitative models, 8 trading strategies, portfolio construction, risk management, and a daily orchestration pipeline. This milestone expands to 24+ strategies, adds NLP for central bank communications, production orchestration (Dagster), monitoring (Grafana), and a React dashboard.

## Core Value

Reliable, point-in-time-correct macro and market data flowing into a queryable system — the foundation everything else (agents, strategies, risk) depends on. If the data layer doesn't work, nothing works.

## Current Milestone: v3.0 Strategy Engine, Risk & Portfolio Management

**Goal:** Expand from 8 to 24+ trading strategies across all asset classes, add NLP pipeline for central bank communications (COPOM + FOMC), enhance risk engine (Monte Carlo VaR, reverse stress, Black-Litterman portfolio optimization), add Dagster production orchestration, Grafana monitoring dashboards, React multi-page dashboard, and comprehensive integration testing.

**Target features:**
- 16 new trading strategies (FX, rates, inflation, cupom cambial, sovereign, cross-asset)
- Enhanced backtesting engine (portfolio-level, walk-forward, deflated Sharpe, cost model)
- NLP pipeline for COPOM/FOMC communications (scrapers, hawk/dove sentiment)
- Enhanced Cross-Asset Agent with LLM-powered narrative and CrossAssetView
- Signal aggregation v2 (Bayesian, crowding penalty, staleness discount)
- Risk engine v2 (Monte Carlo VaR, reverse stress, component VaR)
- Portfolio optimization (Black-Litterman, mean-variance, Kelly sizing)
- Dagster production orchestration (16+ assets, dependency graph)
- Grafana monitoring (4 provisioned dashboards)
- Alert system (10 rules, Slack + email)
- React multi-page dashboard (5 pages: Strategies, Signals, Risk, Portfolio, Agents)
- API expansion (backtest routes, WebSocket channels)
- Daily report generator (markdown, HTML, email, Slack)
- Integration testing and CI/CD expansion

## Requirements

### Validated

- [x] Docker Compose stack with TimescaleDB, Redis, MongoDB, Kafka, MinIO
- [x] SQLAlchemy 2.0 ORM models with 10 tables including 7 TimescaleDB hypertables with compression
- [x] 11 data connectors covering Brazil + US macro data (250+ series)
- [x] Instrument seeding (~25) and series metadata (150-200+ entries)
- [x] Historical backfill orchestrator with idempotent inserts
- [x] Transforms: curves, returns, macro calculations, vol surface
- [x] FastAPI REST API with 12 endpoints and point-in-time support
- [x] Data quality framework and infrastructure verification
- [x] 319 tests with CI pipeline
- [x] 5 analytical agents (Inflation, Monetary Policy, Fiscal, FX Equilibrium, Cross-Asset)
- [x] BacktestEngine with point-in-time correctness
- [x] 8 trading strategies (RATES_BR_01-04, INF_BR_01, FX_BR_01, CUPOM_01, SOV_BR_01)
- [x] Signal aggregation with directional consensus and conflict detection
- [x] Portfolio construction (risk parity + conviction overlay + regime scaling)
- [x] Capital allocator with constraint enforcement (leverage, concentration, drift)
- [x] Risk engine (VaR 3 methods, stress testing 4 scenarios, 9 limits, circuit breakers)
- [x] Daily pipeline (8-step orchestration with CLI)
- [x] LLM narrative generation (Claude API + template fallback)
- [x] HTML dashboard (4 tabs, CDN-only React)
- [x] 12 API route files

### Active

*See REQUIREMENTS.md for full REQ-ID list*

### Out of Scope

- Live order execution — research/backtesting focus first
- Multi-user access / authentication — solo user for now
- Bloomberg terminal integration — using free data sources only
- ETFs, mutual funds as investment instruments — stocks only per project constraints
- Production deployment (Kubernetes, Helm) — Phase 3+
- Real-time streaming execution — Phase 3+
- FIX protocol connectivity — Phase 3+

## Context

**Domain**: Global macro trading, focused on Brazil-US axis. The system has 5 specialized analytical agents and 8 trading strategies. This milestone expands strategy coverage to 24+ strategies, adds NLP intelligence from central bank communications, and builds production-grade orchestration and monitoring.

**Existing Infrastructure** (from v1.0 + v2.0):
- TimescaleDB with 10 tables, 7 hypertables, compression policies
- 11 connectors: BCB SGS, FRED, Yahoo Finance, BCB PTAX, BCB Focus, B3/Tesouro Direto, IBGE SIDRA, STN Fiscal, CFTC COT, US Treasury, BCB FX Flow
- 250+ macro series with point-in-time release_time tracking
- Transforms: Nelson-Siegel, returns, z-scores, macro calculations
- FastAPI with 12 endpoints, data quality checks, verification script
- 5 agents: InflationAgent, MonetaryPolicyAgent, FiscalAgent, FxEquilibriumAgent, CrossAssetAgent
- 8 strategies in src/strategies/ (flat files, ALL_STRATEGIES dict registry)
- BacktestEngine in src/backtesting/ (single strategy, PIT correct)
- Signal aggregation in src/portfolio/signal_aggregator.py
- Portfolio construction in src/portfolio/ (risk parity + conviction + regime)
- Risk engine in src/risk/ (VaR, stress, limits, drawdown/circuit breakers)
- Daily pipeline in src/pipeline/daily_pipeline.py (custom Python orchestrator)
- Narrative in src/narrative/generator.py (Claude API + ASCII template fallback)
- HTML dashboard served via FileResponse at /dashboard

**Key Academic References (new for v3.0)**:
- Lopez de Prado (2018) "Advances in Financial Machine Learning" — backtesting, deflated Sharpe
- Black & Litterman (1992) — portfolio optimization with views
- Maillard, Roncalli & Teiletche (2010) — risk parity
- Hansen & McMahon (2016) "Shocking Language" — central bank NLP
- Burnside (2011) — carry trades
- Du, Tepper & Verdelhan (2018) — CIP deviations
- Hamilton (1989) — regime switching / HMM
- Pan & Singleton (2008) — sovereign CDS term structure

**Guide Reference**: `docs/GUIA_COMPLETO_CLAUDE_CODE_Fase2.md` — 18 etapas with detailed specifications for all v3.0 components.

## Constraints

- **Tech Stack**: Python 3.11+, SQLAlchemy 2.0 async, FastAPI, Docker Compose
- **Data Sources**: Free APIs only — no Bloomberg
- **FRED API Key**: Required — free registration
- **Infrastructure**: Docker (TimescaleDB, Redis, MongoDB, Kafka, MinIO) — 16GB+ RAM
- **Investment Focus**: Stocks only, no ETFs or mutual funds
- **LLM Preference**: Claude Opus 4.5/4.6 for narrative generation
- **Real Data Only**: No mock data in production
- **Point-in-Time**: All agent/strategy computations must respect release_time constraints
- **Backtesting Integrity**: No look-ahead bias — strictly point-in-time data access
- **New Dependencies**: Dagster 1.6+, Grafana (Docker), Node.js 18+ (React dashboard)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| TimescaleDB over InfluxDB | SQLAlchemy compatibility, SQL interface, compression | Good |
| BCB swap series for DI curve | Free alternative to Bloomberg DI futures; 12 tenors daily | Good |
| Tesouro Direto for NTN-B rates | Free JSON API with current prices; historical CSVs | Good |
| MongoDB for unstructured data | Agent outputs, LLM responses, document storage | Pending |
| Kafka for event streaming | Future: real-time signal propagation between agents | Pending |
| Point-in-time via release_time | Prevents look-ahead bias in backtesting | Good |
| Monorepo structure | All components in one repo for now | Good |
| ON CONFLICT DO NOTHING | Idempotent inserts enable safe re-runs | Good |
| BaseConnector ABC pattern | Consistent interface across all 11 connectors | Good |
| Template Method for agents | BaseAgent.run() orchestrates load->features->models->narrative | Good |
| Enhance not replace | Existing v2.0 components enhanced, not rewritten from scratch | Pending |
| Coexisting strategies | New strategies (FX-02 etc.) live alongside existing (FX_BR_01 etc.) | Pending |
| Dagster over custom pipeline | Scheduling, retry, monitoring UI — custom pipeline stays as fallback | Pending |

---
*Last updated: 2026-02-22 after milestone v3.0 started*
