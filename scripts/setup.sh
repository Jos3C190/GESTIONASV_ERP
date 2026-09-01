#!/usr/bin/env bash
# ERP System — reproducible single-command development setup.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

git config core.hooksPath .githooks 2>/dev/null || true

log()  { printf "${GREEN}[setup]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[setup]${NC} %s\n" "$*"; }
info() { printf "${CYAN}[setup]${NC} %s\n" "$*"; }
err()  { printf "${RED}[setup]${NC} %s\n" "$*" >&2; }

if [[ ! -f .env ]]; then
  log "Copying .env.example -> .env"
  cp .env.example .env
  warn ".env created from the development template. Review all secrets before production use."
else
  info ".env already exists — leaving it untouched."
fi

random_hex() {
  local bytes="$1"
  od -An -N"$bytes" -tx1 /dev/urandom | tr -d ' \n'
}

ensure_secret() {
  local key="$1"
  local marker="$2"
  local bytes="$3"
  local value
  value=$(grep -E "^${key}=" .env 2>/dev/null | tail -n 1 | cut -d= -f2- || true)
  if [[ -z "$value" || "$value" == "$marker" ]]; then
    if grep -qE "^${key}=" .env; then
      sed -i.bak "s|^${key}=.*|${key}=$(random_hex "$bytes")|" .env
      rm -f .env.bak
    else
      printf '\n%s=%s\n' "$key" "$(random_hex "$bytes")" >> .env
    fi
    log "Generated local secret: $key"
  fi
}

ensure_secret "OBJECT_STORAGE_ACCESS_KEY" "CHANGE_ME_GENERATE_LOCAL_ACCESS_KEY" 16
ensure_secret "OBJECT_STORAGE_SECRET_KEY" "CHANGE_ME_GENERATE_LOCAL_SECRET_KEY" 32
ensure_secret "REDIS_PASSWORD" "CHANGE_ME_GENERATE_LOCAL_REDIS_PASSWORD" 32
ensure_secret "GRAFANA_ADMIN_PASSWORD" "CHANGE_ME_GENERATE_LOCAL_GRAFANA_PASSWORD" 32

grafana_user=$(grep -E '^GRAFANA_ADMIN_USER=' .env 2>/dev/null | tail -n 1 | cut -d= -f2- | tr -d '\r' || true)
grafana_user=${grafana_user:-admin}

log "Building and starting ERP services and the local observability stack..."
docker compose up -d --build

log "Waiting for PostgreSQL..."
for i in $(seq 1 60); do
  status=$(docker compose ps -q db | xargs -I{} docker inspect --format '{{json .State.Health.Status}}' {} 2>/dev/null || true)
  if [[ "$status" == *"healthy"* ]]; then
    log "PostgreSQL is healthy."
    break
  fi
  sleep 2
  if [[ $i -eq 60 ]]; then
    err "PostgreSQL did not become healthy. Run 'docker compose logs db'."
    exit 1
  fi
done

log "Waiting for the backend, migration 0042, document services and OpenTelemetry..."
for i in $(seq 1 150); do
  if curl -sf http://localhost:8000/health/ready 2>/dev/null | grep -q '"status":"ok"'; then
    log "Backend, schema, RustFS, ClamAV, Redis, OCR worker and Collector are healthy."
    break
  fi
  sleep 2
  if [[ $i -eq 150 ]]; then
    err "The document-processing stack did not become healthy. Run 'docker compose logs backend redis ocr-worker'."
    exit 1
  fi
done

log "Waiting for Grafana, Prometheus and Alertmanager..."
for i in $(seq 1 90); do
  if curl -sf http://localhost:3000/api/health 2>/dev/null | grep -q '"database"'; then
    if curl -sf http://localhost:9090/-/ready >/dev/null 2>&1 && \
       curl -sf http://localhost:9093/-/ready >/dev/null 2>&1; then
      log "Observability interfaces are healthy."
      break
    fi
  fi
  sleep 2
  if [[ $i -eq 90 ]]; then
    err "The observability stack did not become healthy. Run 'make observability-logs'."
    exit 1
  fi
done

log "Verifying the one-shot Grupo Lorena bootstrap job..."
seed_id=$(docker compose ps -a -q seed)
if [[ -z "$seed_id" ]]; then
  err "The seed container was not created. Run 'docker compose logs seed'."
  exit 1
fi
seed_status=$(docker inspect --format '{{.State.Status}}:{{.State.ExitCode}}' "$seed_id")
if [[ "$seed_status" != "exited:0" ]]; then
  err "The seed did not finish successfully ($seed_status)."
  docker compose logs seed
  exit 1
fi
log "Grupo Lorena seed completed successfully."

log "Waiting for the frontend..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:5173/healthz >/dev/null 2>&1; then
    log "Frontend is healthy."
    break
  fi
  sleep 2
  if [[ $i -eq 60 ]]; then
    err "Frontend did not become healthy. Run 'docker compose logs frontend'."
    exit 1
  fi
done

echo
log "================ ERP System is ready ================"
info "Frontend:  http://localhost:5173"
info "Backend:   http://localhost:8000"
info "API docs:  http://localhost:8000/docs"
info "RustFS:    http://localhost:9001"
info "Redis:     127.0.0.1:6379 (password in .env)"
info "Grafana:   http://localhost:3000 (user: $grafana_user)"
info "Prometheus:http://localhost:9090"
info "Alerts:    http://localhost:9093"
info "Username:  ${SUPER_ADMIN_USERNAME:-superadmin}"
info "Password:  the SUPER_ADMIN_PASSWORD value from .env"
echo
warn "Change development credentials and secrets before any production deployment."
