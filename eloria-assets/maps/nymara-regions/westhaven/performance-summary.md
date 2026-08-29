# Westhaven: performance summary

Numbers counted from the package, not measured in a frame. See "What is not
here" at the bottom.

The machine-written figures live in `performance.json`; this file quotes them
and says what they mean. They are two files on purpose — a build that writes its
own JSON dump into the document is a build that clobbers the document.

## The budget

The repository's stated desktop guideline, from
`maps/four-gates-city/performance-summary.md`, is **1.5 M visible triangles and
512 MiB of texture**.

The target set for this region up front was **under 4 instanced triangles per
square metre**, on the reasoning that Westhaven is a masonry region with a
sparse tree belt rather than a forest, so Mirrorhold (3.8) is the right
calibration and Amberwood (9.4) is not.

## What it came out at

| | `world.glb` | `world-lod2.glb` |
| --- | --- | --- |
| file size | 21.60 MB | 13.67 MB |
| nodes | 4,419 | 3,629 |
| unique triangles | 452,652 | 369,474 |
| instanced triangles | 1,137,392 | 955,676 |
| unique meshes | 252 | 240 |
| materials | 24 | 23 |
| placements | 1,900 | 1,594 |
| embedded texture bytes | 19.96 MB | 12.4 MB |

**3.43 instanced triangles per square metre** over the 576 m x 576 m playable
square. Inside the target, inside the guideline, and just under Mirrorhold's
3.8 — which is the right neighbourhood for a stone region.

For calibration against the two regions that bracket the range:

| region | instanced triangles | tris/m² | package |
| --- | --- | --- | --- |
| Amberwood | 3,123,378 | 9.4 | 28.7 MB |
| Mirrorhold | 1,246,632 | 3.8 | 16.1 MB |
| **Westhaven** | **1,137,392** | **3.43** | **21.6 MB** |
| Four Gates | 4,538 | — | 3.0 MB |

Westhaven is denser in bytes than Mirrorhold at fewer triangles because it
carries more distinct materials: nine of its own plus fifteen shared, against a
mostly-stone palette.

## Where the triangles are

| | instanced triangles | share |
| --- | --- | --- |
| terrain (7 surface sub-meshes) | ~206,600 | 18% |
| water (one sea plane) | ~90,000 | 8% |
| city houses (385 instances, 12 variants) | ~430,000 | 38% |
| trees (257 instances, 3 species x 3 tiers) | ~180,000 | 16% |
| ground dressing (536 instances) | ~64,000 | 6% |
| harbour works, ships, landmarks, props | ~166,000 | 14% |

Instancing is what makes this affordable. 385 houses draw from 12 meshes and
257 trees from 9, so the city and the tree belt together are 21 unique meshes
and 642 nodes.

## The levers that were actually pulled

In the order the guide recommends, cheapest first:

1. **Ground-dressing subdivision.** The sea plane was the single biggest item
   in the first build: at a 3.5 m cell over a 240 m reach it was 203,000
   triangles — more than half the whole region's geometry, for flat water. At
   4.5 m it is 90,000 and the waterline is not visibly worse.
2. **One water body instead of two.** A separate harbour plane cost triangles
   and z-fought with the sea plane. Dropped; the distinction moved to the water
   shader's depth tint.
3. **Per-instance detail tier.** Trees are placed at `high` within 130 m of the
   spawn, `mid` to 300 m, `low` beyond. The LOD2 package forces `low`.
4. **No landmass backdrop.** Amberwood ships one; Westhaven does not need it
   and it was ~40,000 triangles of coarse rock.
5. **The material pin.** `shingles`, `cobble_paving`, `bark_pale` and
   `water_sea` were pinned and unreferenced — each superseded by a Westhaven
   recipe — and were embedding their textures for nothing. Removing them took
   1.4 MB off the package. The LOD pin drops `undergrowth` as well, which the
   reduced build does not use. This is the exact mistake the production guide
   records Amberwood making at a cost of 2.79 MB, and the build's own
   unreferenced-material warning is what caught it.

Texture bytes dominate: 19.96 MB of the 21.60 MB package is embedded imagery.
ORM maps are compacted to 256 px; base colour and normals stay at 512.

## LOD2

`world-lod2.glb` is 36.7% smaller and carries 16.0% fewer instanced triangles.
The size reduction is much larger than the triangle reduction because the
reduced package also halves texture resolution, and textures are where the
bytes are.

Nothing streams or switches LOD at runtime yet. The second package exists to be
swapped in wholesale.

## What is not here

- **No frame was profiled.** These are static counts from the built package.
  No draw-call count, no GPU timing, no measurement on real hardware at any
  resolution.
- **No memory figure for the loaded scene.** The 512 MiB texture guideline is
  quoted for context; what Godot actually allocates after import was not
  measured.
- **LOD2 was not rendered in the engine.** It validates and loads through the
  offline path only.
- **No streaming budget**, because nothing streams.
