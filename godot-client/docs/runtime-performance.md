# Client runtime performance

Notes on the runtime cost of the Godot client and the mechanisms that keep it
down. Measured on the Four Gates package (1717 imported mesh nodes referencing
42 meshes) at 1280x720 with the GL Compatibility renderer.

| | before | after |
| --- | --- | --- |
| Draw calls per frame, minimap and full map wired as shipped | 9 237 | 335 |
| Draw calls per frame, gameplay camera alone | 559 | 335 |
| Visible world `MeshInstance3D` | 1 717 | 687 + 132 batches |
| First actor spawned in a session | 1 169 ms | 1 204 ms |
| Every actor after the first | 1 148 ms | 2.5 ms |

## Where the frame goes

**One world, three cameras.** `MapViewport` and `FullMapViewport` share the
gameplay `World3D`, so each is a complete extra render of the region - geometry,
materials and the directional shadow pass. Both shipped on `UPDATE_ALWAYS`,
which is where the 9 237 draw calls came from. They are now idle by default and
`Main._update_map_viewports()` asks for a single redraw only while the matching
UI is on screen: the minimap at ~15 Hz, the full map at ~5 Hz. The character
creation preview follows the same rule through `_update_preview_viewport()`.

If you add another SubViewport over the gameplay world, drive it the same way.
Leaving one on `UPDATE_ALWAYS` silently doubles the client's raster cost.

**Static instance batching.** A region is mostly repeats: 140 tree trunks, 36
lamps, 32 wall segments, all pointing at a handful of shared meshes.
`WorldLoader._batch_static_instances()` collapses groups of four or more
identical opaque instances within a 180 m cell into one
`MultiMeshInstance3D`. Cells keep frustum culling meaningful; without them a
single batch spanning the whole city would always be drawn.

Instances are skipped when they carry collision (any child node), a skin, a
material override, a per-surface override, a visibility range, or a blended
material - blended surfaces are sorted per instance, so batching them would
change the picture. Source nodes stay in the tree with `visible = false`, so
manifest declarations, name lookups and tooling keep resolving.

Per-map controls live under `rendering` in the world manifest:

```json
"rendering": {
  "batchStaticInstances": true,
  "batchMinimumInstances": 4,
  "batchCellMetres": 180.0
}
```

**Actor visuals off the map cameras.** Nameplates and selection rings render on
visual layer 2. The gameplay camera draws layers 1 and 2; the map cameras draw
layers 1 and 3. They therefore cost nothing in the two top-down views, which
never showed them legibly anyway.

## Where actor spawns go

**Model and equipment glTF parsing.** Every actor used to run
`GLTFDocument.append_from_file()` for its race mesh, again for its hair, and
again for each native equipment model. `GlbSceneCache` parses each file once,
packs it, and instantiates from there. Instances share mesh and material
resources; per-actor tinting goes through `material_override`, so nothing leaks
between actors.

**Animation retargeting.** `Universal_Animation_Library.glb` is 11 MB and holds
162 clips built from roughly 226 000 keyframes. `NativeAnimationImporter` used
to reparse it and rebuild every clip key by key, in GDScript, for each actor.
It now rebuilds only the clips the actor's action map can request - 18 of the
162 for the current maps - and caches the finished `AnimationLibrary` under the
source path, skeleton node path, rig signature and clip set. Animations are
immutable during playback, so one library backs many `AnimationPlayer`s safely.

The remaining ~1.2 s is the one-time parse of the animation library. It is paid
by the first actor that enters view. Prewarming it behind the map loading
screen is the obvious next step.

Both caches are dropped in `Main._clear_world_presentation()` when the session
ends.

## Per-packet and per-frame work

* `state_changed(&"actors")` fires once per actor packet. `Main` coalesces the
  burst into one `_sync_world()` per frame instead of rebuilding every actor's
  presentation once per packet.
* The rendered-surface ray sample is cached per actor and repeated only when
  that actor's position changes, instead of once per actor per packet.
* `ReplicatedActor3D` stops its physics processing once its interpolation
  segment has finished and it faces where the server says it should, and wakes
  on the next packet, keypress or surface sample.
* `EloriaProtocol.try_decode()` takes an offset so a burst drains without
  re-copying the receive buffer after each packet.
* `render_diagnostics()` walks an actor's whole subtree. It was an argument to a
  `print_debug` that ran on every placement; `print_debug` is a no-op outside
  debug builds but its arguments are always evaluated. It is now a one-shot per
  map load.

## Second pass: animation, per-packet rebuilds, spawns

Measured 2026-09-05 on develop, before and after, at 1280x720 on the GL
Compatibility renderer with an RTX 5080 laptop GPU. Scene CPU is a headless
run with the engine's idle sleep removed (`OS.low_processor_usage_mode_sleep_usec
= 1`, otherwise every headless frame is padded to 6.9 ms); render CPU and GPU
are the renderer's own timers (`RenderingServer.viewport_set_measure_render_time`
and `viewport_get_measured_render_time_cpu/gpu`). Windowed wall-clock frame
times are not usable for this work: the compositor throttles a background
window to steps of the refresh rate, and `Performance.TIME_PROCESS` read from a
SceneTree script is not meaningful either.

| | before | after |
| --- | --- | --- |
| Sunmane herd, 111 animals, GPU per frame over the empty steppe | +1.8 ms | +0.3 ms |
| 61 idle actors spread over 60x60 tiles, scene CPU per frame | 1.24 ms | 0.58 ms |
| `_sync_stats` with the statistics window hidden | 9.4 ms | 0.6 ms |
| One chat line arriving with a full 1000-line buffer | 7.7 ms | 0.15 ms |
| Actor flush with 81 actors and nothing changed | 1.1 ms | 0.1 ms |
| `ItemAtlas.icon_for` | 31 us | 2 us |
| Twenty actors entering view | 48 ms in one frame | 13 ms a frame for five frames |
| The first actor's animation-library parse | 330 ms on the main thread | a worker thread, during the map load |

**The animation gate.** Skinning was the largest cost on a populated map: about
5 ms a frame for sixty race actors on screen (77 bones, 9 skinned mesh
instances and 26 700 vertices each, re-posed and re-skinned every frame), and
every body was animated whether or not the camera could see it. `AnimationGate`
(`src/world/animation_gate.gd`) classifies each animated body against the
gameplay camera ten times a second: outside the frustum its AnimationPlayer is
paused where it stands, beyond 45 m it is stepped every other frame by the time
both frames covered, so it plays at the same speed with half the updates, and
otherwise it is untouched. `Main._update_animation_gate()` drives the actors
through `ReplicatedActor3D.set_animation_tier()`, which sleeps the cape cloth
along with a paused body and never pauses a clip that does not loop, so an
actor caught sitting down finishes the move; `AmbientPopulation` gates its own
herd from `_process`. What is on screen and near the camera animates exactly as
before; the local player is never gated.

**A window that is not showing is not rebuilt.** The statistics document, the
counters page and the session table are rebuilt from controls, and the
partial-stat packets that drive them arrive with every health, food and
experience tick. `_sync_stats_window()` now only marks them stale while the
window is hidden; `stats_panel.visibility_changed` rebuilds them when it is
shown. The meters, skill rows and indicators on the HUD are still refreshed by
every packet.

**Chat lines are appended.** `_append_chat_line()` appends the arriving line to
the chat panel and the console and drops the oldest paragraph past the cap with
`remove_paragraph(0, true)`, instead of clearing and re-appending a hundred and
a thousand lines. A log whose last rendered line is no longer the line before
the new one - a reconnect cleared the buffer, a fixture replaced it - is rebuilt
in full, so the incremental and full paths cannot disagree.

**Only the actors that changed are re-presented.** Every AppState site that
writes `actors` records the id in `changed_actors`; the per-frame flush calls
`_sync_world(AppState.take_changed_actors())` and visits those ids plus any
actor that still has no node. `_sync_world()` with no argument is still the
full pass a map load and the fixtures use. The command reducer copies the actor
record shallowly; nothing writes into its nested dictionaries in place.

**Spawns are budgeted and the library is prewarmed.** `_sync_world` builds at
most `ACTOR_SPAWN_BUDGET` actors per pass and leaves the rest for the next frame
(`_spawn_backlog`); the local player is always built at once.
`NativeAnimationImporter.prewarm()` parses a shared library on a worker thread
as the map starts loading, and the parsed source is kept for the session so a
second rig never parses the 11 MB file again.

**Item icons are shared.** `ItemAtlas.icon_for()` keeps one AtlasTexture per
picture, and command 226's descriptions are indexed by slot once per list
rather than searched for every slot of every refresh.

## Checking a change

`tests/test_runtime_performance.gd` guards the viewport scheduling, the surface
sample cache, the in-place packet decode, the shared icons, the actor change
set, the hidden statistics window, the appended chat line, the prewarmed
library and the spawn budget. `tests/test_animation_gate.gd` guards the gate's
tiers and the one-shot exemption.
`tests/integration/sunmane_performance.gd` writes frame timings, draw calls and
primitive counts as JSON for a region package.
