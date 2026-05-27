# LOCAL DEV / EMERGENCY ONLY — not production. Production: GitHub → Render (compliance.keepyourcontracts.com).
# Requires gitignored bin/cloudflared.exe and .cloudflared/ config on a developer machine.

Start-Process -WindowStyle Minimized -FilePath "E:\JetFighter_Compliance\bin\cloudflared.exe" -ArgumentList @("tunnel","--config","E:\JetFighter_Compliance\.cloudflared\config-kyc.yml","run")
