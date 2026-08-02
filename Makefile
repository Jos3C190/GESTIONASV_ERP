# ERP System — Makefile. Conventional targets.
# All heavy lifting is delegated to docker compose / scripts.

.DEFAULT_GOAL := help
.PHONY: help up down restart logs ps build seed reset-db test test-backend test-frontend \
        test-unit test-integration test-e2e lint fmt clean setup db-shell backend-shell frontend-shell security-scan

COMPOSE := docker compose
COMPOSE_PROD := $(COMPOSE) -f compose.yaml -f compose.prod.yaml --profile prod

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make <target>\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## One-command setup: copy .env, build, start, migrate, seed
	@./scripts/setup.sh

up: ## Start dev stack and run the idempotent bootstrap seed
	$(COMPOSE) up -d --build

down: ## Stop dev stack
	$(COMPOSE) down

restart: ## Restart dev stack
	$(COMPOSE) restart

logs: ## Tail logs (all services)
	$(COMPOSE) logs -f --tail=200

ps: ## Show container status
	$(COMPOSE) ps

build: ## (Re)build images
	$(COMPOSE) build

seed: ## Re-run the idempotent Grupo Lorena seed
	@./scripts/seed.sh

reset-db: ## Wipe and recreate the database (DESTRUCTIVE)
	@./scripts/reset-db.sh

test: ## Run all tests (backend + frontend)
	@./scripts/run-tests.sh all

test-backend: ## Run backend tests
	@./scripts/run-tests.sh backend

test-frontend: ## Run frontend tests
	@./scripts/run-tests.sh frontend

test-unit: ## Run backend unit tests only
	@./scripts/run-tests.sh backend-unit

test-integration: ## Run backend integration tests only
	@./scripts/run-tests.sh backend-integration

test-e2e: ## Run backend e2e tests only
	@./scripts/run-tests.sh backend-e2e

lint: ## Lint backend and frontend
	@./scripts/run-tests.sh lint

security-scan: ## Run automated Red Team security scan (OWASP ZAP Baseline + Trivy)
	@bash ./scripts/security-scan.sh baseline

security-scan-deep: ## Run deep Red Team security scan (OWASP ZAP OpenAPI DAST + Pytest Fuzzing + Trivy)
	@bash ./scripts/security-scan.sh deep

fmt: ## Format code (backend + frontend)
	$(COMPOSE) exec backend uv run ruff format app tests
	$(COMPOSE) exec frontend pnpm format

clean: ## Remove all containers, volumes, and build cache (DESTRUCTIVE)
	$(COMPOSE) down -v --rmi local --remove-orphans

db-shell: ## Open psql in the db container
	$(COMPOSE) exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

backend-shell: ## Open shell in the backend container
	$(COMPOSE) exec backend bash

frontend-shell: ## Open shell in the frontend container
	$(COMPOSE) exec frontend sh

prod-up: ## Start the prod profile (with nginx)
	$(COMPOSE_PROD) up -d --build

prod-down: ## Stop the prod profile
	$(COMPOSE_PROD) down
