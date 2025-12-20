# PowerShell script to stop Aphorium API server and frontend
# Usage: .\stop_app.ps1

Write-Host "Stopping Aphorium servers..." -ForegroundColor Yellow

# Read PIDs from file
$pidFile = ".app_pids.txt"
if (Test-Path $pidFile) {
    $pids = Get-Content $pidFile
    foreach ($pid in $pids) {
        if ($pid -match '^\d+$') {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "Stopping process $pid..." -ForegroundColor Cyan
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
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

# Kill processes by port
$backendPort = 8000
$frontendPort = 3000

# Backend port
try {
    $backendProcs = Get-NetTCPConnection -LocalPort $backendPort -ErrorAction SilentlyContinue | 
        Select-Object -ExpandProperty OwningProcess -Unique
    if ($backendProcs) {
        foreach ($pid in $backendProcs) {
            Write-Host "Stopping process on port $backendPort (PID: $pid)..." -ForegroundColor Cyan
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
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
        foreach ($pid in $frontendProcs) {
            Write-Host "Stopping process on port $frontendPort (PID: $pid)..." -ForegroundColor Cyan
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    # Port check failed, continue
}

Write-Host "Servers stopped." -ForegroundColor Green
