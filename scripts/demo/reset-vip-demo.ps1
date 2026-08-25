param(
    [ValidateSet("DryRun", "Apply")][string]$Mode = "DryRun",
    [string]$ApiRoot = "http://localhost:8000",
    [string]$VerifiedBackupPath = "",
    [switch]$ConfirmNonProduction,
    [switch]$SkipReprovision
)

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "reset-demo-environment.ps1") @PSBoundParameters
