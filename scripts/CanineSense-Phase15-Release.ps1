<#
.SYNOPSIS
    CanineSense AI — Phase 15 Master Release Orchestrator
.DESCRIPTION
    Executes Phase 15 Audit -> Migration Prepare -> Backup Verify -> Security -> ML Evaluation ->
    Full Regression -> Android Readiness (allowBlocked) -> Deployment Verification.
#>
[CmdletBinding()]
param(
    [switch]$ExecuteDeploy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("phase15-release-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase15-release-summary.json"

function Write-P15Log {
    param([string]$Level, [string]$Msg)
    $line = "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))] [$Level] $Msg"
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

$deployArgs = if ($ExecuteDeploy) { @("-ExecuteDeploy") } else { @() }
$stages = @(
    @{ name = "Phase15_Audit"; script = "CanineSense-Phase15-Audit.ps1"; args = @(); allowBlocked = $false },
    @{ name = "Phase15_MigrationPrepare"; script = "CanineSense-Phase15-Migration-Prepare.ps1"; args = @("-SimulateIsolatedMigration"); allowBlocked = $false },
    @{ name = "Phase15_BackupVerify"; script = "CanineSense-Phase15-Backup-Verify.ps1"; args = @(); allowBlocked = $false },
    @{ name = "Phase14_Security"; script = "CanineSense-Phase14-Security.ps1"; args = @(); allowBlocked = $false },
    @{ name = "MLEvaluation"; script = "CanineSense-ML-Improvement.ps1"; args = @(); allowBlocked = $false },
    @{ name = "FullRegression"; script = "CanineSense-Regression.ps1"; args = @(); allowBlocked = $false },
    @{ name = "Phase15_Android"; script = "CanineSense-Phase15-Android-Readiness.ps1"; args = @(); allowBlocked = $true },
    @{ name = "Phase14_Deployment"; script = "CanineSense-Phase14-Deployment.ps1"; args = $deployArgs; allowBlocked = $false }
)

$gateResults = @()
$failed = $false
foreach ($st in $stages) {
    Write-P15Log "INFO" "Running $($st.name) ($($st.script))..."
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot $st.script) @($st.args) 2>&1 | ForEach-Object { Add-Content -Path $LogPath -Value "$_" }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prevEap

    $stStatus = if ($code -eq 0) { "PASS" } elseif ($st.allowBlocked -and $code -eq 2) { "BLOCKED" } else { "FAIL" }
    $gateResults += @{ name = $st.name; status = $stStatus; exit_code = $code }
    Write-P15Log $stStatus "$($st.name) finished (exit=$code)."
    if ($stStatus -eq "FAIL") {
        $failed = $true
        break
    }
}

$overall = if ($failed) { "FAIL" } else { "PARTIAL" }
$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    overall_software_gates = if ($failed) { "FAIL" } else { "PASS" }
    overall_phase15_status = $overall
    production_data_persistence = "BLOCKED - FREE EPHEMERAL INFRASTRUCTURE DOES NOT PROVIDE A VERIFIED DURABLE PRODUCTION GUARANTEE"
    stages = $gateResults
}
$rep | ConvertTo-Json -Depth 5 | Set-Content -Path $OutJson -Encoding UTF8
Write-P15Log "INFO" "Phase 15 Orchestrator complete (software=$( $rep.overall_software_gates ), overall=$overall)."
if ($failed) { exit 1 }
exit 0
