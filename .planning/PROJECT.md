# Macro Fund System — Complete Trading Platform

## What This Is

A comprehensive macro trading system for a global macro hedge fund focused on Brazil and the US. The system spans the full investment workflow: data infrastructure (11 connectors, 250+ series), 5 AI-driven analytical agents, 24+ quantitative trading strategies, NLP pipeline for central bank communications, portfolio optimization (Black-Litterman, Kelly sizing), risk management (Monte Carlo VaR, reverse stress testing), production orchestration (Dagster), and a complete Portfolio Management System with human-in-the-loop trade workflow, 7 operational frontend pages, and compliance audit trail.

## Core Value

Reliable, point-in-time-correct macro and market data flowing into a queryable system — the foundation everything else (agents, strategies, risk, PMS) depends on. If the data layer doesn't work, nothing works.

## Current State

**v4.0 shipped** — all 4 milestones complete (v1.0 through v4.0), 27 phases, 74 plans.

**System capabilities:**
- **Data Layer** (v1.0): 11 connectors, 250+ series, TimescaleDB, transforms, FastAPI API
- **Analytics Layer** (v2.0): 5 agents, 8 base strategies, backtesting, risk engine, daily pipeline
- **Strategy Layer** (v3.0): 24+ strategies, NLP, Bayesian signal aggregation, Monte Carlo VaR, Black-Litterman, Dagster orchestration, Grafana monitoring, React dashboard
- **Operations Layer** (v4.0): PMS with trade workflow, position management, morning briefings, risk monitoring, performance attribution, 7 frontend pages, Redis caching, compliance audit

**Codebase:** ~47,000 Python LOC (`src/`), ~9,300 JSX LOC (React frontend), 15 database tables (10 base + 5 PMS), 26+ Dagster assets

## Requirements

### Validated

- ✓ Docker Compose stack with TimescaleDB, Redis, MongoDB, Kafka, MinIO — v1.0
- ✓ SQLAlchemy 2.0 ORM models with 15 tables including hypertables with compression — v1.0 (10 tables), v4.0 (+5 PMS tables)
- ✓ 11 data connectors covering Brazil + US macro data (250+ series) — v1.0
- ✓ Transforms: curves (Nelson-Siegel), returns, macro calculations, vol surface — v1.0
- ✓ FastAPI REST API with 40+ endpoints and point-in-time support — v1.0 (12), v2.0 (+9), v3.0 (+14), v4.0 (+20 PMS)
- ✓ Data quality framework and infrastructure verification — v1.0
- ✓ 5 analytical agents (Inflation, Monetary Policy, Fiscal, FX Equilibrium, Cross-Asset) — v2.0
- ✓ BacktestEngine v2 with portfolio-level, walk-forward, deflated Sharpe — v2.0 (base), v3.0 (enhanced)
- ✓ 24+ trading strategies across FX, rates, inflation, cupom cambial, sovereign, cross-asset — v2.0 (8), v3.0 (+16)
- ✓ Signal aggregation v2 (Bayesian, crowding penalty, staleness discount) — v3.0
- ✓ Risk engine v2 (Monte Carlo VaR, reverse stress, component VaR) — v3.0
- ✓ Portfolio optimization (Black-Litterman, Kelly sizing, risk budgets) — v3.0
- ✓ Dagster production orchestration (26+ assets, EOD + pre-open schedules) — v3.0 (22 assets), v4.0 (+4 PMS)
- ✓ Grafana monitoring (4 dashboards, AlertManager) — v3.0
- ✓ React multi-page dashboard (5 analytics pages + 7 PMS pages) — v3.0, v4.0
- ✓ NLP pipeline: COPOM/FOMC scrapers, central bank sentiment analysis — v3.0
- ✓ Cross-Asset Agent v2: HMM regime classification, LLM narrative — v3.0
- ✓ PMS database (5 tables: positions, proposals, journal, briefings, P&L history) — v4.0
- ✓ PositionManager with full lifecycle (open, close, MTM, P&L tracking) — v4.0
- ✓ Human-in-the-loop trade workflow (signal-to-proposal, approve/reject/modify) — v4.0
- ✓ 20+ PMS API endpoints across 6 routers — v4.0
- ✓ Morning Pack daily briefing service (9 sections, LLM narrative) — v4.0
- ✓ RiskMonitorService (real-time VaR, stress, limits, concentration) — v4.0
- ✓ PerformanceAttributionEngine (5-dimension P&L decomposition) — v4.0
- ✓ 7 PMS frontend pages (Morning Pack, Position Book, Trade Blotter, Risk Monitor, Attribution, Journal, Agent Intel) — v4.0
- ✓ PMS design system (Bloomberg-dense dark theme, 8 components) — v4.0
- ✓ Compliance & Audit module (audit trail, SHA-256 hash verification) — v4.0
- ✓ Redis caching layer (tiered TTLs, write-through + cascade invalidation) — v4.0
- ✓ Go-live checklist, DR playbook, backup/restore scripts — v4.0

### Active

(No active requirements — all milestones shipped. Define new requirements with `/gsd:new-milestone`.)

### Out of Scope

- Live order execution / FIX protocol — system provides trade proposals, human executes externally
- Multi-user access / authentication — solo portfolio manager for now
- Bloomberg terminal integration — using free data sources only
- ETFs, mutual funds — stocks only per project constraints
- Kubernetes / Helm deployment — Docker Compose sufficient for current scale
- Mobile app / PWA — desktop-first operational interface
- Real-time streaming execution — batch/polling model with 60s intervals

## Context

**Domain**: Global macro trading, Brazil-US axis. Full investment workflow from data collection through trade proposal generation and performance attribution.

**Tech Stack:**
- Python 3.11+, SQLAlchemy 2.0, FastAPI, Docker Compose
- TimescaleDB (15 tables, hypertables with compression), Redis (PMS caching), MongoDB, Kafka, MinIO
- Dagster 1.6+ (26+ assets, EOD + pre-open schedules)
- Grafana (4 monitoring dashboards)
- React 18 + Tailwind CSS + Recharts (CDN-loaded, no build tooling)
- Claude Opus 4.5/4.6 for LLM narrative generation (with template fallback)

**Key Academic References:**
- Lopez de Prado (2018) "Advances in Financial Machine Learning" — backtesting, deflated Sharpe
- Black & Litterman (1992) — portfolio optimization with views
- Maillard, Roncalli & Teiletche (2010) — risk parity
- Hansen & McMahon (2016) "Shocking Language" — central bank NLP
- Burnside (2011) — carry trades
- Du, Tepper & Verdelhan (2018) — CIP deviations
- Hamilton (1989) — regime switching / HMM
- Pan & Singleton (2008) — sovereign CDS term structure

**Guide References:**
- `docs/GUIA_COMPLETO_CLAUDE_CODE_Fase0.md` — v1.0 Data Infrastructure (15 etapas)
- `docs/GUIA_COMPLETO_CLAUDE_CODE_Fase1.md` — v2.0 Quantitative Models (20 etapas)
- `docs/GUIA_COMPLETO_CLAUDE_CODE_Fase2.md` — v3.0 Strategy Engine (18 etapas)
- `docs/GUIA_COMPLETO_CLAUDE_CODE_Fase3_PMS.md` — v4.0 Portfolio Management System (20 etapas)

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
- **Dependencies**: Dagster 1.6+, Grafana (Docker), React 18 (CDN)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| TimescaleDB over InfluxDB | SQLAlchemy compatibility, SQL interface, compression | ✓ Good |
| BCB swap series for DI curve | Free alternative to Bloomberg DI futures; 12 tenors daily | ✓ Good |
| Tesouro Direto for NTN-B rates | Free JSON API with current prices; historical CSVs | ✓ Good |
| MongoDB for unstructured data | Agent outputs, LLM responses, document storage | ⚠️ Revisit — not heavily used yet |
| Kafka for event streaming | Future: real-time signal propagation between agents | ⚠️ Revisit — not used in current batch model |
| Point-in-time via release_time | Prevents look-ahead bias in backtesting | ✓ Good |
| Monorepo structure | All components in one repo for now | ✓ Good |
| ON CONFLICT DO NOTHING | Idempotent inserts enable safe re-runs | ✓ Good |
| BaseConnector ABC pattern | Consistent interface across all 11 connectors | ✓ Good |
| Template Method for agents | BaseAgent.run() orchestrates load→features→models→narrative | ✓ Good |
| Enhance not replace (v3.0) | Existing v2.0 components enhanced, not rewritten | ✓ Good — coexistence works |
| Coexisting strategies (v3.0) | New strategies (FX-02) live alongside existing (FX_BR_01) | ✓ Good — 24 strategies total |
| Dagster over custom pipeline (v3.0) | Scheduling, retry, monitoring UI | ✓ Good — 26+ assets, 3 schedules |
| CDN-only React (v2.0-v4.0) | No build tooling, Babel in-browser JSX | ✓ Good — works for complexity level |
| Dict-based positions (v4.0) | Decoupled from ORM for flexibility and testability | ✓ Good |
| Bloomberg-dense dark theme (v4.0) | Professional operational UI for PMS pages | ✓ Good |
| Redis write-through + invalidation (v4.0) | Instant post-write reads, graceful degradation | ✓ Good |
| Immutable position correction (v4.0) | Close at entry price + reopen; never delete records | ✓ Good — audit trail preserved |
| Template-based LLM fallback (v2.0-v4.0) | Works without API key; enhanced when key available | ✓ Good |

---
*Last updated: 2026-02-26 after v4.0 milestone — all milestones complete*
