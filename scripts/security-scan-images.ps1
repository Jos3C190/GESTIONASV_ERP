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

    Invoke-SecurityStep "Build backend dev" {
        docker build --target dev -t erp-security-backend-dev:local backend
    }
    Invoke-SecurityStep "Build backend prod" {
        docker build --target prod -t erp-security-backend-prod:local backend
    }
    Invoke-SecurityStep "Build OCR worker" {
        docker build --target ocr -t erp-security-ocr:local backend
    }
    Invoke-SecurityStep "Build Dockerfile default (Render)" {
        docker build -t erp-security-render-default:local backend
    }

    Write-Host "--> Validate default Dockerfile command" -ForegroundColor Yellow
    $renderCommand = docker image inspect erp-security-render-default:local --format "{{json .Config.Cmd}}"
    if ($LASTEXITCODE -ne 0 -or $renderCommand -notmatch "uvicorn" -or $renderCommand -match "arq") {
        Write-Host "    FAILED: default image must start Uvicorn, not ARQ ($renderCommand)" -ForegroundColor Red
        $script:ScanFailed = $true
    } else {
        Write-Host "    OK: default image starts the production API" -ForegroundColor Green
    }

    Invoke-SecurityStep "Trivy backend dev libraries" {
        docker compose --profile security run --rm security-trivy-backend-dev
    }
    Invoke-SecurityStep "Trivy backend dev OS (Debian severity)" {
        docker compose --profile security run --rm security-trivy-backend-dev-os
    }
    Invoke-SecurityStep "Trivy backend prod libraries" {
        docker compose --profile security run --rm security-trivy-backend-prod
    }
    Invoke-SecurityStep "Trivy backend prod OS (Debian severity)" {
        docker compose --profile security run --rm security-trivy-backend-prod-os
    }
    Invoke-SecurityStep "Trivy OCR worker libraries" {
        docker compose --profile security run --rm security-trivy-ocr
    }
    Invoke-SecurityStep "Trivy OCR worker OS (Debian severity)" {
        docker compose --profile security run --rm security-trivy-ocr-os
    }

    if ($script:ScanFailed) {
        exit 1
    }

    Write-Host "All project-owned backend images passed library and Debian OS gates." -ForegroundColor Green
} finally {
    Pop-Location
}
