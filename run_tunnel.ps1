$ErrorActionPreference='Stop'; Set-StrictMode -Version Latest
Start-Process -WindowStyle Minimized -FilePath 'E:\JetFighter_Compliance\bin\cloudflared.exe' -ArgumentList @('tunnel','--config',""C:\Users\Carl\.cloudflared\config-jetfighter.yml"",'run','jetfighter-compliance')
