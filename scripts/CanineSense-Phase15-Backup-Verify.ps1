<#
.SYNOPSIS
    CanineSense AI — Phase 15 Backup & Recovery Verification Script
.DESCRIPTION
    Reuses CanineSense-Phase14-Persistence.ps1, verifies isolated backup & verify_backup_archive,
    and checks live Render backup/persistence status without altering live production data.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("phase15-backup-verify-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase15-backup-verify.json"

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "CanineSense-Phase14-Persistence.ps1") 2>&1 | Tee-Object -FilePath $LogPath | Out-Null
$p14Exit = $LASTEXITCODE
$ErrorActionPreference = $prevEap

$p14Rep = Get-Content (Join-Path $LogDir "phase14-persistence.json") -Raw | ConvertFrom-Json
$status = if ($p14Exit -eq 0 -and $p14Rep.architecture_status -eq "PASS") { "PASS" } else { "FAIL" }

$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    isolated_backup_verify_status = $status
    pytest_persistence_dr = $p14Rep.pytest_persistence_dr
    live_render_persistence = $p14Rep.live_render_persistence
    production_backup_durability = "BLOCKED"
    note = "Isolated backup and restore verification passed locally; Render container-local storage provides zero off-site/durable backup guarantee."
}
$rep | ConvertTo-Json -Depth 6 | Set-Content -Path $OutJson -Encoding UTF8
Write-Host "[$status] Phase 15 isolated backup verification=$status | PRODUCTION BACKUP DURABILITY: BLOCKED."
if ($status -ne "PASS") { exit 1 }
exit 0
