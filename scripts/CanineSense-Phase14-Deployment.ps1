<#
.SYNOPSIS
    CanineSense AI — Phase 14 Deployment Reconciliation & Live Integrity Verification
.DESCRIPTION
    Reconciles local Git HEAD, origin/main, origin/gh-pages, Render live deployment, and live
    GitHub Pages HTML bundle. Optionally executes safe fast-forward push via CanineSense-Deployment-Recovery.ps1.
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
$LogPath = Join-Path $LogDir ("phase14-deployment-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase14-deployment.json"

$GitExtra = @("C:\Program Files\Git\cmd\git.exe")
if ($env:LOCALAPPDATA) {
    Get-ChildItem (Join-Path $env:LOCALAPPDATA "GitHubDesktop\app-*") -ErrorAction SilentlyContinue | ForEach-Object {
        $GitExtra += (Join-Path $_.FullName "resources\app\git\cmd\git.exe")
    }
}
$GitExe = $GitExtra | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $GitExe) { $GitExe = (Get-Command git -ErrorAction Stop).Source }

if ($ExecuteDeploy) {
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "CanineSense-Deployment-Recovery.ps1") -ExecuteDeploy 2>&1 | Tee-Object -FilePath $LogPath -Append
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "CanineSense-Release-Verify.ps1") -CheckLiveProduction 2>&1 | Tee-Object -FilePath $LogPath -Append
$verExit = $LASTEXITCODE

$localHead = (& $GitExe -C $RepoRoot rev-parse HEAD).Trim()
$remoteMain = ((& $GitExe -C $RepoRoot ls-remote origin refs/heads/main) -split '\s+')[0]
$remotePages = ((& $GitExe -C $RepoRoot ls-remote origin refs/heads/gh-pages) -split '\s+')[0]

$renderDeploy = $null
$renderExe = (Get-Command render -ErrorAction SilentlyContinue)
if ($renderExe) {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $deploysRaw = & $renderExe.Source deploys list srv-dbq9o9m7bikc73dctmq0 -o json 2>$null | Out-String
    $ErrorActionPreference = $prevEap
    if ($deploysRaw) {
        $parsed = $deploysRaw | ConvertFrom-Json
        $arr = if ($parsed -is [System.Array]) { $parsed } elseif ($parsed.value) { $parsed.value } else { @($parsed) }
        $live = $arr | Where-Object { $_.status -eq "live" } | Select-Object -First 1
        if ($live) {
            $renderDeploy = @{ id = $live.id; status = $live.status; commit_id = $live.commit.id; finished_at = $live.finishedAt }
        }
    }
}

$liveHealth = Invoke-RestMethod -Uri "https://caninesense-backend.onrender.com/api/health" -TimeoutSec 20
$openapi = Invoke-RestMethod -Uri "https://caninesense-backend.onrender.com/api/openapi.json" -TimeoutSec 20
$routeCount = @($openapi.paths.PSObject.Properties.Name).Count
$pagesHtml = (Invoke-WebRequest -Uri "https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/" -UseBasicParsing -TimeoutSec 20).Content
$bundleMatch = if ($pagesHtml -match 'assets/(index-[A-Za-z0-9_-]+\.js)') { $Matches[1] } else { "unknown" }

$status = if ($verExit -eq 0 -and $liveHealth.status -eq "ok" -and $routeCount -ge 58) { "PASS" } else { "FAIL" }
$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    overall_status = $status
    git_local_head = $localHead
    git_origin_main = $remoteMain
    git_origin_gh_pages = $remotePages
    render_live = $renderDeploy
    live_health_status = $liveHealth.status
    live_persistence = $liveHealth.persistence
    openapi_route_count = $routeCount
    live_pages_bundle = $bundleMatch
}
$rep | ConvertTo-Json -Depth 6 | Set-Content -Path $OutJson -Encoding UTF8
Write-Host "[$status] Phase 14 deployment reconciliation complete (main=$remoteMain, gh-pages=$remotePages, bundle=$bundleMatch, routes=$routeCount)."
if ($status -ne "PASS") { exit 1 }
exit 0
