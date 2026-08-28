# Mirrorhold change log

## Production pass — 576 m region

Branch: `feature/mirrorhold-production-glb-map` (client),
`feature/mirrorhold-576m-server-map` (server).

### Replaced

The whole package. The previous one was the shared placeholder generator's
output and carried the defects section 3 of the region production guide lists,
all of which were confirmed here before anything was built:

- **The terrain was flat.** `Terrain_ELM_Authority` was y = 0.0 everywhere over
  a ±96 m extent, and `production-index.json` recorded
  `terrainHeightRange: [0.0, 0.0]`.
- **Twelve of nineteen landmark names belonged to other regions**: Amberwood
  Hollow Tree, Grey Moor Ritual Shrine, Manymouth Tidal Waystone, Ssarathi Ruin
  Arch, Sunmane Burial Mound, Sunmane Caravan Camp, Verdant Water Shrine,
  Westhaven Harbor Crane, Westhaven Lighthouse, Westhaven Sea Cave, Whitehorn
  Glacier. Only seven of the fifty-four instances were Mirrorhold's own. None
  of it was preserved.
- **`source-elm/mirrorhold.elm` was a 32x32 flat placeholder** at height 11.
- **`references/00-concept-detail-board.png` is truncated** to 786,446 bytes;
  only its top row of five panels decodes. Still true in this commit — see
  `validation-report.md`.
- The `textures/` directory of loose region maps is gone; the package embeds
  its textures in the GLB.

### Added

- 576 m x 576 m terrain: a mountain massif rising north, two glacier cirques,
  a lake basin in the south, stamped civic terraces, four graded roads and
  three watercourses. Relief 0 to about 195 m.
- The citadel: orrery and armillary, high and great courts, gate wall and
  wings, rose gallery, two lens towers, mirror basins.
- The civic descent: fountain plaza, canal terraces, aqueduct, north overlook,
  the stair town in five shelves, the east stair, retaining walls along the
  switchbacks, eight cliff waterfalls.
- The lake: the ring and four causeways, the north quay with three docks and
  boats, two islets, the south watch.
- Eighteen satellite sites, an alpine spruce belt, and road, harbour and
  terrace dressing.
- 31 landmarks, 8 interactives, 18 NPC and creature markers, 38 harvestables,
  6 portals, 3 spawns.
- `source/` in full, and a regenerated 96x96 `source-elm/mirrorhold.elm`.

### Shared toolkit

Changes made in `../_toolkit/` for this region, all additive:

- `noise.stable_hash()` and its five call sites — the build was not
  deterministic, because seeds were derived from Python's salted `hash()`.
- `preview.py`'s texture cache keyed on a digest of the recipe sources, and
  moved off a hardcoded `/tmp` that Windows resolves to `C:\tmp`. Before this,
  a stale cache silently shipped textures that no longer matched the source.
- `regionbuild.py`: `Placement` and `RegionBuild` moved out of
  `amberwood/region.py` and re-exported.
- `regionpaths.py`: region package, plan, build-module and views resolution, so
  the relocated scripts stop assuming they live inside one region.
- `terrain.build_meshes(materials=...)`: per-region surface-class materials.
- Terrain surface classes `SNOW=7`, `ICE=8`, `MARBLE=9`, `TURF=10`, appended.
- Texture recipes: `snow_pack`, `glacier_ice`, `blue_crystal`,
  `veined_marble`, `pale_ashlar`, `gilt_brass`, `slate_roof`, `alpine_turf`,
  a `lake` tone for `water_surface`, and a `mirror_glass` material.
- `terrain.backdrop(open_side=, clip_interior=)`: the mask could never exclude
  the interior, because the distance it tested is clamped at zero. Harmless on
  a map whose border is lower than its middle, which is why Amberwood never
  showed it; on Mirrorhold the coarse backdrop sheet poked up through the
  slopes as scattered white patches. The old behaviour is still the default.
- `godot_capture.gd`: renders a package's camera set through Godot itself.
- Material sets are now pinned per region, so a recipe added for one region
  cannot change another region's GLB.

### Known defects fixed during the pass

- `Placement.walk_surface=True` on a `MeshGroup` prefixed every part of the
  group with `Walk_`, making roofs and domes walk surfaces. Walk-surface nodes
  dropped from 81 to 28 when corrected.
- The gate wall and the rose gallery were placed inside the citadel court's
  footprint.
- The snow line at 104 m put snow across the civic terraces.
- The orrery's dome hid the armillary it was built to display.
