# Amberwood validation report

## glTF 2.0

`source/validate_gltf.py` implements the structural and semantic checks that
matter for Godot's `GLTFDocument` import path — chunk structure, accessor bounds
against buffer views, declared min/max against actual data, index range against
vertex count, unit-length normals, tangent handedness, material and texture
references, embedded image signatures, node parenting and cycles, scene roots,
and node-name uniqueness. It was written for this project because the Khronos
`gltf-validator` binary cannot be fetched in the build environment; run against
the repository's own `four-gates-city.glb` it agrees with the committed Khronos
report (0 errors, 0 warnings).

Result for `world.glb`: **0 errors, 0 warnings** (`world.glb.validator.json`).
Result for `world-lod2.glb`: **0 errors, 0 warnings**
(`world-lod2.glb.validator.json`).

The package uses no glTF extensions, declares none as required, embeds every
buffer and image, and uses triangles only.

## Runtime contract

`source/verify_runtime.py` reproduces what the client does at load time rather
than trusting that it will work:

* It rebuilds the navigation surface exactly as `WorldLoader` does — every mesh
  node whose name begins with a `navigation.surfaceNodePrefixes` entry, with
  accumulated node transforms.
* It casts the same downward ray `Main._place_actor_on_surface` uses at the
  centre of **all 36,864 reachable server tiles**.
* It cross-checks the collision grid's encoded heights against that surface.

Result:

| Check | Result |
| --- | --- |
| Walk-surface nodes / triangles | 29 nodes, ~181,700 triangles |
| Server tiles sampled | 147,456 (every reachable tile of the 384-cell map) |
| Grounding-ray misses | **0** — no tile where an actor would fall back to `walkingHeight` |
| Spawn points grounded | 3 / 3, each within 0.05 m of the surface, with even ground around them |
| Collision binary | `EWCG` v1, 768 x 768, dimensions multiples of six, payload size exact |
| Collision cells disagreeing with the rendered surface | 1 of ~4,000 sampled (a cliff face) |
| Errors | **0** |
| Warnings | 3 |

The warnings are expected and documented:

* `GROUNDING_DISCONTINUITY` — adjacent tiles whose surface height differs by
  more than 6 m. These are the ravine walls, the coastal cliffs and the edges of
  the canopy platforms, which own their footprint by design.
* `LANDMARK_BELOW_SURFACE` for `great-tree` — the landmark anchor is the tree's
  base, and a canopy platform sits 15 m above it. That is the intended layout.
* `COLLISION_SURFACE_MISMATCH` on one sampled cell, where the collision grid's
  bilinear terrain sample and the rendered triangle disagree by 13 m on a cliff
  face. The cell is on a 45-degree slope and is not reachable ground.

## What has **not** been verified

This build was produced in an environment with no GPU, no Godot binary and no
access to `eloria-server`. Three classes of check in the brief could not be run
here and are the first things a reviewer should do:

1. **In-client rendering.** Every capture in `references/captures/` comes from
   the offline software renderer in `source/amberwood/render.py`, driven by the
   same material table the GLB ships (`source/amberwood/materials.py`). It is a
   faithful preview, not Godot: alpha-cutout ordering, shadow filtering, LOD and
   culling behaviour must still be confirmed in the real client.
2. **End-to-end login and movement.** No local server could be started, so
   click-to-move, WASD, camera, portals, tab map and coordinate reporting are
   unverified against the live protocol. The grounding contract they depend on
   is verified offline above.
3. **Lore and naming.** The written Amberwood region description named in the
   brief was not available, and `eloria-server` could not be read. Every place
   name in `world.json` is a placeholder — see `modeling-assumptions.md`.
