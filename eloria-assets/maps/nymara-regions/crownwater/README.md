# Crownwater production map

The Nymara lagoon city, taken from its placeholder package to a production
runtime map at **576 m x 576 m, one metre per tile** (96x96 server ELM tiles).

Composition authority is
`eloria-assets/concepts/nymara-regions/crownwater_region_concept.png`. Player
scale was worked from the ten-panel detail board, which is **truncated on disk**
and was supplied to this session separately - see `comparison-report.md`, which
does not pretend otherwise.

## What is here

| File | What it is |
| --- | --- |
| `world.glb` | self-contained glTF 2.0, 23.4 MB, 587,106 unique / 1,271,396 instanced triangles |
| `world-lod2.glb` | reduced package, 14.0 MB, 42% smaller |
| `world.json` | schema-1 manifest: bounds, transform, spawns, collision, navigation, landmarks, interactives, NPC and creature markers, harvestables, portals, roads, water, environment, minimap, provenance |
| `collision.bin` | EWCG v1, 1152 x 1152 half-metre cells, 25.6% walkable |
| `minimap.webp` | rendered from the final geometry, not drawn |
| `camera-views.json` | 23 framings, emitted from `source/views.py` |
| `performance.json` | raw measurements written by the build |
| `references/captures/` | **real Godot 4.7.2 client frames**, not offline previews |
| `references/comparisons/` | aerial and panel comparison sheets, contact sheet |
| `source/` | the complete, reproducible build |

## Building it

```sh
cd source && python build_crownwater.py
python ../../_toolkit/verify_runtime.py --package ..
python make_sheets.py
```

Deterministic: the same seed reproduces the same bytes. Verified - two
independent runs produce byte-identical `world.glb`, `world-lod2.glb`,
`world.json`, `collision.bin`, `minimap.webp`, `camera-views.json` and
`performance.json`. The two `*.validator.json` files differ only in the
absolute path they record and their timestamp. The build imports the
shared toolkit at `maps/nymara-regions/_toolkit/` and **modifies nothing in it**.

Real client captures (needs a Godot 4.7.2 binary and a display):

```sh
ELORIA_ARTIFACT_DIR=<dir> godot --audio-driver Dummy \
  --rendering-method gl_compatibility --path godot-client \
  --script res://tests/integration/rendered_crownwater.gd
```

## Verification

| Check | Result |
| --- | --- |
| `validate_gltf.py` on `world.glb` | **0 errors, 0 warnings** |
| `validate_gltf.py` on `world-lod2.glb` | **0 errors, 0 warnings** |
| `verify_runtime.py` | **0 errors**, 2 documented warnings |
| Grounding-ray misses | **0** across all 331,776 reachable server tiles |
| Loads through the real `world_loader.gd` | **yes** - 23/23 captures pass |

See `validation-report.md` for what those numbers do and do not cover, and
`modeling-assumptions.md` for the decisions a reviewer may want to overrule.

## Interiors

Four interiors open off this map: The Drowned Crown (under the basilica), The
Tide Cistern (under the garden islet), The Harbour Customs Hall and The Tide
Campanile. Built by `source/build_interiors.py`, verified by
`source/verify_interiors.py`, documented in
`../interiors/CROWNWATER_INTERIORS.md`.

## Server

Crownwater needs a bigger server map, as Amberwood does.
`../source-elm/crownwater.elm` is regenerated to 96x96 tiles / 576x576 height
cells from this build's own collision grid and must be loaded server-side. The
matching generator and contract-test change is on the `eloria-server` branch
`feature/crownwater-96-server-map`.
