# =============================================================================
# LEGACY STARTUP SCRIPT
# =============================================================================
# This script is DEPRECATED. Use start_production.ps1 instead.
# Canonical startup path: start_production.ps1
# Reason: Duplicate functionality, uses port 8000 (inconsistent with other scripts)
# =============================================================================

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# DEV / EMERGENCY ONLY - production customers use Render (jetfighter-compliance.onrender.com).
# See docs/KYC_RENDER_PRODUCTION_CUTOVER.md

Write-Host "`n=== JetFighter Compliance Full Launch (LOCAL DEV - NOT PRODUCTION) ===`n"

# --- Stop old processes ---
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 1

# --- Start FastAPI Backend ---
Write-Host "Starting FastAPI backend..." -ForegroundColor Cyan
Start-Process -WindowStyle Minimized `
    -WorkingDirectory "E:\JetFighter_Compliance" `
    -FilePath "E:\JetFighter_Compliance\.venv\Scripts\python.exe" `
    -ArgumentList "-m","uvicorn","server:app","--host","127.0.0.1","--port","8000"

Start-Sleep -Seconds 3

# --- Start Cloudflare Tunnel ---
Write-Host "Starting Cloudflare Tunnel (kyc-prod)..." -ForegroundColor Green
Start-Process -WindowStyle Minimized `
    -FilePath "E:\JetFighter_Compliance\bin\cloudflared.exe" `
    -ArgumentList @(
        "tunnel",
        "--config","E:\JetFighter_Compliance\.cloudflared\config-jetfighter.yml",
        "run","kyc-prod"
    )

Start-Sleep -Seconds 3

# --- Open JetFighter Dashboard ---
Write-Host "Opening Control Dashboard..."
Start-Process "http://127.0.0.1:8000/ui/control.html"

Write-Host "`nAll systems online. JetFighter is fully operational.`n"
