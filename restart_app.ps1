# PowerShell script to restart Aphorium API server and frontend
# Usage: .\restart_app.ps1

# Setup logging
$logDir = "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}
$logFile = Join-Path $logDir "restart_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO",
        [switch]$NoConsole
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] [$Level] $Message"
    
    # Write to log file
    Add-Content -Path $logFile -Value $logMessage -Encoding UTF8
    
    # Write to console with colors
    if (-not $NoConsole) {
        switch ($Level) {
            "ERROR" { Write-Host $Message -ForegroundColor Red }
            "WARN"  { Write-Host $Message -ForegroundColor Yellow }
            "SUCCESS" { Write-Host $Message -ForegroundColor Green }
            "INFO"  { Write-Host $Message -ForegroundColor Cyan }
            default { Write-Host $Message }
        }
    }
}

Write-Log "============================================================" "INFO"
Write-Log "Restarting Aphorium..." "INFO"
Write-Log "Log file: $logFile" "INFO"
Write-Log "============================================================" "INFO"

# Stop the servers and kill all related processes
Write-Log "Stopping previous instances..." "INFO"

# First, run stop script to clean up
Write-Log "Running stop_app.ps1..." "INFO"
try {
    & ".\stop_app.ps1" 2>&1 | ForEach-Object {
        Write-Log $_ "INFO" -NoConsole
    }
    Write-Log "stop_app.ps1 completed" "SUCCESS"
} catch {
    Write-Log "Error running stop_app.ps1: $_" "ERROR"
}

# Kill ALL processes that might be related:
# 1. Processes on ports 8000, 3000, 3001, 3002, 3003, etc. (in case frontend tried different ports)
Write-Log "Killing processes on ports..." "INFO"
$portsToCheck = @(8000) + (3000..3010)
$foundAny = $false
foreach ($port in $portsToCheck) {
    try {
        $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($connections) {
            $foundAny = $true
            $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($processId in $pids) {
                Write-Log "  Killing process on port $port (PID: $processId)..." "INFO"
                try {
                    Stop-Process -Id $processId -Force -ErrorAction Stop
                    Write-Log "    Successfully killed PID: $processId" "SUCCESS"
                } catch {
                    Write-Log "    Failed to kill PID: $processId - $_" "WARN"
                }
            }
        }
    } catch {
        Write-Log "  Error checking port $port : $_" "WARN"
    }
}
if (-not $foundAny) {
    Write-Log "  No processes found on ports 8000, 3000-3010" "INFO"
}

# 2. Kill all node processes (frontend)
Write-Log "Killing all node processes..." "INFO"
$nodeProcesses = Get-Process node -ErrorAction SilentlyContinue
if ($nodeProcesses) {
    $nodeProcesses | ForEach-Object {
        Write-Log "  Killing node process (PID: $($_.Id))..." "INFO"
        try {
            Stop-Process -Id $_.Id -Force -ErrorAction Stop
            Write-Log "    Successfully killed node PID: $($_.Id)" "SUCCESS"
        } catch {
            Write-Log "    Failed to kill node PID: $($_.Id) - $_" "WARN"
        }
    }
} else {
    Write-Log "  No node processes found" "INFO"
}

# 3. Kill all python processes running uvicorn
Write-Log "Killing uvicorn/python processes..." "INFO"
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    $pythonProcesses | ForEach-Object {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
            if ($cmdLine -like "*uvicorn*" -or $cmdLine -like "*api.main*" -or $cmdLine -like "*aphorium*") {
                Write-Log "  Killing uvicorn process (PID: $($_.Id))..." "INFO"
                try {
                    Stop-Process -Id $_.Id -Force -ErrorAction Stop
                    Write-Log "    Successfully killed uvicorn PID: $($_.Id)" "SUCCESS"
                } catch {
                    Write-Log "    Failed to kill uvicorn PID: $($_.Id) - $_" "WARN"
                }
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
                Write-Log "  Killing python process using our ports (PID: $($_.Id))..." "INFO"
                try {
                    Stop-Process -Id $_.Id -Force -ErrorAction Stop
                    Write-Log "    Successfully killed python PID: $($_.Id)" "SUCCESS"
                } catch {
                    Write-Log "    Failed to kill python PID: $($_.Id) - $_" "WARN"
                }
            }
        }
    }
} else {
    Write-Log "  No python processes found" "INFO"
}

# 4. Kill tail and sed processes (from log monitoring)
Write-Log "Killing tail/sed processes..." "INFO"
$logProcesses = Get-Process | Where-Object {
    $_.ProcessName -eq "tail" -or 
    $_.CommandLine -like "*tail*logs*" -or
    $_.CommandLine -like "*sed*"
}
if ($logProcesses) {
    $logProcesses | ForEach-Object {
        Write-Log "  Killing $($_.ProcessName) process (PID: $($_.Id))..." "INFO"
        try {
            Stop-Process -Id $_.Id -Force -ErrorAction Stop
            Write-Log "    Successfully killed $($_.ProcessName) PID: $($_.Id)" "SUCCESS"
        } catch {
            Write-Log "    Failed to kill $($_.ProcessName) PID: $($_.Id) - $_" "WARN"
        }
    }
} else {
    Write-Log "  No tail/sed processes found" "INFO"
}

# 5. Kill any processes from PID file
if (Test-Path ".app_pids.txt") {
    Write-Log "Killing processes from PID file..." "INFO"
    $pids = Get-Content ".app_pids.txt" | Where-Object { $_ -match '^\d+$' }
    foreach ($processId in $pids) {
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Log "  Killing process PID: $processId..." "INFO"
            try {
                Stop-Process -Id $processId -Force -ErrorAction Stop
                Write-Log "    Successfully killed PID: $processId" "SUCCESS"
            } catch {
                Write-Log "    Failed to kill PID: $processId - $_" "WARN"
            }
        } else {
            Write-Log "  Process PID: $processId not found (may have already terminated)" "INFO"
        }
    }
    Remove-Item ".app_pids.txt" -Force -ErrorAction SilentlyContinue
    Write-Log "  Removed .app_pids.txt file" "INFO"
} else {
    Write-Log "  No PID file found" "INFO"
}

# Wait for ports 8000 and 3000 to be released - NEVER use different ports
Write-Log "Checking if ports 8000 and 3000 are in use..." "INFO"
$port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$port3000InUse = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue

# Only wait if ports are actually in use
if ($port8000InUse -or $port3000InUse) {
    Write-Log "Ports are in use. Waiting for release..." "WARN"
    Write-Log "IMPORTANT: Will wait until ports are free - will NOT use different ports!" "WARN"
    $maxWait = 30
    $waited = 0
    
    while ($waited -lt $maxWait) {
        $port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
        $port3000InUse = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
        
        if (-not $port8000InUse -and -not $port3000InUse) {
            Write-Log "All ports are free!" "SUCCESS"
            break
        }
        
        # If ports still in use, try to kill processes again
        if ($port8000InUse) {
            $pids = $port8000InUse | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($processId in $pids) {
                Write-Log "  Port 8000 still in use, killing PID: $processId..." "WARN"
                try {
                    Stop-Process -Id $processId -Force -ErrorAction Stop
                    Write-Log "    Successfully killed PID: $processId" "SUCCESS"
                } catch {
                    Write-Log "    Failed to kill PID: $processId - $_" "WARN"
                }
            }
        }
        
        if ($port3000InUse) {
            $pids = $port3000InUse | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($processId in $pids) {
                Write-Log "  Port 3000 still in use, killing PID: $processId..." "WARN"
                try {
                    Stop-Process -Id $processId -Force -ErrorAction Stop
                    Write-Log "    Successfully killed PID: $processId" "SUCCESS"
                } catch {
                    Write-Log "    Failed to kill PID: $processId - $_" "WARN"
                }
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
        Write-Log "  Waiting for ports 8000 and 3000... ($waited/$maxWait)" "INFO"
    }
    
    # Final check - fail if ports still in use
    $port8000InUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    $port3000InUse = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
    
    if ($port8000InUse -or $port3000InUse) {
        Write-Log "" "ERROR"
        Write-Log "ERROR: Ports 8000 and/or 3000 are still in use after $maxWait seconds!" "ERROR"
        Write-Log "Port 8000 in use: $($null -ne $port8000InUse)" "ERROR"
        Write-Log "Port 3000 in use: $($null -ne $port3000InUse)" "ERROR"
        Write-Log "Please manually kill processes and try again." "ERROR"
        Write-Log "You can use: Get-NetTCPConnection -LocalPort 8000,3000 | Stop-Process -Id {OwningProcess}" "WARN"
        exit 1
    }
} else {
    Write-Log "Ports 8000 and 3000 are already free!" "SUCCESS"
}

# Wait a bit more to ensure ports are fully released
Write-Log "Waiting 2 seconds to ensure ports are fully released..." "INFO"
Start-Sleep -Seconds 2

# Final aggressive cleanup - kill any remaining processes on our ports
Write-Log "Final cleanup: killing any remaining processes on ports 8000 and 3000..." "INFO"
$portsToCheck = @(8000, 3000)
foreach ($port in $portsToCheck) {
    try {
        $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($connections) {
            $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($processId in $pids) {
                Write-Log "  Killing process on port $port (PID: $processId)..." "INFO"
                try {
                    Stop-Process -Id $processId -Force -ErrorAction Stop
                    Write-Log "    Successfully killed PID: $processId" "SUCCESS"
                } catch {
                    Write-Log "    Failed to kill PID: $processId - $_" "WARN"
                }
            }
            Start-Sleep -Milliseconds 500
        }
    } catch {
        Write-Log "  Error checking port $port : $_" "WARN"
    }
}

# Kill all node processes one more time (in case something started)
Write-Log "Killing all node processes one final time..." "INFO"
$nodeProcesses = Get-Process node -ErrorAction SilentlyContinue
if ($nodeProcesses) {
    $nodeProcesses | ForEach-Object {
        Write-Log "  Killing node process (PID: $($_.Id))..." "INFO"
        try {
            Stop-Process -Id $_.Id -Force -ErrorAction Stop
            Write-Log "    Successfully killed node PID: $($_.Id)" "SUCCESS"
        } catch {
            Write-Log "    Failed to kill node PID: $($_.Id) - $_" "WARN"
        }
    }
} else {
    Write-Log "  No node processes found" "INFO"
}

# Wait one more second
Start-Sleep -Seconds 1

# Final verification - ports must be free
Write-Log "Verifying ports 8000 and 3000 are free..." "INFO"
$port8000Final = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$port3000Final = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue

if ($port8000Final -or $port3000Final) {
    Write-Log "" "WARN"
    Write-Log "WARNING: Ports still in use after cleanup!" "WARN"
    Write-Log "Port 8000: $(if ($port8000Final) { "IN USE (PID: $($port8000Final.OwningProcess))" } else { "FREE" })" "WARN"
    Write-Log "Port 3000: $(if ($port3000Final) { "IN USE (PID: $($port3000Final.OwningProcess))" } else { "FREE" })" "WARN"
    Write-Log "Attempting to kill again..." "WARN"
    if ($port8000Final) {
        $pids = $port8000Final | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($processId in $pids) {
            try {
                Stop-Process -Id $processId -Force -ErrorAction Stop
                Write-Log "  Successfully killed PID: $processId on port 8000" "SUCCESS"
            } catch {
                Write-Log "  Failed to kill PID: $processId on port 8000 - $_" "WARN"
            }
        }
    }
    if ($port3000Final) {
        $pids = $port3000Final | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($processId in $pids) {
            try {
                Stop-Process -Id $processId -Force -ErrorAction Stop
                Write-Log "  Successfully killed PID: $processId on port 3000" "SUCCESS"
            } catch {
                Write-Log "  Failed to kill PID: $processId on port 3000 - $_" "WARN"
            }
        }
    }
    Start-Sleep -Seconds 1
} else {
    Write-Log "  Ports 8000 and 3000 are confirmed free!" "SUCCESS"
}

# Close this terminal and start new one with servers
Write-Log "Starting new terminal with servers..." "SUCCESS"
Write-Log "============================================================" "INFO"

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

# Final check: make absolutely sure port 3000 is free
`$port3000Check = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
if (`$port3000Check) {
    `$pid = `$port3000Check | Select-Object -ExpandProperty OwningProcess -Unique
    Write-Host "  WARNING: Port 3000 still in use (PID: `$pid), killing..." -ForegroundColor Yellow
    Stop-Process -Id `$pid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    `$port3000Check = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
    if (`$port3000Check) {
        Write-Host "  ERROR: Port 3000 still in use after kill attempt!" -ForegroundColor Red
        Write-Host "  Please manually kill the process and try again" -ForegroundColor Red
        exit 1
    }
}

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
