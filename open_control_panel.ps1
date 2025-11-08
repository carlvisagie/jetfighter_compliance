# Open Control Panel; start server if needed. (PS5-safe)
$ErrorActionPreference='Stop'; Set-StrictMode -Version Latest
$Root = 'E:\JetFighter_Compliance'
if (-not (Test-Path $Root)) { $Root = 'C:\JetFighter_Compliance' }
if (-not (Test-Path $Root)) { throw "Project root not found on E: or C:" }
Set-Location $Root
if (-not (Get-NetTCPConnection -State Listen -LocalPort 8080 -ErrorAction SilentlyContinue)) {
  if (-not (Test-Path ".\.venv")) { python -m venv ".\.venv" }
  $py = ".\.venv\Scripts\python.exe"
  & $py -m pip install --upgrade pip | Out-Null
  & $py -m pip install -r .\requirements.txt | Out-Null
  Start-Process -WindowStyle Minimized $py -ArgumentList "-m","uvicorn","server:app","--host","127.0.0.1","--port","8080","--reload"
  Start-Sleep -Seconds 2
}
Start-Process "http://127.0.0.1:8080/ui/control.html"
