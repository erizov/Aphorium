# PowerShell script to start Aphorium with combined logs
cd 'E:\Python\GptEngineer\Aphorium'

# Activate virtual environment
& "venv\Scripts\Activate.ps1"

# Create logs directory
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

function Get-PidsOnPort([int]$port) {
    try {
        $rows = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
            Where-Object { $_.State -eq "Listen" }
        if ($rows) {
            return @(
                $rows |
                    Select-Object -ExpandProperty OwningProcess -Unique |
                    Where-Object { $_ -is [int] -and $_ -gt 0 } |
                    Sort-Object -Unique
            )
        }
    } catch {
        # Fallback: parse netstat output (works even when Get-NetTCPConnection is restricted)
        try {
            $lines = netstat -ano -p TCP | Select-String -Pattern (":$port\\s+LISTENING\\s+(\\d+)$")
            $pids = @()
            foreach ($m in $lines.Matches) {
                $pids += [int]$m.Groups[1].Value
            }
            return @($pids | Where-Object { $_ -gt 0 } | Sort-Object -Unique)
        } catch {
            return @()
        }
    }
    return @()
}

# Log files (stdout/stderr must be different files for Start-Process).
# Use per-run timestamps to avoid file locks from aborted sessions.
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backendOutLog = Join-Path "logs" "backend.$ts.out.log"
$backendErrLog = Join-Path "logs" "backend.$ts.err.log"
$frontendOutLog = Join-Path "logs" "frontend.$ts.out.log"
$frontendErrLog = Join-Path "logs" "frontend.$ts.err.log"

New-Item -ItemType File -Path $backendOutLog -Force | Out-Null
New-Item -ItemType File -Path $backendErrLog -Force | Out-Null
New-Item -ItemType File -Path $frontendOutLog -Force | Out-Null
New-Item -ItemType File -Path $frontendErrLog -Force | Out-Null

# Start backend
Write-Host "Starting backend API server..." -ForegroundColor Green

# Ensure Python deps are installed (openai is required by llm_client)
& "E:\Python\GptEngineer\Aphorium\venv\Scripts\python.exe" -c "import openai" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python dependency 'openai' missing. Installing requirements..." -ForegroundColor Yellow
    & "E:\Python\GptEngineer\Aphorium\venv\Scripts\python.exe" -m pip install -r "E:\Python\GptEngineer\Aphorium\requirements.txt"
}

# Ensure port 8001 is free (8000 may be used by another app)
$backendPortPids = Get-PidsOnPort 8001
if ($backendPortPids.Count -gt 0) {
    Write-Host "  WARNING: Port 8001 in use (PID(s): $($backendPortPids -join ', ')), killing..." -ForegroundColor Yellow
    foreach ($portPid in $backendPortPids) {
        Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
    }

    $deadline = (Get-Date).AddSeconds(8)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 400
        $backendPortPids = Get-PidsOnPort 8001
        if ($backendPortPids.Count -eq 0) { break }
    }

    if ($backendPortPids.Count -gt 0) {
        Write-Host "  ERROR: Port 8001 still in use (PID(s): $($backendPortPids -join ', '))!" -ForegroundColor Red
        Write-Host "  Please manually kill the process(es) and try again" -ForegroundColor Red
        exit 1
    }
}

$backendProc = Start-Process `
    -FilePath "E:\Python\GptEngineer\Aphorium\venv\Scripts\python.exe" `
    -ArgumentList @(
        "-m", "uvicorn", "api.main:app",
        "--host", "0.0.0.0",
        "--port", "8001"
    ) `
    -WorkingDirectory "E:\Python\GptEngineer\Aphorium" `
    -RedirectStandardOutput $backendOutLog `
    -RedirectStandardError $backendErrLog `
    -PassThru

# Start frontend
Write-Host "Starting frontend dev server..." -ForegroundColor Green

# Final check: make absolutely sure port 3000 is free
$portPids = Get-PidsOnPort 3000
if ($portPids.Count -gt 0) {
    Write-Host "  WARNING: Port 3000 in use (PID(s): $($portPids -join ', ')), killing..." -ForegroundColor Yellow
    foreach ($portPid in $portPids) {
        Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
    }

    $deadline = (Get-Date).AddSeconds(8)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 400
        $portPids = Get-PidsOnPort 3000
        if ($portPids.Count -eq 0) { break }
    }

    if ($portPids.Count -gt 0) {
        Write-Host "  ERROR: Port 3000 still in use (PID(s): $($portPids -join ', '))!" -ForegroundColor Red
        Write-Host "  Please manually kill the process(es) and try again" -ForegroundColor Red
        exit 1
    }
}

$frontendProc = Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList @(
        "run", "dev", "--", "--port", "3000", "--strictPort"
    ) `
    -WorkingDirectory "E:\Python\GptEngineer\Aphorium\frontend" `
    -RedirectStandardOutput $frontendOutLog `
    -RedirectStandardError $frontendErrLog `
    -PassThru

# Save PIDs
$backendProc.Id | Out-File -FilePath ".app_pids.txt" -Encoding utf8
$frontendProc.Id | Out-File -FilePath ".app_pids.txt" -Append -Encoding utf8

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Aphorium is running. Showing combined logs..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Backend API: http://localhost:8001" -ForegroundColor Yellow
Write-Host "Frontend:    http://localhost:3000" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers" -ForegroundColor Cyan
Write-Host ""

# Tail logs (stream only new lines) and exit if a process dies
try {
    $tailBackendOut = Start-Job -ScriptBlock {
        param($path)
        Get-Content -Path $path -Wait -Tail 0
    } -ArgumentList $backendOutLog
    $tailBackendErr = Start-Job -ScriptBlock {
        param($path)
        Get-Content -Path $path -Wait -Tail 0
    } -ArgumentList $backendErrLog
    $tailFrontendOut = Start-Job -ScriptBlock {
        param($path)
        Get-Content -Path $path -Wait -Tail 0
    } -ArgumentList $frontendOutLog
    $tailFrontendErr = Start-Job -ScriptBlock {
        param($path)
        Get-Content -Path $path -Wait -Tail 0
    } -ArgumentList $frontendErrLog

    while ($true) {
        if ($backendProc.HasExited) {
            Write-Host ""
            Write-Host "Backend process exited ($($backendProc.ExitCode))." -ForegroundColor Red
            Write-Host "Last backend log lines:" -ForegroundColor Yellow
            Get-Content $backendOutLog -Tail 40 -ErrorAction SilentlyContinue
            Get-Content $backendErrLog -Tail 120 -ErrorAction SilentlyContinue
            exit 1
        }
        if ($frontendProc.HasExited) {
            Write-Host ""
            Write-Host "Frontend process exited ($($frontendProc.ExitCode))." -ForegroundColor Red
            Write-Host "Last frontend log lines:" -ForegroundColor Yellow
            Get-Content $frontendOutLog -Tail 80 -ErrorAction SilentlyContinue
            Get-Content $frontendErrLog -Tail 160 -ErrorAction SilentlyContinue
            exit 1
        }

        $newBackendOut = Receive-Job -Job $tailBackendOut -ErrorAction SilentlyContinue
        foreach ($line in $newBackendOut) {
            if ($line) { Write-Host "[BACKEND] $line" -ForegroundColor Cyan }
        }
        $newBackendErr = Receive-Job -Job $tailBackendErr -ErrorAction SilentlyContinue
        foreach ($line in $newBackendErr) {
            if ($line) { Write-Host "[BACKEND:ERR] $line" -ForegroundColor Red }
        }
        $newFrontendOut = Receive-Job -Job $tailFrontendOut -ErrorAction SilentlyContinue
        foreach ($line in $newFrontendOut) {
            if ($line) { Write-Host "[FRONTEND] $line" -ForegroundColor Magenta }
        }
        $newFrontendErr = Receive-Job -Job $tailFrontendErr -ErrorAction SilentlyContinue
        foreach ($line in $newFrontendErr) {
            if ($line) { Write-Host "[FRONTEND:ERR] $line" -ForegroundColor Red }
        }

        Start-Sleep -Milliseconds 250
    }
} finally {
    if ($tailBackendOut) { Stop-Job $tailBackendOut -ErrorAction SilentlyContinue }
    if ($tailBackendErr) { Stop-Job $tailBackendErr -ErrorAction SilentlyContinue }
    if ($tailFrontendOut) { Stop-Job $tailFrontendOut -ErrorAction SilentlyContinue }
    if ($tailFrontendErr) { Stop-Job $tailFrontendErr -ErrorAction SilentlyContinue }
    if ($tailBackendOut) { Remove-Job $tailBackendOut -Force -ErrorAction SilentlyContinue }
    if ($tailBackendErr) { Remove-Job $tailBackendErr -Force -ErrorAction SilentlyContinue }
    if ($tailFrontendOut) { Remove-Job $tailFrontendOut -Force -ErrorAction SilentlyContinue }
    if ($tailFrontendErr) { Remove-Job $tailFrontendErr -Force -ErrorAction SilentlyContinue }

    Write-Host "
Stopping servers..." -ForegroundColor Yellow
    if (-not $backendProc.HasExited) {
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
    if ($null -ne $frontendProc -and -not $frontendProc.HasExited) {
        Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue
    }
    & ".\stop_app.ps1"
}
