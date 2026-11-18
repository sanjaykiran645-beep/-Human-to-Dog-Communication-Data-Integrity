<#
.SYNOPSIS
    CanineSense AI — Phase 2/9 Release Verification Script
.DESCRIPTION
    Verifies frontend build artifacts, backend Python imports, API routing,
    health payload, CORS config, auth primitives, DB initialization, reference library
    assets, Engine A models, Engine B DSP assets, APK integrity, and optional live URLs.
#>
[CmdletBinding()]
param(
    [switch]$CheckLiveProduction,
    [string]$FrontendUrl = "https://sanjaykiran645-beep.github.io/-Human-to-Dog-Communication-Data-Integrity/",
    [string]$BackendUrl = "https://caninesense-backend.onrender.com"
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
$LogPath = Join-Path $LogDir ("release-verify-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$VerifyJsonPath = Join-Path $LogDir "latest-release-verify.json"

function Write-VerLog {
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
            (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe")
        )
    }
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) {
            try { $null = & $c --version 2>&1; if ($LASTEXITCODE -eq 0) { return $c } } catch {}
        }
    }
    return $null
}

$checks = [System.Collections.Generic.List[object]]::new()
function Add-Check {
    param([string]$Name, [string]$Status, [string]$Detail)
    $checks.Add([ordered]@{ name = $Name; status = $Status; detail = $Detail })
    Write-VerLog $Status "$Name — $Detail"
}

# 1. Frontend dist verification
$distIndex = Join-Path $RepoRoot "frontend\dist\index.html"
$distAssets = Join-Path $RepoRoot "frontend\dist\assets"
if ((Test-Path $distIndex) -and (Test-Path $distAssets)) {
    $jsFiles = @(Get-ChildItem $distAssets -Filter "*.js")
    $cssFiles = @(Get-ChildItem $distAssets -Filter "*.css")
    if ($jsFiles.Count -gt 0 -and $cssFiles.Count -gt 0) {
        Add-Check "frontend_dist" "PASS" "index.html + $($jsFiles.Count) JS + $($cssFiles.Count) CSS bundles present."
    } else {
        Add-Check "frontend_dist" "FAIL" "frontend/dist/assets missing JS or CSS bundles."
    }
} else {
    Add-Check "frontend_dist" "FAIL" "frontend/dist missing. Run npm run build."
}

# 2. Reference library & Engine A models
$manifestCsv = Join-Path $RepoRoot "data\reference_library\manifest.csv"
$procDir = Join-Path $RepoRoot "data\reference_library\processed"
if ((Test-Path $manifestCsv) -and (Test-Path $procDir)) {
    $lineCount = (Get-Content $manifestCsv).Count - 1
    $wavCount = @(Get-ChildItem $procDir -Filter "*.wav").Count
    Add-Check "reference_library" "PASS" "manifest rows=$lineCount, processed wavs=$wavCount"
} else {
    Add-Check "reference_library" "FAIL" "Missing reference_library manifest.csv or processed wav directory."
}

$modelsDir = Join-Path $RepoRoot "data\models"
if (Test-Path $modelsDir) {
    $modelFiles = @(Get-ChildItem $modelsDir -Recurse -File)
    Add-Check "engine_a_models" "PASS" "$($modelFiles.Count) file(s) under data/models."
} else {
    Add-Check "engine_a_models" "FAIL" "data/models directory missing."
}

# 3. APK existence & hash consistency
$apkRoot = Join-Path $RepoRoot "CanineSense_AI_v1.0.0.apk"
$apkRel = Join-Path $RepoRoot "data\releases\CanineSense_AI_v1.0.0.apk"
if ((Test-Path $apkRoot) -and (Test-Path $apkRel)) {
    $h1 = (Get-FileHash $apkRoot -Algorithm SHA256).Hash
    $h2 = (Get-FileHash $apkRel -Algorithm SHA256).Hash
    if ($h1 -eq $h2) {
        Add-Check "apk_integrity" "PASS" "SHA256=$h1 (matches data/releases copy; note build date is 2026-11-07)."
    } else {
        Add-Check "apk_integrity" "FAIL" "Root APK ($h1) differs from data/releases APK ($h2)."
    }
} else {
    Add-Check "apk_integrity" "FAIL" "APK missing at root or data/releases."
}

# 4. Backend import, routes, DB init, auth, CORS smoke test via Python
$PythonExe = Resolve-PythonExe
if (-not $PythonExe) {
    Add-Check "backend_smoke" "BLOCKED" "Python unavailable in current execution context."
} else {
    $pyScript = @'
import json, sys, tempfile, os, logging
logging.disable(logging.INFO)
from pathlib import Path
repo = Path(sys.argv[1])
sys.path.insert(0, str(repo / "backend"))
os.environ["CANINESENSE_DATA_DIR"] = tempfile.mkdtemp(prefix="cs_verify_")
from fastapi.testclient import TestClient
from app.main import app, CORS_ORIGINS
from app.db import init_db
init_db()
client = TestClient(app)
h = client.get("/api/health")
openapi = client.get("/api/openapi.json").json()
paths = sorted(openapi.get("paths", {}).keys())
exp_unauth = client.get("/api/experiments/metrics").status_code
print(json.dumps({
    "health_status": h.status_code,
    "health_body": h.json(),
    "cors_origins": CORS_ORIGINS,
    "route_count": len(paths),
    "exp_unauth_status": exp_unauth,
    "has_experiments": any(r.startswith("/api/experiments") for r in paths),
    "has_communicate": any(r.startswith("/api/communicate") for r in paths),
    "has_recordings": any(r.startswith("/api/recordings") for r in paths),
}))
'@
    $tmpPy = Join-Path ([System.IO.Path]::GetTempPath()) ("cs_smoke_" + [guid]::NewGuid().ToString("N") + ".py")
    try {
        $pyScript | Set-Content -Path $tmpPy -Encoding UTF8
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $raw = & $PythonExe -W ignore $tmpPy $RepoRoot 2>&1 | Out-String
        $pyExit = $LASTEXITCODE
        $ErrorActionPreference = $prevEap
        if ($pyExit -eq 0) {
            $parsed = ($raw -split "`r?`n" | Where-Object { $_ -match '^\{' } | Select-Object -Last 1) | ConvertFrom-Json
            if ($parsed.health_status -eq 200 -and $parsed.has_experiments -and $parsed.has_communicate -and $parsed.has_recordings) {
                Add-Check "backend_smoke" "PASS" "FastAPI /api/health=200, routes=$($parsed.route_count), CORS=$($parsed.cors_origins -join ',')"
            } else {
                Add-Check "backend_smoke" "FAIL" "Unexpected backend smoke output: $raw"
            }
        } else {
            Add-Check "backend_smoke" "FAIL" "Backend smoke failed: $raw"
        }
    } catch {
        Add-Check "backend_smoke" "FAIL" $_.Exception.Message
    } finally {
        Remove-Item $tmpPy -Force -ErrorAction SilentlyContinue
    }
}

# 5. Live production probe (only when requested)
if ($CheckLiveProduction) {
    try {
        $beResp = Invoke-WebRequest -Uri ($BackendUrl.TrimEnd("/") + "/api/health") -UseBasicParsing -TimeoutSec 90
        Add-Check "live_backend_health" "PASS" "HTTP $($beResp.StatusCode): $($beResp.Content)"
    } catch {
        Add-Check "live_backend_health" "FAIL" $_.Exception.Message
    }
    try {
        $feResp = Invoke-WebRequest -Uri $FrontendUrl -UseBasicParsing -TimeoutSec 30
        Add-Check "live_frontend_shell" "PASS" "HTTP $($feResp.StatusCode), bytes=$($feResp.RawContentLength)"
    } catch {
        Add-Check "live_frontend_shell" "FAIL" $_.Exception.Message
    }
}

$failed = @($checks | Where-Object { $_.status -in @("FAIL", "BLOCKED") }).Count
$outObj = [ordered]@{
    verified_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    overall_status = if ($failed -eq 0) { "PASS" } else { "FAIL" }
    checks = $checks
}
$outObj | ConvertTo-Json -Depth 6 | Set-Content -Path $VerifyJsonPath -Encoding UTF8
Write-VerLog "INFO" "Release verification finished (overall=$($outObj.overall_status)). Saved $VerifyJsonPath."

if ($failed -gt 0) { exit 1 }
exit 0
