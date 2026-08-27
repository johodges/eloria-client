# Sunmane Steppe - production region package

The Sunmane Steppe is the Orun horse culture's grassland: four clan camps ring a
shared seasonal market at a ceremonial crossroads, caravanserais guard the
travel axes, and windmills, wells, animal pens, banner shrines and burial mounds
carry the wider pastoral landscape out to a rugged western coast.

This package replaces the earlier starter conversion, which carried landmark
silhouettes borrowed from other regions' name-spaces and no authored
architecture.

## Runtime files

| File | Purpose |
|---|---|
| `world.glb` | Self-contained glTF 2.0 region: terrain, water, architecture, props, vegetation, embedded PBR textures |
| `world.json` | Schema 1.1 manifest: bounds, coordinate transform, spawn points, collision, navigation, landmarks, interactives, environment, population, minimap transform |
| `world-lod2.glb` / `world-lod2.json` | Reduced package for low-end settings: ground clutter and road dressing removed, textures at half resolution |
| `minimap.webp`, `full-map.webp` | Rendered orthographically from `world.glb` through the client's own world loader |
| `camera-views.json` | Reproducible client camera framings, derived from the exported landmark positions |
| `textures/` | The authored PBR kit as editable source; the same maps are embedded in the GLB |
| `references/` | Aerial overview and the ten-panel detail board, the visual authority for the region |
| `comparison/` | Concept-versus-client sheets, one per reference panel |

Nothing at runtime depends on rerunning the build: the committed GLB, manifest
and minimap load directly.

## Region frame

| Property | Value |
|---|---|
| Server arrival datum | `(58, 58)` -> Godot `(0, 0)` |
| Metres per server tile | 1.0 |
| World span | 208 m x 208 m |
| Elevation range | -20.5 m to 46.17 m |
| North axis | `-Z` |
| West walk portal | server `(6, 58)` |
| East walk portal | server `(110, 58)` |
| North interior entrance | server `(58, 100)` (Ssarathi Royal Archive) |

## Landmark inventory

The counts the written region description specifies are asserted by
`tools/sunmane/validate_package.py`.

| Landmark | Count |
|---|---:|
| animal-pen | 6 |
| banner-shrine | 8 |
| bridge | 3 |
| burial-mound | 6 |
| caravanserai | 4 |
| gate | 4 |
| great-hall | 1 |
| landing | 1 |
| outpost | 5 |
| round-tent | 12 |
| seasonal-market | 4 |
| standing-stones | 13 |
| well | 4 |
| windmill | 6 |

Ambient livestock: 84
animals across 15 groups, instanced by
the client's ambient population system rather than baked into the world mesh.
Server-owned NPCs, harvestables and creature spawns are recorded under
`runtimePopulation` for the matching server profile.

## Rebuilding

```sh
python3 eloria-assets/tools/sunmane/build.py                 # world.glb + world.json
python3 eloria-assets/tools/sunmane/build.py --lod 2         # world-lod2.glb
python3 eloria-assets/tools/sunmane/creatures.py             # steppe horses
python3 eloria-assets/tools/sunmane/views.py                 # camera-views.json
python3 eloria-assets/tools/sunmane/validate_package.py      # package checks

godot --headless --path godot-client --script res://tests/integration/sunmane_grounding.gd
xvfb-run -a godot --display-driver x11 --rendering-method gl_compatibility \
  --path godot-client --script res://tests/integration/sunmane_minimap.gd
xvfb-run -a godot --display-driver x11 --rendering-method gl_compatibility \
  --path godot-client --script res://tests/integration/rendered_sunmane_steppe.gd
python3 eloria-assets/tools/sunmane/comparison.py            # comparison sheets
```

All geometry, textures and creature assets in this package are original Eloria
project work under CC-BY-4.0. No third-party asset packs and no Eternal Lands
assets were used, converted or traced.
