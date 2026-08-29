# Ssarathi Ruins production map package

Ssarathi Ruins is the drowned serpent city of Nymara: a flooded jungle basin
holding the remains of a jade-and-gold city, its causeways standing a metre or
two out of shallow turquoise water, its temple on the northern axis, and
waterfalls coming off the valley wall behind it.

The region is authored at **576 m x 576 m** on a 96 x 96-tile server map at one
metre per tile, matching Amberwood, Mirrorhold, Whitehorn Range, Amethyst
Barrens and Crownwater.

This directory is the runtime package plus everything needed to rebuild it.

## Runtime files

| File | What it is |
| --- | --- |
| `world.glb` | Self-contained glTF 2.0 scene: geometry, materials and every texture embedded. No external files, no glTF extensions. |
| `world.json` | GLB world manifest, schema version 1 — bounds, coordinate transform, spawns, collision and navigation declarations, landmarks, interactives, NPC and creature markers, harvestables, portals, roads, water, environment, minimap transform, provenance. |
| `world-lod2.glb` | Reduced package: far-tier vegetation only, no ground clutter, half-resolution textures. |
| `collision.bin` | Half-metre walkability grid, `EWCG` version 1, 1152 x 1152 cells over the server footprint. |
| `minimap.webp` | North-up minimap rendered from the final geometry, not drawn by hand. |
| `camera-views.json` | The camera set, emitted from `source/views.py`, shared by the offline preview renderer and the in-engine capture harness. |
| `world.glb.validator.json` | glTF 2.0 validation report. |
| `client-check-report.json` | Grounding verified **in Godot 4.7.2**, through the project's own `WorldLoader` and `main.gd`'s grounding ray. |
| `performance-summary.md` | Triangle, node, texture and package budgets. |

## Source

`source/` holds this region's composition and its build entry point. The shared
authoring toolkit it calls lives in `../_toolkit/` and is not modified by this
region — the twelve material recipes, the two tree species and the
architectural kit are all registered into the shared tables at build time.

```sh
cd source
python3 build_ssarathi.py                        # writes the package one dir up
python3 ../../_toolkit/verify_runtime.py --package ..
python3 ../../_toolkit/validate_gltf.py ../world.glb
python3 ../../_toolkit/export_source_elm.py      # regenerates the 96x96 server ELM
python3 ../../_toolkit/capture_views.py          # offline comparison captures
python3 ../../_toolkit/compress_captures.py      # PNG -> WebP
python3 ../../_toolkit/make_comparison.py        # concept/build comparison sheets
```

| Module | What it is |
| --- | --- |
| `region.py` | Extents, datums, anchors, street and channel routes, terrain sculpting, and the massing pass that fills the quarters between the streets. |
| `ssarathikit.py` | Twelve procedural material recipes and the build-time registrar. |
| `ssaratharch.py` | The architectural kit: temple, vault portal, serpent columns, stela, bridges, colonnades, towers, ruin blocks, docks, shrines, palms. |
| `populate.py` | Placement passes, in the order the production guide prescribes. |
| `views.py` | The camera set, the detail-board panel mapping, and this region's capture lighting. |
| `build_ssarathi.py` | The build: GLB export, collision grid, minimap, manifest, validation. |

The build is deterministic: a cache-cold rebuild reproduces every artefact
byte-for-byte, verified by building twice from a cleared texture cache. Runtime
startup never depends on rerunning it — the committed artefacts load directly.

## Coordinates

Right-handed, metres, Y up, north toward `-Z`. The server's 576-cell grid maps
at one metre per tile with the arrival datum at server `(174, 174)`:

```
godot_x = server_x - 174        godot_z = 174 - server_y
```

so the reachable footprint is `x ∈ [-174, 401]`, `z ∈ [-401, 174]`. Terrain is
cut 30 m larger on every side and the surplus is raised into jungle-clad valley
walls, so a character cannot reach an unfinished void.

**This needs a matching server map.** `../source-elm/ssarathi_ruins.elm` is
regenerated here at 96 x 96 tiles (576 x 576 height cells) with real elevation
and walkability, replacing the flat 32 x 32 placeholder. The server-side change
is `johodges/eloria-server` branch `feature/ssarathi-ruins-576m-server-map`; the
two must land together, because this manifest declares `serverOrigin [174, 174]`
and without the server change the region's two maps disagree on both size and
datum. Note that the server still generates its own procedural heights and does
not consume this ELM — see `modeling-assumptions.md`.

## Navigation contract

The Godot client turns every `MeshInstance3D` whose name begins with an entry in
`navigation.surfaceNodePrefixes` into collision on its navigation layer, then
grounds actors with a downward ray. This package uses two prefixes:

* `Terrain_` — the five terrain surface classes (`JadePaving`, `MossStone`,
  `JungleFloor`, `Silt`, `Rock`).
* `Walk_` — authored walkable decks only: the seven channel bridges, the eight
  timber dock jetties, the temple's five stair flights and its summit floor, the
  vault threshold, the stela plinth and the shrine steps. Twenty-four in total.

**Almost all of Ssarathi's walkable ground is terrain, not deck.** The
causeways are stone embankments raised out of the basin floor, so they are part
of the heightfield; only genuine spans over carved water are `Walk_` geometry.
That is the opposite balance from Crownwater and it is deliberate — see
`modeling-assumptions.md`.

Structural geometry is never a walk surface, so the grounding ray cannot snap a
character onto a cornice, a roof or the top of an arch.

`verify_runtime.py` casts that exact ray at all 331,776 reachable server tiles
and reports **zero misses**. Godot 4.7.2, loading the package through the real
`WorldLoader`, agrees: **zero misses** across 20,736 sampled tiles, with all
three spawns within 0.06 m of their manifest heights.
