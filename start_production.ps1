# LOCAL DEV ONLY — not the production launch path.
# Production: GitHub → Render (kyc-backend). Customer flow: inquiry.html → intake → project → events.
# Optional Cloudflare Tunnel for temporary public URLs on this machine only.

$ErrorActionPreference = "Stop"
Set-Location "E:\JetFighter_Compliance"

Write-Host "=== JETFIGHTER LOCAL DEV STARTUP (tunnel + uvicorn) ===" -ForegroundColor Cyan

Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 5

if (!(Test-Path "E:\JetFighter_Compliance\.venv\Scripts\python.exe")) { throw "Python missing." }
if (!(Test-Path "E:\JetFighter_Compliance\.cloudflared\tunnel-token.txt")) { throw "Tunnel token missing." }

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "cd E:\JetFighter_Compliance; E:\JetFighter_Compliance\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8080"
)

Write-Host "Waiting for backend..." -ForegroundColor Yellow

$backendOk = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        Invoke-RestMethod "http://127.0.0.1:8080/healthz" | Out-Null
        $backendOk = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $backendOk) {
    throw "Backend failed to become healthy on port 8080."
}

Write-Host "Backend healthy." -ForegroundColor Green

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "`$tok = Get-Content 'E:\JetFighter_Compliance\.cloudflared\tunnel-token.txt' -Raw; `$tok = `$tok.Trim(); & 'E:\JetFighter_Compliance\bin\cloudflared.exe' tunnel run --token `$tok"
)

Write-Host "Waiting for tunnel/public site..." -ForegroundColor Yellow

$publicOk = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        Invoke-WebRequest "https://compliance.keepyourcontracts.com/ui/shop.html" -UseBasicParsing | Out-Null
        Invoke-WebRequest "https://compliance.keepyourcontracts.com/ui/intake.html" -UseBasicParsing | Out-Null
        $publicOk = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $publicOk) {
    throw "Public site failed to become reachable."
}

Write-Host "=== SYSTEM ONLINE ===" -ForegroundColor Green
Start-Process "https://compliance.keepyourcontracts.com/ui/shop.html"
