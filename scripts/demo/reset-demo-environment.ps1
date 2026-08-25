param(
    [ValidateSet("DryRun", "Apply")][string]$Mode = "DryRun",
    [string]$ApiRoot = "http://localhost:8000",
    [string]$VerifiedBackupPath = "",
    [switch]$ConfirmNonProduction,
    [switch]$SkipReprovision
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$allowlistPath = Join-Path $repositoryRoot "demo-data\stage2\cleanup-allowlist.json"
$configuration = Get-Content -Raw -LiteralPath $allowlistPath | ConvertFrom-Json -Depth 20
$platformCredentialPath = Join-Path $env:LOCALAPPDATA "Veltrix\VIP\stage4\platform-operator.dpapi"

function Invoke-CheckedNative([scriptblock]$Command, [string]$FailureMessage) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw $FailureMessage }
}

function Quote-SqlLiteral([string]$Value) {
    return "'" + $Value.Replace("'", "''") + "'"
}

function Get-DatabaseLines([string]$Sql) {
    $output = docker compose exec -T postgres psql -X -U vip -d vip -At -v ON_ERROR_STOP=1 -c $Sql
    if ($LASTEXITCODE -ne 0) { throw "Database inspection failed." }
    return @($output | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
}

function Assert-ExactSubset([string]$Label, [string[]]$Actual, [string[]]$Allowed) {
    $unexpected = @($Actual | Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and $_ -notin $Allowed })
    if ($unexpected.Count -gt 0) {
        throw "$Label contains unreviewed values; cleanup refused: $($unexpected -join ', ')"
    }
}

function Assert-SafeEnvironment {
    if ($env:APP_ENV -ne "demo") { throw "Set APP_ENV=demo explicitly." }
    if ($env:ALLOW_DEMO_RESET -ne "true") { throw "Set ALLOW_DEMO_RESET=true explicitly." }
    if (-not $ConfirmNonProduction) { throw "Pass -ConfirmNonProduction after verifying the local target." }
    if (-not $VerifiedBackupPath) { throw "A restore-verified PostgreSQL backup is required." }
    $backup = Resolve-Path -LiteralPath $VerifiedBackupPath -ErrorAction Stop
    if ((Get-Item -LiteralPath $backup).Length -lt 1MB) { throw "The backup is unexpectedly small." }

    $uri = [Uri]$ApiRoot
    if ($uri.Scheme -ne "http" -or $uri.Host -notin @("localhost", "127.0.0.1", "::1")) {
        throw "ApiRoot must be an explicit local HTTP endpoint."
    }
    $version = Invoke-RestMethod -Uri "$ApiRoot/api/v1/version" -TimeoutSec 10
    if ($version.environment -notin @("development", "test")) {
        throw "Refusing API environment '$($version.environment)'."
    }
    $ready = Invoke-RestMethod -Uri "$ApiRoot/ready" -TimeoutSec 10
    if ($ready.status -ne "ready") { throw "VIP API is not ready." }

    $identity = @(Get-DatabaseLines "SELECT current_database()||'|'||coalesce(inet_server_addr()::text,'local')||'|'||current_user;")[0] -split '\|'
    if ($identity[0] -ne "vip" -or $identity[2] -ne "vip") { throw "Unexpected database identity." }
    $containerName = (docker compose ps -q postgres | ForEach-Object { docker inspect --format '{{.Name}}' $_ }).TrimStart('/')
    if ($containerName -ne "vip-postgres-1") { throw "Unexpected PostgreSQL container '$containerName'." }

    $containerBackup = "/tmp/vip-stage2-safety-backup.dump"
    Invoke-CheckedNative { docker cp $backup "vip-postgres-1:$containerBackup" | Out-Null } "Could not copy the verified backup."
    Invoke-CheckedNative { docker compose exec -T postgres pg_restore --list $containerBackup | Out-Null } "Backup is not structurally readable."
    docker compose exec -T postgres rm -f $containerBackup | Out-Null

    $current = (docker compose exec -T api alembic current 2>$null | Select-Object -Last 1).Trim()
    $head = (docker compose exec -T api alembic heads 2>$null | Select-Object -Last 1).Trim()
    if (-not $current -or $current -ne $head -or $current -notmatch "\(head\)$") {
        throw "Migrations must be at one Alembic head."
    }
    return [ordered]@{ api_environment=$version.environment; database=$identity[0]; server=$identity[1]; migration=$current; backup=$backup.Path }
}

function Get-CleanupInventory {
    $retained = @($configuration.retainedOrganizationSlugs)
    $retainedSql = ($retained | ForEach-Object { Quote-SqlLiteral $_ }) -join ','
    $organizations = Get-DatabaseLines "SELECT slug FROM organizations WHERE slug NOT IN ($retainedSql) ORDER BY slug;"
    $users = Get-DatabaseLines "SELECT username FROM users WHERE username <> 'vip.demo.platform.admin' AND username <> 'qa_platform_super_admin' AND username NOT LIKE 'northstar.%' AND username NOT LIKE 'crestline.%' AND username NOT LIKE 'meridian.%' ORDER BY username;"
    $schemas = Get-DatabaseLines "SELECT nspname FROM pg_namespace WHERE nspname NOT IN ('pg_catalog','information_schema','public','vip_demo_northstar','vip_demo_crestline','vip_demo_meridian') AND nspname NOT LIKE 'pg_toast%' AND nspname NOT LIKE 'pg_temp_%' ORDER BY nspname;"
    $tables = Get-DatabaseLines "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'b85_ui_source_%' OR tablename LIKE 'vip_b5_b85_ui_source_%' OR tablename LIKE 'vip_b5_cert_dashboard_%' OR tablename LIKE 'vip_b5_cert_pipeline_%' OR tablename='vip_b5_sales_demo') ORDER BY tablename;"
    Assert-ExactSubset "Organizations" $organizations @($configuration.approvedOrganizationSlugs)
    Assert-ExactSubset "Users" $users @($configuration.approvedUsernames)
    Assert-ExactSubset "Schemas" $schemas @($configuration.approvedSchemas)
    foreach ($table in $tables) {
        if (-not (@($configuration.approvedPublicTablePatterns | Where-Object { $table -match $_ }).Count)) {
            throw "Public table '$table' is not approved for cleanup."
        }
    }
    return [ordered]@{ organizations=$organizations; users=$users; schemas=$schemas; public_tables=$tables }
}

function Update-PlatformCredentialIdentity {
    if (-not (Test-Path -LiteralPath $platformCredentialPath)) { throw "Protected platform credential store is missing." }
    $protected = (Get-Content -Raw -LiteralPath $platformCredentialPath).Trim()
    $plain = [System.Net.NetworkCredential]::new("", (ConvertTo-SecureString $protected)).Password
    $credential = $plain | ConvertFrom-Json -Depth 10
    if ($credential.username -eq "qa_platform_super_admin") {
        $credential.username = "vip.demo.platform.admin"
        $encrypted = ConvertFrom-SecureString (ConvertTo-SecureString ($credential | ConvertTo-Json -Compress) -AsPlainText -Force)
        Set-Content -LiteralPath $platformCredentialPath -Value $encrypted -Encoding utf8
    } elseif ($credential.username -ne "vip.demo.platform.admin") {
        throw "Protected platform credential has an unexpected username."
    }
}

function Remove-ApprovedQaState($Inventory) {
    $orgSql = (@($Inventory.organizations) | ForEach-Object { Quote-SqlLiteral $_ }) -join ','
    $userSql = (@($Inventory.users) | ForEach-Object { Quote-SqlLiteral $_ }) -join ','
    $statements = [System.Collections.Generic.List[string]]::new()
    $statements.Add("BEGIN;")
    $statements.Add("SET LOCAL synchronous_commit=off;")
    if ($orgSql) {
        $statements.Add("CREATE TEMP TABLE purge_orgs AS SELECT id FROM organizations WHERE slug IN ($orgSql);")
        $statements.Add("DELETE FROM dashboard_delivery_runs WHERE organization_id IN (SELECT id FROM purge_orgs);")
        $statements.Add("DELETE FROM dashboards WHERE organization_id IN (SELECT id FROM purge_orgs);")
        $statements.Add("DELETE FROM semantic_models WHERE organization_id IN (SELECT id FROM purge_orgs);")
        $statements.Add("DELETE FROM dataset_lineage_edges WHERE organization_id IN (SELECT id FROM purge_orgs);")
        $statements.Add("DELETE FROM datasets WHERE organization_id IN (SELECT id FROM purge_orgs);")
        $statements.Add("DELETE FROM pipeline_runs WHERE organization_id IN (SELECT id FROM purge_orgs);")
        $statements.Add("DELETE FROM invitations WHERE organization_id IN (SELECT id FROM purge_orgs);")
        $statements.Add("DELETE FROM workspace_memberships WHERE organization_id IN (SELECT id FROM purge_orgs);")
        $statements.Add("DELETE FROM organization_memberships WHERE organization_id IN (SELECT id FROM purge_orgs);")
        $statements.Add("DELETE FROM organizations WHERE id IN (SELECT id FROM purge_orgs);")
    }
    if ($userSql) { $statements.Add("DELETE FROM users WHERE username IN ($userSql);") }
    $statements.Add("UPDATE users SET username='vip.demo.platform.admin', normalized_username='vip.demo.platform.admin', email='vip.demo.platform.admin@example.com', normalized_email='vip.demo.platform.admin@example.com', display_name='VIP Demo Platform Administrator', job_title='Demo Platform Administrator', department='Platform Operations', updated_at=now() WHERE username='qa_platform_super_admin' AND NOT EXISTS (SELECT 1 FROM users WHERE username='vip.demo.platform.admin');")
    $statements.Add("COMMIT;")
    $sql = $statements -join "`n"
    $sql | docker compose exec -T postgres psql -X -U vip -d vip -v ON_ERROR_STOP=1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Tenant/user cleanup failed and was rolled back." }

    foreach ($schema in @($Inventory.schemas)) {
        if ($schema -notin @($configuration.approvedSchemas)) { throw "Unsafe schema target '$schema'." }
        Invoke-CheckedNative { docker compose exec -T postgres psql -X -U vip -d vip -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS `"$schema`" CASCADE;" | Out-Null } "Schema cleanup failed."
    }
    foreach ($table in @($Inventory.public_tables)) {
        if ($table -notmatch '^[a-z0-9_]+$') { throw "Unsafe table target '$table'." }
        Invoke-CheckedNative { docker compose exec -T postgres psql -X -U vip -d vip -v ON_ERROR_STOP=1 -c "DROP TABLE IF EXISTS public.`"$table`" CASCADE;" | Out-Null } "Table cleanup failed."
    }
    Update-PlatformCredentialIdentity
}

$safety = Assert-SafeEnvironment
$inventory = Get-CleanupInventory
$preview = [ordered]@{
    mode=$Mode
    safety=$safety
    cleanup_counts=[ordered]@{ organizations=@($inventory.organizations).Count; users=@($inventory.users).Count; schemas=@($inventory.schemas).Count; public_tables=@($inventory.public_tables).Count }
    cleanup_targets=$inventory
}
$preview | ConvertTo-Json -Depth 10
if ($Mode -eq "DryRun") { exit 0 }

Remove-ApprovedQaState $inventory
if (-not $SkipReprovision) {
    if (-not $env:VIP_STAGE4_POSTGRES_PASSWORD -and $env:VIP_DEMO_POSTGRES_PASSWORD) {
        $env:VIP_STAGE4_POSTGRES_PASSWORD = $env:VIP_DEMO_POSTGRES_PASSWORD
    }
    if (-not $env:VIP_STAGE4_POSTGRES_PASSWORD) { throw "Set VIP_DEMO_POSTGRES_PASSWORD (or VIP_STAGE4_POSTGRES_PASSWORD) without committing it." }
    $env:VIP_DEMO_ENVIRONMENT = "stage4"
    $env:VIP_STAGE4_BACKUP_VERIFIED = "TRUE"
    & (Join-Path $repositoryRoot "scripts\demo-stage4\provision-enterprise-demo.ps1") -Mode Apply -ApiRoot $ApiRoot -VerifiedBackupPath $VerifiedBackupPath -ConfirmNonProduction
    if ($LASTEXITCODE -ne 0) { throw "Demo reprovisioning failed." }
}
& (Join-Path $repositoryRoot "scripts\demo-stage4\validate-enterprise-demo.ps1") -ApiRoot $ApiRoot
if ($LASTEXITCODE -ne 0) { throw "Demo validation failed." }

$final = @(Get-DatabaseLines "SELECT (SELECT count(*) FROM organizations)||'|'||(SELECT count(*) FROM workspaces)||'|'||(SELECT count(*) FROM users)||'|'||(SELECT count(*) FROM connections)||'|'||(SELECT count(*) FROM datasets)||'|'||(SELECT count(*) FROM pipelines)||'|'||(SELECT count(*) FROM semantic_models)||'|'||(SELECT count(*) FROM dashboards);")
"FINAL_COUNTS organizations|workspaces|users|connections|datasets|pipelines|semantic_models|dashboards=$($final[0])"
