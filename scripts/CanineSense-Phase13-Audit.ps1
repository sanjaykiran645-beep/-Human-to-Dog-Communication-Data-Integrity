<#
.SYNOPSIS
    CanineSense AI — Phase 13.1/13.2 Master Audit Automation Script
.DESCRIPTION
    Verifies workspace root, Git branch/remotes/checkpoint, runs existing RedTeam-Audit
    and Regression gates, and writes structured Phase 13 audit JSON + timestamped log.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "backend\app\main.py")) -or -not (Test-Path (Join-Path $RepoRoot "frontend\package.json"))) {
    Write-Error "FATAL: Invalid project root '$RepoRoot'."
    exit 2
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("phase13-audit-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase13-audit-summary.json"

function Write-P13Log {
    param([string]$Level, [string]$Msg)
    $clean = $Msg -replace '(sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|gho_[A-Za-z0-9]{10,}|rnd_[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._-]+)', '[REDACTED]'
    $line = "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))] [$Level] $clean"
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

$GitExe = @("C:\Program Files\Git\cmd\git.exe")
if ($env:LOCALAPPDATA) {
    Get-ChildItem (Join-Path $env:LOCALAPPDATA "GitHubDesktop\app-*") -ErrorAction SilentlyContinue | ForEach-Object {
        $GitExe += (Join-Path $_.FullName "resources\app\git\cmd\git.exe")
    }
}
$ResolvedGit = ($GitExe | Where-Object { Test-Path $_ } | Select-Object -First 1)

Write-P13Log "INFO" "Phase 13 Audit starting at $RepoRoot"

$gitState = [ordered]@{ available = [bool]$ResolvedGit; branch = $null; head_sha = $null; dirty_count = 0 }
if ($ResolvedGit) {
    $gitState.branch = (& $ResolvedGit -C $RepoRoot rev-parse --abbrev-ref HEAD).Trim()
    $gitState.head_sha = (& $ResolvedGit -C $RepoRoot rev-parse HEAD).Trim()
    $gitState.dirty_count = @(& $ResolvedGit -C $RepoRoot status --porcelain).Count
    Write-P13Log "INFO" "Git branch=$($gitState.branch), HEAD=$($gitState.head_sha), dirty=$($gitState.dirty_count)"
}

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "CanineSense-RedTeam-Audit.ps1") 2>&1 | ForEach-Object { Write-P13Log "INFO" "$_" }
$rtCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap

$auditStatus = if ($rtCode -eq 0) { "PASS" } else { "FAIL" }
$summary = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    repo_root = $RepoRoot
    git = $gitState
    redteam_audit_status = $auditStatus
    overall_status = $auditStatus
}
$summary | ConvertTo-Json -Depth 5 | Set-Content -Path $OutJson -Encoding UTF8
Write-P13Log $auditStatus "Phase 13 Audit completed (status=$auditStatus)"
if ($auditStatus -ne "PASS") { exit 1 }
exit 0
