param(
  [string]$Domain = "keepyourcontracts.com",
  [switch]$RestoreAutomatic # use -RestoreAutomatic to revert adapters to DHCP DNS
)

function Write-Info($msg) { Write-Host "[INFO ] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[ OK  ] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN ] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR  ] $msg" -ForegroundColor Red }

# Paths
$RootOut = "C:\Users\Carl\JetFighter_Automation\diagnostics"
$null = New-Item -ItemType Directory -Force -Path $RootOut | Out-Null
$Stamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$ReportMd = Join-Path $RootOut "DNS_Report_$($Domain)_$Stamp.md"

# DNS sets
$PublicResolvers = @("1.1.1.1","1.0.0.1","8.8.8.8","9.9.9.9")
# Minimal record set we care about (edit if you add providers)
$Queries = @(
  @{ Name=$Domain;                    Type="NS"    ; Label="Zone NS (who is authoritative?)" },
  @{ Name=$Domain;                    Type="A"     ; Label="Root A/ALIAS (@)" },
  @{ Name="www.$Domain";             Type="CNAME" ; Label="www CNAME" },
  @{ Name=$Domain;                    Type="MX"    ; Label="Mail MX" },
  @{ Name=$Domain;                    Type="TXT"   ; Label="SPF/Other TXT at root" },
  @{ Name="_dmarc.$Domain";          Type="TXT"   ; Label="DMARC" },
  @{ Name="s1._domainkey.$Domain";   Type="CNAME" ; Label="DKIM selector s1 (e.g., SendGrid/ESP)" },
  @{ Name="s2._domainkey.$Domain";   Type="CNAME" ; Label="DKIM selector s2 (optional)" }
)

# === Restore mode ===
if ($RestoreAutomatic) {
  Write-Info "Restoring all UP adapters to Automatic (DHCP) DNS…"
  Get-DnsClient | Where-Object { $_.InterfaceOperationalStatus -eq "Up" } | ForEach-Object {
    try {
      Set-DnsClientServerAddress -InterfaceIndex $_.InterfaceIndex -ResetServerAddresses -ErrorAction Stop
      Write-Ok "Adapter [$($_.InterfaceAlias)] reset to Automatic."
    } catch { Write-Err "Failed on [$($_.InterfaceAlias)]: $($_.Exception.Message)" }
  }
  Write-Info "Done."
  exit 0
}

# 1) Force resolvers on all UP adapters
Write-Info "Setting DNS servers to 1.1.1.1, 1.0.0.1, 8.8.8.8 for all UP adapters…"
Get-DnsClient | Where-Object { $_.InterfaceOperationalStatus -eq "Up" } | ForEach-Object {
  try {
    Set-DnsClientServerAddress -InterfaceIndex $_.InterfaceIndex -ServerAddresses $PublicResolvers -ErrorAction Stop
    Write-Ok "Adapter [$($_.InterfaceAlias)] now using: $($PublicResolvers -join ', ')"
  } catch { Write-Err "Adapter [$($_.InterfaceAlias)] error: $($_.Exception.Message)" }
}

# 2) Flush caches thoroughly
Write-Info "Flushing DNS caches…"
ipconfig /flushdns | Out-Null
try { Clear-DnsClientCache | Out-Null } catch {}
Write-Ok "Local DNS cache cleared."

# 3) Discover authoritative nameservers from multiple public resolvers
function Get-AuthoritativeNS($domain, $servers) {
  $ns = New-Object System.Collections.Generic.List[string]
  foreach ($s in $servers) {
    try {
      $r = Resolve-DnsName -Name $domain -Type NS -Server $s -ErrorAction Stop
      $r | Where-Object { $_.QueryType -eq "NS" } | ForEach-Object {
        $ns.Add($_.NameHost.TrimEnd('.'))
      }
    } catch {}
  }
  return ($ns | Sort-Object -Unique)
}
$AuthNS = Get-AuthoritativeNS -domain $Domain -servers $PublicResolvers
if ($AuthNS.Count -eq 0) {
  Write-Warn "Could not discover authoritative NS from public resolvers."
} else {
  Write-Ok ("Authoritative NS (discovered): " + ($AuthNS -join ", "))
}

# Helper to run one query against many servers
function Query-AllServers([string]$name, [string]$type, [string[]]$servers) {
  $out = @()
  foreach ($srv in $servers) {
    $entry = [ordered]@{ Server=$srv; Answer=$null; Status="NOANSWER/ERROR" }
    try {
      $ans = Resolve-DnsName -Name $name -Type $type -Server $srv -ErrorAction Stop
      if ($ans) {
        $entry.Status = "OK"
        $entry.Answer = ($ans | ForEach-Object {
          if ($_.Type -eq "CNAME") { $_.CanonicalName }
          elseif ($_.Type -eq "TXT") { ($_.Strings -join "") }
          elseif ($_.Type -eq "MX")  { "$($_.Preference) $($_.NameExchange)" }
          elseif ($_.Type -eq "NS")  { $_.NameHost }
          elseif ($_.Type -eq "A")   { $_.IPAddress }
          else { "$($_.Type) $($_.NameHost)$($_.IPAddress)$($_.Strings)" }
        }) -join " | "
      }
    } catch {
      $entry.Status = "ERROR: " + $_.Exception.Message
    }
    $out += [pscustomobject]$entry
  }
  return ,$out
}

# Servers to test: public + (if found) authoritative
$ServersToTest = @()
$ServersToTest += $PublicResolvers
if ($AuthNS.Count -gt 0) { $ServersToTest += $AuthNS }

# Build report
$lines = @()
$lines += "# DNS Audit Report for $Domain"
$lines += ""
$lines += "*Generated:* $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")"
$lines += "*Tested Resolvers:* $($ServersToTest -join ', ')"
$lines += ""
$lines += "## Findings"
$overallProblems = 0

foreach ($q in $Queries) {
  $lines += "### $($q.Label) — **$($q.Name)** ($($q.Type))"
  $rows = Query-AllServers -name $q.Name -type $q.Type -servers $ServersToTest

  $table = @("| Server | Status | Answer |","|---|---|---|")
  $rowProblems = 0
  foreach ($r in $rows) {
    # Track problems for summary
    if ($r.Status -ne "OK") { $rowProblems++ }

    # Compute answer string without using the ternary operator
    $answerString = if ([string]::IsNullOrWhiteSpace($r.Answer)) { "-" } else { $r.Answer }

    # Append the formatted row
    $table += "| $($r.Server) | $($r.Status) | $answerString |"
  }

  # If any problems were detected in this query, increment overall problems counter
  if ($rowProblems -gt 0) { $overallProblems++ }

  $lines += $table
  $lines += ""
}

# Summary + Quick guidance
$lines += "## Summary"
if ($overallProblems -eq 0) {
  $lines += "- ✅ All tested records resolved consistently across public and authoritative servers."
} else {
  $lines += "- ❌ Inconsistencies or errors detected. Focus on rows with `NOANSWER/ERROR` or differing answers between Public vs Authoritative."
}
$lines += ""
$lines += "## Quick Guidance"
$lines += "- **Use exactly one DNS mode at Namecheap:** either *Namecheap Basic/PremiumDNS* **or** *Custom DNS (Cloudflare nameservers)*. Do **not** mix."
$lines += "- If you stay on Namecheap DNS and you need a Cloudflare Tunnel hostname (e.g., `app.$Domain`), create a `CNAME` like `app -> <your-tunnel-uuid>.cfargotunnel.com`."
$lines += "- For Shopify root, point `@` to Shopify’s A/ALIAS per Shopify’s panel; `www -> shops.myshopify.com` (CNAME)."
$lines += "- For email, ensure MX, SPF (`v=spf1 ... ~all`), DKIM selectors (e.g., `s1._domainkey` CNAMED to your ESP), and DMARC (`_dmarc` TXT) all exist **in the same zone**."

$lines -join "`r`n" | Out-File -FilePath $ReportMd -Encoding UTF8
Write-Ok "Report written to: $ReportMd"

Write-Info "Done. If you want to revert adapters to Automatic DNS later, run:"
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" -RestoreAutomatic" -ForegroundColor White
