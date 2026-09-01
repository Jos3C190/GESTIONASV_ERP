# ERP System — Makefile. Conventional targets.
# All heavy lifting is delegated to docker compose / scripts.

.DEFAULT_GOAL := help
.PHONY: help up down restart logs ps build seed reset-db test test-backend test-frontend \
        test-unit test-integration test-e2e lint fmt clean setup db-shell backend-shell frontend-shell \
        security-scan security-scan-images security-scan-deep storage-backup storage-restore observability-status observability-logs \
        observability-validate observability-restart

COMPOSE := docker compose
COMPOSE_PROD := $(COMPOSE) -f compose.yaml -f compose.prod.yaml --profile prod

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make <target>\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## One-command setup: copy .env, build, start, migrate, seed
	@./scripts/setup.sh

up: ## Start dev stack and run the first-setup bootstrap when needed
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

seed: ## Run the Grupo Lorena bootstrap only when not initialized (or FORCE_SEED=true)
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

security-scan-images: ## Build and scan project-owned backend images with Trivy
	@bash ./scripts/security-scan-images.sh

security-scan-deep: ## Run deep Red Team security scan (OWASP ZAP OpenAPI DAST + Pytest Fuzzing + Trivy)
	@bash ./scripts/security-scan.sh deep

fmt: ## Format code (backend + frontend)
	$(COMPOSE) exec backend uv run ruff format app tests
	$(COMPOSE) exec frontend pnpm format

clean: ## Remove all containers, volumes, and build cache (DESTRUCTIVE)
	$(COMPOSE) down -v --rmi local --remove-orphans

observability-status: ## Show health of the local telemetry stack
	$(COMPOSE) ps grafana prometheus alertmanager otel-collector loki tempo

observability-logs: ## Tail logs from the local telemetry stack
	$(COMPOSE) logs -f --tail=200 grafana prometheus alertmanager otel-collector loki tempo

observability-validate: ## Validate Compose and observability configuration files
	$(COMPOSE) config --quiet
	$(COMPOSE) run --rm --no-deps otel-collector validate --config=/etc/otelcol/config.yaml
	$(COMPOSE) run --rm --no-deps --entrypoint /bin/promtool prometheus check config /etc/prometheus/prometheus.yml
	$(COMPOSE) run --rm --no-deps --entrypoint /bin/promtool prometheus check rules /etc/prometheus/rules/erp-alerts.yml
	$(COMPOSE) run --rm --no-deps --entrypoint /bin/amtool alertmanager check-config /etc/alertmanager/alertmanager.yml
	$(COMPOSE) run --rm --no-deps loki "-verify-config" "-config.file=/etc/loki/loki.yaml"
	$(COMPOSE) run --rm --no-deps tempo "-config.file=/etc/tempo/tempo.yaml" "-config.verify=true"
	$(COMPOSE) run --rm --no-deps -v "$(CURDIR)/observability:/observability:ro" backend \
		python -c "import glob,json; [json.load(open(path, encoding='utf-8')) for path in glob.glob('/observability/grafana/dashboards/*.json')]"

observability-restart: ## Restart the telemetry stack without touching ERP data
	$(COMPOSE) restart grafana prometheus alertmanager otel-collector loki tempo

db-shell: ## Open psql in the db container
	$(COMPOSE) exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

backend-shell: ## Open shell in the backend container
	$(COMPOSE) exec backend bash

frontend-shell: ## Open shell in the frontend container
	$(COMPOSE) exec frontend sh

storage-backup: ## Export the local document bucket under object-storage/backups
	mkdir -p object-storage/backups
	$(COMPOSE) run --rm -v "$(CURDIR)/object-storage/backups:/backup" backend \
		python -m app.infrastructure.storage_backup export /backup

storage-restore: ## Restore BACKUP_DIR from object-storage/backups (set STORAGE_RESTORE_FORCE=true to overwrite)
	@test -n "$(BACKUP_DIR)" || (echo "Usage: make storage-restore BACKUP_DIR=YYYYMMDDTHHMMSSZ" && exit 2)
	$(COMPOSE) run --rm -e STORAGE_RESTORE_FORCE=$(STORAGE_RESTORE_FORCE) \
		-v "$(CURDIR)/object-storage/backups:/backup" backend \
		python -m app.infrastructure.storage_backup restore /backup/$(BACKUP_DIR)

prod-up: ## Start the prod profile (with nginx)
	$(COMPOSE_PROD) up -d --build

prod-down: ## Stop the prod profile
	$(COMPOSE_PROD) down
