# ================================
# Purposeful Coaching Backend Expansion - Stage 1
# Safe Installer
# ================================

$ErrorActionPreference = "Continue"
$LogFile = "install_stage1.log"

Function Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "$timestamp $msg"
    "$timestamp $msg" | Out-File -FilePath $LogFile -Append
}

$repoRoot  = "E:\JetFighter_Compliance"
$backend   = "$repoRoot\backend"
$zipUrl    = "https://example.com/purposeful_backend_stage1.zip"   # real link will go here
$zipFile   = "$env:TEMP\purposeful_backend_stage1.zip"

Log "=== Stage1 Install Started ==="

try {
    Log "Downloading backend expansion..."
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing
} catch {
    Log "Download failed: $_"
}

try {
    Log "Extracting to $backend ..."
    Expand-Archive -Path $zipFile -DestinationPath $backend -Force
} catch {
    Log "Extraction failed: $_"
}

try {
    Log "Running DB migrations..."
    cd $repoRoot
    .\manage.ps1 db upgrade 2>&1 | Tee-Object -FilePath $LogFile -Append
} catch {
    Log "DB migration failed: $_"
}

Log "Stage1 install complete."
Log "You can now run: .\manage.ps1 run"

# Prevent window from closing immediately
Write-Host "Press ENTER to close..."
[void][System.Console]::ReadLine()
