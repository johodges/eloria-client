# Grey Moors — performance summary

Measured from the September 2026 package. These are asset counts, not frame-rate
measurements. Sizes below use decimal MB; texture memory uses MiB.

| Metric | Full package | Reduced package |
| --- | ---: | ---: |
| GLB size | 31.09 MB | 17.19 MB |
| Nodes | 7,681 | 798 |
| Unique triangles | 436,256 | 404,278 |
| Instanced triangles | 757,336 | 417,746 |
| Meshes | 652 | — |
| Materials | 46 | — |
| Embedded images | 106 | — |
| Embedded texture data | 13.79 MB | — |
| Uncompressed texture memory | 103.1 MiB | — |
| Placements | 7,165 | — |

The full package contains 2.28 instanced triangles
per square metre of its 576 m × 576 m footprint. Relative to the preceding
package, this layout adds 122,932 bytes and removes 3,858 instanced triangles.
The reduced package adds 350,596 bytes and 9,730 instanced triangles.

The added cost is the continuous surveyed crossings, refuge and larger barrow
crown. Clearing route obstructions and clipping the backdrop reduce other
geometry. The full build still reuses meshes for ground scrub, erratics and
standing stones. Material classes retain their existing identifiers.

The historical desktop guideline in four-gates-city/performance-summary.md
is 1.5 million visible triangles and 512 MiB of textures. The package's
0.76 million instanced triangles and 103.1 MiB of uncompressed texture data
sit below those asset budgets, but do not predict a frame rate or total
runtime memory. Visible triangles, batching, shadow costs and runtime service
objects depend on the client.

Both GLBs passed validation with zero errors and warnings. The package was
reviewed in Godot GL Compatibility with its own manifest environment. No
play-session benchmark was performed. Reachability and correction-pass results
are in layout-review.md; raw build collision counters precede those passes.
