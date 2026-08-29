# Grey Moors — performance summary

Counted from the shipped package by the build, not measured as a frame rate.
Nothing here has been run on a target machine.

## The numbers

| | `world.glb` | `world-lod2.glb` |
| --- | --- | --- |
| file size | 23.00 MB | 12.49 MB |
| nodes | 7,648 | 461 |
| unique triangles | 352,490 | 314,680 |
| instanced triangles | 674,110 | 314,680 |
| meshes | 391 | — |
| materials | 22 | 22 |
| embedded images | 65 | 65 |
| embedded texture bytes | 9.15 MB | — |
| texture memory, uncompressed | 60.9 MB | — |
| placements | 7,331 | — |

**2.03 instanced triangles per square metre** over the 576 m × 576 m footprint.

## Against the budget

The repository's stated desktop guideline, from
`four-gates-city/performance-summary.md`, is 1.5 M visible triangles and 512 MiB
of texture. Grey Moors is at **0.67 M triangles and 61 MiB of texture** — inside
the guideline on both counts, with room to spare.

Against the two regions that bracket the range:

| region | instanced triangles | per m² | GLB |
| --- | --- | --- | --- |
| Amberwood | 3,123,378 | 9.4 | 31.5 MB |
| Mirrorhold | 1,246,632 | 3.8 | 16.1 MB |
| **Grey Moors** | **674,110** | **2.03** | **23.0 MB** |

Grey Moors is the lightest 576 m region so far, and that is a property of the
subject rather than restraint: it has no forest and no city. Amberwood spends
most of its budget on trees; Mirrorhold on masonry. A moor is ground, stone and
water, and ground is cheap.

**The target was set up front at 2–4 triangles per square metre** and measured
every build. An early pass came in at 1.13 — visibly bare — and the ground
cover was raised deliberately to close that, not to hit a number.

## Where the triangles are

| | approx. instanced triangles |
| --- | --- |
| terrain, multi-material, crack-free | 228,000 |
| distant backdrop | 8,000 |
| ground scrub (6,048 clumps, ~2 sided cards each) | ~250,000 |
| scattered standing stones (360) and erratics (778) | ~37,000 |
| dead trees (10, grown skeletons) | ~35,000 |
| barrow portals, crypts, towers, crofts, peat works | ~90,000 |
| boardwalks, causeway bridges, rings, avenue | ~26,000 |

The single largest lever is ground scrub, and it is the one that most changes
whether the region reads as a moor. It is spent deliberately.

## Where the bytes are

Texture data is 9.15 MB of the 23.00 MB package; the rest is geometry. Every
ORM map is trimmed to 256 and the alpha-cut scrub atlas ships without a normal
map, which is `TextureSet.compact`'s doing and costs nothing visible.

The package embeds **only the 22 materials this region uses**, via `only=` on
`register_gltf_materials`. With several regions appending kits to the shared
material table, embedding all of them would add roughly ten megabytes of PNG per
foreign kit for no gain.

## Batching

The client collapses groups of four or more identical opaque meshes into one
`MultiMeshInstance3D` per 180 m spatial cell. Grey Moors is built for that: the
6,048 scrub clumps reference 14 meshes, the 360 standing stones reference 10,
and the 778 erratics reference 8. 7,648 nodes reference 391 meshes.

## Caveats

- Nothing streams. The whole package loads at once.
- Nothing switches LOD. `world-lod2.glb` is built and validated but no code
  selects it.
- No frame rate has been measured, on any machine, at any resolution. The real
  client frames in `references/client-captures/` were rendered offscreen at
  1600 × 1000 on an RTX 5080 laptop GPU; that is not a play-session benchmark.
