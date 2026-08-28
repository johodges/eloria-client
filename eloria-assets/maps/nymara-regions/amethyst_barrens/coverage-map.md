# Amethyst Barrens — coverage map

What exists where, in Godot metres. North is −Z. Server tile (174, 174) is the
Godot origin; the playable footprint is x ∈ [−174, 401], z ∈ [−401, 174].

## Landmarks — 47

| Type | Count | Spread (x) | Spread (z) |
| --- | --- | --- | --- |
| `civic` — the Glasswarden Observatory | 1 | −78 | −204 |
| `bridge` — Amethyst Crystal Bridge | 7 | −90 … 285 | −270 … 24 |
| `cave` — Amethyst Geode Cave | 4 | −114 … 318 | −306 … 114 |
| `phenomenon` — Amethyst Levitating Shards | 8 | −138 … 354 | −330 … 120 |
| `ruin` — Amethyst Storm Ruin | 6 | −114 … 282 | −288 … 66 |
| `diggings` — Resonant Crystal Cluster | 10 | −90 … 342 | −234 … 90 |
| `camp` — Glasswarden Field Station | 6 | −24 … 324 | −252 … 102 |
| `tower` — Glasswarden Watchtower | 3 | −156 … 360 | −252 … 138 |
| `monument` — The Resonance Ring | 1 | 306 | 96 |
| `natural` — The Amethyst Massif | 1 | 168 | −330 |

Every quadrant carries landmarks; nothing is clustered into one corner. The
sparsest area is the far south-west, which the concept also leaves as open
plain.

## Ground surface classes

| Class | Material | Share |
| --- | --- | --- |
| `Barrens` | `amethyst_barrens_dust` | dominant — the basin floor |
| `StormRock` | `amethyst_storm_rock` | ridges, steep ground, the massif |
| `CrystalField` | `amethyst_crystal_field` | massif skirt, digging floors, shard sites, river banks |
| `ResonantRoad` | `amethyst_resonant_road` | the ten roads and the arrival apron |
| `Shore` | `shore_shingle` | the two sea corners and the shallows |
| `Paving` | `cobble_paving` | the observatory forecourt only |

## Routes — 10

`arrival_road`, `observatory_approach`, `massif_road`, `basin_road`,
`east_road`, `south_road`, `coast_road`, `west_road`, `overlook_track`,
`north_track`.

The web meets at the observatory gate, the basin diggings and the eastern
ruins, as the aerial shows. `overlook_track` and `north_track` are worn barrens
rather than laid roadway.

## Water

- `Water_Sea` — one plane covering both the north-east bay and the south-east
  inlet, clipped to ground below sea level, running past the coast to the
  horizon.
- `Water_RiverResonant` — the main river, north mountains to the south-east sea.
- `Water_RiverBeck` — the north-west tributary.

## Spawns — 3

| id | server tile | lands on |
| --- | --- | --- |
| `default` | (174, 174) | `ResonantRoad` — the arrival apron |
| `observatory` | (102, 318) | `Paving` — the forecourt |
| `massif-camp` | (306, 426) | `CrystalField` |

All three are grounded; `verify_runtime.py` confirms each lands on a walk
surface.

## Portals — 5

| id | kind | destination |
| --- | --- | --- |
| `west-road` | map transition | `maps/nymara/amberwood.elm` |
| `north-pass` | map transition | `maps/nymara/whitehorn_range.elm` |
| `east-shore` | map transition | `maps/nymara/crownwater.elm` |
| `south-road` | map transition | `maps/nymara/sunmane_steppe.elm` |
| `resonant-vault-stair` | interior entrance | `maps/nymara/resonant_vault.elm` |

Neighbour assignments are inferred from the Nymara region layout and the
server's map table. **They are not verified against a canonical adjacency
map** — `source-elm/regions-connections.json` exists and was not reconciled
against these. The server is authoritative for transitions regardless.

## Server-owned metadata

Editor and visual markers only; nothing dynamic is baked into the mesh. All
carry `"authority": "server"`.

- 15 NPC markers — 10 named roles, 5 creature zones
- 6 interactives — one assay bench per field station
- 64 harvestables — `amethyst-shard` seams scattered over the crystal fields

## Environment zones — 5

`barrens-core`, `massif`, `observatory`, `coast`, `south`. Used for the storm
flashes, crystal glow, dust and ambient audio declared in `world.json`.

## Captures — 30 cameras

Ten map to detail-board panels 1–10. One aerial. Sixteen supporting views
covering the massif, the observatory court, arrival, both coasts, the stone
ring, the eastern watchtower, the river, the south road, the ruin basin, the
massif foot, the northern geode, the west road, spawn grounding, a bridge deck
and the observatory deck. Three storm-light variants.

Rendered twice: offline in `references/captures/`, and through the real client
loader in `references/client-captures/`.
