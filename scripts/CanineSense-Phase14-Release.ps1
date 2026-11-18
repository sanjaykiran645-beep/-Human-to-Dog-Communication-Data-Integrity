<#
.SYNOPSIS
    CanineSense AI — Phase 14 Consolidated Release Gate Orchestrator
.DESCRIPTION
    Executes Audit -> Persistence -> Security -> ML Evaluation -> Full Regression ->
    Android Readiness (allowBlocked) -> Deployment Reconciliation.
    Writes structured gate summary to logs/phase14-release-summary.json.
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
$LogPath = Join-Path $LogDir ("phase14-release-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase14-release-summary.json"

function Write-P14Log {
    param([string]$Level, [string]$Msg)
    $line = "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))] [$Level] $Msg"
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

$deployArgs = if ($ExecuteDeploy) { @("-ExecuteDeploy") } else { @() }
$stages = @(
    @{ name = "Phase13_Audit"; script = "CanineSense-Phase13-Audit.ps1"; args = @(); allowBlocked = $false },
    @{ name = "Phase14_Persistence"; script = "CanineSense-Phase14-Persistence.ps1"; args = @(); allowBlocked = $false },
    @{ name = "Phase14_Security"; script = "CanineSense-Phase14-Security.ps1"; args = @(); allowBlocked = $false },
    @{ name = "MLEvaluation"; script = "CanineSense-ML-Improvement.ps1"; args = @(); allowBlocked = $false },
    @{ name = "FullRegression"; script = "CanineSense-Regression.ps1"; args = @(); allowBlocked = $false },
    @{ name = "Phase14_Android"; script = "CanineSense-Phase14-Android.ps1"; args = @(); allowBlocked = $true },
    @{ name = "Phase14_Deployment"; script = "CanineSense-Phase14-Deployment.ps1"; args = $deployArgs; allowBlocked = $false }
)

$gateResults = @()
$failed = $false
foreach ($st in $stages) {
    Write-P14Log "INFO" "Running $($st.name) ($($st.script))..."
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot $st.script) @($st.args) 2>&1 | ForEach-Object { Add-Content -Path $LogPath -Value "$_" }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prevEap

    $stStatus = if ($code -eq 0) { "PASS" } elseif ($st.allowBlocked -and $code -eq 2) { "BLOCKED" } else { "FAIL" }
    $gateResults += @{ name = $st.name; status = $stStatus; exit_code = $code }
    Write-P14Log $stStatus "$($st.name) finished (exit=$code)."
    if ($stStatus -eq "FAIL") {
        $failed = $true
        break
    }
}

$overall = if ($failed) { "FAIL" } else { "PARTIAL" }
$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    overall_software_gates = if ($failed) { "FAIL" } else { "PASS" }
    overall_phase14_readiness = $overall
    reason_partial = "Production Render persistence remains BLOCKED pending owner approval; Android APK rebuild remains BLOCKED missing JDK/SDK; Engine A 90% and Engine B biological efficacy remain NOT VALIDATED."
    stages = $gateResults
}
$rep | ConvertTo-Json -Depth 5 | Set-Content -Path $OutJson -Encoding UTF8
Write-P14Log "INFO" "Phase 14 Release Orchestrator complete (software=$( $rep.overall_software_gates ), overall=$overall)."
if ($failed) { exit 1 }
exit 0
