# DISASTER RECOVERY PLAYBOOK

## Macro Fund PMS -- Recovery Procedures

**Version:** 1.0
**Last Updated:** 2026-02-25
**System:** Macro Trading Platform v4.0 (PMS)

---

## Overview

This playbook covers recovery procedures for common failure scenarios in the Macro Fund PMS. Each scenario includes symptoms, diagnostic steps, and recovery actions.

**Key Principles:**
- Data immutability: Never delete records. Use correction entries instead.
- Backups first: Before any destructive recovery action, ensure a fresh backup exists.
- Verify after recovery: Always run verification scripts after any restore operation.
- Document everything: Record all incidents and recovery actions in the Decision Journal.

---

## Scenario 1: Database Unavailable (TimescaleDB)

### Symptoms
- API returns HTTP 500 errors on data endpoints
- Dashboard pages show blank/loading indefinitely
- `docker compose ps timescaledb` shows unhealthy or exited status
- Application logs show `connection refused` or `could not connect to server`

### Diagnostic Steps
```bash
# 1. Check container status
docker compose ps timescaledb

# 2. Check container logs for errors
docker compose logs timescaledb --tail=50

# 3. Check if port is accessible
docker compose exec timescaledb pg_isready -U macro_user -d macro_trading

# 4. Check disk space (common cause of DB failure)
df -h
docker system df
```

### Recovery Actions

**If container stopped/crashed:**
```bash
# Restart the container
docker compose up -d timescaledb

# Wait for health check to pass (30 seconds)
sleep 30

# Verify
docker compose ps timescaledb
curl -s http://localhost:8000/health | python -m json.tool
```

**If data corrupted (container starts but queries fail):**
```bash
# 1. Stop all application services
docker compose stop dagster-webserver 2>/dev/null || true

# 2. Restore from latest backup
bash scripts/restore.sh backups/<latest>/macro_trading_<timestamp>.pgdump

# 3. Run migrations to ensure schema is current
alembic upgrade head

# 4. Verify data integrity
python scripts/verify_phase2.py
python scripts/verify_phase3.py || echo "Phase 3 verification not available"

# 5. Restart all services
docker compose up -d
```

**If disk full:**
```bash
# 1. Check which volumes are consuming space
docker system df -v

# 2. Remove old backups (keep last 2 weeks)
ls -lt backups/ | tail -n +15 | xargs rm -rf

# 3. Run TimescaleDB compression manually
docker compose exec timescaledb psql -U macro_user -d macro_trading \
    -c "SELECT compress_chunk(c) FROM show_chunks('position_pnl_history') c WHERE NOT is_compressed;"

# 4. Prune Docker resources
docker system prune -f
```

### Post-Recovery Verification
- [ ] `GET /health` returns 200
- [ ] Position Book loads with correct data
- [ ] MTM runs successfully
- [ ] Decision Journal entries intact

---

## Scenario 2: Redis Unavailable

### Symptoms
- API responses noticeably slower (no cache hits)
- No `X-Cache: HIT` header in API responses
- `docker compose exec redis redis-cli ping` times out or fails
- Application logs show Redis connection errors

### Diagnostic Steps
```bash
# 1. Check container status
docker compose ps redis

# 2. Check container logs
docker compose logs redis --tail=20

# 3. Test connectivity
docker compose exec redis redis-cli ping
```

### Recovery Actions

**Redis is stateless cache -- no data loss on restart.**

```bash
# 1. Restart Redis container
docker compose up -d redis

# 2. Wait for health check
sleep 10

# 3. Verify
docker compose exec redis redis-cli ping
# Expected: PONG

# 4. Verify API health
curl -s http://localhost:8000/health | python -m json.tool
```

**Cache rebuilds automatically on next request.** No manual cache warming needed. The first request for each cached endpoint will be slower (cache miss), then subsequent requests use cache.

### Post-Recovery Verification
- [ ] `redis-cli ping` returns PONG
- [ ] `GET /health` returns 200
- [ ] API response times return to normal within 5 minutes

---

## Scenario 3: Incorrect Position Recorded

### Symptoms
- Position Book shows wrong instrument, size, or direction
- P&L calculations appear incorrect due to wrong entry data
- Manual cross-check reveals discrepancy with broker records

### Important: Data Immutability Rule

**Do NOT delete the incorrect position.** The system maintains an immutable audit trail. All corrections are made through compensating entries.

### Recovery Actions

```
Step 1: Close the incorrect position at entry price (net zero P&L)
  POST /api/v1/pms/book/positions/{incorrect_id}/close
  Body: { "exit_price": <same as entry_price>, "notes": "CORRECTION: Closing incorrect position entry" }

Step 2: Add explanatory note in Decision Journal
  POST /api/v1/pms/journal
  Body: {
    "entry_type": "correction",
    "content": "Position {id} was recorded incorrectly. Closed at entry price for zero P&L. Correct position opened as {new_id}.",
    "related_position_id": "{incorrect_id}"
  }

Step 3: Open the correct position
  POST /api/v1/pms/book/positions/open
  Body: { <correct instrument, size, direction, entry_price> }

Step 4: Verify in Position Book
  - Incorrect position shows as CLOSED with zero P&L
  - Correct position shows as OPEN with accurate entry data
  - Decision Journal shows correction trail
```

### Post-Recovery Verification
- [ ] Incorrect position status: CLOSED, realized P&L: 0
- [ ] Correct position opened with accurate data
- [ ] Decision Journal documents the correction
- [ ] Total portfolio P&L unaffected by correction

---

## Scenario 4: Incorrect Mark-to-Market (Wrong Price)

### Symptoms
- P&L values appear unreasonable given market moves
- MTM prices do not match actual market closing prices
- Suspicion of stale or incorrect price data in system

### Recovery Actions

```
Step 1: Identify the incorrect MTM timestamp and affected positions
  GET /api/v1/pms/book/positions
  Review unrealized_pnl and current_price fields

Step 2: Re-run MTM with correct manual price override
  POST /api/v1/pms/book/mtm
  Body: {
    "manual_prices": {
      "<instrument_id>": <correct_price>
    }
  }

Step 3: Record correction in Decision Journal
  POST /api/v1/pms/journal
  Body: {
    "entry_type": "correction",
    "content": "MTM corrected for {instrument}. Previous price: {wrong}. Correct price: {correct}. Source: {Bloomberg/broker/exchange}."
  }

Step 4: Verify updated P&L
  - Check Position Book for corrected unrealized P&L values
  - Cross-check with manual calculation
```

### Prevention
- Compare MTM prices against multiple sources before accepting
- Set up alerts for unusual P&L moves (>5% daily) in AlertManager
- Review data connector freshness in Grafana Data Quality dashboard

### Post-Recovery Verification
- [ ] Position P&L values match manual calculations
- [ ] Decision Journal records the price correction
- [ ] Risk Monitor reflects corrected values

---

## Scenario 5: Dagster Pipeline Failure

### Symptoms
- Morning Pack not generated (stale data in dashboard)
- Dagster UI shows failed run (red status at `http://localhost:3001`)
- Email/Slack alert received for pipeline failure
- Data appears outdated (check timestamps in API responses)

### Diagnostic Steps
```bash
# 1. Check Dagster container status
docker compose --profile dagster ps dagster-webserver

# 2. Check Dagster logs
docker compose --profile dagster logs dagster-webserver --tail=50

# 3. Open Dagster UI and check run history
# Navigate to http://localhost:3001 -> Runs tab
```

### Recovery Actions

**If Dagster container is down:**
```bash
# Restart Dagster
docker compose --profile dagster up -d dagster-webserver

# Wait for startup
sleep 30

# Verify UI accessible
curl -s http://localhost:3001 > /dev/null && echo "Dagster UI is up" || echo "Dagster UI not responding"
```

**If pipeline run failed (container healthy):**
```bash
# Option 1: Re-trigger full pipeline via Makefile
make dagster-run-all

# Option 2: Re-trigger specific failed asset via Dagster UI
# Navigate to http://localhost:3001 -> Assets -> select failed asset -> Materialize
```

**If pipeline unavailable -- manual fallback:**
```bash
# Generate morning pack manually
curl -X POST http://localhost:8000/api/v1/pms/morning-pack/generate

# Run daily data pipeline manually
python scripts/daily_run.py

# Run agents manually (if needed)
python -c "from src.agents.runner import run_all_agents; run_all_agents()"
```

### Post-Recovery Verification
- [ ] Dagster UI shows successful run (green status)
- [ ] Morning Pack generated with current date
- [ ] Data freshness check: latest data within 1 business day
- [ ] Agent signals updated

---

## General Restore Procedure

This procedure is cross-referenced from all scenarios involving data loss or corruption.

```bash
# 1. Stop application services (keep database and cache running)
docker compose stop dagster-webserver 2>/dev/null || true

# 2. List available backups
ls -lt backups/

# 3. Restore from backup
bash scripts/restore.sh backups/<date>/macro_trading_<timestamp>.pgdump

# 4. Run migrations (in case backup is from older schema version)
alembic upgrade head

# 5. Verify data integrity
python scripts/verify_phase2.py
python scripts/verify_phase3.py || echo "Phase 3 verification not available"

# 6. Restart all services
docker compose up -d

# 7. Verify system health
curl -s http://localhost:8000/health | python -m json.tool
```

### Backup Inventory

| Backup Type | Location | Frequency | Retention |
|-------------|----------|-----------|-----------|
| Full pg_dump | `backups/<date>/macro_trading_*.pgdump` | Daily (manual or scheduled) | 30 days |
| PMS CSV exports | `backups/<date>/*_*.csv` | With each backup run | 30 days |

### Recovery Time Objectives

| Scenario | Expected Recovery Time |
|----------|----------------------|
| Container restart | 1-2 minutes |
| Redis restart (cache rebuild) | 2-5 minutes |
| Full database restore | 10-30 minutes (depends on DB size) |
| Position correction | 5-10 minutes |
| MTM correction | 2-5 minutes |
| Pipeline re-run | 5-15 minutes |

---

## Incident Logging

After any recovery action, create an incident record:

```
Date: YYYY-MM-DD HH:MM
Scenario: [1-5]
Symptoms: [what was observed]
Root Cause: [what caused the failure]
Recovery Actions: [steps taken]
Recovery Time: [how long it took]
Data Loss: [any data lost? Y/N, details]
Prevention: [what can prevent recurrence]
```

Log incidents in the Decision Journal with `entry_type: "incident"` for permanent audit trail.

---

**Notes:**
- Test this playbook quarterly by running through each scenario in a staging environment
- Update recovery procedures when infrastructure changes
- Keep backup scripts and this playbook in version control
- Ensure at least 2 team members are familiar with all recovery procedures
