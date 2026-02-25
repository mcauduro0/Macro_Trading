# GO-LIVE CHECKLIST

## Macro Fund PMS -- Production Deployment Checklist

**Version:** 1.0
**Last Updated:** 2026-02-25
**System:** Macro Trading Platform v4.0 (PMS)

---

## 1. Infrastructure Prerequisites

- [ ] **TimescaleDB**: Container running (`docker compose ps timescaledb` shows healthy)
- [ ] **TimescaleDB**: Connection tested (`make psql` opens interactive shell)
- [ ] **TimescaleDB**: Market data available up to D-1 (query `SELECT MAX(date) FROM market_data`)
- [ ] **TimescaleDB**: All PMS tables created (portfolio_positions, trade_proposals, decision_journal, daily_briefings, position_pnl_history)
- [ ] **Redis**: Container running and responding (`docker compose exec redis redis-cli ping` returns PONG)
- [ ] **Redis**: Cache eviction policy set (maxmemory-policy allkeys-lru)
- [ ] **FastAPI**: All endpoints responding (`GET /health` returns 200)
- [ ] **FastAPI**: PMS API endpoints registered (`GET /api/v1/pms/book/positions`, `/api/v1/pms/proposals`, `/api/v1/pms/journal`)
- [ ] **Dagster**: PMS pipeline assets defined and visible in Dagster UI (port 3001)
- [ ] **Dagster**: Pipeline tested with manual trigger (`make dagster-run-all`)
- [ ] **Docker Compose**: `docker compose up -d` starts core services (timescaledb, redis, mongodb)
- [ ] **Docker Compose**: No container restart loops (`docker compose ps` shows all healthy)

## 2. PMS Configuration

- [ ] **Risk Limits**: PMSRiskLimits reviewed and configured in `src/pms/risk_limits_config.py`
- [ ] **AUM**: Initial fund AUM value set in settings (`FUND_AUM_BRL` environment variable)
- [ ] **LLM API Key**: Anthropic API key configured (`ANTHROPIC_API_KEY`) for LLM narrative generation (optional -- template fallback exists)
- [ ] **Timezone**: System timezone set to `America/Sao_Paulo` in environment config
- [ ] **Transaction Costs**: Default BPS configured in TransactionCostModel
- [ ] **Position Limits**: Max positions per asset class reviewed
- [ ] **VaR Parameters**: Confidence level (95%/99%) and lookback period (756 days) confirmed

## 3. Data Quality

- [ ] **Phase 2 Verification**: `python scripts/verify_phase2.py` passes all checks (v3.0 components)
- [ ] **Phase 3 Verification**: `python scripts/verify_phase3.py` passes all checks (v4.0 PMS components)
- [ ] **Key Series Updated**: SELIC rate current (BCB connector)
- [ ] **Key Series Updated**: DI curve available (B3/ANBIMA connector)
- [ ] **Key Series Updated**: USDBRL exchange rate current
- [ ] **Key Series Updated**: IPCA inflation data current
- [ ] **Historical Depth**: At least 252 trading days of market data available for historical VaR calculation
- [ ] **Agent Execution**: All 5 agents ran successfully on the last business day
- [ ] **Signal Quality**: Signal aggregation producing valid composite signals
- [ ] **Data Freshness**: No stale series older than 3 business days in critical feeds

## 4. PMS Workflow Smoke Test

- [ ] **Open Position**: `POST /api/v1/pms/book/positions/open` creates a test position successfully
- [ ] **Decision Journal**: Entry automatically created for position open event
- [ ] **Execute MTM**: `POST /api/v1/pms/book/mtm` calculates mark-to-market valuations
- [ ] **P&L Verification**: Unrealized P&L calculated correctly (manual cross-check with known prices)
- [ ] **Morning Pack**: `POST /api/v1/pms/morning-pack/generate` produces a briefing
- [ ] **Proposals Generated**: Trade proposals appear in Morning Pack output
- [ ] **Approve Proposal**: Successfully approve a test trade proposal
- [ ] **Reject Proposal**: Successfully reject a test proposal with mandatory notes
- [ ] **Close Position**: Close test position and verify realized P&L recorded
- [ ] **Audit Trail**: Complete trail visible in Decision Journal (open -> MTM -> approve/reject -> close)
- [ ] **Risk Monitor**: Risk metrics update after position changes
- [ ] **Performance Attribution**: Attribution calculations run without errors

## 5. Backups

- [ ] **Backup Script**: `bash scripts/backup.sh` executes without errors
- [ ] **Backup Output**: Timestamped backup file created in `backups/` directory
- [ ] **Backup Contents**: pg_dump file and CSV exports for PMS tables present
- [ ] **Restore Test**: `bash scripts/restore.sh <backup_file>` restores database successfully
- [ ] **Post-Restore Verification**: Data integrity confirmed after restore
- [ ] **DR Playbook**: `docs/DR_PLAYBOOK.md` reviewed by operations team

## 6. Monitoring

- [ ] **Grafana**: Dashboards loading at port 3002 (start with `docker compose --profile monitoring up -d`)
- [ ] **Grafana Dashboards**: All 4 v3.0 dashboards operational (Pipeline Health, Data Quality, Macro, Risk)
- [ ] **AlertManager**: 10 default alert rules configured and active
- [ ] **Alert Channels**: Slack and email notification channels tested
- [ ] **Dagster UI**: Accessible at port 3001, showing asset lineage
- [ ] **Log Rotation**: Application logs configured with size-based rotation
- [ ] **Disk Space**: Sufficient storage for 30+ days of data and backups

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Portfolio Manager | | | |
| System Administrator | | | |
| Risk Officer | | | |

---

**Notes:**
- All items must be checked before moving to live trading
- Failed items should be documented with remediation plan
- Re-run this checklist after any infrastructure changes
- Keep a dated copy of each completed checklist in `backups/checklists/`
