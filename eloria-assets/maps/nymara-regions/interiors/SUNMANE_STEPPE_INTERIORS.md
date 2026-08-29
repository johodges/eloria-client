# Sunmane Steppe interiors

Sunmane's two cave systems now share **one map with unwalkable blackspace
between them**, the way Eternal Lands lays out a region's interiors, and the way
`amethyst_barrens_insides`, `crownwater_insides` and `ssarathi_insides` already
do in this repository. One package, one GLB, one collision grid, two sections,
one spawn and one exit portal each.

Package: `interiors/sunmane_insides/`. Not yet routed - see below.

| section | name | class | walkable cells | surface door on the steppe |
|---|---|---|---:|---|
| `sunmane_wind_caves` | Sunmane Wind Caves | cave | 2,118 | server `(128, 175)`, south face of the eastern butte |
| `sunmane_crystal_hollow` | Amethyst Crystal Hollow | cave | 2,291 | server `(182, 154)`, Amethyst badland |

6.61 MB, 384 × 384 half-metre collision cells of which **4,409 are walkable** —
the rest is the rock around each system and the 82 m of nothing between them.

## Nothing was re-authored

This is a layout change, not an art one. Both systems keep the specs, the
clearance field, the shell generator, the props, the braziers and the light
markers they already shipped as separate packages. `caves.Shell` gained a
movable sample centre so a system can be built somewhere other than the origin;
`insides.py` builds both into one `Builder` and writes one package.

`caves.py` still produces the two standalone packages and they are kept: they
are what you want when iterating on one system, exactly as
`crownwater/source/build_interiors.py` was kept alongside its
`build_insides.py`. Their *output* does change once, because of defect 1 below.

## Layout

```
z=-15  +----------------+                    +------------------+
       |  wind caves    |                    | crystal hollow   |
       |  60 x 60       |       82 m         | 60 x 60          |
z=-75  +----------------+                    +------------------+
         x=13     x=73                        x=139      x=199
```

Each system keeps its own 60 m sampling square; they sit 126 m apart centre to
centre. The shells taper well inside those squares, so the actual empty band
between any geometry of one and any of the other is **82 m**, measured off the
built GLB rather than assumed. The collision grid agrees: a 164-cell blocked
band separates the two occupied regions.

**The blackspace costs nothing to build.** The cavern floor only exists where a
system's clearance field is open, so there is no floor between the two systems
to stand on and nothing there to render. The gutter is not a wall; it is the
absence of cave.

## Verification

| check | result |
|---|---|
| `validate_gltf.py` | **0 errors, 0 warnings** |
| Godot 4.7.2, real `WorldLoader` | **PASS** — 8,815 of 9,216 sampled tiles miss and **every one is blackspace**: 0 misses on cells `collision.bin` marks walkable |
| Spawns | 3 / 3 grounded, within **0.005 m** |
| Determinism | byte-identical `world.glb` and `collision.bin` across repeat builds |
| Standalone packages | still build, and are now reproducible; regenerated once (defect 1) |

## Four defects this found

None were visible while each system was its own map.

### 1. The cave build was never reproducible

`caves.py` seeded from `abs(hash(spec["id"])) % 10_000`. Python salts `hash()`
on a str per process, so **two builds of identical code produced different
GLBs** — the two shipped cave packages could not be reproduced from their own
source. The production guide names this exact trap. Replaced with a CRC32-based
`stable_seed`, and verified: repeat builds are now identical, and pinning
`PYTHONHASHSEED` is no longer needed.

`settlement.py` has two more salted-hash seeds (lines 365 and 1075) that affect
the **region** build. Those are out of scope here and are still there.

### 2. Node names collided

Both systems number their boulders and stalactites from zero, so the combined
GLB failed the validator with 54 reused node names — and the client resolves
collision and navigation nodes by name. `Builder` gained a `name_suffix`, empty
by default.

**A suffix, not a prefix.** `navigation.surfaceNodePrefixes` matches the *start*
of a name, so tagging the front turned every `Terrain_CaveFloor_*` into
something the client did not recognise as a walk surface: the first attempt
built no navigation surface at all and grounded nothing on the entire map.

### 3. `Shell.axis` was read as a coordinate

`self.axis` served as both the x and the z axis while both were the symmetric
`-HALF_EXTENT..+HALF_EXTENT`. The moment a system moves, reading a z coordinate
out of the x axis places the whole cavern at the wrong end of the map — which is
exactly what happened. Now `axis_x` and `axis_z` are separate and `axis` is kept
only for its size.

### 4. The rim is not walkable, and the grid has to say so

The cavern tapers to a crawl space at its edge. Cells there have clearance and a
floor quad, so a naive grid called them walkable, and the in-engine check
reported a miss — a *different* single cell each time the mask was adjusted,
because it is a continuous rim rather than one hole. The grid now requires the
agent the manifest itself declares to fit: clearance ≥ `agentRadius` 0.55 and
headroom ≥ `agentHeight` 1.9. That took the in-engine result to zero misses.

## It is not wired up yet, and that is deliberate

**The combined package is built and verified but nothing routes to it.** The
steppe's two doors still go to the two separate maps, exactly as before, and the
client registry is unchanged.

Wiring it needs a decision that is not a layout refactor:

Sunmane is the first region whose interiors are *already two served server maps*
(`sunmane_wind_caves.elm` and `sunmane_crystal_hollow.elm`). Crownwater's,
Amethyst's and Ssarathi's absorbed rooms never were - each of those regions only
ever had one interior map key, so combining cost nothing server-side.

Serving Sunmane's two systems as one map therefore means **retiring
`sunmane_crystal_hollow` as a served map**, which touches:

| | |
|---|---|
| `config/eloria/maps.txt` | the map declaration and both portal pairs |
| `tools/generate_nymara_maps.py` | the interiors tuple, tile count and arrival |
| `config/eloria/client_content_manifest.json` | the map entry |
| `Dockerfile` | an assertion that the ELM ships in the image |
| four test files | `SUNMANE_CAVE_CONNECTIONS`, `INTERIOR_CONNECTIONS`, `NYMARA_INTERIORS`, `EXPECTED_SIZES`, `ARRIVALS`, and the Docker collision test |

That is a deployment change - it alters what ships in the container - so it is
left for the map's owner rather than taken unilaterally. The alternative is to
leave both systems served separately and treat this package as the client-side
option, which is the state as merged.

When it is wired, the shape is:

| door | on the steppe | arrives at | section |
|---|---|---|---|
| `wind-caves-mouth` | tile (128, 175) | tile (43, 27) | wind caves |
| `crystal-hollow-adit` | tile (182, 154) | tile (169, 28) | crystal hollow |

The package already carries both arrivals and both return portals.

## Known limitations

* **One environment block serves two systems of different character.** The
  limestone caves were lit warm and the amethyst hollow violet; a single map
  can carry only one environment, so this is pitched between them and the
  per-system light markers carry the difference. A genuine compromise of the
  single-map layout rather than a choice — the same one Crownwater's insides
  made.
* **Nothing has been played.** Collision response, navmesh generation and portal
  transitions are unverified. The in-engine check proves the map loads through
  the real `WorldLoader` and that every walkable cell has floor under it; it
  does not prove an actor can walk it or that a portal fires.
* **No server has loaded the map.** The registry entry and the routing are in
  place, but end-to-end play was not exercised.
* **No client frames.** The two standalone packages have their own rendered
  minimaps; this combined package ships neither a minimap nor capture frames.
  The manifest declares `minimap.webp` and the file is not there yet.
* **No new content.** Sunmane still has the two interiors it had. If the region
  wants a third — the drovers' shelter and the eastern adit are modelled cave
  mouths with closed backs — that is authoring work, not a layout change.
