.PHONY: setup up up-full down down-clean ps logs migrate migration install lint test verify seed backfill backfill-fast api quality psql daily daily-dry daily-date test-integration test-all dagster dagster-run-all verify-pms verify-all backup restore morning-pack pms-dev

# ── Setup ────────────────────────────────────────────────────────────
# Full first-time setup
setup:
	cp -n .env.example .env || true
	pip install -e ".[dev]"
	docker compose pull

# ── Docker ───────────────────────────────────────────────────────────
# Start core services (TimescaleDB, Redis, MongoDB, MinIO)
up:
	docker compose up -d
	@echo "Waiting for services..."
	@sleep 5
	@docker compose ps

# Start all services including Kafka
up-full:
	docker compose --profile full up -d

# Stop all services
down:
	docker compose down

# Stop all services and remove volumes
down-clean:
	docker compose down -v

# Show running services
ps:
	docker compose ps

# Follow service logs
logs:
	docker compose logs -f

# ── Database ─────────────────────────────────────────────────────────
# Run database migrations
migrate:
	alembic upgrade head

# Create a new migration (usage: make migration msg="description")
migration:
	alembic revision --autogenerate -m "$(msg)"

# Open psql shell on TimescaleDB
psql:
	docker exec -it $$(docker compose ps -q timescaledb) psql -U macro_user -d macro_trading

# ── Data Pipeline ────────────────────────────────────────────────────
# Seed reference data (instruments + series metadata)
seed:
	python scripts/seed_instruments.py
	python scripts/seed_series_metadata.py

# Full historical backfill (all sources, from 2010)
backfill:
	python scripts/backfill.py --source all --start-date 2010-01-01

# Fast backfill (key sources only, from 2020)
backfill-fast:
	python scripts/backfill.py --source bcb_sgs,fred,yahoo --start-date 2020-01-01

# ── Development ──────────────────────────────────────────────────────
# Install project in editable mode with dev dependencies
install:
	pip install -e ".[dev]"

# Run linter
lint:
	ruff check src/

# Run tests
test:
	pytest tests/ -v --cov=src

# Start the FastAPI server
api:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# ── Verification ─────────────────────────────────────────────────────
# Full infrastructure verification
verify:
	python scripts/verify_infrastructure.py

# Quick verification (skip data quality)
verify-quick:
	python scripts/verify_infrastructure.py --quick

# Run data quality checks
quality:
	python -c "from src.quality.checks import DataQualityChecker; import json; print(json.dumps(DataQualityChecker().run_all_checks(), indent=2))"

# ── Daily Pipeline ────────────────────────────────────────────────
# Run daily pipeline for today
daily:
	python scripts/daily_run.py

# Run daily pipeline in dry-run mode (no DB writes)
daily-dry:
	python scripts/daily_run.py --dry-run

# Run daily pipeline for a specific date
daily-date:
	python scripts/daily_run.py --date $(DATE)

# ── Integration Tests ────────────────────────────────────────────────
# Run integration tests only
test-integration:
	pytest tests/test_integration/ -v

# Run all tests (unit + integration)
test-all:
	pytest tests/ -v --cov=src

# ── Dagster Orchestration ────────────────────────────────────────────
# Start Dagster webserver (UI at http://localhost:3001)
dagster:
	docker compose --profile dagster up -d dagster-webserver
	@echo "Dagster UI available at http://localhost:3001"

# Run full pipeline (materialize all assets in dependency order)
dagster-run-all:
	docker compose --profile dagster exec dagster-webserver dagster asset materialize --select '*' -m src.orchestration.definitions

# ── PMS Operations ──────────────────────────────────────────────
# Verify all PMS components (v4.0)
verify-pms:
	python scripts/verify_phase3.py

# Full system verification (v1-v4)
verify-all:
	python scripts/verify_phase2.py && python scripts/verify_phase3.py

# Database backup
backup:
	bash scripts/backup.sh

# Database restore (usage: make restore FILE=backups/2026-02-25_1800/macro_trading_2026-02-25_1800.pgdump)
restore:
	bash scripts/restore.sh $(FILE)

# Generate morning pack manually
morning-pack:
	python -c "from src.pms.morning_pack import MorningPackService; from datetime import date; import asyncio; ms = MorningPackService(); print(asyncio.run(ms.generate(briefing_date=date.today())))"

# Start PMS development (API + Docker)
pms-dev:
	docker compose up -d
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
