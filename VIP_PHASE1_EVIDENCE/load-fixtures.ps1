$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$plain = & (Join-Path $repoRoot 'apps/api/scripts/show-full-platform-qa-credentials.ps1')
try {
    $payload = $plain | ConvertFrom-Json
    $credentials = $payload.credentials
    $editor = $credentials.qa_workspace_editor
    if (-not $editor.email -or -not $editor.password) {
        throw 'The workspace editor QA credential is unavailable.'
    }

    $env:VIP_PHASE1_EMAIL = [string]$editor.email
    $env:VIP_PHASE1_PASSWORD = [string]$editor.password
    $env:VIP_PHASE1_ORGANIZATION = 'QA_Enterprise_A_20260804'
    $env:VIP_PHASE1_ORGANIZATION_ID = '17a4e171-ced9-40cf-883d-e42ff2dc4267'
    $env:VIP_PHASE1_WORKSPACE = 'Default'
    $env:VIP_PHASE1_WORKSPACE_ID = 'b26c56a6-b743-4ce4-ae20-4da17cdb6e36'

    # Existing E2E modules import the complete persona contract even when a
    # focused spec uses only one persona. Populate it without printing secrets.
    $mapping = @{
        VIP_E2E = 'qa_workspace_editor'
        VIP_E2E_TENANT_A = 'qa_workspace_viewer'
        VIP_E2E_TENANT_B = 'qa_cross_tenant_attacker'
        VIP_E2E_GOVERNANCE_ADMIN = 'qa_workspace_admin'
        VIP_E2E_GOVERNANCE_EDITOR = 'qa_workspace_editor'
        VIP_E2E_GOVERNANCE_VIEWER = 'qa_workspace_viewer'
        VIP_E2E_GOVERNANCE_RESTRICTED = 'qa_explicitly_denied_user'
        VIP_E2E_MODULE_RESTRICTED = 'qa_workspace_operator'
        VIP_E2E_NORMAL_USER = 'qa_organization_member'
    }
    foreach ($entry in $mapping.GetEnumerator()) {
        $credential = $credentials.($entry.Value)
        [Environment]::SetEnvironmentVariable("$($entry.Key)_EMAIL", [string]$credential.email, 'Process')
        [Environment]::SetEnvironmentVariable("$($entry.Key)_PASSWORD", [string]$credential.password, 'Process')
    }
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
    $env:VIP_E2E_CERTIFICATION_DATASET_NAME = 'vip_b5_sales_demo'
    $env:VIP_E2E_CERTIFICATION_SEMANTIC_MODEL_NAME = 'QA Revenue Semantic Model'
    $env:VIP_E2E_GOVERNANCE_RESTRICTED_ID = '00000000-0000-0000-0000-000000000000'
}
finally {
    $plain = $null
    $payload = $null
}
