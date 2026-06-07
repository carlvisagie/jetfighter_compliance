# Founding Pilot intake pipeline soak verification
# Usage: powershell -File scripts/verify_founding_pilot_pipeline.ps1 [-BaseUrl URL] [-OpsPassword PASS]

param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$OpsPassword = $env:OPS_PASSWORD
)

$fail = 0

function Fail([string]$msg) {
    Write-Host "[FAIL] $msg" -ForegroundColor Red
    $script:fail++
}

function Pass([string]$msg) {
    Write-Host "[PASS] $msg" -ForegroundColor Green
}

if (-not $OpsPassword) {
    Fail "OPS_PASSWORD not set — required for operator endpoints"
    exit 1
}

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
try {
    $login = Invoke-RestMethod "$BaseUrl/api/ops/login" -Method POST -ContentType "application/json" `
        -Body (@{ password = $OpsPassword } | ConvertTo-Json) -WebSession $session -TimeoutSec 30
    if (-not $login.ok) { Fail "ops login failed"; exit 1 }
    Pass "ops login"
} catch {
    Fail "ops login — $($_.Exception.Message)"
    exit 1
}

function Upload-Files([string[]]$names, [hashtable]$extra) {
    $boundary = [System.Guid]::NewGuid().ToString()
    $LF = "`r`n"
    $body = New-Object System.IO.MemoryStream
    $enc = [System.Text.Encoding]::UTF8
    foreach ($kv in $extra.GetEnumerator()) {
        $body.Write($enc.GetBytes("--$boundary$LF"), 0, $enc.GetByteCount("--$boundary$LF"))
        $body.Write($enc.GetBytes("Content-Disposition: form-data; name=`"$($kv.Key)`"$LF$LF"), 0, $enc.GetByteCount("Content-Disposition: form-data; name=`"$($kv.Key)`"$LF$LF"))
        $body.Write($enc.GetBytes("$($kv.Value)$LF"), 0, $enc.GetByteCount("$($kv.Value)$LF"))
    }
    foreach ($n in $names) {
        $bytes = [System.Text.Encoding]::ASCII.GetBytes("%PDF-1.4 verify")
        $body.Write($enc.GetBytes("--$boundary$LF"), 0, $enc.GetByteCount("--$boundary$LF"))
        $body.Write($enc.GetBytes("Content-Disposition: form-data; name=`"files`"; filename=`"$n`"$LF"), 0, $enc.GetByteCount("Content-Disposition: form-data; name=`"files`"; filename=`"$n`"$LF"))
        $body.Write($enc.GetBytes("Content-Type: application/pdf$LF$LF"), 0, $enc.GetByteCount("Content-Type: application/pdf$LF$LF"))
        $body.Write($bytes, 0, $bytes.Length)
        $body.Write($enc.GetBytes($LF), 0, $enc.GetByteCount($LF))
    }
    $body.Write($enc.GetBytes("--$boundary--$LF"), 0, $enc.GetByteCount("--$boundary--$LF"))
    $resp = Invoke-WebRequest "$BaseUrl/api/founding-pilot/upload" -Method POST -WebSession $session `
        -ContentType "multipart/form-data; boundary=$boundary" -Body $body.ToArray() -TimeoutSec 120
    return ($resp.Content | ConvertFrom-Json)
}

Write-Host "`n=== 1-file upload ===" -ForegroundColor Cyan
try {
    $one = Upload-Files @("soak1.pdf") @{ email = "soak@example.com"; expected_file_count = "1" }
    if ($one.verified_file_count -eq 1 -and $one.customer_may_show_success) { Pass "1-file verified" } else { Fail "1-file counts/success" }
    $global:SoakIntakeId = $one.intake_id
} catch { Fail "1-file upload — $($_.Exception.Message)" }

Write-Host "`n=== 10-file upload ===" -ForegroundColor Cyan
try {
    $tenNames = 0..9 | ForEach-Object { "soak10_$_.pdf" }
    $ten = Upload-Files $tenNames @{
        email = "soak10@example.com"
        expected_file_count = "10"
        expected_file_names = ($tenNames | ConvertTo-Json -Compress)
    }
    if ($ten.verified_file_count -eq 10) { Pass "10-file verified" } else { Fail "10-file verified count $($ten.verified_file_count)" }
} catch { Fail "10-file upload — $($_.Exception.Message)" }

Write-Host "`n=== Multi-batch 30 files ===" -ForegroundColor Cyan
try {
    $all = 0..29 | ForEach-Object { "soak30_$_.pdf" }
    $b1 = Upload-Files ($all[0..14]) @{
        email = "soak30@example.com"
        expected_file_count = "30"
        expected_file_names = ($all | ConvertTo-Json -Compress)
        upload_manifest = (@{ client_selected_count = 30; batch_complete = $false } | ConvertTo-Json -Compress)
    }
    if ($b1.custody_status -ne "partial_upload") { Fail "batch1 should be partial_upload" }
    else { Pass "batch1 partial_upload" }
    $b2 = Upload-Files ($all[15..29]) @{
        intake_id = $b1.intake_id
        token = $b1.token
        expected_file_count = "30"
        expected_file_names = ($all | ConvertTo-Json -Compress)
        upload_manifest = (@{ client_selected_count = 30; batch_complete = $true } | ConvertTo-Json -Compress)
    }
    if ($b2.verified_file_count -eq 30 -and $b2.customer_may_show_success) { Pass "multi-batch 30 verified" }
    else { Fail "multi-batch final counts" }
} catch { Fail "multi-batch — $($_.Exception.Message)" }

Write-Host "`n=== Operator surfaces ===" -ForegroundColor Cyan
$iid = $global:SoakIntakeId
foreach ($path in @(
        "/api/operator/founding-pilot/queue",
        "/api/operator/founding-pilot/diagnostics",
        "/api/operator/founding-pilot/reconcile",
        "/api/operator/founding-pilot/retention-check/$iid",
        "/api/operator/founding-pilot/intake/$iid/audit"
    )) {
    try {
        $r = Invoke-RestMethod "$BaseUrl$path" -WebSession $session -TimeoutSec 60
        if ($null -eq $r) { Fail "$path empty" } else { Pass $path }
    } catch {
        Fail "$path — $($_.Exception.Message)"
    }
}

try {
    $rc = Invoke-RestMethod "$BaseUrl/api/operator/founding-pilot/retention-check/$iid" -WebSession $session
    if ($rc.counts_match -and $rc.file_hashes_match) { Pass "retention-check counts_match" }
    else { Fail "retention-check mismatch on soak intake" }
} catch {
    Fail "retention-check verify — $($_.Exception.Message)"
}

Write-Host ""
if ($fail -gt 0) {
    Write-Host "PIPELINE VERIFY FAILED ($fail checks)" -ForegroundColor Red
    exit 1
}
Write-Host "PIPELINE VERIFY PASSED" -ForegroundColor Green
exit 0
