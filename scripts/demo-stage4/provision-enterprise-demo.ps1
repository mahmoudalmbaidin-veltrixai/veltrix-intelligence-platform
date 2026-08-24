param(
    [ValidateSet("DryRun", "Apply")][string]$Mode = "DryRun",
    [string]$ApiRoot = "http://localhost:8000",
    [string]$VerifiedBackupPath = "",
    [switch]$ConfirmNonProduction,
    [switch]$IncludeLegacyStage2Cleanup
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$scenarioPath = Join-Path $repositoryRoot "demo-data\stage4\scenarios.json"
$generatedRoot = Join-Path $repositoryRoot "demo-data\stage4\generated"
$artifactRoot = Join-Path $repositoryRoot "artifacts\demo-stage4"
$credentialRoot = Join-Path $env:LOCALAPPDATA "Veltrix\VIP\stage4"
$credentialPath = Join-Path $credentialRoot "demo-user-credentials.dpapi"
$platformCredentialPath = Join-Path $credentialRoot "platform-operator.dpapi"
$manifestPath = Join-Path $artifactRoot "environment-manifest.json"
$configuration = Get-Content -Raw -LiteralPath $scenarioPath | ConvertFrom-Json -Depth 60
$demoSlugs = @($configuration.organizations.slug)
$demoSchemas = @($configuration.organizations.schema)

function Invoke-CheckedNative([scriptblock]$Command, [string]$FailureMessage) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw $FailureMessage }
}

function Assert-SafeEnvironment {
    if ($env:VIP_DEMO_ENVIRONMENT -ne "stage4") { throw "Set VIP_DEMO_ENVIRONMENT=stage4 explicitly." }
    if (-not $ConfirmNonProduction) { throw "Pass -ConfirmNonProduction after verifying the target." }
    if ($env:VIP_STAGE4_BACKUP_VERIFIED -ne "TRUE") { throw "Set VIP_STAGE4_BACKUP_VERIFIED=TRUE only after restore verification." }
    if (-not $VerifiedBackupPath) { throw "A verified baseline backup path is required." }
    $resolvedBackup = Resolve-Path -LiteralPath $VerifiedBackupPath -ErrorAction Stop
    if ((Get-Item -LiteralPath $resolvedBackup).Length -lt 1MB) { throw "The backup is unexpectedly small." }
    $version = Invoke-RestMethod -Uri "$ApiRoot/api/v1/version" -TimeoutSec 10
    if ($version.environment -notin @("development", "test")) { throw "Refusing environment '$($version.environment)'." }
    $ready = Invoke-RestMethod -Uri "$ApiRoot/ready" -TimeoutSec 10
    if ($ready.status -ne "ready") { throw "VIP API is not ready." }
    $current = (docker exec vip-api-1 alembic current 2>$null | Select-Object -Last 1).Trim()
    $head = (docker exec vip-api-1 alembic heads 2>$null | Select-Object -Last 1).Trim()
    if (-not $current -or $current -ne $head -or $current -notmatch "\(head\)$") { throw "Migration state is not at a single head." }
    $verifyContainerPath = "/tmp/vip-stage4-safety-verification.dump"
    docker cp $resolvedBackup "vip-postgres-1:$verifyContainerPath" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not copy the verified backup for structural validation." }
    docker exec vip-postgres-1 pg_restore --list $verifyContainerPath | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "The verified backup is not readable by pg_restore." }
    foreach ($slug in @($demoSlugs + $configuration.legacyStage2.slug)) {
        if ($slug -notmatch "^[a-z0-9]+(?:-[a-z0-9]+)*$") { throw "Unsafe demo slug: $slug" }
        $count = (docker exec vip-postgres-1 psql -X -U vip -d vip -Atc "SELECT count(*) FROM organizations WHERE slug='$slug';").Trim()
        if ($count -notin @("0", "1")) { throw "Expected zero or one exact tenant for $slug, found $count." }
    }
    foreach ($schema in @($demoSchemas + $configuration.legacyStage2.schema)) {
        if ($schema -notmatch "^vip_demo_[a-z0-9_]+$") { throw "Unsafe demo schema: $schema" }
    }
    return [ordered]@{
        environment=$version.environment
        migration=$current
        backup=(Resolve-Path -LiteralPath $VerifiedBackupPath).Path
        backup_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $VerifiedBackupPath).Hash
    }
}

function New-DemoPassword {
    $bytes = [byte[]]::new(24)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return ([Convert]::ToBase64String($bytes) + "!V9")
}

function Protect-Json($Value, [string]$Path) {
    $json = $Value | ConvertTo-Json -Depth 20 -Compress
    $encrypted = ConvertFrom-SecureString (ConvertTo-SecureString $json -AsPlainText -Force)
    Set-Content -LiteralPath $Path -Value $encrypted -Encoding utf8
}

function Unprotect-Json([string]$Path) {
    $protected = (Get-Content -Raw -LiteralPath $Path).Trim()
    $plain = [System.Net.NetworkCredential]::new("", (ConvertTo-SecureString $protected)).Password
    return $plain | ConvertFrom-Json -Depth 30
}

function Get-OrCreateCredentials {
    New-Item -ItemType Directory -Force -Path $credentialRoot | Out-Null
    if (Test-Path -LiteralPath $credentialPath) {
        $userSecrets = Unprotect-Json $credentialPath
    } else {
        $userSecrets = [ordered]@{}
        foreach ($organization in $configuration.organizations) {
            foreach ($user in $organization.users) { $userSecrets[$user.username] = New-DemoPassword }
        }
        if (@($userSecrets.Values | Select-Object -Unique).Count -ne 24) { throw "Demo passwords must be unique." }
        Protect-Json $userSecrets $credentialPath
        $userSecrets = Unprotect-Json $credentialPath
    }
    if (Test-Path -LiteralPath $platformCredentialPath) {
        $platformSecret = Unprotect-Json $platformCredentialPath
    } else {
        if (-not $env:VIP_STAGE4_PLATFORM_PASSWORD) { throw "VIP_STAGE4_PLATFORM_PASSWORD is required for the initial secure setup." }
        $platformSecret = [ordered]@{ username=if($env:VIP_STAGE4_PLATFORM_USERNAME){$env:VIP_STAGE4_PLATFORM_USERNAME}else{"qa_platform_super_admin"}; password=$env:VIP_STAGE4_PLATFORM_PASSWORD }
        Protect-Json $platformSecret $platformCredentialPath
        $platformSecret = Unprotect-Json $platformCredentialPath
    }
    if (-not $env:VIP_STAGE4_POSTGRES_PASSWORD) { throw "VIP_STAGE4_POSTGRES_PASSWORD is required and is never stored in source." }
    return @{ users=$userSecrets; platform=$platformSecret }
}

function New-VipSession([string]$Username, [string]$Password) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ username=$Username; password=$Password } | ConvertTo-Json -Compress
    Invoke-RestMethod -Method Post -Uri "$ApiRoot/auth/login" -WebSession $session -ContentType "application/json" -Body $body | Out-Null
    return $session
}

function Invoke-VipApi {
    param(
        [Parameter(Mandatory)][Microsoft.PowerShell.Commands.WebRequestSession]$Session,
        [Parameter(Mandatory)][string]$Method,
        [Parameter(Mandatory)][string]$Path,
        [object]$Body=$null,
        [string]$OrganizationId="",
        [string]$WorkspaceId=""
    )
    $headers = @{ Origin="http://localhost:3009" }
    if ($OrganizationId) { $headers["X-Organization-ID"]=$OrganizationId }
    if ($WorkspaceId) { $headers["X-Workspace-ID"]=$WorkspaceId }
    if ($Method -notin @("Get","Head","Options")) { $headers["X-CSRF-Token"]=$Session.Cookies.GetCookies($ApiRoot)["vip_csrf_token"].Value }
    $arguments = @{ Method=$Method; Uri="$ApiRoot$Path"; WebSession=$Session; Headers=$headers; ContentType="application/json" }
    if ($null -ne $Body) { $arguments.Body=$Body | ConvertTo-Json -Depth 60 -Compress }
    return Invoke-RestMethod @arguments
}

function Invoke-VipFileUpload($Session, [string]$Path, [string]$OrganizationId, [string]$WorkspaceId) {
    $headers = @{
        Origin="http://localhost:3009"
        "X-Organization-ID"=$OrganizationId
        "X-Workspace-ID"=$WorkspaceId
        "X-CSRF-Token"=$Session.Cookies.GetCookies($ApiRoot)["vip_csrf_token"].Value
        "X-File-Name"=[System.IO.Path]::GetFileName($Path)
    }
    $extension=[System.IO.Path]::GetExtension($Path).ToLowerInvariant()
    $contentType=if($extension -eq ".xlsx"){"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}else{"text/csv"}
    return Invoke-RestMethod -Method Post -Uri "$ApiRoot/api/v1/files" -WebSession $Session -Headers $headers -ContentType $contentType -InFile $Path
}

function Remove-ExactTenant([string]$Slug, [string]$Schema) {
    if ($Slug -notmatch "^[a-z0-9]+(?:-[a-z0-9]+)*$") { throw "Unsafe tenant slug." }
    if ($Schema -notmatch "^vip_demo_[a-z0-9_]+$") { throw "Unsafe demo schema." }
    $count=(docker exec vip-postgres-1 psql -X -U vip -d vip -Atc "SELECT count(*) FROM organizations WHERE slug='$Slug';").Trim()
    if ($count -notin @("0","1")) { throw "Cleanup refused for ${Slug}: count $count." }
    if ($count -eq "1") {
        $sql="BEGIN; DELETE FROM dashboard_delivery_runs WHERE organization_id=(SELECT id FROM organizations WHERE slug='$Slug'); DELETE FROM dashboards WHERE organization_id=(SELECT id FROM organizations WHERE slug='$Slug'); DELETE FROM semantic_models WHERE organization_id=(SELECT id FROM organizations WHERE slug='$Slug'); DELETE FROM dataset_lineage_edges WHERE organization_id=(SELECT id FROM organizations WHERE slug='$Slug'); DELETE FROM datasets WHERE organization_id=(SELECT id FROM organizations WHERE slug='$Slug'); DELETE FROM pipeline_runs WHERE organization_id=(SELECT id FROM organizations WHERE slug='$Slug'); DELETE FROM invitations WHERE organization_id=(SELECT id FROM organizations WHERE slug='$Slug'); DELETE FROM workspace_memberships WHERE organization_id=(SELECT id FROM organizations WHERE slug='$Slug'); DELETE FROM organization_memberships WHERE organization_id=(SELECT id FROM organizations WHERE slug='$Slug'); DELETE FROM organizations WHERE slug='$Slug'; COMMIT;"
        docker exec vip-postgres-1 psql -X -v ON_ERROR_STOP=1 -U vip -d vip -c $sql | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Targeted tenant cleanup rolled back for $Slug." }
    }
    docker exec vip-postgres-1 psql -X -v ON_ERROR_STOP=1 -U vip -d vip -c "DROP SCHEMA IF EXISTS $Schema CASCADE;" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Targeted demo schema cleanup failed for $Schema." }
}

function Get-PlatformUser($PlatformSession, [string]$Username) {
    $items=(Invoke-VipApi -Session $PlatformSession -Method Get -Path "/api/v1/platform/users?page=1&page_size=100&search=$Username").items
    return $items | Where-Object username -eq $Username | Select-Object -First 1
}

function Wait-PipelineRun($Session, [string]$OrganizationId, [string]$WorkspaceId, $Pipeline, $Run) {
    $deadline=(Get-Date).AddMinutes(4)
    do {
        Start-Sleep -Seconds 2
        $Run=Invoke-VipApi -Session $Session -Method Get -Path "/api/v1/pipelines/$($Pipeline.id)/runs/$($Run.id)" -OrganizationId $OrganizationId -WorkspaceId $WorkspaceId
    } while ($Run.status -in @("queued","running") -and (Get-Date) -lt $deadline)
    if ($Run.status -ne "succeeded") { throw "Pipeline '$($Pipeline.name)' failed with status $($Run.status)." }
    return $Run
}

function Wait-DashboardExport($Session, [string]$OrganizationId, [string]$WorkspaceId, $Dashboard, [string]$Format) {
    $item=Invoke-VipApi -Session $Session -Method Post -Path "/api/v1/dashboards/$($Dashboard.id)/exports" -OrganizationId $OrganizationId -WorkspaceId $WorkspaceId -Body @{format=$Format;filters=@{};locale="en-US";timezone="Asia/Riyadh"}
    $deadline=(Get-Date).AddMinutes(4)
    do {
        Start-Sleep -Seconds 2
        $status=(docker exec vip-postgres-1 psql -X -U vip -d vip -Atc "SELECT status FROM dashboard_exports WHERE id='$($item.id)';").Trim()
    } while ($status -in @("queued","running","rendering") -and (Get-Date) -lt $deadline)
    if ($status -ne "completed") { throw "$Format export failed for $($Dashboard.name): $status" }
    return @{id=$item.id;status=$status;format=$Format}
}

function New-WorkspaceAssets($Organization, $Workspace, $AdminSession, $WorkspaceRow) {
    $orgId=$Organization.id.ToString(); $workspaceId=$WorkspaceRow.id.ToString()
    $scope=@{OrganizationId=$orgId;WorkspaceId=$workspaceId}
    $connection=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/connections" @scope -Body @{
        name="$($Workspace.name) — Demo PostgreSQL Landing"
        description="Environment-based local PostgreSQL landing zone for synthetic $($Workspace.department) demo data."
        connection_type="postgresql"
        configuration=@{host="postgres";port=5432;database="vip";username="vip";ssl_mode="disable";connect_timeout_seconds=10}
        credentials=@{password=$env:VIP_STAGE4_POSTGRES_PASSWORD}
    }
    $connectionTest=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/connections/$($connection.id)/test" @scope
    if ($connectionTest.status -ne "success") { throw "Connection test failed for $($Workspace.name)." }

    $csvName=[System.IO.Path]::ChangeExtension($Workspace.inputFile,".csv")
    $csvPath=Join-Path $generatedRoot $csvName
    $sourcePath=if($Workspace.sourceMode -eq "xlsx"){Join-Path $generatedRoot $Workspace.inputFile}else{$csvPath}
    if (-not (Test-Path -LiteralPath $sourcePath)) { throw "Missing source file: $sourcePath" }
    if ($Workspace.sourceMode -eq "postgresql") {
        $sourceResult=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/datasets/ingest-csv" @scope -Body @{
            connection_id=$connection.id;source_schema=$Organization.schema;source_name=$Workspace.sourceName;display_name=$Workspace.datasetName;description="SYNTHETIC DEMO DATA — $($Workspace.businessPurpose)";csv_content=Get-Content -Raw -LiteralPath $csvPath
        }
        $uploadedFile=$null
    } else {
        $uploadedFile=Invoke-VipFileUpload $AdminSession $sourcePath $orgId $workspaceId
        $sourceResult=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/datasets/ingest-file" @scope -Body @{
            file_id=$uploadedFile.id;connection_id=$connection.id;source_schema=$Organization.schema;source_name=$Workspace.sourceName;display_name=$Workspace.datasetName;description="SYNTHETIC DEMO DATA — $($Workspace.businessPurpose)"
        }
    }
    $rawDataset=$sourceResult.datasets[0]
    $lookupDataset=$null
    if ($Workspace.flagship) {
        $lookupResult=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/datasets/ingest-csv" @scope -Body @{
            connection_id=$connection.id;source_schema=$Organization.schema;source_name=$Workspace.lookupSourceName;display_name=$Workspace.lookupDatasetName;description="SYNTHETIC DEMO DATA — deterministic regional targets and benchmarks.";csv_content=Get-Content -Raw -LiteralPath (Join-Path $generatedRoot $Workspace.lookupFile)
        }
        $lookupDataset=$lookupResult.datasets[0]
    }

    $extraColumns=if($Workspace.flagship){", target_region text, target_value numeric(24,6), benchmark_score numeric(24,6), regional_lead text, variance_to_target numeric(24,6)"}else{""}
    $ddl="CREATE TABLE $($Organization.schema).$($Workspace.outputSourceName) (record_id text, event_date date, period text, region text, location text, category text, subcategory text, status text, owner_group text, quantity bigint, primary_value numeric(24,6), cost_value numeric(24,6), score numeric(24,6), cycle_hours numeric(24,6), sla_met text, risk_flag text, notes text$extraColumns);"
    docker exec vip-postgres-1 psql -X -v ON_ERROR_STOP=1 -U vip -d vip -c $ddl | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not create curated output table for $($Workspace.name)." }
    $outputDataset=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/datasets" @scope -Body @{
        connection_id=$connection.id;dataset_type="table";source_catalog="vip";source_schema=$Organization.schema;source_name=$Workspace.outputSourceName;display_name=$Workspace.outputDatasetName;description="Pipeline-governed synthetic demo output.";is_read_only=$false
    }
    Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/datasets/discover" @scope -Body @{connection_id=$connection.id;schemas=@($Organization.schema);include_object_types=@("table");include_names=@($Workspace.outputSourceName);persist=$true} | Out-Null

    $rawFields=Invoke-VipApi -Session $AdminSession -Method Get -Path "/api/v1/datasets/$($rawDataset.id)/fields" @scope
    $fieldByName=@{}; foreach($field in $rawFields){$fieldByName[$field.source_name]=$field}
    foreach($rule in @(
        @{field_id=$fieldByName.raw_record_id.id;rule_type="not_null";name="Business identifier is required";description="Every synthetic record requires a stable identifier.";configuration=@{};severity="error"},
        @{field_id=$fieldByName.metric_value.id;rule_type="range";name="Primary value is non-negative";description="Negative measures are rejected by the curation flow.";configuration=@{min=0};severity="error"},
        @{field_id=$fieldByName.region_name.id;rule_type="accepted_values";name="Region uses governed GCC demo values";description="Regions use the approved fictional operating list.";configuration=@{values=@("Central","Western","Eastern","Northern","Southern")};severity="warning"},
        @{field_id=$fieldByName.raw_record_id.id;rule_type="unique";name="Business identifier is unique";description="Duplicate identifiers are detected before curation.";configuration=@{};severity="error"}
    )) { Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/datasets/$($rawDataset.id)/quality-rules" @scope -Body $rule | Out-Null }
    $qualityJob=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/datasets/$($rawDataset.id)/quality-evaluations" @scope
    $profile=Invoke-VipApi -Session $AdminSession -Method Get -Path "/api/v1/datasets/$($rawDataset.id)/profile" @scope

    $selected=@("raw_record_id","event_date","period","region_name","location","category","subcategory","status","owner_group","quantity","metric_value","metric_cost","score","cycle_hours","sla_met","risk_flag","notes")
    $rename=[ordered]@{raw_record_id="record_id";region_name="region";metric_value="primary_value";metric_cost="cost_value"}
    $nodes=@(
        @{key="source";type="source-dataset";title="Synthetic Governed Source";x=0;y=0;config=@{source_type="dataset";dataset_id=$rawDataset.id;row_limit=5000}},
        @{key="select";type="select-columns";title="Select Business Fields";x=240;y=0;config=@{columns=$selected}},
        @{key="rename";type="rename-columns";title="Standardize Business Names";x=480;y=0;config=@{renames=$rename}},
        @{key="filter";type="filter";title="Reject Invalid Records";x=720;y=0;config=@{formula='not isempty([record_id]) and [primary_value] >= 0'}},
        @{key="nulls";type="null-handling";title="Treat Missing Regions";x=960;y=0;config=@{field="region";strategy="replace";value="Unassigned"}},
        @{key="normalize";type="formula";title="Normalize Region Names";x=1200;y=0;config=@{field="region";formula="title([region])"}},
        @{key="dedupe";type="deduplicate";title="Deduplicate Business IDs";x=1440;y=0;config=@{fields=@("record_id")}}
    )
    $edges=@(
        @{key="e1";source="source";target="select"},@{key="e2";source="select";target="rename"},@{key="e3";source="rename";target="filter"},@{key="e4";source="filter";target="nulls"},@{key="e5";source="nulls";target="normalize"},@{key="e6";source="normalize";target="dedupe"}
    )
    if ($Workspace.flagship) {
        $nodes += @(
            @{key="convert";type="type-convert";title="Confirm Numeric Measure";x=680;y=-180;config=@{field="primary_value";target_type="number"}},
            @{key="targets";type="source-dataset";title="Regional Targets";x=1440;y=260;config=@{source_type="dataset";dataset_id=$lookupDataset.id;row_limit=100}},
            @{key="join";type="join";title="Join Regional Targets";x=1680;y=0;config=@{left_field="region";right_field="target_region";join_type="left"}},
            @{key="variance";type="formula";title="Calculate Target Variance";x=1920;y=0;config=@{field="variance_to_target";formula="[primary_value] - [target_value]"}},
            @{key="quality";type="row-validation";title="Business Quality Gate";x=2160;y=0;config=@{rules=@(@{formula='[quantity] > 0';reason="Quantity must be positive"},@{formula='[score] >= 0';reason="Score cannot be negative"})}},
            @{key="sort";type="sort";title="Sort Recent Priority";x=2400;y=0;config=@{fields=@(@{field="event_date";direction="desc"})}},
            @{key="output";type="output-dataset";title="Curated Enterprise Output";x=2640;y=-100;config=@{dataset_id=$outputDataset.id;write_mode="replace"}},
            @{key="aggregate";type="aggregate";title="Regional Performance Summary";x=2640;y=160;config=@{group_by=@("region");aggregations=@(@{field="primary_value";operation="sum";alias="total_value"},@{field="record_id";operation="count";alias="record_count"})}},
            @{key="artifact";type="file-export";title="Protected Summary Artifact";x=2880;y=160;config=@{format="csv";filename="$($Workspace.key)-regional-summary.csv"}}
        )
        # Re-route rename through type conversion before filter.
        $edges = @($edges | Where-Object key -ne "e3")
        $edges += @(
            @{key="e3a";source="rename";target="convert"},@{key="e3b";source="convert";target="filter"},
            @{key="e7";source="dedupe";target="join"},@{key="e8";source="targets";target="join"},@{key="e9";source="join";target="variance"},@{key="e10";source="variance";target="quality"},@{key="e11";source="quality";target="sort"},@{key="e12";source="sort";target="output"},@{key="e13";source="sort";target="aggregate"},@{key="e14";source="aggregate";target="artifact"}
        )
    } else {
        $nodes += @(
            @{key="output";type="output-dataset";title="Curated Department Output";x=1680;y=-80;config=@{dataset_id=$outputDataset.id;write_mode="replace"}},
            @{key="aggregate";type="aggregate";title="Regional Department Summary";x=1680;y=140;config=@{group_by=@("region");aggregations=@(@{field="primary_value";operation="sum";alias="total_value"})}}
        )
        $edges += @(@{key="e7";source="dedupe";target="output"},@{key="e8";source="dedupe";target="aggregate"})
    }
    $pipelineEditor=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/pipelines" @scope -Body @{name=$Workspace.pipelineName;description=$Workspace.businessPurpose;tags=@("stage4-demo",$Organization.key,$Workspace.key);canvas=@{zoom=0.78;pan=@{x=20;y=160}};nodes=$nodes;edges=$edges}
    $pipeline=$pipelineEditor.pipeline
    $reopened=Invoke-VipApi -Session $AdminSession -Method Get -Path "/api/v1/pipelines/$($pipeline.id)" @scope
    $saved=Invoke-VipApi -Session $AdminSession -Method Put -Path "/api/v1/pipelines/$($pipeline.id)" @scope -Body @{expected_version=$reopened.pipeline.row_version;name=$pipeline.name;description=$Workspace.businessPurpose;tags=@("stage4-demo",$Organization.key,$Workspace.key);canvas=$reopened.canvas;nodes=$reopened.nodes;edges=$reopened.edges}
    $validation=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/pipelines/$($pipeline.id)/validate" @scope
    if (-not $validation.valid) { throw "Pipeline validation failed for $($Workspace.name): $($validation.errors | ConvertTo-Json -Depth 20 -Compress)" }
    Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/pipelines/$($pipeline.id)/publish" @scope -Body @{expected_version=$saved.pipeline.row_version;change_summary="Stage 4 deterministic enterprise demo"} | Out-Null
    $run=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/pipelines/$($pipeline.id)/runs" @scope -Body @{}
    $run=Wait-PipelineRun $AdminSession $orgId $workspaceId $pipeline $run

    $outputFields=Invoke-VipApi -Session $AdminSession -Method Get -Path "/api/v1/datasets/$($outputDataset.id)/fields" @scope
    $outputField=@{}; foreach($field in $outputFields){$outputField[$field.source_name]=$field}
    $semantic=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/semantic-models" @scope -Body @{key="$($Organization.key)_$($Workspace.key.Replace('-','_'))";name=$Workspace.semanticModelName;description=$Workspace.businessPurpose;primary_dataset_id=$outputDataset.id;timezone="Asia/Riyadh";currency="SAR"}
    foreach($dimension in @(
        @{key="date";field="event_date";name="Date";type="time";time=$true;granularities=@("day","month","quarter","year")},
        @{key="period";field="period";name="Period";type="categorical";time=$false;granularities=@()},
        @{key="region";field="region";name="Region";type="geographic";time=$false;granularities=@()},
        @{key="location";field="location";name=$Workspace.locationLabel;type="categorical";time=$false;granularities=@()},
        @{key="category";field="category";name=$Workspace.categoryLabel;type="categorical";time=$false;granularities=@()},
        @{key="status";field="status";name="Status";type="categorical";time=$false;granularities=@()}
    )) { Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/semantic-models/$($semantic.id)/dimensions" @scope -Body @{dataset_id=$outputDataset.id;field_id=$outputField[$dimension.field].id;key=$dimension.key;name=$dimension.name;dimension_type=$dimension.type;is_time_dimension=$dimension.time;time_granularities=$dimension.granularities;is_hidden=$false} | Out-Null }
    $measures=@{}
    foreach($measure in @(
        @{key="primary";field="primary_value";name=$Workspace.primaryMetricName;aggregation="sum"},@{key="cost";field="cost_value";name=$Workspace.costMetricName;aggregation="sum"},@{key="records";field="record_id";name=$Workspace.recordLabel;aggregation="count_distinct"},@{key="score";field="score";name=$Workspace.scoreMetricName;aggregation="average"},@{key="cycle";field="cycle_hours";name=$Workspace.cycleMetricName;aggregation="average"}
    )) { $measures[$measure.key]=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/semantic-models/$($semantic.id)/measures" @scope -Body @{dataset_id=$outputDataset.id;field_id=$outputField[$measure.field].id;key=$measure.key;name=$measure.name;aggregation=$measure.aggregation;is_hidden=$false} }
    foreach($metric in @(
        @{key="primary_total";name="Total $($Workspace.primaryMetricName)";measure="primary";unit="SAR"},@{key="cost_total";name="Total $($Workspace.costMetricName)";measure="cost";unit="SAR"},@{key="record_count";name="Total $($Workspace.recordLabel)";measure="records";unit="records"},@{key="average_score";name="Average $($Workspace.scoreMetricName)";measure="score";unit="score"},@{key="average_cycle";name="Average $($Workspace.cycleMetricName)";measure="cycle";unit="hours"}
    )) { Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/semantic-models/$($semantic.id)/metrics" @scope -Body @{key=$metric.key;name=$metric.name;metric_type="measure";base_measure_id=$measures[$metric.measure].id;unit=$metric.unit} | Out-Null }
    $semanticValidation=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/semantic-models/$($semantic.id)/validate" @scope
    if (-not $semanticValidation.valid) { throw "Semantic model validation failed for $($Workspace.name)." }
    Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/semantic-models/$($semantic.id)/publish" @scope | Out-Null

    $widgetCount=if($Workspace.flagship){9}else{6}; $widgetIds=1..$widgetCount | ForEach-Object {[guid]::NewGuid().ToString()}
    $widgets=@(
        @{id=$widgetIds[0];type="kpi";title="Total $($Workspace.primaryMetricName)";semantic_model_id=$semantic.id;query=@{metrics=@("primary_total");dimensions=@();filters=@();order_by=@();limit=1};config=@{number_style="currency";currency="SAR";decimals=0};layout=@{x=0;y=0;w=3;h=3}},
        @{id=$widgetIds[1];type="kpi";title="Total $($Workspace.recordLabel)";semantic_model_id=$semantic.id;query=@{metrics=@("record_count");dimensions=@();filters=@();order_by=@();limit=1};config=@{number_style="number";decimals=0};layout=@{x=3;y=0;w=3;h=3}},
        @{id=$widgetIds[2];type="kpi";title="Average $($Workspace.scoreMetricName)";semantic_model_id=$semantic.id;query=@{metrics=@("average_score");dimensions=@();filters=@();order_by=@();limit=1};config=@{number_style="number";decimals=1};layout=@{x=6;y=0;w=3;h=3}},
        @{id=$widgetIds[3];type="bar";title="$($Workspace.primaryMetricName) by Region";semantic_model_id=$semantic.id;query=@{metrics=@("primary_total");dimensions=@("region");filters=@();order_by=@(@{field="primary_total";direction="desc"});limit=10};config=@{currency="SAR";show_legend=$false};layout=@{x=0;y=3;w=6;h=5}},
        @{id=$widgetIds[4];type="line";title="$($Workspace.primaryMetricName) Trend";semantic_model_id=$semantic.id;query=@{metrics=@("primary_total");dimensions=@("period");filters=@();order_by=@(@{field="period";direction="asc"});limit=24};config=@{currency="SAR";show_gridlines=$true};layout=@{x=6;y=3;w=6;h=5}},
        @{id=$widgetIds[5];type="table";title="Regional Performance Detail";semantic_model_id=$semantic.id;query=@{metrics=@("primary_total","cost_total","record_count","average_score");dimensions=@("region");filters=@();order_by=@(@{field="primary_total";direction="desc"});limit=20};config=@{currency="SAR";columns=@("region","primary_total","cost_total","record_count","average_score")};layout=@{x=0;y=8;w=12;h=7}}
    )
    if ($Workspace.flagship) {
        $widgets += @(
            @{id=$widgetIds[6];type="kpi";title="Average $($Workspace.cycleMetricName)";semantic_model_id=$semantic.id;query=@{metrics=@("average_cycle");dimensions=@();filters=@();order_by=@();limit=1};config=@{number_style="number";decimals=1};layout=@{x=9;y=0;w=3;h=3}},
            @{id=$widgetIds[7];type="donut";title="$($Workspace.primaryMetricName) by $($Workspace.categoryLabel)";semantic_model_id=$semantic.id;query=@{metrics=@("primary_total");dimensions=@("category");filters=@();order_by=@(@{field="primary_total";direction="desc"});limit=10};config=@{currency="SAR";show_legend=$true};layout=@{x=0;y=15;w=6;h=5}},
            @{id=$widgetIds[8];type="column";title="$($Workspace.costMetricName) by Status";semantic_model_id=$semantic.id;query=@{metrics=@("cost_total");dimensions=@("status");filters=@();order_by=@(@{field="cost_total";direction="desc"});limit=10};config=@{currency="SAR"};layout=@{x=6;y=15;w=6;h=5}}
        )
    }
    $dashboard=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/dashboards" @scope -Body @{name=$Workspace.dashboardName;description=$Workspace.businessPurpose;slug="$($Organization.key)-$($Workspace.key)-dashboard";tags=@("stage4-demo",$Organization.key,$Workspace.key)}
    $dashboardEditor=Invoke-VipApi -Session $AdminSession -Method Get -Path "/api/v1/dashboards/$($dashboard.id)/editor" @scope
    $dashboardEditor=Invoke-VipApi -Session $AdminSession -Method Put -Path "/api/v1/dashboards/$($dashboard.id)/editor" @scope -Body @{expected_version=$dashboardEditor.version;name=$Workspace.dashboardName;description=$Workspace.businessPurpose;tags=@("stage4-demo",$Organization.key,$Workspace.key);pages=@(@{key="overview";name="Overview";description=$Workspace.businessPurpose;position=0;canvas=@{columns=12;row_height=72};widgets=$widgets});filters=@(@{key="date";label="Date";type="date_range";semantic_model_id=$semantic.id;dimension_key="date";operator="between";widget_ids=$widgetIds;position=0},@{key="region";label="Region";type="multi_select";semantic_model_id=$semantic.id;dimension_key="region";operator="in";widget_ids=$widgetIds;position=1},@{key="category";label=$Workspace.categoryLabel;type="multi_select";semantic_model_id=$semantic.id;dimension_key="category";operator="in";widget_ids=$widgetIds;position=2},@{key="status";label="Status";type="multi_select";semantic_model_id=$semantic.id;dimension_key="status";operator="in";widget_ids=$widgetIds;position=3});change_summary="Stage 4 enterprise demo layout"}
    Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/dashboards/$($dashboard.id)/publish" @scope -Body @{expected_version=$dashboardEditor.version;change_summary="Stage 4 published demo dashboard"} | Out-Null
    $exports=@(); $schedule=$null
    if ($Workspace.flagship) {
        $exports+=Wait-DashboardExport $AdminSession $orgId $workspaceId $dashboard "pdf"
        $exports+=Wait-DashboardExport $AdminSession $orgId $workspaceId $dashboard "png"
        $schedule=Invoke-VipApi -Session $AdminSession -Method Post -Path "/api/v1/dashboards/$($dashboard.id)/deliveries" @scope -Body @{name="$($Organization.name) Weekly Flagship Brief";recipients=@("demo.delivery@example.com");cc=@();bcc=@();subject=$Workspace.dashboardName;format="pdf";filters=@{};schedule_type="weekly";timezone="Asia/Riyadh";include_dashboard_link=$true;enabled=$false;max_retries=1}
    }
    $datasetManifest=@(@{id=$rawDataset.id;name=$rawDataset.display_name;kind="raw"},@{id=$outputDataset.id;name=$outputDataset.display_name;kind="curated"})
    if($lookupDataset){$datasetManifest+=@{id=$lookupDataset.id;name=$lookupDataset.display_name;kind="lookup"}}
    return [ordered]@{
        workspace_id=$workspaceId;connection=@{id=$connection.id;name=$connection.name;status=$connectionTest.status};upload=if($uploadedFile){@{id=$uploadedFile.id;filename=$uploadedFile.filename}}else{$null};datasets=$datasetManifest;quality=@{evaluation_id=$qualityJob.id;profile_rows=$profile.row_count};pipeline=@{id=$pipeline.id;name=$pipeline.name;status=$run.status;rows_processed=$run.rows_processed};semantic_model=@{id=$semantic.id;name=$semantic.name;status="published"};dashboard=@{id=$dashboard.id;name=$dashboard.name;status="published";exports=$exports;schedule=$schedule}
    }
}

$safety=Assert-SafeEnvironment
$preview=[ordered]@{mode=$Mode;target_environment=$safety.environment;backup=$safety.backup;organizations=@();cleanup=@()}
foreach($slug in $demoSlugs){$preview.cleanup+=@{slug=$slug;existing=(docker exec vip-postgres-1 psql -X -U vip -d vip -Atc "SELECT count(*) FROM organizations WHERE slug='$slug';").Trim()}}
if($IncludeLegacyStage2Cleanup){$preview.cleanup+=@{slug=$configuration.legacyStage2.slug;existing=(docker exec vip-postgres-1 psql -X -U vip -d vip -Atc "SELECT count(*) FROM organizations WHERE slug='$($configuration.legacyStage2.slug)';").Trim()}}
foreach($org in $configuration.organizations){$preview.organizations+=@{slug=$org.slug;workspaces=$org.workspaces.Count;users=$org.users.Count;sources=@($org.workspaces.sourceMode)}}
if($Mode -eq "DryRun"){$preview | ConvertTo-Json -Depth 20; exit 0}

New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null
& (Join-Path $PSScriptRoot "generate-synthetic-data.ps1") -OutputRoot $generatedRoot | Out-Null
$secrets=Get-OrCreateCredentials
$platformSession=New-VipSession $secrets.platform.username $secrets.platform.password
if($IncludeLegacyStage2Cleanup){Remove-ExactTenant $configuration.legacyStage2.slug $configuration.legacyStage2.schema}
foreach($index in 0..($demoSlugs.Count-1)){Remove-ExactTenant $demoSlugs[$index] $demoSchemas[$index]}

$environment=[ordered]@{generated_at=(Get-Date).ToUniversalTime().ToString("o");baseline=$safety;organizations=@();credential_store=$credentialPath;platform_credential_store=$platformCredentialPath}
foreach($orgDefinition in $configuration.organizations){
    $organization=Invoke-VipApi -Session $platformSession -Method Post -Path "/api/v1/platform/organizations" -Body @{name=$orgDefinition.name;slug=$orgDefinition.slug}
    $orgDefinition | Add-Member -NotePropertyName id -NotePropertyValue $organization.id -Force
    $defaultWorkspace=$organization.workspaces | Where-Object is_default | Select-Object -First 1
    $firstDefinition=$orgDefinition.workspaces[0]
    $renamedDefault=Invoke-VipApi -Session $platformSession -Method Patch -Path "/api/v1/organizations/$($organization.id)/workspaces/$($defaultWorkspace.id)" -Body @{name=$firstDefinition.name;slug=$firstDefinition.slug} -OrganizationId $organization.id -WorkspaceId $defaultWorkspace.id
    $workspaceRows=[ordered]@{$firstDefinition.key=$renamedDefault}
    foreach($workspaceDefinition in @($orgDefinition.workspaces | Select-Object -Skip 1)){
        $workspaceRows[$workspaceDefinition.key]=Invoke-VipApi -Session $platformSession -Method Post -Path "/api/v1/platform/organizations/$($organization.id)/workspaces" -Body @{name=$workspaceDefinition.name;slug=$workspaceDefinition.slug}
    }
    $userRows=[ordered]@{}
    foreach($userDefinition in $orgDefinition.users){
        $user=Get-PlatformUser $platformSession $userDefinition.username
        if($user){
            Invoke-VipApi -Session $platformSession -Method Post -Path "/api/v1/platform/users/$($user.id)/activate" | Out-Null
            Invoke-VipApi -Session $platformSession -Method Post -Path "/api/v1/platform/users/$($user.id)/reset-password" -Body @{password=$secrets.users.($userDefinition.username);must_change_password=$false} | Out-Null
            Invoke-VipApi -Session $platformSession -Method Post -Path "/api/v1/platform/organizations/$($organization.id)/members" -Body @{username=$userDefinition.username;organization_role=$userDefinition.orgRole} | Out-Null
        } else {
            $user=Invoke-VipApi -Session $platformSession -Method Post -Path "/api/v1/platform/users" -Body @{username=$userDefinition.username;email=$userDefinition.email;display_name=$userDefinition.displayName;password=$secrets.users.($userDefinition.username);is_platform_admin=$false;organization_id=$organization.id;organization_role=$userDefinition.orgRole}
        }
        $userRows[$userDefinition.key]=$user
        foreach($access in $userDefinition.access.PSObject.Properties){
            $workspace=$workspaceRows[$access.Name]
            Invoke-VipApi -Session $platformSession -Method Post -Path "/api/v1/platform/organizations/$($organization.id)/workspaces/$($workspace.id)/members" -Body @{username=$userDefinition.username;workspace_role=$access.Value} | Out-Null
        }
    }
    $adminDefinition=$orgDefinition.users | Where-Object key -eq "org-admin" | Select-Object -First 1
    $adminSession=New-VipSession $adminDefinition.username $secrets.users.($adminDefinition.username)
    docker exec vip-postgres-1 psql -X -v ON_ERROR_STOP=1 -U vip -d vip -c "CREATE SCHEMA $($orgDefinition.schema);" | Out-Null
    if($LASTEXITCODE -ne 0){throw "Could not create exact demo schema $($orgDefinition.schema)."}
    $orgManifest=[ordered]@{id=$organization.id;key=$orgDefinition.key;name=$orgDefinition.name;slug=$orgDefinition.slug;industry=$orgDefinition.industry;story=$orgDefinition.story;workspaces=@();users=@()}
    foreach($workspaceDefinition in $orgDefinition.workspaces){
        $workspaceRow=$workspaceRows[$workspaceDefinition.key]
        $assets=New-WorkspaceAssets $orgDefinition $workspaceDefinition $adminSession $workspaceRow
        $orgManifest.workspaces+=@{id=$workspaceRow.id;key=$workspaceDefinition.key;name=$workspaceDefinition.name;slug=$workspaceDefinition.slug;department=$workspaceDefinition.department;flagship=$workspaceDefinition.flagship;source_mode=$workspaceDefinition.sourceMode;assets=$assets}
    }
    foreach($userDefinition in $orgDefinition.users){$orgManifest.users+=@{id=$userRows[$userDefinition.key].id;username=$userDefinition.username;email=$userDefinition.email;display_name=$userDefinition.displayName;organization_role=$userDefinition.orgRole;access=$userDefinition.access;purpose=$userDefinition.purpose}}
    $environment.organizations+=$orgManifest
}

# Remove the bootstrap platform operator from tenant memberships after the
# organization admins have been created and the assets have been verified.
$platformUser=Get-PlatformUser $platformSession $secrets.platform.username
foreach($organizationRow in $environment.organizations){
    Invoke-VipApi -Session $platformSession -Method Delete -Path "/api/v1/platform/organizations/$($organizationRow.id)/members/by-user/$($platformUser.id)" | Out-Null
}

# Final security posture: every generally shareable demo password is temporary and must be changed.
foreach($orgDefinition in $configuration.organizations){foreach($userDefinition in $orgDefinition.users){$user=Get-PlatformUser $platformSession $userDefinition.username;Invoke-VipApi -Session $platformSession -Method Post -Path "/api/v1/platform/users/$($user.id)/reset-password" -Body @{password=$secrets.users.($userDefinition.username);must_change_password=$true} | Out-Null}}
if($IncludeLegacyStage2Cleanup){foreach($username in $configuration.legacyStage2.usernames){$legacy=Get-PlatformUser $platformSession $username;if($legacy){Invoke-VipApi -Session $platformSession -Method Post -Path "/api/v1/platform/users/$($legacy.id)/suspend" | Out-Null}}}
$environment | ConvertTo-Json -Depth 60 | Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Output "organizations=$($environment.organizations.Count)"
Write-Output "workspaces=$(@($environment.organizations.workspaces).Count)"
Write-Output "users=$(@($environment.organizations.users).Count)"
Write-Output "manifest=$manifestPath"
Write-Output "credential_store=$credentialPath"
