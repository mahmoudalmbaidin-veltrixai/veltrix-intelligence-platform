param(
    [string]$ApiRoot = "http://localhost:8000",
    [Parameter(Mandatory)][string]$VerifiedBackupPath,
    [switch]$ConfirmNonProduction
)

$ErrorActionPreference = "Stop"
if (-not $ConfirmNonProduction) { throw "Pass -ConfirmNonProduction after checking the local target." }
& (Join-Path $PSScriptRoot "provision-enterprise-demo.ps1") `
    -Mode Apply `
    -ApiRoot $ApiRoot `
    -VerifiedBackupPath $VerifiedBackupPath `
    -ConfirmNonProduction `
    -IncludeLegacyStage2Cleanup
