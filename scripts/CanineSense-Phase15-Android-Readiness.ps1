<#
.SYNOPSIS
    CanineSense AI — Phase 15 Android Toolchain & Build Readiness Check
.DESCRIPTION
    Reuses CanineSense-Phase14-Android.ps1 to inspect JDK 17+, Android SDK 34, Gradle,
    Capacitor packages, disk capacity, security manifest, and APK SHA-256.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$OutJson = Join-Path $LogDir "phase15-android-readiness.json"

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "CanineSense-Phase14-Android.ps1")
$code = $LASTEXITCODE
$ErrorActionPreference = $prevEap

Copy-Item -Path (Join-Path $LogDir "phase14-android.json") -Destination $OutJson -Force
exit $code
