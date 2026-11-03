#!/usr/bin/env bash
# Enciende el servidor GPS local y lo conecta con el ERP. Se puede repetir sin riesgo.
#
#   make setup-gps                 detecta la IP de esta PC
#   GPS_HOST=192.168.1.50 make setup-gps
#   bash scripts/setup-gps.sh      sin Make
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { printf "${GREEN}[gps]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[gps]${NC} %s\n" "$*"; }
err()  { printf "${RED}[gps]${NC} %s\n" "$*" >&2; }

ADMIN_URL="${TRACCAR_ADMIN_URL:-http://127.0.0.1:8082}"
SERVICE_EMAIL="erp-service@traccar.local"

env_value() {
  grep -E "^$1=" .env 2>/dev/null | tail -n 1 | cut -d= -f2- | tr -d '\r' || true
}

set_env() {
  if grep -qE "^$1=" .env; then
    sed -i.bak "s|^$1=.*|$1=$2|" .env
    rm -f .env.bak
  else
    printf '\n%s=%s\n' "$1" "$2" >> .env
  fi
}

# La dirección de la red, no la de Docker ni la de WSL: es la que alcanza un teléfono.
detect_host() {
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command \
      '$r = Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Sort-Object RouteMetric | Select-Object -First 1; (Get-NetIPAddress -InterfaceIndex $r.InterfaceIndex -AddressFamily IPv4).IPAddress' \
      2>/dev/null | tr -d '\r' | head -n 1
  elif command -v ip >/dev/null 2>&1; then
    ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]*\).*/\1/p'
  elif command -v route >/dev/null 2>&1; then
    ipconfig getifaddr "$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')" 2>/dev/null || true
  fi
}

http_code() {
  curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@" || true
}

for tool in docker curl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    err "Falta $tool."
    exit 1
  fi
done
if [[ ! -f .env ]]; then
  err "No existe .env. Instala primero el ERP con 'make setup'."
  exit 1
fi

[[ -n "$(env_value TRACCAR_URL)" ]] || set_env TRACCAR_URL "http://traccar:8082"

public_url="$(env_value TRACCAR_PUBLIC_URL)"
if [[ -n "${GPS_HOST:-}" ]]; then
  public_url="http://${GPS_HOST}:5055"
  set_env TRACCAR_PUBLIC_URL "$public_url"
elif [[ -z "$public_url" ]]; then
  host="$(detect_host || true)"
  if [[ -n "$host" ]]; then
    public_url="http://${host}:5055"
    set_env TRACCAR_PUBLIC_URL "$public_url"
  fi
fi

log "Levantando el servidor GPS..."
docker compose --profile tracking up -d traccar

log "Esperando a que responda..."
for i in $(seq 1 90); do
  [[ "$(http_code "$ADMIN_URL/api/server")" == "200" ]] && break
  if [[ $i -eq 90 ]]; then
    err "El servidor GPS no respondió. Revisa 'docker compose --profile tracking logs traccar'."
    exit 1
  fi
  sleep 2
done

user="$(env_value TRACCAR_USER)"
password="$(env_value TRACCAR_PASSWORD)"
if [[ -n "$user" && -n "$password" ]]; then
  if [[ "$(http_code -u "$user:$password" "$ADMIN_URL/api/devices")" != "200" ]]; then
    err "El servidor GPS rechaza TRACCAR_USER y TRACCAR_PASSWORD de tu .env. Corrígelos y repite."
    exit 1
  fi
  log "La cuenta de servicio ya funciona."
else
  password="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"
  body="{\"name\":\"ERP\",\"email\":\"$SERVICE_EMAIL\",\"password\":\"$password\"}"
  created="$(http_code -X POST -H 'Content-Type: application/json' -d "$body" "$ADMIN_URL/api/users")"
  if [[ "$created" != "200" ]]; then
    err "No se pudo crear la cuenta de servicio (HTTP $created): el servidor GPS ya tiene usuarios."
    err "Pon una cuenta de administrador en TRACCAR_USER y TRACCAR_PASSWORD de tu .env y repite."
    exit 1
  fi
  set_env TRACCAR_USER "$SERVICE_EMAIL"
  set_env TRACCAR_PASSWORD "$password"
  log "Cuenta de servicio creada y guardada en .env."

  # El primer usuario queda como administrador; nadie más debe poder registrarse.
  server="$(curl -s --max-time 10 "$ADMIN_URL/api/server" | sed 's/"registration":true/"registration":false/')"
  closed="$(http_code -X PUT -u "$SERVICE_EMAIL:$password" -H 'Content-Type: application/json' -d "$server" "$ADMIN_URL/api/server")"
  if [[ "$closed" == "200" ]]; then
    log "Registro público del servidor GPS cerrado."
  else
    warn "No se pudo cerrar el registro público (HTTP $closed)."
  fi
fi

# Sin el ERP levantado no hay nada que actualizar: tomará estos valores al arrancar.
if [[ -n "$(docker compose ps -q backend 2>/dev/null)" ]]; then
  log "Aplicando la configuración al ERP..."
  docker compose up -d --no-deps backend tracking-monitor
fi

echo
log "================ Servidor GPS listo ================"
if [[ -n "$public_url" ]]; then
  log "Los equipos reportan a: $public_url"
  if [[ -z "${GPS_HOST:-}" ]]; then
    warn "Si tu PC cambia de IP, repite con GPS_HOST=<ip> para actualizarla."
  fi
else
  warn "No se pudo detectar la IP de esta PC. Repite con GPS_HOST=<ip>."
fi
log "Para conectar un equipo: Flota > un vehículo > pestaña GPS > Conectar GPS."
warn "Esta dirección solo sirve en tu red. Si un teléfono no llega, revisa el firewall de la PC."
