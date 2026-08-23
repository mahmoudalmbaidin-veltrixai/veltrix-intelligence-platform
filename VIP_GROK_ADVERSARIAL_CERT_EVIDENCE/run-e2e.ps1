# Independent cert harness. Does not modify the frozen application tree.
$ErrorActionPreference = 'Continue'
$repo = 'C:\Users\MahmoudAlmbaidin\Downloads\VIP'
Set-Location $repo

$credentials = (& "$repo\apps\api\scripts\show-full-platform-qa-credentials.ps1" | ConvertFrom-Json).credentials
function Set-Persona([string]$prefix, [string]$key) {
    $entry = $credentials.$key
    Set-Item -Path "Env:${prefix}_EMAIL" -Value ([string]$entry.email)
    Set-Item -Path "Env:${prefix}_PASSWORD" -Value ([string]$entry.password)
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

$env:VIP_E2E_GOVERNANCE_DEMO_EMAIL = 'governance-admin@vip.demo'
$env:VIP_E2E_GOVERNANCE_DEMO_PASSWORD = 'Enterprise review 2026!'
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
$env:PLAYWRIGHT_REUSE_SERVER = '1'
Remove-Item Env:PLAYWRIGHT_BROWSERS_PATH -ErrorAction SilentlyContinue

# Restricted-user id required by persona fixtures.
$apiRoot = 'http://localhost:8000'
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$loginBody = @{ username = 'qa_platform_super_admin'; password = $credentials.qa_platform_super_admin.password } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "$apiRoot/auth/login" -WebSession $session -ContentType 'application/json' -Body $loginBody | Out-Null
$deniedUsers = (Invoke-RestMethod -Method Get -Uri "$apiRoot/api/v1/platform/users?page=1&page_size=100&search=qa_explicitly_denied_user" -WebSession $session).items
$deniedUser = @($deniedUsers | Where-Object { $_.username -eq 'qa_explicitly_denied_user' })[0]
if (-not $deniedUser) { throw 'explicit-deny persona missing' }
$env:VIP_E2E_GOVERNANCE_RESTRICTED_ID = [string]$deniedUser.id

$playwrightArgs = @(
    '.\node_modules\@playwright\test\cli.js', 'test',
    '--project=chrome-desktop',
    '--project=firefox-desktop',
    '--project=webkit-desktop',
    '--project=chromium-mobile',
    '--project=chrome-high-dpi'
)
Write-Host "Launching Playwright: $($playwrightArgs -join ' ')"
& node @playwrightArgs
exit $LASTEXITCODE
