param(
    [string]$CredentialFile = ""
)

$ErrorActionPreference = "Stop"
if (-not $CredentialFile) {
    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
    $CredentialFile = Join-Path $repoRoot "artifacts\qa\full-platform\qa-credentials.dpapi"
}

$cipherText = [System.IO.File]::ReadAllText((Resolve-Path $CredentialFile))
$secure = ConvertTo-SecureString $cipherText
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
}
