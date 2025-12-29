# PowerShell script to stop Aphorium API server and frontend
# Usage: .\stop_app.ps1

Write-Host "Stopping Aphorium servers..." -ForegroundColor Yellow

# Read PIDs from file
$pidFile = ".app_pids.txt"
if (Test-Path $pidFile) {
    $pids = Get-Content $pidFile
    foreach ($processId in $pids) {
        if ($processId -match '^\d+$') {
            $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "Stopping process $processId..." -ForegroundColor Cyan
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# Clean up temporary scripts
if (Test-Path "start_backend.ps1") {
    Remove-Item "start_backend.ps1" -Force -ErrorAction SilentlyContinue
}
if (Test-Path "start_frontend.ps1") {
    Remove-Item "start_frontend.ps1" -Force -ErrorAction SilentlyContinue
}

# Find and kill uvicorn/python processes
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*api.main*"
} | ForEach-Object {
    Write-Host "Stopping Python process $($_.Id)..." -ForegroundColor Cyan
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

# Find and kill node processes (frontend)
Get-Process node -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "Stopping node process $($_.Id)..." -ForegroundColor Cyan
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

# Kill tail and sed processes (from log monitoring)
Get-Process | Where-Object {
    $_.ProcessName -eq "tail" -or 
    $_.CommandLine -like "*tail*logs*" -or
    $_.CommandLine -like "*sed*"
} | ForEach-Object {
    Write-Host "Stopping $($_.ProcessName) process $($_.Id)..." -ForegroundColor Cyan
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

# Kill processes by port
$backendPort = 8000
$frontendPort = 3000

# Backend port
try {
    $backendProcs = Get-NetTCPConnection -LocalPort $backendPort -ErrorAction SilentlyContinue | 
        Select-Object -ExpandProperty OwningProcess -Unique
    if ($backendProcs) {
        foreach ($processId in $backendProcs) {
            Write-Host "Stopping process on port $backendPort (PID: $processId)..." -ForegroundColor Cyan
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    # Port check failed, continue
}

# Frontend port
try {
    $frontendProcs = Get-NetTCPConnection -LocalPort $frontendPort -ErrorAction SilentlyContinue | 
        Select-Object -ExpandProperty OwningProcess -Unique
    if ($frontendProcs) {
        foreach ($processId in $frontendProcs) {
            Write-Host "Stopping process on port $frontendPort (PID: $processId)..." -ForegroundColor Cyan
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    # Port check failed, continue
}

Write-Host "Servers stopped." -ForegroundColor Green
