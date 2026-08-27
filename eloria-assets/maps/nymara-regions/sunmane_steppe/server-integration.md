# Sunmane Steppe - server integration

Everything in this document is server-side work that this client change does
**not** perform. The client change is self-contained and does not alter the
network protocol or any gameplay behaviour; the region loads and is traversable
with the server exactly as it is today.

`eloria-server` was not reachable from the workspace this package was built in,
so none of the records below could be committed there. They are written out in
full so the matching server pull request is transcription rather than redesign.

## Hooks

The region's hook names come from
`maps/nymara-regions/source-elm/regions-connections.json` and are unchanged:

| Hook | Name |
|---|---|
| npc | `npcs.nymara.sunmane_steppe` |
| spawn | `spawns.nymara.sunmane_steppe` |
| hazard | `hazards.nymara.sunmane_steppe` |
| harvest | `harvest.nymara.sunmane_steppe` |

## Map registration

| Property | Value |
|---|---|
| Server map id | `maps/nymara/sunmane_steppe.elm` |
| Arrival datum | `(58, 58)` |
| Walk portal west | `(6, 58)` from Amethyst Barrens `(110, 58)` |
| Walk portal east | `(110, 58)` to Amberwood `(6, 58)` |
| Interior entrance | `(58, 100)` to Ssarathi Royal Archive `(58, 10)` |

These are the coordinates already recorded in `regions-connections.json`; the
client map is built around them rather than proposing new ones.

## Safe spawn surfaces

The client grounds actors by raycasting the navigation surface, and every
sampled column in the region grounds successfully, so any walkable tile is a
safe spawn. The four positions the manifest names explicitly:

| Spawn id | Server tile | Note |
|---|---|---|
| `arrival-datum` | `(58, 58)` | ceremonial crossroads at the shared market |
| `west-caravanserai` | `(6, 58)` | arrival from Amethyst Barrens |
| `east-caravanserai` | `(110, 58)` | departure toward Amberwood |
| `north-barrowfield` | `(58, 100)` | Ssarathi Royal Archive entrance approach |

## NPC posts (10)

| Id | Label | Role | Server tile |
|---|---|---|---|
| `khan-of-the-sunmane` | Orun khan | quest | `(58, 60)` |
| `market-broker` | Seasonal market broker | trade | `(50, 48)` |
| `horse-master` | Camp horse master | trade | `(28, 92)` |
| `caravan-master-west` | West caravan master | travel | `(6, 54)` |
| `caravan-master-east` | East caravan master | travel | `(110, 54)` |
| `shrine-keeper` | Banner shrine keeper | quest | `(33, 92)` |
| `miller` | Steppe miller | trade | `(102, 25)` |
| `well-keeper` | Crossroads well keeper | service | `(58, 37)` |
| `barrow-warden` | Barrow warden | quest | `(58, 96)` |
| `cove-factor` | Cove landing factor | trade | `(-14, 5)` |

## Harvestable resources (12)

| Id | Label | Kind | Server tile |
|---|---|---|---|
| `sunmane-wheat-00` | Sunmane wheat | crop | `(92, 28)` |
| `sunmane-wheat-01` | Sunmane wheat | crop | `(24, 104)` |
| `sunmane-wheat-02` | Sunmane wheat | crop | `(110, 14)` |
| `sunmane-wheat-03` | Sunmane wheat | crop | `(6, 36)` |
| `sunmane-wheat-04` | Sunmane wheat | crop | `(80, 116)` |
| `steppe-herbs-00` | Steppe herbs | herb | `(0, 78)` |
| `steppe-herbs-01` | Steppe herbs | herb | `(120, 98)` |
| `steppe-herbs-02` | Steppe herbs | herb | `(34, 0)` |
| `shore-clay-00` | Shore clay | mineral | `(-16, 10)` |
| `shore-clay-01` | Shore clay | mineral | `(-12, 104)` |
| `mesa-flint-00` | Mesa flint | mineral | `(38, 132)` |
| `mesa-flint-01` | Mesa flint | mineral | `(118, 120)` |

## Hostile creature spawns (6)

All models below already exist in the client's creature catalogue.

| Model | Area | Count | Radius | Server tile |
|---|---|---:|---:|---|
| `dire_wolf` | north mesa breaks | 3 | 10.0 m | `(28, 126)` |
| `dire_wolf` | eastern breaks | 3 | 10.0 m | `(132, 92)` |
| `wild_boar` | south-west scrub | 4 | 11.0 m | `(2, -2)` |
| `red_fox` | open steppe | 4 | 14.0 m | `(88, 108)` |
| `elk` | northern pasture | 4 | 12.0 m | `(6, 108)` |
| `mountain_goat` | coastal cliffs | 3 | 9.0 m | `(-22, 46)` |

## Livestock actor types

Three new creature assets ship with this change:
`sunmane_steppe_horse`, `sunmane_dun_mare` and `sunmane_grey_pony`. They are
registered in `godot-client/data/actors/models.json` by model id and are
instanced as **scenery** by the client's ambient population system, so they need
nothing from the server to appear.

They are deliberately registered with `serverActorType: null`. Actor-type
numbers are the server's to allocate, and the creature block in
`models.json` currently runs 204-235. If the server wants these as networked,
attackable or rideable actors it should allocate the next free numbers and add
the matching `actorTypes` entries; until then the client will simply never
receive one over the wire, which is harmless.

## What must not change

The map deliberately requires no protocol change:

- One metre per server tile, and the arrival datum at `(58, 58)`, both matching
  the entry already committed in `godot-client/data/maps/registry.json`.
- Server tile to world position uses the existing `CoordinateAdapter` unchanged.
- Walkability remains server-authoritative. The client's navigation surface
  covers the whole landform on purpose, so a grounding raycast can never miss;
  it does not decide where a player may go.
