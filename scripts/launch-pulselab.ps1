<#
.SYNOPSIS
    PulseLab EDA Platform Launcher — Native & Container Orchestrator
.DESCRIPTION
    Launches PulseLab Generative Hardware Platform either in Docker Container mode
    (pulling from GHCR or building locally) or Native Python 3.12 mode.
.PARAMETER Mode
    'Container' (default) or 'Native'
.PARAMETER Port
    Host port to bind FastAPI Gateway & Web Studio (default: 8000)
.PARAMETER Pull
    Pull latest image from ghcr.io/anarcoiris/pulse:latest
.PARAMETER Build
    Force local Docker build
.PARAMETER Stop
    Stops running PulseLab instance
.PARAMETER Status
    Checks health and container status
.PARAMETER OpenBrowser
    Automatically opens Web Studio in default browser
#>

param(
    [ValidateSet("Container", "Native")]
    [string]$Mode = "Container",
    [int]$Port = 8000,
    [switch]$Pull,
    [switch]$Build,
    [switch]$Stop,
    [switch]$Status,
    [switch]$Logs,
    [switch]$OpenBrowser,
    [switch]$Caddy,
    [string]$Domain = "localhost"
)

$RepoRoot = if ($env:PULSE_REPO_PATH -and (Test-Path $env:PULSE_REPO_PATH)) {
    $env:PULSE_REPO_PATH
} elseif (Test-Path (Join-Path $PSScriptRoot "docker-compose.pulselab.yml")) {
    $PSScriptRoot
} else {
    Split-Path $PSScriptRoot -Parent
}
Set-Location $RepoRoot

$Py312 = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Py312 -or -not (Test-Path $Py312)) {
    $Py312 = Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"
}
if (-not (Test-Path $Py312)) {
    $Py312 = "python"
}

function Show-Banner {
    Write-Host ""
    Write-Host " ================================================================ " -ForegroundColor Cyan
    Write-Host "        ⚡ PulseLab Generative EDA & PCB Synthesis Studio        " -ForegroundColor Yellow -BackgroundColor Black
    Write-Host " ================================================================ " -ForegroundColor Cyan
    Write-Host ""
}

# ── Status Check ─────────────────────────────────────────────────────────────
if ($Status) {
    Show-Banner
    Write-Host "[*] Checking PulseLab Health..." -ForegroundColor Cyan
    
    # Check Docker container
    $dockerRunning = $false
    try {
        $container = docker ps --filter "name=pulselab-eda" --format "{{.ID}} | {{.Image}} | {{.Status}} | {{.Ports}}"
        if ($container) {
            $dockerRunning = $true
            Write-Host "  [Docker Container] ACTIVE" -ForegroundColor Green
            Write-Host "  $container" -ForegroundColor Gray
        }
    } catch {}

    # Check HTTP endpoint
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:$Port/api/v1/presets" -TimeoutSec 3 -ErrorAction Stop
        Write-Host "  [HTTP Gateway]     ONLINE at http://localhost:$Port" -ForegroundColor Green
        Write-Host "  [Presets Loaded]   $($resp.presets.Count) presets available" -ForegroundColor Green
    } catch {
        Write-Host "  [HTTP Gateway]     OFFLINE on port $Port" -ForegroundColor DarkGray
    }
    Write-Host ""
    exit 0
}

# ── Stop Instance ─────────────────────────────────────────────────────────────
if ($Stop) {
    Show-Banner
    Write-Host "[*] Stopping PulseLab services..." -ForegroundColor Yellow
    if (Test-Path $ComposeFile) {
        docker compose -f $ComposeFile down --remove-orphans
    }
    # Stop native background process if running
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -match "app.main:app"
    } | Stop-Process -Force -ErrorAction SilentlyContinue

    Write-Host "[+] PulseLab stopped successfully." -ForegroundColor Green
    exit 0
}

# ── View Logs ─────────────────────────────────────────────────────────────────
if ($Logs) {
    if ($Mode -eq "Container") {
        docker compose -f $ComposeFile logs -f --tail=100
    } else {
        Get-Content (Join-Path $RepoRoot "logs\pulselab.log") -Wait -Tail 50
    }
    exit 0
}

Show-Banner

# ── Launch Container Mode ─────────────────────────────────────────────────────
if ($Mode -eq "Container") {
    Write-Host "[*] Target Mode: Docker Container (GHCR / Local Compose)" -ForegroundColor Cyan
    Write-Host "    Container Name: pulselab-eda" -ForegroundColor Gray
    Write-Host "    Host Port:      $Port" -ForegroundColor Gray
    Write-Host ""

    $env:PULSE_PORT = "$Port"
    $env:SITE_ADDRESS = "$Domain"

    if ($Pull) {
        Write-Host "[*] Pulling latest image from GHCR (ghcr.io/anarcoiris/pulse:latest)..." -ForegroundColor Yellow
        docker compose -f $ComposeFile pull
    }

    if ($Build) {
        Write-Host "[*] Building local Docker image..." -ForegroundColor Yellow
        docker compose -f $ComposeFile build
    }

    $ProfileFlag = if ($Caddy) { "--profile prod" } else { "" }
    Write-Host "[*] Starting PulseLab container stack $ProfileFlag..." -ForegroundColor Cyan
    if ($Caddy) {
        docker compose -f $ComposeFile --profile prod up -d
    } else {
        docker compose -f $ComposeFile up -d
    }

    Write-Host ""
    Write-Host "  [+] PulseLab is running in container!" -ForegroundColor Green
    if ($Caddy) {
        Write-Host "  ➜ Caddy Reverse Proxy / DDNS: https://$Domain (HTTP :80 / HTTPS :443)" -ForegroundColor Yellow
        Write-Host "  ➜ Direct API Gateway:          http://localhost:$Port" -ForegroundColor Cyan
    } else {
        Write-Host "  ➜ Web Studio & API:            http://localhost:$Port" -ForegroundColor Yellow
    }
    Write-Host "  ➜ API Documentation: http://localhost:$Port/docs" -ForegroundColor Cyan
    Write-Host "  ➜ OpenAPI Schema:    http://localhost:$Port/openapi.json" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Logs:   .\scripts\launch-pulselab.ps1 -Logs" -ForegroundColor Gray
    Write-Host "  Stop:   .\scripts\launch-pulselab.ps1 -Stop" -ForegroundColor Gray
    Write-Host "  Status: .\scripts\launch-pulselab.ps1 -Status" -ForegroundColor Gray
    Write-Host ""

    if ($OpenBrowser) {
        Start-Process "http://localhost:$Port"
    }
    exit 0
}

# ── Launch Native Mode ────────────────────────────────────────────────────────
if ($Mode -eq "Native") {
    Write-Host "[*] Target Mode: Native Python 3.12" -ForegroundColor Cyan
    if (-not (Test-Path $Py312)) {
        Write-Error "Python 3.12 not found at $Py312"
        exit 1
    }

    Write-Host "[*] Starting uvicorn backend on port $Port..." -ForegroundColor Cyan
    $env:PYTHONIOENCODING = "utf-8"
    
    if ($OpenBrowser) {
        Start-Process "http://localhost:$Port"
    }

    & $Py312 -m uvicorn app.main:app --host 0.0.0.0 --port $Port --reload
}
