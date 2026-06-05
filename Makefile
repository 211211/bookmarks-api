.PHONY: help install migrate run seed test lint podman-up podman-down podman-logs clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install runtime + dev dependencies
	python -m pip install --upgrade pip
	pip install -r requirements-dev.txt

migrate:  ## Apply database migrations
	alembic upgrade head

run:  ## Start the dev server (reload) on :8000
	uvicorn app.main:app --reload

seed:  ## Populate sample data
	python -m scripts.seed

test:  ## Run the test suite
	pytest

lint:  ## Lint with ruff (if installed)
	ruff check .

podman-up:  ## Build & start the Podman stack (API + PostgreSQL)
	podman-compose up --build

podman-down:  ## Stop and remove the Podman stack
	podman-compose down

podman-logs:  ## Tail API logs
	podman-compose logs -f api

clean:  ## Remove local SQLite db and caches
	rm -f bookmarks.db
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
