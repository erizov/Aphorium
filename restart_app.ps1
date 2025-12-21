# PowerShell script to restart Aphorium API server and frontend
# Usage: .\restart_app.ps1

Write-Host "Restarting Aphorium..." -ForegroundColor Cyan

# Stop the servers and kill all related processes
Write-Host "Stopping previous instances..." -ForegroundColor Yellow

# Kill processes on ports 8000 and 3000
$port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess
$port3000 = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess

if ($port8000) {
    Write-Host "Killing process on port 8000 (PID: $port8000)..." -ForegroundColor Yellow
    Stop-Process -Id $port8000 -Force -ErrorAction SilentlyContinue
}

if ($port3000) {
    Write-Host "Killing process on port 3000 (PID: $port3000)..." -ForegroundColor Yellow
    Stop-Process -Id $port3000 -Force -ErrorAction SilentlyContinue
}

# Also kill any processes from PID file
if (Test-Path ".app_pids.txt") {
    $pids = Get-Content ".app_pids.txt" | Where-Object { $_ -match '^\d+$' }
    foreach ($pid in $pids) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Killing process PID: $pid..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
}

# Kill any uvicorn or node processes related to this app
Get-Process | Where-Object {
    ($_.ProcessName -eq "python" -or $_.ProcessName -eq "node") -and
    ($_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*aphorium*" -or $_.Path -like "*aphorium*")
} | Stop-Process -Force -ErrorAction SilentlyContinue

# Wait for ports to be released
Write-Host "Waiting for ports to be released..." -ForegroundColor Cyan
$maxWait = 10
$waited = 0
while ($waited -lt $maxWait) {
    $port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    $port3000InUse = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
    
    if (-not $port8000InUse -and -not $port3000InUse) {
        break
    }
    
    Start-Sleep -Seconds 1
    $waited++
    Write-Host "  Waiting... ($waited/$maxWait)" -ForegroundColor Gray
}

if ($waited -ge $maxWait) {
    Write-Host "Warning: Ports may still be in use. Continuing anyway..." -ForegroundColor Yellow
}

# Wait a bit more
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
