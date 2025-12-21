# PowerShell script to restart Aphorium API server and frontend
# Usage: .\restart_app.ps1

Write-Host "Restarting Aphorium..." -ForegroundColor Cyan

# Stop the servers and kill all related processes
Write-Host "Stopping previous instances..." -ForegroundColor Yellow

# First, run stop script to clean up
& ".\stop_app.ps1"

# Kill ALL processes that might be related:
# 1. Processes on ports 8000, 3000, 3001, 3002, 3003, etc. (in case frontend tried different ports)
Write-Host "Killing processes on ports..." -ForegroundColor Yellow
for ($port = 8000; $port -le 3010; $port++) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($pid in $pids) {
            Write-Host "  Killing process on port $port (PID: $pid)..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
}

# 2. Kill all node processes (frontend)
Write-Host "Killing all node processes..." -ForegroundColor Yellow
Get-Process node -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "  Killing node process (PID: $($_.Id))..." -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

# 3. Kill all python processes running uvicorn
Write-Host "Killing uvicorn/python processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        if ($cmdLine -like "*uvicorn*" -or $cmdLine -like "*api.main*" -or $cmdLine -like "*aphorium*") {
            Write-Host "  Killing uvicorn process (PID: $($_.Id))..." -ForegroundColor Yellow
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    } catch {
        # If we can't check command line, check if it's using our ports
        $usingPort = $false
        try {
            $conns = Get-NetTCPConnection -OwningProcess $_.Id -ErrorAction SilentlyContinue
            if ($conns) {
                $ports = $conns | Select-Object -ExpandProperty LocalPort
                if ($ports -contains 8000 -or $ports -contains 3000) {
                    $usingPort = $true
                }
            }
        } catch {}
        if ($usingPort) {
            Write-Host "  Killing python process using our ports (PID: $($_.Id))..." -ForegroundColor Yellow
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

# 4. Kill tail and sed processes (from log monitoring)
Write-Host "Killing tail/sed processes..." -ForegroundColor Yellow
Get-Process | Where-Object {
    $_.ProcessName -eq "tail" -or 
    $_.CommandLine -like "*tail*logs*" -or
    $_.CommandLine -like "*sed*"
} | ForEach-Object {
    Write-Host "  Killing $($_.ProcessName) process (PID: $($_.Id))..." -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

# 5. Kill any processes from PID file
if (Test-Path ".app_pids.txt") {
    Write-Host "Killing processes from PID file..." -ForegroundColor Yellow
    $pids = Get-Content ".app_pids.txt" | Where-Object { $_ -match '^\d+$' }
    foreach ($pid in $pids) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  Killing process PID: $pid..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item ".app_pids.txt" -Force -ErrorAction SilentlyContinue
}

# Wait for ports 8000 and 3000 to be released - NEVER use different ports
Write-Host "Checking if ports 8000 and 3000 are in use..." -ForegroundColor Cyan
$port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$port3000InUse = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue

# Only wait if ports are actually in use
if ($port8000InUse -or $port3000InUse) {
    Write-Host "Ports are in use. Waiting for release..." -ForegroundColor Yellow
    Write-Host "IMPORTANT: Will wait until ports are free - will NOT use different ports!" -ForegroundColor Yellow
    $maxWait = 30
    $waited = 0
    
    while ($waited -lt $maxWait) {
        $port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
        $port3000InUse = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
        
        if (-not $port8000InUse -and -not $port3000InUse) {
            Write-Host "All ports are free!" -ForegroundColor Green
            break
        }
        
        # If ports still in use, try to kill processes again
        if ($port8000InUse) {
            $pids = $port8000InUse | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($pid in $pids) {
                Write-Host "  Port 8000 still in use, killing PID: $pid..." -ForegroundColor Yellow
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        }
        
        if ($port3000InUse) {
            $pids = $port3000InUse | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($pid in $pids) {
                Write-Host "  Port 3000 still in use, killing PID: $pid..." -ForegroundColor Yellow
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        }
        
        # Also kill any remaining node/python processes using our ports
        Get-Process node -ErrorAction SilentlyContinue | Where-Object {
            try {
                $conns = Get-NetTCPConnection -OwningProcess $_.Id -ErrorAction SilentlyContinue
                if ($conns) {
                    $ports = $conns | Select-Object -ExpandProperty LocalPort
                    $ports -contains 8000 -or $ports -contains 3000
                } else { $false }
            } catch { $false }
        } | Stop-Process -Force -ErrorAction SilentlyContinue
        
        Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            try {
                $conns = Get-NetTCPConnection -OwningProcess $_.Id -ErrorAction SilentlyContinue
                if ($conns) {
                    $ports = $conns | Select-Object -ExpandProperty LocalPort
                    $ports -contains 8000 -or $ports -contains 3000
                } else { $false }
            } catch { $false }
        } | Stop-Process -Force -ErrorAction SilentlyContinue
        
        Start-Sleep -Seconds 1
        $waited++
        Write-Host "  Waiting for ports 8000 and 3000... ($waited/$maxWait)" -ForegroundColor Gray
    }
    
    # Final check - fail if ports still in use
    $port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    $port3000InUse = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
    
    if ($port8000InUse -or $port3000InUse) {
        Write-Host "" -ForegroundColor Red
        Write-Host "ERROR: Ports 8000 and/or 3000 are still in use after $maxWait seconds!" -ForegroundColor Red
        Write-Host "Port 8000 in use: $($port8000InUse -ne $null)" -ForegroundColor Red
        Write-Host "Port 3000 in use: $($port3000InUse -ne $null)" -ForegroundColor Red
        Write-Host "Please manually kill processes and try again." -ForegroundColor Red
        Write-Host "You can use: Get-NetTCPConnection -LocalPort 8000,3000 | Stop-Process -Id {OwningProcess}" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "Ports 8000 and 3000 are already free!" -ForegroundColor Green
}

# Wait a bit more to ensure ports are fully released
Write-Host "Waiting 2 seconds to ensure ports are fully released..." -ForegroundColor Green
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
    # Use strict port - will fail if 3000 is not available
    npm run dev -- --port 3000 --strictPort
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
