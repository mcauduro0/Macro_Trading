# Macro Hedge Fund AI System — Roadmap

## Milestone: v1.0 — Full Production Trading System

### Overview
Build a production-grade macro trading system for a global macro hedge fund focused on Brazil and USA. The system features ~25 strategies operating FX, rates, inflation, cupom cambial, and sovereign credit, powered by 5 specialized AI agents.

### Phase 0: Data Infrastructure
**Goal:** Build the complete data foundation — Docker services, database schemas, 11 data connectors, 200+ macro series, transforms, FastAPI API, and data quality framework.
**Success Criteria:**
- Docker Compose stack running (TimescaleDB, Redis, MongoDB, Kafka, MinIO)
- 10 database tables (9 hypertables + 1 reference table) with TimescaleDB compression
- 11 data connectors operational (BCB SGS, FRED, BCB Focus, B3, ANBIMA, IBGE, STN, CFTC, Treasury, Yahoo, BCB PTAX/FX Flow)
- 200+ macro series seeded and backfilled (2010-present)
- Silver layer transforms (curves, returns, macro, vol surface)
- FastAPI with 12+ endpoints
- Data quality checks passing (score > 80/100)
- `make verify` returns PASS

### Phase 1: Quantitative Models & Agents
**Goal:** Build the analytical agent framework, 5 specialized agents, backtesting engine, and initial 8 trading strategies.
**Success Criteria:**
- Agent Framework (BaseAgent, signals, reports, data loader)
- 5 Agents: Inflation, Monetary Policy, Fiscal, FX Equilibrium, Cross-Asset
- Backtesting Engine with point-in-time correctness
- 8 Trading Strategies across rates, inflation, FX, cupom cambial, sovereign
- Signal Aggregation & Portfolio Construction
- Risk Management (VaR, limits, circuit breakers)
- Daily orchestration pipeline
- Web dashboard

### Phase 2: Strategy Engine, Risk & Portfolio Management
**Goal:** Scale to 25+ strategies, add NLP pipeline, production-grade risk engine, portfolio optimization, and orchestration.
**Success Criteria:**
- 17+ additional strategies (total ~25)
- NLP Pipeline for COPOM/FOMC communications
- Risk Engine (VaR/CVaR 3 methods, 6 stress scenarios, 9 limits)
- Portfolio Construction (risk parity, Black-Litterman, mean-variance)
- Dagster orchestration with full DAG
- Grafana monitoring (4 dashboards)
- Alert system (10 rules)
- CI/CD pipeline

### Phase 3: Production Infrastructure & Live Trading
**Goal:** Production deployment with execution management, real-time feeds, compliance, security, and go-live readiness.
**Success Criteria:**
- Execution Management System (Order, Fill, Position, PnL lifecycle)
- Paper/B3/CME gateways (FIX 4.4)
- Kafka real-time streaming with Bloomberg/Refinitiv adapters
- Compliance & audit logging (dual-write, 7-year retention)
- Pre-trade risk controls
- Kubernetes + Helm deployment
- CI/CD (GitHub Actions: dev -> staging -> prod)
- JWT Auth + Rate Limiting + Emergency Stop
- Go-Live Checklist verified
