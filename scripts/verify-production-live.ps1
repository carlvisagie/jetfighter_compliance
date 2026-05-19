# KeepYourContracts - live production verification (run after Owner env/DNS/Stripe changes)
# Usage: powershell -File scripts/verify-production-live.ps1

$Render = "https://jetfighter-compliance.onrender.com"
$Custom = "https://keepyourcontracts.com"
$fail = 0

function Test-JsonHealth($url, $label) {
    try {
        $r = Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 30
        $ok = $r.Content.TrimStart().StartsWith("{") -and $r.Content -match '"ok"\s*:\s*true'
        if ($ok) { Write-Host "[PASS] $label" -ForegroundColor Green; return $true }
        Write-Host "[FAIL] $label - not JSON ok (CT=$($r.Headers['Content-Type']))" -ForegroundColor Red
        return $false
    } catch {
        Write-Host "[FAIL] $label - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

Write-Host ""
Write-Host "=== Render readiness ===" -ForegroundColor Cyan
try {
    $ready = Invoke-RestMethod "$Render/health/ready" -TimeoutSec 30
    $ready | ConvertTo-Json -Compress | Write-Host
    if ($ready.checks.environment -ne "production") {
        Write-Host "[FAIL] ENVIRONMENT not production (got $($ready.checks.environment))" -ForegroundColor Red
        $fail++
    } else { Write-Host "[PASS] ENVIRONMENT=production" -ForegroundColor Green }
    if (-not $ready.checks.stripe_webhook_configured) {
        Write-Host "[FAIL] STRIPE_WEBHOOK_SECRET not configured" -ForegroundColor Red
        $fail++
    } else { Write-Host "[PASS] Stripe webhook secret set" -ForegroundColor Green }
    if (-not $ready.checks.intake_secret_configured) {
        Write-Host "[FAIL] INTAKE_TOKEN_SECRET still default" -ForegroundColor Red
        $fail++
    } else { Write-Host "[PASS] Intake secret configured" -ForegroundColor Green }
} catch {
    Write-Host "[FAIL] /health/ready - $_" -ForegroundColor Red
    $fail++
}

Write-Host ""
Write-Host "=== Stripe route ===" -ForegroundColor Cyan
try {
    Invoke-WebRequest "$Render/webhooks/stripe" -Method POST -Body "{}" -ContentType "application/json" -UseBasicParsing -TimeoutSec 20 | Out-Null
    Write-Host "[FAIL] Stripe unsigned POST should not return 2xx" -ForegroundColor Red
    $fail++
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 401) { Write-Host "[PASS] Stripe route rejects unsigned (401)" -ForegroundColor Green }
    elseif ($code -eq 503) { Write-Host "[FAIL] STRIPE_WEBHOOK_SECRET still missing (503)" -ForegroundColor Red; $fail++ }
    else { Write-Host "[WARN] Stripe returned $code" -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "=== Ops guard (production) ===" -ForegroundColor Cyan
try {
    Invoke-WebRequest "$Render/events/payment/test" -Method POST -Body '{"order_id":"x","email":"x@y.com","name":"X","skus":["T"]}' -ContentType "application/json" -UseBasicParsing | Out-Null
    Write-Host "[FAIL] payment/test allowed without X-Ops-Key in production" -ForegroundColor Red
    $fail++
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 403) {
        Write-Host "[PASS] payment/test blocked without ops key (403)" -ForegroundColor Green
    } else {
        Write-Host "[WARN] payment/test returned $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=== Custom domain ===" -ForegroundColor Cyan
if (-not (Test-JsonHealth "$Custom/healthz" "keepyourcontracts.com /healthz")) { $fail++ }
try {
    $r = Invoke-WebRequest "$Custom/ui/shop.html" -UseBasicParsing -TimeoutSec 25
    if ($r.StatusCode -eq 200) { Write-Host "[PASS] /ui/shop.html" -ForegroundColor Green }
} catch {
    Write-Host "[FAIL] /ui/shop.html - $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
    $fail++
}

Write-Host ""
Write-Host "=== Inquiry on Render (smoke) ===" -ForegroundColor Cyan
try {
    $fd = @{ name = "Verify"; email = "verify@example.com"; subject = "VERIFY"; message = "probe" }
    $j = Invoke-RestMethod "$Render/api/inquiry/submit" -Method POST -Body $fd -TimeoutSec 40
    if ($j.ok -and $j.intake_url -notmatch "127\.0\.0\.1|localhost") {
        Write-Host "[PASS] inquiry + HTTPS intake_url" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] inquiry response bad" -ForegroundColor Red
        $fail++
    }
} catch {
    Write-Host "[FAIL] inquiry - $_" -ForegroundColor Red
    $fail++
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
if ($fail -eq 0) { Write-Host "ALL CHECKS PASSED - eligible for STABILIZED OPERATIONS MODE" -ForegroundColor Green; exit 0 }
Write-Host "$fail check group(s) FAILED - complete Owner activation checklist" -ForegroundColor Red
exit 1
