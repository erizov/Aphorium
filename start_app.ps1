# PowerShell script to start Aphorium API server
# Usage: .\start_app.ps1

Write-Host "Starting Aphorium API server..." -ForegroundColor Green

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Virtual environment not found. Creating..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& "venv\Scripts\Activate.ps1"

# Check if dependencies are installed
Write-Host "Checking dependencies..." -ForegroundColor Cyan
pip show fastapi | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
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
    # Check if PostgreSQL service is running (Windows)
    $pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
    if ($pgService) {
        if ($pgService.Status -ne "Running") {
            Write-Host "Warning: PostgreSQL service may not be running" -ForegroundColor Yellow
            Write-Host "  Service status: $($pgService.Status)" -ForegroundColor Yellow
        } else {
            Write-Host "  PostgreSQL service is running" -ForegroundColor Green
        }
    }
} elseif ($dbUrl -like "*sqlite*") {
    Write-Host "Using SQLite database" -ForegroundColor Cyan
} else {
    Write-Host "Database URL not configured in .env" -ForegroundColor Yellow
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

# Start the server
Write-Host "Starting API server on http://localhost:8000" -ForegroundColor Green
Write-Host "API docs available at http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

