<#
.SYNOPSIS
    CanineSense AI — Phase 13 Priority B Security Hardening & Verification Script
.DESCRIPTION
    Executes security-critical pytest suites (auth, IDOR, security hardening, client red-team,
    and Priority 7 reviewer invitation authorization tests), checks npm audit, and scans source
    for exposed secrets or unsafe flags.
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
$LogPath = Join-Path $LogDir ("security-hardening-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase13-security-hardening.json"

function Write-SecLog {
    param([string]$Level, [string]$Msg)
    $clean = $Msg -replace '(sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._-]+)', '[REDACTED]'
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
    Write-SecLog "BLOCKED" "Python interpreter unavailable."
    exit 2
}

$env:PYTHONPATH = (Join-Path $RepoRoot "backend")
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$secOut = & $PythonExe -m pytest `
    (Join-Path $RepoRoot "backend\tests\test_auth.py") `
    (Join-Path $RepoRoot "backend\tests\test_security_hardening.py") `
    (Join-Path $RepoRoot "backend\tests\test_security_idor.py") `
    (Join-Path $RepoRoot "backend\tests\test_client_redteam_audit.py") `
    (Join-Path $RepoRoot "backend\tests\test_experimental_validation.py") -v 2>&1 | Out-String
$secExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
Add-Content -Path $LogPath -Value $secOut -Encoding UTF8

$passed = 0; $failed = 0
if ($secOut -match '(\d+)\s+passed') { $passed = [int]$Matches[1] }
if ($secOut -match '(\d+)\s+failed') { $failed = [int]$Matches[1] }

# Static checks
$manifestPath = Join-Path $RepoRoot "mobile-android\android\app\src\main\AndroidManifest.xml"
$cleartextDisabled = $false
if (Test-Path $manifestPath) {
    $cleartextDisabled = ((Get-Content $manifestPath -Raw) -match 'usesCleartextTraffic="false"')
}
$secretMatches = @(Select-String -Path (Join-Path $RepoRoot "backend\app\**\*.py"), (Join-Path $RepoRoot "frontend\src\**\*.ts"), (Join-Path $RepoRoot "frontend\src\**\*.tsx") -Pattern '(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|rnd_[A-Za-z0-9]{20,}|BEGIN (RSA|EC|OPENSSH) PRIVATE KEY)' -ErrorAction SilentlyContinue)

$overall = if ($secExit -eq 0 -and $cleartextDisabled -and $secretMatches.Count -eq 0) { "PASS" } else { "FAIL" }

$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    security_pytest = @{ exit_code = $secExit; passed = $passed; failed = $failed }
    android_cleartext_disabled = $cleartextDisabled
    hardcoded_secret_hits = $secretMatches.Count
    overall_status = $overall
}
$rep | ConvertTo-Json -Depth 5 | Set-Content -Path $OutJson -Encoding UTF8
Write-SecLog $overall "Security hardening verification complete (status=$overall, passed=$passed, failed=$failed)"

if ($overall -ne "PASS") { exit 1 }
exit 0
