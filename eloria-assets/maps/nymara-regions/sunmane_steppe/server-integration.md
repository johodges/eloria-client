# Sunmane Steppe - server integration

Everything in this document is server-side work that this client change
does **not** perform. The client change is self-contained and does not
alter the network protocol or any gameplay behaviour; the region loads
and is traversable with the server exactly as it is today.

`eloria-server` was not reachable from the workspace this package was
built in, so none of the records below could be committed there. They are
generated from the committed manifests by
`tools/sunmane/server_integration.py`, so the matching server pull
request is transcription rather than redesign.

## Hooks

The region's hook names come from
`maps/nymara-regions/source-elm/regions-connections.json` and are
unchanged:

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
| Metres per server tile | 1.0 |
| Arrival datum | `(58, 58)` |
| Addressable tiles | 0..191 on both axes |
| Addressable world band | X -58..133, Z -133..58 |
| Walk portal west | `(6, 58)` from Amethyst Barrens `(110, 58)` |
| Walk portal east | `(110, 58)` to Amberwood `(6, 58)` |
| Interior entrance | `(58, 100)` to Ssarathi Royal Archive `(58, 10)` |

The region is wider than the addressable band on purpose. Everything
outside it - the far spires, the summits, the open sea - is scenery a
player can see but never stand on, and it is marked
`"reachable": false` in the manifest. The server needs no record of it.

## New interior maps

Two cave interiors ship as their own packages under
`maps/nymara-regions/interiors/` and are registered client-side in
`godot-client/data/maps/registry.json`. They need server map ids and the
matching transition records:

| Server map id | Name | Datum | Entrance on the steppe | Arrival inside | Exit back to |
|---|---|---|---|---|---|
| `maps/nymara/sunmane_wind_caves.elm` | Sunmane Wind Caves | `(30, 30)` | `(128, 175)` | `(30, 12)` | `(128, 175)` |
| `maps/nymara/sunmane_crystal_hollow.elm` | Amethyst Crystal Hollow | `(30, 30)` | `(182, 154)` | `(30, 13)` | `(182, 154)` |

Both interiors are one metre per tile like the surface map, use
`invertServerY`, and place their datum at the centre of a 60 m square, so
every walkable tile is in 0..60 on both axes. The other two cave mouths on
the surface - the drovers' shelter and the eastern adit - are modelled
shelters with no interior and need no registration.

## Safe spawn surfaces

The client grounds actors by raycasting the navigation surface, and every
sampled column in the region grounds successfully, so any walkable tile is
a safe spawn. The positions the manifests name explicitly:

| Spawn id | Server tile | Map | Note |
|---|---|---|---|
| arrival-datum | `(58, 58)` | sunmane_steppe | ceremonial crossroads at the shared market |
| west-caravanserai | `(6, 58)` | sunmane_steppe | arrival from Amethyst Barrens |
| east-caravanserai | `(110, 58)` | sunmane_steppe | departure toward Amberwood |
| north-barrowfield | `(58, 100)` | sunmane_steppe | Ssarathi Royal Archive entrance approach |
| entrance-hall | `(30, 12)` | sunmane_wind_caves | Entrance hall |
| wind-gallery | `(30, 28)` | sunmane_wind_caves | The wind gallery |
| adit-mouth | `(30, 13)` | sunmane_crystal_hollow | Adit mouth |
| geode-chamber | `(30, 32)` | sunmane_crystal_hollow | The geode chamber |

## NPC posts (15)

| Id | Label | Role | Server tile |
|---|---|---|---|
| `khan-of-the-sunmane` | Orun khan | quest | `(58, 60)` |
| `market-broker` | Seasonal market broker | trade | `(50, 48)` |
| `horse-master` | Camp horse master | trade | `(28, 92)` |
| `caravan-master-west` | West caravan master | travel | `(16, 54)` |
| `caravan-master-east` | East caravan master | travel | `(100, 54)` |
| `shrine-keeper` | Banner shrine keeper | quest | `(33, 92)` |
| `miller` | Steppe miller | trade | `(102, 25)` |
| `well-keeper` | Crossroads well keeper | service | `(58, 37)` |
| `barrow-warden` | Barrow warden | quest | `(58, 96)` |
| `cove-factor` | Cove landing factor | trade | `(5, 14)` |
| `dune-well-keeper` | Dune well keeper | service | `(62, 148)` |
| `salt-factor` | Salt-pan factor | trade | `(122, 156)` |
| `wind-cave-watch` | Wind caves watch | quest | `(128, 170)` |
| `amethyst-prospector` | Amethyst prospector | trade | `(180, 150)` |
| `range-warden` | Whitehorn range warden | quest | `(156, 146)` |

## Harvestable resources (20)

| Id | Label | Kind | Server tile |
|---|---|---|---|
| `sunmane-wheat-00` | Sunmane wheat | crop | `(92, 28)` |
| `sunmane-wheat-01` | Sunmane wheat | crop | `(24, 104)` |
| `sunmane-wheat-02` | Sunmane wheat | crop | `(110, 14)` |
| `sunmane-wheat-03` | Sunmane wheat | crop | `(6, 36)` |
| `sunmane-wheat-04` | Sunmane wheat | crop | `(80, 116)` |
| `steppe-herbs-00` | Steppe herbs | herb | `(8, 78)` |
| `steppe-herbs-01` | Steppe herbs | herb | `(120, 98)` |
| `steppe-herbs-02` | Steppe herbs | herb | `(34, 0)` |
| `shore-clay-00` | Shore clay | mineral | `(4, 10)` |
| `shore-clay-01` | Shore clay | mineral | `(6, 104)` |
| `mesa-flint-00` | Mesa flint | mineral | `(38, 132)` |
| `mesa-flint-01` | Mesa flint | mineral | `(118, 120)` |
| `amethyst-shard-00` | Amethyst shard | mineral | `(168, 154)` |
| `amethyst-shard-01` | Amethyst shard | mineral | `(184, 128)` |
| `pan-salt-00` | Pan salt | mineral | `(64, 182)` |
| `pan-salt-01` | Pan salt | mineral | `(120, 168)` |
| `dune-sage-00` | Dune sage | herb | `(38, 166)` |
| `dune-sage-01` | Dune sage | herb | `(98, 154)` |
| `scree-ore-00` | Scree iron ore | mineral | `(182, 98)` |
| `scree-ore-01` | Scree iron ore | mineral | `(12, 184)` |

## Hostile creature spawns (10)

All models below already exist in the client's creature catalogue.

| Model | Area | Count | Radius | Server tile |
|---|---|---|---|---|
| `dire_wolf` | north mesa breaks | 3 | 10.0 m | `(28, 126)` |
| `dire_wolf` | eastern breaks | 3 | 10.0 m | `(132, 92)` |
| `wild_boar` | south-west scrub | 4 | 11.0 m | `(10, 8)` |
| `red_fox` | open steppe | 4 | 14.0 m | `(88, 108)` |
| `elk` | northern pasture | 4 | 12.0 m | `(6, 108)` |
| `mountain_goat` | coastal cliffs | 3 | 9.0 m | `(6, 46)` |
| `mountain_goat` | Whitehorn foothills | 3 | 12.0 m | `(150, 178)` |
| `dire_wolf` | wind cave approach | 3 | 11.0 m | `(114, 166)` |
| `red_fox` | amethyst badland | 3 | 12.0 m | `(172, 136)` |
| `wild_boar` | dune margin scrub | 4 | 12.0 m | `(34, 150)` |

## Interaction points needing server behaviour

The manifest declares 70 interaction points. The ones that need a server
decision rather than a client-side prompt are the map transitions:

| Id | Label | Server tile | Destination map | Arrival tile |
|---|---|---|---|---|
| `cave-wind_caves` | Sunmane Wind Caves | `(128, 175)` | `maps/nymara/sunmane_wind_caves.elm` | `(30, 12)` |
| `cave-crystal_hollow` | Amethyst Crystal Hollow | `(182, 154)` | `maps/nymara/sunmane_crystal_hollow.elm` | `(30, 13)` |

The remainder - wells, water stations, shrines, markets, shelters,
hitching rails - are ordinary interaction points and behave like the
equivalents in other regions.

## Livestock actor types

Three creature assets ship with this change: `sunmane_steppe_horse`,
`sunmane_dun_mare` and `sunmane_grey_pony`. They are registered in
`godot-client/data/actors/models.json` by model id and are instanced as
**scenery** by the client's ambient population system, so they need
nothing from the server to appear.

They are deliberately registered with `serverActorType: null`. Actor-type
numbers are the server's to allocate, and the creature block in
`models.json` currently runs 204-235. If the server wants these as
networked, attackable or rideable actors it should allocate the next free
numbers and add the matching `actorTypes` entries; until then the client
will simply never receive one over the wire, which is harmless.

## What must not change

The map deliberately requires no protocol change:

- One metre per server tile, and the arrival datum at `(58, 58)`, both
  matching the entry already committed in
  `godot-client/data/maps/registry.json`.
- Server tile to world position uses the existing `CoordinateAdapter`
  unchanged; the region moved its world centre, not its datum.
- Walkability remains server-authoritative. The client's navigation
  surface covers the whole landform on purpose, so a grounding raycast
  can never miss; it does not decide where a player may go.
