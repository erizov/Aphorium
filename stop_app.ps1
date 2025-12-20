# PowerShell script to stop Aphorium API server
# Usage: .\stop_app.ps1

Write-Host "Stopping Aphorium API server..." -ForegroundColor Yellow

# Find and kill uvicorn processes
$processes = Get-Process | Where-Object { $_.ProcessName -like "*uvicorn*" -or $_.CommandLine -like "*api.main:app*" }

if ($processes) {
    foreach ($proc in $processes) {
        Write-Host "Stopping process $($proc.Id)..." -ForegroundColor Cyan
        Stop-Process -Id $proc.Id -Force
    }
    Write-Host "Server stopped." -ForegroundColor Green
} else {
    Write-Host "No running server found." -ForegroundColor Yellow
}

# Also try to find Python processes running the API
$pythonProcs = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*api.main*" -or $_.CommandLine -like "*uvicorn*"
}

if ($pythonProcs) {
    foreach ($proc in $pythonProcs) {
        Write-Host "Stopping Python process $($proc.Id)..." -ForegroundColor Cyan
        Stop-Process -Id $proc.Id -Force
    }
}

