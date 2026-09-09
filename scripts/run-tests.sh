#!/usr/bin/env bash
# Unified test runner. Usage:
#   ./scripts/run-tests.sh all|backend|backend-unit|backend-integration|backend-e2e|frontend|lint
set -euo pipefail
TARGET="${1:-all}"

PYTEST_STRICT_FLAGS=(-ra -W error::sqlalchemy.exc.SAWarning)

run_backend() {
  local scope="${1:-all}"
  echo "[tests] Backend ($scope)..."
  if [[ "$scope" == "all" ]]; then
    docker compose exec -T backend uv run pytest "${PYTEST_STRICT_FLAGS[@]}" --ignore=tests/unit/test_ocr_worker.py
  elif [[ "$scope" == "unit" ]]; then
    docker compose exec -T backend uv run pytest "tests/$scope" "${PYTEST_STRICT_FLAGS[@]}" --ignore=tests/unit/test_ocr_worker.py
  else
    docker compose exec -T backend uv run pytest "tests/$scope" "${PYTEST_STRICT_FLAGS[@]}"
  fi
}

run_frontend() {
  echo "[tests] Frontend (vitest)..."
  docker compose exec -T frontend pnpm test:unit --run
}

run_backend_quality() {
  echo "[quality] Backend (ruff check)..."
  docker compose exec -T backend uv run --frozen ruff check app tests
  echo "[quality] Backend (ruff format check)..."
  docker compose exec -T backend uv run --frozen ruff format --check app tests
  echo "[quality] Backend (mypy)..."
  docker compose exec -T backend uv run --frozen mypy app
}

run_frontend_quality() {
  echo "[quality] Frontend (svelte-check)..."
  docker compose exec -T frontend pnpm check
  echo "[quality] Frontend (eslint)..."
  docker compose exec -T frontend pnpm lint
  echo "[quality] Frontend (production build)..."
  docker compose exec -T frontend env SVELTE_ADAPTER=node pnpm build
}

run_ocr() {
  echo "[tests] OCR worker logic..."
  # The runtime OCR image intentionally excludes dev tools and runs as a
  # non-root user. Execute the worker tests in the backend dev image, which
  # provides pytest and installs the locked OCR extra without mutating the
  # worker's production environment.
  docker compose exec -T backend uv run --frozen --extra ocr pytest -q -ra tests/unit/test_ocr_worker.py
}

run_lint() {
  run_backend_quality
  run_frontend_quality
}

case "$TARGET" in
  all)               run_backend all; run_ocr; run_frontend; run_lint ;;
  backend)           run_backend all ;;
  backend-unit)      run_backend unit ;;
  backend-integration) run_backend integration ;;
  backend-e2e)       run_backend e2e ;;
  frontend)          run_frontend; run_frontend_quality ;;
  lint)              run_lint ;;
  *)
    echo "Usage: $0 {all|backend|backend-unit|backend-integration|backend-e2e|frontend|lint}"
    exit 2 ;;
esac
