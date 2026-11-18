<#
.SYNOPSIS
    CanineSense AI — Phase 13 Priority A Data Integrity & Backup/Restore Verification Script
.DESCRIPTION
    Executes isolated database integrity checks (PRAGMA integrity_check, foreign_key_check,
    schema_migrations), storage SHA-256 verification, backup creation in a temporary directory,
    isolated restore validation, and runs backend/tests/test_data_durability.py.
    Never modifies or restores over production data.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "backend\app\services\durability.py"))) {
    Write-Error "FATAL: durability.py missing under '$RepoRoot'."
    exit 2
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("data-integrity-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase13-data-integrity.json"

function Write-DataLog {
    param([string]$Level, [string]$Msg)
    $clean = $Msg -replace '(sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._-]+)', '[REDACTED]'
    $line = "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))] [$Level] $clean"
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

$PythonExe = @(
    (Join-Path $env:LOCALAPPDATA "Python\bin\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe")
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $PythonExe = $cmd.Source }
}

if (-not $PythonExe) {
    Write-DataLog "BLOCKED" "Python interpreter unavailable."
    @{ overall_status = "BLOCKED"; reason = "Python interpreter unavailable" } | ConvertTo-Json | Set-Content -Path $OutJson -Encoding UTF8
    exit 2
}

$env:PYTHONPATH = (Join-Path $RepoRoot "backend")

Write-DataLog "INFO" "Running pytest durability suite (test_data_durability.py)..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pytestOut = & $PythonExe -m pytest (Join-Path $RepoRoot "backend\tests\test_data_durability.py") -v 2>&1 | Out-String
$pytestExit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
Add-Content -Path $LogPath -Value $pytestOut -Encoding UTF8

$passed = 0; $failed = 0
if ($pytestOut -match '(\d+)\s+passed') { $passed = [int]$Matches[1] }
if ($pytestOut -match '(\d+)\s+failed') { $failed = [int]$Matches[1] }

# Also run live local DB & storage audit if backend/data/caninesense.sqlite3 exists (read-only)
$probePy = @'
import json, sys, tempfile
from pathlib import Path
repo = Path(sys.argv[1])
sys.path.insert(0, str(repo / "backend"))
from app import config, db
from app.services import durability
db.init_db()
db_rep = durability.verify_database_integrity(config.DB_PATH)
with db.SessionLocal() as s:
    st_rep = durability.audit_storage_integrity(s, config.STORAGE_DIR)
with tempfile.TemporaryDirectory(prefix="cs_bkp_probe_") as td:
    bkp = durability.create_verified_backup(Path(td), config.DB_PATH, config.STORAGE_DIR)
    res = durability.validate_restore_in_isolation(Path(bkp["backup_zip"]))
print(json.dumps({
    "db_integrity": db_rep,
    "storage_integrity": st_rep,
    "backup_probe": {"status": bkp["status"], "file_count": bkp["file_count"]},
    "isolated_restore_probe": res,
    "render_free_tier_ephemeral": True,
}))
'@

$tmpPy = Join-Path ([System.IO.Path]::GetTempPath()) ("cs_dur_" + [guid]::NewGuid().ToString("N") + ".py")
$probeObj = $null
$probeExit = 1
try {
    $probePy | Set-Content -Path $tmpPy -Encoding UTF8
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $probeRaw = & $PythonExe -W ignore $tmpPy $RepoRoot 2>&1 | Out-String
    $probeExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    $jsonLine = ($probeRaw -split "`r?`n" | Where-Object { $_ -match '^\{' } | Select-Object -Last 1)
    if ($jsonLine) { $probeObj = $jsonLine | ConvertFrom-Json }
} finally {
    Remove-Item $tmpPy -Force -ErrorAction SilentlyContinue
}

$overall = if ($pytestExit -eq 0 -and $probeExit -eq 0 -and $probeObj -and $probeObj.db_integrity.status -eq "PASS" -and $probeObj.isolated_restore_probe.status -eq "PASS") {
    "PASS"
} else {
    "FAIL"
}

$result = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    pytest_durability = @{ exit_code = $pytestExit; passed = $passed; failed = $failed }
    local_integrity_probe = $probeObj
    production_render_durability = "NOT DURABLE (Render free-tier ephemeral container disk)"
    overall_status = $overall
}
$result | ConvertTo-Json -Depth 6 | Set-Content -Path $OutJson -Encoding UTF8
Write-DataLog $overall "Data integrity verification finished (status=$overall, pytest_passed=$passed, pytest_failed=$failed)"

if ($overall -ne "PASS") { exit 1 }
exit 0
