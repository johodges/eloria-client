# Verdant Stair change log

What changed from the `terrain-landmark-material-pass` placeholder to this
package, and the mistakes worth recording so the next region does not repeat
them.

## Starting condition

The placeholder had every defect section 3 of `REGION-PRODUCTION-GUIDE.md`
lists, verified rather than assumed:

* **Flat terrain.** One `Terrain_ELM_Authority` mesh, `min [-96, 0, -96]` to
  `max [96, 0, 96]`: y = 0 everywhere, and only 192 m across rather than 576.
* **Foreign landmarks.** 9 of 55 belonged to other regions — Amberwood Estate,
  Crownwater Ferry Dock, Four Gates Gatehouse, Westhaven Dry Dock, Mirrorhold
  Floating Market, Ssarathi Water Gate, Manymouth Hidden Dock, Whitehorn Rope
  Bridge, Resonant Crystal Cluster. None was preserved.
* **Pre-schema manifest.** No `bounds`, no `coordinateTransform`,
  `spawnPoints` where the schema wants `spawns`, and a `collision` block that
  was a bare list of node names.
* **Flat placeholder ELM.** `source-elm/verdant_stair.elm` was 32 × 32 tiles at
  height 11 throughout, 39,880 bytes.
* **Truncated detail board.** `references/00-concept-detail-board.png` was cut
  to 786,445 bytes, of which only the top row of five panels decodes — but an
  intact 3,351,416-byte copy was already sitting beside it in the working tree,
  untracked. That copy is now committed as the board, so nobody has to ask for
  it again.

The QA README under `qa/regions/verdant-stair/` does exist, contrary to the
guide's expectation of `qa/regions/<region>/` with an underscore.

## What was built

Terrain first, as the guide asks. The heightfield was exported, validated and
run through `verify_runtime.py` at zero grounding misses **before any detail
work**, and only then populated.

* `source/region.py` — the composition: eight terraces on a south-west to
  north-east diagonal, six watercourses, four gorges, the lagoon shoreline.
* `source/populate.py` — eight placement passes, largest to smallest, plus the
  server's own population tables.
* `source/views.py` — the camera set, the panel mapping and this region's
  lighting.
* `source/build_verdant_stair.py` — the build entry point.
* `_toolkit/amberwood/junglecraft.py` — the kit pieces the board needs that no
  existing module could build.

## Mistakes worth recording

Each of these shipped in a draft and was caught by looking at the result.

1. **Terrace risers 25 m wide are ramps, not cliffs.** The first `TERRACES`
   table left 6 design units between shelves, which is about 25 m of ground for
   a 17–28 m rise: a 40° slope a player walks straight up. The region stopped
   reading as a stair at all. Narrowed to 2.5 units, about 10.6 m, and the
   cliffs appeared.

2. **Noise at 0.004 across a 635 m map is a constant.** The wander meant to
   break the shelf edges into something organic did nothing at all, however
   large its amplitude, because the noise field was under three cells wide over
   the whole terrain. The four cliff lines came out ruled. Raised to 0.0105 and
   0.029 and they scallop.

3. **Roads fill the gorges the bridges span.** Every gorge is a bridge site, so
   a route runs up to each one, and `grade_path` levels its corridor with
   `flatten=0.90`. Carving the ravines inside `build_terrain` — before the
   roads — meant the roads quietly filled them back in. The symptom was an
   aqueduct standing on ground a metre below its own deck with nothing to span.
   `carve_ravines()` now runs at the end of `apply_built_ground`.

4. **An arcade sized from its abutments has no idea how deep the gorge is.**
   `min(ground(west), ground(east))` is the terrace level, because both
   abutments stand on the terrace. The bridge was built 8 m tall from there and
   ended up 7.6 m proud of the deck it was meant to carry. Sizing from the
   deepest ground along the span fixed it. `verify_runtime` reported this as
   `LANDMARK_BELOW_SURFACE` three builds running, with the same number each
   time, which was the clue that it was the *bridge* that was wrong and not the
   marker.

5. **Detail-tier thresholds decide the triangle budget, not tree count.** With
   "high inside 26 m of a route, mid inside 70 m" and thirty-odd routes
   crossing the map, almost every tree counted as near one. Almost nothing
   landed on the far tier and the wood alone came to 9.7 M triangles — 30.8 per
   square metre, over three times Amberwood. Tightening to 12 m / 30 m, with a
   modest spacing and branch-count trim, brought it to about a third of that.

6. **The material pin is a contract, and it needs teeth both ways.** Amberwood
   warns about pinned-but-unreferenced materials. This build also *fails* on
   referenced-but-unpinned ones, which immediately caught four materials
   Amberwood's reused kits hardcode — `cobble_paving` on the multi-arch bridge
   deck, `forest_floor` in a leaf drift, `water_pool` in a well, `amber_resin`
   in the lamp posts. Three are remapped to this region's equivalents at the
   single point where a mesh is registered; the lantern amber is kept and
   pinned, because one warm note in a green region is worth 40 KB.

7. **`kind` is not `type`.** The landmark entries were written with a `kind`
   field. Nothing reads it: the manifest convention — and the key
   `verify_runtime` uses to exempt bridges and pavilions from its floating
   check — is `type`. Renamed, with Amberwood's vocabulary rather than a second
   one.

8. **Ninety random samples over a 576 m map find two spots on a cliff.** The
   vine-curtain pass sampled the whole map and rejected everything that was not
   on a riser, and placed ten curtains in the entire region. Sampling *along*
   the riser instead — pick a point on it, then test for steepness — found
   them.

## Toolkit changes

Added, never forked (see the shared `_toolkit/README.md` for the rule):

* `terrain.py`: two surface classes, `TERRACE_MOSS` and `WET_ROCK`, in the
  23–26 block reserved for this region.
* `textures.py`: thirteen recipes, two water tones, and `_pinna_polygon` — a
  frond built from `_leaf_polygon`'s wide oak lobes stacks into something
  closer to a pine cone than a fern.
* `materials.py`: the fifteen matching specs, appended.
* `junglecraft.py`: the new kit module.

One **bug fix** rather than an addition:

* `capture_views.py` put a region's `DAY_LIGHTING` override *dict* into
  `REGION_LIGHTING`, where the aerial branch then called `vars()` on it. Any
  region using the documented lighting hook crashed with
  `TypeError: vars() argument must have __dict__ attribute` — after a full
  texture and region build, so about ninety seconds in. The overrides are now
  normalised to `Lighting` objects once `DAY` and `GOLDEN` exist. Verdant Stair
  is the first region to use the hook, which is why it had never fired.

## What the captures caught that the validators could not

The guide is explicit that a clean validator report is not a claim that the map
looks right, and this round proved it: every defect below passed both
validators and `verify_runtime` without a murmur.

9. **Cliff faces reading as blank pale ramps.** Four separate hypotheses were
   tested and all four were wrong before a ray probe along the offending
   camera's own sightline settled it. It was not the terrace walls, not the
   stair's substructure, not the paved route corridors, and not UV stretching.
   The faces were simply `Terrain_Rock` and `Terrain_WetRock`, and the wet
   limestone recipe was the palest ground in the region — a near-white rock
   under a bright sun. Darkening the cliff, wet-rock and terrace-stone recipes
   by about a third was the actual fix, and it changed the whole region: the
   town, the aerial and the risers all resolved at once.

   The three false leads were still worth keeping, because each was a real
   defect in its own right and each is now fixed:

   * **Terrain UVs are a top-down planar projection.** `mesh.heightfield` maps
     world XZ straight to UV, so a near-vertical face gets almost no UV
     variation over tens of metres. That is harmless in Amberwood and wrong
     here, where the region is *made* of cliff faces. Every terrain class now
     gets `project_uv_triplanar`, which degenerates to exactly the same
     projection on flat ground.
   * **Paved roads were painted up 60-degree cliffs.** `grade_path` marks its
     whole corridor, and `PAVING` and `PATH` are `AUTHORED_SURFACES`, so the
     slope rule will not touch them. Six-metre-wide pale ramps ran up every
     riser. Built surfaces steeper than the walk limit are now handed back to
     the rock; the climbs are carried by the authored stairs.
   * **The Grand Stair's substructure was one blank block.** A 22 m flight at
     this pitch runs nearly forty metres out from the cliff foot, so the mass
     under its landings is tall. It is now coursed and battered.

10. **The lagoon shoreline was a row of rectangular notches.** The water plane
    is clipped to where the ground is below sea level, so its cell size *is*
    the shoreline resolution. 8 m cells were visible from the beach; 4 m are
    not.

11. **The offline capture cameras need looking at, not just placing.** Of the
    first thirty-eight, four were inside canopy, one was photographing the
    flank of the stair it was named after, and the aerial sat 780 m up and
    450 m outside the map, photographing the region as an object in a void.
    `capture_views.py --only <ids>` re-shoots a subset in seconds and merges
    into the existing index, which is what makes iterating on framing
    affordable.

12. **Two regions claimed the same surface classes.** Grey Moors (#196) and
    this branch both cut from a develop where class 23 was free, and both took
    it — this one 23-24, Grey Moors 23-27. Because both blocks append to the
    same table in the same place, git could have merged them without raising a
    conflict, leaving two constants with the same value, `SURFACE_NAMES`
    holding only one, and the losing region's terrain quietly mislabelled in
    its own package. Nothing would have crashed.

    Verdant Stair moved to 28-29, being the side that needs two classes rather
    than five. Confirmed inert by rebuilding on the new numbers: `world.glb`
    byte-identical, `world.json` and `collision.bin` unchanged, `validate_gltf`
    still 0/0. No server change either — nothing outside `terrain.py` uses the
    integers, `world.json` records surfaces by name, and the ELM export reads
    `collision.bin`, whose cell byte is a height code and not a class.

    Found by reading a sibling PR before opening this one, not by any check in
    the pipeline. Nothing in the toolkit would catch it.
