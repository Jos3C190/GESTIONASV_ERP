#!/usr/bin/env bash
# Run the official first-setup seed. FORCE_SEED=true explicitly reconciles it.
set -euo pipefail

echo "[seed] Running Grupo Lorena seed..."
docker compose run --rm seed
