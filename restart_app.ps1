# PowerShell script to restart Aphorium API server and frontend
# Usage: .\restart_app.ps1

Write-Host "Restarting Aphorium..." -ForegroundColor Cyan

# Stop the servers
& ".\stop_app.ps1"

# Wait a moment
Start-Sleep -Seconds 2

# Start both servers and show logs in same terminal
Write-Host "Starting servers with combined logs..." -ForegroundColor Green

# Activate virtual environment
& "venv\Scripts\Activate.ps1"

# Start backend in background job
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    & "$using:PWD\venv\Scripts\python.exe" -m uvicorn api.main:app --host 0.0.0.0 --port 8000
}

# Start frontend in background job
$frontendJob = Start-Job -ScriptBlock {
    Set-Location "$using:PWD\frontend"
    npm run dev
}

# Save PIDs
$backendJob.Id | Out-File -FilePath ".app_pids.txt" -Encoding utf8
$frontendJob.Id | Out-File -FilePath ".app_pids.txt" -Append -Encoding utf8

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Aphorium is running. Showing combined logs..." -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
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
    Write-Host "`nStopping servers..." -ForegroundColor Yellow
    Stop-Job -Job $backendJob, $frontendJob
    Remove-Job -Job $backendJob, $frontendJob
    & ".\stop_app.ps1"
}
