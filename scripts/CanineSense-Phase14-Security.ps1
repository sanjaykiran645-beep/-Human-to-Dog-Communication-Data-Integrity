<#
.SYNOPSIS
    CanineSense AI — Phase 14 Security Closure Verification Script
.DESCRIPTION
    Reuses CanineSense-SecurityHardening.ps1, executes Phase 14 negative reviewer authorization,
    account erasure/token revocation, SQLi/upload/traversal tests (test_phase14_security.py),
    and runs frontend production npm audit.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "backend\app\main.py"))) {
    Write-Error "FATAL: Invalid project root '$RepoRoot'."
    exit 2
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("phase14-security-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase14-security.json"

function Write-P14SecLog {
    param([string]$Level, [string]$Msg)
    $clean = $Msg -replace '(sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|rnd_[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._-]+)', '[REDACTED]'
    $line = "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))] [$Level] $clean"
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

$PythonExe = @(
    (Join-Path $env:LOCALAPPDATA "Python\bin\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe")
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $PythonExe = $cmd.Source }
}
if (-not $PythonExe) {
    Write-P14SecLog "BLOCKED" "Python interpreter unavailable."
    exit 2
}

$env:PYTHONPATH = (Join-Path $RepoRoot "backend")

Write-P14SecLog "INFO" "Running Phase 13 SecurityHardening script..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "CanineSense-SecurityHardening.ps1") 2>&1 | ForEach-Object { Add-Content -Path $LogPath -Value "$_" }
$p13Exit = $LASTEXITCODE
$ErrorActionPreference = $prevEap

Write-P14SecLog "INFO" "Running Phase 14 security pytest suite (incl. test_phase14_security.py)..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$secOut = & $PythonExe -m pytest `
    (Join-Path $RepoRoot "backend\tests\test_auth.py") `
    (Join-Path $RepoRoot "backend\tests\test_security_hardening.py") `
    (Join-Path $RepoRoot "backend\tests\test_security_idor.py") `
    (Join-Path $RepoRoot "backend\tests\test_client_redteam_audit.py") `
    (Join-Path $RepoRoot "backend\tests\test_experimental_validation.py") `
    (Join-Path $RepoRoot "backend\tests\test_phase14_security.py") -v 2>&1 | Out-String
$secExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
Add-Content -Path $LogPath -Value $secOut -Encoding UTF8

$passed = 0; $failed = 0
if ($secOut -match '(\d+)\s+passed') { $passed = [int]$Matches[1] }
if ($secOut -match '(\d+)\s+failed') { $failed = [int]$Matches[1] }

$npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
$npmTotalVulns = -1
if ($npmCmd) {
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $auditRaw = & $npmCmd.Source audit --omit=dev --json 2>$null | Out-String
        $ErrorActionPreference = $prevEap
        if ($auditRaw) {
            $auditObj = $auditRaw | ConvertFrom-Json
            $npmTotalVulns = [int]$auditObj.metadata.vulnerabilities.total
        }
    } finally {
        Pop-Location
    }
}

$p13Rep = if (Test-Path (Join-Path $LogDir "phase13-security-hardening.json")) {
    Get-Content (Join-Path $LogDir "phase13-security-hardening.json") -Raw | ConvertFrom-Json
} else { $null }

$overall = if ($p13Exit -eq 0 -and $secExit -eq 0 -and $failed -eq 0 -and $npmTotalVulns -eq 0) { "PASS" } else { "FAIL" }
$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    overall_status = $overall
    security_pytest = @{ exit_code = $secExit; passed = $passed; failed = $failed }
    npm_prod_vulnerabilities = $npmTotalVulns
    android_cleartext_disabled = if ($p13Rep) { $p13Rep.android_cleartext_disabled } else { $false }
    hardcoded_secret_hits = if ($p13Rep) { $p13Rep.hardcoded_secret_hits } else { -1 }
}
$rep | ConvertTo-Json -Depth 5 | Set-Content -Path $OutJson -Encoding UTF8
Write-P14SecLog $overall "Phase 14 security verification finished (status=$overall, passed=$passed, failed=$failed, npm_prod_vulns=$npmTotalVulns)"

if ($overall -ne "PASS") { exit 1 }
exit 0
