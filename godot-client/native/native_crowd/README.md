# Native crowd reducer prototype

This prototype compares two native boundaries without changing the default
client path:

- `NativeCrowdReducer.reduce_packet()` reduces one complete command-2 payload
  into the existing `AppState.actors` dictionary. It preserves the outer
  dictionary object, shallow-copies each touched actor record once, and returns
  the touched ids. A malformed payload and a local actor's command 19 are
  detected before mutation and return `invalid` or `fallback` respectively.
- `NativeCrowdStore` keeps command-hot scalar fields in a contiguous
  `vector<ActorState>` and resolves the protocol's 16-bit actor ids through a
  fixed 65,536-entry id-to-slot index. Removal swaps the last record into the
  vacated slot and repairs the index; `reset()` discards every old slot, so a
  reused id starts from its replacement record. `snapshot_dirty()` includes the
  cost of materializing changed records back into the existing dictionary.
  Delaying that call across several packets is a benchmark mode, not a
  parity-preserving production path, because GDScript observers currently run
  after every packet.

The compact store owns only `x`, `y`, command, sequence, facing, health, and the
sit/combat/alive flags. The caller still owns names, map placement, appearance,
equipment, buffs, aim state, and all other cold fields. External changes to hot
fields after `reset()` are not observed; a benchmark must reset the store after
replacing actor snapshots. This is why the store is not wired into `AppState`.

The dependency is pinned to godot-cpp 10.0.0-stable commit
`507ed9d840c01a3c5b2a39af8bb4000bfac30bf5`, targeting its Godot 4.7 API.
The binding profile is centered on `RefCounted`; it also enables `OS`, which
godot-cpp's core `print_string.cpp` includes even for this small extension.
Configure and build from this directory with CMake. The build fetches godot-cpp
into the ignored `.deps` directory and writes the library under
`godot-client/bin/<platform>`.

The `.gdextension` file is a template on purpose. A benchmark setup copies it
to `godot-client/bin/native_crowd.gdextension` only after the matching library
has been built. A normal checkout therefore has no missing native dependency
and keeps the existing GDScript path. The descriptor deliberately selects the
release benchmark library for both editor and template processes; the build
commands below produce that exact file rather than an absent debug variant.

On Windows, from the repository root in PowerShell:

```powershell
(Get-Process -Id $PID).ProcessorAffinity = 15
$nativeSource = "godot-client/native/native_crowd"
$nativeBuild = "$nativeSource/build/windows-release"
# Process-local only: lets g++.exe find its own tools while configuring.
$env:PATH = "C:/msys64/mingw64/bin;$env:PATH"
& C:/msys64/mingw64/bin/cmake.exe -S $nativeSource -B $nativeBuild `
  -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release `
  -DGODOTCPP_TARGET=template_release `
  -DCMAKE_CXX_COMPILER=C:/msys64/mingw64/bin/g++.exe `
  -DCMAKE_MAKE_PROGRAM=C:/msys64/mingw64/bin/mingw32-make.exe
& C:/msys64/mingw64/bin/cmake.exe --build $nativeBuild --parallel 2
```

The MinGW target statically links `libgcc` and `libstdc++`; it neither installs
runtime DLLs globally nor changes `PATH`. On Linux:

```sh
taskset -c 0-3 cmake -S godot-client/native/native_crowd \
  -B godot-client/native/native_crowd/build/linux-release \
  -DCMAKE_BUILD_TYPE=Release -DGODOTCPP_TARGET=template_release
taskset -c 0-3 cmake --build \
  godot-client/native/native_crowd/build/linux-release --parallel 2
```

After either build, run all three parity suites with Godot's user data, logs,
temporary files, and test output isolated inside the worktree. On Windows,
from the repository root in PowerShell:

```powershell
(Get-Process -Id $PID).ProcessorAffinity = 15
$godot = "$PWD/godot-client/Godot_v4.7.2-stable_win64_console.exe"
$isolated = "$PWD/godot-client/test-artifacts/native-crowd/native-isolated"
$results = "$isolated/results"
$env:APPDATA = "$isolated/appdata"
$env:LOCALAPPDATA = "$isolated/localappdata"
$env:USERPROFILE = "$isolated/userprofile"
$env:TEMP = "$isolated/temp"
$env:TMP = $env:TEMP
$env:ELORIA_CROWD_EXPECT_USER_ROOT = $isolated
$env:ELORIA_NATIVE_CROWD = "1"
New-Item -ItemType Directory -Force -Path `
  $env:APPDATA,$env:LOCALAPPDATA,$env:USERPROFILE,$env:TEMP,$results | Out-Null
foreach ($test in @(
  "test_native_crowd",
  "test_native_crowd_app_state",
  "test_native_crowd_edges")) {
  & $godot --headless --path "$PWD/godot-client" `
    --log-file "$results/$test.log" --script "res://tests/$test.gd"
  if ($LASTEXITCODE -ne 0) { throw "$test failed" }
}
```

On Linux, from the repository root:

```sh
isolated="$PWD/godot-client/test-artifacts/native-crowd/native-isolated"
results="$isolated/results"
mkdir -p "$isolated/home" "$isolated/xdg-data" "$isolated/xdg-config" \
  "$isolated/xdg-cache" "$isolated/tmp" "$results"
export HOME="$isolated/home"
export XDG_DATA_HOME="$isolated/xdg-data"
export XDG_CONFIG_HOME="$isolated/xdg-config"
export XDG_CACHE_HOME="$isolated/xdg-cache"
export TMPDIR="$isolated/tmp"
export ELORIA_CROWD_EXPECT_USER_ROOT="$isolated"
export ELORIA_NATIVE_CROWD=1
for test in test_native_crowd test_native_crowd_app_state \
  test_native_crowd_edges; do
  taskset -c 0-3 godot --headless --path godot-client \
    --log-file "$results/$test.log" --script "res://tests/$test.gd" || exit 1
done
```

Then run the reducer-only timing comparison. It records GDScript, native
Dictionary reduction, packed state with per-packet export, and packed state
with deferred export. The last mode is deliberately labelled non-equivalent.
Reset, reduction, and materialization components run as a separate timing pass,
so their clock reads do not inflate the total-mode measurements.

Use the same isolated environment initialized above. On Windows, while the
PowerShell variables from the parity run are still active:

```powershell
$env:ELORIA_CROWD_EXPECT_USER_ROOT = $isolated
$env:ELORIA_NATIVE_CROWD = "1"
$env:ELORIA_ARTIFACT_DIR = $results
& $godot --headless --path "$PWD/godot-client" `
  --log-file "$results/native-crowd-reducer.log" `
  --script res://tests/integration/native_crowd_reducer_benchmark.gd
if ($LASTEXITCODE -ne 0) { throw "native reducer benchmark failed" }
```

On Linux, while the exported isolation variables above are still active:

```sh
export ELORIA_CROWD_EXPECT_USER_ROOT="$isolated"
export ELORIA_NATIVE_CROWD=1
export ELORIA_ARTIFACT_DIR="$results"
taskset -c 0-3 godot --headless --path godot-client \
  --log-file "$results/native-crowd-reducer.log" \
  --script res://tests/integration/native_crowd_reducer_benchmark.gd || exit 1
```

Both invocations write `native-crowd-reducer.json` and its log beneath the
isolated `$results` directory. `ELORIA_CROWD_EXPECT_USER_ROOT` and
`ELORIA_NATIVE_CROWD=1` remain required from the parity-run setup.
