<#
.SYNOPSIS
    CanineSense AI — Phase 13 Master Release Gate & Verification Orchestrator
.DESCRIPTION
    Executes Phase 13 Audit, Data Integrity, Security Hardening, ML Evaluation,
    Full Regression, Android Readiness, and Release Verification in sequence.
    Optionally triggers Deployment Recovery only when all software release gates pass.
#>
[CmdletBinding()]
param(
    [switch]$DeployAfterGates
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("phase13-release-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

function Write-RelLog {
    param([string]$Level, [string]$Msg)
    $line = "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))] [$Level] $Msg"
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

$steps = @(
    @{ name = "Phase13_Audit"; script = "CanineSense-Phase13-Audit.ps1"; args = @(); allowBlocked = $false },
    @{ name = "DataIntegrity"; script = "CanineSense-DataIntegrity.ps1"; args = @(); allowBlocked = $false },
    @{ name = "SecurityHardening"; script = "CanineSense-SecurityHardening.ps1"; args = @(); allowBlocked = $false },
    @{ name = "MLEvaluation"; script = "CanineSense-ML-Improvement.ps1"; args = @(); allowBlocked = $false },
    @{ name = "FullRegression"; script = "CanineSense-Regression.ps1"; args = @(); allowBlocked = $false },
    @{ name = "AndroidReadiness"; script = "CanineSense-Android-Readiness.ps1"; args = @(); allowBlocked = $true },
    @{ name = "ReleaseVerify"; script = "CanineSense-Release-Verify.ps1"; args = @("-CheckLiveProduction"); allowBlocked = $false }
)

$gateFailed = $false
foreach ($st in $steps) {
    Write-RelLog "INFO" "Running $($st.name) ($($st.script))..."
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot $st.script) @($st.args) 2>&1 | ForEach-Object { Add-Content -Path $LogPath -Value "$_" }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($code -eq 0) {
        Write-RelLog "PASS" "$($st.name) passed."
    } elseif ($st.allowBlocked -and $code -eq 2) {
        Write-RelLog "BLOCKED" "$($st.name) reported BLOCKED (expected when Android SDK absent)."
    } else {
        Write-RelLog "FAIL" "$($st.name) failed with exit code $code."
        $gateFailed = $true
        break
    }
}

if ($gateFailed) {
    Write-RelLog "FAIL" "Phase 13 software release gates failed. Deployment aborted."
    exit 1
}

if ($DeployAfterGates) {
    Write-RelLog "INFO" "All software release gates passed. Invoking Deployment Recovery..."
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "CanineSense-Deployment-Recovery.ps1") -ExecuteDeploy 2>&1 | ForEach-Object { Write-RelLog "INFO" "$_" }
    $depCode = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($depCode -ne 0) {
        Write-RelLog "FAIL" "Deployment recovery failed (exit=$depCode)."
        exit 1
    }
}

Write-RelLog "PASS" "Phase 13 Release Orchestrator complete."
exit 0
