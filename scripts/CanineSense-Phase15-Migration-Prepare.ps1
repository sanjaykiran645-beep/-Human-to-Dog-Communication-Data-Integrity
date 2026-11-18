<#
.SYNOPSIS
    CanineSense AI — Phase 15 Durable Storage & Database Migration Preparation (Read-Only Default)
.DESCRIPTION
    Inspects database schema, migrations, foreign keys, storage paths, backup metadata, generates
    database and SHA-256 file inventories, validates PostgreSQL DDL compatibility, runs
    test_phase15_migration_readiness.py, and optionally runs isolated migration simulation.
#>
[CmdletBinding()]
param(
    [switch]$SimulateIsolatedMigration
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "backend\app\services\migration_prep.py"))) {
    Write-Error "FATAL: migration_prep.py missing under '$RepoRoot'."
    exit 2
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("phase15-migration-prep-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase15-migration-readiness.json"

$PythonExe = @(
    (Join-Path $env:LOCALAPPDATA "Python\bin\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe")
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $PythonExe = $cmd.Source }
}
if (-not $PythonExe) {
    @{ overall_status = "BLOCKED"; reason = "Python interpreter unavailable" } | ConvertTo-Json | Set-Content -Path $OutJson -Encoding UTF8
    exit 2
}

$env:PYTHONPATH = (Join-Path $RepoRoot "backend")

$simFlag = if ($SimulateIsolatedMigration) { "1" } else { "0" }
$prepPy = @'
import json, os, sys
from pathlib import Path
repo = Path(sys.argv[1])
sim = sys.argv[2] == "1"
sys.path.insert(0, str(repo / "backend"))
from app import config, db
from app.services import durability, migration_prep

db.init_db()
schema_rep = migration_prep.inspect_schema_and_migrations(config.DB_PATH)
pg_rep = migration_prep.validate_postgresql_ddl_compatibility()
with db.SessionLocal() as session:
    db_inv = migration_prep.generate_database_inventory(session)
    st_inv = migration_prep.generate_storage_inventory_and_manifest(session, config.STORAGE_DIR)
bkp_health = durability.check_backup_health(config.BACKUP_DIR, config.BACKUP_MAX_AGE_HOURS)
sim_rep = migration_prep.simulate_migration_in_isolation(config.DB_PATH, config.STORAGE_DIR) if sim else {"status": "NOT_RUN"}

print(json.dumps({
    "schema_inspection": schema_rep,
    "postgresql_compatibility": pg_rep,
    "database_inventory": db_inv,
    "storage_inventory_summary": {
        "storage_provider": st_inv["storage_provider"],
        "total_files": st_inv["total_files"],
        "total_bytes": st_inv["total_bytes"],
        "audit_status": st_inv["audit"]["status"],
        "missing_files_count": st_inv["audit"]["missing_files_count"],
        "orphaned_files_count": st_inv["audit"]["orphaned_files_count"],
    },
    "backup_health": bkp_health,
    "isolated_migration_simulation": sim_rep,
}))
'@

$tmpPy = Join-Path ([System.IO.Path]::GetTempPath()) ("cs_mig_" + [guid]::NewGuid().ToString("N") + ".py")
$prepObj = $null
$prepExit = 1
try {
    $prepPy | Set-Content -Path $tmpPy -Encoding UTF8
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $raw = & $PythonExe -W ignore $tmpPy $RepoRoot $simFlag 2>&1 | Out-String
    $prepExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    Add-Content -Path $LogPath -Value $raw -Encoding UTF8
    $jsonLine = ($raw -split "`r?`n" | Where-Object { $_ -match '^\{' } | Select-Object -Last 1)
    if ($jsonLine) { $prepObj = $jsonLine | ConvertFrom-Json }
} finally {
    Remove-Item $tmpPy -Force -ErrorAction SilentlyContinue
}

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$ptOut = & $PythonExe -m pytest (Join-Path $RepoRoot "backend\tests\test_phase15_migration_readiness.py") -v 2>&1 | Out-String
$ptExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
Add-Content -Path $LogPath -Value $ptOut -Encoding UTF8

$passed = 0; $failed = 0
if ($ptOut -match '(\d+)\s+passed') { $passed = [int]$Matches[1] }
if ($ptOut -match '(\d+)\s+failed') { $failed = [int]$Matches[1] }

$ok = ($prepExit -eq 0 -and $ptExit -eq 0 -and $prepObj -and $prepObj.schema_inspection.status -eq "PASS" -and $prepObj.postgresql_compatibility.status -eq "PASS")
if ($SimulateIsolatedMigration -and ($prepObj.isolated_migration_simulation.status -ne "PASS")) { $ok = $false }
$status = if ($ok) { "PASS" } else { "FAIL" }

$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    overall_status = $status
    read_only_mode = (-not $SimulateIsolatedMigration)
    pytest_migration = @{ exit_code = $ptExit; passed = $passed; failed = $failed }
    readiness = $prepObj
    production_persistence_status = "BLOCKED - FREE EPHEMERAL INFRASTRUCTURE DOES NOT PROVIDE A VERIFIED DURABLE PRODUCTION GUARANTEE"
}
$rep | ConvertTo-Json -Depth 7 | Set-Content -Path $OutJson -Encoding UTF8
Write-Host "[$status] Phase 15 migration readiness finished (passed=$passed, pg_ddl=$($prepObj.postgresql_compatibility.status))."
if ($status -ne "PASS") { exit 1 }
exit 0
