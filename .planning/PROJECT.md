# Macro Fund System — Portfolio Management System

## What This Is

A comprehensive macro trading system for a global macro hedge fund focused on Brazil and the US. The system has 11 data connectors (250+ series), 5 AI-driven analytical agents, 24+ trading strategies across all asset classes, NLP pipeline for central bank communications, Bayesian signal aggregation, Monte Carlo VaR risk engine, Black-Litterman portfolio optimization, Dagster orchestration, Grafana monitoring, and a React multi-page dashboard. This milestone adds a Portfolio Management System (PMS) with position management, trade workflow with human-in-the-loop approval, operational screens, and production readiness.

## Core Value

Reliable, point-in-time-correct macro and market data flowing into a queryable system — the foundation everything else (agents, strategies, risk, portfolio management) depends on. If the data layer doesn't work, nothing works.

## Current Milestone: v4.0 Portfolio Management System (PMS)

**Goal:** Build an operational Portfolio Management System with position tracking, human-in-the-loop trade workflow, morning briefing pack, real-time risk monitoring, performance attribution, 7 operational frontend screens, compliance/audit, and production infrastructure (Redis cache, Dagster PMS pipeline, Go-Live checklist).

**Target features:**
- PMS database schemas (positions, trades, orders, approvals, attribution)
- Position Manager with real-time tracking and P&L calculation
- Trade Workflow with human-in-the-loop approval (suggested -> review -> approve/reject -> execute)
- 20+ new PMS API endpoints
- Morning Pack (daily briefing: market snapshot, overnight moves, signal summary, risk status)
- Risk Monitor (real-time limit tracking, breach alerts, exposure heatmap)
- Performance Attribution (Brinson-Fachler, factor-based, strategy-level P&L decomposition)
- Design System (reusable component library for operational screens)
- 7 operational frontend screens (Morning Pack, Position Book, Trade Blotter, Risk Monitor, Performance Attribution, Decision Journal, Agent Intelligence)
- Compliance, Audit & Security (audit trail, trade logging, role-based access)
- Redis Cache Optimization (hot path caching for PMS queries)
- Dagster PMS Daily Pipeline (morning pack -> signals -> trades -> risk -> report)
- Go-Live Checklist & Disaster Recovery
- Verification script and integration tests

## Requirements

### Validated

- [x] Docker Compose stack with TimescaleDB, Redis, MongoDB, Kafka, MinIO
- [x] SQLAlchemy 2.0 ORM models with 10 tables including 7 TimescaleDB hypertables
- [x] 11 data connectors covering Brazil + US macro data (250+ series)
- [x] 5 analytical agents (Inflation, Monetary Policy, Fiscal, FX Equilibrium, Cross-Asset)
- [x] 24+ trading strategies across FX, rates, inflation, cupom, sovereign, cross-asset
- [x] NLP pipeline for COPOM/FOMC communications (scrapers, hawk/dove sentiment)
- [x] Signal aggregation v2 (Bayesian, crowding, staleness)
- [x] Risk engine v2 (Monte Carlo VaR, reverse stress, component VaR)
- [x] Portfolio optimization (Black-Litterman, mean-variance, Kelly sizing)
- [x] Dagster orchestration (22 assets, dependency graph, 3 schedules)
- [x] Grafana monitoring (4 dashboards, alert system)
- [x] React multi-page dashboard (5 pages: Strategies, Signals, Risk, Portfolio, Agents)
- [x] API with 30+ endpoints, WebSocket channels, daily reports

### Active

*See REQUIREMENTS.md for full REQ-ID list*

### Out of Scope

- Live order execution to exchanges — PMS manages positions and approvals, not FIX connectivity
- Multi-tenant / multi-fund — single fund for now
- Bloomberg terminal integration — using free data sources only
- ETFs, mutual funds as instruments — stocks only per project constraints
- Mobile app / PWA — desktop-first operational screens
- Kubernetes / Helm deployment — Docker Compose sufficient for now

## Context

**Domain**: Global macro trading, focused on Brazil-US axis. The system has the full analytical pipeline (data -> agents -> strategies -> signals -> risk -> portfolio). This milestone adds the operational layer: how a portfolio manager interacts with the system daily (morning briefing, position review, trade approval, risk monitoring, performance review).

**Existing Infrastructure** (from v1.0 + v2.0 + v3.0):
- TimescaleDB with 10+ tables, 7 hypertables, compression policies
- 11 connectors, 250+ macro series, point-in-time release_time tracking
- 5 agents with quantitative models and LLM narrative
- 24+ strategies with StrategyRegistry, BacktestEngine v2
- NLP pipeline: COPOM/FOMC scrapers, sentiment analysis
- Signal aggregation v2, Risk engine v2, Portfolio optimization
- Dagster orchestration, Grafana monitoring, AlertManager
- React multi-page dashboard (CDN-only, HashRouter)
- FastAPI with 30+ endpoints, WebSocket channels
- Daily report generator, CI/CD pipeline

**Guide Reference**: `docs/GUIA_COMPLETO_CLAUDE_CODE_Fase3.md` — 20 etapas with detailed specifications for all v4.0 PMS components.

## Constraints

- **Tech Stack**: Python 3.11+, SQLAlchemy 2.0 async, FastAPI, Docker Compose
- **Data Sources**: Free APIs only — no Bloomberg
- **Infrastructure**: Docker (TimescaleDB, Redis, MongoDB, Kafka, MinIO) — 16GB+ RAM
- **Investment Focus**: Stocks only, no ETFs or mutual funds
- **LLM Preference**: Claude Opus 4.5/4.6 for narrative generation
- **Real Data Only**: No mock data in production
- **Point-in-Time**: All agent/strategy computations must respect release_time constraints
- **Human-in-the-Loop**: Trade execution requires explicit PM approval
- **Existing Dependencies**: Dagster 1.6+, Grafana (Docker), Node.js 18+ (React dashboard)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| TimescaleDB over InfluxDB | SQLAlchemy compatibility, SQL interface, compression | Good |
| BCB swap series for DI curve | Free alternative to Bloomberg DI futures; 12 tenors daily | Good |
| Point-in-time via release_time | Prevents look-ahead bias in backtesting | Good |
| Monorepo structure | All components in one repo for now | Good |
| BaseConnector ABC pattern | Consistent interface across all 11 connectors | Good |
| Template Method for agents | BaseAgent.run() orchestrates load->features->models->narrative | Good |
| Enhance not replace | Build on existing code, don't rewrite | Good |
| Coexisting strategies | New strategies live alongside existing ones | Good |
| Dagster over custom pipeline | Scheduling, retry, monitoring UI | Good |
| CDN-only React | No build step, HashRouter, unpkg CDN | Good |
| Human-in-the-loop trades | PM reviews and approves before execution | — Pending |
| PMS as operational layer | Separate from analytical pipeline, consumes its outputs | — Pending |

---
*Last updated: 2026-02-23 after milestone v4.0 started*
