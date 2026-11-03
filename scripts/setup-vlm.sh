#!/usr/bin/env bash
# Prepara el modelo que lee licencias y enciende su worker. Se puede repetir sin riesgo.
#
#   make setup-vlm                 pregunta antes de descargar
#   bash scripts/setup-vlm.sh --yes         sin preguntar
#   bash scripts/setup-vlm.sh --no-start    solo prepara el modelo
#
# Sin GPU no hace falta: sin el modelo, los datos de la licencia se escriben a mano.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Git Bash convertiría rutas como /models en rutas de Windows.
export MSYS_NO_PATHCONV=1

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { printf "${GREEN}[vlm]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[vlm]${NC} %s\n" "$*"; }
err()  { printf "${RED}[vlm]${NC} %s\n" "$*" >&2; }

# Versiones fijadas: el conversor debe ser el del motor de backend/Dockerfile.
LLAMA_COMMIT=785322d17f2d51e5185cf996a1f4e46d87640841
WEIGHTS_REPO=tencent/HunyuanOCR
WEIGHTS_REVISION=47644ecc4fc854efa4f505155158831f36773ee4
WEIGHTS_SHA256=632a1e082c4dd5a3284cf1ffcdba2fdaa06f435762c58c2f34aff0f3bd6c0249
MODEL_FILE=hyocr-f16.gguf
MMPROJ_FILE=mmproj-hyocr-f16.gguf
MODEL_SHA256=d86ca28a9d1a6203fd0957cbe19db9979ba2007ce78286cb248c64f5974e08b9
MMPROJ_SHA256=bde41b070775ef502cb2d050096c2ba22ff2d65e308a2fca2ea8d7b822ec5a31
TOOLS_IMAGE=python:3.12-slim-bookworm
MIN_VRAM_MIB=4000
MIN_DISK_GB=10

assume_yes=false
start_worker=true
for arg in "$@"; do
  case "$arg" in
    --yes) assume_yes=true ;;
    --no-start) start_worker=false ;;
    *) err "Opción desconocida: $arg"; exit 2 ;;
  esac
done

set_env() {
  if ! grep -qE "^$1=" .env; then
    printf '\n%s=%s\n' "$1" "$2" >> .env
  elif ! grep -qE "^$1=$2"$'\r'"?$" .env; then
    sed -i.bak "s|^$1=.*|$1=$2|" .env
    rm -f .env.bak
  fi
}

for tool in docker nvidia-smi; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    [[ "$tool" == nvidia-smi ]] && err "No se encontró una GPU NVIDIA. Sin ella, las licencias se escriben a mano."
    [[ "$tool" == docker ]] && err "Falta docker."
    exit 1
  fi
done
if [[ ! -f .env ]]; then
  err "No existe .env. Instala primero el ERP con 'make setup'."
  exit 1
fi

vram_mib="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n 1 | tr -d '\r ')"
if (( vram_mib < MIN_VRAM_MIB )); then
  err "La GPU tiene ${vram_mib} MiB y el modelo necesita unos ${MIN_VRAM_MIB} MiB."
  exit 1
fi
log "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1 | tr -d '\r') (${vram_mib} MiB)"

if [[ -z "${VLM_MODELS_VOLUME:-}" ]]; then
  project="$(docker compose config 2>/dev/null | sed -n 's/^name: //p' | head -n 1 | tr -d '\r')"
  VLM_MODELS_VOLUME="${project:?No se pudo leer la configuración de Compose}_vlm-models"
fi
BUILD_VOLUME="${VLM_MODELS_VOLUME}-build"

model_checksums() {
  docker run --rm -v "$VLM_MODELS_VOLUME:/models:ro" "$TOOLS_IMAGE" sh -c \
    "cd /models && sha256sum $MODEL_FILE $MMPROJ_FILE 2>/dev/null" | awk '{print $1}' | tr '\n' ' ' || true
}

expected_checksums="$MODEL_SHA256 $MMPROJ_SHA256 "
if [[ "$(model_checksums)" == "$expected_checksums" ]]; then
  log "El modelo ya está preparado y verificado."
else
  free_gb="$(docker run --rm "$TOOLS_IMAGE" sh -c "df -BG --output=avail / | tail -n 1 | tr -dc 0-9")"
  if (( free_gb < MIN_DISK_GB )); then
    err "Docker tiene ${free_gb} GB libres y hacen falta unos ${MIN_DISK_GB} GB."
    exit 1
  fi
  log "Hay que preparar el modelo: descarga unos 3 GB y ocupa unos 2 GB al terminar."
  warn "Los pesos son de Tencent, con su propia licencia:"
  warn "https://huggingface.co/$WEIGHTS_REPO"
  if [[ "$assume_yes" != true ]]; then
    read -r -p "¿Continuar? [s/N] " answer
    if [[ ! "$answer" =~ ^[sSyY]$ ]]; then
      warn "Cancelado; no se descargó nada."
      exit 0
    fi
  fi

  # El volumen temporal sobrevive a un fallo: al repetir, no se descarga dos veces.
  docker volume create "$BUILD_VOLUME" >/dev/null
  log "Descargando y convirtiendo; puede tardar varios minutos..."
  docker run --rm -i \
    -v "$BUILD_VOLUME:/build" -v "$VLM_MODELS_VOLUME:/models" \
    -e LLAMA_COMMIT="$LLAMA_COMMIT" -e WEIGHTS_REPO="$WEIGHTS_REPO" \
    -e WEIGHTS_REVISION="$WEIGHTS_REVISION" -e WEIGHTS_SHA256="$WEIGHTS_SHA256" \
    -e MODEL_FILE="$MODEL_FILE" -e MMPROJ_FILE="$MMPROJ_FILE" \
    -e MODEL_SHA256="$MODEL_SHA256" -e MMPROJ_SHA256="$MMPROJ_SHA256" \
    "$TOOLS_IMAGE" sh -s <<'CONTAINER'
set -eu
export PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1
mkdir -p /build/weights /build/out

pip install -q "huggingface_hub==2.4.0"
hf download "$WEIGHTS_REPO" --revision "$WEIGHTS_REVISION" --local-dir /build/weights \
  --exclude 'v1.0/*' --exclude 'dflash/*' >/dev/null
echo "$WEIGHTS_SHA256  /build/weights/model.safetensors" | sha256sum -c -

python - <<'PY'
import io, os, tarfile, urllib.request
commit = os.environ["LLAMA_COMMIT"]
url = f"https://github.com/ggml-org/llama.cpp/archive/{commit}.tar.gz"
with urllib.request.urlopen(url) as response:
    tarfile.open(fileobj=io.BytesIO(response.read())).extractall("/build", filter="data")
PY
src="/build/llama.cpp-$LLAMA_COMMIT"

pip install -q --index-url https://download.pytorch.org/whl/cpu "torch==2.15.0+cpu"
pip install -q "transformers==5.22.1" "safetensors==0.8.0" "numpy==2.5.4" \
  "sentencepiece==0.2.2" "protobuf==7.36.2" "jinja2==3.1.6" "tqdm==4.70.1" \
  "pyyaml==6.0.3" "requests==2.34.2" "$src/gguf-py"

cd "$src"
python convert_hf_to_gguf.py --outfile "/build/out/$MODEL_FILE" --outtype f16 /build/weights
python convert_hf_to_gguf.py --outfile "/build/out/$MMPROJ_FILE" --outtype f16 --mmproj /build/weights

cd /build/out
printf '%s  %s\n%s  %s\n' "$MODEL_SHA256" "$MODEL_FILE" "$MMPROJ_SHA256" "$MMPROJ_FILE" | sha256sum -c -
# Copia y luego renombra: un corte nunca deja un modelo a medias con el nombre final.
for file in "$MODEL_FILE" "$MMPROJ_FILE"; do
  cp "$file" "/models/$file.tmp"
  mv "/models/$file.tmp" "/models/$file"
done
CONTAINER

  if [[ "$(model_checksums)" != "$expected_checksums" ]]; then
    err "El modelo copiado no coincide con el esperado."
    exit 1
  fi
  docker volume rm "$BUILD_VOLUME" >/dev/null
  log "Modelo preparado y verificado."
fi

if [[ "$start_worker" != true ]]; then
  log "Modelo listo. Para encenderlo, repite sin --no-start."
  exit 0
fi

set_env VLM_ENABLED true
log "Encendiendo el worker..."
docker compose --profile vlm up -d --build vlm-worker backend

log "Esperando al worker..."
for i in $(seq 1 60); do
  status="$(docker compose --profile vlm ps vlm-worker --format '{{.Status}}' 2>/dev/null || true)"
  [[ "$status" == *"(healthy)"* ]] && break
  if [[ $i -eq 60 ]]; then
    err "El worker no quedó sano. Revisa 'docker compose --profile vlm logs vlm-worker'."
    exit 1
  fi
  sleep 3
done

log "Comprobando que el modelo cargue en la GPU..."
docker compose --profile vlm exec -T vlm-worker /opt/venv/bin/python - <<'PY'
import subprocess, sys, time, urllib.request

server = subprocess.Popen(
    ["/app/llama-server", "--model", "/models/hyocr-f16.gguf",
     "--mmproj", "/models/mmproj-hyocr-f16.gguf", "--host", "127.0.0.1", "--port", "18099",
     "--ctx-size", "4096", "--n-gpu-layers", "99", "-fa", "on", "--jinja", "--no-webui"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
ready = False
try:
    for _ in range(90):
        if server.poll() is not None:
            break
        try:
            urllib.request.urlopen("http://127.0.0.1:18099/health", timeout=2)
            ready = True
            break
        except OSError:
            time.sleep(1)
finally:
    server.terminate()
    server.wait(timeout=20)
sys.exit(0 if ready else 1)
PY

echo
log "================ Lector de licencias listo ================"
log "El modelo cargó en la GPU y la liberó; solo ocupa memoria mientras lee."
log "Pruébalo: Conductores > un conductor > pestaña Licencia > Capturar con fotos."
warn "Falta tu prueba: revisa que proponga bien los datos de una licencia de muestra."
