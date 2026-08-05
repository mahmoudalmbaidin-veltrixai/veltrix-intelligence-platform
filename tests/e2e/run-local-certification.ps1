param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PlaywrightArgs = @('--project=chrome-desktop')
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$credentials = (& (Join-Path $repo 'apps\api\scripts\show-full-platform-qa-credentials.ps1') | ConvertFrom-Json).credentials

function Set-Persona([string]$prefix, [string]$key) {
    $entry = $credentials.$key
    if (-not $entry -or -not $entry.email -or -not $entry.password) {
        throw "Secure QA credential $key is unavailable. Run the documented QA seed/resume command first."
    }
    [Environment]::SetEnvironmentVariable("${prefix}_EMAIL", [string]$entry.email, 'Process')
    [Environment]::SetEnvironmentVariable("${prefix}_PASSWORD", [string]$entry.password, 'Process')
}

Set-Persona 'VIP_E2E' 'qa_platform_super_admin'
Set-Persona 'VIP_E2E_TENANT_A' 'qa_organization_member'
Set-Persona 'VIP_E2E_TENANT_B' 'qa_cross_tenant_attacker'
Set-Persona 'VIP_E2E_GOVERNANCE_ADMIN' 'qa_organization_admin'
Set-Persona 'VIP_E2E_GOVERNANCE_EDITOR' 'qa_workspace_editor'
Set-Persona 'VIP_E2E_GOVERNANCE_VIEWER' 'qa_workspace_viewer'
Set-Persona 'VIP_E2E_GOVERNANCE_RESTRICTED' 'qa_explicitly_denied_user'
Set-Persona 'VIP_E2E_MODULE_RESTRICTED' 'qa_direct_acl_user'
Set-Persona 'VIP_E2E_NORMAL_USER' 'qa_organization_member'

$env:VIP_E2E_ORGANIZATION_NAME = 'QA_Enterprise_A_20260804'
$env:VIP_E2E_ORGANIZATION_A_NAME = 'QA_Enterprise_A_20260804'
$env:VIP_E2E_ORGANIZATION_B_NAME = 'QA_Enterprise_B_20260804'
$env:VIP_E2E_WORKSPACE_A_PRIMARY = 'Default'
$env:VIP_E2E_WORKSPACE_A_SECONDARY = 'QA_Analytics'
$env:VIP_E2E_WORKSPACE_B_PRIMARY = 'Default'
$env:VIP_E2E_TENANT_A_ORGANIZATION_NAME = 'QA_Enterprise_A_20260804'
$env:VIP_E2E_TENANT_A_WORKSPACE_NAME = 'Default'
$env:VIP_E2E_TENANT_B_ORGANIZATION_NAME = 'QA_Enterprise_B_20260804'
$env:VIP_E2E_TENANT_B_WORKSPACE_NAME = 'Default'
$env:VIP_E2E_DESTINATION_CONNECTION_NAME = 'QA_PostgreSQL_Valid'
$env:VIP_E2E_CERTIFICATION_DATASET_NAME = 'QA Browser Certification Dataset'
$env:VIP_E2E_CERTIFICATION_SEMANTIC_MODEL_NAME = 'QA Browser Certification Semantic Model'

# Verify and safely repair the only mutable browser prerequisite: explicit
# super-admin membership in the secondary workspace. Existing membership is
# read first, so repeated runs do not create duplicate audit events.
$apiRoot = 'http://localhost:8000'
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$loginBody = @{ username = 'qa_platform_super_admin'; password = $credentials.qa_platform_super_admin.password } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "$apiRoot/auth/login" -WebSession $session -ContentType 'application/json' -Body $loginBody | Out-Null
$users = (Invoke-RestMethod -Method Get -Uri "$apiRoot/api/v1/platform/users?page=1&page_size=100&search=qa_platform_super_admin" -WebSession $session).items
$admin = @($users | Where-Object { $_.username -eq 'qa_platform_super_admin' })[0]
if (-not $admin) { throw 'The protected QA platform-super-admin fixture is missing.' }
$organizations = (Invoke-RestMethod -Method Get -Uri "$apiRoot/api/v1/platform/organizations?page=1&page_size=100" -WebSession $session).items
$orgA = @($organizations | Where-Object { $_.name -eq $env:VIP_E2E_ORGANIZATION_A_NAME })[0]
if (-not $orgA) { throw "Required QA organization $($env:VIP_E2E_ORGANIZATION_A_NAME) is missing." }
$orgDetail = Invoke-RestMethod -Method Get -Uri "$apiRoot/api/v1/platform/organizations/$($orgA.id)" -WebSession $session
$primary = @($orgDetail.workspaces | Where-Object { $_.name -eq $env:VIP_E2E_WORKSPACE_A_PRIMARY })[0]
if (-not $primary) { throw "Required QA workspace $($env:VIP_E2E_WORKSPACE_A_PRIMARY) is missing." }
$secondary = @($orgDetail.workspaces | Where-Object { $_.name -eq $env:VIP_E2E_WORKSPACE_A_SECONDARY })[0]
if (-not $secondary) { throw "Required QA workspace $($env:VIP_E2E_WORKSPACE_A_SECONDARY) is missing." }
$summary = Invoke-RestMethod -Method Get -Uri "$apiRoot/api/v1/platform/users/$($admin.id)/access-summary" -WebSession $session
if (-not @($summary.workspaces | Where-Object { $_.workspace_id -eq $secondary.id })) {
    $csrf = $session.Cookies.GetCookies($apiRoot)['vip_csrf_token'].Value
    $headers = @{ Origin = 'http://localhost:3009'; 'X-CSRF-Token' = $csrf }
    $body = @{ username = 'qa_platform_super_admin'; workspace_role = 'workspace_admin' } | ConvertTo-Json -Compress
    Invoke-RestMethod -Method Post -Uri "$apiRoot/api/v1/platform/organizations/$($orgA.id)/workspaces/$($secondary.id)/members" -WebSession $session -Headers $headers -ContentType 'application/json' -Body $body | Out-Null
}

# Provision the exact live dataset and semantic-model fixtures used by the
# browser suites. Creation is source-key/name idempotent, and the only ACL repair
# is an exact deny for the named explicit-deny persona on the named model.
$adminSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$adminLogin = @{ username = 'qa_organization_admin'; password = $credentials.qa_organization_admin.password } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "$apiRoot/auth/login" -WebSession $adminSession -ContentType 'application/json' -Body $adminLogin | Out-Null
$adminCsrf = $adminSession.Cookies.GetCookies($apiRoot)['vip_csrf_token'].Value
$tenantHeaders = @{
    Origin = 'http://localhost:3009'
    'X-CSRF-Token' = $adminCsrf
    'X-Organization-ID' = [string]$orgA.id
    'X-Workspace-ID' = [string]$primary.id
}
$connections = Invoke-RestMethod -Method Get -Uri "$apiRoot/api/v1/connections?page_size=100" -WebSession $adminSession -Headers $tenantHeaders
$destination = @($connections.items | Where-Object { $_.name -eq $env:VIP_E2E_DESTINATION_CONNECTION_NAME })
if ($destination.Count -ne 1) {
    throw "Expected exactly one $($env:VIP_E2E_DESTINATION_CONNECTION_NAME) connection; found $($destination.Count)."
}
if ($destination[0].type.key -ne 'postgresql' -or $destination[0].health_status -ne 'healthy') {
    throw "Certification destination must be a healthy PostgreSQL connection."
}
$datasetBody = @{
    connection_id = [string]$destination[0].id
    dataset_type = 'table'
    source_catalog = 'vip'
    source_schema = 'public'
    source_name = 'qa_browser_certification'
    display_name = $env:VIP_E2E_CERTIFICATION_DATASET_NAME
    description = 'Idempotent browser certification fixture'
    is_read_only = $true
} | ConvertTo-Json -Compress
$dataset = Invoke-RestMethod -Method Post -Uri "$apiRoot/api/v1/datasets" -WebSession $adminSession -Headers $tenantHeaders -ContentType 'application/json' -Body $datasetBody
if ($dataset.display_name -ne $env:VIP_E2E_CERTIFICATION_DATASET_NAME) {
    throw 'The exact browser certification dataset could not be resolved.'
}
$models = @(Invoke-RestMethod -Method Get -Uri "$apiRoot/api/v1/semantic-models" -WebSession $adminSession -Headers $tenantHeaders)
$model = @($models | Where-Object { $_.name -eq $env:VIP_E2E_CERTIFICATION_SEMANTIC_MODEL_NAME })[0]
if (-not $model) {
    $modelBody = @{
        key = 'qa_browser_certification'
        name = $env:VIP_E2E_CERTIFICATION_SEMANTIC_MODEL_NAME
        description = 'Idempotent browser certification fixture'
        primary_dataset_id = [string]$dataset.id
        timezone = 'Asia/Riyadh'
        currency = 'SAR'
    } | ConvertTo-Json -Compress
    $model = Invoke-RestMethod -Method Post -Uri "$apiRoot/api/v1/semantic-models" -WebSession $adminSession -Headers $tenantHeaders -ContentType 'application/json' -Body $modelBody
}
if ([string]$model.primary_dataset_id -ne [string]$dataset.id) {
    throw 'The browser certification semantic model is not bound to the exact certification dataset.'
}
$deniedUsers = (Invoke-RestMethod -Method Get -Uri "$apiRoot/api/v1/platform/users?page=1&page_size=100&search=qa_explicitly_denied_user" -WebSession $session).items
$deniedUser = @($deniedUsers | Where-Object { $_.username -eq 'qa_explicitly_denied_user' })[0]
if (-not $deniedUser) { throw 'The explicit-deny QA persona is missing.' }
[Environment]::SetEnvironmentVariable('VIP_E2E_GOVERNANCE_RESTRICTED_ID', [string]$deniedUser.id, 'Process')
$entries = @(Invoke-RestMethod -Method Get -Uri "$apiRoot/api/v1/resources/semantic_model/$($model.id)/access" -WebSession $adminSession -Headers $tenantHeaders)
$exactDeny = @($entries | Where-Object {
    $_.subject_type -eq 'user' -and [string]$_.subject_id -eq [string]$deniedUser.id -and $_.effect -eq 'deny'
})
if ($exactDeny.Count -eq 0) {
    $denyBody = @{
        subject_type = 'user'
        subject_id = [string]$deniedUser.id
        access_level = 'view'
        effect = 'deny'
        expires_at = $null
    } | ConvertTo-Json -Compress
    Invoke-RestMethod -Method Post -Uri "$apiRoot/api/v1/resources/semantic_model/$($model.id)/access" -WebSession $adminSession -Headers $tenantHeaders -ContentType 'application/json' -Body $denyBody | Out-Null
}

Push-Location $repo
try {
    & node '.\node_modules\@playwright\test\cli.js' test @PlaywrightArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
