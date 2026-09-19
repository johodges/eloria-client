[CmdletBinding()]
param(
    [string]$GodotPath = "",
    [ValidateSet("primary", "matrix", "features", "stress", "all", "custom")]
    [string]$Profile = "primary",
    [ValidateSet("Both", "Headless", "Windowed")]
    [string]$Mode = "Both",
    [ValidateSet("gl_compatibility", "forward_plus")]
    [string[]]$Renderer = @("gl_compatibility"),
    [ValidateSet("Both", "GDScript", "Native")]
    [string]$NativeBackend = "Both",
    [ValidateRange(1, 20)]
    [int]$Repeats = 3,
    [ValidateRange(1, 180)]
    [int]$TimeoutMinutes = 30,
    [string]$Counts = "",
    [string]$Populations = "",
    [string]$Activities = "",
    [string]$Visibilities = "",
    [string]$Features = "",
    [string]$Networks = "",
    [string]$Map = "four_gates",
    [int]$SampleMilliseconds = 2500,
    [int]$WarmupMilliseconds = 1000,
    [int]$CadenceMilliseconds = 100,
    [switch]$Capture,
    [string]$Label = "",
    [string]$InterferenceLabel = "shared host; unrelated Godot jobs may be present"
)

$ErrorActionPreference = "Stop"
(Get-Process -Id $PID).ProcessorAffinity = 15

$clientRoot = Split-Path -Parent $PSScriptRoot
$repositoryRoot = Split-Path -Parent $clientRoot
$runRoot = Join-Path $clientRoot "test-artifacts/native-crowd"
$userRoot = Join-Path $runRoot "user-data"
New-Item -ItemType Directory -Force -Path $runRoot, $userRoot | Out-Null

if ([string]::IsNullOrWhiteSpace($GodotPath)) {
    $godot = Get-Command godot4, godot, Godot -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $godot) {
        throw "Godot was not found. Pass -GodotPath with the executable path."
    }
    $GodotPath = $godot.Source
}
$GodotPath = (Resolve-Path -LiteralPath $GodotPath).Path
$launchPath = $GodotPath
if ([IO.Path]::GetFileNameWithoutExtension($GodotPath) -like '*_console') {
    $directPath = Join-Path (Split-Path -Parent $GodotPath) `
        (([IO.Path]::GetFileNameWithoutExtension($GodotPath) -replace '_console$', '') + '.exe')
    if (-not (Test-Path -LiteralPath $directPath)) {
        throw "The console Godot executable has no sibling direct executable at $directPath."
    }
    $launchPath = (Resolve-Path -LiteralPath $directPath).Path
}

# Keep mutable state in this worktree. The process mask is the enforceable CPU
# bound. Thread environment variables are requests recorded in the report;
# Godot does not expose a runtime worker-count query.
$env:APPDATA = Join-Path $userRoot "appdata"
$env:LOCALAPPDATA = Join-Path $userRoot "localappdata"
$env:USERPROFILE = Join-Path $userRoot "profile"
$env:TEMP = Join-Path $userRoot "temp"
$env:TMP = $env:TEMP
$env:NUMBER_OF_PROCESSORS = "4"
$env:GODOT_THREADS_OVERRIDE = "2"
$env:OMP_NUM_THREADS = "2"
$env:OPENBLAS_NUM_THREADS = "2"
$env:MKL_NUM_THREADS = "2"
New-Item -ItemType Directory -Force -Path $env:APPDATA, $env:LOCALAPPDATA,
    $env:USERPROFILE, $env:TEMP | Out-Null

$gitSafe = "safe.directory=$($repositoryRoot.Replace('\', '/'))"
$commit = (& git -c $gitSafe -C $repositoryRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Cannot determine the benchmark commit." }
& git -c $gitSafe -C $repositoryRoot diff --quiet --ignore-submodules --
$worktreeDirty = $LASTEXITCODE -ne 0
& git -c $gitSafe -C $repositoryRoot diff --cached --quiet --ignore-submodules --
$indexDirty = $LASTEXITCODE -ne 0
$sourceRelativePaths = @(
    "godot-client/tests/integration/crowd_benchmarks.gd",
    "godot-client/tests/integration/crowd_benchmark_main.gd",
    "godot-client/tests/integration/crowd_benchmark_main.tscn",
    "godot-client/scripts/run_crowd_benchmarks.ps1",
    "godot-client/src/state/app_state.gd",
    "godot-client/src/app/main.gd",
    "godot-client/src/actors/replicated_actor_3d.gd",
    "godot-client/native/native_crowd/src/native_crowd_reducer.cpp",
    "godot-client/native/native_crowd/src/native_crowd_reducer.h",
    "godot-client/native/native_crowd/src/register_types.cpp",
    "godot-client/native/native_crowd/src/register_types.h",
    "godot-client/bin/native_crowd.gdextension",
    "godot-client/bin/windows/native_crowd.windows.template_release.x86_64.dll"
)
$sourceStatus = @(& git -c $gitSafe -C $repositoryRoot status --porcelain -- `
    $sourceRelativePaths)
$dirty = $worktreeDirty -or $indexDirty -or $sourceStatus.Count -gt 0
$sourceHashes = [ordered]@{}
foreach ($relativePath in $sourceRelativePaths) {
    $absolutePath = Join-Path $repositoryRoot $relativePath
    if (Test-Path -LiteralPath $absolutePath) {
        $sourceHashes[$relativePath] = (Get-FileHash -Algorithm SHA256 `
            -LiteralPath $absolutePath).Hash.ToLowerInvariant()
    }
}
$sourceHashText = ($sourceHashes.GetEnumerator() | ForEach-Object {
    "$($_.Key)=$($_.Value)"
}) -join "`n"
$sourceHashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
try {
    $sourceHashBytes = [System.Text.Encoding]::UTF8.GetBytes($sourceHashText)
    $sourceHash = [Convert]::ToHexString(
        $sourceHashAlgorithm.ComputeHash($sourceHashBytes)).ToLowerInvariant()
}
finally {
    $sourceHashAlgorithm.Dispose()
}

$env:ELORIA_CROWD_PROFILE = $Profile
$env:ELORIA_CROWD_COUNTS = $Counts
$env:ELORIA_CROWD_POPULATIONS = $Populations
$env:ELORIA_CROWD_ACTIVITIES = $Activities
$env:ELORIA_CROWD_VISIBILITIES = $Visibilities
$env:ELORIA_CROWD_FEATURES = $Features
$env:ELORIA_CROWD_NETWORKS = $Networks
$env:ELORIA_CROWD_MAP = $Map
$env:ELORIA_CROWD_SAMPLE_MSEC = [string]$SampleMilliseconds
$env:ELORIA_CROWD_WARMUP_MSEC = [string]$WarmupMilliseconds
$env:ELORIA_CROWD_CADENCE_MSEC = [string]$CadenceMilliseconds
$env:ELORIA_CROWD_CAPTURE = if ($Capture) { "1" } else { "0" }
$env:ELORIA_CROWD_LABEL = $Label
$env:ELORIA_CROWD_INTERFERENCE = $InterferenceLabel
$env:ELORIA_CROWD_ARTIFACT_DIR = $runRoot
$env:ELORIA_CROWD_USER_ROOT = $userRoot
$env:ELORIA_CROWD_COMMIT = $commit
$env:ELORIA_CROWD_DIRTY = if ($dirty) { "1" } else { "0" }
$env:ELORIA_CROWD_SOURCE_HASH = $sourceHash

$modes = switch ($Mode) {
    "Headless" { @("headless") }
    "Windowed" { @("windowed") }
    default { @("headless", "windowed") }
}
$backends = switch ($NativeBackend) {
    "GDScript" { @("gdscript") }
    "Native" { @("native") }
    default { @("gdscript", "native") }
}
$safeLabel = ($Label -replace '[^A-Za-z0-9_.-]+', '-').Trim('-')
if ([string]::IsNullOrWhiteSpace($safeLabel)) { $safeLabel = "unlabelled" }

function Set-And-VerifyAffinity([System.Diagnostics.Process]$Process,
        [hashtable]$Observed, [string]$ExpectedPath,
        [datetime]$ExpectedStartTime) {
    try {
        if ($Process.HasExited) { return }
        $Process.ProcessorAffinity = 15
        $Process.Refresh()
        $actual = $Process.ProcessorAffinity.ToInt64()
        $actualPath = $Process.MainModule.FileName
        $actualStartTime = $Process.StartTime.ToUniversalTime()
        $Observed[[string]$Process.Id] = @{
            name = $Process.ProcessName
            path = $actualPath
            startTimeUtc = $actualStartTime.ToString('o')
            affinityMask = $actual
        }
        if (-not $actualPath.Equals($ExpectedPath,
                [StringComparison]::OrdinalIgnoreCase) -or
                $actualStartTime -ne $ExpectedStartTime) {
            throw "Captured process identity changed for PID $($Process.Id)."
        }
        if ($actual -ne 15) {
            throw "Process $($Process.Id) has affinity $actual instead of 15."
        }
    }
    catch [System.InvalidOperationException] {
        # The captured process can exit between HasExited and inspection.
    }
}

function Quote-ProcessArgument([string]$Value) {
    if ($Value -notmatch '[\s"]') { return $Value }
    return '"' + ($Value -replace '"', '\"') + '"'
}

function Assert-BenchmarkReport([string]$JsonPath, [string]$ExpectedProfile) {
    if (-not (Test-Path -LiteralPath $JsonPath)) {
        throw "Benchmark exited without writing $JsonPath."
    }
    try { $result = Get-Content -Raw -LiteralPath $JsonPath | ConvertFrom-Json }
    catch { throw "Benchmark artifact is not valid JSON: $JsonPath`n$_" }
    if ($result.schemaVersion -ne 1 -or $result.profile -ne $ExpectedProfile -or
            $result.failureCount -ne 0) {
        throw "Benchmark artifact reports an invalid schema, profile, or failure count: $JsonPath"
    }
    $cells = @($result.cells)
    if ($cells.Count -eq 0 -or $cells.Count -ne @($result.plannedCells).Count) {
        throw "Benchmark artifact has incomplete cell coverage: $JsonPath"
    }
    foreach ($cell in $cells) {
        if ($cell.fixture.before.total -ne $cell.count -or
                $cell.fixture.after.total -ne $cell.count) {
            throw "Benchmark artifact has an actor-count mismatch: $JsonPath"
        }
    }
    if ($ExpectedProfile -eq "primary" -and ($cells.Count -ne 1 -or
            $cells[0].count -ne 300 -or $cells[0].plannedActive -ne 100 -or
            $cells[0].fixture.before.frustumAndDrawVisible -ne 150)) {
        throw "Primary acceptance invariants are absent: $JsonPath"
    }
}

foreach ($trial in 1..$Repeats) {
    $trialBackends = @($backends)
    if ($trialBackends.Count -eq 2 -and $trial % 2 -eq 0) {
        [array]::Reverse($trialBackends)
    }
    foreach ($renderingMethod in $Renderer) {
        $env:ELORIA_CROWD_RENDERER = $renderingMethod
        foreach ($run in $modes) {
            foreach ($backend in $trialBackends) {
                $env:ELORIA_NATIVE_CROWD = if ($backend -eq "native") { "1" } else { "0" }
                $env:ELORIA_CROWD_NATIVE_BACKEND = $backend
                $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
                $runId = "$safeLabel-$Profile-$backend-$renderingMethod-$run-trial$trial-$timestamp"
                $env:ELORIA_CROWD_TRIAL = [string]$trial
                $env:ELORIA_CROWD_RUN_ID = $runId
                $env:ELORIA_CROWD_OUTPUT = "$runId.json"
                $env:ELORIA_CROWD_PROCESS_METADATA = (@{
                    runnerPid = $PID
                    affinityMask = 15
                    logicalProcessors = @(0, 1, 2, 3)
                    requestedWorkerThreads = 2
                } | ConvertTo-Json -Compress)
                $logPath = Join-Path $runRoot "$runId.log"
                $stdoutPath = Join-Path $runRoot "$runId.stdout.log"
                $stderrPath = Join-Path $runRoot "$runId.stderr.log"
                $processPath = Join-Path $runRoot "$runId.process.json"
				$jsonPath = Join-Path $runRoot "$runId.json"
                $arguments = @(
                    "--audio-driver", "Dummy",
                    "--rendering-method", $renderingMethod,
                    "--path", $clientRoot,
                    "--script", "res://tests/integration/crowd_benchmarks.gd",
                    "--log-file", $logPath
                )
                if ($run -eq "headless") { $arguments = @("--headless") + $arguments }
				$quotedArguments = @($arguments | ForEach-Object {
					Quote-ProcessArgument ([string]$_
				)})

                Write-Host "Running $runId serially (affinity=0xF; worker request=2)..."
                $observed = @{}
                $process = Start-Process -FilePath $launchPath -ArgumentList $quotedArguments `
					-PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutPath `
					-RedirectStandardError $stderrPath
				$expectedProcessPath = $launchPath
				$expectedProcessStart = $process.StartTime.ToUniversalTime()
                Set-And-VerifyAffinity $process $observed $expectedProcessPath `
					$expectedProcessStart
				$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
				$artifactSeenAt = $null
				$postReportStop = $false
				do {
					$process.Refresh()
					$live = if ($process.HasExited) { 0 } else { 1 }
					if ($live -gt 0) {
						Set-And-VerifyAffinity $process $observed $expectedProcessPath `
							$expectedProcessStart
					}
					if ((Get-Date) -ge $deadline) {
						if (-not $process.HasExited) { $process.Kill($true) }
						throw "$runId exceeded the $TimeoutMinutes minute timeout."
					}
					if (Test-Path -LiteralPath $jsonPath) {
						if ($null -eq $artifactSeenAt) { $artifactSeenAt = Get-Date }
						elseif (((Get-Date) - $artifactSeenAt).TotalSeconds -ge 5 -and $live -gt 0) {
							$process.Kill($true)
							$postReportStop = $true
						}
					}
					if ($live -gt 0) { Start-Sleep -Seconds 1 }
                } while ($live -gt 0)
                $process.WaitForExit()
				$scriptErrorsDetected = $false
				foreach ($diagnosticPath in @($logPath, $stdoutPath, $stderrPath)) {
					if ((Test-Path -LiteralPath $diagnosticPath) -and
							(Select-String -Path $diagnosticPath -Pattern 'SCRIPT ERROR|Parse Error' -Quiet)) {
						$scriptErrorsDetected = $true
					}
				}
				$schemaValid = $false
				$reportValidationError = ""
				try {
					Assert-BenchmarkReport $jsonPath $Profile
					$schemaValid = $true
				}
				catch {
					$reportValidationError = $_.Exception.Message
				}
				$cleanExit = -not $postReportStop -and $process.ExitCode -eq 0
				$reportValid = $schemaValid -and -not $scriptErrorsDetected -and $cleanExit
                @{
                    runId = $runId
                    rootPid = $process.Id
                    exitCode = $process.ExitCode
                    affinityMask = 15
                    allObservedProcessesVerified = $true
                    observedProcesses = $observed
                    commit = $commit
                    dirty = $dirty
					sourceHash = $sourceHash
					sourceFiles = $sourceHashes
					requestedGodotPath = $GodotPath
					launchExecutablePath = $launchPath
					monitoring = "captured direct Godot Process object only; exact path/start time and mask checked every second"
					postReportStop = $postReportStop
					abortedAfterReport = $postReportStop
					cleanExit = $cleanExit
					scriptErrorsDetected = $scriptErrorsDetected
					schemaValid = $schemaValid
					reportValid = $reportValid
					reportValidationError = $reportValidationError
                    renderer = $renderingMethod
                    mode = $run
                    backend = $backend
                    trial = $trial
                } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $processPath
				if ($postReportStop) {
					throw "$runId wrote a report but required forced post-report termination. See $logPath"
				}
                if ($process.ExitCode -ne 0) {
                    throw "$runId failed with exit code $($process.ExitCode). See $logPath"
                }
				if ($scriptErrorsDetected) {
					throw "$runId logged a script or parse error. See $logPath"
				}
				if (-not $reportValid) {
					throw $reportValidationError
				}
            }
        }
    }
}

Write-Host "Crowd benchmark artifacts: $runRoot"
