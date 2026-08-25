param(
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$scenarioPath = Join-Path $repositoryRoot "demo-data\stage4\scenarios.json"
if (-not $OutputRoot) { $OutputRoot = Join-Path $repositoryRoot "demo-data\stage4\generated" }
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$configuration = Get-Content -Raw -LiteralPath $scenarioPath | ConvertFrom-Json -Depth 40
$pythonCommand = if ($env:VIP_DEMO_PYTHON) { $env:VIP_DEMO_PYTHON } else { (Get-Command python -ErrorAction Stop).Source }
$xlsxConverter = Join-Path $PSScriptRoot "csv_to_xlsx.py"
$regions = @(
    @{ Name = "Central"; Weight = 1.18 },
    @{ Name = "Western"; Weight = 1.12 },
    @{ Name = "Eastern"; Weight = 1.08 },
    @{ Name = "Northern"; Weight = 0.91 },
    @{ Name = "Southern"; Weight = 0.86 }
)

function Get-ScenarioValues([string]$Key) {
    switch ($Key) {
        "sales-commercial" { return @{ Categories=@("Electronics","Home & Living","Grocery","Apparel"); Subcategories=@("Premium","Core","Value","Seasonal"); Locations=@("Riyadh Metro","Jeddah Coast","Dammam Hub","Tabuk Cluster","Abha Cluster"); Statuses=@("Completed","Completed","In Progress","Returned"); Owners=@("Commercial North","Commercial Central","Commercial West","Key Accounts"); Base=1450; CostRatio=0.69; ScoreBase=78; CycleBase=18 } }
        "supply-chain" { return @{ Categories=@("Fast Moving","Seasonal","Imported","Private Label"); Subcategories=@("Inbound","Storage","Replenishment","Outbound"); Locations=@("Riyadh DC","Jeddah DC","Dammam DC","Tabuk Cross-dock","Khamis Hub"); Statuses=@("Fulfilled","Fulfilled","Delayed","At Risk"); Owners=@("Planning","Procurement","Warehouse","Transport"); Base=8200; CostRatio=0.83; ScoreBase=91; CycleBase=30 } }
        "executive-management" { return @{ Categories=@("Commercial","Supply Chain","Customer","Operations"); Subcategories=@("Growth","Margin","Resilience","Exception"); Locations=@("Retail Division","Distribution Division","Digital Division","Shared Services"); Statuses=@("On Track","On Track","Watch","Exception"); Owners=@("Executive Office","Finance","Strategy","Operations"); Base=18500; CostRatio=0.76; ScoreBase=84; CycleBase=42 } }
        "network-operations" { return @{ Categories=@("Critical","High","Medium","Low"); Subcategories=@("Power","Transmission","Radio","Backhaul"); Locations=@("Site CT-101","Site CT-214","Site CT-337","Site CT-452","Site CT-589"); Statuses=@("Resolved","Resolved","Monitoring","Open"); Owners=@("NOC Core","NOC Radio","NOC Transport","Regional NOC"); Base=11800; CostRatio=0.14; ScoreBase=99; CycleBase=52 } }
        "field-maintenance" { return @{ Categories=@("Preventive","Corrective","Emergency","Inspection"); Subcategories=@("Power","Radio","Cooling","Civil"); Locations=@("Team Riyadh","Team Jeddah","Team Dammam","Team Tabuk","Team Abha"); Statuses=@("Closed","Closed","In Progress","Escalated"); Owners=@("Field North","Field Central","Field West","Vendor Services"); Base=5200; CostRatio=0.34; ScoreBase=92; CycleBase=11 } }
        "quality-performance" { return @{ Categories=@("Power Stability","Transmission Loss","Configuration","Data Completeness"); Subcategories=@("Recurring","One-time","Preventable","External"); Locations=@("Cluster A","Cluster B","Cluster C","Cluster D","Cluster E"); Statuses=@("Compliant","Compliant","Review","Violation"); Owners=@("Quality Assurance","NOC Quality","Field Quality","Data Governance"); Base=9200; CostRatio=0.09; ScoreBase=88; CycleBase=72 } }
        "ehs-compliance" { return @{ Categories=@("Low","Moderate","High","Critical"); Subcategories=@("Inspection","Observation","Incident","Corrective Action"); Locations=@("Facility MF-01","Facility MF-07","Facility MF-12","Facility MF-18","Facility MF-23"); Statuses=@("Closed","Closed","Action Due","Escalated"); Owners=@("EHS Central","EHS West","EHS East","Compliance Office"); Base=6400; CostRatio=0.17; ScoreBase=93; CycleBase=38 } }
        "maintenance-operations" { return @{ Categories=@("HVAC","Electrical","Fire Systems","Vertical Transport"); Subcategories=@("Preventive","Corrective","Inspection","Overhaul"); Locations=@("Zone Riyadh","Zone Jeddah","Zone Dammam","Zone Tabuk","Zone Abha"); Statuses=@("Completed","Completed","Scheduled","Outage"); Owners=@("Asset Care","Mobile Maintenance","Specialist Vendor","Reliability Team"); Base=7100; CostRatio=0.39; ScoreBase=82; CycleBase=16 } }
        "service-performance" { return @{ Categories=@("Cleaning","Security","Helpdesk","Space Services"); Subcategories=@("Standard","Urgent","Planned","Customer Request"); Locations=@("Portfolio Central","Portfolio West","Portfolio East","Portfolio North","Portfolio South"); Statuses=@("Resolved","Resolved","In Progress","Breached"); Owners=@("Service Desk","Mobile Team","Site Team","Customer Care"); Base=3900; CostRatio=0.44; ScoreBase=4.2; CycleBase=9 } }
        default { throw "Unknown scenario key: $Key" }
    }
}

function New-ScenarioRows($Workspace) {
    $values = Get-ScenarioValues $Workspace.key
    $rowTarget = 600
    $rows = [System.Collections.Generic.List[object]]::new()
    for ($index = 1; $index -le $rowTarget; $index++) {
        $region = $regions[($index * 7 + $Workspace.key.Length) % $regions.Count]
        $date = (Get-Date "2025-01-01").AddDays(($index * 13 + $Workspace.key.Length * 11) % 540)
        $category = $values.Categories[($index * 5) % $values.Categories.Count]
        $subcategory = $values.Subcategories[($index * 3 + 1) % $values.Subcategories.Count]
        $location = $values.Locations[($index * 11 + 2) % $values.Locations.Count]
        $status = $values.Statuses[($index * 7 + 3) % $values.Statuses.Count]
        $owner = $values.Owners[($index * 2 + 1) % $values.Owners.Count]
        $season = 0.88 + ((($date.Month + 2) % 6) * 0.055)
        $growth = 1 + ([math]::Floor(($date - (Get-Date "2025-01-01")).TotalDays / 90) * 0.018)
        $quantity = 1 + (($index * 9) % 12)
        $metric = [math]::Round($values.Base * $region.Weight * $season * $growth * (0.72 + (($index % 9) * 0.055)), 2)
        $cost = [math]::Round($metric * ($values.CostRatio + (($index % 5) * 0.012)), 2)
        $score = if ($Workspace.key -eq "service-performance") {
            [math]::Round([math]::Min(5, [math]::Max(1, $values.ScoreBase + ((($index % 7) - 3) * 0.12))), 2)
        } else {
            [math]::Round([math]::Min(100, [math]::Max(0, $values.ScoreBase + ((($index % 11) - 5) * 0.85))), 2)
        }
        $cycle = [math]::Round([math]::Max(0.5, $values.CycleBase * (0.65 + (($index % 13) * 0.055))), 2)
        $slaMet = if (($index % 9) -in @(0,1)) { "No" } else { "Yes" }
        $risk = if ($status -in @("Returned","At Risk","Exception","Open","Escalated","Violation","Outage","Breached") -or $slaMet -eq "No") { "At Risk" } else { "Controlled" }
        $recordPrefix = $Workspace.key.ToUpperInvariant().Replace("-", "")
        $recordId = "{0}-{1:D5}" -f $recordPrefix, $index
        $rows.Add([pscustomobject][ordered]@{
            raw_record_id = $recordId
            event_date = $date.ToString("yyyy-MM-dd")
            period = $date.ToString("yyyy-MM")
            region_name = $region.Name
            location = $location
            category = $category
            subcategory = $subcategory
            status = $status
            owner_group = $owner
            quantity = $quantity
            metric_value = $metric
            metric_cost = $cost
            score = $score
            cycle_hours = $cycle
            sla_met = $slaMet
            risk_flag = $risk
            notes = "SYNTHETIC DEMO DATA — $($Workspace.businessPurpose)"
        })
    }

    # Keep one deliberate "before analysis" quality scenario. The remaining
    # workspaces stay presentation-clean so the demo does not look broadly dirty.
    if ($Workspace.key -eq "sales-commercial") {
        $rows[10].region_name = $null
        $rows[50].region_name = $rows[50].region_name.ToLowerInvariant()
        $rows[100].raw_record_id = $null
        $rows[150].metric_value = -1
        $rows.Add($rows[39].PSObject.Copy())
        $rows.Add($rows[219].PSObject.Copy())
        $rows.Add($rows[419].PSObject.Copy())
    }
    return $rows
}

$manifest = [ordered]@{ generated_at=(Get-Date).ToUniversalTime().ToString("o"); seed=$configuration.dataSeed; files=@() }
foreach ($organization in $configuration.organizations) {
    foreach ($workspace in $organization.workspaces) {
        $rows = New-ScenarioRows $workspace
        $csvName = [System.IO.Path]::ChangeExtension($workspace.inputFile, ".csv")
        $csvPath = Join-Path $OutputRoot $csvName
        $rows | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding utf8
        if ($workspace.sourceMode -eq "xlsx") {
            $xlsxPath = Join-Path $OutputRoot $workspace.inputFile
            & $pythonCommand $xlsxConverter $csvPath $xlsxPath
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $xlsxPath) -or (Get-Item -LiteralPath $xlsxPath).Length -lt 1KB) {
                throw "Could not generate deterministic XLSX source: $xlsxPath"
            }
        }
        $manifest.files += [ordered]@{
            organization=$organization.slug
            workspace=$workspace.key
            path=$csvPath
            rows=$rows.Count
            sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $csvPath).Hash
            source_mode=$workspace.sourceMode
            synthetic=$true
        }

        if ($workspace.flagship) {
            $scenarioValues = Get-ScenarioValues $workspace.key
            $targetRows = for ($index = 0; $index -lt $regions.Count; $index++) {
                [pscustomobject][ordered]@{
                    target_region = $regions[$index].Name
                    target_value = [math]::Round($scenarioValues.Base * (0.95 + $index * 0.04), 2)
                    benchmark_score = if ($workspace.key -eq "network-operations") { 99.3 } elseif ($workspace.key -eq "ehs-compliance") { 94.0 } else { 82.0 }
                    regional_lead = @("Team Saffron","Team Cobalt","Team Cedar","Team Quartz","Team Amber")[$index]
                }
            }
            $lookupPath = Join-Path $OutputRoot $workspace.lookupFile
            $targetRows | Export-Csv -LiteralPath $lookupPath -NoTypeInformation -Encoding utf8
            $manifest.files += [ordered]@{
                organization=$organization.slug
                workspace=$workspace.key
                path=$lookupPath
                rows=$targetRows.Count
                sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $lookupPath).Hash
                source_mode="csv-lookup"
                synthetic=$true
            }
        }
    }
}

$manifestPath = Join-Path $OutputRoot "synthetic-data-manifest.json"
$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Output "scenario_files=$($manifest.files.Count)"
Write-Output "manifest=$manifestPath"
Write-Output "seed=$($configuration.dataSeed)"
