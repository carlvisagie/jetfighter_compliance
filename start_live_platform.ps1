# =============================================================================
# LEGACY STARTUP SCRIPT
# =============================================================================
# This script is DEPRECATED. Use start_production.ps1 instead.
# Canonical startup path: start_production.ps1
# Reason: Duplicate functionality, no health check verification
# =============================================================================

$ErrorActionPreference='Stop'

Write-Host "Starting JetFighter Compliance Platform..." -ForegroundColor Cyan

# Kill old processes
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

Start-Sleep -Seconds 3

# Start backend
Start-Process powershell -ArgumentList '-NoExit','-Command','cd E:\JetFighter_Compliance; .\.venv\Scripts\Activate.ps1; python -m uvicorn server:app --host 127.0.0.1 --port 8080'

Start-Sleep -Seconds 8

# Start tunnel
Start-Process powershell -ArgumentList '-NoExit','-Command','E:\JetFighter_Compliance\bin\cloudflared.exe tunnel --config E:\JetFighter_Compliance\.cloudflared\config-jetfighter.yml run'

Write-Host ""
Write-Host "Platform launch sequence complete." -ForegroundColor Green
Write-Host ""

Start-Sleep -Seconds 5

Start-Process "https://compliance.keepyourcontracts.com/ui/shop.html"
Start-Process "https://compliance.keepyourcontracts.com/ui/intake.html"