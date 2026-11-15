<#
Applies a Sigma workbook YAML spec to an existing workbook (PUT /v2/workbooks/{workbookId}/spec).
WARNING: this REPLACES THE WHOLE WORKBOOK (all pages). For multi-page workbooks use sigma_cli.py push,
which adds/replaces only the report's page(s) and keeps the others.
Windows PowerShell 5.1+ / PowerShell 7. No modules required.

Security (each user uses THEIR OWN Sigma API client):
  - Client ID and Secret are typed at hidden prompts; they stay in memory only and are never printed or saved.
  - Credentials are only sent over HTTPS to *.sigmacomputing.com (BaseUrl is validated).
  - The YAML on disk is not changed: the connectionId is substituted in memory.

Usage:
  powershell -ExecutionPolicy Bypass -File .\push_to_sigma.ps1 -BaseUrl https://api.us.azure.sigmacomputing.com -YamlPath .\page.yaml
  (add -ConnectionId <uuid> -WorkbookId <uuid> to skip the listings)
#>
param(
    [Parameter(Mandatory = $true)][string]$BaseUrl,
    [Parameter(Mandatory = $true)][string]$YamlPath,
    [string]$ConnectionId,
    [string]$WorkbookId,
    [string]$LogPath
)
$ErrorActionPreference = "Stop"
$placeholder = "REPLACE_WITH_SIGMA_CONNECTION_ID"

$uri = [uri]$BaseUrl.TrimEnd('/')
if ($uri.Scheme -ne "https" -or -not $uri.Host.EndsWith(".sigmacomputing.com")) {
    throw "BaseUrl must be https://<host>.sigmacomputing.com (credentials are only sent to Sigma)."
}
$base = "https://$($uri.Host)"
if (-not (Test-Path $YamlPath)) { throw "File not found: $YamlPath" }
$YamlPath = (Resolve-Path $YamlPath).Path

function Read-Hidden([string]$prompt) {
    $s = Read-Host $prompt -AsSecureString
    $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}

$clientId = Read-Hidden "Sigma Client ID (hidden)"
$secret = Read-Hidden "Sigma Client Secret (hidden)"
try {
    $body = "grant_type=client_credentials&client_id=$([uri]::EscapeDataString($clientId))&client_secret=$([uri]::EscapeDataString($secret))"
    $token = (Invoke-RestMethod -Method Post -Uri "$base/v2/auth/token" -ContentType "application/x-www-form-urlencoded" -Body $body).access_token
} catch {
    throw "Authentication failed on $base. Check your own Client ID/Secret and the BaseUrl of your Sigma org."
} finally {
    $clientId = $null; $secret = $null; $body = $null
}
Write-Host "Authenticated on $base"
$h = @{ Authorization = "Bearer $token" }

$text = Get-Content $YamlPath -Raw -Encoding UTF8
if ($text.Contains($placeholder) -and -not $ConnectionId) {
    (Invoke-RestMethod -Uri "$base/v2/connections?limit=500" -Headers $h).entries | Select-Object connectionId, name, type | Format-Table -AutoSize
    $ConnectionId = Read-Host "connectionId to replace $placeholder"
}
if (-not $WorkbookId) {
    (Invoke-RestMethod -Uri "$base/v2/workbooks?limit=500" -Headers $h).entries | Select-Object workbookId, name, path | Format-Table -AutoSize
    Write-Host "Tip: create and save an EMPTY workbook in Sigma first; the target is fully overwritten."
    $WorkbookId = Read-Host "workbookId of the target workbook (it will be OVERWRITTEN)"
}
$wbName = (Invoke-RestMethod -Uri "$base/v2/workbooks/$WorkbookId" -Headers $h).name
$ok = Read-Host "Overwrite workbook '$wbName' with $(Split-Path $YamlPath -Leaf)? [y/N]"
if ($ok -notin @("y", "yes")) { Write-Host "Cancelled."; exit 0 }

while ($true) {
    $text = Get-Content $YamlPath -Raw -Encoding UTF8          # re-read: fix the YAML between attempts
    if ($ConnectionId) { $text = $text.Replace($placeholder, $ConnectionId) }
    $bytes = [Text.Encoding]::UTF8.GetBytes($text)
    try {
        Invoke-RestMethod -Method Put -Uri "$base/v2/workbooks/$WorkbookId/spec" -Headers $h -ContentType "application/yaml" -Body $bytes | Out-Null
        if ($LogPath) { "OK $(Get-Date -Format s)" | Set-Content $LogPath -Encoding utf8 }
        Write-Host "OK: spec applied to '$wbName'. Reload the workbook in Sigma." -ForegroundColor Green
        break
    } catch {
        $msg = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
        if ($LogPath) { "ERROR $(Get-Date -Format s)`n$msg" | Set-Content $LogPath -Encoding utf8 }   # Sigma response only
        Write-Host "Sigma rejected the spec (nothing was changed):" -ForegroundColor Red
        Write-Host $msg
    }
    if ((Read-Host "Fix the YAML and press Enter to resend (q to quit)") -eq "q") { break }
}
$token = $null
