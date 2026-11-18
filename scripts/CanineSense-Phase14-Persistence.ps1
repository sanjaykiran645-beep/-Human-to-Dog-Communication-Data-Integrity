<#
.SYNOPSIS
    CanineSense AI — Phase 14 Data Persistence & Disaster Recovery Verification Script
.DESCRIPTION
    Reuses Phase 13 data integrity checks, runs Phase 14 persistence/DR tests (isolated backup,
    metadata sidecar, row-count verification, ZipSlip defense, retention pruning, backup health),
    and inspects live Render /api/health persistence telemetry without touching live DBs.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "backend\app\services\durability.py"))) {
    Write-Error "FATAL: Invalid project root '$RepoRoot'."
    exit 2
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("phase14-persistence-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase14-persistence.json"

function Write-PersLog {
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
    Write-PersLog "BLOCKED" "Python interpreter unavailable."
    @{ architecture_status = "BLOCKED"; production_status = "BLOCKED" } | ConvertTo-Json | Set-Content -Path $OutJson -Encoding UTF8
    exit 2
}

$env:PYTHONPATH = (Join-Path $RepoRoot "backend")

Write-PersLog "INFO" "Running Phase 13 data integrity gate..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "CanineSense-DataIntegrity.ps1") 2>&1 | ForEach-Object { Add-Content -Path $LogPath -Value "$_" }
$p13Exit = $LASTEXITCODE
$ErrorActionPreference = $prevEap

Write-PersLog "INFO" "Running Phase 14 persistence & disaster recovery pytest suite..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$p14Out = & $PythonExe -m pytest (Join-Path $RepoRoot "backend\tests\test_data_durability.py") (Join-Path $RepoRoot "backend\tests\test_phase14_durability_recovery.py") -v 2>&1 | Out-String
$p14Exit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
Add-Content -Path $LogPath -Value $p14Out -Encoding UTF8

$passed = 0; $failed = 0
if ($p14Out -match '(\d+)\s+passed') { $passed = [int]$Matches[1] }
if ($p14Out -match '(\d+)\s+failed') { $failed = [int]$Matches[1] }

# Live Render /api/health persistence inspection
$livePersistence = $null
$liveStatus = "UNREACHABLE"
try {
    $health = Invoke-RestMethod -Uri "https://caninesense-backend.onrender.com/api/health" -TimeoutSec 60
    $livePersistence = $health.persistence
    $liveStatus = if ($livePersistence.durable_across_redeploy -eq $true) { "DURABLE" } else { "BLOCKED - OWNER INFRASTRUCTURE APPROVAL REQUIRED" }
} catch {
    $liveStatus = "UNREACHABLE: $($_.Exception.Message)"
}

$archStatus = if ($p13Exit -eq 0 -and $p14Exit -eq 0 -and $failed -eq 0) { "PASS" } else { "FAIL" }
$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    architecture_status = $archStatus
    pytest_persistence_dr = @{ exit_code = $p14Exit; passed = $passed; failed = $failed }
    live_render_persistence = $livePersistence
    production_data_durability = $liveStatus
}
$rep | ConvertTo-Json -Depth 6 | Set-Content -Path $OutJson -Encoding UTF8
Write-PersLog $archStatus "Phase 14 persistence architecture=$archStatus (passed=$passed, failed=$failed), production=$liveStatus"

if ($archStatus -ne "PASS") { exit 1 }
exit 0
