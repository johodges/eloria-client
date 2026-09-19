# Native presentation kernels: second crowd follow-up

This study continues `perf/native-crowd-300-benchmark` from
`269c0eeb83dba09a704230e684c72e5f5ea3eca8`. The earlier
[presentation cleanup](crowd-presentation-optimization.md) and
[original crowd study](native-crowd-study.md) retain the historical population
matrix, reducer investigation and original acceptance evidence.

## Scope and method

The primary fixture remains 300 actors, 150 camera-visible and 100 active,
with equipment, overhead information, animation, capes and representative
combat effects. The desired result is a complete rendered frame below
16.67 ms. Headless results measure a scene CPU proxy; windowed wall samples
include compositor/host pacing. Neither alone certifies sustained 60 FPS on
the intended midrange target. Render CPU and asynchronous GPU samples are
reported independently, not added to wall time.

All heavy local work runs serially on logical processors 0–3 (affinity mask
15); native builds use `--parallel 2`. All agents share that affinity limit.
Every run carries the user-approved label: `shared host; unrelated Godot jobs
authorized; activity not continuously monitored`.

The machine is the same Intel Core Ultra 9 275HX / RTX 5080 Laptop GPU host
with 31.38 GiB RAM, 16 GiB VRAM, Windows build 26100.9457, NVIDIA 591.91 and
Godot 4.7.2 stable official (`ed1daf0bf`). This is not a midrange hardware
certification. The development-host component headroom gates remain 8/10 ms
mean/p95 scene CPU, 3/4 ms render CPU and 6/8 ms world GPU, evaluated separately.

## Measured decisions

### Cache capsule invariants in GDScript

The cape solver computed each capsule axis and squared span repeatedly within
its three chains and two relaxation passes. Computing these once per modifier
pass preserves constraint order, floating-point operation order and bone
writes. Complete-modifier measurements against frozen `269c0eeb8` fell from
61.495 to 56.433 microseconds (8.23%) across seven rotated paired trials. All
seven pairs were faster. Exact prior-solver parity and the existing cloth and
idle tests passed. This change is enabled in the default GDScript path.

### Reject the GDScript ArrayMesh rewrite

Moving spell-flight geometry into packed arrays in GDScript preserved exact
mesh arrays and material parameters but made the complete construction and
submission measurement slower: 6.53% windowed Compatibility and 9.92%
headless. That candidate remains a test fixture only. Mesh readback was kept
outside the accepted timed loop; an earlier instrumented attempt is retained
separately as rejected evidence.

### Measure the cape solver's scene contribution

A diagnostic disabled cape simulation while retaining equipped cape meshes.
It does not preserve animated cape presentation and cannot qualify as an
optimization or acceptance run. Two rotated full/off comparisons reduced mean
scene CPU by 20.7% and 6.0%; the median of run means was 31.570 versus
27.383 ms. One disabled run had a worse p95. This noisy shared-host evidence,
together with 75 active modifiers and the focused call cost, justified testing
an arithmetic-only native kernel. It does not justify deleting simulation.

### Prototype two coarse native operations

`NativeCapeConstraintKernel.step()` advances all three cape chains in one
call. It validates inputs, computes into local packed copies and publishes
point/history arrays only after the complete step. Godot retains the modifier,
animated skeleton reads, rest construction, clock, state ownership and bone
pose writes. A rejected call leaves point/history state unchanged for the
original GDScript fallback.

`NativeSpellFlightGeometry.build()` constructs one complete flight's ribbon
and glow geometry and returns six packed arrays. Godot retains endpoint
tracking, event timing, lifetime, materials, nodes and mesh submission. A
rejected result selects the complete original ImmediateMesh implementation
for that flight. World-effect rings, runes, particles and actor combat cues
remain in Godot.

These kernels do not add native actor storage, a new renderer, animation LOD
or new visibility rules. The existing native reducer is independently
selectable and stays disabled in presentation comparisons. The default
renderer remains Compatibility.

The native presentation paths are opt-in through `ELORIA_NATIVE_PRESENTATION`:
`0`/unset disables both; `cape`, `flight` or `both` selects the corresponding
kernel. Missing extensions retain the GDScript path. Benchmarks verify actual
native instances, successful calls and zero fallback calls, so requesting a
native path cannot silently count as measuring one. Build instructions and
the exact boundary are in the [extension README](../native/native_crowd/README.md).

## Correctness and focused performance

The production flight path passed exact mesh-array and material-parameter
comparison in Compatibility and Forward+, opt-in mode checks, call-counter
checks and an injected malformed-result fallback comparison. The broader
flight probe covers effect branches, powers, cameras, endpoint changes,
zero-length/vertical/long trajectories, release, arrival and expiry. Timings
include native boundary calls, production output validation and mesh submission.
The rendered complete-draw median fell from 21,971.5 to 7,624 microseconds per
180 draws (65.30% lower); the headless result fell from 21,789.5 to 6,868
microseconds (68.48% lower). These are focused construction measurements,
not total frame or GPU improvements.

The native cape path passed comparison to the immediately preceding frozen
GDScript solver over the complete motion/reset/teleport sequence, checked
actual native use with zero fallback, and verified atomic malformed/read-only
input rejection and wrapper fallback parity. Existing cloth and idle tests
passed. Its interface-inclusive complete-modifier median fell from 70.569
to 28.400 microseconds (59.76% lower), a saving of 42.169 microseconds per
pass across seven rotated trials of 1,500 passes. Baseline drift between
separate experiments means these focused results must not be combined into
an invented aggregate speedup.

The existing armour-clearance fixture already failed with both original and
optimized GDScript solvers in the previous study; this is a known inherited
failure, not a claim that every repository test passes.

## Evidence and reproducibility

Portable evidence includes:

- [GDScript cape cache and solver diagnostic](benchmarks/crowd-cape-capsule-and-solver-diagnostics-2026-09-19.json).
- [Rejected GDScript ArrayMesh candidate](benchmarks/effect-arraymesh-flight-negative-2026-09-19.json).

Raw logs, process manifests, source/library hashes and captured arrays live
under the task worktree's ignored `godot-client/test-artifacts` directory.
Failed attempts remain separate from accepted measurements. A native build
initially failed before compiling the candidate because its process lacked
the MinGW runtime directory in `PATH`; prepending that directory locally as
documented resolved the failure. No machine-wide compiler setting changed.

## Repository isolation

The original fetched `develop` starting commit was
`a0806f2f2462a87037171042e62a6ed3ff37c760`. All work is confined to
`C:/Users/User/Desktop/eloria-project/wt-native-crowd-300` on
`perf/native-crowd-300-benchmark`. No push or merge is part of this work.
