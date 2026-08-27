#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

Write-Host "=== VIP product certification collector ==="
Write-Host "This does not score the product. It records the reproducible baseline."
Write-Host ""

python "$root\scripts\certification\collect-baseline.py"
Write-Host ""
Write-Host "Compose services:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
Write-Host ""
Write-Host "Alembic current:"
docker exec vip-api-1 alembic current
Write-Host ""
Write-Host "Next: follow docs/certification/final-product-audit/AUDIT_CHECKLIST.md"
Write-Host "Live API probe (credentials via env, never commit):"
Write-Host "  python scripts/certification/live_api_probe.py"
