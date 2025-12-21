# PowerShell script to start Aphorium with combined logs
cd 'E:\Python\GptEngineer\Aphorium'

# Activate virtual environment
& "venv\Scripts\Activate.ps1"

# Create logs directory
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

# Start backend in background job
Write-Host "Starting backend API server..." -ForegroundColor Green
$backendJob = Start-Job -ScriptBlock {
    Set-Location 'E:\Python\GptEngineer\Aphorium'
    & 'E:\Python\GptEngineer\Aphorium\venv\Scripts\python.exe' -m uvicorn api.main:app --host 0.0.0.0 --port 8000
}

# Start frontend in background job
Write-Host "Starting frontend dev server..." -ForegroundColor Green

# Final check: make absolutely sure port 3000 is free
$port3000Check = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
if ($port3000Check) {
    $pid = $port3000Check | Select-Object -ExpandProperty OwningProcess -Unique
    Write-Host "  WARNING: Port 3000 still in use (PID: $pid), killing..." -ForegroundColor Yellow
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    $port3000Check = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
    if ($port3000Check) {
        Write-Host "  ERROR: Port 3000 still in use after kill attempt!" -ForegroundColor Red
        Write-Host "  Please manually kill the process and try again" -ForegroundColor Red
        exit 1
    }
}

$frontendJob = Start-Job -ScriptBlock {
    Set-Location 'E:\Python\GptEngineer\Aphorium\frontend'
    # Use strict port - will fail if 3000 is not available
    npm run dev -- --port 3000 --strictPort
}

# Save PIDs
$backendJob.Id | Out-File -FilePath ".app_pids.txt" -Encoding utf8
$frontendJob.Id | Out-File -FilePath ".app_pids.txt" -Append -Encoding utf8

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Aphorium is running. Showing combined logs..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Backend API: http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend:    http://localhost:3000" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers" -ForegroundColor Cyan
Write-Host ""

# Show logs from both jobs
try {
    while ($true) {
        $backendOutput = Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
        $frontendOutput = Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue
        
        if ($backendOutput) {
            Write-Host "[BACKEND] $backendOutput" -ForegroundColor Cyan
        }
        if ($frontendOutput) {
            Write-Host "[FRONTEND] $frontendOutput" -ForegroundColor Magenta
        }
        
        Start-Sleep -Milliseconds 500
    }
} finally {
    Write-Host "
Stopping servers..." -ForegroundColor Yellow
    Stop-Job -Job $backendJob, $frontendJob
    Remove-Job -Job $backendJob, $frontendJob
    & ".\stop_app.ps1"
}
