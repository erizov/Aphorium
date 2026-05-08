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

# Kill processes by port
$backendPort = 8001
$frontendPort = 3000

# Backend port
try {
    $backendProcs = Get-NetTCPConnection -LocalPort $backendPort -ErrorAction SilentlyContinue | 
        Select-Object -ExpandProperty OwningProcess -Unique
    if ($backendProcs) {
        foreach ($processId in $backendProcs) {
            if ($processId -is [int] -and $processId -gt 0) {
                Write-Host "Stopping process on port $backendPort (PID: $processId)..." -ForegroundColor Cyan
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            }
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
            if ($processId -is [int] -and $processId -gt 0) {
                Write-Host "Stopping process on port $frontendPort (PID: $processId)..." -ForegroundColor Cyan
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            }
        }
    }
} catch {
    # Port check failed, continue
}

Write-Host "Servers stopped." -ForegroundColor Green
