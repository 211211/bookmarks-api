# Bookmarks API — developer task runner.
# Run `make` (or `make help`) to list targets.
.DEFAULT_GOAL := help

VENV ?= .venv
HOST ?= 127.0.0.1
PORT ?= 8000

# Use the project venv if present, otherwise fall back to system python3 so the
# targets work whether or not a venv has been created/activated.
ifeq ($(wildcard $(VENV)/bin/python),)
PY := python3
else
PY := $(VENV)/bin/python
endif

.PHONY: help venv install migrate makemigration downgrade run seed seed-reset \
        test cov lint format audit check openapi db-reset clean \
        build up down logs ps

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Setup ──────────────────────────────────────────────────────────────────
venv: ## Create the virtualenv (.venv)
	python3 -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip

install: venv ## Create venv + install dev dependencies
	$(VENV)/bin/pip install -r requirements-dev.txt

# ── Database / migrations ──────────────────────────────────────────────────
migrate: ## Apply all migrations (upgrade head)
	$(PY) -m alembic upgrade head

makemigration: ## Autogenerate a migration: make makemigration m="message"
	$(PY) -m alembic revision --autogenerate -m "$(m)"

downgrade: ## Roll back the most recent migration
	$(PY) -m alembic downgrade -1

db-reset: ## Delete the local SQLite db, then migrate + seed
	rm -f bookmarks.db
	$(PY) -m alembic upgrade head
	$(PY) -m scripts.seed

# ── Run / data ─────────────────────────────────────────────────────────────
run: ## Run the dev server with autoreload (HOST/PORT overridable)
	$(PY) -m uvicorn app.main:app --reload --host $(HOST) --port $(PORT)

seed: ## Populate sample data
	$(PY) -m scripts.seed

seed-reset: ## Wipe and reseed sample data
	$(PY) -m scripts.seed --reset

# ── Quality ────────────────────────────────────────────────────────────────
test: ## Run the test suite
	$(PY) -m pytest

cov: ## Run tests with a coverage report
	$(PY) -m pytest --cov=app --cov-report=term-missing

lint: ## Lint with ruff
	$(PY) -m ruff check .

format: ## Auto-format and fix with ruff
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

audit: ## Scan dependencies for known vulnerabilities (pip-audit)
	$(PY) -m pip_audit -r requirements.txt

check: lint test ## Lint + test (CI gate)

openapi: ## Export the OpenAPI spec to openapi.json
	$(PY) -c "import json; from app.main import app; open('openapi.json','w').write(json.dumps(app.openapi(), indent=2))"
	@echo "wrote openapi.json"

# ── Podman (compose stack: API + PostgreSQL) ───────────────────────────────
build: ## Build the API image
	podman-compose build

up: ## Build & start the stack (API + PostgreSQL)
	podman-compose up --build

down: ## Stop and remove the stack (use ARGS=-v to drop data)
	podman-compose down $(ARGS)

logs: ## Tail API logs
	podman-compose logs -f api

ps: ## Show stack containers
	podman-compose ps

# ── Housekeeping ───────────────────────────────────────────────────────────
clean: ## Remove local db, generated specs, and caches
	rm -f bookmarks.db openapi.json
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
