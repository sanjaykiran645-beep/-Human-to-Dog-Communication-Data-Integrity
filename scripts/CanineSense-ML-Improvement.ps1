<#
.SYNOPSIS
    CanineSense AI — Phase 13 Priority C Engine A ML Reproduction & Verification Script
.DESCRIPTION
    Reproduces the dog-independent 6-class Engine A evaluation without altering held-out test splits,
    computes dataset/model SHA-256 hashes, and verifies honest reporting of the 90% accuracy gate.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$EvalScript = Join-Path $RepoRoot "scripts\reproduce_engine_a_eval.py"
if (-not (Test-Path $EvalScript)) {
    Write-Error "FATAL: Missing $EvalScript"
    exit 2
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("ml-improvement-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase13-ml-evaluation.json"

function Write-MlLog {
    param([string]$Level, [string]$Msg)
    $line = "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))] [$Level] $Msg"
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
    Write-MlLog "BLOCKED" "Python interpreter unavailable."
    exit 2
}

$manifestHash = (Get-FileHash (Join-Path $RepoRoot "data\reference_library\manifest.csv") -Algorithm SHA256).Hash
$rfHash = $null
$rfPath = Join-Path $RepoRoot "data\models\candidates\rf_candidate.joblib"
if (Test-Path $rfPath) { $rfHash = (Get-FileHash $rfPath -Algorithm SHA256).Hash }

Write-MlLog "INFO" "Executing Engine A dog-independent evaluation (manifest_sha256=$manifestHash)..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$evalOut = & $PythonExe $EvalScript 2>&1 | Out-String
$evalExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
Add-Content -Path $LogPath -Value $evalOut -Encoding UTF8

$metricsObj = $null
$metricsPath = Join-Path $RepoRoot "docs\engine_a_metrics.json"
if (Test-Path $metricsPath) {
    $metricsObj = Get-Content $metricsPath -Raw | ConvertFrom-Json
}

$targetMet = if ($metricsObj) { [bool]$metricsObj.scientific_assessment.target_met } else { $false }
$balAcc = if ($metricsObj) { $metricsObj.balanced_accuracy } else { $null }
$gateStatus = if ($evalExit -ne 0) { "FAIL" } elseif ($targetMet) { "PASS" } else { "FAIL" }

$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    manifest_sha256 = $manifestHash
    rf_candidate_sha256 = $rfHash
    eval_script_exit_code = $evalExit
    balanced_accuracy = $balAcc
    overall_accuracy = if ($metricsObj) { $metricsObj.accuracy } else { $null }
    macro_f1 = if ($metricsObj) { $metricsObj.macro_f1 } else { $null }
    ece = if ($metricsObj) { $metricsObj.ece } else { $null }
    target_90pct_met = $targetMet
    scientific_gate_status = $gateStatus
}
$rep | ConvertTo-Json -Depth 5 | Set-Content -Path $OutJson -Encoding UTF8
Write-MlLog "INFO" "Engine A reproduction finished (balanced_accuracy=$balAcc, 90%_gate=$gateStatus)"

# Exit 0 because the evaluation pipeline itself succeeded and reported the scientific gate honestly;
# callers inspect scientific_gate_status in phase13-ml-evaluation.json.
if ($evalExit -ne 0) { exit 1 }
exit 0
