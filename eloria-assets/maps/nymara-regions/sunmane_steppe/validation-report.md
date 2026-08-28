# Sunmane Steppe validation report

Every result below was produced in this workspace against the committed
artefacts. Commands are in `README.md`.

## glTF 2.0 conformance

Khronos glTF-Validator 2.0.0-dev.3.10, the same version the Four Gates package
records.

| Package | Errors | Warnings | Infos |
|---|---:|---:|---:|
| `world.glb` | 0 | 0 | 12 |
| `world-lod2.glb` | 0 | 0 | 12 |

The twelve infos in each are `NODE_EMPTY`, one per lighting marker node. Those
nodes are intentional: they carry the warm landmark and transition light
positions the region description calls for, as named transforms rather than a
glTF light extension, so the package needs no loader change. Full reports are
committed as `world.glb.validator.json` and `world-lod2.glb.validator.json`.

Independent structural verification, separate from the Khronos tool and from
Godot, is in `tools/sunmane/validate_package.py`: it parses the GLB container
and JSON chunk itself and checks self-containment, node-name uniqueness, that
every declared collision and landmark node actually exists, the coordinate and
minimap transforms, and the landmark counts. **316 of 316 checks pass.**

## Client tests

Run with Godot 4.7.2 - the version `godot-client/project.godot` pins - under
`xvfb` with the `gl_compatibility` renderer.

| Test | Result |
|---|---|
| `sunmane_grounding.gd` | PASS |
| `sunmane_traversal.gd` | PASS |
| `rendered_sunmane_steppe.gd` | PASS |
| `sunmane_minimap.gd` | PASS |
| `sunmane_performance.gd` | PASS |
| `test_protocol.gd` (existing) | PASS |
| `test_world_input.gd` (existing) | PASS |
| `test_native_glb_assets.py` (existing) | PASS |
| `world_validation.tscn` Four Gates smoke test (existing) | PASS |
| Main scene smoke test (existing) | PASS |
| `check_provenance.py` | PASS |

### Grounding

`sunmane_grounding.gd` loads the package through the real `WorldLoader`, then
raycasts the navigation-surface layer exactly as `main.gd` does when it places
an actor.

- Navigation-surface bodies created: 66 (64 terrain chunks, the edge apron and
  the crossroads plaza).
- Arrival datum `(58, 58)` grounds at y = 9.6.
- All three portal approaches ground: west `(6, 58)`, east `(110, 58)`, north
  `(58, 100)`.
- **2809 of 2809 sampled columns ground successfully - zero misses** across the
  whole 208 m square on a 4 m grid, so no position exists where an actor would
  fall through to the manifest fallback height.

This test caught two real defects during development, both since fixed: terrain
quads wound clockwise from above, which made the ground simultaneously invisible
and transparent to the grounding ray, and an 18-column gap on the exact map
boundary line.

### Traversal

`sunmane_traversal.gd` exercises the client-side half of gameplay against the
package. Movement authorisation and map transitions belong to the server and are
not exercised; everything the client itself computes is.

- Server tile to world position and back round-trips exactly for all 900
  sampled tiles, and the arrival datum maps to the world origin.
- Click-to-move picking - a camera ray into the navigation layer, converted to a
  server tile exactly as `main.gd` does - succeeds at all 14 representative
  locations, and every picked point converts to an on-map tile.
- The camera stays above its focus ground across all 100 combinations of the
  isometric rig's pitch, yaw and zoom range.
- All 106 declared collision nodes produced bodies, and every probed structure
  presents the collision its form implies; open timber frames such as the
  lookout towers and the dock piles are deliberately walk-through.
- The world edge is raised rim or open water on 91 of 96 perimeter samples.
- All three portal approaches ground with standing headroom.
- Every server tile maps inside the minimap image, and the declared pixel
  transform matches the bounds and image size exactly.

This test found three real defects, all since fixed:

1. The west and east caravanserais stood exactly on their portal tiles, so an
   arriving player would have materialised inside the building. They now stand
   inboard, with the arrival point on the open road at the gate.
2. The cove landing, two outposts, two satellite camps, an outlying pen and
   several resource and population records sat west of Godot X -58 or south of
   Godot Z 58, which are server tiles below zero - addresses the server cannot
   express, so a player could never have walked to them. All are now inside the
   addressable band, which the manifest records explicitly as
   `coordinateTransform.addressableWorldBounds` and the package validator now
   asserts for every landmark, interactive and population record.
3. A herd and a boar spawn were likewise outside that band.

### Rendered views

`rendered_sunmane_steppe.gd` loads the package through the client's world
loader, applies the manifest environment through `WorldEnvironmentBinder`,
spawns the ambient livestock through `AmbientPopulation`, then captures 21
framings plus 4 golden-hour variants. Framings come from `camera-views.json`,
derived from the exported landmark positions using the client's own isometric
rig convention, so each is a view a player can reach in game. Each capture is
asserted to be the reference resolution and to contain at least 64 distinct
sampled colours, which fails loudly on a blank or single-material frame.

### Minimap

`sunmane_minimap.gd` renders orthographically from the exported geometry into a
1024 x 1024 SubViewport. The manifest records
`pixelsPerMetre = 4.923077` and an explicit
pixel transform. Spot-checking the transform against the rendered image: the
crossroads, the great hall and the eastern mesa all land on land pixels, and
both open-sea probes land on water pixels.

## Geometry integrity

`tools/sunmane/checks.py` runs inside the builder and fails the build on
malformed geometry. Every emitted primitive is checked for triangles wound
against their vertex normals, degenerate triangles, non-finite positions or
UVs, and non-unit normals; closed kit solids are additionally checked for
positive signed volume, which catches inside-out geometry that a winding check
alone cannot see. The current build emits zero of any of these.

## What is not verified here

- **No live server session.** `eloria-server` is not reachable from this
  workspace and neither is the development server the repository's
  `rendered-server-session` CI job uses, so the real login flow, protocol
  round-trip and server-side walkability were not exercised. Everything the
  client does with the package - manifest parse, GLB import, collision build,
  grounding raycast, environment binding, ambient population, minimap - was
  exercised directly. See `server-integration.md`.
- **No GPU.** All rendering was Mesa llvmpipe software rasterisation. Frame
  times are therefore not player frame rates; see `performance-summary.md`.
