# Amethyst Barrens — performance summary

Measured from the committed `world.glb`. Region area is 576 m x 576 m
= 331,776 m^2.

| | |
| --- | --- |
| `world.glb` | 19.53 MB |
| Nodes | 942 |
| Meshes | 229 |
| Materials | 13 |
| Embedded images | 39 |
| Unique triangles | 444,452 |
| Instanced triangles | 601,820 |
| Placements | 483 |
| Embedded texture bytes | 4.25 MB |
| **Unique triangles / m^2** | **1.34** |
| **Instanced triangles / m^2** | **1.81** |

## Against the guideline

The repository's stated desktop guideline, from
`four-gates-city/performance-summary.md`, is 1.5 M visible triangles and
512 MiB of texture.

At 601,820 instanced triangles this region is **40% of the triangle budget**
with the whole map resident, and 4.25 MB of embedded texture. Nothing streams
and nothing switches LOD, so that is the worst case rather than an average.

For calibration: Amberwood at the same 576 m extent is 3,146,376 instanced
triangles and 29.0 MB, about 9.5 triangles per square metre and roughly 2.1x
the guideline. Amethyst Barrens is a little over a seventh of that density.

That is not a virtue. A storm-scoured basin is genuinely emptier than an autumn
forest, but the concept art is denser than this build — see
`comparison-report.md`. The headroom between 1.81 and the ~4.5 triangles per
square metre that would still sit inside the guideline is where the missing
spires, ruin fields and roadside structures should go.

## Where the bytes are

Geometry dominates, which is unusual for this toolkit and is a direct result of
pinning the material set. The build passes `only=<used set>` to
`register_gltf_materials`, so the package embeds the 13 materials it uses rather
than all 46 in the shared table. Embedding the whole table would add roughly
10 MB of PNG per region kit for textures nothing references.

Texture maps are trimmed by `TextureSet.compact` at ORM 256, with normal maps
kept at full resolution for the ground classes where they carry the most.

## Cheapest levers, if this needs to come down

1. Per-instance detail tier on the crystal outcrops (260 placed, ~390 triangles
   each) - the single largest instanced contribution.
2. Ground-dressing counts: 112 rock clusters and 207 vein scatters.
3. Terrain cell size, currently 2.0 m. The terrain sub-meshes are 205,564
   triangles of the 444,492 unique total.
4. Unique kit variant count - 8 outcrop variants, 5 vein-scatter variants.

## Not measured

No frame timing. There is a GPU here and the map loads and renders through the
real `WorldLoader`, but no FPS, draw-call count or GPU memory figure was taken;
the capture harness renders single frames with a settle delay, which says
nothing about sustained performance. The `world-lod2.glb` reduced package was
not built for this region.
