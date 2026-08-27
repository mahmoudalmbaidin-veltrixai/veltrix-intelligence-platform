param([switch]$AcknowledgeSensitiveOutput)

$ErrorActionPreference = "Stop"
if (-not $AcknowledgeSensitiveOutput) {
    throw "Re-run with -AcknowledgeSensitiveOutput only in a private, non-recorded session."
}
$credentialPath = Join-Path $env:LOCALAPPDATA "Veltrix\VIP\demo-credentials.dpapi"
if (-not (Test-Path -LiteralPath $credentialPath)) { throw "Demo credentials have not been prepared." }
$protected = (Get-Content -Raw -LiteralPath $credentialPath).Trim()
$plain = [System.Net.NetworkCredential]::new("", (ConvertTo-SecureString $protected)).Password
$credentials = $plain | ConvertFrom-Json
[pscustomobject]@{ Persona = "Organization Admin"; Username = "demo.organization.admin"; Email = "demo.admin@vip.example"; Password = $credentials.admin }
[pscustomobject]@{ Persona = "Editor"; Username = "demo.sales.editor"; Email = "demo.editor@vip.example"; Password = $credentials.editor }
[pscustomobject]@{ Persona = "Viewer"; Username = "demo.executive.viewer"; Email = "demo.viewer@vip.example"; Password = $credentials.viewer }
