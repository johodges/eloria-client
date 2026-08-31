# Four Gates map change log

## 1.0.0 — production GLB package

First authored production pass, replacing the `four-gates-city` graybox
(4,538 unique triangles of untextured primitives).

- New self-contained authoring pipeline under `eloria-assets/tools/four_gates/`:
  a core-only glTF 2.0 writer, an indexed mesh toolkit, procedural PBR material
  synthesis, modular kits, landmark assemblies, an analytic terrain field and a
  deterministic city layout.
- Sculpted terrain: flat civic plateau, battered cliff, continuous turquoise
  water ring, four causeway crossings, outer highland rim, alpine skyline and a
  northern massif carrying the sanctuary shelf. Terrain surfacing is driven by
  height **and slope**, so steep ground reads as rock everywhere.
- 29 original tileable PBR material sets (base colour, tangent normal, packed
  ORM; emissive for the sapphire crystal).
- Landmarks: five twin-drum gatehouses with animated portcullises, 40 curtain
  wall bays and 8 drum towers, four arched bridges, the plaza mandala and
  crystal-crowned monument, four arcaded porticos, and the northern sanctuary
  with a ceremonial stair, glowing portal and beacon.
- 346 district buildings across four kits with authored variation, plus market
  squares, farm plots, docks, cranes, street furniture and ~850 planted trees.
- Manifest-driven environment (sky, sun, ambient, fog, tonemap, water) applied
  by a new `WorldEnvironmentApplier`, so the map ships with its art direction.
- Collision proxies inset inside their parent geometry (never visible), a
  navigation surface prefix contract, and 28 convex navigation polygons.
- Khronos glTF-Validator: **0 errors, 0 warnings**.

## 1.0.1 — face winding correction

Reported after merge: some building walls did not read as solid.

**Cause.** Almost every primitive in `meshlib.py` listed its quad corners
clockwise as seen from outside. glTF front faces are counter-clockwise and
Godot culls back faces, so those surfaces rendered inside-out: the outward face
was culled and the viewer looked through the near wall at the interior of the
far one. `explode()` derives normals from the winding, so the authored NORMAL
attribute pointed inward too and agreed with the bad winding — which is why
lighting looked merely *dark* rather than obviously broken, and why the defect
survived the earlier visual review. Silhouettes were unaffected; only depth
ordering and shading were, so it read as an art problem at a distance and as
see-through walls up close.

**Fix.** `_quad_indices` now emits outward-CCW triangles; `arch_ring`,
`ring_band`, `quad_strip` and `torus_arc` had their corner order reversed to
match; the explicit triangle lists in `pyramid`, `gable_roof` and `hip_roof`
were flipped; and the end caps of `cylinder` and `prism` were corrected
independently of their sides.

**Guard.** `eloria-assets/tools/four_gates/test_geometry.py` asserts the
invariant directly — positive signed volume for every closed primitive, no
inward-facing faces on convex ones, +Y normals on every ground surface, and no
authored normal pointing into the opposite hemisphere from its winding. It
fails loudly on any regression.

Side effect: the authored collision proxies now block all four movement probes
in the gameplay test rather than three; a trimesh built from an inside-out mesh
was missing rays from one direction.

### Defects found and fixed during the initial pass

These were caught by the validator, the independent viewer and the client:

- glTF index accessors declared a third of their true element count, so only
  one triangle in three would have been drawn by any conformant loader.
- Flat-shaded normals were computed against stale indices after vertex
  duplication, giving null normals on hard-surface geometry.
- Ground, ring, strip and polar surfaces were wound clockwise, so every terrain
  and road surface faced downward.
- Bridge arches sprang above the deck and occluded the whole crossing.
- The bridge deck slab and its fascia were exactly coincident, producing
  z-fighting bands across the causeway.

## Interiors — six street-level rooms

Six interiors now open off the Four Gates streets, each shipped as an ordinary
world package (`world.glb` + `world.json`) under `eloria-assets/maps/`:

| Package | Room | Quarter |
| --- | --- | --- |
| `four-gates-lantern-row` | Lantern Row — covered market hall | agricultural |
| `four-gates-stormglass-house` | The Stormglass House — glazier and alchemist | service |
| `four-gates-mirrorsmith-forge` | Mirrorsmith's Forge — repair and reforge | service |
| `four-gates-reedworks` | The Reedworks — reed and cordage works | industrial |
| `four-gates-ferrymans-rest` | The Ferryman's Rest — tavern | harbour |
| `four-gates-deposit-four-keys` | The Deposit of Four Keys — storage vault | civic |

They are authored by `eloria-assets/tools/four_gates/build_interiors.py` from
the interior kit in `interiors.py`, with every door position taken from
`interior_index.py` so the city shopfronts and the interiors' exit portals can
never drift apart. Each embeds a ten-to-twelve material subset at interior
resolution rather than the city's full thirty, which is why a room is under
3.2 MB against the city's 23.5 MB.

Nothing about the wire protocol changed. A door is a `CHANGE_MAP` to another
map id exactly like any other map change; the server stays authoritative over
where the player is.

### The interior camera

The isometric rig is framed for open ground: 26 m back at −60°. Indoors that
puts the camera above the roof and behind the near wall, and the player sees a
ceiling and nothing else. Two changes fix it, and both are manifest-driven so
the city is untouched:

- **`camera` block** — an interior declares its own framing (pitch −48°,
  distance scaled to the room's long axis, tighter zoom limits).
  `WorldEnvironmentApplier.apply_camera()` applies it on load.
- **`cutaway` block** — names the roof nodes to hide outright and the four wall
  nodes with their outward normals. `InteriorCutaway` hides the roof, and hides
  any wall whose outward normal points back towards the camera, following the
  rig as it rotates. Only visibility changes: the static bodies the loader
  builds from those meshes stay in place, so a cut-away wall is still solid.

The room shell is therefore emitted as six nodes (`Shell_Ceiling`,
`Shell_Beams`, and one per wall) rather than one fused mesh, which is what
makes the cutaway addressable at all.

### Verified

- Khronos glTF-Validator 2.0.0-dev.3.10: **0 errors, 0 warnings** on all six.
- `tests/integration/rendered_interiors.gd` — 66 checks, 0 failures. Each room
  is rendered twice: once from inside, and once at its own camera profile with
  the cutaway applied, asserting the roof is hidden, the near wall is hidden,
  the far wall is still drawn, and all four walls keep their collision.
- `tests/integration/rendered_map_transition.gd` — 16 checks, 0 failures.
  City → interior → city through an authoritative `CHANGE_MAP`, with grounding
  confirmed at both ends. This closes the "portals and map transitions
  unverified" gap flagged in the original validation report.
- `tests/integration/rendered_four_gates_gameplay.gd` — 28 checks, 0 failures,
  confirming the city is unaffected by the client changes.

## 1.0.2 — plaza grounding and coplanar paving

Reported from a client screenshot of the plaza: the benches float, and the
paving is shot through with shimmering stripes.

**Cause — floating dressing.** `build_plaza()` hung every prop off a literal
`PLATEAU_Y + 0.96` (benches off `PLATEAU_Y + 1.42`), a datum that matches no
surface in the map. The paving apron sits at `PLATEAU_Y + 0.06` and the raised
inner terrace at `PLATEAU_Y + 0.48`, so the whole plaza set stood in the air:
benches by 0.94 m, planters by 0.96 m, statues and lamps by 0.90 m, fountains
by 0.48 m, and the monument by 0.42 m. Every other prop in the city is placed
with `self.ground()` and was unaffected, which is why only the plaza showed it.

**Cause — striped paving.** Two independent sets of exactly coplanar faces.
`plaza_disc()` built its two steps as full-radius cylinders that kept their top
caps, then laid an overlapping inner disc over each, putting up to four
identical surfaces at the same height across the middle of the plaza. Separately
`build_roads()` authored the plaza disc, the three ring roads, the four
ceremonial avenues and the four diagonal streets all at one height, and the
avenues ran from `r = 0`, so they paved over the mandala and over each other at
the centre. A sampled sweep of the walking surfaces found 443 coplanar hits in
900 probes; the depth test then picked a winner per pixel and the plaza
shimmered.

**Fix.**

- `plaza_disc()` is now one apron annulus, one capless riser and three abutting
  terrace annuli (the middle one in `stone_trim`, so the step ring still reads).
  No two paving faces share a plane. The profile is unchanged — apron at the
  plateau datum, terrace 0.42 m above it — so nothing else moves.
- `build_roads()` gives each carriageway class its own datum: radials and
  diagonals 3 cm under the apron, ring roads 3 cm over them. The avenues now
  start at `PLAZA_RADIUS - 4`, so the mandala covers their inner ends without a
  gap and the four of them no longer overlap at the centre.
- `WorldBuild.plaza_surface(x, z)` returns the real top of the paving — terrace,
  apron or `ground()` beyond the disc — and the monument, fountains, statues,
  benches, planters and lamps all stand on it.

### Verified

- Coplanar sweep over the walking surfaces: **443 → 0** overlapping hits in the
  same 900 probes.
- Prop grounding audit (mesh base against the highest surface beneath it):
  benches, fountains, statues and lamps all at **0.00 m**; the four planters
  that sit on an avenue are 3 cm into the paving, the same convention as every
  `ground()`-placed prop.
- `collision.bin` is byte-identical to 1.0.1 — the walk grid is derived from the
  terrain field, so none of this touches collision or `walkingHeight`.
- 5,376 fewer unique triangles (189,551 → 184,175); the duplicates were the
  hidden mandala surfaces.

## 1.0.3 — coplanar surfaces across the map

Reported from a client screenshot: textures on the models flicker, most visibly
around the gates.

**Cause — collision proxies were drawn.** `collider()` builds a low-poly box
inside each of the 428 buildings and landmarks it stands for, and the manifest's
note claimed those boxes were "fully enclosed and never visible". They are
inset by 5 to 10 mm, which is not a clearance the depth buffer can resolve at
the distance a district is seen from, and `COLLISION_Sanctuary_Body` is flush
with the sanctuary's own wall. Every large townhouse in the city therefore drew
two same-facing walls in the same plane. A proxy is a physics volume, not a
surface: the manifest now says so with `collision.nodesAreProxies`, and the
client hides the nodes while keeping the shapes built from them.

**Cause — surfaces sharing a datum.** Six independent cases, all the same
mistake in different kits:

- Every townhouse ran its wall to the top of its own cornice, so the wall head
  and the cornice cap were one plane on all 346 district buildings. The wall now
  stops at the cornice soffit, which is where a cornice actually sits.
- The four plaza porticos stood at `PLATEAU_Y`, putting their stylobate exactly
  on the ground under it; they now sit on the `PLAZA_LIFT` paving datum, like
  the paving and the carriageways.
- The sanctuary's paved terrace met its authored shelf to 2.6 mm; it moves onto
  the same paving datum.
- Bridge decks ran out onto causeway ground authored at exactly `CAUSEWAY_Y`.
  They now carry `BRIDGE_LIFT` clear of it.
- Each bridge's cutwaters sprang off the pier crown with their base caps facing
  up out of it, and the spandrels either side of a pier were sized to overlap.
  The noses spring from inside the soffit and the spandrels stop short.
- Curtain-wall bays cut their band and parapet to the bay length exactly, so
  three end caps shared the joint plane; both now run past it.
- Farm plots were sized 22-34 m radially in an 18 m ring step and cached in six
  slots shared by forty plots of different sizes, so most fields were handed a
  plane too big for their cell and ran over their neighbours. Each is now a
  fraction of its own cell and the cache is keyed on the size it holds.

### Verified

- `eloria-assets/tools/check_zfighting.py` (new) measures the real overlap area
  between coplanar same-facing surfaces, clipping every candidate pair in-plane
  so adjacent terrain triangles are not counted, and skipping whatever the
  manifest declares hidden. Four Gates: **82,424 → 1,584 m²**, a 98% reduction,
  with nothing left above 180 m².
- Client-side, `main.tscn`'s camera near plane moves from the engine default
  0.05 m to 1.0 m. The client renders through GL Compatibility, whose depth
  buffer is fixed point, so the resolvable step at distance z is about
  `z^2 / (near * 2^24)`: 12 mm at 100 m before, 0.6 mm after. The isometric rig
  never brings the camera nearer than 8 m to its focus, so nothing is clipped.
- 414 more unique triangles (184,175 -> 184,589): the farm-plot cache now holds
  a plane per field size instead of six shared ones. `collision.bin` is
  byte-identical, so none of this touches the walk grid or `walkingHeight`.
- Khronos-shaped validator: 0 errors, 0 warnings.

## 1.0.4 — the outer ring's surface classes

Reported from the client's top-down map: the outer rocky band between the water
and the map's edge reads as a jagged, speckled interleave rather than an edge,
and looks like z-fighting.

**It is not z-fighting.** Every pixel out there is drawn once. The terrain is one
mesh split into five sub-meshes by surface class, and the split is a strict
partition: 48,832 + 18,310 + 23,028 + 6,556 + 2,154 = 98,880 triangles, which is
the whole mesh and no triangle twice. Painting every drawn surface a flat colour
keyed on its mesh and shooting the rim orthographically from above returns one
unbroken colour under the trees — no second surface is competing for those
pixels — and `check_zfighting.py` reports nothing in the ring at all. Squeezing
the map camera's depth range from 0.05–2500 m to 100–700 m, which is a fourfold
gain in depth resolution, moves seven pixels in a 1024² frame.

**Cause — one class per triangle instead of one per quad.** `polar_surface`
asked `material_fn` once per *triangle*. A quad's two triangles are two
different planes and their centroids sit a radial step apart, so wherever the
ground hovers near a class threshold the two halves of one quad came back in
different classes and the boundary ran along the quad's own diagonal. On the
plateau that happened to 1% of quads; on the outer rim, where the slope sits
either side of the rock cut-off for two hundred metres, it happened to **9%**,
and since a polar quad out there is 4.5 m radially by 12.8 m around, each tooth
is a long thin sliver. Seen from 448 m up at 2.2 m per pixel, several thousand
of those slivers is the "dithered mess".

**Fix.** `meshlib.polar_surface` decides the class once per quad, from the
quad's centre and its own normal, and hands both triangles that class. A patch
of ground belongs to one surface class; how the mesh happened to cut it into
triangles is not the ground's business. This is the Four Gates counterpart of
the rule the region toolkit already carries — *splitting one field into
sub-meshes selects quads, not vertices*.

### Verified

- Rock/grass/sand boundaries in the rim read as coherent bands in the packaged
  minimap render and in a 3072² shot of the in-game full-map framing; the long
  interleaved slivers are gone. Ground-level views are visually unchanged.
- 98,880 terrain triangles before and after, and the same 184,589 unique
  triangles map-wide: no geometry moved, only which sub-mesh owns it. The class
  mix shifts by under 4% (rock 18,310 → 19,004 triangles).
- `collision.bin` is byte-identical, so the walk grid and `walkingHeight` are
  untouched. `check_zfighting.py`: 1,584.2 m² across 83 pairs, unchanged.
- 37 KB smaller (23,545,448 → 23,508,048 bytes): fewer vertices duplicated at
  class seams.
- `rendered_four_gates_map.gd`, `rendered_four_gates_views.gd`,
  `test_world_lighting.gd` and `test_occluder_fade.gd` all pass.
