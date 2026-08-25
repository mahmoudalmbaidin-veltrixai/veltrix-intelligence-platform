param([string]$ApiRoot = "http://localhost:8000")

$ErrorActionPreference = "Stop"
$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$manifestPath = Join-Path $repositoryRoot "artifacts\demo-stage4\environment-manifest.json"
$credentialPath = Join-Path $env:LOCALAPPDATA "Veltrix\VIP\stage4\demo-user-credentials.dpapi"
$platformPath = Join-Path $env:LOCALAPPDATA "Veltrix\VIP\stage4\platform-operator.dpapi"

function Unprotect-Json([string]$Path) {
    $protected = (Get-Content -Raw -LiteralPath $Path).Trim()
    $plain = [System.Net.NetworkCredential]::new("", (ConvertTo-SecureString $protected)).Password
    return $plain | ConvertFrom-Json -Depth 40
}

function New-Session([string]$Username, [string]$Password) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    Invoke-RestMethod -Method Post -Uri "$ApiRoot/auth/login" -WebSession $session -ContentType "application/json" -Body (@{ username=$Username; password=$Password } | ConvertTo-Json -Compress) | Out-Null
    return $session
}

function Platform-Api($Session, [string]$Method, [string]$Path, $Body=$null) {
    $headers = @{ Origin="http://localhost:3009" }
    if ($Method -notin @("Get", "Head", "Options")) { $headers["X-CSRF-Token"]=$Session.Cookies.GetCookies($ApiRoot)["vip_csrf_token"].Value }
    $arguments = @{ Method=$Method; Uri="$ApiRoot$Path"; WebSession=$Session; Headers=$headers; ContentType="application/json" }
    if ($null -ne $Body) { $arguments.Body=$Body | ConvertTo-Json -Depth 20 -Compress }
    return Invoke-RestMethod @arguments
}

$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json -Depth 100
$secrets = Unprotect-Json $credentialPath
$platformSecret = Unprotect-Json $platformPath
$organization = $manifest.organizations | Where-Object key -eq "northstar" | Select-Object -First 1
$workspace = $organization.workspaces | Where-Object flagship | Select-Object -First 1
$foreignOrganization = $manifest.organizations | Where-Object key -eq "crestline" | Select-Object -First 1
$foreignWorkspace = $foreignOrganization.workspaces | Where-Object flagship | Select-Object -First 1
$admin = $organization.users | Where-Object username -eq "northstar.org.admin" | Select-Object -First 1
$viewer = $organization.users | Where-Object username -eq "northstar.commercial.viewer" | Select-Object -First 1
$platform = New-Session $platformSecret.username $platformSecret.password
$enabledUsers = [System.Collections.Generic.List[object]]::new()

try {
    foreach ($user in @($admin, $viewer)) {
        $found = (Platform-Api $platform Get "/api/v1/platform/users?page=1&page_size=100&search=$($user.username)").items | Where-Object username -eq $user.username | Select-Object -First 1
        Platform-Api $platform Post "/api/v1/platform/users/$($found.id)/reset-password" @{ password=$secrets.($user.username); must_change_password=$false } | Out-Null
        $enabledUsers.Add(@{ id=$found.id; username=$user.username })
    }

    $env:PLAYWRIGHT_REUSE_SERVER = "1"
    $env:VIP_STAGE4_ADMIN_USERNAME = $admin.username
    $env:VIP_STAGE4_ADMIN_PASSWORD = $secrets.($admin.username)
    $env:VIP_STAGE4_VIEWER_USERNAME = $viewer.username
    $env:VIP_STAGE4_VIEWER_PASSWORD = $secrets.($viewer.username)
    $env:VIP_STAGE4_ORGANIZATION_NAME = $organization.name
    $env:VIP_STAGE4_WORKSPACE_NAME = $workspace.name
    $env:VIP_STAGE4_CONNECTION_ID = $workspace.assets.connection.id
    $env:VIP_STAGE4_CONNECTION_NAME = $workspace.assets.connection.name
    $env:VIP_STAGE4_RAW_DATASET_ID = ($workspace.assets.datasets | Where-Object kind -eq "raw").id
    $env:VIP_STAGE4_RAW_DATASET_NAME = ($workspace.assets.datasets | Where-Object kind -eq "raw").name
    $env:VIP_STAGE4_PIPELINE_ID = $workspace.assets.pipeline.id
    $env:VIP_STAGE4_PIPELINE_NAME = $workspace.assets.pipeline.name
    $env:VIP_STAGE4_SEMANTIC_ID = $workspace.assets.semantic_model.id
    $env:VIP_STAGE4_SEMANTIC_NAME = $workspace.assets.semantic_model.name
    $env:VIP_STAGE4_DASHBOARD_ID = $workspace.assets.dashboard.id
    $env:VIP_STAGE4_DASHBOARD_NAME = $workspace.assets.dashboard.name
    $env:VIP_STAGE4_FOREIGN_DASHBOARD_ID = $foreignWorkspace.assets.dashboard.id

    & node .\node_modules\@playwright\test\cli.js test tests/e2e/stage4-enterprise-demo.spec.ts --project=chrome-desktop --project=firefox-desktop --project=webkit-desktop
    if ($LASTEXITCODE -ne 0) { throw "Cross-browser demo certification failed." }
} finally {
    foreach ($user in $enabledUsers) {
        Platform-Api $platform Post "/api/v1/platform/users/$($user.id)/reset-password" @{ password=$secrets.($user.username); must_change_password=$true } | Out-Null
    }
    Remove-Item Env:VIP_STAGE4_ADMIN_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:VIP_STAGE4_VIEWER_PASSWORD -ErrorAction SilentlyContinue
}
