#!/usr/bin/env bash
# Unified test runner. Usage:
#   ./scripts/run-tests.sh all|backend|backend-unit|backend-integration|backend-e2e|frontend|lint
set -euo pipefail
TARGET="${1:-all}"

run_backend() {
  local scope="${1:-all}"
  echo "[tests] Backend ($scope)..."
  if [[ "$scope" == "all" ]]; then
    docker compose exec -T backend uv run pytest -ra
  else
    docker compose exec -T backend uv run pytest "tests/$scope" -ra
  fi
}

run_frontend() {
  echo "[tests] Frontend (vitest)..."
  docker compose exec -T frontend pnpm test:unit --run
}

run_lint() {
  echo "[lint] Backend (ruff)..."
  docker compose exec -T backend uv run --frozen ruff check app tests
  echo "[lint] Frontend (svelte-check)..."
  docker compose exec -T frontend pnpm check
}

case "$TARGET" in
  all)               run_backend all; run_frontend ;;
  backend)           run_backend all ;;
  backend-unit)      run_backend unit ;;
  backend-integration) run_backend integration ;;
  backend-e2e)       run_backend e2e ;;
  frontend)          run_frontend ;;
  lint)              run_lint ;;
  *)
    echo "Usage: $0 {all|backend|backend-unit|backend-integration|backend-e2e|frontend|lint}"
    exit 2 ;;
esac
