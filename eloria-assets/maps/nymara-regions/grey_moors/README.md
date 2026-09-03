# Grey Moors

A drowned burial moor: sodden black peat and olive moor-grass under permanent
overcast, standing stones and turf barrows over the whole of it, boardwalks and
laid causeways across the bog, broken towers on the skyline, and a bay biting
into the south-west corner.

Production package. 576 m x 576 m at one metre per tile, on the server's 96x96
ELM grid, with the arrival datum at server (174, 174) — the same extent every
other production Nymara region uses.

| | |
| --- | --- |
| status | `production-geometry-materials-population` |
| extent | 576 m x 576 m, 1 m per tile, `serverCells` 576 |
| arrival datum | server (174, 174) = Godot origin |
| unique triangles | 352,170 |
| instanced triangles | 662,590 (2.00 per m²) |
| nodes | 7,288 |
| `world.glb` | 22.89 MB, self-contained, no glTF extensions |
| `world-lod2.glb` | 12.49 MB, 314,680 instanced triangles |
| validator | 0 errors, 0 warnings |
| runtime verifier | 0 errors, 0 grounding misses across all 331,776 server tiles |

## Layout

```
grey_moors/
  world.glb                     self-contained glTF 2.0: geometry, materials, textures
  world-lod2.glb                reduced package for distance
  world.json                    manifest, schema version 1
  collision.bin                 EWCG v1, 1152 x 1152 half-metre cells
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
python3 build_grey_moors.py                    # world.glb, world.json, collision.bin, minimap, lod2
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
