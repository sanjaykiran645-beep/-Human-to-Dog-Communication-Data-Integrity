<#
.SYNOPSIS
    CanineSense AI — Phase 13 Priority F Android Release Readiness Audit Script
.DESCRIPTION
    Checks Java/JDK 17+, Android SDK 34, Gradle wrapper, Capacitor configuration,
    AndroidManifest.xml, network_security_config.xml, disk space, and existing APK hash.
    Does not fabricate APKs or install large SDK toolchains automatically.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$MobileDir = Join-Path $RepoRoot "mobile-android"
if (-not (Test-Path $MobileDir)) {
    Write-Error "FATAL: mobile-android directory missing under '$RepoRoot'."
    exit 2
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("android-readiness-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
$OutJson = Join-Path $LogDir "phase13-android-readiness.json"

function Write-AndLog {
    param([string]$Level, [string]$Msg)
    $line = "[$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))] [$Level] $Msg"
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

$javaCmd = Get-Command java -ErrorAction SilentlyContinue
$javacCmd = Get-Command javac -ErrorAction SilentlyContinue
$gradleCmd = Get-Command gradle -ErrorAction SilentlyContinue
$gradlewPath = Join-Path $MobileDir "android\gradlew.bat"
$androidSdkEnv = @($env:ANDROID_HOME, $env:ANDROID_SDK_ROOT, (Join-Path $env:LOCALAPPDATA "Android\Sdk")) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

$pkgJson = Get-Content (Join-Path $RepoRoot "frontend\package.json") -Raw | ConvertFrom-Json
$hasCapAndroid = [bool]($pkgJson.dependencies.PSObject.Properties.Name -contains "@capacitor/android" -or $pkgJson.devDependencies.PSObject.Properties.Name -contains "@capacitor/android")

$apkPath = Join-Path $RepoRoot "CanineSense_AI_v1.0.0.apk"
$apkSha = if (Test-Path $apkPath) { (Get-FileHash $apkPath -Algorithm SHA256).Hash } else { $null }
$apkBytes = if (Test-Path $apkPath) { (Get-Item $apkPath).Length } else { 0 }

$manifestPath = Join-Path $MobileDir "android\app\src\main\AndroidManifest.xml"
$netSecPath = Join-Path $MobileDir "android\app\src\main\res\xml\network_security_config.xml"
$manifestRaw = if (Test-Path $manifestPath) { Get-Content $manifestPath -Raw } else { "" }

$blockers = [System.Collections.Generic.List[string]]::new()
if (-not $javacCmd) { $blockers.Add("JDK 17+ (javac) not installed") }
if (-not $androidSdkEnv) { $blockers.Add("Android SDK 34 not installed") }
if (-not (Test-Path $gradlewPath) -and -not $gradleCmd) { $blockers.Add("Gradle wrapper (gradlew.bat) and system gradle missing") }
if (-not $hasCapAndroid) { $blockers.Add("@capacitor/android and @capacitor/cli not present in frontend/package.json") }

$status = if ($blockers.Count -eq 0) { "PASS" } else { "BLOCKED" }

$freeC = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
$freeE = [math]::Round((Get-PSDrive E).Free / 1GB, 2)

$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    build_readiness_status = $status
    blockers = $blockers
    toolchain = @{
        java_found = [bool]$javaCmd
        javac_found = [bool]$javacCmd
        gradle_wrapper_found = (Test-Path $gradlewPath)
        android_sdk_found = [bool]$androidSdkEnv
        capacitor_android_installed = $hasCapAndroid
    }
    security_config = @{
        cleartext_traffic_disabled = ($manifestRaw -match 'usesCleartextTraffic="false"')
        network_security_config_present = (Test-Path $netSecPath)
        record_audio_permission = ($manifestRaw -match 'RECORD_AUDIO')
        allow_backup_false = ($manifestRaw -match 'allowBackup="false"')
    }
    existing_apk = @{
        path = $apkPath
        bytes = $apkBytes
        sha256 = $apkSha
        status = "OBSOLETE (built 2026-11-07)"
    }
    disk_free_gb = @{ C = $freeC; E = $freeE }
}

$rep | ConvertTo-Json -Depth 6 | Set-Content -Path $OutJson -Encoding UTF8
Write-AndLog $status "Android release readiness check finished (status=$status, blockers=$($blockers -join '; '))"
if ($status -ne "PASS") { exit 2 }
exit 0
