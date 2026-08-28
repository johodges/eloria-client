# Crownwater interiors

Four authored interiors reached from named landmarks on the 576 m Crownwater
map. They are built with the region's own kit — `crownkit.py` for materials,
`crownarch.py` for architecture — over the shared toolkit's shell parts, so a
doorway, a column and a stair tread are the same construction indoors as out.

| package | name | class | surface anchor | triangles | GLB | walk cells |
|---|---|---|---|---:|---:|---:|
| `drowned_crown` | The Drowned Crown | dungeon | `crownwater-cathedral` | 25,334 | 5.24 MB | 17,100 |
| `crownwater_tide_cistern` | The Tide Cistern | utility | `crownwater-pavilion-pavilion_west` | 32,976 | 3.78 MB | 11,784 |
| `crownwater_customs_hall` | The Harbour Customs Hall | settlement | `crownwater-customs-hall` | 11,706 | 4.49 MB | 9,304 |
| `crownwater_tide_campanile` | The Tide Campanile | tower | `crownwater-campanile` | 6,510 | 2.58 MB | 536 |

## Why these four

Crownwater is a city on water, so its insides are about water: what lies under
it, what holds it back, and what floats on it. Each takes a different answer, so
no two are the same room with different textures.

**The Drowned Crown** is the water winning — an older palace the basilica was
built on top of, now half flooded. The only one whose programme was *given*
rather than invented: `drowned_crown/concept.json` lists flooded vestibule,
water galleries, submerged arch, shell altar, statue court, water channel,
collapsed dome, air pocket and objective hall, and every one is a space. The
water line is held flat at y = −6.05 throughout and the floors step down beneath
it, so the wading gets deeper as you go in until the collapsed dome lets the
light back in.

**The Tide Cistern** is water put to use: a hundred columns standing in a hand's
depth of fresh water under the garden islet, lit by oculi down from the plaza,
with a brass sluice gear that lets the basin down to the lagoon. Symmetric and
repetitive where the Drowned Crown is broken. A raised walk crosses it so the
room is traversable on foot rather than only wadeable.

**The Harbour Customs Hall** is the only one with a job — ledger hall, mezzanine
office, bonded store stacked to the trusses, a strongroom, and a water gate
where a lighter comes in *under* the building to unload. Timber and plaster over
stone. Mundane on purpose: three monuments in a row would make Crownwater a
museum rather than a place people work.

**The Tide Campanile** is the one dry, bright, vertical space — a hollow 26 m
shaft with a switchback stair, a ringing floor and an open belfry, deliberately
the opposite of the Drowned Crown in every axis.

## Building them

```sh
cd ../crownwater/source
python build_interiors.py                    # all four
python build_interiors.py --only drowned_crown
python verify_interiors.py --report ../interiors-verification.json
```

Deterministic for a given seed. Nothing in `_toolkit/` is modified: the toolkit's
`chamber`, `passage` and `_barrel_vault` are imported unchanged, and Crownwater's
six material recipes are registered at build time by `crownkit.register()`.

Real client frames (needs a Godot 4.7.2 binary and a display):

```sh
ELORIA_ARTIFACT_DIR=<dir> godot --audio-driver Dummy \
  --rendering-method gl_compatibility --path godot-client \
  --script res://tests/integration/rendered_crownwater_interiors.gd
```

## Verification

`verify_interiors.py` rather than the region's `verify_runtime.py`, and the
difference matters. The region tool casts the grounding ray at every tile of the
bounding box and calls a tile with no floor a miss. That is right for a region,
where every server tile is ground. It is wrong for an interior, which is rooms
carved out of solid rock: run against these four it reports **46–74% "misses"**,
every one of them correct behaviour.

The contract that actually holds indoors is narrower and stricter — *every cell
the collision grid calls walkable must have a walk surface under it* — and that
is what `verify_interiors.py` checks.

| package | walkable cells | without a surface | height disagreements | spawn problems |
|---|---:|---:|---:|---:|
| `drowned_crown` | 17,100 | **0** | 0 | 0 |
| `crownwater_tide_campanile` | 536 | **0** | 0 | 0 |
| `crownwater_tide_cistern` | 11,784 | **0** | 0 | 0 |
| `crownwater_customs_hall` | 9,304 | **0** | 0 | 0 |

glTF: **0 errors** on all four. In-client: all four load through the real
`WorldLoader`, and the 19 frames in each package's `references/captures/` are
**real Godot client frames, not offline previews**.

## Three client-contract defects this found

All three were invisible to the offline tools and only appeared when the
packages were rendered through the client's own code path. **All three affect
Amberwood's interiors too, and are not fixed there.**

### 1. Manifest lights are read from `environment.lights`, not the top level

`WorldEnvironmentBinder._apply_lights` reads
`manifest.data["environment"]["lights"]`. `build_interiors.py` — inherited from
Amberwood's — emitted a **top-level** `"lights"` array, which the binder never
looks at. An interior lit only by a directional sun it has a ceiling against
renders black.

The binder also reads `entry["color"]`; the build wrote `"colour"`, so even once
found, every lamp fell back to the default tint.

**Amberwood's four interiors still emit 27 lights the binder cannot see.**

### 2. Placement is single-layer, so no deck may span a tower's footprint

The client places an actor on the **first** surface a ray from y = 400 meets. The
campanile's ringing floor and belfry gallery originally spanned the full 10 m
footprint, so every placement in the tower — including its arrival spawn —
grounded 26 m up on the belfry rather than on the ground floor.

Both decks are now **annular**, leaving a well down the middle where a campanile
hangs its bell anyway. A player can still *walk* the stair normally; only
placement is single-layer. The rule this leaves behind: **no spawn or portal may
sit beneath a deck.**

### 3. `hanging_lamps` returns a pair, and lamp positions are `[x, y, z]`

`hanging_lamps(points)` returns `(mesh, positions)` and takes `(x, y, z)`.
Hand-built lamp entries written `[x, z, y]` lit a point 27 m above the cistern
basin instead of 3 m above it — silent, because a light in the wrong place is
still a valid light.

## Where they attach

Each interior's surface entrance is a portal on the Crownwater region manifest,
sitting on the landmark it belongs to; each package carries the matching return
portal to `maps/nymara/crownwater.elm`. All four are registered in
`godot-client/data/maps/registry.json` with
`"interiorOf": "maps/nymara/crownwater.elm"`.

Two region changes were needed to give two of them a door:

* **The cathedral was renamed** from "The Drowned Crown" to **"The Crown
  Basilica"**. The interior beneath it is the drowned palace it was built over,
  and two things could not carry the same name.
* **A customs house was added** to the harbour islet — the region had no
  building there at all, only quays and stalls, so the customs hall had no
  surface entrance to hang off.

## Known limitations

* **`drowned_crown`'s own detail board is truncated** (786,446 bytes; the same
  defect as fifteen of the seventeen region boards). Its ten concept *subjects*
  are listed in `concept.json` and every one is built, but there is no artwork
  to compare against, so no panel comparison sheet exists for it.
* **The `drowned_crown` server portal is contested.** `concept.json` declares
  `parentRegion: crownwater`; `eloria-server`'s `config/eloria/maps.txt` links
  it to `mirrorhold`, and has since before either region was worked on. **Those
  two lines are deliberately left untouched** — whichever session edits them
  resolves the disagreement unilaterally on no authority. It needs a decision.
* **No server ELMs.** These are client-side packages, as Amberwood's interiors
  are. Nothing has been added to `source-elm/` and no server has loaded them.
* **Names are placeholders**, as the region's are. No authoritative written
  description was available.
* **Lighting is judged by eye.** The four are readable in client frames but the
  Drowned Crown's deeper rooms are dark by intent, and "dark enough to be
  atmospheric" versus "too dark to play" is not something these captures settle.
