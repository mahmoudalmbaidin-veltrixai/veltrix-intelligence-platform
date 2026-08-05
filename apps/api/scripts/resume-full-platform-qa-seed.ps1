param(
    [string]$ApiRoot = "http://localhost:8000",
    [string]$ArtifactRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")) "artifacts\qa\full-platform"
}
New-Item -ItemType Directory -Force -Path $ArtifactRoot | Out-Null

function New-QaPassword {
    $bytes = New-Object byte[] 24
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) }
    finally { $generator.Dispose() }
    return ([Convert]::ToBase64String($bytes) + "!9Qa")
}

$script:Session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
function Invoke-VipApi {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Path,
        [object]$Body = $null,
        [string]$OrganizationId = "",
        [string]$WorkspaceId = ""
    )
    $headers = @{ Origin = "http://localhost:3009" }
    if ($OrganizationId) { $headers["X-Organization-ID"] = $OrganizationId }
    if ($WorkspaceId) { $headers["X-Workspace-ID"] = $WorkspaceId }
    if ($Method -notin @("Get", "Head", "Options")) {
        $headers["X-CSRF-Token"] = $script:Session.Cookies.GetCookies($ApiRoot)["vip_csrf_token"].Value
    }
    $arguments = @{ Method = $Method; Uri = "$ApiRoot$Path"; WebSession = $script:Session; Headers = $headers; ContentType = "application/json" }
    if ($null -ne $Body) { $arguments.Body = $Body | ConvertTo-Json -Depth 20 -Compress }
    return Invoke-RestMethod @arguments
}

$qaUserCount = docker exec vip-postgres-1 psql -U vip -d vip -Atc "SELECT count(*) FROM users WHERE username LIKE 'qa\_%';"
$qaOrgCount = docker exec vip-postgres-1 psql -U vip -d vip -Atc "SELECT count(*) FROM organizations WHERE slug IN ('qa-enterprise-a-20260804','qa-enterprise-b-20260804');"
if ($qaUserCount -ne "38" -or $qaOrgCount -ne "2") {
    throw "Resume refused: expected exactly 38 QA users and 2 QA organizations, found $qaUserCount and $qaOrgCount."
}

$adminUsername = "qa_platform_super_admin"
$adminPassword = New-QaPassword
$env:DATABASE_URL = "postgresql+asyncpg://vip:vip_local_dev_only@localhost:5432/vip"
$env:REDIS_URL = "redis://localhost:6379/0"
$adminPassword | & (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe") (Join-Path $PSScriptRoot "reset-qa-bootstrap-password.py") --username $adminUsername | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to recover the QA platform administrator." }

$loginBody = @{ username = $adminUsername; password = $adminPassword } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "$ApiRoot/auth/login" -WebSession $script:Session -ContentType "application/json" -Body $loginBody | Out-Null

$organizations = (Invoke-VipApi -Method Get -Path "/api/v1/platform/organizations?page=1&page_size=100").items
$orgARow = @($organizations | Where-Object { $_.slug -eq "qa-enterprise-a-20260804" })[0]
$orgBRow = @($organizations | Where-Object { $_.slug -eq "qa-enterprise-b-20260804" })[0]
$orgA = Invoke-VipApi -Method Get -Path "/api/v1/platform/organizations/$($orgARow.id)"
$orgB = Invoke-VipApi -Method Get -Path "/api/v1/platform/organizations/$($orgBRow.id)"
$orgADefault = @($orgA.workspaces | Where-Object { $_.is_default })[0]

$allUsers = (Invoke-VipApi -Method Get -Path "/api/v1/platform/users?page=1&page_size=100").items
$qaUsers = @($allUsers | Where-Object { $_.username.StartsWith("qa_") } | Sort-Object username)
if ($qaUsers.Count -ne 38) { throw "API inventory returned $($qaUsers.Count) QA users instead of 38." }

$adminUser = @($qaUsers | Where-Object { $_.username -eq $adminUsername })[0]
if (-not $adminUser) { throw "Protected QA platform administrator is missing." }
$adminAccess = Invoke-VipApi -Method Get -Path "/api/v1/platform/users/$($adminUser.id)/access-summary"
$adminWorkspaceIds = @($adminAccess.workspaces | ForEach-Object { $_.workspace_id.ToString() })
foreach ($workspace in @($orgA.workspaces) + @($orgB.workspaces)) {
    if ($workspace.id.ToString() -notin $adminWorkspaceIds) {
        $organizationId = if ($workspace.organization_id) { $workspace.organization_id } elseif ($workspace.id -in @($orgB.workspaces.id)) { $orgB.id } else { $orgA.id }
        Invoke-VipApi -Method Post -Path "/api/v1/platform/organizations/$organizationId/workspaces/$($workspace.id)/members" -Body @{
            username = $adminUsername
            workspace_role = "workspace_admin"
        } | Out-Null
    }
}

$credentials = [ordered]@{}
$credentials[$adminUsername] = @{ password = $adminPassword; email = "qa_platform_super_admin@vip.qa.local"; persona = "Platform Super Admin" }
foreach ($user in $qaUsers) {
    if ($user.username -eq $adminUsername) { continue }
    $password = New-QaPassword
    Invoke-VipApi -Method Post -Path "/api/v1/platform/users/$($user.id)/reset-password" -Body @{ password = $password; must_change_password = $false } | Out-Null
    $label = ($user.display_name -replace '^QA ', '')
    $credentials[$user.username] = @{ password = $password; email = $user.email; persona = $label }
}

$rolesRaw = Invoke-VipApi -Method Get -Path "/api/v1/custom-roles?include_system=false&include_archived=false" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id
$roles = @()
foreach ($roleItem in $rolesRaw) { $roles += $roleItem }
$apiRole = @($roles | Where-Object { $_.name -eq "QA API Developer" })[0]
if (-not $apiRole) {
    $apiRole = Invoke-VipApi -Method Post -Path "/api/v1/custom-roles" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{
        name = "QA API Developer"
        description = "AUTOMATION_QA role for api_developer_user"
        scope = "workspace"
        permission_keys = @("job.read", "events.subscribe")
    }
    $apiUser = @($qaUsers | Where-Object { $_.username -eq "qa_api_developer_user" })[0]
    Invoke-VipApi -Method Post -Path "/api/v1/custom-roles/$($apiRole.id)/assignments" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{ subject_type = "user"; subject_id = $apiUser.id } | Out-Null
    $roles += $apiRole
}

$groupsRaw = Invoke-VipApi -Method Get -Path "/api/v1/groups" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id
$groups = @()
foreach ($groupItem in $groupsRaw) { $groups += $groupItem }
$groupRole = @($groups | Where-Object { $_.name -eq "QA_Group_Role_Assignees" })[0]
if (-not $groupRole) {
    $groupRole = Invoke-VipApi -Method Post -Path "/api/v1/groups" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{ name = "QA_Group_Role_Assignees"; description = "AUTOMATION_QA group-backed custom role"; workspace_id = $orgADefault.id }
}
$groupRoleId = ([Guid]([string](@($groupRole.id)[0]))).ToString()
$groupRoleUser = @($qaUsers | Where-Object { $_.username -eq "qa_group_role_user" })[0]
$groupRoleUserId = ([Guid]$groupRoleUser.id).ToString()
$groupMembers = @(Invoke-VipApi -Method Get -Path "/api/v1/groups/$groupRoleId/members" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id)
if (-not @($groupMembers | Where-Object { $_ -and $_.user_id -and $_.user_id.ToString() -eq $groupRoleUserId })) {
    Invoke-VipApi -Method Post -Path "/api/v1/groups/$groupRoleId/members" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{ user_id = $groupRoleUserId } | Out-Null
}
$groupAnalystRole = @($roles | Where-Object { $_.name -eq "QA Group Analyst" })[0]
$groupAnalystRoleId = ([Guid]([string](@($groupAnalystRole.id)[0]))).ToString()
$groupAssignments = @(Invoke-VipApi -Method Get -Path "/api/v1/custom-roles/$groupAnalystRoleId/assignments" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id)
if (-not @($groupAssignments | Where-Object { $_.subject_type -eq "group" -and $_.subject_id.ToString() -eq $groupRoleId })) {
    Invoke-VipApi -Method Post -Path "/api/v1/custom-roles/$groupAnalystRoleId/assignments" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{ subject_type = "group"; subject_id = $groupRoleId } | Out-Null
}

$groupAcl = @($groups | Where-Object { $_.name -eq "QA_Group_Resource_Access" })[0]
if (-not $groupAcl) {
    $groupAcl = Invoke-VipApi -Method Post -Path "/api/v1/groups" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{ name = "QA_Group_Resource_Access"; description = "AUTOMATION_QA group ACL principal"; workspace_id = $orgADefault.id }
}
$groupAclId = ([Guid]([string](@($groupAcl.id)[0]))).ToString()
$groupAclUser = @($qaUsers | Where-Object { $_.username -eq "qa_group_acl_user" })[0]
$groupAclUserId = ([Guid]$groupAclUser.id).ToString()
$aclMembers = @(Invoke-VipApi -Method Get -Path "/api/v1/groups/$groupAclId/members" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id)
if (-not @($aclMembers | Where-Object { $_ -and $_.user_id -and $_.user_id.ToString() -eq $groupAclUserId })) {
    Invoke-VipApi -Method Post -Path "/api/v1/groups/$groupAclId/members" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{ user_id = $groupAclUserId } | Out-Null
}

$secretObject = [ordered]@{ created_at = (Get-Date).ToUniversalTime().ToString("o"); api_root = $ApiRoot; credentials = $credentials }
$secretJson = $secretObject | ConvertTo-Json -Depth 8
$encrypted = ConvertFrom-SecureString (ConvertTo-SecureString -String $secretJson -AsPlainText -Force)
$credentialPath = Join-Path $ArtifactRoot "qa-credentials.dpapi"
[System.IO.File]::WriteAllText($credentialPath, $encrypted, [System.Text.Encoding]::UTF8)

$workspaces = @($orgA.workspaces) + @($orgB.workspaces)
$manifest = [ordered]@{
    run_id = "20260804"
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    organizations = @($orgA, $orgB)
    workspaces = $workspaces
    users = @($qaUsers | ForEach-Object { @{ id = $_.id; username = $_.username; email = $_.email; status = $_.status; is_platform_admin = $_.is_platform_admin } })
    custom_roles = @($roles | ForEach-Object { @{ id = $_.id; name = $_.name; slug = $_.slug; scope = $_.scope; permission_keys = $_.permission_keys } })
    groups = @(@{ id = $groupRole.id; name = $groupRole.name; purpose = "group_role" }, @{ id = $groupAcl.id; name = $groupAcl.name; purpose = "group_acl" })
    credential_fixture = $credentialPath
}
$manifestPath = Join-Path $ArtifactRoot "qa-resource-manifest.json"
[System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 20), [System.Text.Encoding]::UTF8)

Write-Output "qa_users=$($qaUsers.Count)"
Write-Output "qa_organizations=2"
Write-Output "qa_workspaces=$($workspaces.Count)"
Write-Output "qa_custom_roles=$($roles.Count)"
Write-Output "qa_groups=2"
Write-Output "manifest_path=$manifestPath"
Write-Output "credential_fixture=$credentialPath"
