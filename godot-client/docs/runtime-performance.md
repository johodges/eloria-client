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

## Checking a change

`tests/test_runtime_performance.gd` guards the viewport scheduling, the surface
sample cache and the in-place packet decode.
`tests/integration/sunmane_performance.gd` writes frame timings, draw calls and
primitive counts as JSON for a region package.
