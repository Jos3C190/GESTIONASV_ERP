#!/usr/bin/env bash
# Destructive: recreate the public schema, migrate and run the default seed.
set -euo pipefail

echo "[reset-db] WARNING: this destroys all data in the public schema."
read -r -p "Type 'yes' to continue: " ans
if [[ "$ans" != "yes" ]]; then
  echo "[reset-db] Aborted."
  exit 0
fi

echo "[reset-db] Recreating the public schema..."
docker compose exec -T db psql -U "${POSTGRES_USER:-erp_admin}" -d "${POSTGRES_DB:-erp_db}" \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO ${POSTGRES_USER:-erp_admin}; GRANT ALL ON SCHEMA public TO public;"

echo "[reset-db] Restarting the backend to run Alembic migrations..."
docker compose restart backend

for i in $(seq 1 60); do
  if curl -sf http://localhost:8000/health/live >/dev/null 2>&1; then
    echo "[reset-db] Running the Grupo Lorena seed..."
    docker compose run --rm seed
    echo "[reset-db] Database ready."
    exit 0
  fi
  sleep 2
done

echo "[reset-db] Backend did not become healthy. Run 'docker compose logs backend'." >&2
exit 1
