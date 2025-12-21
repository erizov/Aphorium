# PowerShell script to restart Aphorium API server and frontend
# Usage: .\restart_app.ps1

Write-Host "Restarting Aphorium..." -ForegroundColor Cyan

# Stop the servers and kill all related processes
Write-Host "Stopping previous instances..." -ForegroundColor Yellow

# First, run stop script to clean up
& ".\stop_app.ps1"

# Kill processes on ports 8000, 3000, 3001, 3002 (in case frontend tried different ports)
$ports = @(8000, 3000, 3001, 3002)
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($pid in $pids) {
            Write-Host "Killing process on port $port (PID: $pid)..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
}

# Kill all node processes (frontend)
Get-Process node -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "Killing node process (PID: $($_.Id))..." -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

# Kill all python processes running uvicorn
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        if ($cmdLine -like "*uvicorn*" -or $cmdLine -like "*api.main*") {
            Write-Host "Killing uvicorn process (PID: $($_.Id))..." -ForegroundColor Yellow
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    } catch {
        # If we can't check command line, kill it anyway if it's using our ports
    }
}

# Wait for ports to be released with more aggressive checking
Write-Host "Waiting for ports to be released..." -ForegroundColor Cyan
$maxWait = 15
$waited = 0
while ($waited -lt $maxWait) {
    $allPortsFree = $true
    foreach ($port in @(8000, 3000)) {
        $inUse = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($inUse) {
            $allPortsFree = $false
            # Try to kill again
            $pids = $inUse | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($pid in $pids) {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        }
    }
    
    if ($allPortsFree) {
        Write-Host "All ports are free!" -ForegroundColor Green
        break
    }
    
    Start-Sleep -Seconds 1
    $waited++
    Write-Host "  Waiting for ports... ($waited/$maxWait)" -ForegroundColor Gray
}

# Final check - fail if ports still in use
$port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$port3000InUse = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue

if ($port8000InUse -or $port3000InUse) {
    Write-Host "ERROR: Ports are still in use after $maxWait seconds!" -ForegroundColor Red
    Write-Host "Please manually kill processes and try again." -ForegroundColor Red
    exit 1
}

# Wait a bit more to ensure ports are fully released
Start-Sleep -Seconds 2

# Close this terminal and start new one with servers
Write-Host "Starting new terminal with servers..." -ForegroundColor Green

# Create startup script
$startScript = @"
# PowerShell script to start Aphorium with combined logs
cd '$PWD'

# Activate virtual environment
& "venv\Scripts\Activate.ps1"

# Create logs directory
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

# Start backend in background job
Write-Host "Starting backend API server..." -ForegroundColor Green
`$backendJob = Start-Job -ScriptBlock {
    Set-Location '$PWD'
    & '$PWD\venv\Scripts\python.exe' -m uvicorn api.main:app --host 0.0.0.0 --port 8000
}

# Start frontend in background job
Write-Host "Starting frontend dev server..." -ForegroundColor Green
`$frontendJob = Start-Job -ScriptBlock {
    Set-Location '$PWD\frontend'
    npm run dev
}

# Save PIDs
`$backendJob.Id | Out-File -FilePath ".app_pids.txt" -Encoding utf8
`$frontendJob.Id | Out-File -FilePath ".app_pids.txt" -Append -Encoding utf8

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
    while (`$true) {
        `$backendOutput = Receive-Job -Job `$backendJob -ErrorAction SilentlyContinue
        `$frontendOutput = Receive-Job -Job `$frontendJob -ErrorAction SilentlyContinue
        
        if (`$backendOutput) {
            Write-Host "[BACKEND] `$backendOutput" -ForegroundColor Cyan
        }
        if (`$frontendOutput) {
            Write-Host "[FRONTEND] `$frontendOutput" -ForegroundColor Magenta
        }
        
        Start-Sleep -Milliseconds 500
    }
} finally {
    Write-Host "`nStopping servers..." -ForegroundColor Yellow
    Stop-Job -Job `$backendJob, `$frontendJob
    Remove-Job -Job `$backendJob, `$frontendJob
    & ".\stop_app.ps1"
}
"@

$startScript | Out-File -FilePath "start_with_logs.ps1" -Encoding utf8

# Start new PowerShell window with the startup script
Start-Process powershell -ArgumentList "-NoExit", "-File", "start_with_logs.ps1"

# Close this window after a short delay
Start-Sleep -Seconds 1
exit
