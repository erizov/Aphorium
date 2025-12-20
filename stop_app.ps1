# PowerShell script to stop Aphorium API server and frontend
# Usage: .\stop_app.ps1

Write-Host "Stopping Aphorium servers..." -ForegroundColor Yellow

# Stop background jobs
$pidFile = ".app_pids.txt"
if (Test-Path $pidFile) {
    $pids = Get-Content $pidFile
    foreach ($pid in $pids) {
        $job = Get-Job -Id $pid -ErrorAction SilentlyContinue
        if ($job) {
            Write-Host "Stopping job $pid..." -ForegroundColor Cyan
            Stop-Job -Id $pid -ErrorAction SilentlyContinue
            Remove-Job -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# Stop all background jobs
Get-Job | Where-Object { $_.Command -like "*uvicorn*" -or $_.Command -like "*npm*" } | ForEach-Object {
    Write-Host "Stopping job $($_.Id)..." -ForegroundColor Cyan
    Stop-Job -Id $_.Id -ErrorAction SilentlyContinue
    Remove-Job -Id $_.Id -Force -ErrorAction SilentlyContinue
}

# Find and kill uvicorn processes
$uvicornProcs = Get-Process | Where-Object { 
    $_.ProcessName -like "*python*" -and 
    $_.CommandLine -like "*uvicorn*" -or
    $_.CommandLine -like "*api.main*"
} -ErrorAction SilentlyContinue

if ($uvicornProcs) {
    foreach ($proc in $uvicornProcs) {
        Write-Host "Stopping uvicorn process $($proc.Id)..." -ForegroundColor Cyan
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}

# Find and kill node processes (frontend)
$nodeProcs = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*frontend*" -or
    $_.CommandLine -like "*vite*" -or
    $_.CommandLine -like "*npm*"
}

if ($nodeProcs) {
    foreach ($proc in $nodeProcs) {
        Write-Host "Stopping node process $($proc.Id)..." -ForegroundColor Cyan
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}

# Also try to find processes by port
$backendPort = 8000
$frontendPort = 3000

# Kill processes on backend port
$backendProcs = Get-NetTCPConnection -LocalPort $backendPort -ErrorAction SilentlyContinue | 
    Select-Object -ExpandProperty OwningProcess -Unique
if ($backendProcs) {
    foreach ($pid in $backendProcs) {
        Write-Host "Stopping process on port $backendPort (PID: $pid)..." -ForegroundColor Cyan
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
}

# Kill processes on frontend port
$frontendProcs = Get-NetTCPConnection -LocalPort $frontendPort -ErrorAction SilentlyContinue | 
    Select-Object -ExpandProperty OwningProcess -Unique
if ($frontendProcs) {
    foreach ($pid in $frontendProcs) {
        Write-Host "Stopping process on port $frontendPort (PID: $pid)..." -ForegroundColor Cyan
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Servers stopped." -ForegroundColor Green
