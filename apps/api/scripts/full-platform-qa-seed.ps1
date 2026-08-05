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
        $csrfCookie = $script:Session.Cookies.GetCookies($ApiRoot)["vip_csrf_token"]
        if (-not $csrfCookie) { throw "The authenticated session has no CSRF cookie." }
        $headers["X-CSRF-Token"] = $csrfCookie.Value
    }
    $arguments = @{
        Method = $Method
        Uri = "$ApiRoot$Path"
        WebSession = $script:Session
        Headers = $headers
        ContentType = "application/json"
    }
    if ($null -ne $Body) { $arguments.Body = $Body | ConvertTo-Json -Depth 20 -Compress }
    return Invoke-RestMethod @arguments
}

$runId = "20260804"
$adminUsername = "qa_platform_super_admin"
$adminEmail = "qa_platform_super_admin@vip.qa.local"
$adminPassword = New-QaPassword

$existing = docker exec vip-postgres-1 psql -U vip -d vip -Atc "SELECT count(*) FROM users WHERE normalized_username='qa_platform_super_admin';"
$existingQaOrganizations = docker exec vip-postgres-1 psql -U vip -d vip -Atc "SELECT count(*) FROM organizations WHERE slug IN ('qa-enterprise-a-20260804','qa-enterprise-b-20260804');"
if ($existing -eq "0" -and $existingQaOrganizations -eq "0") {
    $adminPassword | docker exec -i vip-api-1 python -m vip_api.cli create-user --username $adminUsername --email $adminEmail --display-name "QA Platform Super Admin" --password-stdin | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the QA platform administrator." }
    docker exec vip-api-1 python -m vip_api.cli grant-platform-admin --email $adminEmail | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to grant the QA platform administrator flag." }
}
elseif ($existing -eq "1" -and $existingQaOrganizations -eq "0") {
    $env:DATABASE_URL = "postgresql+asyncpg://vip:vip_local_dev_only@localhost:5432/vip"
    $env:REDIS_URL = "redis://localhost:6379/0"
    $adminPassword | & (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe") (Join-Path $PSScriptRoot "reset-qa-bootstrap-password.py") --username $adminUsername | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to recover the partial QA bootstrap account." }
}
else {
    throw "QA seed refused: an existing QA estate was detected. Use the recorded manifest instead of creating an overlapping estate."
}

$loginBody = @{ username = $adminUsername; password = $adminPassword } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "$ApiRoot/auth/login" -WebSession $script:Session -ContentType "application/json" -Body $loginBody | Out-Null

$orgA = Invoke-VipApi -Method Post -Path "/api/v1/platform/organizations" -Body @{
    name = "QA_Enterprise_A_$runId"
    slug = "qa-enterprise-a-$runId"
    owner_email = $adminEmail
}
$orgB = Invoke-VipApi -Method Post -Path "/api/v1/platform/organizations" -Body @{
    name = "QA_Enterprise_B_$runId"
    slug = "qa-enterprise-b-$runId"
    owner_email = $adminEmail
}

$orgADefault = @($orgA.workspaces | Where-Object { $_.is_default })[0]
$orgBDefault = @($orgB.workspaces | Where-Object { $_.is_default })[0]
$orgAAnalytics = Invoke-VipApi -Method Post -Path "/api/v1/platform/organizations/$($orgA.id)/workspaces" -Body @{ name = "QA_Analytics"; slug = "qa-analytics" }
$orgARestricted = Invoke-VipApi -Method Post -Path "/api/v1/platform/organizations/$($orgA.id)/workspaces" -Body @{ name = "QA_Restricted"; slug = "qa-restricted" }
$orgBAnalytics = Invoke-VipApi -Method Post -Path "/api/v1/platform/organizations/$($orgB.id)/workspaces" -Body @{ name = "QA_Analytics_B"; slug = "qa-analytics-b" }
$orgBIsolated = Invoke-VipApi -Method Post -Path "/api/v1/platform/organizations/$($orgB.id)/workspaces" -Body @{ name = "QA_Isolated_B"; slug = "qa-isolated-b" }

$personas = @(
    @{ key = "platform_support_admin"; label = "Platform Support Admin"; org = "A"; orgRole = "organization_admin"; wsRole = "workspace_admin" },
    @{ key = "organization_admin"; label = "Organization Admin"; org = "A"; orgRole = "organization_admin"; wsRole = "workspace_admin" },
    @{ key = "organization_member"; label = "Organization Member"; org = "A"; orgRole = "organization_member"; wsRole = "viewer" },
    @{ key = "workspace_admin"; label = "Workspace Admin"; org = "A"; orgRole = "organization_member"; wsRole = "workspace_admin" },
    @{ key = "workspace_editor"; label = "Workspace Editor"; org = "A"; orgRole = "organization_member"; wsRole = "editor" },
    @{ key = "workspace_operator"; label = "Workspace Operator"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "workspace_viewer"; label = "Workspace Viewer"; org = "A"; orgRole = "organization_member"; wsRole = "viewer" },
    @{ key = "custom_role_user"; label = "Custom Role User"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "group_role_user"; label = "Group-Based Role User"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "direct_acl_user"; label = "Direct ACL User"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "group_acl_user"; label = "Group ACL User"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "explicitly_denied_user"; label = "Explicitly Denied User"; org = "A"; orgRole = "organization_member"; wsRole = "editor" },
    @{ key = "expired_access_user"; label = "Expired Access User"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "suspended_user"; label = "Suspended User"; org = "A"; orgRole = "organization_member"; wsRole = "viewer" },
    @{ key = "archived_user"; label = "Archived User Candidate"; org = "A"; orgRole = "organization_member"; wsRole = "viewer" },
    @{ key = "cross_tenant_attacker"; label = "Cross-Tenant Attacker"; org = "B"; orgRole = "organization_member"; wsRole = "viewer" },
    @{ key = "dataset_query_only"; label = "Dataset Query-Only User"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "dataset_editor"; label = "Dataset Editor"; org = "A"; orgRole = "organization_member"; wsRole = "editor" },
    @{ key = "dataset_certifier"; label = "Dataset Certifier"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "pipeline_owner"; label = "Pipeline Owner"; org = "A"; orgRole = "organization_member"; wsRole = "editor" },
    @{ key = "pipeline_developer"; label = "Pipeline Developer"; org = "A"; orgRole = "organization_member"; wsRole = "editor" },
    @{ key = "pipeline_operator"; label = "Pipeline Operator"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "pipeline_viewer"; label = "Pipeline Viewer"; org = "A"; orgRole = "organization_member"; wsRole = "viewer" },
    @{ key = "dashboard_viewer"; label = "Dashboard Viewer"; org = "A"; orgRole = "organization_member"; wsRole = "viewer" },
    @{ key = "dashboard_interactive"; label = "Dashboard Interactive User"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "dashboard_editor"; label = "Dashboard Editor"; org = "A"; orgRole = "organization_member"; wsRole = "editor" },
    @{ key = "dashboard_manager"; label = "Dashboard Manager"; org = "A"; orgRole = "organization_member"; wsRole = "workspace_admin" },
    @{ key = "connection_use_only"; label = "Connection Use-Only User"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "connection_tester"; label = "Connection Tester"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "connection_editor"; label = "Connection Editor"; org = "A"; orgRole = "organization_member"; wsRole = "editor" },
    @{ key = "connection_secret_rotator"; label = "Connection Secret Rotator"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "connection_administrator"; label = "Connection Administrator"; org = "A"; orgRole = "organization_member"; wsRole = "workspace_admin" },
    @{ key = "semantic_query_user"; label = "Semantic Query User"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "report_consumer"; label = "Report Consumer"; org = "A"; orgRole = "organization_member"; wsRole = "viewer" },
    @{ key = "scheduler_operator"; label = "Scheduler Operator"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "file_upload_user"; label = "File Upload User"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" },
    @{ key = "api_developer_user"; label = "API/Developer User"; org = "A"; orgRole = "organization_member"; wsRole = "restricted_user" }
)

$credentials = [ordered]@{}
$credentials[$adminUsername] = @{ password = $adminPassword; email = $adminEmail; persona = "Platform Super Admin" }
$userRecords = [ordered]@{}
$userRecords[$adminUsername] = (Invoke-VipApi -Method Get -Path "/api/v1/platform/users?page=1&page_size=100&search=$adminUsername").items[0]

# Platform certification uses the super-admin to prove a validated workspace
# transition. Provision every QA workspace explicitly; the platform flag does
# not bypass the tenancy navigation inventory.
foreach ($workspace in @($orgADefault, $orgAAnalytics, $orgARestricted, $orgBDefault, $orgBAnalytics, $orgBIsolated)) {
    $organizationId = if ($workspace.id -in @($orgBDefault.id, $orgBAnalytics.id, $orgBIsolated.id)) { $orgB.id } else { $orgA.id }
    Invoke-VipApi -Method Post -Path "/api/v1/platform/organizations/$organizationId/workspaces/$($workspace.id)/members" -Body @{
        username = $adminUsername
        workspace_role = "workspace_admin"
    } | Out-Null
}

foreach ($persona in $personas) {
    $username = "qa_$($persona.key)"
    $email = "$username@vip.qa.local"
    $password = New-QaPassword
    $targetOrg = if ($persona.org -eq "B") { $orgB } else { $orgA }
    $targetWorkspace = if ($persona.org -eq "B") { $orgBDefault } else { $orgADefault }
    $created = Invoke-VipApi -Method Post -Path "/api/v1/platform/users" -Body @{
        username = $username
        email = $email
        display_name = "QA $($persona.label)"
        password = $password
        is_platform_admin = $false
        organization_id = $targetOrg.id
        organization_role = $persona.orgRole
    }
    if ($persona.wsRole -ne "viewer") {
        Invoke-VipApi -Method Post -Path "/api/v1/platform/organizations/$($targetOrg.id)/workspaces/$($targetWorkspace.id)/members" -Body @{
            username = $username
            workspace_role = $persona.wsRole
        } | Out-Null
    }
    $credentials[$username] = @{ password = $password; email = $email; persona = $persona.label }
    $userRecords[$username] = $created
}

Invoke-VipApi -Method Post -Path "/api/v1/platform/organizations/$($orgB.id)/members" -Body @{
    username = "qa_platform_support_admin"
    organization_role = "organization_admin"
} | Out-Null
Invoke-VipApi -Method Post -Path "/api/v1/platform/organizations/$($orgB.id)/workspaces/$($orgBDefault.id)/members" -Body @{
    username = "qa_platform_support_admin"
    workspace_role = "workspace_admin"
} | Out-Null

Invoke-VipApi -Method Post -Path "/api/v1/platform/users/$($userRecords['qa_suspended_user'].id)/suspend" | Out-Null

$customRoleDefinitions = @(
    @{ key = "workspace_operator"; name = "QA Workspace Operator"; permissions = @("pipeline.read", "pipeline.execute", "pipeline.runs.read", "pipeline.runs.retry", "job.read") },
    @{ key = "custom_role_user"; name = "QA Custom Analyst"; permissions = @("dataset.read", "dataset.fields.read", "semantic_model.read", "semantic.query", "dashboard.read", "dashboard.query") },
    @{ key = "group_role_user"; name = "QA Group Analyst"; permissions = @("dataset.read", "semantic_model.read", "semantic.query", "dashboard.read", "dashboard.query") },
    @{ key = "dataset_certifier"; name = "QA Dataset Certifier"; permissions = @("dataset.read", "dataset.fields.read", "dataset.classification.update", "dataset.quality.read") },
    @{ key = "pipeline_operator"; name = "QA Pipeline Operator"; permissions = @("pipeline.read", "pipeline.execute", "pipeline.runs.read", "pipeline.runs.retry", "pipeline.runs.cancel") },
    @{ key = "dashboard_interactive"; name = "QA Dashboard Interactive"; permissions = @("dashboard.read", "dashboard.query", "dashboard.filter.manage", "dashboard.export", "dashboard.export.read", "dashboard.export.download") },
    @{ key = "connection_use_only"; name = "QA Connection Use Only"; permissions = @("connection.read", "connection.types.read", "dataset.discover") },
    @{ key = "connection_tester"; name = "QA Connection Tester"; permissions = @("connection.read", "connection.types.read", "connection.test", "connection.health.read") },
    @{ key = "connection_secret_rotator"; name = "QA Connection Secret Rotator"; permissions = @("connection.read", "connection.credentials.rotate") },
    @{ key = "semantic_query_user"; name = "QA Semantic Query"; permissions = @("dataset.read", "dataset.fields.read", "semantic_model.read", "semantic.query") },
    @{ key = "scheduler_operator"; name = "QA Scheduler Operator"; permissions = @("dashboard.read", "dashboard.delivery.read", "dashboard.delivery.manage", "dashboard.delivery.send", "report.read", "report.schedule") },
    @{ key = "file_upload_user"; name = "QA File Uploader"; permissions = @("file.upload", "file.download", "file.manage", "job.read") },
    @{ key = "api_developer_user"; name = "QA API Developer"; permissions = @("job.read", "events.subscribe") }
)

$roleRecords = [ordered]@{}
foreach ($definition in $customRoleDefinitions) {
    $role = Invoke-VipApi -Method Post -Path "/api/v1/custom-roles" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{
        name = $definition.name
        description = "AUTOMATION_QA role for $($definition.key)"
        scope = "workspace"
        permission_keys = $definition.permissions
    }
    $roleRecords[$definition.key] = $role
    if ($definition.key -ne "group_role_user") {
        Invoke-VipApi -Method Post -Path "/api/v1/custom-roles/$($role.id)/assignments" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{
            subject_type = "user"
            subject_id = $userRecords["qa_$($definition.key)"].id
        } | Out-Null
    }
}

$groupRole = Invoke-VipApi -Method Post -Path "/api/v1/groups" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{
    name = "QA_Group_Role_Assignees"
    description = "AUTOMATION_QA group-backed custom role"
    workspace_id = $orgADefault.id
}
Invoke-VipApi -Method Post -Path "/api/v1/groups/$($groupRole.id)/members" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{ user_id = $userRecords["qa_group_role_user"].id } | Out-Null
Invoke-VipApi -Method Post -Path "/api/v1/custom-roles/$($roleRecords['group_role_user'].id)/assignments" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{ subject_type = "group"; subject_id = $groupRole.id } | Out-Null

$groupAcl = Invoke-VipApi -Method Post -Path "/api/v1/groups" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{
    name = "QA_Group_Resource_Access"
    description = "AUTOMATION_QA group ACL principal"
    workspace_id = $orgADefault.id
}
Invoke-VipApi -Method Post -Path "/api/v1/groups/$($groupAcl.id)/members" -OrganizationId $orgA.id -WorkspaceId $orgADefault.id -Body @{ user_id = $userRecords["qa_group_acl_user"].id } | Out-Null

$secretObject = [ordered]@{
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    api_root = $ApiRoot
    credentials = $credentials
}
$secretJson = $secretObject | ConvertTo-Json -Depth 8
$encrypted = ConvertFrom-SecureString (ConvertTo-SecureString -String $secretJson -AsPlainText -Force)
$credentialPath = Join-Path $ArtifactRoot "qa-credentials.dpapi"
[System.IO.File]::WriteAllText($credentialPath, $encrypted, [System.Text.Encoding]::UTF8)

$manifest = [ordered]@{
    run_id = $runId
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    organizations = @($orgA, $orgB)
    workspaces = @($orgADefault, $orgAAnalytics, $orgARestricted, $orgBDefault, $orgBAnalytics, $orgBIsolated)
    users = @($userRecords.Values | ForEach-Object { @{ id = $_.id; username = $_.username; email = $_.email; status = $_.status; is_platform_admin = $_.is_platform_admin } })
    custom_roles = @($roleRecords.Values | ForEach-Object { @{ id = $_.id; name = $_.name; slug = $_.slug; scope = $_.scope; permission_keys = $_.permission_keys } })
    groups = @(
        @{ id = $groupRole.id; name = $groupRole.name; purpose = "group_role" },
        @{ id = $groupAcl.id; name = $groupAcl.name; purpose = "group_acl" }
    )
    credential_fixture = $credentialPath
}
$manifestPath = Join-Path $ArtifactRoot "qa-resource-manifest.json"
[System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 20), [System.Text.Encoding]::UTF8)

Write-Output "qa_users=$($userRecords.Count)"
Write-Output "qa_organizations=2"
Write-Output "qa_workspaces=6"
Write-Output "qa_custom_roles=$($roleRecords.Count)"
Write-Output "qa_groups=2"
Write-Output "manifest_path=$manifestPath"
Write-Output "credential_fixture=$credentialPath"
