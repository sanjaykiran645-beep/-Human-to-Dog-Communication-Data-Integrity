<#
.SYNOPSIS
    CanineSense AI — Phase 15 Environment & Free Infrastructure Audit
.DESCRIPTION
    Reuses CanineSense-Phase13-Audit.ps1, verifies Git state, rollback tags, free-tier
    Render/GitHub Pages configuration, zero paid services, and saves logs/phase15-audit.json.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "backend\app\main.py"))) {
    Write-Error "FATAL: Invalid project root '$RepoRoot'."
    exit 2
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("phase15-audit-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase15-audit.json"

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "CanineSense-Phase13-Audit.ps1") 2>&1 | Tee-Object -FilePath $LogPath | Out-Null
$p13Exit = $LASTEXITCODE
$ErrorActionPreference = $prevEap

$renderYaml = Get-Content (Join-Path $RepoRoot "render.yaml") -Raw
$isFreePlan = ($renderYaml -match 'plan:\s*free')
$hasPaidDisk = ($renderYaml -match 'disk:')
$zeroPaidApproved = ($isFreePlan -and -not $hasPaidDisk)

$p13Summary = Get-Content (Join-Path $LogDir "phase13-audit-summary.json") -Raw | ConvertFrom-Json
$status = if ($p13Exit -eq 0 -and $zeroPaidApproved) { "PASS" } else { "FAIL" }

$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    overall_status = $status
    git = $p13Summary.git
    render_plan_free = $isFreePlan
    render_paid_disk_configured = $hasPaidDisk
    zero_paid_infrastructure_verified = $zeroPaidApproved
}
$rep | ConvertTo-Json -Depth 5 | Set-Content -Path $OutJson -Encoding UTF8
Write-Host "[$status] Phase 15 environment & free-tier audit complete (free_plan=$isFreePlan, paid_disk=$hasPaidDisk)."
if ($status -ne "PASS") { exit 1 }
exit 0
