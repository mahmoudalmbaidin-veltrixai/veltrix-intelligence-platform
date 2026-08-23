# Independent Data Quality HTTP scale probe against live SHA runtime.
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\MahmoudAlmbaidin\Downloads\VIP'
$out = Join-Path $PSScriptRoot 'quality\http-scale.json'
$credentials = (& "$repo\apps\api\scripts\show-full-platform-qa-credentials.ps1" | ConvertFrom-Json).credentials
$api = 'http://localhost:8000'
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$login = @{ username = 'qa_platform_super_admin'; password = $credentials.qa_platform_super_admin.password } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "$api/auth/login" -WebSession $session -ContentType 'application/json' -Body $login | Out-Null
$csrf = $session.Cookies.GetCookies($api)['vip_csrf_token'].Value
$orgId = '17a4e171-ced9-40cf-883d-e42ff2dc4267'

$workspaces = @(
    @{ size = 10; id = 'c1f8509d-f1c3-462d-9b5b-3578b3bd95c8' },
    @{ size = 100; id = '25ef406b-c185-4a40-914b-1df0b4f007d3' },
    @{ size = 250; id = '6540eed6-a8d8-440b-b4fc-9bf7d1fa3294' },
    @{ size = 1000; id = '1aae4f52-3114-4377-aa4f-ae29965999d6' }
)

function Invoke-Counted([string]$url, $headers) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $resp = Invoke-WebRequest -Uri $url -WebSession $session -Headers $headers -UseBasicParsing
    $sw.Stop()
    $json = $resp.Content | ConvertFrom-Json
    return [pscustomobject]@{
        status = [int]$resp.StatusCode
        ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 2)
        bytes = $resp.RawContentLength
        total = $json.total
        items = @($json.items).Count
        url = $url
    }
}

$results = @()
foreach ($ws in $workspaces) {
    $headers = @{
        'X-Organization-ID' = $orgId
        'X-Workspace-ID' = $ws.id
        Origin = 'http://localhost:3009'
        'X-CSRF-Token' = $csrf
    }
    $calls = @()
    $calls += Invoke-Counted "$api/api/v1/datasets?page=1&page_size=100" $headers
    $calls += Invoke-Counted "$api/api/v1/datasets/quality/rules?page=1&page_size=100" $headers
    $calls += Invoke-Counted "$api/api/v1/datasets/quality/incidents?page=1&page_size=100" $headers
    $perDataset = $calls | Where-Object { $_.url -match '/datasets/.+/quality' }
    $results += [pscustomobject]@{
        size = $ws.size
        workspace_id = $ws.id
        http_calls = $calls.Count
        per_dataset_quality_calls = @($perDataset).Count
        dataset_total = $calls[0].total
        dataset_items = $calls[0].items
        quality_rule_total = $calls[1].total
        quality_rule_items = $calls[1].items
        incident_total = $calls[2].total
        incident_items = $calls[2].items
        statuses = @($calls | ForEach-Object { $_.status })
        elapsed_ms = @($calls | ForEach-Object { $_.ms })
        calls = $calls
    }
}

# Seed one rule per dataset in the 1000-row workspace, then re-hit once.
$seedSql = @"
INSERT INTO dataset_quality_rules (
  id, organization_id, workspace_id, dataset_id, rule_type, name, description,
  configuration, severity, status, is_enabled, created_at, updated_at
)
SELECT gen_random_uuid(), d.organization_id, d.workspace_id, d.id, 'not_null',
       'GROK-CERT-RULE', '', '{}'::json, 'warning', 'not_evaluated', true, now(), now()
FROM datasets d
WHERE d.workspace_id = '1aae4f52-3114-4377-aa4f-ae29965999d6'
  AND NOT EXISTS (
    SELECT 1 FROM dataset_quality_rules r
     WHERE r.dataset_id = d.id AND r.name = 'GROK-CERT-RULE'
  );
"@
$seedSql | docker compose --project-directory $repo exec -T postgres psql -U vip -d vip | Out-Null

$headers1000 = @{
    'X-Organization-ID' = $orgId
    'X-Workspace-ID' = '1aae4f52-3114-4377-aa4f-ae29965999d6'
    Origin = 'http://localhost:3009'
    'X-CSRF-Token' = $csrf
}
$after = @{
    size = 1000
    phase = 'after_rule_seed'
    rules = Invoke-Counted "$api/api/v1/datasets/quality/rules?page=1&page_size=100" $headers1000
    incidents = Invoke-Counted "$api/api/v1/datasets/quality/incidents?page=1&page_size=100" $headers1000
    datasets = Invoke-Counted "$api/api/v1/datasets?page=1&page_size=100" $headers1000
}

$payload = @{ before = $results; after_1000_rules = $after }
$payload | ConvertTo-Json -Depth 8 | Set-Content $out
Write-Host "Wrote $out"
$payload | ConvertTo-Json -Depth 4
