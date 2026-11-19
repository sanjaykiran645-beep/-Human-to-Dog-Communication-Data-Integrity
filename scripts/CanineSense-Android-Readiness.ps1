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
if (-not $javaCmd -and $env:JAVA_HOME -and (Test-Path "$env:JAVA_HOME\bin\java.exe")) { $javaCmd = Get-Command "$env:JAVA_HOME\bin\java.exe" }
if (-not $javaCmd) {
    $jdkBin = Get-ChildItem 'C:\Program Files\Microsoft\jdk-17*\bin\java.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($jdkBin) { $javaCmd = Get-Command $jdkBin.FullName }
}
$javacCmd = Get-Command javac -ErrorAction SilentlyContinue
if (-not $javacCmd -and $env:JAVA_HOME -and (Test-Path "$env:JAVA_HOME\bin\javac.exe")) { $javacCmd = Get-Command "$env:JAVA_HOME\bin\javac.exe" }
if (-not $javacCmd) {
    $jdkcBin = Get-ChildItem 'C:\Program Files\Microsoft\jdk-17*\bin\javac.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($jdkcBin) { $javacCmd = Get-Command $jdkcBin.FullName }
}
$gradleCmd = Get-Command gradle -ErrorAction SilentlyContinue
$gradlewCandidates = @(
    (Join-Path $RepoRoot "frontend\android\gradlew.bat"),
    (Join-Path $MobileDir "android\gradlew.bat")
)
$gradlewPath = $gradlewCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
$androidSdkEnv = @(
    $env:ANDROID_HOME,
    $env:ANDROID_SDK_ROOT,
    'E:\Android\Sdk',
    (Join-Path $env:LOCALAPPDATA "Android\Sdk")
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
$hasSdk34 = [bool]($androidSdkEnv -and (Test-Path (Join-Path $androidSdkEnv "platforms\android-34")))

$pkgJson = Get-Content (Join-Path $RepoRoot "frontend\package.json") -Raw | ConvertFrom-Json
$hasCapAndroid = [bool](
    ($pkgJson.dependencies.PSObject.Properties.Name -contains "@capacitor/android" -or $pkgJson.devDependencies.PSObject.Properties.Name -contains "@capacitor/android") -and
    ($pkgJson.dependencies.PSObject.Properties.Name -contains "@capacitor/cli" -or $pkgJson.devDependencies.PSObject.Properties.Name -contains "@capacitor/cli")
)

$apkCandidates = @(
    (Join-Path $RepoRoot "data\releases\CanineSense_AI_latest.apk"),
    (Join-Path $RepoRoot "CanineSense_AI_v1.0.0.apk")
)
$apkPath = $apkCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $apkPath) { $apkPath = (Join-Path $RepoRoot "data\releases\CanineSense_AI_latest.apk") }
$apkSha = if (Test-Path $apkPath) { (Get-FileHash $apkPath -Algorithm SHA256).Hash } else { $null }
$apkBytes = if (Test-Path $apkPath) { (Get-Item $apkPath).Length } else { 0 }

$manifestCandidates = @(
    (Join-Path $RepoRoot "frontend\android\app\src\main\AndroidManifest.xml"),
    (Join-Path $MobileDir "android\app\src\main\AndroidManifest.xml")
)
$manifestPath = $manifestCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
$netSecCandidates = @(
    (Join-Path $RepoRoot "frontend\android\app\src\main\res\xml\network_security_config.xml"),
    (Join-Path $MobileDir "android\app\src\main\res\xml\network_security_config.xml")
)
$netSecPath = $netSecCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
$manifestRaw = if ($manifestPath -and (Test-Path $manifestPath)) { Get-Content $manifestPath -Raw } else { "" }

$blockers = [System.Collections.Generic.List[string]]::new()
if (-not $javacCmd) { $blockers.Add("JDK 17+ (javac) not installed") }
if (-not $hasSdk34) { $blockers.Add("Android SDK 34 not installed") }
if (-not $gradlewPath -and -not $gradleCmd) { $blockers.Add("Gradle wrapper (gradlew.bat) and system gradle missing") }
if (-not $hasCapAndroid) { $blockers.Add("@capacitor/android and @capacitor/cli not present in frontend/package.json") }
if (-not (Test-Path $apkPath)) { $blockers.Add("Signed release APK missing at data/releases/CanineSense_AI_latest.apk") }

$status = if ($blockers.Count -eq 0) { "READY" } else { "BLOCKED" }

$freeC = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
$freeE = [math]::Round((Get-PSDrive E).Free / 1GB, 2)

$rep = [ordered]@{
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    build_readiness_status = $status
    blockers = $blockers
    toolchain = @{
        java_found = [bool]$javaCmd
        javac_found = [bool]$javacCmd
        gradle_wrapper_found = [bool]$gradlewPath
        android_sdk_found = [bool]$hasSdk34
        capacitor_android_installed = $hasCapAndroid
    }
    security_config = @{
        cleartext_traffic_disabled = ($manifestRaw -match 'usesCleartextTraffic="false"')
        network_security_config_present = [bool]($netSecPath -and (Test-Path $netSecPath))
        record_audio_permission = ($manifestRaw -match 'RECORD_AUDIO')
        allow_backup_false = ($manifestRaw -match 'allowBackup="false"')
    }
    existing_apk = @{
        path = $apkPath
        bytes = $apkBytes
        sha256 = $apkSha
        status = if (Test-Path $apkPath) { "SIGNED_RELEASE" } else { "MISSING" }
    }
    disk_free_gb = @{ C = $freeC; E = $freeE }
}

$rep | ConvertTo-Json -Depth 6 | Set-Content -Path $OutJson -Encoding UTF8
Write-AndLog $status "Android release readiness check finished (status=$status, blockers=$($blockers -join '; '))"
if ($status -ne "READY") { exit 2 }
exit 0
