param(
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

if (-not $OutputPath) {
    $repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
    $OutputPath = Join-Path $repositoryRoot "demo-data\vip_demo_sales_orders.csv"
}

$regions = @(
    @{ Region = "Central"; City = "Riyadh" },
    @{ Region = "Western"; City = "Jeddah" },
    @{ Region = "Eastern"; City = "Dammam" },
    @{ Region = "Northern"; City = "Tabuk" }
)
$channels = @("Enterprise Direct", "Partner", "Digital", "Inside Sales")
$products = @(
    @{ Category = "Analytics"; Product = "Insight Suite"; Price = 185 },
    @{ Category = "Data Management"; Product = "Data Hub"; Price = 240 },
    @{ Category = "Governance"; Product = "Control Center"; Price = 165 },
    @{ Category = "Operations"; Product = "Process Monitor"; Price = 125 }
)
$representatives = @("Amina Saleh", "Omar Haddad", "Lina Nasser", "Yousef Karim", "Sara Mansour", "Fahad Rahman")
$statuses = @("Completed", "Completed", "Completed", "In Progress")

$rows = [System.Collections.Generic.List[object]]::new()
for ($index = 1; $index -le 720; $index++) {
    $region = $regions[($index - 1) % $regions.Count]
    $channel = $channels[(($index - 1) * 3) % $channels.Count]
    $product = $products[(($index - 1) * 5) % $products.Count]
    $quantity = 1 + (($index * 7) % 8)
    $unitPrice = [decimal]($product.Price + (($index % 6) * 7.5))
    $revenue = [decimal]($quantity * $unitPrice)
    $costRatio = [decimal](0.62 + (($index % 5) * 0.035))
    $cost = [math]::Round($revenue * $costRatio, 2)
    $profit = [math]::Round($revenue - $cost, 2)
    $orderDate = (Get-Date "2025-01-01").AddDays(($index * 11) % 365)

    $rows.Add([pscustomobject][ordered]@{
        Order_ID = "ORD-2025-{0:D4}" -f $index
        Order_Date = $orderDate.ToString("yyyy-MM-dd")
        Order_Month = $orderDate.ToString("yyyy-MM")
        Customer = "Fictional Enterprise {0:D3}" -f (1 + (($index * 13) % 160))
        Region = $region.Region
        City = $region.City
        Sales_Channel = $channel
        Product_Category = $product.Category
        Product = $product.Product
        Quantity = $quantity
        Unit_Price = $unitPrice
        Revenue = $revenue
        Cost = $cost
        Profit = $profit
        Sales_Representative = $representatives[($index - 1) % $representatives.Count]
        Status = $statuses[($index - 1) % $statuses.Count]
    })
}

# Controlled, documented issues. No randomness is used.
$rows[10].Region = $null
$rows[210].Region = $null
$rows[50].Region = $rows[50].Region.ToLowerInvariant()
$rows[250].Region = $rows[250].Region.ToLowerInvariant()
$rows[450].Region = $rows[450].Region.ToLowerInvariant()
$rows[100].Product_Category = $null
$rows[500].Product_Category = $null
$rows[300].Order_ID = $null
$rows[400].Revenue = -100
$rows[400].Profit = -($rows[400].Cost + 100)

foreach ($duplicateIndex in @(99, 299, 599)) {
    $rows.Add($rows[$duplicateIndex].PSObject.Copy())
}

$directory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$rows | Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding utf8

Write-Output "demo_csv=$OutputPath"
Write-Output "rows=$($rows.Count)"
Write-Output "base_rows=720"
Write-Output "duplicate_rows=3"
Write-Output "null_region_rows=2"
Write-Output "lowercase_region_rows=3"
Write-Output "blank_category_rows=2"
Write-Output "blank_order_id_rows=1"
Write-Output "negative_revenue_rows=1"
