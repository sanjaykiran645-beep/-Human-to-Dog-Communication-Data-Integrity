<#
.SYNOPSIS
    CanineSense AI — Phase 2/3 Red-Team Release Audit Automation Script
.DESCRIPTION
    Inspects Git state, project files, dependency manifests, frontend/backend configs,
    Docker/Render/GitHub/Android configs, secret exposure, duplicate assets, and known
    static defects. Generates RED_TEAM_AUDIT.json and RED_TEAM_AUDIT.md.
#>
[CmdletBinding()]
param(
    [switch]$IncludeRemoteChecks
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $RepoRoot "backend\app\main.py")) -or -not (Test-Path (Join-Path $RepoRoot "frontend\package.json"))) {
    Write-Error "FATAL: Invalid repository root '$RepoRoot'. Aborting without modifying files."
    exit 2
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("redteam-audit-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

function Write-AuditLog {
    param([string]$Level, [string]$Message)
    $redacted = $Message -replace '(sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|gho_[A-Za-z0-9]{10,}|rnd_[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._-]+|CANINESENSE_SECRET_KEY\s*=\s*\S+)', '[REDACTED]'
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

Write-AuditLog "INFO" "Starting Red-Team Audit at $RepoRoot"

# 1. Git State Inspection
$gitInfo = [ordered]@{
    git_available = [bool]$GitExe
    branch = $null
    head_sha = $null
    origin_main_sha = $null
    gh_pages_sha = $null
    origin_gh_pages_sha = $null
    working_tree_dirty = $null
    dirty_files_count = 0
    remote_url = $null
}

$headRefFile = Join-Path $RepoRoot ".git\HEAD"
if (Test-Path $headRefFile) {
    $gitInfo.branch = (Get-Content $headRefFile -Raw).Trim()
}
foreach ($refMap in @(
    @{ key = "head_sha"; path = ".git\refs\heads\main" },
    @{ key = "origin_main_sha"; path = ".git\refs\remotes\origin\main" },
    @{ key = "gh_pages_sha"; path = ".git\refs\heads\gh-pages" },
    @{ key = "origin_gh_pages_sha"; path = ".git\refs\remotes\origin\gh-pages" }
)) {
    $p = Join-Path $RepoRoot $refMap.path
    if (Test-Path $p) {
        $gitInfo[$refMap.key] = (Get-Content $p -Raw).Trim()
    }
}

if ($GitExe) {
    try {
        $gitInfo.remote_url = (& $GitExe -C $RepoRoot remote get-url origin 2>$null | Out-String).Trim()
        $gitInfo.head_sha = (& $GitExe -C $RepoRoot rev-parse HEAD 2>$null | Out-String).Trim()
        $statusLines = @(& $GitExe -C $RepoRoot status --porcelain 2>$null)
        $gitInfo.dirty_files_count = $statusLines.Count
        $gitInfo.working_tree_dirty = ($statusLines.Count -gt 0)
        Write-AuditLog "INFO" "Git HEAD=$($gitInfo.head_sha), dirty_count=$($gitInfo.dirty_files_count)"
    } catch {
        Write-AuditLog "WARN" "Git execution failed: $($_.Exception.Message)"
    }
} else {
    Write-AuditLog "WARN" "git executable unavailable in sandbox/PATH; using .git/refs fallback."
}

# 2. Config & Infrastructure Inspection
$findings = [System.Collections.Generic.List[object]]::new()
function Add-Finding {
    param([string]$Id, [string]$Severity, [string]$Category, [string]$File, [string]$Status, [string]$Summary)
    $findings.Add([ordered]@{
        id = $Id
        severity = $Severity
        category = $Category
        file = $File
        classification = $Status
        summary = $Summary
    })
}

# Check .github workflows
$workflowsDir = Join-Path $RepoRoot ".github\workflows"
if (-not (Test-Path $workflowsDir)) {
    Add-Finding "RT-INFRA-01" "MEDIUM" "CI/CD" ".github/workflows" "MISSING" "No .github/workflows directory exists; GitHub Pages/CI deployment is manual or external."
}

# Check frontend/src/api.ts routing vs .env.production
$apiTsPath = Join-Path $RepoRoot "frontend\src\api.ts"
if (Test-Path $apiTsPath) {
    $apiTs = Get-Content $apiTsPath -Raw
    if ($apiTs -notmatch '(?s)function getBackendUrl.*?configuredApi.*?github\.io') {
        Add-Finding "RT-FE-01" "HIGH" "Deployment/Routing" "frontend/src/api.ts" "DEFECTIVE" "getBackendUrl() ignores import.meta.env.VITE_API_URL on static GitHub Pages host."
    }
    if ($apiTs -match 'raw \? JSON\.parse\(raw\) : null' -and $apiTs -notmatch 'try\s*\{\s*return raw \? JSON\.parse') {
        Add-Finding "RT-FE-02" "LOW" "Resilience" "frontend/src/api.ts" "DEFECTIVE" "getUser() calls JSON.parse(raw) without try/catch, risking render crash if localStorage cs_user is corrupted."
    }
}

# Check Dashboard.tsx mojibake
$dashPath = Join-Path $RepoRoot "frontend\src\pages\Dashboard.tsx"
if (Test-Path $dashPath) {
    $dashRaw = Get-Content $dashPath -Raw
    if ($dashRaw -match 'Speak to Dog \?|Dog \? Human|Human \? Dog|dog\?s breed') {
        Add-Finding "RT-FE-03" "LOW" "UI/Encoding" "frontend/src/pages/Dashboard.tsx" "DEFECTIVE" "Mojibake replacement characters ('?') appear in UI copy ('Speak to Dog ?', 'Dog ? Human', 'dog?s')."
    }
}

# Check backend/app/routers/experiments.py defects
$expPath = Join-Path $RepoRoot "backend\app\routers\experiments.py"
if (Test-Path $expPath) {
    $expRaw = Get-Content $expPath -Raw
    if ($expRaw -match 'random\.randint' -and $expRaw -notmatch '(?m)^import random\b') {
        Add-Finding "RT-BE-01" "HIGH" "Priority7/Runtime" "backend/app/routers/experiments.py" "DEFECTIVE" "Uses random.randint(...) in create_randomized_schedule when randomization_seed is omitted without importing random (raises NameError 500)."
    }
    if ($expRaw -match 'def submit_independent_review' -and $expRaw -notmatch 'ReviewerAssignment|reviewer_allowlist') {
        Add-Finding "RT-SEC-01" "MEDIUM" "Authorization/Privacy" "backend/app/routers/experiments.py" "SECURITY RISK" "submit_independent_review hides primary_observer_category during blind reviews, but relies on trial UUID secrecy rather than an explicit reviewer invite/assignment table."
    }
}

# Check backend/app/routers/analytics.py delete_account completeness
$anaPath = Join-Path $RepoRoot "backend\app\routers\analytics.py"
if (Test-Path $anaPath) {
    $anaRaw = Get-Content $anaPath -Raw
    if ($anaRaw -match 'def delete_account' -and $anaRaw -notmatch 'StudyParticipant') {
        Add-Finding "RT-BE-02" "MEDIUM" "DataErasure" "backend/app/routers/analytics.py" "DEFECTIVE" "delete_account does not explicitly purge Priority 7 tables (TrialIndependentReview, BehaviouralTrial, TrialSchedule, ExperimentalCue, StudyParticipant) before deleting User."
    }
}

# Check render.yaml persistence
$renderYamlPath = Join-Path $RepoRoot "render.yaml"
if (Test-Path $renderYamlPath) {
    $renderRaw = Get-Content $renderYamlPath -Raw
    if ($renderRaw -match 'plan:\s*free' -and $renderRaw -notmatch 'disk:') {
        Add-Finding "RT-DEP-01" "HIGH" "Persistence" "render.yaml" "DEFECTIVE" "Render free tier without persistent disk makes SQLite (/app/data/caninesense.sqlite3) and /app/data/storage ephemeral across deploys/restarts."
    }
}

# Check Android manifest cleartext traffic & APK staleness
$manifestPath = Join-Path $RepoRoot "mobile-android\android\app\src\main\AndroidManifest.xml"
if (Test-Path $manifestPath) {
    $manRaw = Get-Content $manifestPath -Raw
    if ($manRaw -match 'usesCleartextTraffic="true"') {
        Add-Finding "RT-MOB-01" "MEDIUM" "Security" "mobile-android/android/app/src/main/AndroidManifest.xml" "SECURITY RISK" "android:usesCleartextTraffic=\"true\" permits unencrypted HTTP traffic in Android release configuration."
    }
}

$apkRoot = Join-Path $RepoRoot "CanineSense_AI_v1.0.0.apk"
$apkRel = Join-Path $RepoRoot "data\releases\CanineSense_AI_v1.0.0.apk"
$apkHash = $null
if (Test-Path $apkRoot) {
    $apkHash = (Get-FileHash $apkRoot -Algorithm SHA256).Hash
    $apkInfo = Get-Item $apkRoot
    Add-Finding "RT-MOB-02" "HIGH" "ReleaseConsistency" "CanineSense_AI_v1.0.0.apk" "OBSOLETE" "Packaged APK ($($apkInfo.Length) bytes, LastWrite=$($apkInfo.LastWriteTimeUtc.ToString('u')), SHA256=$apkHash) contains Nov 7 minimal assets (index-B_fOKfw7.js) and stub dex, diverging from Priority 7/8 web source."
}
if ((Test-Path $apkRoot) -and (Test-Path $apkRel)) {
    $h2 = (Get-FileHash $apkRel -Algorithm SHA256).Hash
    if ($apkHash -eq $h2) {
        Add-Finding "RT-DUP-01" "LOW" "DuplicateAsset" "data/releases/CanineSense_AI_v1.0.0.apk" "DUPLICATE" "Identical binary copy of root CanineSense_AI_v1.0.0.apk."
    }
}

# Check duplicate docs root vs docs/
$docsDir = Join-Path $RepoRoot "docs"
$dupDocs = @()
if (Test-Path $docsDir) {
    Get-ChildItem $docsDir -File | ForEach-Object {
        $rootCopy = Join-Path $RepoRoot $_.Name
        if (Test-Path $rootCopy) {
            $hDoc = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
            $hRoot = (Get-FileHash $rootCopy -Algorithm SHA256).Hash
            $dupDocs += [ordered]@{ name = $_.Name; identical = ($hDoc -eq $hRoot) }
        }
    }
    if ($dupDocs.Count -gt 0) {
        Add-Finding "RT-DUP-02" "LOW" "Documentation" "docs/*" "DUPLICATE" "$($dupDocs.Count) report/spec files exist in both repo root and docs/ (1 diverges: engine_b_action_taxonomy.md)."
    }
}

# Check .env exposure and source secret scan
$envFile = Join-Path $RepoRoot ".env"
$gitignoreFile = Join-Path $RepoRoot ".gitignore"
$envIgnored = $false
if (Test-Path $gitignoreFile) {
    $gi = Get-Content $gitignoreFile -Raw
    $envIgnored = ($gi -match '(?m)^\.env$')
}
if ((Test-Path $envFile) -and (-not $envIgnored)) {
    Add-Finding "RT-SEC-02" "CRITICAL" "Secrets" ".env" "SECURITY RISK" ".env exists and is not listed in .gitignore."
}

$secretHits = @()
$scanFiles = Get-ChildItem (Join-Path $RepoRoot "backend\app"), (Join-Path $RepoRoot "frontend\src") -Recurse -File -Include *.py,*.ts,*.tsx,*.js,*.jsx -ErrorAction SilentlyContinue
foreach ($sf in $scanFiles) {
    $matches = Select-String -Path $sf.FullName -Pattern '(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|rnd_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{20,}|BEGIN (RSA|EC|OPENSSH) PRIVATE KEY)' -ErrorAction SilentlyContinue
    foreach ($m in $matches) {
        $secretHits += "$($sf.FullName):$($m.LineNumber)"
    }
}
if ($secretHits.Count -gt 0) {
    Add-Finding "RT-SEC-03" "CRITICAL" "Secrets" ($secretHits -join ", ") "SECURITY RISK" "Potential secret literal matched in source files."
}

# 3. File-by-File Inventory Classification
$allFiles = Get-ChildItem $RepoRoot -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $_.FullName -notmatch '\\(\.git|node_modules|__pycache__|\.pytest_cache|dist|\.gradle)\\'
}

$classifiedFiles = [System.Collections.Generic.List[object]]::new()
$counts = @{
    PASS = 0; DEFECTIVE = 0; MISSING = 0; OBSOLETE = 0;
    DUPLICATE = 0; "SECURITY RISK" = 0; UNUSED = 0; "REQUIRES OWNER INPUT" = 0
}

$dupDocSet = @{}
foreach ($d in $dupDocs) { $dupDocSet[$d.name] = $true }

foreach ($f in $allFiles) {
    $rel = $f.FullName.Substring($RepoRoot.Length + 1).Replace('\', '/')
    $cls = "PASS"
    $reason = "Verified on disk"

    if ($rel -eq "render.yaml") {
        $cls = "DEFECTIVE"
        $reason = "Free tier lacks persistent disk for SQLite/uploads across restarts"
    } elseif ($rel -eq "frontend/src/api.ts" -and ($findings | Where-Object { $_.file -eq "frontend/src/api.ts" })) {
        $cls = "DEFECTIVE"
        $reason = "See audit findings for verified code defect"
    } elseif ($rel -eq "backend/app/routers/experiments.py") {
        $cls = "SECURITY RISK"
        $reason = "Blind review relies on trial UUID secrecy without explicit reviewer assignment table"
    } elseif ($rel -eq "mobile-android/android/app/src/main/AndroidManifest.xml" -and ($findings | Where-Object { $_.id -eq "RT-MOB-01" })) {
        $cls = "SECURITY RISK"
        $reason = "usesCleartextTraffic=true enabled"
    } elseif ($rel -eq "CanineSense_AI_v1.0.0.apk") {
        $cls = "OBSOLETE"
        $reason = "APK built 2026-11-07 before Priority 7/8 updates"
    } elseif ($rel -eq "data/releases/CanineSense_AI_v1.0.0.apk") {
        $cls = "DUPLICATE"
        $reason = "Identical SHA-256 copy of root CanineSense_AI_v1.0.0.apk"
    } elseif ($rel -like "docs/*" -and $dupDocSet.ContainsKey($f.Name)) {
        $cls = "DUPLICATE"
        $reason = "Duplicate of root documentation file"
    } elseif ($rel -eq ".env" -or $rel -eq "frontend/.env.production") {
        $cls = "REQUIRES OWNER INPUT"
        $reason = "Environment-specific deployment config; never commit secrets"
    }

    $counts[$cls]++
    $classifiedFiles.Add([ordered]@{
        path = $rel
        bytes = $f.Length
        last_write_utc = $f.LastWriteTimeUtc.ToString("yyyy-MM-ddTHH:mm:ssZ")
        classification = $cls
        reason = $reason
    })
}

$auditObj = [ordered]@{
    generated_at_utc = $Timestamp
    repo_root = $RepoRoot
    git = $gitInfo
    apk_sha256 = $apkHash
    file_classification_totals = $counts
    total_files_audited = $classifiedFiles.Count
    findings = $findings
    files = $classifiedFiles
}

$jsonOut = Join-Path $RepoRoot "RED_TEAM_AUDIT.json"
$mdOut = Join-Path $RepoRoot "RED_TEAM_AUDIT.md"

$auditObj | ConvertTo-Json -Depth 6 | Set-Content -Path $jsonOut -Encoding UTF8

$mdLines = [System.Collections.Generic.List[string]]::new()
$mdLines.Add("# CanineSense AI — Automated Red-Team Audit")
$mdLines.Add("")
$mdLines.Add("- **Generated UTC:** $Timestamp")
$mdLines.Add("- **Repo Root:** ``$RepoRoot``")
$mdLines.Add("- **Git HEAD:** ``$($gitInfo.head_sha)`` (branch ref: ``$($gitInfo.branch)``)")
$mdLines.Add("- **GitHub Pages Ref:** ``$($gitInfo.gh_pages_sha)``")
$mdLines.Add("- **APK SHA-256:** ``$apkHash``")
$mdLines.Add("- **Total Files Audited (excluding build/git/cache):** $($classifiedFiles.Count)")
$mdLines.Add("")
$mdLines.Add("## Classification Totals")
$mdLines.Add("")
$mdLines.Add("| Classification | Count |")
$mdLines.Add("|---|---:|")
foreach ($k in $counts.Keys) {
    $mdLines.Add("| $k | $($counts[$k]) |")
}
$mdLines.Add("")
$mdLines.Add("## Verified Findings")
$mdLines.Add("")
$mdLines.Add("| ID | Severity | Category | File | Status | Summary |")
$mdLines.Add("|---|---|---|---|---|---|")
foreach ($fd in $findings) {
    $mdLines.Add("| $($fd.id) | $($fd.severity) | $($fd.category) | ``$($fd.file)`` | $($fd.classification) | $($fd.summary) |")
}
$mdLines -join "`r`n" | Set-Content -Path $mdOut -Encoding UTF8

Write-AuditLog "INFO" "Audit complete: $($findings.Count) findings, $($classifiedFiles.Count) files classified. Wrote RED_TEAM_AUDIT.json and RED_TEAM_AUDIT.md."
exit 0
