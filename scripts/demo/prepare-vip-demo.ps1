param(
    [string]$ApiRoot = "http://localhost:8000",
    [switch]$ResetExistingTenant
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$csvPath = Join-Path $repositoryRoot "demo-data\vip_demo_sales_orders.csv"
$artifactRoot = Join-Path $repositoryRoot "artifacts\demo-stage2"
$credentialRoot = Join-Path $env:LOCALAPPDATA "Veltrix\VIP"
$credentialPath = Join-Path $credentialRoot "demo-credentials.dpapi"
$manifestPath = Join-Path $artifactRoot "environment-manifest.json"
$demoSlug = "veltrix-demo-organization"
$demoSchema = "vip_demo_sales"

New-Item -ItemType Directory -Force -Path $artifactRoot, $credentialRoot | Out-Null
& (Join-Path $PSScriptRoot "generate-vip-demo-data.ps1") -OutputPath $csvPath | Out-Null

function New-DemoPassword {
    $bytes = [byte[]]::new(24)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return ([Convert]::ToBase64String($bytes) + "!V9")
}

if (Test-Path -LiteralPath $credentialPath) {
    $protected = (Get-Content -Raw -LiteralPath $credentialPath).Trim()
    $plain = [System.Net.NetworkCredential]::new("", (ConvertTo-SecureString $protected)).Password
    $credentials = $plain | ConvertFrom-Json
} else {
    $credentials = [pscustomobject]@{
        bootstrap = New-DemoPassword
        admin = New-DemoPassword
        editor = New-DemoPassword
        viewer = New-DemoPassword
    }
    $credentialJson = $credentials | ConvertTo-Json -Compress
    $encrypted = ConvertFrom-SecureString (ConvertTo-SecureString $credentialJson -AsPlainText -Force)
    Set-Content -LiteralPath $credentialPath -Value $encrypted -Encoding utf8
}

$env:DATABASE_URL = "postgresql+asyncpg://vip:vip_local_dev_only@localhost:5432/vip"
$env:REDIS_URL = "redis://localhost:6379/0"
$credentials.bootstrap | & (Join-Path $repositoryRoot "apps\api\.venv\Scripts\python.exe") (Join-Path $repositoryRoot "apps\api\scripts\reset-qa-bootstrap-password.py") --username qa_platform_super_admin | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not recover the local QA bootstrap operator." }

if ($ResetExistingTenant) {
    $count = docker exec vip-postgres-1 psql -U vip -d vip -Atc "SELECT count(*) FROM organizations WHERE slug='$demoSlug';"
    if ($count -notin @("0", "1")) { throw "Reset refused: expected zero or one exact demo tenant, found $count." }
    if ($count -eq "1") {
        $tenantPurge = "BEGIN; DELETE FROM dashboard_delivery_runs WHERE organization_id=(SELECT id FROM organizations WHERE slug='$demoSlug'); DELETE FROM dashboards WHERE organization_id=(SELECT id FROM organizations WHERE slug='$demoSlug'); DELETE FROM semantic_models WHERE organization_id=(SELECT id FROM organizations WHERE slug='$demoSlug'); DELETE FROM dataset_lineage_edges WHERE organization_id=(SELECT id FROM organizations WHERE slug='$demoSlug'); DELETE FROM datasets WHERE organization_id=(SELECT id FROM organizations WHERE slug='$demoSlug'); DELETE FROM pipeline_runs WHERE organization_id=(SELECT id FROM organizations WHERE slug='$demoSlug'); DELETE FROM invitations WHERE organization_id=(SELECT id FROM organizations WHERE slug='$demoSlug'); DELETE FROM workspace_memberships WHERE organization_id=(SELECT id FROM organizations WHERE slug='$demoSlug'); DELETE FROM organization_memberships WHERE organization_id=(SELECT id FROM organizations WHERE slug='$demoSlug'); DELETE FROM organizations WHERE slug='$demoSlug'; COMMIT;"
        docker exec vip-postgres-1 psql -v ON_ERROR_STOP=1 -U vip -d vip -c $tenantPurge | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Tenant reset failed; the transaction was rolled back." }
    }
} else {
    $count = docker exec vip-postgres-1 psql -U vip -d vip -Atc "SELECT count(*) FROM organizations WHERE slug='$demoSlug';"
    if ($count -ne "0") { throw "The exact demo tenant already exists. Re-run with -ResetExistingTenant to rebuild only that tenant." }
}

function New-VipSession([string]$Username, [string]$Password) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ username = $Username; password = $Password } | ConvertTo-Json -Compress
    Invoke-RestMethod -Method Post -Uri "$ApiRoot/auth/login" -WebSession $session -ContentType "application/json" -Body $body | Out-Null
    return $session
}

function Invoke-VipApi {
    param(
        [Parameter(Mandatory)][Microsoft.PowerShell.Commands.WebRequestSession]$Session,
        [Parameter(Mandatory)][string]$Method,
        [Parameter(Mandatory)][string]$Path,
        [object]$Body = $null,
        [string]$OrganizationId = "",
        [string]$WorkspaceId = ""
    )
    $headers = @{ Origin = "http://localhost:3009" }
    if ($OrganizationId) { $headers["X-Organization-ID"] = $OrganizationId }
    if ($WorkspaceId) { $headers["X-Workspace-ID"] = $WorkspaceId }
    if ($Method -notin @("Get", "Head", "Options")) {
        $headers["X-CSRF-Token"] = $Session.Cookies.GetCookies($ApiRoot)["vip_csrf_token"].Value
    }
    $arguments = @{
        Method = $Method
        Uri = "$ApiRoot$Path"
        WebSession = $Session
        Headers = $headers
        ContentType = "application/json"
    }
    if ($null -ne $Body) { $arguments.Body = $Body | ConvertTo-Json -Depth 40 -Compress }
    return Invoke-RestMethod @arguments
}

$platform = New-VipSession "qa_platform_super_admin" $credentials.bootstrap
$organization = Invoke-VipApi -Session $platform -Method Post -Path "/api/v1/platform/organizations" -Body @{
    name = "Veltrix Demo Organization"
    slug = $demoSlug
}

$personas = @(
    @{ key = "admin"; username = "demo.organization.admin"; email = "demo.admin@vip.example"; display = "Veltrix Demo Administrator"; orgRole = "organization_admin"; wsRole = "workspace_admin" },
    @{ key = "editor"; username = "demo.sales.editor"; email = "demo.editor@vip.example"; display = "Veltrix Demo Editor"; orgRole = "organization_member"; wsRole = "editor" },
    @{ key = "viewer"; username = "demo.executive.viewer"; email = "demo.viewer@vip.example"; display = "Veltrix Executive Viewer"; orgRole = "organization_member"; wsRole = "viewer" }
)
$userRows = [ordered]@{}
foreach ($persona in $personas) {
    $existing = (Invoke-VipApi -Session $platform -Method Get -Path "/api/v1/platform/users?page=1&page_size=100&search=$($persona.username)").items | Where-Object username -eq $persona.username | Select-Object -First 1
    if ($existing) {
        Invoke-VipApi -Session $platform -Method Post -Path "/api/v1/platform/users/$($existing.id)/reset-password" -Body @{ password = $credentials.($persona.key); must_change_password = $false } | Out-Null
        Invoke-VipApi -Session $platform -Method Post -Path "/api/v1/platform/organizations/$($organization.id)/members" -Body @{ username = $persona.username; organization_role = $persona.orgRole } | Out-Null
        $userRows[$persona.key] = $existing
    } else {
        $userRows[$persona.key] = Invoke-VipApi -Session $platform -Method Post -Path "/api/v1/platform/users" -Body @{
            username = $persona.username
            email = $persona.email
            display_name = $persona.display
            password = $credentials.($persona.key)
            is_platform_admin = $false
            organization_id = $organization.id
            organization_role = $persona.orgRole
        }
    }
}

$workspaces = [ordered]@{}
foreach ($definition in @(
    @{ key = "executive"; name = "Executive Analytics"; slug = "executive-analytics" },
    @{ key = "sales"; name = "Sales Analytics"; slug = "sales-analytics" },
    @{ key = "operations"; name = "Operations Analytics"; slug = "operations-analytics" }
)) {
    $workspaces[$definition.key] = Invoke-VipApi -Session $platform -Method Post -Path "/api/v1/platform/organizations/$($organization.id)/workspaces" -Body @{ name = $definition.name; slug = $definition.slug }
}

foreach ($workspace in $workspaces.Values) {
    foreach ($persona in $personas) {
        if ($persona.key -eq "viewer" -and $workspace.id -ne $workspaces.executive.id) { continue }
        Invoke-VipApi -Session $platform -Method Post -Path "/api/v1/platform/organizations/$($organization.id)/workspaces/$($workspace.id)/members" -Body @{ username = $persona.username; workspace_role = $persona.wsRole } | Out-Null
    }
}

$adminSession = New-VipSession "demo.organization.admin" $credentials.admin
$orgId = $organization.id.ToString()
$workspaceId = $workspaces.executive.id.ToString()
$scope = @{ OrganizationId = $orgId; WorkspaceId = $workspaceId }

$connection = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/connections" @scope -Body @{
    name = "Demo Sales PostgreSQL"
    description = "Local PostgreSQL source for the fictional enterprise sales demonstration."
    connection_type = "postgresql"
    configuration = @{ host = "postgres"; port = 5432; database = "vip"; username = "vip"; ssl_mode = "disable"; connect_timeout_seconds = 10 }
    credentials = @{ password = "vip_local_dev_only" }
}
$connectionTest = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/connections/$($connection.id)/test" @scope

docker exec vip-postgres-1 psql -v ON_ERROR_STOP=1 -U vip -d vip -c "DROP SCHEMA IF EXISTS $demoSchema CASCADE; CREATE SCHEMA $demoSchema;" | Out-Null
$csvContent = Get-Content -Raw -LiteralPath $csvPath
$csvIngest = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/datasets/ingest-csv" @scope -Body @{
    connection_id = $connection.id
    source_schema = $demoSchema
    source_name = "sales_orders_raw"
    display_name = "Sales Orders — Raw CSV"
    description = "Fictional 2025 sales orders with controlled, documented quality issues."
    csv_content = $csvContent
}
$rawDataset = $csvIngest.datasets[0]

$cleanColumns = 'order_id text, order_date date, order_month text, customer text, region text, city text, sales_channel text, product_category text, product text, quantity bigint, unit_price numeric(24,6), revenue numeric(24,6), cost numeric(24,6), profit numeric(24,6), sales_representative text, status text'
docker exec vip-postgres-1 psql -v ON_ERROR_STOP=1 -U vip -d vip -c "CREATE TABLE $demoSchema.sales_orders_curated ($cleanColumns);" | Out-Null
$cleanDataset = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/datasets" @scope -Body @{
    connection_id = $connection.id
    dataset_type = "table"
    source_catalog = "vip"
    source_schema = $demoSchema
    source_name = "sales_orders_curated"
    display_name = "Curated Sales Orders"
    description = "Pipeline-governed output used by the executive semantic model."
    is_read_only = $false
}
Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/datasets/discover" @scope -Body @{
    connection_id = $connection.id
    schemas = @($demoSchema)
    include_object_types = @("table")
    include_names = @("sales_orders_curated")
    persist = $true
} | Out-Null

$rawFields = Invoke-VipApi -Session $adminSession -Method Get -Path "/api/v1/datasets/$($rawDataset.id)/fields" @scope
$fieldByName = @{}
foreach ($field in $rawFields) { $fieldByName[$field.source_name] = $field }
$qualityRules = @(
    @{ field_id = $fieldByName.Order_ID.id; rule_type = "not_null"; name = "Order ID is required"; description = "Every order must have a business identifier."; configuration = @{}; severity = "error" },
    @{ field_id = $fieldByName.Revenue.id; rule_type = "range"; name = "Revenue is non-negative"; description = "Revenue cannot be below zero."; configuration = @{ min = 0 }; severity = "error" },
    @{ field_id = $fieldByName.Region.id; rule_type = "accepted_values"; name = "Region uses approved values"; description = "Regions must match the governed territory list."; configuration = @{ values = @("Central", "Western", "Eastern", "Northern") }; severity = "warning" },
    @{ field_id = $fieldByName.Order_ID.id; rule_type = "unique"; name = "Order ID is unique"; description = "Duplicate business identifiers are rejected."; configuration = @{}; severity = "error" }
)
foreach ($rule in $qualityRules) {
    Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/datasets/$($rawDataset.id)/quality-rules" @scope -Body $rule | Out-Null
}
$qualityJob = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/datasets/$($rawDataset.id)/quality-evaluations" @scope

$renameMap = [ordered]@{
    Order_ID = "order_id"; Order_Date = "order_date"; Order_Month = "order_month"; Customer = "customer"; Region = "region"; City = "city"; Sales_Channel = "sales_channel"; Product_Category = "product_category"; Product = "product"; Quantity = "quantity"; Unit_Price = "unit_price"; Revenue = "revenue"; Cost = "cost"; Profit = "profit"; Sales_Representative = "sales_representative"; Status = "status"
}
$selectedColumns = @($renameMap.Keys)
$nodes = @(
    @{ key = "source"; type = "source-dataset"; title = "Raw Sales CSV"; x = 0; y = 0; config = @{ source_type = "dataset"; dataset_id = $rawDataset.id; row_limit = 2000 } },
    @{ key = "select"; type = "select-columns"; title = "Select Business Columns"; x = 260; y = 0; config = @{ columns = $selectedColumns } },
    @{ key = "rename"; type = "rename-columns"; title = "Standardize Column Names"; x = 520; y = 0; config = @{ renames = $renameMap } },
    @{ key = "convert"; type = "type-convert"; title = "Convert Revenue Type"; x = 780; y = 0; config = @{ field = "revenue"; target_type = "number" } },
    @{ key = "filter"; type = "filter"; title = "Filter Invalid Records"; x = 1040; y = 0; config = @{ formula = 'not isempty([order_id]) and not isempty([product_category]) and [revenue] >= 0' } },
    @{ key = "nulls"; type = "null-handling"; title = "Handle Missing Regions"; x = 1300; y = 0; config = @{ field = "region"; strategy = "replace"; value = "Unassigned" } },
    @{ key = "normalize"; type = "formula"; title = "Normalize Region Names"; x = 1560; y = 0; config = @{ field = "region"; formula = "title([region])" } },
    @{ key = "quality"; type = "row-validation"; title = "Business Quality Gate"; x = 1820; y = 0; config = @{ rules = @(@{ formula = '[quantity] > 0'; reason = "Quantity must be positive" }, @{ formula = '[revenue] >= [cost]'; reason = "Revenue must cover cost" }) } },
    @{ key = "dedupe"; type = "deduplicate"; title = "Deduplicate Orders"; x = 2080; y = 0; config = @{ fields = @("order_id") } },
    @{ key = "output"; type = "output-dataset"; title = "Curated Sales Output"; x = 2340; y = -120; config = @{ dataset_id = $cleanDataset.id; write_mode = "replace" } },
    @{ key = "aggregate"; type = "aggregate"; title = "Regional Revenue Summary"; x = 2340; y = 140; config = @{ group_by = @("region"); aggregations = @(@{ field = "revenue"; operation = "sum"; alias = "total_revenue" }, @{ field = "order_id"; operation = "count"; alias = "order_count" }) } },
    @{ key = "artifact"; type = "file-export"; title = "Protected Regional Summary"; x = 2600; y = 140; config = @{ format = "csv"; filename = "regional-revenue-summary.csv" } }
)
$edges = @()
$chain = @("source", "select", "rename", "convert", "filter", "nulls", "normalize", "quality", "dedupe", "output")
for ($index = 0; $index -lt $chain.Count - 1; $index++) { $edges += @{ key = "edge-$index"; source = $chain[$index]; target = $chain[$index + 1] } }
$edges += @{ key = "edge-aggregate"; source = "dedupe"; target = "aggregate" }
$edges += @{ key = "edge-artifact"; source = "aggregate"; target = "artifact" }

$pipelineEditor = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/pipelines" @scope -Body @{
    name = "Sales Revenue Quality & Curation"
    description = "Deterministic preparation flow from raw CSV to governed executive analytics."
    tags = @("demo", "sales", "governed")
    canvas = @{ zoom = 0.78; pan = @{ x = 30; y = 180 } }
    nodes = $nodes
    edges = $edges
}
$pipeline = $pipelineEditor.pipeline
$pipelineValidation = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/pipelines/$($pipeline.id)/validate" @scope
if (-not $pipelineValidation.valid) { throw "Demo pipeline validation failed: $($pipelineValidation | ConvertTo-Json -Depth 20 -Compress)" }
$pipelinePublished = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/pipelines/$($pipeline.id)/publish" @scope -Body @{ expected_version = $pipeline.row_version; change_summary = "Stage 2 deterministic demo baseline" }
$pipelineRun = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/pipelines/$($pipeline.id)/runs" @scope -Body @{}

$deadline = (Get-Date).AddMinutes(3)
do {
    Start-Sleep -Seconds 2
    $pipelineRun = Invoke-VipApi -Session $adminSession -Method Get -Path "/api/v1/pipelines/$($pipeline.id)/runs/$($pipelineRun.id)" @scope
} while ($pipelineRun.status -in @("queued", "running") -and (Get-Date) -lt $deadline)
if ($pipelineRun.status -ne "succeeded") { throw "Demo pipeline did not succeed; final status: $($pipelineRun.status)." }

$cleanFields = Invoke-VipApi -Session $adminSession -Method Get -Path "/api/v1/datasets/$($cleanDataset.id)/fields" @scope
$cleanFieldByName = @{}
foreach ($field in $cleanFields) { $cleanFieldByName[$field.source_name] = $field }
$semanticModel = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/semantic-models" @scope -Body @{
    key = "executive_sales"
    name = "Executive Sales Semantic Model"
    description = "Governed commercial metrics for the VIP enterprise demonstration."
    primary_dataset_id = $cleanDataset.id
    timezone = "Asia/Riyadh"
    currency = "SAR"
}
foreach ($dimension in @(
    @{ key = "date"; field = "order_date"; name = "Date"; type = "time"; time = $true; granularities = @("day", "month", "quarter", "year") },
    @{ key = "month"; field = "order_month"; name = "Month"; type = "categorical"; time = $false; granularities = @() },
    @{ key = "region"; field = "region"; name = "Region"; type = "geographic"; time = $false; granularities = @() },
    @{ key = "city"; field = "city"; name = "City"; type = "geographic"; time = $false; granularities = @() },
    @{ key = "product_category"; field = "product_category"; name = "Product Category"; type = "categorical"; time = $false; granularities = @() },
    @{ key = "sales_channel"; field = "sales_channel"; name = "Sales Channel"; type = "categorical"; time = $false; granularities = @() },
    @{ key = "sales_representative"; field = "sales_representative"; name = "Sales Representative"; type = "categorical"; time = $false; granularities = @() }
)) {
    Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/semantic-models/$($semanticModel.id)/dimensions" @scope -Body @{
        dataset_id = $cleanDataset.id; field_id = $cleanFieldByName[$dimension.field].id; key = $dimension.key; name = $dimension.name; dimension_type = $dimension.type; is_time_dimension = $dimension.time; time_granularities = $dimension.granularities; is_hidden = $false
    } | Out-Null
}
$measureDefinitions = @(
    @{ key = "revenue"; field = "revenue"; name = "Revenue"; aggregation = "sum" },
    @{ key = "profit"; field = "profit"; name = "Profit"; aggregation = "sum" },
    @{ key = "orders"; field = "order_id"; name = "Orders"; aggregation = "count_distinct" },
    @{ key = "average_order_value"; field = "revenue"; name = "Average Order Value"; aggregation = "average" }
)
$measures = [ordered]@{}
foreach ($definition in $measureDefinitions) {
    $measures[$definition.key] = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/semantic-models/$($semanticModel.id)/measures" @scope -Body @{
        dataset_id = $cleanDataset.id; field_id = $cleanFieldByName[$definition.field].id; key = $definition.key; name = $definition.name; aggregation = $definition.aggregation; is_hidden = $false
    }
}
$metrics = [ordered]@{}
foreach ($definition in @(
    @{ key = "total_revenue"; name = "Total Revenue"; measure = "revenue"; unit = "SAR" },
    @{ key = "total_profit"; name = "Total Profit"; measure = "profit"; unit = "SAR" },
    @{ key = "order_count"; name = "Order Count"; measure = "orders"; unit = "orders" },
    @{ key = "average_order_value"; name = "Average Order Value"; measure = "average_order_value"; unit = "SAR" }
)) {
    $metrics[$definition.key] = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/semantic-models/$($semanticModel.id)/metrics" @scope -Body @{
        key = $definition.key; name = $definition.name; metric_type = "measure"; base_measure_id = $measures[$definition.measure].id; unit = $definition.unit
    }
}
$metrics.profit_margin = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/semantic-models/$($semanticModel.id)/metrics" @scope -Body @{
    key = "profit_margin"; name = "Profit Margin"; description = "Total profit divided by total revenue."; metric_type = "ratio"; numerator_metric_id = $metrics.total_profit.id; denominator_metric_id = $metrics.total_revenue.id; unit = "percent"
}
$semanticValidation = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/semantic-models/$($semanticModel.id)/validate" @scope
if (-not $semanticValidation.valid) { throw "Semantic model validation failed." }
Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/semantic-models/$($semanticModel.id)/publish" @scope | Out-Null

$widgetIds = 1..9 | ForEach-Object { [guid]::NewGuid().ToString() }
$widgets = @(
    @{ id = $widgetIds[0]; type = "kpi"; title = "Total Revenue"; semantic_model_id = $semanticModel.id; query = @{ metrics = @("total_revenue"); dimensions = @(); filters = @(); order_by = @(); limit = 1 }; config = @{ number_style = "currency"; currency = "SAR"; decimals = 0 }; layout = @{ x = 0; y = 0; w = 3; h = 3 } },
    @{ id = $widgetIds[1]; type = "kpi"; title = "Total Profit"; semantic_model_id = $semanticModel.id; query = @{ metrics = @("total_profit"); dimensions = @(); filters = @(); order_by = @(); limit = 1 }; config = @{ number_style = "currency"; currency = "SAR"; decimals = 0 }; layout = @{ x = 3; y = 0; w = 3; h = 3 } },
    @{ id = $widgetIds[2]; type = "kpi"; title = "Total Orders"; semantic_model_id = $semanticModel.id; query = @{ metrics = @("order_count"); dimensions = @(); filters = @(); order_by = @(); limit = 1 }; config = @{ number_style = "number"; decimals = 0 }; layout = @{ x = 6; y = 0; w = 3; h = 3 } },
    @{ id = $widgetIds[3]; type = "kpi"; title = "Profit Margin"; semantic_model_id = $semanticModel.id; query = @{ metrics = @("profit_margin"); dimensions = @(); filters = @(); order_by = @(); limit = 1 }; config = @{ number_style = "percent"; decimals = 1 }; layout = @{ x = 9; y = 0; w = 3; h = 3 } },
    @{ id = $widgetIds[4]; type = "bar"; title = "Revenue by Region"; semantic_model_id = $semanticModel.id; query = @{ metrics = @("total_revenue"); dimensions = @("region"); filters = @(); order_by = @(@{ field = "total_revenue"; direction = "desc" }); limit = 10 }; config = @{ currency = "SAR"; show_legend = $false }; layout = @{ x = 0; y = 3; w = 6; h = 5 } },
    @{ id = $widgetIds[5]; type = "line"; title = "Revenue Trend by Month"; semantic_model_id = $semanticModel.id; query = @{ metrics = @("total_revenue"); dimensions = @("month"); filters = @(); order_by = @(@{ field = "month"; direction = "asc" }); limit = 24 }; config = @{ currency = "SAR"; show_gridlines = $true }; layout = @{ x = 6; y = 3; w = 6; h = 5 } },
    @{ id = $widgetIds[6]; type = "donut"; title = "Revenue by Product Category"; semantic_model_id = $semanticModel.id; query = @{ metrics = @("total_revenue"); dimensions = @("product_category"); filters = @(); order_by = @(@{ field = "total_revenue"; direction = "desc" }); limit = 10 }; config = @{ currency = "SAR"; show_legend = $true }; layout = @{ x = 0; y = 8; w = 6; h = 5 } },
    @{ id = $widgetIds[7]; type = "column"; title = "Profit by Sales Channel"; semantic_model_id = $semanticModel.id; query = @{ metrics = @("total_profit"); dimensions = @("sales_channel"); filters = @(); order_by = @(@{ field = "total_profit"; direction = "desc" }); limit = 10 }; config = @{ currency = "SAR" }; layout = @{ x = 6; y = 8; w = 6; h = 5 } },
    @{ id = $widgetIds[8]; type = "table"; title = "Regional Performance Detail"; semantic_model_id = $semanticModel.id; query = @{ metrics = @("total_revenue", "total_profit", "order_count"); dimensions = @("region"); filters = @(); order_by = @(@{ field = "total_revenue"; direction = "desc" }); limit = 20 }; config = @{ currency = "SAR"; columns = @("region", "total_revenue", "total_profit", "order_count") }; layout = @{ x = 0; y = 13; w = 12; h = 7 } }
)
$dashboard = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/dashboards" @scope -Body @{
    name = "Executive Sales Performance"
    description = "Executive view of fictional 2025 revenue, profit, orders, and margin."
    slug = "executive-sales-performance"
    tags = @("executive", "sales", "demo")
}
$dashboardEditor = Invoke-VipApi -Session $adminSession -Method Get -Path "/api/v1/dashboards/$($dashboard.id)/editor" @scope
$dashboardEditor = Invoke-VipApi -Session $adminSession -Method Put -Path "/api/v1/dashboards/$($dashboard.id)/editor" @scope -Body @{
    expected_version = $dashboardEditor.version
    name = "Executive Sales Performance"
    description = "Executive view of fictional 2025 revenue, profit, orders, and margin."
    tags = @("executive", "sales", "demo")
    pages = @(@{ key = "overview"; name = "Executive Overview"; description = "Commercial performance at a glance"; position = 0; canvas = @{ columns = 12; row_height = 72 }; widgets = $widgets })
    filters = @(
        @{ key = "date"; label = "Date"; type = "date_range"; semantic_model_id = $semanticModel.id; dimension_key = "date"; operator = "between"; widget_ids = $widgetIds; position = 0 },
        @{ key = "region"; label = "Region"; type = "multi_select"; semantic_model_id = $semanticModel.id; dimension_key = "region"; operator = "in"; widget_ids = $widgetIds; position = 1 },
        @{ key = "product_category"; label = "Product Category"; type = "multi_select"; semantic_model_id = $semanticModel.id; dimension_key = "product_category"; operator = "in"; widget_ids = $widgetIds; position = 2 },
        @{ key = "sales_channel"; label = "Sales Channel"; type = "multi_select"; semantic_model_id = $semanticModel.id; dimension_key = "sales_channel"; operator = "in"; widget_ids = $widgetIds; position = 3 }
    )
    change_summary = "Stage 2 executive demo layout"
}
$publishedDashboard = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/dashboards/$($dashboard.id)/publish" @scope -Body @{ expected_version = $dashboardEditor.version; change_summary = "Stage 2 customer-demo publication" }

$semanticTotals = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/semantic-query" @scope -Body @{ semantic_model_id = $semanticModel.id; metrics = @("total_revenue", "total_profit", "order_count", "profit_margin"); dimensions = @(); filters = @(); order_by = @(); limit = 1 }
$semanticRegions = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/semantic-query" @scope -Body @{ semantic_model_id = $semanticModel.id; metrics = @("total_revenue"); dimensions = @("region"); filters = @(); order_by = @(@{ field = "total_revenue"; direction = "desc" }); limit = 20 }
$semanticCategories = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/semantic-query" @scope -Body @{ semantic_model_id = $semanticModel.id; metrics = @("total_revenue"); dimensions = @("product_category"); filters = @(); order_by = @(@{ field = "total_revenue"; direction = "desc" }); limit = 20 }

$exports = [ordered]@{}
$backupRoot = Join-Path $artifactRoot "backup-assets"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
foreach ($format in @("pdf", "png")) {
    $item = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/dashboards/$($dashboard.id)/exports" @scope -Body @{ format = $format; filters = @{}; locale = "en-US"; timezone = "Asia/Riyadh" }
    $exportId = $item.id.ToString()
    $deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 2
        $exportStatus = docker exec vip-postgres-1 psql -U vip -d vip -Atc "SELECT status FROM dashboard_exports WHERE id='$exportId';"
    } while ($exportStatus -in @("queued", "running", "rendering") -and (Get-Date) -lt $deadline)
    if ($exportStatus -ne "completed") { throw "Dashboard $format export did not complete; final status: $exportStatus." }
    $items = Invoke-VipApi -Session $adminSession -Method Get -Path "/api/v1/dashboards/$($dashboard.id)/exports" @scope
    $item = @($items) | Where-Object { $_.format -eq $format } | Sort-Object created_at -Descending | Select-Object -First 1
    $exports[$format] = $item
    $download = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/dashboard-exports/$($item.id)/download-token" @scope
    $downloadUri = if ($download.url.StartsWith("http")) { $download.url } else { "$ApiRoot$($download.url)" }
    Invoke-WebRequest -UseBasicParsing -Uri $downloadUri -WebSession $adminSession -OutFile (Join-Path $backupRoot "Executive-Sales-Performance.$format") | Out-Null
}

$schedule = Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/dashboards/$($dashboard.id)/deliveries" @scope -Body @{
    name = "Monday Executive Sales Brief"
    recipients = @("demo.recipient@vip.example")
    cc = @(); bcc = @()
    subject = "VIP Executive Sales Performance"
    format = "pdf"
    filters = @{}
    schedule_type = "weekly"
    timezone = "Asia/Riyadh"
    include_dashboard_link = $true
    enabled = $false
    max_retries = 1
}

$qualityDeadline = (Get-Date).AddMinutes(2)
do {
    Start-Sleep -Seconds 2
    $qualityEvaluations = Invoke-VipApi -Session $adminSession -Method Get -Path "/api/v1/datasets/$($rawDataset.id)/quality-evaluations?limit=10" @scope
    $qualityEvaluation = $qualityEvaluations | Where-Object id -eq $qualityJob.id | Select-Object -First 1
} while ($qualityEvaluation.status -in @("queued", "running") -and (Get-Date) -lt $qualityDeadline)
$qualityResults = Invoke-VipApi -Session $adminSession -Method Get -Path "/api/v1/datasets/$($rawDataset.id)/quality-results" @scope

$sqlTotals = docker exec vip-postgres-1 psql -U vip -d vip -At -F '|' -c "SELECT count(DISTINCT order_id), round(sum(revenue),2), round(sum(profit),2), round(sum(profit)/NULLIF(sum(revenue),0),6) FROM $demoSchema.sales_orders_curated; SELECT region, round(sum(revenue),2) FROM $demoSchema.sales_orders_curated GROUP BY region ORDER BY sum(revenue) DESC LIMIT 1; SELECT product_category, round(sum(revenue),2) FROM $demoSchema.sales_orders_curated GROUP BY product_category ORDER BY sum(revenue) DESC LIMIT 1;"
$curatedRows = docker exec vip-postgres-1 psql -U vip -d vip -Atc "SELECT count(*) FROM $demoSchema.sales_orders_curated;"

$notifications = Invoke-VipApi -Session $adminSession -Method Get -Path "/api/v1/notifications?limit=50" @scope
Invoke-VipApi -Session $adminSession -Method Post -Path "/api/v1/notifications/read-all" @scope | Out-Null

$manifest = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    organization = @{ id = $organization.id; name = $organization.name; slug = $organization.slug }
    workspaces = @($workspaces.Values | ForEach-Object { @{ id = $_.id; name = $_.name; slug = $_.slug } })
    users = @($personas | ForEach-Object { @{ username = $_.username; email = $_.email; display_name = $_.display; organization_role = $_.orgRole; workspace_role = $_.wsRole } })
    connection = @{ id = $connection.id; name = $connection.name; health = $connectionTest.status }
    csv = @{ path = $csvPath; rows = 723; sha256 = (Get-FileHash -LiteralPath $csvPath -Algorithm SHA256).Hash }
    datasets = @{ raw = @{ id = $rawDataset.id; name = $rawDataset.display_name }; curated = @{ id = $cleanDataset.id; name = $cleanDataset.display_name } }
    quality = @{ evaluation_id = @($qualityResults)[0].evaluation_id; status = "completed"; results = $qualityResults }
    pipeline = @{ id = $pipeline.id; name = $pipeline.name; run_id = $pipelineRun.id; run_status = $pipelineRun.status; rows_written = [int]$curatedRows }
    semantic_model = @{ id = $semanticModel.id; name = $semanticModel.name; status = "published"; totals = $semanticTotals; regions = $semanticRegions; categories = $semanticCategories }
    dashboard = @{ id = $dashboard.id; name = $dashboard.name; status = "published" }
    exports = @{ pdf = $exports.pdf; png = $exports.png }
    schedule = @{ id = $schedule.id; name = $schedule.name; enabled = $schedule.enabled; timezone = $schedule.timezone }
    notification_count = @($notifications).Count
    sql_parity = @($sqlTotals)
    backup_assets = @{ pdf = (Join-Path $backupRoot "Executive-Sales-Performance.pdf"); png = (Join-Path $backupRoot "Executive-Sales-Performance.png") }
    credential_store = $credentialPath
}
Set-Content -LiteralPath $manifestPath -Value ($manifest | ConvertTo-Json -Depth 30) -Encoding utf8

Write-Output "organization_id=$($organization.id)"
Write-Output "workspace_id=$workspaceId"
Write-Output "connection_test=$($connectionTest.status)"
Write-Output "raw_rows=723"
Write-Output "pipeline_status=$($pipelineRun.status)"
Write-Output "quality_status=$($qualityEvaluation.status)"
Write-Output "pdf_export=$($exports.pdf.status)"
Write-Output "png_export=$($exports.png.status)"
Write-Output "manifest=$manifestPath"
Write-Output "credential_store=$credentialPath"
