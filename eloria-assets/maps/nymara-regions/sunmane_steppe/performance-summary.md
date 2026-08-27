# Sunmane Steppe performance summary

## Package cost

| Measure | LOD1 | LOD2 |
|---|---:|---:|
| GLB bytes | 14,447,996 | 7,189,332 |
| Unique mesh triangles | 167,847 | 101,071 |
| Meshes | 172 | 107 |
| Nodes | 747 | 213 |
| Materials | 27 | 25 |
| Embedded textures | 27 | 27 |
| Terrain triangles | 51,200 | 51,200 |
| Kit unique triangles | 41,211 | 39,939 |
| Kit instances | 607 | 129 |
| Ground-cover triangles | 60,940 | 0 |
| Landmarks / interactives | 77 / 61 | 77 / 61 |

LOD2 is 50% smaller on disk
and carries 71% fewer nodes while
keeping the terrain, the architecture and the whole landmark inventory.

Embedded texture payload is 4.29 MiB of PNG at LOD1 across nine
tileable material families. ORM and normal maps are stored at half the
base-colour resolution because both carry lower-frequency information than the
albedo they accompany, and tangents are emitted only for the primitives whose
material actually has a normal map - which is why the Khronos validator reports
zero warnings for both packages.

## Measured in the running client

Godot 4.7.2, `gl_compatibility` renderer, 1280x720, adapter
`llvmpipe (LLVM 20.1.2, 256 bits)`.

**These frame times are software rasterisation.** This session had no GPU, so
Mesa's llvmpipe rendered every frame on the CPU. The absolute milliseconds are
not a prediction of player frame rate. The useful figures are the relative costs
between packages and views, the draw-call and primitive counts, and the geometry
and memory totals, all of which are hardware independent.

| Package | View | Draw calls | Primitives | ms/frame (llvmpipe) |
|---|---|---:|---:|---:|
| LOD1 | gameplay-default | 2,216 | 577,110 | 408.96 |
| LOD1 | gameplay-zoomed-out | 2,739 | 644,181 | 434.0 |
| LOD1 | region-overview | 1,737 | 350,314 | 261.77 |
| LOD1 | low-settings-no-shadows | 909 | 216,408 | 162.95 |
| LOD1 | high-settings | 2,087 | 522,233 | 366.96 |
| LOD2 | gameplay-default | 1,587 | 418,335 | 352.26 |
| LOD2 | gameplay-zoomed-out | 1,856 | 411,269 | 355.69 |
| LOD2 | region-overview | 1,086 | 215,592 | 210.14 |
| LOD2 | low-settings-no-shadows | 624 | 158,242 | 144.82 |
| LOD2 | high-settings | 1,453 | 371,152 | 329.8 |

| Package | Load time | Mesh instances | Collision bodies | Ambient animals |
|---|---:|---:|---:|---:|
| LOD1 | 482.5 ms | 735 | 172 | 84 |
| LOD2 | 327.3 ms | 201 | 172 | 84 |

Renderer-reported GPU memory at the default gameplay camera, LOD1: texture
22.2 MiB, buffers
16.1 MiB.

## Against the repository's reference budget

`maps/four-gates-city/performance-summary.md` documents a desktop LOD1 budget of
1.5M visible triangles and 512 MiB of texture memory, and 350k triangles and
192 MiB on mobile.

| | Four Gates LOD1 | Sunmane LOD1 | Sunmane LOD2 |
|---|---:|---:|---:|
| GLB bytes | 14,447,996 | 7,189,332 | 7,189,032 |
| Nodes | 747 | 213 | 213 |
| Unique mesh triangles | 4,538 | 167,847 | 101,071 |
| Texture memory | 28 MiB | 22 MiB | - |

Sunmane carries far more unique geometry than Four Gates because its terrain is
a sculpted 208 m heightfield with real ground cover rather than a terraced
plateau, and because its architecture is authored rather than assembled from
scaled primitives. Both sit well inside the documented desktop budget; LOD2 sits
inside the mobile one.

Draw calls are the honest weak point: 2,216 at the
default gameplay camera against 1,587 for LOD2.
That is the cost of instancing several hundred authored props as plain glTF
nodes, which is what the current loader consumes; Four Gates sits in the same
range for the same reason at 1,750 nodes. Batching the small
props into per-chunk meshes would trade roughly 50k duplicated triangles for
about 600 fewer draw calls. It is deliberately not done here because the loader
has no multi-mesh path and triangles are the budget the repository documents,
but it is the first thing to try if a low-end target proves draw-call bound.
