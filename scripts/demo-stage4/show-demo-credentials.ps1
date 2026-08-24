param([switch]$AcknowledgeSensitiveOutput)

$ErrorActionPreference = "Stop"
if (-not $AcknowledgeSensitiveOutput) {
    throw "Re-run with -AcknowledgeSensitiveOutput only in a private, non-recorded session."
}
$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$configuration = Get-Content -Raw -LiteralPath (Join-Path $repositoryRoot "demo-data\stage4\scenarios.json") | ConvertFrom-Json -Depth 60
$credentialPath = Join-Path $env:LOCALAPPDATA "Veltrix\VIP\stage4\demo-user-credentials.dpapi"
if (-not (Test-Path -LiteralPath $credentialPath)) { throw "Stage 4 credentials do not exist." }
$protected = (Get-Content -Raw -LiteralPath $credentialPath).Trim()
$plain = [System.Net.NetworkCredential]::new("", (ConvertTo-SecureString $protected)).Password
$credentials = $plain | ConvertFrom-Json -Depth 30
foreach ($organization in $configuration.organizations) {
    foreach ($user in $organization.users) {
        [pscustomobject]@{
            Organization = $organization.name
            FullName = $user.displayName
            Username = $user.username
            Email = $user.email
            Password = $credentials.($user.username)
            MustChangePassword = $true
        }
    }
}

