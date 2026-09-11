# Exterior region streaming

Amberwood (384 m) and Whitehorn Range (396 m) now share a surveyed road. The
client loads the actual receiving scene before arrival, displays it across a
common terrain cut, and adopts that same scene when the server changes maps.
The traveller and gameplay camera are rebased into the new coordinate frame.
Their screen position, heading and zoom remain continuous.

## Scope

The generated continent graph enables background preloading on 17 walking and
causeway links. Only Amberwood–Whitehorn currently has reciprocal terrain
surveys and simultaneous visible scenery. The other 16 links preload hidden
destinations and retain the existing scene transition. Seven ferry links and
interior/magical portals retain their own travel behavior.

This is scene streaming with authoritative map handoff. Networked players,
enemies, NPCs, harvest objects, audio and dynamic lamps still belong to the
active server map. Cross-border actor visibility, combat and resource selection
need a separate server interest protocol; scenery does not simulate those actors.
The minimap changes to the active region's existing coordinate system.
Crowded arrivals can still be adjusted by the server's existing free-tile rule;
the current live proof uses one QA traveller, not a multiplayer border crowd.

## Runtime

- `ExteriorRegionStream` checks proximity every 250 ms. It begins a private
  background import within 170 m of an authored crossing and retains a neighbor
  until 220 m. The closest two neighbors are eligible; loading uses one worker.
- `WorldLoader.prepare_detached` constructs a private tree, including collision
  and static batches, off the active SceneTree. It does not publish shared cache
  state or write disk cache entries on the worker. Completed results attach on
  the main thread. The existing package digest validates disk cache reads.
- Declared NPC body and harvest model scenes are prepared privately, then
  installed in `GlbSceneCache` on arrival. Resource and absolute paths share a
  canonical cache key. Equipment and individual creature animation preparation
  are not yet part of the proximity manifest.
- Generation tokens discard work superseded by disconnect, teleport or another
  transition. Closing the client lets its worker finish before renderer teardown.
  Distant resident roots are freed. Shared actor model caches last until logout.
- Active ground keeps navigation layer 8. A visible neighbor exposes terrain
  only on picking layer 16, with no active structural collision. Clicking into
  it routes through the server crossing, then continues to the clicked tile
  after the authoritative arrival. A new world click, minimap click or keyboard
  movement cancels that continuation.
- A ready scene is transferred, not parsed again. A nearby surveyed crossing
  also retains the old scene for looking back. The camera focus, pan, yaw, and
  traveller's interpolation endpoints all receive the same rigid transform.
- If no scene is ready (for example a teleport directly to a cold border), the
  existing synchronous loader remains the fallback. This can still stall.
- Atmosphere blends across 65 m on either side of the shared road, including
  sun orientation in the rebased coordinate frame. The sky resource is reused.

## Authored geography and contracts

`_toolkit/streaming_borders.py` defines reciprocal anchors, a 42 m approach
collar, a broad saddle, a shared gravel/turf/frost palette and matching texture
coordinates. The final paint sits above continuous substrate. Terrain is split
at the exact join; `_StreamOverflow` geometry remains available for authoritative
grounding and is visually hidden when the receiving region is resident.
Ordinary map-specific terrain remains beyond the cut while loading. The old
copied Amberwood/Whitehorn vistas were removed, so these builds no longer
depend on each other's generated GLB. Other unsurveyed approaches retain their
existing static views.

Anchors sit halfway between each departure tile center and the reciprocal
arrival. `continent_portals.py` generates seven lanes with mirrored lateral
coordinates, validates their walkability, and preserves two tiles of arrival
clearance. The server transports facing and omits magical teleport effects for
declared ordinary land travel. The server still decides all traversal.

The Undercut's visual root doorway stays in place. Its interaction tile is now
in front of the closed decorative root frame (Amberwood 311,301); its secret
return, authored content posts and portal table move together.

## Rebuild

From each region's `source` directory, run:

```powershell
python rebuild_landscape.py --server C:/path/to/server --data C:/path/to/generated-data
```

For an exterior-only geometry iteration, run `build_amberwood.py` or
`build_whitehorn.py`, then the same wrapper with `--skip-build`. The wrappers
apply surface-height refinement, walk openings, landmark collision, scoped
server collision sync, generated map grids, portal/content authoring, marker
positions, package digests and the shared connection manifest. No hand edits to
generated GLB, collision or server positions are needed.

`eloria-assets/tools/build_exterior_streaming.py --server C:/path/to/server`
publishes the same connection JSON to the client and server. Supply `--server`
to include the region's NPC model paths. The scene cache format is version 2;
older snapshots rebuild because static batches now use root-local transforms.

## Verification and expansion

Run `tests/test_exterior_streaming.gd` and `tests/test_map_cache.gd` in Godot,
the client movement/object/lighting/reconnect checks, and the server's
`tests/test_exterior_streaming.py` plus collision, content, portal, surveyed-deck
and inhabited-route contracts. `tests/integration/rendered_exterior_streaming.gd`
extends the real-client route walker with scene/actor identity and camera
continuity assertions and adjacent crossing captures. It accepts the same
`ELORIA_WALK_SPEC` and isolated local-server environment as the landscape walk.

Before enabling another visible join, survey both receiving roads, blend their
landforms and materials, align tile-center arrival frames, regenerate all
contracts, and walk every lane in both directions. Retain each biome's own
settlement pattern and terrain logic. Multiple connected joins also need a
continent-wide orientation and loop-consistency survey; the pilot uses local
rebasing and is not a globally embedded continent.

Next pairs: Amberwood–Grey Moors (dry meadow to wet peat causeway),
Whitehorn–Mirrorhold (snowline to inhabited granite terraces), then
Whitehorn–Amethyst Barrens (exposed rock and crystalline seams). Keep ferry
journeys deliberate. A broader production rollout also needs lower-end memory
budgets, chunked attachment/GPU preparation, and cross-map actor interest.
