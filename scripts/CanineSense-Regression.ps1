<#
.SYNOPSIS
    CanineSense AI — Phase 2 Regression Execution Script
.DESCRIPTION
    Executes actual backend pytest suites (full, Engine A, Engine B, Priority 7, Priority 8,
    and security tests) plus frontend TypeScript check, Vite build, and oxlint.
    Fails with non-zero exit code if required tools are missing or any gate fails.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "backend\app\main.py"))) {
    Write-Error "FATAL: Invalid repository root '$RepoRoot'."
    exit 2
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("regression-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$ResultJsonPath = Join-Path $LogDir "latest-regression-results.json"

function Write-RegLog {
    param([string]$Level, [string]$Message)
    $redacted = $Message -replace '(sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._-]+)', '[REDACTED]'
    $line = "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))] [$Level] $redacted"
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Resolve-PythonExe {
    $candidates = @()
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
    if ($env:LOCALAPPDATA) {
        $candidates += @(
            (Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"),
            (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
            (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
            (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe")
        )
    }
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) {
            try {
                $ver = & $c --version 2>&1
                if ($LASTEXITCODE -eq 0) { return $c }
            } catch {}
        }
    }
    return $null
}

$PythonExe = Resolve-PythonExe
$NpmExe = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
if (-not $NpmExe) { $NpmExe = (Get-Command npm -ErrorAction SilentlyContinue) }
$NpxExe = (Get-Command npx.cmd -ErrorAction SilentlyContinue)
if (-not $NpxExe) { $NpxExe = (Get-Command npx -ErrorAction SilentlyContinue) }
$NodeExe = (Get-Command node -ErrorAction SilentlyContinue)

$results = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    repo_root = $RepoRoot
    python_exe = $PythonExe
    node_exe = if ($NodeExe) { $NodeExe.Source } else { $null }
    suites = [System.Collections.Generic.List[object]]::new()
    overall_status = "PASS"
}

function Invoke-Step {
    param([string]$Name, [scriptblock]$Action)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    Write-RegLog "INFO" "Running suite: $Name"
    $output = ""
    $code = 0
    try {
        $output = (& $Action 2>&1 | Out-String)
        $code = $LASTEXITCODE
    } catch {
        $output = $_.Exception.Message
        $code = 1
    }
    $sw.Stop()
    $passed = 0; $failed = 0; $skipped = 0
    if ($output -match '(\d+)\s+passed') { $passed = [int]$Matches[1] }
    if ($output -match '(\d+)\s+failed') { $failed = [int]$Matches[1] }
    if ($output -match '(\d+)\s+skipped') { $skipped = [int]$Matches[1] }

    $status = if ($code -eq 0) { "PASS" } else { "FAIL" }
    if ($status -ne "PASS") { $results.overall_status = "FAIL" }

    $results.suites.Add([ordered]@{
        name = $Name
        status = $status
        exit_code = $code
        duration_sec = [math]::Round($sw.Elapsed.TotalSeconds, 2)
        passed = $passed
        failed = $failed
        skipped = $skipped
        summary_tail = (($output -split "`r?`n" | Select-Object -Last 8) -join "`n")
    })
    Add-Content -Path $LogPath -Value $output -Encoding UTF8
    Write-RegLog $status "$Name completed (exit=$code, passed=$passed, failed=$failed, skipped=$skipped, $($sw.Elapsed.TotalSeconds.ToString('F2'))s)"
}

if (-not $PythonExe) {
    Write-RegLog "FAIL" "Python interpreter not found or inaccessible in current execution context."
    $results.overall_status = "BLOCKED"
    $results.suites.Add([ordered]@{ name = "backend_pytest"; status = "BLOCKED"; exit_code = 127; passed = 0; failed = 0; skipped = 0; summary_tail = "Python interpreter unavailable" })
} else {
    $env:PYTHONPATH = (Join-Path $RepoRoot "backend")
    Invoke-Step "backend_pytest_full" { & $PythonExe -m pytest (Join-Path $RepoRoot "backend\tests") -v }
    Invoke-Step "backend_priority8_audio_matrix" { & $PythonExe -m pytest (Join-Path $RepoRoot "backend\tests\test_communicator_audio_matrix.py") -v }
    Invoke-Step "backend_priority7_validation_lab" { & $PythonExe -m pytest (Join-Path $RepoRoot "backend\tests\test_experimental_validation.py") -v }
    Invoke-Step "backend_security_suite" { & $PythonExe -m pytest (Join-Path $RepoRoot "backend\tests\test_auth.py") (Join-Path $RepoRoot "backend\tests\test_security_hardening.py") (Join-Path $RepoRoot "backend\tests\test_security_idor.py") -v }
}

if (-not $NpmExe) {
    Write-RegLog "FAIL" "npm not found."
    $results.overall_status = "FAIL"
    $results.suites.Add([ordered]@{ name = "frontend_checks"; status = "BLOCKED"; exit_code = 127; passed = 0; failed = 0; skipped = 0; summary_tail = "npm unavailable" })
} else {
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        Invoke-Step "frontend_lint_oxlint" { & $NpmExe.Source run lint }
        Invoke-Step "frontend_typecheck_tsc" { & $NpxExe.Source tsc -b }
        Invoke-Step "frontend_vite_build" { & $NpmExe.Source run build }
    } finally {
        Pop-Location
    }
}

$results | ConvertTo-Json -Depth 6 | Set-Content -Path $ResultJsonPath -Encoding UTF8
Write-RegLog "INFO" "Saved structured regression results to $ResultJsonPath (overall=$($results.overall_status))"

if ($results.overall_status -ne "PASS") {
    exit 1
}
exit 0
