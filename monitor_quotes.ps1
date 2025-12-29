# Monitor quote loading progress every 5 minutes
# Stops after 6 hours or when target (30k) is reached

$endTime = (Get-Date).AddHours(6)
$targetQuotes = 30000
$prevTotal = $null
$interval = 300  # 5 minutes

Write-Host "Starting quote monitoring..."
Write-Host "Target: $targetQuotes quotes"
Write-Host "Will stop after: $endTime"
Write-Host "Checking every $interval seconds"
Write-Host "=" * 70

while ((Get-Date) -lt $endTime) {
    # Get current quote count
    $pyScript = @"
from database import SessionLocal
from models import Quote
from collections import Counter
db = SessionLocal()
rows = db.query(Quote.language).all()
db.close()
langs = Counter([r[0] for r in rows])
total = sum(langs.values())
print(f"{total}")
print(f"{dict(langs)}")
"@
    
    $output = python -c $pyScript 2>&1
    $lines = $output -split "`r?`n" | Where-Object { $_.Trim() -ne "" }
    
    if ($lines.Count -ge 2) {
        $total = [int]$lines[0]
        $langs = $lines[1]
        
        $delta = 0
        if ($prevTotal -ne $null) {
            $delta = $total - $prevTotal
        }
        
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        $remaining = $targetQuotes - $total
        
        Write-Host "[$timestamp] Total: $total | Delta: $delta | Remaining: $remaining | Languages: $langs"
        
        # Check if target reached
        if ($total -ge $targetQuotes) {
            Write-Host "=" * 70
            Write-Host "Target reached! Stopping monitoring."
            break
        }
        
        $prevTotal = $total
    } else {
        Write-Host "[$timestamp] Error getting quote count: $output"
    }
    
    Start-Sleep -Seconds $interval
}

Write-Host "=" * 70
Write-Host "Monitoring stopped."

