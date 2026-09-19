# Equipment data and presentation follow-up

This study continues the isolated `perf/native-crowd-300-benchmark` branch from
`90b0dd505cb7a693b6886dd99dc8efd7db0283c2`. The preceding
[impact geometry study](crowd-impact-geometry-optimization.md) measured a
21.114 ms median headless scene CPU proxy and no consistent rendered gain.
The target remains a complete frame below 16.67 ms with 300 actors, 150 visible
and 100 active, retaining equipment, overhead information, animation and effects.

## Choosing the next change

The new [script profile evidence](benchmarks/crowd-script-profile-2026-09-19.json)
captures the existing primary fixture with native presentation `All` and the
GDScript reducer. The installed Godot executable requires both `--debug` and
`--profiling` for its local script profiler. Its `FRAME` output is one frame
snapshot sampled periodically, not an aggregate over the preceding interval.
The capture contains 18 snapshots; five contain the benchmark's `_sample_cell`
function. Coroutine scheduling makes that a useful indication of the sampling
phase, not an exact capture boundary or an unbiased sample of every frame.

Within those five snapshots, hand-prop visibility costs about 1.073 ms per
snapshot inclusive, with equipment-model resolution accounting for 0.770 ms.
That path resolves fit groups and duplicates fitted model data merely to test
whether the weapon has a separate animated-bow representation. These are
nested costs and must not be added. They justify a focused complete-callback
comparison, not a predicted whole-frame saving.

Other small candidates were deferred: cape bone-pose writing accounts for
about 0.588 ms per snapshot, world-detail mesh submission 0.369 ms, and flight
surface submission 0.206 ms. Even removing each entire measured cost would
leave a small upper bound before integration overhead. These sparse observations
do not justify another native kernel. Effect construction remains an event
cost; the earlier allocation probe already measured it separately.

Profiler timings are diagnostic only. Synchronous engine and extension calls
are charged to their script callers when native-call profiling is disabled.
Inherited callback accounting and nested functions can also make reported
script totals exceed the frame total. Neither those totals nor the profiled
29.720 ms wall mean are acceptance measurements.

The official Godot binary has no debug symbols, so the available script tools
cannot reliably distinguish engine animation evaluation, skeleton finalization,
skin upload and scene traversal. Godot recommends a production build with
`production=yes debug_symbols=yes` for that investigation.
[Official profiling documentation](https://docs.godotengine.org/en/4.7/engine_details/development/profiling/index.html#sampling-profilers).
The existing production animation schedule is retained; a synthetic manual
advance fixture would not be equivalent evidence.

The equipment audit also found a lifecycle cost: each actor deep-copies the
entire 860,660-byte equipment catalog. The current investigation tests bounded
immutable snapshots while preserving the previous defensive-copy behavior:
changing the caller's catalog must not change an existing actor, and a newly
configured actor must receive the changed contents. Actor equipment choices,
appearance, materials, nodes and animation remain individually owned.

## Implementation and focused checks

The hand-prop change caches only whether the resolved main-hand model has
`rangedAnimationScene`. Weapon removal/replacement and actor reconfiguration
invalidate it. Equipment creation seeds it from the model already resolved for
that operation. Every visibility call still assigns every valid current prop,
including a newly attached prop or a node whose visibility changed externally.
Disabled, empty and shield-only paths need no weapon lookup.

Seven rotated trials compare the complete `CombatPresentation3D.update_pose()`
callback against an exact frozen accessor from the preceding runtime. Timed
actors have no lookup-count instrumentation; separate actors provide the
untimed lookup traces. The windowed Compatibility medians are:

| Scenario | Frozen accessor (µs/callback) | Cached accessor | Change |
| --- | ---: | ---: | ---: |
| Idle bow | 18.610 | 9.682 | -48.0% |
| Ranged hold | 18.208 | 8.378 | -54.0% |
| Melee | 17.205 | 5.088 | -70.4% |
| Casting, effects disabled | 17.648 | 4.443 | -74.8% |
| Casting, full effects | 116.718 | 96.945 | -16.9% |

Headless results agree in direction. These focused timings exclude skeleton
evaluation and signal dispatch and do not predict a whole-frame gain. Exact
visibility snapshots cover melee and ranged weapons, shields, the legacy bow,
empty equipment, unchanged equipment, swaps, clearing, late props, external
visibility changes, effects disabled and a changed rig/fit-specific registry.
Warm candidate callbacks perform zero model lookups versus two in the frozen
accessor for the timed scenarios.
The [focused evidence](benchmarks/hand-prop-visibility-cache-2026-09-19.json)
preserves both raw runs. Their captured baseline commit string contained a
typo; the correction is explicit in the bundle. The reviewer independently
matched the frozen method bytes against the real historical commit and
recomputed every scenario median from the raw trials. No timing artifact was
rewritten to correct metadata.

The first catalog prototype serialized and compared content on every actor
acquisition. It reduced retained allocations by roughly 821 MB, but increased
the focused 300-copy median from 1.274 s to 5.490 s. That design was rejected.
The retained design prepares a recursively read-only snapshot once when Main
loads its catalog. Actors share only an exact recognized prepared identity;
arbitrary caller dictionaries still receive `duplicate(true)`. The registry
retains at most four prepared catalogs. Evicted identities safely fall back
to copying. No per-actor serialization or content hashing remains.

The final eight-trial rotated catalog probe measures 300 deep copies at a
median 1,535,054 µs versus 90.5 µs for prepared acquisitions. Preparation costs
36,255.5 µs once. The acquisition interval retains 824,672,634 additional Godot
static bytes for deep copies versus 7,434 bytes for shared references. The
latter excludes the prepared snapshot allocated before that interval; neither
counter is process RSS. This establishes a lifecycle/allocation improvement,
not a frame-rate result.

The final contract checks detached recursive freezing, mutable fallback,
typed containers, capacity/eviction and unsupported packed/Object input.
Two real rigs and two equipment kits produce matching surface-array hashes,
transforms, skin bindings, material texture/color state and visibility through
swaps. Actors keep distinct equipment nodes and material-override state, and
clearing or changing one actor cannot alter another. The existing equipment
fit-profile and 16-rig combat tests also pass under windowed Compatibility.
An earlier headless fit-profile attempt failed during script loading before
explicit helper preloads were added; it is rejected evidence, not a passed
test. The final-byte windowed rerun resolves that regression check.

The shared-catalog census runs outside the benchmark sample interval and
records actual actor registry identities, read-only state and sharing with
Main. This verifies whether the production fast path is used independently
of timing or memory counters. Full-scene results below must distinguish
Godot static allocation counters from process resident memory.

## Controlled comparison protocol

The historical runtime is `90b0dd505cb7a693b6886dd99dc8efd7db0283c2`.
Both variants use native presentation `All`, the GDScript reducer and the same
981,504-byte native DLL, SHA-256
`7321af0475b974313a15317ed6f9db459cf6e47146c5b5ff4ca983f74ccb5a1a`.
Only Main and ReplicatedActor runtime sources are reversed; the final harness
and optional catalog helper remain identical, and the historical runtime never
calls that helper. The intended sequence is headless A/B/B/A/A/B, then windowed
B/A/B for each renderer, with five-second sample intervals and full features.
Report packaging rejects a baseline other than 300 independent mutable actor
catalogs or a candidate other than one shared read-only Main catalog.

Run serially from the dedicated worktree with clean tracked sources:

```powershell
(Get-Process -Id $PID).ProcessorAffinity = 15
$crowdRevision = (& git -c safe.directory=C:/Users/User/Desktop/eloria-project/wt-native-crowd-300 rev-parse HEAD).Trim()
$crowdReplay = @{
    OptimizedRevision = $crowdRevision
    BaselineRevision = '90b0dd505cb7a693b6886dd99dc8efd7db0283c2'
    GodotPath = '.\godot-client\Godot_v4.7.2-stable_win64_console.exe'
    BaselineNativePresentation = 'All'
    CandidateNativePresentation = 'All'
    RelativePaths = @(
        'godot-client/src/app/main.gd'
        'godot-client/src/actors/replicated_actor_3d.gd'
    )
    SampleMilliseconds = 5000
    CpuSlotGranted = $true
}
& .\godot-client\scripts\run_crowd_reversal_benchmark.ps1 @crowdReplay `
    -Mode Headless -Renderer gl_compatibility -Sequence 'A,B,B,A,A,B' `
    -Label 'equipment-data-replay-headless'
& .\godot-client\scripts\run_crowd_reversal_benchmark.ps1 @crowdReplay `
    -Mode Windowed -Renderer gl_compatibility -Sequence 'B,A,B' -Capture `
    -Label 'equipment-data-replay-gl'
& .\godot-client\scripts\run_crowd_reversal_benchmark.ps1 @crowdReplay `
    -Mode Windowed -Renderer forward_plus -Sequence 'B,A,B' -Capture `
    -Label 'equipment-data-replay-forward-plus'
```

`-CpuSlotGranted` records an exclusive task-owned heavy-job handoff, not
permission to overlap task-owned engine jobs. Native setup remains in the
[extension README](../native/native_crowd/README.md).

## Measurement conditions

All task commands and their children use logical processors 0–3, affinity mask
15. Heavy engine/test jobs run serially with an explicit shared CPU-slot handoff.
The user-approved interference label remains:
`shared host; unrelated Godot jobs authorized; activity not continuously monitored`.
The high-end development host is not a midrange certification target. Native
presentation stays opt-in, the GDScript reducer is retained, and the shipping
renderer is unchanged. Headless scene time, windowed wall time, render CPU and
asynchronous GPU samples remain distinct measurements.
