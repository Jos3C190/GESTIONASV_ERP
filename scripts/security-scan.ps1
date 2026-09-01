param (
    [switch]$Deep
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:ScanFailed = $false

function Invoke-SecurityStep {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][scriptblock]$Action
    )

    Write-Host "--> $Label" -ForegroundColor Yellow
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    FAILED ($LASTEXITCODE): $Label" -ForegroundColor Red
        $script:ScanFailed = $true
    } else {
        Write-Host "    OK: $Label" -ForegroundColor Green
    }
}

$rootDirectory = Split-Path -Parent $PSScriptRoot
Push-Location $rootDirectory
try {
    New-Item -ItemType Directory -Force -Path "reports" | Out-Null
    $mode = if ($Deep) { "deep" } else { "baseline" }

    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host " ERP System - Auditoria de Seguridad" -ForegroundColor Cyan
    Write-Host " Modo: $mode" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan

    Invoke-SecurityStep "Pruebas adversariales del backend" {
        docker compose exec -T backend uv run --frozen pytest tests/integration/api/test_security_bounds.py -v
    }

    if ($Deep) {
        Invoke-SecurityStep "OWASP ZAP OpenAPI activo" {
            docker compose --profile security-deep run --rm security-zap-deep
        }
    } else {
        Invoke-SecurityStep "OWASP ZAP baseline" {
            docker compose --profile security run --rm security-zap
        }
    }

    Invoke-SecurityStep "Trivy filesystem y lockfiles" {
        docker compose --profile security run --rm security-trivy
    }

    Invoke-SecurityStep "Construccion y escaneo Trivy de imagenes propias" {
        $powerShellExecutable = (Get-Process -Id $PID).Path
        & $powerShellExecutable -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot/security-scan-images.ps1"
    }

    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host " Reportes locales: .\reports\" -ForegroundColor Cyan

    if ($script:ScanFailed) {
        Write-Host " Auditoria FALLIDA: revise los pasos y reportes anteriores." -ForegroundColor Red
        if (Test-Path "$PSScriptRoot/notify.ps1") {
            & "$PSScriptRoot/notify.ps1" -Title "Auditoria de Seguridad Fallida" -Message "Uno o mas controles de seguridad fallaron."
        }
        exit 1
    }

    Write-Host " Auditoria aprobada: todos los controles finalizaron correctamente." -ForegroundColor Green
    if (Test-Path "$PSScriptRoot/notify.ps1") {
        & "$PSScriptRoot/notify.ps1" -Title "Auditoria de Seguridad Aprobada" -Message "Los controles Pytest, ZAP y Trivy finalizaron correctamente."
    }
} finally {
    Pop-Location
}
