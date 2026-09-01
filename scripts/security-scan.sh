#!/usr/bin/env bash
# Run the ERP security checks and preserve every available report.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
MODE="${1:-baseline}"
FAILED=0

cd "$ROOT_DIR"

if [[ "$MODE" != "baseline" && "$MODE" != "deep" ]]; then
    echo "Usage: $0 [baseline|deep]" >&2
    exit 2
fi

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

mkdir -p reports

echo "======================================================================"
echo " ERP System - Auditoria de Seguridad"
echo " Modo: $MODE"
echo "======================================================================"

run_step \
    "Pruebas adversariales del backend" \
    docker compose exec -T backend uv run --frozen pytest \
        tests/integration/api/test_security_bounds.py -v

if [[ "$MODE" == "deep" ]]; then
    run_step \
        "OWASP ZAP OpenAPI activo" \
        docker compose --profile security-deep run --rm security-zap-deep
else
    run_step \
        "OWASP ZAP baseline" \
        docker compose --profile security run --rm security-zap
fi

run_step \
    "Trivy filesystem y lockfiles" \
    docker compose --profile security run --rm security-trivy

run_step \
    "Construccion y escaneo Trivy de imagenes propias" \
    bash "$SCRIPT_DIR/security-scan-images.sh"

echo "======================================================================"
echo "Reportes locales: ./reports/"
if [[ "$FAILED" -ne 0 ]]; then
    echo "Auditoria FALLIDA: revise los pasos y reportes anteriores." >&2
    exit 1
fi

echo "Auditoria aprobada: todos los controles finalizaron correctamente."
if command -v powershell.exe >/dev/null 2>&1; then
    if ! powershell.exe -ExecutionPolicy Bypass -File "./scripts/notify.ps1" \
        -Title "Auditoria de Seguridad Aprobada" \
        -Message "Los controles Pytest, ZAP y Trivy finalizaron correctamente." \
        >/dev/null 2>&1; then
        echo "Aviso: no se pudo mostrar la notificacion local." >&2
    fi
fi
