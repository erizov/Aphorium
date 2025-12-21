# PowerShell script to start Aphorium API server and frontend
# Usage: .\start_app.ps1

Write-Host "Starting Aphorium..." -ForegroundColor Green
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Virtual environment not found. Creating..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& "venv\Scripts\Activate.ps1"

# Check if dependencies are installed
Write-Host "Checking backend dependencies..." -ForegroundColor Cyan
pip show fastapi | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing backend dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Check frontend dependencies
Write-Host "Checking frontend dependencies..." -ForegroundColor Cyan
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location frontend
    npm install
    Set-Location ..
}

# Check if .env file exists
Write-Host "Checking configuration..." -ForegroundColor Cyan
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
        Copy-Item .env.example .env
        Write-Host "Please edit .env with your database credentials!" -ForegroundColor Yellow
    } else {
        Write-Host "Creating .env file with defaults..." -ForegroundColor Yellow
        @"
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aphorium
LOG_LEVEL=INFO
LOG_FILE=logs/aphorium.log
API_HOST=0.0.0.0
API_PORT=8000
WIKIQUOTE_RU_BASE_URL=https://ru.wikiquote.org
WIKIQUOTE_EN_BASE_URL=https://en.wikiquote.org
SCRAPE_DELAY=1.0
"@ | Out-File -FilePath .env -Encoding utf8
        Write-Host "Please edit .env with your database credentials!" -ForegroundColor Yellow
    }
}

# Check database configuration
Write-Host "Checking database..." -ForegroundColor Cyan
$dbUrl = ""
if (Test-Path ".env") {
    $dbUrl = (Get-Content .env | Select-String "DATABASE_URL").ToString()
}

if ($dbUrl -like "*postgresql*") {
    Write-Host "Using PostgreSQL database" -ForegroundColor Green
    $pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
    if ($pgService) {
        if ($pgService.Status -ne "Running") {
            Write-Host "Warning: PostgreSQL service may not be running" -ForegroundColor Yellow
        } else {
            Write-Host "  PostgreSQL service is running" -ForegroundColor Green
        }
    }
} elseif ($dbUrl -like "*sqlite*") {
    Write-Host "Using SQLite database" -ForegroundColor Cyan
}

# Check if database is initialized
if (-not (Test-Path ".db_initialized")) {
    Write-Host "Database not initialized. Setting up..." -ForegroundColor Yellow
    
    if ($dbUrl -like "*sqlite*") {
        python setup_database_sqlite.py
    } else {
        python init_database.py
    }
    
    New-Item -ItemType File -Path ".db_initialized" -Force | Out-Null
}

# Create logs directory
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

# PID file
$pidFile = ".app_pids.txt"

# Start backend server in new window
Write-Host ""
Write-Host "Starting backend API server..." -ForegroundColor Green
$backendScript = @"
cd '$PWD'
& '$PWD\venv\Scripts\python.exe' -m uvicorn api.main:app --host 0.0.0.0 --port 8000
pause
"@
$backendScript | Out-File -FilePath "start_backend.ps1" -Encoding utf8

$backendProcess = Start-Process powershell -ArgumentList "-NoExit", "-File", "start_backend.ps1" -PassThru
$backendProcess.Id | Out-File -FilePath $pidFile -Encoding utf8

# Start frontend dev server in new window
Write-Host "Starting frontend dev server..." -ForegroundColor Green
$frontendScript = @"
cd '$PWD\frontend'
npm run dev -- --port 3000 --strictPort
pause
"@
$frontendScript | Out-File -FilePath "start_frontend.ps1" -Encoding utf8

$frontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-File", "start_frontend.ps1" -PassThru
$frontendProcess.Id | Out-File -FilePath $pidFile -Append -Encoding utf8

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Aphorium is starting..." -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Backend API: http://localhost:8000" -ForegroundColor Yellow
Write-Host "API Docs:    http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "Frontend:    http://localhost:3000" -ForegroundColor Yellow
Write-Host ""
Write-Host "Both servers are running in separate windows." -ForegroundColor Green
Write-Host "To stop both servers, run: .\stop_app.ps1" -ForegroundColor Cyan
Write-Host ""

# Wait a moment for servers to start
Start-Sleep -Seconds 5

# Check if servers are running
try {
    $backendCheck = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
    if ($backendCheck.StatusCode -eq 200) {
        Write-Host "[OK] Backend server is running" -ForegroundColor Green
    }
} catch {
    Write-Host "[...] Backend server starting (check the backend window)..." -ForegroundColor Yellow
}

Write-Host "[...] Frontend server starting (check the frontend window)..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Backend PID: $($backendProcess.Id)" -ForegroundColor Gray
Write-Host "Frontend PID: $($frontendProcess.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "You can close this window. Servers will continue running." -ForegroundColor Cyan
Write-Host "Use .\stop_app.ps1 to stop both servers." -ForegroundColor Cyan
