<#
.SYNOPSIS
    Run the MVP RAG pipeline locally (without Docker).
    This script starts all components in order with proper health checks.

.DESCRIPTION
    Starts the following services in dependency order:
    1. KB Manager (port 8000)
    2. Guardrails (port 8200) - requires Gemma Manager at 9000
    3. Orchestrator (port 8100)
    4. Open WebUI (port 13000) - configured to use Orchestrator

    Note: This requires the Gemma Manager to already be running at port 9000
    (from server-setup). The embedding services (ports 8001-8003) should also
    be running for KB ingestion.

.PARAMETER SkipKB
    Skip starting KB Manager (assume it's already running)

.PARAMETER SkipGuardrails
    Skip starting Guardrails (assume it's already running)

.PARAMETER SkipOrchestrator
    Skip starting Orchestrator (assume it's already running)

.EXAMPLE
    .\scripts\run_mvp.ps1

.EXAMPLE
    .\scripts\run_mvp.ps1 -SkipKB
#>

param(
    [switch]$SkipKB,
    [switch]$SkipGuardrails,
    [switch]$SkipOrchestrator,
    [int]$HealthCheckTimeout = 120,
    [int]$HealthCheckInterval = 5
)

$ErrorActionPreference = "Stop"

# Colors for output
$Green = [ConsoleColor]::Green
$Yellow = [ConsoleColor]::Yellow
$Red = [ConsoleColor]::Red
$Cyan = [ConsoleColor]::Cyan

function Write-Status {
    param([string]$Message, [ConsoleColor]$Color = $Cyan)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Message" -ForegroundColor $Color
}

function Write-Success {
    param([string]$Message)
    Write-Status "✓ $Message" $Green
}

function Write-Warning {
    param([string]$Message)
    Write-Status "⚠ $Message" $Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Status "✗ $Message" $Red
}

function Test-HealthEndpoint {
    param(
        [string]$Url,
        [string]$ServiceName,
        [int]$Timeout = 120,
        [int]$Interval = 5
    )
    
    Write-Status "Waiting for $ServiceName at $Url..."
    $startTime = Get-Date
    $deadline = $startTime.AddSeconds($Timeout)
    
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5 -ErrorAction Stop
            if ($response.status -eq 'ok' -or $response.status -eq 'ready' -or $response -eq 'OK') {
                Write-Success "$ServiceName is healthy"
                return $true
            }
        } catch {
            # Ignore errors, keep retrying
        }
        Start-Sleep -Seconds $Interval
    }
    
    Write-Error "$ServiceName health check timed out after ${Timeout}s"
    return $false
}

function Test-ReadinessEndpoint {
    param(
        [string]$Url,
        [string]$ServiceName,
        [int]$Timeout = 120,
        [int]$Interval = 5
    )
    
    Write-Status "Waiting for $ServiceName readiness at $Url..."
    $startTime = Get-Date
    $deadline = $startTime.AddSeconds($Timeout)
    
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5 -ErrorAction Stop
            if ($response.status -eq 'ready') {
                Write-Success "$ServiceName is ready"
                return $true
            } elseif ($response.status -eq 'not_ready') {
                Write-Warning "$ServiceName not ready yet: $($response.dependencies | Where-Object {$_.status -ne 'ready'} | ForEach-Object { $_.name })"
            }
        } catch {
            # Ignore errors, keep retrying
        }
        Start-Sleep -Seconds $Interval
    }
    
    Write-Error "$ServiceName readiness check timed out after ${Timeout}s"
    return $false
}

# Get repository root
$RepoRoot = Split-Path $PSScriptRoot -Parent
Write-Status "Repository root: $RepoRoot"

# Verify submodules are initialized
Write-Status "Checking submodule status..."
$submoduleStatus = git -C $RepoRoot submodule status --recursive
if ($submoduleStatus -match '^-') {
    Write-Error "Submodules not initialized. Run: git submodule update --init --recursive"
    exit 1
}
Write-Success "Submodules initialized"

# Check for .env files
$envFiles = @(
    "$RepoRoot\components\guardrails\.env",
    "$RepoRoot\components\orchestrator\.env"
)

foreach ($envFile in $envFiles) {
    if (-not (Test-Path $envFile)) {
        $example = $envFile.Replace('.env', '.env.example')
        if (Test-Path $example) {
            Copy-Item $example $envFile
            Write-Warning "Created $envFile from example. Please review and update if needed."
        } else {
            Write-Warning "No .env file found at $envFile and no example to copy from"
        }
    }
}

# Start KB Manager
if (-not $SkipKB) {
    Write-Status "Starting KB Manager..."
    $kbDir = "$RepoRoot\components\knowledgebase\kb-manager"
    $kbEnv = @{
        KB_DB_URL = "sqlite+aiosqlite:///$kbDir/data/kb_test.db"
        KB_SOURCE_DIR = "$RepoRoot\components\knowledgebase\kb-source"
        KB_WEB_PORT = 8000
    }
    
    $kbProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$kbDir'; `$env:KB_DB_URL='$($kbEnv.KB_DB_URL)'; `$env:KB_SOURCE_DIR='$($kbEnv.KB_SOURCE_DIR)'; `$env:KB_WEB_PORT=$($kbEnv.KB_WEB_PORT)'; python run_server.py" -PassThru
    $global:kbPid = $kbProcess.Id
    Write-Status "KB Manager started with PID $($global:kbPid)"
    
    if (-not (Test-HealthEndpoint "http://127.0.0.1:8000/" "KB Manager" $HealthCheckTimeout $HealthCheckInterval)) {
        Write-Error "KB Manager failed to start"
        exit 1
    }
} else {
    Write-Status "Skipping KB Manager (assumed running)"
    if (-not (Test-HealthEndpoint "http://127.0.0.1:8000/" "KB Manager" 10 2)) {
        Write-Error "KB Manager not accessible at http://127.0.0.1:8000/"
        exit 1
    }
}

# Start Guardrails
if (-not $SkipGuardrails) {
    Write-Status "Starting Guardrails..."
    $grDir = "$RepoRoot\components\guardrails"
    $grEnv = @{
        GUARDRAILS_PORT = 8200
        UPSTREAM_LLM_BASE_URL = "http://127.0.0.1:9000/v1"
        UPSTREAM_LLM_MODEL = "gemma-4-31b"
        UPSTREAM_LLM_API_KEY = "sk-local-dev"
    }
    
    $grProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$grDir'; `$env:GUARDRAILS_PORT=$($grEnv.GUARDRAILS_PORT); `$env:UPSTREAM_LLM_BASE_URL='$($grEnv.UPSTREAM_LLM_BASE_URL)'; `$env:UPSTREAM_LLM_MODEL='$($grEnv.UPSTREAM_LLM_MODEL)'; `$env:UPSTREAM_LLM_API_KEY='$($grEnv.UPSTREAM_LLM_API_KEY)'; python -m work_rag_guardrails.api" -PassThru
    $global:grPid = $grProcess.Id
    Write-Status "Guardrails started with PID $($global:grPid)"
    
    if (-not (Test-ReadinessEndpoint "http://127.0.0.1:8200/ready" "Guardrails" $HealthCheckTimeout $HealthCheckInterval)) {
        Write-Error "Guardrails failed to start"
        exit 1
    }
} else {
    Write-Status "Skipping Guardrails (assumed running)"
    if (-not (Test-ReadinessEndpoint "http://127.0.0.1:8200/ready" "Guardrails" 10 2)) {
        Write-Error "Guardrails not accessible at http://127.0.0.1:8200/ready"
        exit 1
    }
}

# Start Orchestrator
if (-not $SkipOrchestrator) {
    Write-Status "Starting Orchestrator..."
    $orchDir = "$RepoRoot\components\orchestrator"
    $orchEnv = @{
        ORCHESTRATOR_PORT = 8100
        KB_BASE_URL = "http://127.0.0.1:8000"
        GUARDRAILS_BASE_URL = "http://127.0.0.1:8200"
        REQUEST_TIMEOUT_SECONDS = 120
        RETRIEVAL_TOP_K = 5
    }
    
    $orchProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$orchDir'; `$env:ORCHESTRATOR_PORT=$($orchEnv.ORCHESTRATOR_PORT); `$env:KB_BASE_URL='$($orchEnv.KB_BASE_URL)'; `$env:GUARDRAILS_BASE_URL='$($orchEnv.GUARDRAILS_BASE_URL)'; `$env:REQUEST_TIMEOUT_SECONDS=$($orchEnv.REQUEST_TIMEOUT_SECONDS); `$env:RETRIEVAL_TOP_K=$($orchEnv.RETRIEVAL_TOP_K); python -m work_rag_orchestrator.api" -PassThru
    $global:orchPid = $orchProcess.Id
    Write-Status "Orchestrator started with PID $($global:orchPid)"
    
    if (-not (Test-ReadinessEndpoint "http://127.0.0.1:8100/ready" "Orchestrator" $HealthCheckTimeout $HealthCheckInterval)) {
        Write-Error "Orchestrator failed to start"
        exit 1
    }
} else {
    Write-Status "Skipping Orchestrator (assumed running)"
    if (-not (Test-ReadinessEndpoint "http://127.0.0.1:8100/ready" "Orchestrator" 10 2)) {
        Write-Error "Orchestrator not accessible at http://127.0.0.1:8100/ready"
        exit 1
    }
}

Write-Success "All MVP services started successfully!"
Write-Status ""
Write-Status "Service endpoints:"
Write-Status "  KB Manager:       http://127.0.0.1:8000"
Write-Status "  Orchestrator:     http://127.0.0.1:8100"
Write-Status "  Guardrails:       http://127.0.0.1:8200"
Write-Status "  Gemma Manager:    http://127.0.0.1:9000 (from server-setup)"
Write-Status "  Open WebUI:       http://127.0.0.1:13000 (configure separately)"
Write-Status ""
Write-Status "Press Ctrl+C to stop all services..."

# Keep script running and handle cleanup
try {
    while ($true) { Start-Sleep -Seconds 10 }
} finally {
    Write-Status "Shutting down services..."
    if ($global:kbPid) { Stop-Process -Id $global:kbPid -Force -ErrorAction SilentlyContinue }
    if ($global:grPid) { Stop-Process -Id $global:grPid -Force -ErrorAction SilentlyContinue }
    if ($global:orchPid) { Stop-Process -Id $global:orchPid -Force -ErrorAction SilentlyContinue }
    Write-Success "All services stopped"
}