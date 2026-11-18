<#
.SYNOPSIS
    CanineSense AI — Phase 14 Android Build Toolchain & Release Verification Script
.DESCRIPTION
    Reuses CanineSense-Android-Readiness.ps1 to inspect JDK 17+, Android SDK 34, Gradle,
    Capacitor dependencies, disk free space, and existing APK SHA-256. Reports BLOCKED (exit 2)
    when required Android toolchain components are missing. Never fabricates an APK.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("phase14-android-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase14-android.json"

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "CanineSense-Android-Readiness.ps1") 2>&1 | Tee-Object -FilePath $LogPath | Out-Null
$code = $LASTEXITCODE
$ErrorActionPreference = $prevEap

$p13Path = Join-Path $LogDir "phase13-android-readiness.json"
$p13 = if (Test-Path $p13Path) { Get-Content $p13Path -Raw | ConvertFrom-Json } else { $null }

$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    status = if ($p13) { $p13.build_readiness_status } else { "BLOCKED" }
    exit_code = $code
    toolchain = if ($p13) { $p13.toolchain } else { $null }
    blockers = if ($p13) { $p13.blockers } else { @("Android toolchain inspection failed") }
    security_config = if ($p13) { $p13.security_config } else { $null }
    existing_apk = if ($p13) { $p13.existing_apk } else { $null }
    disk_free_gb = if ($p13) { $p13.disk_free_gb } else { $null }
    estimated_toolchain_install_gb = 4.5
}
$rep | ConvertTo-Json -Depth 6 | Set-Content -Path $OutJson -Encoding UTF8
Write-Host "[$($rep.status)] Phase 14 Android check finished (exit=$code)."
exit $code
