.PHONY: up up-full down down-clean ps logs migrate migration install lint test verify

# Start core services (TimescaleDB, Redis, MongoDB, MinIO)
up:
	docker compose up -d

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

# Run database migrations
migrate:
	alembic upgrade head

# Create a new migration (usage: make migration msg="description")
migration:
	alembic revision --autogenerate -m "$(msg)"

# Install project in editable mode with dev dependencies
install:
	pip install -e ".[dev]"

# Run linter
lint:
	ruff check src/

# Run tests
test:
	pytest tests/ -v

# Verify infrastructure connectivity (use after 'make up' and 'make migrate')
verify:
	python scripts/verify_connectivity.py --strict
