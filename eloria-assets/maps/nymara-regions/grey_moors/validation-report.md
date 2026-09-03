# Grey Moors — validation report

Every number here came from a tool run against the shipped package, not from
inspection. Where something was **not** checked, it says so; a clean validator
report covers less than it looks like it does.

## glTF validity

```
python3 ../_toolkit/validate_gltf.py world.glb
errors=0 warnings=0 infos=2

python3 ../_toolkit/validate_gltf.py world-lod2.glb
errors=0 warnings=0 infos=4
```

Full reports in `world.glb.validator.json` and `world-lod2.glb.validator.json`.
The infos are unused-texcoord notices on meshes exported without tangents; they
are informational in the glTF spec and carry no runtime consequence.

Both packages are self-contained: geometry, materials and every texel are
embedded, there are no external file references, and **no glTF extensions are
used**, so the package loads through the client's own loader path with nothing
optional enabled.

## Runtime contract

```
python3 ../_toolkit/verify_runtime.py --report verification-report.json
[nav] 18 walk-surface nodes, 215,226 triangles
[grounding] 331,776 tiles sampled, 0 misses (0.00%)
[collision] 1152x1152, 88.3% walkable
[verify] 0 errors, 1 warnings
```

**0 errors. 0 grounding misses across every one of the 331,776 server tiles.**
Not a sample — the verifier casts a ray at every tile of the 576 x 576 grid, and
every one of them lands on a walk surface. No character on this map can fall
back to `walkingHeight`.

This was proved on bare terrain *before* any detail work, as the production
guide requires: the terrain-only build (`build_grey_moors.py --terrain-only`)
reported `0 errors, 0 misses` over the same 331,776 tiles, and population only
began after that.

### The one warning

```
GROUNDING_DISCONTINUITY: 361 adjacent tile pairs differ by more than 6 m
```

All of them are on the closing rim at the very edge of the playable grid — the
largest are at server tile row/column 575, which is the last tile before the
margin. That rim is a scarp cut deliberately steeper than the collision slope
limit so it is scenery rather than reachable ground. This is the "expected at
cliffs" case the check names, and it is the only warning the package carries.

### Warnings that were fixed rather than documented

Three findings from earlier runs were real defects and were fixed, not excused:

| finding | cause | fix |
| --- | --- | --- |
| `COLLISION_SURFACE_MISMATCH` | boardwalk deck planks were built at half width (`mesh.box` takes full extents) and spaced with 60% gaps, so the grounding ray fell **between** the planks and would have dropped a character off the deck into the bog | planks laid nearly touching, at full deck width |
| `COLLISION_SURFACE_MISMATCH` | boardwalks were modelled from their near end while the collision pass claims a deck footprint symmetrically about the placement, so each span marked its own length of open bog walkable at deck height | the mesh is built centred and placed at the span's midpoint |
| `LANDMARK_FLOATING` (16) | tower, dead-tree and Hanged Oak markers sat at each feature's visual centre | markers moved to where a player stands to look at the thing |

## Collision binary

| | |
| --- | --- |
| format | `EWCG` v1 |
| dimensions | 1152 x 1152 half-metre cells |
| dimensions ÷ 6 | 192 x 192 — positive multiples of six, as required |
| walkable | 1,171,807 cells (88.3%) |
| blocked | 155,297 cells |
| saturated | 35,770 cells (3.05% of walkable) |
| elevated decks | 11 |
| row order | server-tile-Y; row 0 is the +Z southern edge |
| column order | server-tile-X; column 0 is the −X western edge |

Row order is the trap the production guide warns about — writing rows the other
way silently mirrors every walkability decision. `verify_runtime.py`'s
cell-to-surface cross-check is what catches it, and it passes: the encoded
heights agree with the rendered walk surface everywhere it sampled.

The 3.05% saturation is the rim shoulders, discussed in
`modeling-assumptions.md`. Everywhere else the encoded height is the real
surface height, so the server has genuine elevation rather than a flat plateau.

## Manifest

`world.json` was checked against
`godot-client/schemas/world-manifest-1.schema.json` with `jsonschema`'s
Draft 7 validator: **0 schema errors**. It carries every required block:

bounds and playable bounds, coordinate transform, 7 spawn points, collision,
navigation, 61 landmarks, interactives, 15 NPC/creature markers, 64
harvestables, 6 portals, roads, water, environment, minimap transform, LOD
groups, performance, sources, provenance, production status, known limitations.

Navigation uses `surfaceNodePrefixes: ["Terrain_", "Walk_"]`. Only terrain
sub-meshes and the boardwalk and causeway-bridge decks carry those prefixes;
no structural geometry does, so the grounding ray cannot snap an actor onto a
tower, a croft roof or the top of a menhir.

## Server-side agreement

The regenerated `server-collision/grey_moors.bin` is 341,112 bytes, 96 x 96 tiles,
576 x 576 height cells, 88.3% walkable — byte-identical in size and shape to
Amethyst Barrens' and Crownwater's, which is what the server's collision
contract test asserts.

On `eloria-server`, branch `feature/grey-moors-96-server-map`: the four Nymara
and content modules pass (14 passed). The wider suite reports **81 failures with
the change and 81 with it stashed** — none introduced, none fixed.

## What was NOT verified

Stated plainly, because the clean reports above do not cover any of it:

- **End-to-end play.** No login, no server connection, no character walking this
  map. The grounding contract is verified offline against the same geometry and
  the same rule the client uses, and separately observed in real client frames,
  but nobody has walked it.
- **The region's authored weather in the client.** The frames in
  `references/client-captures/` are real Godot 4.7.2 renders through the
  client's own `WorldLoader.load_world()`, but `godot_capture.gd` lights every
  region identically so regions can be compared. The `environment` block in
  `world.json` has therefore never been seen applied.
- **Performance on a real target machine.** The triangle and texture numbers in
  `performance-summary.md` are counted from the package, not measured as a
  frame rate. Nothing streams and nothing switches LOD yet; `world-lod2.glb`
  exists but nothing selects it.
- **Every place name.** All of them are placeholders — see
  `modeling-assumptions.md`.
- **The interior map.** `maps/nymara/grey_moor_barrows.elm` is what the four
  doors target. It is not built by this package and was not built here.
- **The minimap in the client UI.** It is rendered from the final geometry
  rather than drawn, and its transform is in the manifest, but it has not been
  seen in the client's map screen.
