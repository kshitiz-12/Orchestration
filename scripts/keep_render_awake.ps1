# Keep the Render free-tier API awake while you demo / develop.
# Usage:
#   powershell -File scripts/keep_render_awake.ps1
#   powershell -File scripts/keep_render_awake.ps1 -Url https://your-service.onrender.com/health -IntervalSeconds 600

param(
    [string]$Url = "https://orchestration-pqja.onrender.com/health",
    [int]$IntervalSeconds = 600
)

Write-Host "Keeping Render awake: $Url every ${IntervalSeconds}s (Ctrl+C to stop)"
while ($true) {
    $ts = Get-Date -Format "HH:mm:ss"
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 90
        Write-Host "[$ts] OK $($resp.StatusCode) $($resp.Content)"
    }
    catch {
        Write-Host "[$ts] FAIL $($_.Exception.Message)"
    }
    Start-Sleep -Seconds $IntervalSeconds
}
