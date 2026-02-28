#!/usr/bin/env bash
# =============================================================================
# Macro Trading System — Deployment Script
# =============================================================================
# Usage:
#   ./scripts/deploy.sh              # Full deploy (infra + migrations + seed + API)
#   ./scripts/deploy.sh infra        # Only start Docker services
#   ./scripts/deploy.sh migrate      # Only run Alembic migrations
#   ./scripts/deploy.sh seed         # Only seed instruments + series metadata
#   ./scripts/deploy.sh api          # Only (re)start the API container
#   ./scripts/deploy.sh dagster      # Start Dagster webserver + daemon
#   ./scripts/deploy.sh data         # Run initial data loading (connectors)
#   ./scripts/deploy.sh verify       # Run infrastructure verification
#   ./scripts/deploy.sh status       # Show service status
#   ./scripts/deploy.sh stop         # Stop all services
# =============================================================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
preflight() {
    log_info "Running pre-flight checks..."

    if ! command -v docker &>/dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! docker compose version &>/dev/null; then
        log_error "Docker Compose V2 is not available. Please update Docker."
        exit 1
    fi

    if [ ! -f ".env" ]; then
        if [ -f ".env.production" ]; then
            log_warn "No .env found. Copying from .env.production..."
            cp .env.production .env
            log_warn "IMPORTANT: Edit .env with your real credentials before proceeding!"
            exit 1
        elif [ -f ".env.example" ]; then
            log_warn "No .env found. Copying from .env.example..."
            cp .env.example .env
            log_warn "IMPORTANT: Edit .env with your real credentials before proceeding!"
            exit 1
        else
            log_error "No .env, .env.production, or .env.example found."
            exit 1
        fi
    fi

    # Validate critical env vars
    source .env
    if [ "${POSTGRES_PASSWORD:-changeme}" = "changeme" ]; then
        log_warn "POSTGRES_PASSWORD is still 'changeme'. Change it for production!"
    fi
    if [ "${JWT_SECRET_KEY:-changeme-generate-a-real-secret}" = "changeme-generate-a-real-secret" ]; then
        log_warn "JWT_SECRET_KEY is still default. Generate a real secret!"
        log_info "Suggestion: python3 -c \"import secrets; print(secrets.token_hex(32))\""
    fi

    log_ok "Pre-flight checks passed."
}

# ---------------------------------------------------------------------------
# Infrastructure (Docker Compose)
# ---------------------------------------------------------------------------
start_infra() {
    log_info "Starting core infrastructure services..."
    docker compose up -d timescaledb redis mongodb kafka minio

    log_info "Waiting for services to be healthy..."
    local max_wait=120
    local waited=0
    while [ $waited -lt $max_wait ]; do
        local healthy
        healthy=$(docker compose ps --format json 2>/dev/null | grep -c '"healthy"' || true)
        if [ "$healthy" -ge 3 ]; then
            break
        fi
        sleep 5
        waited=$((waited + 5))
        log_info "  Waiting... ($waited/${max_wait}s)"
    done

    # Check individual services
    for svc in timescaledb redis mongodb; do
        if docker compose ps "$svc" 2>/dev/null | grep -q "healthy"; then
            log_ok "$svc is healthy"
        else
            log_warn "$svc may not be healthy yet — check 'docker compose ps'"
        fi
    done
}

# ---------------------------------------------------------------------------
# Alembic migrations
# ---------------------------------------------------------------------------
run_migrations() {
    log_info "Running Alembic migrations..."

    # Update alembic.ini with current DATABASE_URL from .env
    source .env
    local db_url="postgresql://${POSTGRES_USER:-macro_user}:${POSTGRES_PASSWORD}@${POSTGRES_HOST:-localhost}:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-macro_trading}"

    # Run migrations
    SQLALCHEMY_URL="$db_url" alembic upgrade head

    log_ok "All 9 migrations applied successfully."
}

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
seed_data() {
    log_info "Seeding instruments and series metadata..."
    python scripts/seed_instruments.py
    log_ok "Instruments seeded."

    python scripts/seed_series_metadata.py
    log_ok "Series metadata seeded."
}

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
start_api() {
    log_info "Building and starting API container..."
    docker compose up -d --build api
    sleep 5

    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        log_ok "API is running at http://localhost:8000"
        log_ok "Docs at http://localhost:8000/docs"
    else
        log_warn "API may still be starting — check 'docker compose logs api'"
    fi
}

# ---------------------------------------------------------------------------
# Dagster
# ---------------------------------------------------------------------------
start_dagster() {
    log_info "Starting Dagster webserver and daemon..."
    docker compose --profile dagster up -d dagster-webserver dagster-daemon

    sleep 10
    if curl -sf http://localhost:3001 >/dev/null 2>&1; then
        log_ok "Dagster UI at http://localhost:3001"
    else
        log_warn "Dagster may still be starting — check 'docker compose logs dagster-webserver'"
    fi
}

# ---------------------------------------------------------------------------
# Initial data loading
# ---------------------------------------------------------------------------
load_data() {
    log_info "Running initial data loading (connectors)..."
    python scripts/init_data.py
    log_ok "Initial data loading complete."
}

# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
verify() {
    log_info "Running infrastructure verification..."
    python scripts/verify_infrastructure.py
}

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
show_status() {
    log_info "Service status:"
    docker compose ps
    echo ""
    log_info "Dagster services:"
    docker compose --profile dagster ps 2>/dev/null || log_warn "Dagster not started (use './scripts/deploy.sh dagster')"
}

# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------
stop_all() {
    log_info "Stopping all services..."
    docker compose --profile dagster down
    log_ok "All services stopped."
}

# ---------------------------------------------------------------------------
# Full deploy
# ---------------------------------------------------------------------------
full_deploy() {
    preflight
    start_infra
    run_migrations
    seed_data
    start_api
    echo ""
    log_ok "========================================="
    log_ok "  Macro Trading System deployed!"
    log_ok "========================================="
    log_info "API:      http://localhost:8000"
    log_info "API Docs: http://localhost:8000/docs"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Load data:    ./scripts/deploy.sh data"
    log_info "  2. Start Dagster: ./scripts/deploy.sh dagster"
    log_info "  3. Verify:       ./scripts/deploy.sh verify"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
case "${1:-full}" in
    infra)    preflight; start_infra ;;
    migrate)  run_migrations ;;
    seed)     seed_data ;;
    api)      start_api ;;
    dagster)  start_dagster ;;
    data)     load_data ;;
    verify)   verify ;;
    status)   show_status ;;
    stop)     stop_all ;;
    full)     full_deploy ;;
    *)
        echo "Usage: $0 {full|infra|migrate|seed|api|dagster|data|verify|status|stop}"
        exit 1
        ;;
esac
