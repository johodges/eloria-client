# Mirrorhold validation report

What was checked, what passed, and — the part that matters — what was not
checked and could not be.

## Automated checks at the committed build

### `validate_gltf.py ../world.glb`

```
errors=0 warnings=0 infos=0
```

Standalone glTF 2.0 / GLB validation: buffer and accessor bounds, index ranges,
component types, normal length, UV presence, material and texture references,
node hierarchy, and that the file is self-contained with no extensions and no
external resources.

### `verify_runtime.py --package ..`

```
[nav] 30 walk-surface nodes, 206678 triangles
[grounding] 331776 tiles sampled, 0 misses (0.00%)
[collision] 1152x1152, 50.3% walkable
[verify] 0 errors, 3 warnings
```

This reproduces the client's contract offline: it reads the manifest, resolves
every declared collision node in the scene, turns every `MeshInstance3D` whose
name begins with a `navigation.surfaceNodePrefixes` entry into a walk surface,
and casts the grounding ray from y = 400 to y = -100 at the centre of **every
one of the 331,776 reachable server tiles**. Zero misses means no tile falls
through to `walkingHeight`, which is the failure that drops or floats a
character.

The three warnings, each deliberate:

| Warning | Count | Why it is expected |
| --- | --- | --- |
| `GROUNDING_DISCONTINUITY` | 434 | Adjacent tiles differing by more than 6 m. This is a terraced mountain with 195 m of relief; every terrace face, cliff and retaining wall produces them. For scale, Amberwood at 100 m of relief has 811. |
| `COLLISION_SURFACE_MISMATCH` | 1 | One sampled cell of 331,776 where the encoded collision height disagrees with the rendered walk surface, at a deck edge. |
| `LANDMARK_FLOATING` | 1 | The armillary, which is a sphere on a mount above its drum. It is meant to be off the ground. |

### `region_client_check.gd` — the same contract, in-engine

The offline check above reproduces the client's contract in Python. This one
runs it the other way round: Godot 4.7.2 loads the package with the project's
own `WorldLoader.load_world()`, lets it build collision and navigation exactly
as the game does, and casts `main.gd`'s grounding ray - y = 400 down to
y = -100 on `NAVIGATION_SURFACE_LAYER` - against the real physics world.

```
[client-check] loader warnings=1
    warning: navigation polygons did not produce collision
[client-check] server grid 576x576, sampling every 4 tiles
[client-check] grounding: 20736 tiles sampled, 0 misses (0.00%)
[client-check] surface height range: -11.00 .. 257.01
[client-check] spawn { "id": "default", manifestY 42.68, clientY 42.626, delta 0.054 }
[client-check] spawn { "id": "harbour", manifestY 4.55, clientY 4.68, delta 0.13 }
[client-check] spawn { "id": "citadel-gate", manifestY 84.05, clientY 83.999, delta 0.051 }
[client-check] PASS
```

So the offline verifier and the engine agree: no reachable tile falls through
to `walkingHeight`, and every spawn's manifest height is where the client
actually puts an actor standing there. The full report is in
`client-check-report.json`.

The one loader warning is structural and shared with Amberwood: this manifest's
`navigation.navmesh` is `surface-prefix-v1` with an empty `polygons` list,
because navigation is derived from the surface prefixes rather than from baked
polygons. The loader warns whenever that list is empty. Amberwood's manifest is
identical in this respect.

This is a sampled check - every fourth tile in each axis, 20,736 of 331,776 -
because it runs through the physics server rather than a numpy array.
`verify_runtime.py` samples all of them.

### Determinism

A cache-cold rebuild reproduces `world.glb`, `world-lod2.glb`, `world.json`,
`collision.bin`, `minimap.webp` and `performance-summary.md` byte-for-byte.
This had to be fixed before it was true: see `change-log.md`.

### Server side

`generate_nymara_maps.py` on `feature/mirrorhold-576m-server-map` produces a
576 x 576 collision grid for Mirrorhold with a walkable arrival at (174, 174),
and the four Nymara/content test files pass (19 tests). The wider server suite
has 80 pre-existing failures, identical with and without this change.

## Captures

Two independent sets, and **the distinction matters**:

- `references/captures/` — the **offline preview renderer** (`_toolkit/native`,
  a small C rasteriser). These are not the game. They are the authoring
  previews, and they are what the comparison sheets are built from.
- `references/godot-captures/` — **real client frames**. Rendered by Godot
  4.7.2 on a Vulkan Forward+ device, loading `world.glb` through
  `GLTFDocument.append_from_buffer` exactly as a runtime package, with no
  import step and no scene file. These are genuine engine output.

## What was NOT verified

Stated plainly, because a clean validator report covers less than it looks like
it covers.

1. **No end-to-end client session.** The package is loaded, rendered and
   grounded through the real client path - `WorldLoader` and the engine's own
   physics - but nothing here logged in, connected to a server, spawned a
   networked character, or walked around under player control. What is proven
   is that the world builds and grounds correctly in the engine, not that a
   session works.

2. **No server round-trip.** The 96 x 96 map generates and the tests pass, but
   no server was started, no client connected to one, and no map transition was
   taken. The portal entries are alignment metadata.

3. **Every name is invented.** No authoritative written description of
   Mirrorhold was available to this build. "The Orrery", "The Lens Gate", "The
   Drowned Crown", "The Stair Town" and all the rest are placeholders chosen to
   fit the concept art, and should be expected to be replaced. The one
   exception is that the ring is called The Drowned Crown because the client
   registry already points an interior map id of that name at this region.

4. **The detail board in this repository is still truncated.** Every region
   package ships `references/00-concept-detail-board.png` cut to 786,446 bytes,
   of which only the top row of five panels decodes. The panel-level modelling
   in this build was done against an intact copy supplied in conversation, but
   that copy could not be written to disk. So:
   - panels 1–5 in `comparison-report.md` compare against a real concept image;
   - panels 6–10 compare against nothing, and are marked
     `concept UNAVAILABLE` on the sheet rather than being quietly shown as grey.

   Replacing the file and re-running `make_comparison.py` is all that is needed.

5. **Built density is below the concept.** The aerial painting has terraces and
   structures across its whole middle band. This build has the citadel, the
   civic descent, the stair town and eighteen satellite sites, which reads as a
   coherent region but a quieter one than the painting. The east quarter and
   the far south are the thinnest. This is a judgement about how much is
   enough, not a defect, but it is the largest gap between the concept and the
   build.

6. **No performance measurement on real hardware.** The triangle and texture
   figures in `performance-summary.md` are counted from the GLB. No frame time
   was measured; nothing streams and nothing switches LOD.

7. **No interiors.** The two interior entrances point at map ids the registry
   carries. Those packages are not part of this work.
