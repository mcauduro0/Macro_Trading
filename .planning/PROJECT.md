# Macro Fund System — Quantitative Models & Agents

## What This Is

A comprehensive macro trading system for a global macro hedge fund focused on Brazil and the US. Building on a complete data infrastructure (11 connectors, 250+ series, TimescaleDB), this milestone adds AI-driven analytical agents, quantitative models, a backtesting engine, initial trading strategies, signal aggregation, risk management, and a monitoring dashboard.

## Core Value

Reliable, point-in-time-correct macro and market data flowing into a queryable system — the foundation everything else (agents, strategies, risk) depends on. If the data layer doesn't work, nothing works.

## Current Milestone: v2.0 Quantitative Models & Agents

**Goal:** Build 5 analytical agents (Inflation, Monetary Policy, Fiscal, FX Equilibrium, Cross-Asset), a point-in-time backtesting engine, 8 initial trading strategies, signal aggregation, risk management, and a daily pipeline — all powered by the data infrastructure from v1.0.

**Target features:**
- Agent Framework (BaseAgent ABC, signals, reports, point-in-time data loader)
- 5 Analytical Agents with quantitative models
- Event-driven Backtesting Engine with point-in-time correctness
- 8 Trading Strategies (rates, inflation, FX, cupom cambial, sovereign)
- Signal Aggregation & Portfolio Construction
- Risk Management (VaR, limits, circuit breakers)
- Daily Orchestration Pipeline
- LLM Narrative Generation (Claude API)
- Monitoring Dashboard (HTML/React)

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

### Active

*See REQUIREMENTS.md for full REQ-ID list*

### Out of Scope

- Live order execution — research/backtesting focus first
- Multi-user access / authentication — solo user for now
- Bloomberg terminal integration — using free data sources only
- ETFs, mutual funds as investment instruments — stocks only per project constraints
- Production deployment (Kubernetes, Helm) — Phase 2+
- Real-time streaming execution — Phase 2+
- NLP pipeline for central bank communications — Phase 2+
- Additional 17 strategies (total 25) — Phase 2+

## Context

**Domain**: Global macro trading, focused on Brazil-US axis. The system needs 5 specialized analytical agents that understand inflation dynamics, monetary policy, fiscal sustainability, FX equilibrium, and cross-asset regime detection.

**Data Architecture**: Bronze/Silver/Gold layer pattern (v1.0 delivered Bronze+Silver+Gold for data). This milestone adds:
- Agent Layer: 5 analytical agents consuming Silver/Gold data
- Strategy Layer: 8 trading strategies consuming agent signals
- Risk Layer: Portfolio construction, VaR, limits, circuit breakers
- Pipeline: Daily orchestration from data ingestion to risk report

**Existing Infrastructure** (from v1.0):
- TimescaleDB with 10 tables, 7 hypertables, compression policies
- 11 connectors: BCB SGS, FRED, Yahoo Finance, BCB PTAX, BCB Focus, B3/Tesouro Direto, IBGE SIDRA, STN Fiscal, CFTC COT, US Treasury, BCB FX Flow
- 250+ macro series with point-in-time release_time tracking
- Transforms: Nelson-Siegel, returns, z-scores, macro calculations
- FastAPI with 12 endpoints, data quality checks, verification script

**Key Academic References for Agents**:
- Phillips Curve (Friedman 1968, Lucas 1972) — inflation dynamics
- Taylor Rule (Taylor 1993) — monetary policy
- Laubach-Williams (2003) — natural rate estimation via Kalman Filter
- Clark-MacDonald (1998) BEER model — FX fair value
- IMF DSA framework (2013) — debt sustainability
- Hamilton (1989) — regime switching models

**Brazilian Specifics**:
- BCB SGS values use comma as decimal separator
- COPOM meets 8x/year; Focus survey weekly (Mondays)
- IPCA released ~15 days after reference month; IPCA-15 as preview
- DI curve from BCB swap series (proxy for B3 DI futures)
- Inflation target: 3.0% center (CMN)

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
| Template Method for agents | BaseAgent.run() orchestrates load→features→models→narrative | Pending |

---
*Last updated: 2026-02-20 after milestone v2.0 started*
