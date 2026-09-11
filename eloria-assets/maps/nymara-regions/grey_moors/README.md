# Grey Moors

A drowned burial moor: sodden black peat and olive moor-grass under permanent
overcast, standing stones and turf barrows over the whole of it, boardwalks and
laid causeways across the bog, broken towers on the skyline, and a bay biting
into the south-west corner.

Current inhabited-landscape package: **384 m � 384 m**, one metre per tile,
with server origin **(116,116)**. The peat refuge and Great Barrow crown retain
full dimensions while the journeys between them shorten. See
[landscape-redesign.md](landscape-redesign.md) for authored geography and rebuild order.

| Contract | Current result |
| --- | --- |
| exterior extent | 384 � 384 server tiles |
| half-metre collision | 768 � 768, 92.0% walkable |
| full package | 33.29 MB |
| instanced triangles including hidden receiving-scene view | 706,047 |
| GLB validator | 0 errors, 0 warnings |
| runtime grounding | 147,456 tiles, 0 misses, 0 errors, 0 warnings |
| preserved content | 11 portals, 15 exterior secrets, 72 landmarks |

## Layout

```
grey_moors/
  world.glb                     self-contained glTF 2.0: geometry, materials, textures
  world-lod2.glb                reduced package for distance
  world.json                    manifest, schema version 1
  collision.bin                 EWCG v2, 768 x 768 half-metre cells
  minimap.webp                  rendered from the final geometry, not drawn
  verification-report.json      verify_runtime.py output
  world.glb.validator.json      validate_gltf.py output
  world-lod2.glb.validator.json
  source/                       the build; reproducible, never run at startup
  references/
    00-concept-detail-board.png the ten-panel board: player-scale authority
    01-concept-aerial-overview.png the aerial: composition authority
    captures/                   offline preview renders (NOT client frames)
    client-captures/            real Godot 4.7.2 frames through WorldLoader
    comparisons/                panel, aerial and landmark contact sheets
```

## Building it

The shared toolkit lives at `maps/nymara-regions/_toolkit/` and is imported,
not copied.

```sh
cd grey_moors/source
python3 rebuild_landscape.py                  # geometry, minimap, lod2, collision correction and verification
python3 ../../_toolkit/validate_gltf.py ../world.glb
python3 ../../_toolkit/verify_runtime.py --report ../verification-report.json
python3 ../../_toolkit/export_server_collision.py    # writes ../server-collision/grey_moors.bin
python3 ../../_toolkit/capture_views.py
python3 ../../_toolkit/make_comparison.py
```

Real client frames need a Godot 4 binary and a GPU:

```sh
cd godot-client
Godot_v4.7.2-stable_win64_console.exe --path . \
  --script ../eloria-assets/maps/nymara-regions/_toolkit/godot_capture.gd \
  --rendering-driver vulkan --resolution 1600x1000 -- \
  --package=<abs path to this package> --out=<abs path to client-captures>
```

The build is seeded and deterministic: the same seed reproduces the same bytes.
Nothing at runtime depends on rerunning it.

## What is region and what is toolkit

`source/` holds only what makes this map: `region.py` (extents, anchors, routes,
terrain sculpting, surface painting), `populate.py` (placement passes),
`views.py` (the camera set and the board panel mapping) and
`build_grey_moors.py`.

Everything else is shared. This region added to the toolkit rather than forking
it — four surface classes and a worn-track class in `terrain.py`, fourteen
`grey_`-prefixed material recipes in `textures.py`, their specs in
`materials.py`, and a new `moorcraft.py` kit. See `modeling-assumptions.md`.

## Read these too

- `modeling-assumptions.md` — every decision that is an assumption, and why
- `validation-report.md` — what was checked, what passed, what was not checked
- `comparison-report.md` — the build graded against all ten panels and the aerial
- `coverage-map.md` — what stands where
- `performance-summary.md` — budgets and the real numbers
- `change-log.md` — what changed from the placeholder, and the defects fixed
