# 50 hard refreshes — healthz + control.html + key static assets
# Usage: powershell -File scripts/verify-uptime-stability.ps1
# Pass: exit 0. Any 502/non-200 fails.

param(
    [string]$Base = "https://compliance.keepyourcontracts.com",
    [int]$Rounds = 50
)

$paths = @(
    "/healthz",
    "/ui/control.html",
    "/ui/assets/styles/design-system.css",
    "/ui/inquiry.html",
    "/ui/upload.html"
)

$fail = 0
for ($i = 1; $i -le $Rounds; $i++) {
    foreach ($p in $paths) {
        $url = "$Base$p"
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 30
            if ($r.StatusCode -ne 200) {
                Write-Host "[FAIL] round=$i $url HTTP $($r.StatusCode)" -ForegroundColor Red
                $fail++
            }
            if ($p -eq "/healthz" -and $r.Content -notmatch '"safe_mode"\s*:\s*true') {
                Write-Host "[FAIL] round=$i healthz safe_mode not true: $($r.Content)" -ForegroundColor Red
                $fail++
            }
        } catch {
            Write-Host "[FAIL] round=$i $url $($_.Exception.Message)" -ForegroundColor Red
            $fail++
        }
    }
    Start-Sleep -Milliseconds 100
}

if ($fail -eq 0) {
    Write-Host "[PASS] $Rounds rounds x $($paths.Count) paths — all 200" -ForegroundColor Green
    exit 0
}
Write-Host "[FAIL] $fail failures" -ForegroundColor Red
exit 1
