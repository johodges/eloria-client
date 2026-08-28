# Amethyst Barrens production map

A 576 m × 576 m Nymara region: a storm-scoured crystal basin under permanent
cloud, with the Glasswarden Observatory on its terrace in the north-west, a
crystal massif erupting from the northern uplands, mountains closing the north
and west, and the sea biting into the north-east and south-east corners.

| | |
| --- | --- |
| Extent | 576 m × 576 m, one metre per server tile |
| Server map | 96 × 96 ELM tiles (576 × 576 collision cells) |
| Arrival datum | server tile (174, 174) → Godot origin, ground 5.2 m |
| `world.glb` | 19.53 MB, 887 nodes, 444,492 unique / 601,200 instanced triangles |
| `collision.bin` | 1152 × 1152 at 0.5 m, 81.3% walkable |
| Landmarks | 47 |
| Status | `production-geometry-materials-population` |

## Contents

```
world.glb                 self-contained glTF 2.0, no extensions, no external files
world.json                world manifest, schema version 1
collision.bin             half-metre walkability grid (EWCG v1)
minimap.webp              rendered from the final geometry, north-up
world.glb.validator.json  glTF validator report (0 errors, 0 warnings)
references/
  00-concept-detail-board.png    ten-panel board, player-scale authority
  01-concept-aerial-overview.png aerial concept, composition authority
  captures/                      offline preview renders (NOT client frames)
  client-captures/               real Godot 4.7.2 frames through WorldLoader
  comparisons/                   concept-to-build sheets
source/                   the region build; see source/README.md
```

## Building

```bash
cd source && python build_amethyst.py
```

Deterministic: two independent processes produce byte-identical `world.glb`,
`world.json`, `collision.bin` and `minimap.webp`. The only file that differs
between runs is `world.glb.validator.json`, which records its own absolute path
and a timestamp.

The shared authoring toolkit lives at `../_toolkit/` and is imported, not
copied. Region-specific code is `source/region.py` (extent, anchors, routes,
watercourses, terrain), `source/populate.py` (placement passes) and
`source/views.py` (cameras, panel mapping and this region's capture lighting).

## Verification

```bash
PYTHONPATH=../_toolkit python ../_toolkit/validate_gltf.py world.glb
PYTHONPATH=../_toolkit python ../_toolkit/verify_runtime.py
```

- `validate_gltf.py`: **0 errors, 0 warnings**
- `verify_runtime.py`: **0 errors**, 331,776 tiles sampled, **0 grounding
  misses**, one warning for 73 cliff-and-bridge height discontinuities

See `validation-report.md` for the full record and `comparison-report.md` for
what does and does not match the concept.

## Server side

The region needs the regenerated 96 × 96 ELM at
`../source-elm/amethyst_barrens.elm`, written by
`../_toolkit/export_source_elm.py` from the same terrain the GLB is built from.
The matching server change is on `feature/amethyst-barrens-576m-server-map` in
`eloria-server`. The client registry records this under `requiresServerMap`.

Height bytes follow the convention the client already uses,
`elevation_metres = height_byte * 0.2 - 2.2`, with zero meaning blocked. The
basin is authored to sit inside that six-bit band on purpose, so the server gets
real elevation rather than a saturated plateau — 52 distinct height bytes with
8% saturated, against Amberwood's near-total saturation.
