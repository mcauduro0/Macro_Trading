# OPERATIONAL RUNBOOK

## Macro Fund PMS -- Daily Operational Procedures

**Version:** 1.0
**Last Updated:** 2026-02-25
**System:** Macro Trading Platform v4.0 (PMS)

---

## Overview

This runbook describes the portfolio manager's daily routine from pre-market through close, plus weekly maintenance tasks. All times are in BRT (America/Sao_Paulo, UTC-3).

The system automates data collection, signal generation, and risk monitoring. The manager's role is to review signals, make trading decisions, execute trades at the broker, and record execution details.

---

## Daily Schedule

### 06:00 -- Pre-Market

**Objective:** Review overnight data and prepare for the trading day.

1. **Check Dagster Pipeline Status**
   - Open Dagster UI at `http://localhost:3001`
   - Verify the scheduled overnight pipeline completed successfully (green status)
   - If pipeline failed: check error details in Dagster UI, trigger manual re-run with `make dagster-run-all`
   - Alternative: check email alerts for pipeline failure notifications

2. **Review Morning Pack**
   - Navigate to PMS Dashboard -> Morning Pack page
   - Or generate manually: `POST /api/v1/pms/morning-pack/generate`
   - Review sections in order:
     - **Macro Snapshot**: Overnight changes in key indicators (SELIC, DI, USDBRL, IPCA)
     - **Agent Intelligence**: Review signals from all 5 analytical agents
     - **Trade Proposals**: New proposals with conviction scores and rationale
     - **Risk Summary**: Current portfolio risk metrics and limit utilization

3. **Review Trade Blotter**
   - Check pending trade proposals sorted by conviction (highest first)
   - Note any proposals that flip existing positions (marked with flip indicator)
   - Review proposals requiring immediate attention (high conviction >= 0.70)

4. **Check Active Risk Alerts**
   - Navigate to PMS Dashboard -> Risk Monitor page
   - Review any WARNING or BREACH alerts
   - Check VaR utilization against limits
   - Note any concentration risk warnings

### 08:30 -- Market Open (BRT)

**Objective:** Execute trading decisions based on morning analysis.

1. **Execute Mark-to-Market with Opening Prices**
   - Via UI: Click "Run MTM" on Position Book page
   - Via API: `POST /api/v1/pms/book/mtm`
   - Verify P&L values are reasonable given overnight moves

2. **Decide on Trade Proposals**
   - For each pending proposal, choose one action:
     - **Approve**: Click approve, fill in execution details (planned size, broker, limit price)
     - **Reject**: Click reject, provide mandatory rejection notes (minimum rationale required)
     - **Defer**: Leave pending for later decision (review again intraday)
   - Priority: Process high-conviction proposals first (>= 0.70)

3. **Execute Approved Trades at Broker**
   - Open broker platform
   - Enter orders for approved proposals
   - Record execution prices, times, and fill quantities
   - Note any partial fills or significant slippage

4. **Record Execution Details in System**
   - Update each approved proposal with actual execution data:
     - Execution price (actual fill price)
     - Execution quantity
     - Execution timestamp
     - Any notes on market conditions during execution

### 10:00 -- 16:00 -- Intraday Monitoring

**Objective:** Monitor positions and react to significant market moves.

1. **Price Monitoring**
   - If significant market moves occur (>1% in key assets), consider running manual MTM
   - Via UI: Click "Run MTM" on Position Book page
   - Via API: `POST /api/v1/pms/book/mtm`

2. **Risk Monitor**
   - Check Risk Monitor page periodically during volatile sessions
   - Watch for approaching risk limits (WARNING alerts at 80% utilization)
   - If BREACH alert triggered: evaluate whether to reduce positions

3. **Decision Journal**
   - Add notes to Decision Journal for significant market events
   - Document rationale for any intraday trading decisions
   - Record observations that may affect future signal generation

4. **Ad-hoc Morning Pack**
   - If macro landscape shifts significantly, generate a new Morning Pack
   - `POST /api/v1/pms/morning-pack/generate`
   - Review updated agent signals and proposals

### 17:30 -- Market Close (BRT)

**Objective:** End-of-day reconciliation and reporting.

1. **Final Mark-to-Market**
   - Execute MTM with closing prices
   - Via UI: Click "Run MTM" on Position Book page
   - Via API: `POST /api/v1/pms/book/mtm`
   - Note: Dagster EOD pipeline runs automatically at 18:00 BRT

2. **Review Daily P&L**
   - Open Position Book page
   - Review per-position unrealized and realized P&L
   - Check total portfolio P&L for the day
   - Compare against CDI benchmark performance

3. **Check Risk Monitor Post-Close**
   - Review end-of-day risk metrics
   - Ensure all positions within risk limits
   - Note any positions approaching concentration limits

4. **Update Position Theses**
   - For positions with significant P&L impact, update thesis notes
   - Add Decision Journal entries for end-of-day observations
   - Document any thesis changes or stop-loss considerations

5. **EOD Pipeline Verification (18:00+)**
   - After Dagster EOD pipeline completes (18:00 BRT):
     - Verify data freshness in dashboard
     - Check that all agents ran successfully
     - Confirm next morning's data will be ready

---

## Weekly Tasks

### Monday Morning (before 08:00)

1. **Performance Attribution Review**
   - Navigate to PMS Dashboard -> Performance Attribution page
   - Review MTD and QTD performance metrics
   - Analyze attribution by:
     - Asset class (FX, Rates, Inflation, Sovereign, Cross-asset)
     - Factor exposure
     - Individual strategy contribution
   - Identify top and bottom contributors

2. **Decision Journal Analysis**
   - Review past week's journal entries
   - Analyze decision patterns:
     - Win/loss ratio on approved proposals
     - Average conviction of winning vs losing trades
     - Rejection patterns (are rejected proposals performing well?)
   - Document insights for strategy refinement

### Friday Afternoon (after market close)

3. **Backup Verification**
   - Verify automated backups completed for the week
   - Run manual backup if needed: `bash scripts/backup.sh`
   - Check backup directory sizes: `du -sh backups/`
   - Ensure at least 2 weeks of backups retained

4. **System Health Check**
   - Check disk usage: `df -h` (ensure >20% free on data volumes)
   - Check Docker container health: `docker compose ps`
   - Review application logs for errors: `docker compose logs --tail=100`
   - Verify log rotation is working (logs not growing unbounded)
   - Check TimescaleDB compression: run compression policy manually if needed

---

## Emergency Procedures

### System Unresponsive

1. Check Docker services: `docker compose ps`
2. Restart all services: `docker compose restart`
3. If specific service down: `docker compose up -d <service_name>`
4. Check logs: `docker compose logs <service_name> --tail=50`
5. If database corrupted: follow `docs/DR_PLAYBOOK.md` Scenario 1

### Data Feed Stale

1. Check connector status via API: `GET /health`
2. Trigger manual data refresh: `python scripts/daily_run.py`
3. If specific source failing: check source API status (BCB, FRED, B3, etc.)
4. Manual price override for MTM if needed: `POST /api/v1/pms/book/mtm` with manual prices

### Risk Limit Breach

1. Immediately review Risk Monitor page
2. Identify which limit(s) breached
3. Determine root cause (position size, market move, VaR increase)
4. Options:
   - Reduce position to bring within limits
   - If temporary breach from market volatility, document in Journal and monitor
   - If systematic issue, review risk limit configuration

---

## Key Endpoints Reference

| Action | Method | Endpoint |
|--------|--------|----------|
| Health Check | GET | `/health` |
| Open Position | POST | `/api/v1/pms/book/positions/open` |
| Close Position | POST | `/api/v1/pms/book/positions/{id}/close` |
| Mark-to-Market | POST | `/api/v1/pms/book/mtm` |
| List Positions | GET | `/api/v1/pms/book/positions` |
| Generate Morning Pack | POST | `/api/v1/pms/morning-pack/generate` |
| Get Proposals | GET | `/api/v1/pms/proposals` |
| Approve Proposal | POST | `/api/v1/pms/proposals/{id}/approve` |
| Reject Proposal | POST | `/api/v1/pms/proposals/{id}/reject` |
| Decision Journal | GET | `/api/v1/pms/journal` |
| Risk Monitor | GET | `/api/v1/pms/risk/monitor` |
| Performance Attribution | GET | `/api/v1/pms/performance/attribution` |

---

## Key Makefile Commands

| Command | Description |
|---------|-------------|
| `make up` | Start core services (TimescaleDB, Redis, MongoDB, MinIO) |
| `make down` | Stop all services |
| `make ps` | Show running services |
| `make logs` | Follow service logs |
| `make api` | Start FastAPI server on port 8000 |
| `make dagster` | Start Dagster UI on port 3001 |
| `make dagster-run-all` | Trigger full pipeline run |
| `make daily` | Run daily data pipeline |
| `make verify` | Run infrastructure verification |
| `make psql` | Open database shell |

---

**Notes:**
- All times are approximate and should be adjusted to actual market schedule
- B3 trading hours: 10:00-17:00 BRT (regular session)
- Pre-market data availability depends on connector source update times
- Keep this runbook updated as new features are added to the system
