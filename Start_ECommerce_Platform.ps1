[CmdletBinding()]
param(
    [ValidateSet("Auto", "Docker", "Local")]
    [string]$Mode = "Auto",
    [switch]$CheckOnly,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

$LogDirectory = Join-Path $ProjectRoot "results\logs"
New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
$LogFile = Join-Path $LogDirectory "startup.log"

function Write-Status {
    param(
        [string]$Message,
        [ValidateSet("INFO", "OK", "WARN", "ERROR")]
        [string]$Level = "INFO"
    )

    $colors = @{
        INFO = "Cyan"
        OK = "Green"
        WARN = "Yellow"
        ERROR = "Red"
    }
    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Write-Host $line -ForegroundColor $colors[$Level]
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

function Test-CommandAvailable {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-SystemPython {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
        (Join-Path (Split-Path -Parent $ProjectRoot) ".venv\Scripts\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            try {
                & $candidate -c "import sys; assert sys.version_info >= (3, 11)" *> $null
                if ($LASTEXITCODE -eq 0) {
                    return $candidate
                }
            }
            catch {
                continue
            }
        }
    }

    foreach ($command in @("py", "python")) {
        if (Test-CommandAvailable -Name $command) {
            try {
                if ($command -eq "py") {
                    & py -3 -c "import sys; assert sys.version_info >= (3, 11)" *> $null
                }
                else {
                    & python -c "import sys; assert sys.version_info >= (3, 11)" *> $null
                }
                if ($LASTEXITCODE -eq 0) {
                    return $command
                }
            }
            catch {
                continue
            }
        }
    }
    return $null
}

function Test-HttpEndpoint {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Wait-HttpEndpoint {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 180
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpEndpoint -Url $Url) {
            return $true
        }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Test-DockerEngine {
    if (-not (Test-CommandAvailable -Name "docker")) {
        return $false
    }
    try {
        docker info --format "{{.ServerVersion}}" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Start-DockerDesktop {
    $candidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
        (Join-Path $env:LOCALAPPDATA "Docker\Docker Desktop.exe")
    )
    $dockerDesktop = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $dockerDesktop) {
        Write-Status "Docker Desktop was not found." "WARN"
        return $false
    }

    Write-Status "Starting Docker Desktop and waiting for the Linux engine..."
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden | Out-Null
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerEngine) {
            Write-Status "Docker engine is ready." "OK"
            return $true
        }
        Start-Sleep -Seconds 4
    }
    Write-Status "Docker Desktop did not make the Linux engine available within 120 seconds." "WARN"
    return $false
}

function Get-ProjectPython {
    $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        return $venvPython
    }

    $systemPython = Get-SystemPython
    if (-not $systemPython) {
        throw "Python 3.11 or newer is required for Local mode."
    }

    Write-Status "Creating the project Python virtual environment (first run only)..."
    if ($systemPython -eq "py") {
        & py -3 -m venv (Join-Path $ProjectRoot ".venv")
    }
    else {
        & $systemPython -m venv (Join-Path $ProjectRoot ".venv")
    }

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        throw "The Python virtual environment could not be created."
    }
    return $venvPython
}

function Show-StartupDiagnostics {
    $requiredFiles = @(
        "docker-compose.yml",
        "Dockerfile",
        "requirements.txt",
        "src\cli.py",
        "src\dashboard.py",
        "src\realtime\api.py",
        "src\realtime\consumer.py",
        "kubernetes\kustomization.yaml"
    )
    $missingFiles = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath (Join-Path $ProjectRoot $_)) })
    $composeValid = $false
    if (Test-CommandAvailable -Name "docker") {
        docker compose --profile demo config --quiet *> $null
        $composeValid = $LASTEXITCODE -eq 0
    }

    $diagnostics = [ordered]@{
        ProjectRoot = $ProjectRoot
        RequiredFilesPresent = $missingFiles.Count -eq 0
        MissingFiles = if ($missingFiles.Count -eq 0) { "None" } else { $missingFiles -join ", " }
        DockerCLIInstalled = Test-CommandAvailable -Name "docker"
        DockerComposeValid = $composeValid
        DockerEngineReady = Test-DockerEngine
        PythonAvailable = $null -ne (Get-SystemPython)
        HistoricalWarehousePresent = Test-Path -LiteralPath (Join-Path $ProjectRoot "artifacts\ecommerce.duckdb")
        DashboardAlreadyRunning = Test-HttpEndpoint -Url "http://127.0.0.1:8501"
        StrictRealtimeReady = Test-HttpEndpoint -Url "http://127.0.0.1:8001/health"
        StartupLog = $LogFile
    }

    Write-Host ""
    Write-Host "E-Commerce Platform Diagnostics" -ForegroundColor White
    Write-Host "================================" -ForegroundColor White
    [PSCustomObject]$diagnostics | Format-List | Out-Host
    return $diagnostics
}

function Stop-RecordedLocalDashboard {
    $pidFile = Join-Path $LogDirectory "local-dashboard.pid"
    if (-not (Test-Path -LiteralPath $pidFile)) {
        return
    }

    $rawPid = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    [int]$dashboardPid = 0
    if (-not [int]::TryParse($rawPid, [ref]$dashboardPid)) {
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        return
    }

    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $dashboardPid" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -match "(?i)streamlit" -and $process.CommandLine -match "(?i)src[\\/]dashboard\.py") {
        Write-Status "Stopping the launcher-owned historical dashboard before starting Docker..."
        Stop-Process -Id $dashboardPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

function Start-DockerPlatform {
    if (-not (Test-CommandAvailable -Name "docker")) {
        throw "Docker is not installed. Install Docker Desktop or run with -Mode Local."
    }
    if (-not (Test-DockerEngine) -and -not (Start-DockerDesktop)) {
        throw "Docker's Linux engine is unavailable. Open Docker Desktop > Troubleshoot, then retry."
    }

    Stop-RecordedLocalDashboard

    Write-Status "Validating Docker Compose configuration..."
    docker compose --profile demo config --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose configuration validation failed."
    }

    Write-Status "Building and starting RabbitMQ, FastAPI, consumer, simulator, and Streamlit..."
    docker compose --profile demo up -d --build
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose could not start the platform. See: docker compose logs"
    }

    Write-Status "Waiting for the real-time API..."
    if (-not (Wait-HttpEndpoint -Url "http://127.0.0.1:8001/health" -TimeoutSeconds 180)) {
        throw "The real-time API did not become healthy. Run: docker compose logs realtime-api"
    }
    Write-Status "Real-time API and RabbitMQ consumer are healthy." "OK"

    Write-Status "Waiting for the analytics dashboard..."
    if (-not (Wait-HttpEndpoint -Url "http://127.0.0.1:8501" -TimeoutSeconds 180)) {
        throw "The dashboard did not become healthy. Run: docker compose logs dashboard"
    }

    Write-Status "STRICT REAL-TIME MODE IS ACTIVE." "OK"
    Write-Host ""
    Write-Host "Dashboard:          http://127.0.0.1:8501" -ForegroundColor Green
    Write-Host "API documentation:  http://127.0.0.1:8001/docs" -ForegroundColor Green
    Write-Host "RabbitMQ management: http://127.0.0.1:15672" -ForegroundColor Green
    Write-Host "RabbitMQ login:      ecommerce / ecommerce-demo" -ForegroundColor Green
    Write-Host "Stop command:        docker compose --profile demo down" -ForegroundColor Yellow
}

function Start-LocalDashboard {
    Write-Status "Starting local historical analytics mode." "WARN"
    Write-Status "RabbitMQ streaming is not active in Local mode." "WARN"
    $python = Get-ProjectPython

    Write-Status "Checking Python dependencies..."
    & $python -c "import duckdb, pandas, plotly, streamlit"
    if ($LASTEXITCODE -ne 0) {
        Write-Status "Installing pinned Python dependencies (first run only)..."
        & $python -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
        if ($LASTEXITCODE -ne 0) {
            throw "Python dependency installation failed."
        }
    }

    $warehouse = Join-Path $ProjectRoot "artifacts\ecommerce.duckdb"
    if (-not (Test-Path -LiteralPath $warehouse)) {
        Write-Status "Building the sample warehouse and analytical outputs..."
        & $python -m src.cli all --rows 100000 --runs 3
        if ($LASTEXITCODE -ne 0) {
            throw "The historical analytics pipeline failed."
        }
    }

    if (-not (Test-HttpEndpoint -Url "http://127.0.0.1:8501")) {
        Write-Status "Launching Streamlit on port 8501..."
        $arguments = @(
            "-m", "streamlit", "run", "src/dashboard.py",
            "--server.port", "8501",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false"
        )
        $dashboardProcess = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
        Set-Content -LiteralPath (Join-Path $LogDirectory "local-dashboard.pid") -Value $dashboardProcess.Id -Encoding ASCII
    }

    if (-not (Wait-HttpEndpoint -Url "http://127.0.0.1:8501" -TimeoutSeconds 90)) {
        throw "Streamlit did not become ready on port 8501. Review $LogFile"
    }

    Write-Status "Historical analytics dashboard is ready." "OK"
    Write-Host "Dashboard: http://127.0.0.1:8501" -ForegroundColor Green
    Write-Host "Real-time status: OFFLINE until Docker Desktop's Linux engine is repaired." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "E-Commerce Sales Analytics - One-Click Startup" -ForegroundColor White
Write-Host "================================================" -ForegroundColor White
Write-Status "Project: $ProjectRoot"

if ($CheckOnly) {
    Show-StartupDiagnostics | Out-Null
    exit 0
}

try {
    $startedDockerMode = $false
    if ($Mode -in @("Auto", "Docker")) {
        try {
            Start-DockerPlatform
            $startedDockerMode = $true
        }
        catch {
            if ($Mode -eq "Docker") {
                throw
            }
            Write-Status $_.Exception.Message "WARN"
            Write-Status "Automatic fallback: starting the historical dashboard." "WARN"
        }
    }

    if (-not $startedDockerMode) {
        Start-LocalDashboard
    }

    if (-not $NoBrowser) {
        Start-Process "http://127.0.0.1:8501" | Out-Null
    }
    Write-Status "Startup completed. This window may now be closed." "OK"
}
catch {
    Write-Status $_.Exception.Message "ERROR"
    Write-Host ""
    Write-Host "Startup failed. Full log: $LogFile" -ForegroundColor Red
    Write-Host "Press Enter to close this window." -ForegroundColor Yellow
    [void](Read-Host)
    exit 1
}

