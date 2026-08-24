# Nymara production asset manifest

## Runtime contracts

- Client maps: 27 ELM files: six bootstrap, twelve Nymara exteriors, seven
  Nymara interiors, `nomap.elm`, and `newcharactermap.elm`.
- Server-authoritative maps: 25; the two client-only maps are excluded.
- Four Gates arrival and respawn datum: `(58,58)` on visible walkable terrain.
- Exterior border transitions: west `(6,58)`, east `(110,58)`; interior entrance
  `(58,100)`.
- Local maps: one 512x512 RGBA DDS with four mip levels per Nymara exterior and
  interior.  Continent overview: `maps/nymara_continent.dds`.

## Exterior concepts and runtime composition

All twelve exterior regions now use dedicated placement, terrain, elevation,
lighting, and validation logic. The generator intentionally fails if an
exterior reaches the generic composition path. Each region has committed
concept-comparison, overhead, and representative topology QA under
`eloria-assets/qa/regions/`.

| Region | Authoritative concept | Primary runtime kit | Landmark and terrain direction |
|---|---|---|---|
| Mirrorhold | `mirrorhold_region_concept.png` | Glasswarden observatory and Mirrorhold canals | Alpine citadel, reflective pools, switchback roads |
| Crownwater | `crownwater_region_concept.png` | Crownwater ferries and Mirrorhold bridges | Turquoise island capital and causeways |
| Four Gates | `four_gates_region_concept.png` | Gatehouses, radial bridges, civic towers, segmented walls, fountains and park belt | Fortified circular civic island, four monumental approaches, concentric districts, turquoise waterways and unobstructed central arrival plaza |
| Whitehorn Range | `whitehorn_range_region_concept.png` | Glacier, monastery, rope bridge | Glacial valley, caves, passes and temple approach |
| Amethyst Barrens | `amethyst_barrens_region_concept.png` | Crystal bridges, geodes and observatory | Violet badlands and celestial instrument |
| Sunmane Steppe | `sunmane_steppe_region_concept.png` | Orun tents and Sunmane camps | Rider roads, circular tent city and watering holes |
| Amberwood | `amberwood_region_concept.png` | Estate, lodge, ruins and autumn trees | Layered autumn forest and overgrown estate |
| Grey Moors | `grey_moors_region_concept.png` | Barrows, boardwalks and standing stones | Heather, peat bogs and readable causeways |
| Westhaven | `westhaven_region_concept.png` | Harbor, shipyard, lighthouse and seawalls | Dense maritime city and rocky coast |
| Verdant Stair | `verdant_stair_region_concept.png` | Terraces, vine bridges and water shrines | Jungle limestone stairs and waterfalls |
| Ssarathi Ruins | `ssarathi_ruins_region_concept.png` | Temple, archive gate and ritual pools | Flooded processional city and serpent ruins |
| Manymouth Delta | `manymouth_delta_region_concept.png` | Stilt houses, docks and mangroves | Braided channels and flooded-labyrinth approach |

## Exterior completion inventory

| Region | Authored layout | Dedicated terrain | Exact validation | QA directory |
|---|---:|---:|---:|---|
| Mirrorhold | Yes | Yes | Yes | `qa/regions/mirrorhold/` |
| Crownwater | Yes | Yes | Yes | `qa/regions/crownwater/` |
| Four Gates | Yes | Yes | Yes | `qa/four-gates/` |
| Whitehorn Range | Yes | Yes | Yes | `qa/regions/whitehorn-range/` |
| Amethyst Barrens | Yes | Yes | Yes | `qa/regions/amethyst-barrens/` |
| Sunmane Steppe | Yes | Yes | Yes | `qa/regions/sunmane-steppe/` |
| Amberwood | Yes | Yes | Yes | `qa/regions/amberwood/` |
| Grey Moors | Yes | Yes | Yes | `qa/regions/grey-moors/` |
| Westhaven | Yes | Yes | Yes | `qa/regions/westhaven/` |
| Verdant Stair | Yes | Yes | Yes | `qa/regions/verdant-stair/` |
| Ssarthi Ruins | Yes | Yes | Yes | `qa/regions/ssarathi-ruins/` |
| Manymouth Delta | Yes | Yes | Yes | `qa/regions/manymouth-delta/` |

## Style guide

- Polished, readable stylized fantasy; restrained polygon budgets and no
  photorealistic material mismatch.
- Regional silhouettes and palettes follow the corresponding concept, while
  roads and portal corridors remain visually obvious.
- Shared materials use consistent scale: terrain detail reads at player scale,
  landmark texture contrast reads at map scale.
- Fog is atmospheric rather than opaque.  Every configured fog key includes an
  alpha/density value.
- All assets are original Eloria project work under CC-BY-4.0.

## Four Gates vertical slice

- The ELM composition is centred on the authoritative `(58,58)` arrival rather
  than the geometric centre of the 192x192 collision field.
- Four gatehouses and four radial bridges establish the cardinal approaches.
- Twelve wall segments, eight civic towers, public fountains, ward pavilions
  and a landscaped park belt reproduce the concept's fortified island skyline.
- The terrain contains a complete river ring, dry causeways, ring roads and
  gently terraced outer highlands while preserving portal corridors.
- `maps/nymara/four_gates.dds` is purpose-built cartography with landmark
  symbols, district labels, roads, water and four gates; it is not a resized
  copy of the concept painting.

## Regeneration and validation

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

The validator checks the exact map count, ELM sections and dependencies,
Cal3D skeleton/mesh/animation contracts, customization DDS layouts, all local
map DDS files, the continent overview, and all `mapinfo.lst` references.
