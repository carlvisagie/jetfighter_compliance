$ErrorActionPreference="Stop"; Set-StrictMode -Version Latest
$Root = "E:\JetFighter_Compliance"; if (-not (Test-Path $Root)) { $Root="C:\JetFighter_Compliance" }
$Drive = Get-Volume -FileSystemLabel "KYC_TRANSPORT" -ErrorAction SilentlyContinue
if ($Drive) {
  robocopy (Join-Path $Root "data") (([string]$Drive.DriveLetter)+":\KYC_Transport\_Mirror") /MIR /FFT /R:1 /W:1 /XD tmp cache
}
