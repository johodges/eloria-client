# Combat and impact geometry follow-up

This study continues the isolated `perf/native-crowd-300-benchmark` branch from
`9677447685464fcb19a5cb4e7e739f0f67670ae0`. The previous
[native presentation study](crowd-native-presentation-kernels.md) measured
24.328 ms median headless scene CPU proxy in its controlled candidate runs.
The 60 FPS / 16.67 ms complete-frame target remained unmet.

## Current bottleneck diagnostics

Two fresh processes used the unchanged production source, native cape and
flight kernels enabled, and the GDScript actor reducer. Each exercised the
same 300 actors, 150 camera-visible, 100 active fixture. They rotated the
order of full presentation, animation frozen, and effects disabled. Sampling
lasted five seconds after a one-second warmup, with at least 60 samples.

| Diagnostic | First process mean / p95 / p99 | Reversed process mean / p95 / p99 |
| --- | ---: | ---: |
| Full presentation | 23.992 / 37.654 / 45.283 ms | 23.827 / 40.226 / 44.880 ms |
| Animation frozen | 16.709 / 25.767 / 31.383 ms | 20.288 / 30.755 / 36.135 ms |
| Effects disabled | 17.293 / 25.707 / 32.315 ms | 19.955 / 31.645 / 41.103 ms |

Freezing animation reduced the mean by 3.539–7.283 ms in these two comparisons;
disabling effects reduced it by 3.872–6.699 ms. These are broad diagnostic
changes that remove visible behaviour, not candidate optimizations. They
overlap and must not be added. Full-scene means were stable, while the
ablations varied materially with order and host conditions.

The full fixture emitted exactly 150 skeleton updates per frame, with at
most one per actor. Freezing all AnimationPlayers still left 75 updates per
frame from active capes. Native cape calls stayed at 75 per frame in every
cell. Effects-disabled cells contained no world effects; full cells averaged
about 57–58 live effects. Event rates remained about 560–562 commands and
67.3–67.6 combat events per second. Native fallbacks were zero.

The complete combat callback cost about 3.50 ms per full frame, and still
2.92–3.28 ms with effect geometry disabled. This directs the next small
GDScript experiment toward repeated bow and prop work. Earlier focused
measurements also showed repeated world-effect detail construction cost
about 74 microseconds per call, justifying a separate coarse native geometry
experiment. The native path must preserve all effect branches, materials,
timing and geometry before scene measurements can qualify it.

The [diagnostic evidence](benchmarks/crowd-animation-effects-attribution-2026-09-19.json)
retains raw report hashes, source and process attestations, counters and
event rates. Diagnostic hooks add overhead and are excluded from ordinary
acceptance summaries. These measurements do not separately identify engine
animation evaluation, skeleton finalization or skinning cost.

## Changes and focused checks

### Retain unchanged bow geometry in GDScript

`RangerBow3D` caches the upper/lower limb nodes when loading an asset and
retains its string surface while the exact local draw point and flex are
unchanged. An asset change invalidates the cache. World transforms, aim,
smoothing, recoil calculations and arrow state still update every callback.
This change is enabled in the ordinary GDScript path.

The focused probe measures the complete combat callback, including its engine
calls. Eight trials alternate the frozen and current implementation. The
production Compatibility medians were 32.958 to 17.692 microseconds for an
idle equipped bow (46.32% lower), and 31.883 to 17.249 microseconds for a
stationary ranged hold (45.90% lower). Headless reductions were 40.82% and
40.30%. These fixed-pose focused measurements do not establish a whole-frame
gain, and differences in unchanged sword/casting paths are treated as noise.

Nineteen presentation scenarios matched the frozen implementation, including
casting, melee, ranged actions, disabled/hidden effects, rewinds, transitions
and equipment changes. A separate dynamic bow sequence covers changing world
poses, draw points and scale, release recoil, return to idle and a different
bow asset. The existing combat test passed across all 16 player rigs.
The [bow evidence](benchmarks/combat-bow-pose-cache-2026-09-19.json) retains
prototype and production results separately.

### Build complete world-impact detail surfaces natively

The optional `NativeWorldEffectGeometry.build()` constructs an entire effect's
detail surface in one call. It preserves radial marks, healing/ward/harm
shapes, contact sparks, area waves and every spell-specific shape branch.
Godot retains effect creation, anchors, clocks, lifetime, rings, particles,
materials and mesh submission. The default remains the existing GDScript path.

`ELORIA_NATIVE_PRESENTATION=world` enables this kernel alone; `all` combines it
with the existing cape and flight kernels. `both`/`1` still mean cape plus
flight. Missing native support retains the GDScript path, and a rejected build
permanently switches that effect instance to its original ImmediateMesh.
Benchmarks require active instances, successful calls and zero fallback calls.

The production probe measures complete construction, validation and submission.
Seven trials alternate implementations and exclude setup, mesh readback and
GPU completion. The timing workload uses effect IDs 0–5 at power 10; it does
not include ring, particle, flight or anchor work.

| Focused detail draw | Frozen GDScript | Native | Reduction |
| --- | ---: | ---: | ---: |
| Compatibility | 83.806 µs | 45.444 µs | 45.77% |
| Forward+ | 80.092 µs | 49.611 µs | 38.06% |
| Headless CPU | 75.447 µs | 36.719 µs | 51.33% |

The geometry comparison covers 18 effect IDs spanning every shape branch,
powers 1/3/5/7/10, progress endpoints and an intermediate phase, area effects,
flight contact and an unknown effect. A separate contract checks particle
counts at all ten power levels. Vertices, colours, array slots/order and
material properties match exactly in both rendered comparisons. Headless
readback is explicitly not authoritative. Production tests also check mode
selection, counters and exact GDScript fallback after injected malformed output.
The [native world-detail evidence](benchmarks/world-effect-native-geometry-2026-09-19.json)
records source/library hashes and rejected setup attempts separately.

Each focused production run recorded 2,520 successful native calls and no
fallbacks. Ten production checks passed across Compatibility, Forward+ and
headless execution, including the existing flight and cape contracts and all
eleven presentation-mode cases. The combined Windows x86_64 library is
981,504 bytes, SHA-256
`7321af0475b974313a15317ed6f9db459cf6e47146c5b5ff4ca983f74ccb5a1a`.
Linux build/runtime validation remains outstanding; the shipping renderer
and native opt-in default are unchanged.

## Measurement conditions

All task commands share logical processors 0–3, affinity mask 15. Engine
jobs and native builds run serially; builds use two workers. Every timing
run carries the user-approved label:
`shared host; unrelated Godot jobs authorized; activity not continuously monitored`.

The host is the same Core Ultra 9 275HX / RTX 5080 Laptop GPU system as the
previous study. Results are development-host observations, not certification
on a midrange target. Headless wall time is a scene CPU proxy; windowed wall
time includes host/compositor pacing. Render CPU and asynchronous GPU samples
are separate measurements, never summed with the wall samples.
