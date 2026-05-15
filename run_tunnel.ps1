Start-Process -WindowStyle Minimized -FilePath "E:\JetFighter_Compliance\bin\cloudflared.exe" -ArgumentList @("tunnel","--config","E:\JetFighter_Compliance\.cloudflared\config-kyc.yml","run")
