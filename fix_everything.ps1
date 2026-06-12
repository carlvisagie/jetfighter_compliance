# =============================================================================
# LEGACY STARTUP SCRIPT
# =============================================================================
# This script is DEPRECATED. Use start_production.ps1 instead.
# Canonical startup path: start_production.ps1
# Reason: Duplicate functionality
# =============================================================================

$ErrorActionPreference='Stop'; Set-StrictMode -Version Latest
$Root = 'E:\JetFighter_Compliance'
if (-not (Test-Path $Root)) { throw "Project root missing: $Root" }
Set-Location $Root
$Py  = Join-Path $Root '.venv\Scripts\python.exe'
$Cf  = Join-Path $Root 'bin\cloudflared.exe'
$Cfg = Join-Path $env:USERPROFILE '.cloudflared\config-jetfighter.yml'

Get-Process | Where-Object { $\_.Name -match 'python|uvicorn|cloudflared' } | Stop-Process -Force -ErrorAction SilentlyContinue
if (-not (Test-Path $Py)) { python -m venv (Join-Path $Root '.venv') }
& $Py -m pip install --upgrade pip | Out-Null
if (Test-Path (Join-Path $Root 'requirements.txt')) { & $Py -m pip install -r (Join-Path $Root 'requirements.txt') | Out-Null }
Start-Process -WindowStyle Minimized -FilePath $Py -ArgumentList @('-m','uvicorn','server:app','--host','127.0.0.1','--port','8080','--reload')
Start-Sleep -Seconds 2
if ( (Test-Path $Cf) -and (Test-Path $Cfg) ) {
  Start-Process -WindowStyle Minimized -FilePath $Cf -ArgumentList @('tunnel','--config',""E:\JetFighter_Compliance\.cloudflared\config-jetfighter.yml"",'run','jetfighter-compliance')
}
Start-Process 'http://127.0.0.1:8080/ui/control.html'
Write-Host "Fix complete  server, tunnel, and Control Panel opened."
