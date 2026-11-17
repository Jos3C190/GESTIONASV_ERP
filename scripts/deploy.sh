#!/usr/bin/env bash
set -euo pipefail

echo "============================================="
echo ">>> Iniciando Despliegue Automático en AWS..."
echo "============================================="

# Exportar rutas del entorno de ec2-user (node, pnpm, pm2, uv)
export PATH="$HOME/.local/bin:$HOME/bin:/usr/local/bin:/usr/bin:$PATH"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# 1. Traer cambios de la rama activa
cd "$HOME/GESTIONASV_ERP"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-$CURRENT_BRANCH}"
echo ">>> 1. Descargando cambios más recientes de $DEPLOY_BRANCH..."
git fetch origin "$DEPLOY_BRANCH"
git reset --hard origin/"$DEPLOY_BRANCH"

# 2. Actualizar Backend
echo ">>> 2. Actualizando dependencias y migraciones del Backend..."
cd "$HOME/GESTIONASV_ERP/backend"
source .venv/bin/activate
uv sync
alembic upgrade head
pm2 restart erp-backend

# 3. Actualizar Frontend
echo ">>> 3. Compilando y desplegando Frontend..."
cd "$HOME/GESTIONASV_ERP/frontend"
pnpm install
NODE_OPTIONS="--max-old-space-size=1536" PUBLIC_API_URL=http://3.138.246.163:8000 SVELTE_ADAPTER=node pnpm build
pm2 restart erp-frontend

# 4. Guardar lista de PM2
pm2 save

echo "============================================="
echo ">>> ¡Despliegue completado con éxito! 🚀"
echo "============================================="

