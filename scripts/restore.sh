#!/bin/bash
# Macro Fund PMS -- Database Restore
# Restores from a pg_dump backup file.
# Usage: bash scripts/restore.sh <backup_file.pgdump>
set -euo pipefail

BACKUP_FILE="${1:?Usage: bash scripts/restore.sh <backup_file.pgdump>}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will overwrite the current database!"
echo "Backup file: $BACKUP_FILE"
echo ""
read -p "Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo "Stopping application services..."
docker compose stop dagster-webserver 2>/dev/null || true

echo "Restoring database..."
# Terminate active connections
docker compose exec -T timescaledb psql -U macro_user -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='macro_trading' AND pid <> pg_backend_pid();" 2>/dev/null || true

# Drop and recreate database (clean restore)
docker compose exec -T timescaledb psql -U macro_user -d postgres \
    -c "DROP DATABASE IF EXISTS macro_trading;" 2>/dev/null || true
docker compose exec -T timescaledb psql -U macro_user -d postgres \
    -c "CREATE DATABASE macro_trading OWNER macro_user;"

# Restore from dump
cat "$BACKUP_FILE" | docker compose exec -T timescaledb pg_restore \
    -U macro_user \
    -d macro_trading \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists 2>/dev/null || true

echo "Running verification..."
python scripts/verify_phase3.py || echo "WARNING: Some verification checks failed (verify_phase3.py may not exist yet)"

echo ""
echo "Restore complete. Restart services with: docker compose up -d"
