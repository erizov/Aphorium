# PowerShell script to restart Aphorium API server
# Usage: .\restart_app.ps1

Write-Host "Restarting Aphorium API server..." -ForegroundColor Cyan

# Stop the server
& ".\stop_app.ps1"

# Wait a moment
Start-Sleep -Seconds 2

# Start the server
& ".\start_app.ps1"

