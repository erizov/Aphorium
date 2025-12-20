# PowerShell script to restart Aphorium API server and frontend
# Usage: .\restart_app.ps1

Write-Host "Restarting Aphorium..." -ForegroundColor Cyan

# Stop the servers
& ".\stop_app.ps1"

# Wait a moment
Start-Sleep -Seconds 2

# Start the servers
& ".\start_app.ps1"
