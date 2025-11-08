# Run in elevated PowerShell
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (!(Test-Path "$Root\.venv")) { python -m venv "$Root\.venv" }
$Py = Join-Path $Root ".venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r "$Root\requirements.txt"
if (!(Test-Path "$Root\.env")) { Copy-Item "$Root\.env.example" "$Root\.env" }
Write-Host "Ready. Update .env and run:"
Write-Host "  $Py -m uvicorn server:app --host 127.0.0.1 --port 8080 --reload"
