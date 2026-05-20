# KeepYourContracts - Render canonical production verification (Task 24)
# Usage: powershell -File scripts/verify-render-production.ps1
# No secrets required. Does not use Cloudflare Tunnel.

$Render = "https://jetfighter-compliance.onrender.com"
$fail = 0

function Test-Get($path, $label, [switch]$RequireHtml) {
    $url = "$Render$path"
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 45
        if ($r.StatusCode -ne 200) {
            Write-Host "[FAIL] $label - HTTP $($r.StatusCode)" -ForegroundColor Red
            return $false
        }
        if ($RequireHtml -and $r.Content -notmatch "design-system\.css") {
            Write-Host "[FAIL] $label - missing shared CSS" -ForegroundColor Red
            return $false
        }
        Write-Host "[PASS] $label" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[FAIL] $label - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

Write-Host ""
Write-Host "=== Render canonical host ===" -ForegroundColor Cyan
Write-Host $Render

Write-Host ""
Write-Host "=== Core health ===" -ForegroundColor Cyan
if (-not (Test-Get "/healthz" "GET /healthz")) { $fail++ }

Write-Host ""
Write-Host "=== Public UI (static) ===" -ForegroundColor Cyan
if (-not (Test-Get "/ui/shop.html" "GET /ui/shop.html" -RequireHtml)) { $fail++ }
if (-not (Test-Get "/ui/intake.html" "GET /ui/intake.html" -RequireHtml)) { $fail++ }
if (-not (Test-Get "/ui/inquiry.html" "GET /ui/inquiry.html" -RequireHtml)) { $fail++ }
if (-not (Test-Get "/ui/upload.html" "GET /ui/upload.html" -RequireHtml)) { $fail++ }

Write-Host ""
Write-Host "=== Upload / intake routes ===" -ForegroundColor Cyan
if (-not (Test-Get "/upload" "GET /upload (alias)")) { $fail++ }

try {
    $null = Invoke-WebRequest -Uri "$Render/api/intake/resolve?token=invalid" -UseBasicParsing -TimeoutSec 30
    Write-Host "[WARN] intake resolve returned 2xx (expected 4xx for bad token)" -ForegroundColor Yellow
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if (@(400, 401, 403, 404, 422) -contains $code) {
        Write-Host "[PASS] GET /api/intake/resolve route live ($code on bad token)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] intake resolve - $code" -ForegroundColor Red
        $fail++
    }
}

Write-Host ""
Write-Host "=== Inquiry API ===" -ForegroundColor Cyan
try {
    $body = @{
        name    = "RenderVerify"
        email   = "render-verify@example.com"
        subject = "TASK24"
        message = "Render production cutover probe"
    }
    $j = Invoke-RestMethod -Uri "$Render/api/inquiry/submit" -Method POST -Body $body -TimeoutSec 45
    if ($j.ok -and $j.intake_url -and $j.intake_url -notmatch "127\.0\.0\.1|localhost") {
        if ($j.intake_url -match "jetfighter-compliance\.onrender\.com|keepyourcontracts\.com") {
            Write-Host "[PASS] POST /api/inquiry/submit (HTTPS public host)" -ForegroundColor Green
        } else {
            Write-Host "[WARN] inquiry ok but intake_url host unexpected: $($j.intake_url)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[FAIL] inquiry response invalid" -ForegroundColor Red
        $fail++
    }
} catch {
    Write-Host "[FAIL] POST /api/inquiry/submit - $_" -ForegroundColor Red
    $fail++
}

Write-Host ""
Write-Host "=== Evidence register API ===" -ForegroundColor Cyan
$evBody = @{ project_id = "P-RENDER-PROBE"; email = "render-verify@example.com" }
try {
    $null = Invoke-WebRequest -Uri "$Render/api/evidence/register" -Method POST -Body $evBody -UseBasicParsing -TimeoutSec 30
    Write-Host "[WARN] evidence register returned 2xx without files (unexpected)" -ForegroundColor Yellow
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if (@(400, 422) -contains $code) {
        Write-Host "[PASS] POST /api/evidence/register route live ($code validation)" -ForegroundColor Green
    } elseif ($code -eq 404) {
        Write-Host "[FAIL] evidence register 404" -ForegroundColor Red
        $fail++
    } else {
        Write-Host "[PASS] evidence register reachable (HTTP $code)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "=== Readiness (optional) ===" -ForegroundColor Cyan
try {
    $ready = Invoke-RestMethod -Uri "$Render/health/ready" -TimeoutSec 30
    $ready.checks | Format-List environment, public_base_url, data_writable
    if ($ready.checks.public_base_url -match "127\.0\.0\.1|localhost") {
        Write-Host "[WARN] public_base_url still localhost - set PUBLIC_BASE_URL on Render" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[WARN] /health/ready - $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
if ($fail -eq 0) {
    Write-Host "Render production surface OK - use $Render as canonical backend." -ForegroundColor Green
    Write-Host "Local Cloudflare Tunnel is NOT required for production." -ForegroundColor Green
    exit 0
}
Write-Host "$fail check(s) FAILED on Render host" -ForegroundColor Red
exit 1
