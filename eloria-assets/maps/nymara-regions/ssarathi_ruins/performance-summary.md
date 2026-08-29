# Ssarathi Ruins performance summary

Measured on the shipped package, not estimated. Numbers come from
`world.json`'s `performance` block, which the build writes from the exporter's
own counts.

## Budgets

The repository's stated desktop guideline is **1.5 M visible triangles and
512 MiB of texture**, from `four-gates-city/performance-summary.md`.

| | Ssarathi Ruins | LOD2 |
| --- | --- | --- |
| Unique triangles | 394,853 | 337,798 |
| Instanced triangles | **1,879,571** | 854,588 |
| Triangles per square metre | **5.67** | 2.58 |
| Nodes | 7,717 | 3,189 |
| Placements | 2,895 | — |
| Package size | 19.4 MB | 12.6 MB |
| Embedded texture bytes | 19.5 MB | — |
| Texture memory, uncompressed | 174 MiB | — |

At 5.67 triangles per square metre over 576 m x 576 m the region sits between
Mirrorhold (3.8, inside the guideline) and Amberwood (9.4, about 2.1x it), and
is about **1.25x the desktop guideline** at LOD1. `world-lod2.glb` is 854,588
instanced triangles, comfortably inside it. Nothing in the current Godot loader
selects between the two, and nothing streams.

Texture memory is well inside the 512 MiB budget: 174 MiB uncompressed across
24 materials and 66 embedded images.

## Where the triangles are

The region is a *dense* composition rather than a tall one, so the count is
dominated by instance repetition rather than by any single landmark.

| Group | Roughly |
| --- | --- |
| Vegetation — 2,089 trees and palms across two species and three detail tiers, plus 348 undergrowth clumps | the majority of instanced triangles |
| The quarters — 55 ruin buildings, 21 towers and their rubble, on 69 generated blocks | the largest built group |
| Terrain — five surface-class sub-meshes over a 319 x 319 heightfield at 2 m | 206,578 triangles carry the walk surface alone |
| The temple — one 7,166-triangle ziggurat, instanced once | the tallest silhouette, not the heaviest |
| Water — one clipped plane at 3 m cells over the whole basin | |

## The levers that were used

In the order the production guide recommends them:

1. **Per-instance detail tier.** Trees are chosen from near/mid/far by radial
   distance from the ceremonial axis, so the rim — which is most of the
   region's area — is far-tier. Raising the tree spacing from 11 m to 8.5 m
   roughly tripled the tree count without tripling the cost, because almost all
   of the new instances landed on the rim.
2. **Instance, never duplicate.** 2,895 placements share 89 unique meshes.
   Balustrades are one mesh per length class, bridges one per (span, width)
   class, ruin buildings one per 3 m size class.
3. **ORM at 256 and no normal map on alpha-cut foliage** (`TextureSet.compact`),
   which is why 24 materials fit in 19.5 MB.
4. **Cards for foliage silhouettes.** Lily pads, palm fronds and vines are
   alpha-cut quads from atlases, two triangles for a shape that would otherwise
   cost twenty.

## What was measured against what

Every build printed its counts and they were checked against this target each
time. The largest single jump was the massing pass that fills the quarters
between the streets: it took the region from 1.30 M to 1.88 M instanced
triangles, and it is the reason the region reads as a city rather than as a
causeway network on an empty lake. That was a deliberate spend.

## Not measured

No frame timing, no draw-call count and no GPU memory figure: this build has
real Godot frames (see `references/client-captures/`) but no profiling session,
and a triangle budget is not a frame budget. A reviewer with the client running
should check draw calls in particular — the loader batches static instances
into 41 `MultiMeshInstance3D` groups for this package, which is the number that
matters more than the triangle count.
