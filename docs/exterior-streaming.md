# Exterior region streaming

Amberwood (384 m), Whitehorn Range (396 m), Grey Moors (384 m), Mirrorhold
(384 m) and Amethyst Barrens (384 m) form the first connected group. The client
loads the receiving scene before arrival and displays its actual authored
approach. The server's map handoff adopts that same root and rigidly rebases
the traveller and camera, preserving their position, heading and zoom.

## Scope

The generated continent graph enables background preloading on 17 walking and
causeway links. Only Amberwoodâ€“Whitehorn currently has reciprocal terrain
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

`_toolkit/streaming_borders.py` defines each reciprocal frame, a 42 m graded
approach, pair-specific ground materials and matching texture coordinates.
Moor crossings use meadow/heather/earth; the inhabited upland uses turf and
gravel; alpine and crystalline approaches use their own frost or scree mix.
One road's grading protects another road's surveyed strip. This matters at
Mirrorhold's two northern cols, only 87 m apart.

Terrain is split on exact triangle edges within an 80 m wide receiving strip.
Each border has its own overflow identity; making one neighbour resident hides
only that border's overflow. Original collision stays available to departure
tiles. The GLB also contains a 145 m deep subset of its own receiving terrain
and nearby static placements, named `StreamView_<border-id>__...`. These are
exact pieces of the same source geometry. They are excluded from minimaps and
active navigation. No neighbouring generated GLB is an input to these builds.
Placement selection uses transformed mesh bounds, so a tree canopy or boulder
that reaches into the strip stays visible even when its origin lies outside.
Grading also lifts linked portal, spawn and secret metadata with its landmark.

The loader groups normal geometry under `StreamActive` and receiving subsets
under `StreamPreview_<border-id>`. A resident shows only the matching subset;
adoption restores the complete authored scene. This prevents distant terrain
or an unrelated exit overlapping the current region. Preview collision is
restricted to picking layer 16, and disabled when the full region becomes active.
Static batches stay inside their active group, with cache format 3 retaining
the group layout and transforms.

Anchors sit halfway between each departure tile center and the reciprocal
arrival. `continent_portals.py` generates seven lanes with mirrored lateral
coordinates, validates their walkability, and preserves two tiles of arrival
clearance. The server transports facing and omits magical teleport effects for
declared ordinary land travel. The server still decides all traversal.

The Undercut's visual root doorway stays in place. Its interaction tile is now
in front of the closed decorative root frame (Amberwood 311,301); its secret
return, authored content posts and portal table move together.

## Rebuild

Rebuild and integrate the group from the client root:

```powershell
python eloria-assets/tools/rebuild_northern_regions.py --server C:/path/to/server --data C:/path/to/generated-data
```

Use `--skip-build` for reviewed packages. `--stage collision`, `--stage content`
and `--stage publish` allow a failed integration stage to resume. Revision-guarded
migrations preserve content IDs while moving coordinates. Collision generation,
all reciprocal portals, services, resources and encounters are synchronized in
one coordinating checkout. A relocation over 12 m stops for a designed approach.
The publisher records the actual served roster in `source/runtime-content.json`
and `runtimePopulation`, then updates only this group's package digests and the
shared connection JSON. Original lore/editor markers remain identifiable.
Gauntlet completion and bailout definitions use the same surveyed exterior
return as their portal records.

The client registry must use each region's compact origin: (116,116) for
Amberwood, Grey Moors and Amethyst; (120,120) for Whitehorn; (120,96) for Mirrorhold.
The server map sizes and arrival constants are versioned with the migration.

## Verification and expansion

Run `tests/test_exterior_streaming.gd` and `tests/test_map_cache.gd` in Godot,
the client movement/object/lighting/reconnect checks, and the server's
`tests/test_exterior_streaming.py` plus collision, content, portal, surveyed-deck
and inhabited-route contracts. `tests/integration/rendered_exterior_streaming.gd`
extends the real-client route walker with scene/actor identity and camera
continuity assertions and adjacent crossing captures. It accepts the same
`ELORIA_WALK_SPEC` and isolated local-server environment as the landscape walk.

Before enabling another visible join, survey both roads, blend their landforms
and materials, align tile-centre arrival frames, regenerate contracts, and walk
every lane in both directions. Test camera angles, shoulders, multi-neighbour
visibility and single-arrival connectivity, not just the portal's own tile.

The northern group uses local border frames and bounded receiving approaches;
it is not a single globally embedded continent. Region interiors, actors,
resources, ambient life and audio still activate with the server map. Their
handoff can remain visible even when the road and camera are continuous.
An unready scene still takes the synchronous fallback. Broader open-world work
requires cross-map server interest, lower-memory chunks and asynchronous GPU
preparation/attachment. The current budget remains one active map and at most
two neighbouring roots.

See [Northern region rollout](northern-region-rollout.md) for the landscape
principles and the remaining biome-by-biome plan.
