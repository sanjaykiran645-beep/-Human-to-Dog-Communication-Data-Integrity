<#
.SYNOPSIS
    CanineSense AI — Phase 2/10 Safe Deployment Recovery & Release Gate Script
.DESCRIPTION
    Enforces audit and regression gates before any deployment action.
    Defaults to safe DRY-RUN verification. Never force-pushes, never deletes branches,
    never prints secrets, and never asks for tokens in chat.
#>
[CmdletBinding()]
param(
    [switch]$ExecuteDeploy,
    [string]$TargetRepo = "sanjaykiran645-beep/-Human-to-Dog-Communication-Data-Integrity",
    [string]$TargetBranch = "main"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "backend\app\main.py"))) {
    Write-Error "FATAL: Invalid repository root '$RepoRoot'."
    exit 2
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("deploy-recovery-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

function Write-DepLog {
    param([string]$Level, [string]$Message)
    $redacted = $Message -replace '(sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|gho_[A-Za-z0-9]{10,}|rnd_[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._-]+)', '[REDACTED]'
    $line = "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))] [$Level] $redacted"
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Resolve-Tool {
    param([string]$Name, [string[]]$ExtraPaths = @())
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in $ExtraPaths) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

$GitExtra = @("C:\Program Files\Git\cmd\git.exe", "C:\Program Files\Git\bin\git.exe")
if ($env:LOCALAPPDATA) {
    Get-ChildItem (Join-Path $env:LOCALAPPDATA "GitHubDesktop\app-*") -ErrorAction SilentlyContinue | ForEach-Object {
        $GitExtra += (Join-Path $_.FullName "resources\app\git\cmd\git.exe")
    }
}
$GitExe = Resolve-Tool -Name "git" -ExtraPaths $GitExtra
$GhExe = Resolve-Tool -Name "gh"
$RenderExe = Resolve-Tool -Name "render"

Write-DepLog "INFO" "Deployment recovery started (ExecuteDeploy=$ExecuteDeploy, Target=$TargetRepo@$TargetBranch)"

# 1. Verify Audit and Regression Gates
$regPath = Join-Path $LogDir "latest-regression-results.json"
$auditPath = Join-Path $RepoRoot "RED_TEAM_AUDIT.json"
if (-not (Test-Path $regPath)) {
    Write-DepLog "FAIL" "Regression results missing ($regPath). Run CanineSense-Regression.ps1 first."
    exit 1
}
$reg = Get-Content $regPath -Raw | ConvertFrom-Json
if ($reg.overall_status -ne "PASS") {
    Write-DepLog "FAIL" "Regression gate status is $($reg.overall_status). Deployment blocked."
    exit 1
}
if (-not (Test-Path $auditPath)) {
    Write-DepLog "FAIL" "Red-team audit report missing ($auditPath). Run CanineSense-RedTeam-Audit.ps1 first."
    exit 1
}
Write-DepLog "PASS" "Local regression and audit gates verified."

# 2. Verify Git State & Rollback Anchor
if (-not $GitExe) {
    Write-DepLog "FAIL" "git executable unavailable. Cannot safely reconcile or push remote branches."
    exit 1
}

$currentBranch = (& $GitExe -C $RepoRoot rev-parse --abbrev-ref HEAD).Trim()
$headSha = (& $GitExe -C $RepoRoot rev-parse HEAD).Trim()
$originUrl = (& $GitExe -C $RepoRoot remote get-url origin).Trim()
Write-DepLog "INFO" "Rollback point recorded: branch=$currentBranch, HEAD=$headSha, origin=$originUrl"

if ($originUrl -notmatch [regex]::Escape($TargetRepo)) {
    Write-DepLog "FAIL" "Origin URL '$originUrl' does not match target repo '$TargetRepo'."
    exit 1
}
if ($currentBranch -ne $TargetBranch) {
    Write-DepLog "FAIL" "Current branch '$currentBranch' != expected '$TargetBranch'."
    exit 1
}

# Check for any secret files staged or tracked (excluding .example templates)
$trackedSecrets = @(& $GitExe -C $RepoRoot ls-files ".env" ".env.*" "*.secret" ".secret" "*.sqlite3" 2>$null | Where-Object { $_ -and $_ -notmatch '\.example$' })
if ($trackedSecrets.Count -gt 0) {
    Write-DepLog "FAIL" "Sensitive file tracked in Git: $($trackedSecrets -join ', '). Aborting."
    exit 1
}

# 3. Verify GitHub & Render auth without printing credentials
if ($GhExe) {
    $ghCheck = & $GhExe auth status 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Write-DepLog "WARN" "GitHub CLI not authenticated. Run 'gh auth login --web' in browser to authorize."
        if ($ExecuteDeploy) { exit 1 }
    } else {
        Write-DepLog "PASS" "GitHub CLI authentication present."
    }
} else {
    Write-DepLog "WARN" "gh CLI not found."
}

if ($RenderExe) {
    Write-DepLog "INFO" "Render CLI available at $RenderExe"
} else {
    Write-DepLog "WARN" "Render CLI not found."
}

if (-not $ExecuteDeploy) {
    Write-DepLog "INFO" "DRY-RUN complete. No remote mutations performed. Pass -ExecuteDeploy after all gates pass to execute fast-forward deployment."
    exit 0
}

# 4. Safe Fast-Forward Deployment Execution (no force-push, no branch deletion)
Write-DepLog "INFO" "Fetching origin without overwriting local history..."
& $GitExe -C $RepoRoot fetch origin
if ($LASTEXITCODE -ne 0) {
    Write-DepLog "FAIL" "git fetch origin failed."
    exit 1
}

$dirty = @(& $GitExe -C $RepoRoot status --porcelain)
if ($dirty.Count -gt 0) {
    Write-DepLog "FAIL" "Working tree has uncommitted changes ($($dirty.Count)). Commit verified changes cleanly before deploying."
    exit 1
}

Write-DepLog "INFO" "Checking fast-forward safety against origin/$TargetBranch..."
& $GitExe -C $RepoRoot merge-base --is-ancestor "origin/$TargetBranch" HEAD
if ($LASTEXITCODE -ne 0) {
    Write-DepLog "FAIL" "Local HEAD is not a fast-forward descendant of origin/$TargetBranch. Reconcile without force-push before deploying."
    exit 1
}

Write-DepLog "INFO" "Pushing $TargetBranch to origin (fast-forward only)..."
& $GitExe -C $RepoRoot push origin $TargetBranch
if ($LASTEXITCODE -ne 0) {
    Write-DepLog "FAIL" "git push origin $TargetBranch failed."
    exit 1
}

Write-DepLog "PASS" "Fast-forward push to origin/$TargetBranch succeeded at commit $headSha."
exit 0
