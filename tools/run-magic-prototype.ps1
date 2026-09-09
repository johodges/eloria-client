param(
    [ValidateSet('prepared', 'aimed')][string]$Mode = 'prepared',
    [switch]$Live,
    [switch]$Check,
    [string]$GodotPath = '',
    [string]$Server = '',
    [int]$Port = 2000
)
$ErrorActionPreference = 'Stop'
$prototypeRoot = Split-Path -Parent $PSScriptRoot
$projectPath = Join-Path $prototypeRoot 'godot-client'
$assetSource = Join-Path (Split-Path -Parent $prototypeRoot) 'eloria-client'

if (-not $GodotPath) {
    $candidates = @(
        (Join-Path $env:USERPROFILE 'Downloads/godot47/Godot_v4.7.2-stable_win64_console.exe'),
        (Join-Path $env:USERPROFILE 'Downloads/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe')
    )
    $installed = Get-Command godot -ErrorAction SilentlyContinue
    if ($installed) { $candidates += $installed.Source }
    $GodotPath = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (-not $GodotPath -or -not (Test-Path -LiteralPath $GodotPath -PathType Leaf)) {
    throw 'Godot 4.7.2 was not found. Run this script with -GodotPath pointing to the Godot executable.'
}
$engineVersion = (& $GodotPath --version | Out-String).Trim()
if ($engineVersion -notmatch '^4\.7\.2\.') { throw "Expected Godot 4.7.2; found $engineVersion" }

# The local worktree reuses the main checkout's imported artwork. Do not run
# the editor/importer over the shared assets. A full checkout can import its
# own assets normally before running this launcher.
foreach ($link in @(
    @{ Destination = (Join-Path $projectPath 'assets'); Source = (Join-Path $assetSource 'godot-client/assets') },
    @{ Destination = (Join-Path $prototypeRoot 'eloria-assets'); Source = (Join-Path $assetSource 'eloria-assets') },
    @{ Destination = (Join-Path $projectPath '.godot/imported'); Source = (Join-Path $assetSource 'godot-client/.godot/imported') }
)) {
    if (-not (Test-Path -LiteralPath $link.Destination)) {
        if (-not (Test-Path -LiteralPath $link.Source)) { throw "Required assets missing: $($link.Source)" }
        New-Item -ItemType Directory -Path (Split-Path -Parent $link.Destination) -Force | Out-Null
        New-Item -ItemType Junction -Path $link.Destination -Target $link.Source | Out-Null
    }
}
foreach ($cache in @('global_script_class_cache.cfg', 'uid_cache.bin', '.gdignore')) {
    $destination = Join-Path $projectPath ".godot/$cache"
    $source = Join-Path $assetSource "godot-client/.godot/$cache"
    if (-not (Test-Path -LiteralPath $destination) -and (Test-Path -LiteralPath $source)) {
        Copy-Item -LiteralPath $source -Destination $destination
    }
}
$translation = Join-Path $projectPath 'data/i18n/strings.en.translation'
if (-not (Test-Path -LiteralPath $translation)) {
    Copy-Item -LiteralPath (Join-Path $assetSource 'godot-client/data/i18n/strings.en.translation') -Destination $translation
}
$artifactPath = Join-Path $projectPath 'test-artifacts/magic-casting'
New-Item -ItemType Directory -Path $artifactPath -Force | Out-Null
$launchArguments = @('--path', $projectPath, '--log-file', (Join-Path $artifactPath "launch-$Mode.log"))
if ($Check) {
    $launchArguments += @('--headless', '--script', 'res://tests/test_magic_casting_prototype.gd', '--quit-after', '1200')
} elseif (-not $Live) {
    $launchArguments += 'res://src/dev/magic_practice.tscn'
}
$launchArguments += @('--', "--magic-mode=$Mode")
if ($Server) { $launchArguments += @("--server=$Server", "--port=$Port") }
Write-Host "Magic casting prototype: $Mode"
Write-Host $(if ($Live) { 'Live client: log in through the normal login screen.' } else { 'Offline practice: simulated outcomes; no login required.' })
& $GodotPath @launchArguments
$engineExit = $LASTEXITCODE
if ($Check) {
    $logText = Get-Content -LiteralPath (Join-Path $artifactPath "launch-$Mode.log") -Raw
    if ($logText -notmatch 'magic casting prototype: PASS' -or $logText -match 'SCRIPT ERROR|FAIL:') { exit 1 }
}
exit $engineExit
