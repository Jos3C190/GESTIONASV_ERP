#!/usr/bin/env bash
# Build and scan every project-owned backend runtime image.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
FAILED=0

cd "$ROOT_DIR"
mkdir -p reports

run_step() {
    local label="$1"
    shift
    echo "--> $label"
    if "$@"; then
        echo "    OK: $label"
    else
        local code=$?
        echo "    FAILED ($code): $label" >&2
        FAILED=1
    fi
}

run_step "Build backend dev" \
    docker build --target dev -t erp-security-backend-dev:local backend
run_step "Build backend prod" \
    docker build --target prod -t erp-security-backend-prod:local backend
run_step "Build OCR worker" \
    docker build --target ocr -t erp-security-ocr:local backend
run_step "Build Dockerfile default (Render)" \
    docker build -t erp-security-render-default:local backend

echo "--> Validate default Dockerfile command"
if render_cmd="$(docker image inspect erp-security-render-default:local --format '{{json .Config.Cmd}}')" \
    && [[ "$render_cmd" == *uvicorn* ]] \
    && [[ "$render_cmd" != *arq* ]]; then
    echo "    OK: default image starts the production API"
else
    echo "    FAILED: default image must start Uvicorn, not ARQ (${render_cmd:-unavailable})" >&2
    FAILED=1
fi

run_step "Trivy backend dev libraries" \
    docker compose --profile security run --rm security-trivy-backend-dev
run_step "Trivy backend dev OS (Debian severity)" \
    docker compose --profile security run --rm security-trivy-backend-dev-os
run_step "Trivy backend prod libraries" \
    docker compose --profile security run --rm security-trivy-backend-prod
run_step "Trivy backend prod OS (Debian severity)" \
    docker compose --profile security run --rm security-trivy-backend-prod-os
run_step "Trivy OCR worker libraries" \
    docker compose --profile security run --rm security-trivy-ocr
run_step "Trivy OCR worker OS (Debian severity)" \
    docker compose --profile security run --rm security-trivy-ocr-os

if [[ "$FAILED" -ne 0 ]]; then
    exit 1
fi

echo "All project-owned backend images passed library and Debian OS gates."
