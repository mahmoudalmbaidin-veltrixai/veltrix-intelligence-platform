param([string]$ApiRoot = "http://localhost:8000")

$ErrorActionPreference = "Stop"
$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$manifestPath = Join-Path $repositoryRoot "artifacts\demo-stage4\environment-manifest.json"
$evidencePath = Join-Path $repositoryRoot "artifacts\demo-stage4\validation-results.json"
$credentialPath = Join-Path $env:LOCALAPPDATA "Veltrix\VIP\stage4\demo-user-credentials.dpapi"
$platformPath = Join-Path $env:LOCALAPPDATA "Veltrix\VIP\stage4\platform-operator.dpapi"
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json -Depth 80

function Unprotect-Json([string]$Path) {
    $protected=(Get-Content -Raw -LiteralPath $Path).Trim()
    $plain=[System.Net.NetworkCredential]::new("",(ConvertTo-SecureString $protected)).Password
    return $plain | ConvertFrom-Json -Depth 40
}
function New-Session([string]$Username,[string]$Password){
    $session=[Microsoft.PowerShell.Commands.WebRequestSession]::new()
    Invoke-RestMethod -Method Post -Uri "$ApiRoot/auth/login" -WebSession $session -ContentType "application/json" -Body (@{username=$Username;password=$Password}|ConvertTo-Json -Compress) | Out-Null
    return $session
}
function Invoke-Status($Session,[string]$Method,[string]$Path,[string]$OrgId,[string]$WorkspaceId,$Body=$null){
    $headers=@{Origin="http://localhost:3009";"X-Organization-ID"=$OrgId;"X-Workspace-ID"=$WorkspaceId}
    if($Method -notin @("Get","Head","Options")){$headers["X-CSRF-Token"]=$Session.Cookies.GetCookies($ApiRoot)["vip_csrf_token"].Value}
    $args=@{Method=$Method;Uri="$ApiRoot$Path";WebSession=$Session;Headers=$headers;ContentType="application/json";SkipHttpErrorCheck=$true}
    if($null -ne $Body){$args.Body=$Body|ConvertTo-Json -Depth 40 -Compress}
    return (Invoke-WebRequest @args).StatusCode
}
function Platform-Api($Session,[string]$Method,[string]$Path,$Body=$null){
    $headers=@{Origin="http://localhost:3009"}
    if($Method -notin @("Get","Head","Options")){$headers["X-CSRF-Token"]=$Session.Cookies.GetCookies($ApiRoot)["vip_csrf_token"].Value}
    $args=@{Method=$Method;Uri="$ApiRoot$Path";WebSession=$Session;Headers=$headers;ContentType="application/json"}
    if($null -ne $Body){$args.Body=$Body|ConvertTo-Json -Depth 30 -Compress}
    return Invoke-RestMethod @args
}
function Record([string]$Id,[string]$Area,[string]$Scenario,[int]$Expected,[int]$Actual,[string]$Org,[string]$Workspace){
    $script:results.Add([ordered]@{test_id=$Id;organization=$Org;workspace=$Workspace;area=$Area;scenario=$Scenario;expected=$Expected;actual=$Actual;status=if($Expected -eq $Actual){"Passed"}else{"Failed"};verified_at=(Get-Date).ToUniversalTime().ToString("o")})
}

$userSecrets=Unprotect-Json $credentialPath
$platformSecret=Unprotect-Json $platformPath
$platform=New-Session $platformSecret.username $platformSecret.password
$results=[System.Collections.Generic.List[object]]::new()
$temporarilyEnabled=[System.Collections.Generic.List[object]]::new()
try {
    # Temporarily allow test sessions; finally restores the original temporary password and must-change flag.
    foreach($organization in $manifest.organizations){
        foreach($user in $organization.users){
            $found=(Platform-Api $platform Get "/api/v1/platform/users?page=1&page_size=100&search=$($user.username)").items|Where-Object username -eq $user.username|Select-Object -First 1
            Platform-Api $platform Post "/api/v1/platform/users/$($found.id)/reset-password" @{password=$userSecrets.($user.username);must_change_password=$false}|Out-Null
            $temporarilyEnabled.Add(@{id=$found.id;username=$user.username})
        }
    }
    foreach($organization in $manifest.organizations){
        $flagship=$organization.workspaces|Where-Object flagship|Select-Object -First 1
        $support=$organization.workspaces|Where-Object {-not $_.flagship}|Select-Object -First 1
        $orgAdmin=$organization.users|Where-Object organization_role -eq "organization_admin"|Select-Object -First 1
        $editor=$organization.users|Where-Object {$_.access.PSObject.Properties.Value -contains "editor"}|Select-Object -First 1
        $viewer=$organization.users|Where-Object {$_.access.PSObject.Properties.Value -contains "viewer"}|Select-Object -First 1
        $adminSession=New-Session $orgAdmin.username $userSecrets.($orgAdmin.username)
        $editorSession=New-Session $editor.username $userSecrets.($editor.username)
        $viewerSession=New-Session $viewer.username $userSecrets.($viewer.username)
        Record "$($organization.key)-AUTH-ADMIN" "Authentication" "Organization admin authenticates" 200 (Invoke-Status $adminSession Get "/api/v1/tenant-context" $organization.id $flagship.id) $organization.name $flagship.name
        Record "$($organization.key)-PUBLISHED-VIEW" "Dashboard" "Viewer opens published flagship dashboard" 200 (Invoke-Status $viewerSession Get "/api/v1/dashboards/$($flagship.assets.dashboard.id)/viewer" $organization.id $flagship.id) $organization.name $flagship.name
        Record "$($organization.key)-VIEWER-WRITE" "RBAC" "Viewer cannot create pipeline" 403 (Invoke-Status $viewerSession Post "/api/v1/pipelines" $organization.id $flagship.id @{name="Denied";nodes=@();edges=@();canvas=@{};tags=@()}) $organization.name $flagship.name
        Record "$($organization.key)-VIEWER-EXPORT" "RBAC" "Viewer cannot request dashboard export" 403 (Invoke-Status $viewerSession Post "/api/v1/dashboards/$($flagship.assets.dashboard.id)/exports" $organization.id $flagship.id @{format="pdf";filters=@{};locale="en-US";timezone="Asia/Riyadh"}) $organization.name $flagship.name
        Record "$($organization.key)-EDITOR-ADMIN" "RBAC" "Editor cannot administer workspace members" 403 (Invoke-Status $editorSession Get "/api/v1/organizations/$($organization.id)/workspaces/$($flagship.id)/members" $organization.id $flagship.id) $organization.name $flagship.name
        Record "$($organization.key)-WS-TAMPER" "Isolation" "Workspace-scoped user cannot open unauthorized dataset" 404 (Invoke-Status $editorSession Get "/api/v1/datasets/$($support.assets.datasets[0].id)" $organization.id $flagship.id) $organization.name $support.name
        $foreign=$manifest.organizations|Where-Object id -ne $organization.id|Select-Object -First 1
        $foreignWs=$foreign.workspaces|Select-Object -First 1
        Record "$($organization.key)-ORG-TAMPER" "Isolation" "Cross-organization dashboard ID is rejected" 404 (Invoke-Status $adminSession Get "/api/v1/dashboards/$($foreignWs.assets.dashboard.id)/viewer" $organization.id $flagship.id) $organization.name $flagship.name
    }
} finally {
    foreach($item in $temporarilyEnabled){Platform-Api $platform Post "/api/v1/platform/users/$($item.id)/reset-password" @{password=$userSecrets.($item.username);must_change_password=$true}|Out-Null}
}
$databaseChecks=docker exec vip-postgres-1 psql -X -U vip -d vip -At -F '|' -c "SELECT count(*),count(*) FILTER(WHERE password_hash IS NOT NULL),count(*) FILTER(WHERE must_change_password) FROM users WHERE username LIKE 'northstar.%' OR username LIKE 'crestline.%' OR username LIKE 'meridian.%';"
$parts=$databaseChecks.Trim() -split '\|'
$results.Add([ordered]@{test_id="SEC-PASSWORD-HASH";organization="All";workspace="All";area="Credential Security";scenario="All demo passwords are hashed and marked must-change";expected="24|24|24";actual=$databaseChecks.Trim();status=if($databaseChecks.Trim()-eq "24|24|24"){"Passed"}else{"Failed"};verified_at=(Get-Date).ToUniversalTime().ToString("o")})
$summary=[ordered]@{generated_at=(Get-Date).ToUniversalTime().ToString("o");passed=@($results|Where-Object status -eq "Passed").Count;failed=@($results|Where-Object status -eq "Failed").Count;results=$results}
$summary|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $evidencePath -Encoding utf8
$summary|ConvertTo-Json -Depth 6
if($summary.failed -gt 0){exit 1}

