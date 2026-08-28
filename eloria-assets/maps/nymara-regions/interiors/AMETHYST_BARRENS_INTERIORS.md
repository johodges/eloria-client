# Amethyst Barrens interiors

Four authored interiors reached from named landmarks on the 576 m Amethyst
Barrens map. Room, passage and lamp construction comes from the shared toolkit's
`interiors` module, so a doorway and a stair tread are the same thing here as in
Amberwood's; the four compositions are the region's own and live in
`amethyst_barrens/source/interiors.py` rather than in the toolkit.

| package | name | class | surface anchor | rooms | triangles | GLB | walk cells |
|---|---|---|---|---:|---:|---:|---:|
| `resonant_vault` | The Resonant Vault | dungeon | `glasswarden-observatory` | 12 | 82,360 | 6.68 MB | 18,876 |
| `amethyst_geode_hollow` | The Geode Hollow | cave | `amethyst-geode-cave-1` | 7 | 20,872 | 4.62 MB | 12,288 |
| `amethyst_shardworks` | The Shardworks | workings | `resonant-crystal-cluster-0` | 9 | 13,734 | 4.98 MB | 10,252 |
| `amethyst_storm_barrow` | The Storm Barrow | barrow | `amethyst-storm-ruin-0` | 7 | 12,288 | 4.07 MB | 9,496 |

## Why these four

A region whose interiors are all the same room with different props has no
interiors. These are four different kinds of place, and they are deliberately
built from four disjoint material sets:

**The Resonant Vault** — dressed slate and brass, lit, occupied. What the
Glasswardens actually do with the crystal. Follows the ten subjects its concept
package at `interiors/resonant_vault/concept.json` already specified: sealed
approach, laboratory gallery, archive aisle, crystal brazier, experiment table,
lens room, containment cell, energy crossing, research hall, material study. The
brass-inlaid slate floor carries every one of them, which is why it got its own
texture recipe.

**The Geode Hollow** — no dressed stone, no brass, no straight line. A throat
down through rock into the inside of a geode, with a still pool doubling it. The
one interior that is not built, only entered. Crystal is placed on a radial
falloff so the shards are dense against the walls and thin over the floor a
player crosses.

**The Shardworks** — timber, iron, dust and spoil. The crystal being broken out
and hauled up: a headframe open to the sky, a shaft, a sorting floor with a
scale pan, a cutting floor, a working stope with a cart, a winze down to the
deep. The only one of the four where people are working, and the only warm one.

**The Storm Barrow** — coarse rubble and unadorned ashlar, older than the
Glasswardens. A ruined dromos, standing stones brought inside, and a strike well
open to the region's sky where lightning still comes down onto a fused floor
with fulgurite branching up the walls. No brass appears anywhere in it.

## Building them

```sh
cd ../amethyst_barrens/source
python build_interiors.py                    # all four
python build_interiors.py --only resonant_vault
python preview_interior.py resonant_vault /tmp/sheet.png \
       --captures ../../interiors/resonant_vault/references/captures
PYTHONPATH=../../_toolkit python ../../_toolkit/verify_runtime.py \
       --package ../../interiors/resonant_vault
```

`build_interiors.py` emits `world.glb`, `world.json`, `collision.bin` and a
validator report per package, and is deterministic for a given seed.

## The two contracts that matter

**Walk surfaces.** Every standable surface is emitted as a `Walk_<material>`
node. The client turns node names matching `navigation.surfaceNodePrefixes` into
the collision layer its downward grounding ray tests; a floor emitted as ordinary
geometry is scenery the player falls through. The corollary bites too: the
Vault's gallery walkways and every brass rail are deliberately *not* walk
surfaces, because a waist-high rail marked walkable is a ledge the ray will
happily stand an actor on.

**Collision.** `collision.bin` is the region's `EWCG v1` format. The byte is a
six-bit height code, not a flag: 0 is blocked, 1..63 decode as
`origin + value * step`, and each interior fits its own `step` to its vertical
range.

## Where they attach

Each interior's surface entrance is an `interior-entrance` portal on the Amethyst
Barrens region manifest, sitting on the landmark it belongs to, and each package
carries the matching return portal. All four are registered in
`godot-client/data/maps/registry.json` with `interiorOf` pointing at
`maps/nymara/amethyst_barrens.elm`.

The Vault is `resonant_vault`, not `amethyst_resonant_vault`: `eloria-server`'s
map table already carries that key, and the concept package that briefs it is at
`interiors/resonant_vault/`. The other three are new and take the region prefix,
as Amberwood's four do.

## Verification

`verify_runtime.py` reports **0 errors** on all four, and all four pass
`validate_gltf.py` with **0 errors and 0 warnings**.

Each reports one `GROUNDING_RAY_MISS` warning, between 66% and 85% of sampled
tiles. That is expected and not a defect: the harness samples the whole square
footprint, and an interior is rooms inside rock, so most of its bounding square
is legitimately not walkable. Amberwood's four sit at 61–72% for the same reason.
The Vault and the Barrow are higher because they are long and thin.

## Client frames

`references/client-captures/` in each package holds frames rendered by loading
`world.json` through the client's own `WorldLoader.load_world()` on a GPU, using
the shared `_toolkit/godot_capture.gd`. `references/captures/` is the offline
rasteriser and is a preview, not a client frame.

The harness previously lit every package with its region daylight rig, which put
a sun through the ceiling of a sealed vault. It now reads the package manifest
and, when `environment.sky` is `"none"`, lights from the manifest's own ambient
and fog with the sun reduced to a weak vertical fill. That change is in the
shared harness and applies to Amberwood's interiors too.

## What is not verified

- **No interior has been played.** Collision response, navmesh generation,
  portal transitions and transparency sorting are all unverified. The client
  frames prove the packages load and render through the real loader; they do not
  prove an actor can walk through them.
- **The server disagrees about where the Vault leads.**
  `config/eloria/maps.txt` in `eloria-server` routes `resonant_vault` to and from
  `four_gates`, not to Amethyst Barrens. These packages assume the region above,
  which is what the concept and the region manifest say. The server is
  authoritative for transitions, so that table needs reconciling before anyone
  walks through the door. The other three have no server map key at all, exactly
  as Amberwood's four do not.
- **The Storm Barrow is lit as an exterior** in its client frames. It declares
  `sky: "storm"` because its strike well is genuinely open to the region's sky,
  and the harness has one environment per package — so its enclosed rooms get
  daylight they would not have in game. Choosing per-space lighting is a harness
  change nobody has needed yet.
- Place names are the author's throughout except The Resonant Vault, which comes
  from the concept package and the server map table.
