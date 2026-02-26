#!/bin/bash
# Macro Fund PMS -- Database Backup
# Creates timestamped pg_dump of the full TimescaleDB database.
# Usage: bash scripts/backup.sh
set -euo pipefail

DATE=$(date +%Y-%m-%d_%H%M)
BACKUP_DIR="backups/${DATE}"
mkdir -p "$BACKUP_DIR"

echo "Starting backup at $(date)..."

# Full database dump (custom format for pg_restore compatibility)
docker compose exec -T timescaledb pg_dump \
    -U macro_user \
    -d macro_trading \
    -Fc \
    > "${BACKUP_DIR}/macro_trading_${DATE}.pgdump"

echo "Database dump: ${BACKUP_DIR}/macro_trading_${DATE}.pgdump"

# Export PMS tables as CSV for quick inspection
for TABLE in portfolio_positions trade_proposals decision_journal daily_briefings position_pnl_history; do
    docker compose exec -T timescaledb psql \
        -U macro_user -d macro_trading \
        -c "\\COPY ${TABLE} TO STDOUT CSV HEADER" \
        > "${BACKUP_DIR}/${TABLE}_${DATE}.csv" 2>/dev/null || true
done

echo "CSV exports: ${BACKUP_DIR}/*.csv"

# Calculate backup size
SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo ""
echo "Backup complete: ${BACKUP_DIR} (${SIZE})"
echo "Finished at $(date)"
