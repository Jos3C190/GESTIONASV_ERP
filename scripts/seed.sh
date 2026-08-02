#!/usr/bin/env bash
# Run the official Grupo Lorena bootstrap seed (idempotent).
set -euo pipefail

echo "[seed] Running Grupo Lorena seed..."
docker compose run --rm seed
