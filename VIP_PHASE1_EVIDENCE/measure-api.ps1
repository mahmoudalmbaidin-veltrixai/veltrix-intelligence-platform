param(
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [switch]$LegacyFanout
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'load-fixtures.ps1')

$apiRoot = 'http://localhost:8000'
$session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
$login = @{ username = $env:VIP_PHASE1_EMAIL; password = $env:VIP_PHASE1_PASSWORD } | ConvertTo-Json -Compress
Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$apiRoot/auth/login" -WebSession $session -ContentType 'application/json' -Body $login | Out-Null
$headers = @{
    Origin = 'http://localhost:3009'
    'X-Organization-ID' = $env:VIP_PHASE1_ORGANIZATION_ID
    'X-Workspace-ID' = $env:VIP_PHASE1_WORKSPACE_ID
}

$measurements = @()
foreach ($pageSize in @(10, 100)) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $response = Invoke-WebRequest -UseBasicParsing -Uri "$apiRoot/api/v1/datasets?page=1&page_size=$pageSize" -WebSession $session -Headers $headers
    $watch.Stop()
    $body = $response.Content | ConvertFrom-Json
    $qualityRequests = if ($LegacyFanout) { @($body.items).Count } else { 0 }
    $measurements += [ordered]@{
        requested_page_size = $pageSize
        returned_items = @($body.items).Count
        total_visible = [int]$body.total
        list_http_requests = 1
        quality_http_requests = $qualityRequests
        total_dataset_hydration_requests = 1 + $qualityRequests
        backend_list_ms = [math]::Round($watch.Elapsed.TotalMilliseconds, 2)
        payload_bytes = [Text.Encoding]::UTF8.GetByteCount($response.Content)
    }
}

$result = [ordered]@{
    measured_at = (Get-Date).ToUniversalTime().ToString('o')
    organization_id = $env:VIP_PHASE1_ORGANIZATION_ID
    workspace_id = $env:VIP_PHASE1_WORKSPACE_ID
    measurements = $measurements
}
$resolved = [IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputPath))
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($resolved)) | Out-Null
[IO.File]::WriteAllText($resolved, ($result | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
