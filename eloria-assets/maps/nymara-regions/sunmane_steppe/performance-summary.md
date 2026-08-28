# Sunmane Steppe performance summary

## Package cost

| Measure | LOD1 | LOD2 |
|---|---:|---:|
| GLB bytes | 18,407,036 | 9,169,492 |
| Unique mesh triangles | 229,363 | 136,047 |
| Meshes | 255 | 159 |
| Nodes | 1,041 | 312 |
| Materials | 31 | 29 |
| Embedded textures | 30 | 30 |
| Terrain triangles | 80,000 | 80,000 |
| Kit unique triangles | 46,827 | 45,555 |
| Kit instances | 834 | 192 |
| Ground-cover triangles | 87,480 | 0 |
| Landmarks / interactives | 102 / 70 | 102 / 70 |

LOD2 is 50% smaller on disk and carries 70% fewer nodes while keeping the terrain, the architecture and the whole landmark inventory. It drops the ground clutter, the roadside dressing and half the texture resolution.

The embedded texture payload is 4.00 MiB of PNG at LOD1 across the ten tileable material families this package actually uses. `textures/` carries all twelve authored families as editable source; `cavern` and `hide` are used by the cave interiors and the ambient horses respectively and are embedded in those packages, not this one. ORM and normal maps are stored at half the base-colour resolution because both carry lower-frequency information than the albedo they accompany, and tangents are emitted only for the primitives whose material actually has a normal map - which is why the Khronos validator reports zero warnings for both packages.

## Measured in the running client

Godot 4.7.2, `gl_compatibility` renderer, 1280x720, adapter `llvmpipe (LLVM 20.1.2, 256 bits)`.

**These frame times are software rasterisation.** This session had no GPU, so Mesa's llvmpipe rendered every frame on the CPU. The absolute milliseconds are not a prediction of player frame rate. The useful figures are the relative costs between packages and views, the draw-call and primitive counts, and the geometry and memory totals, all of which are hardware independent.

| Package | View | Draw calls | Primitives | ms/frame (llvmpipe) |
|---|---|---:|---:|---:|
| LOD1 | gameplay-default | 2,807 | 674,874 | 366.49 |
| LOD1 | gameplay-zoomed-out | 3,261 | 725,655 | 406.77 |
| LOD1 | region-overview | 2,391 | 462,789 | 299.47 |
| LOD1 | low-settings-no-shadows | 1,378 | 293,251 | 157.17 |
| LOD1 | high-settings | 2,831 | 642,330 | 342.84 |
| LOD2 | gameplay-default | 2,160 | 498,339 | 333.88 |
| LOD2 | gameplay-zoomed-out | 2,269 | 471,071 | 334.61 |
| LOD2 | region-overview | 1,519 | 283,617 | 242.15 |
| LOD2 | low-settings-no-shadows | 989 | 214,168 | 132.03 |
| LOD2 | high-settings | 2,132 | 472,145 | 293.02 |

| Package | Load time | Mesh instances | Collision bodies | Ambient animals |
|---|---:|---:|---:|---:|
| LOD1 | 718.1 ms | 1029 | 241 | 111 |
| LOD2 | 441.5 ms | 300 | 241 | 111 |

Renderer-reported GPU memory at the default gameplay camera, LOD1: texture 22.64 MiB, buffers 19.43 MiB.

## Cave interiors

| Measure | Wind Caves | Crystal Hollow |
|---|---:|---:|
| GLB bytes | 4,147,168 | 4,302,312 |
| Unique mesh triangles | 17,405 | 17,882 |
| Cavern shell triangles | 12,740 | 13,164 |
| Nodes | 201 | 223 |
| Meshes | 57 | 64 |
| Kit instances | 167 | 184 |

Each interior is about a fifth of the surface package on disk and an order of magnitude cheaper in geometry: a cave is a small volume with no terrain grid, no vegetation and no distant scenery, and its shell is two surfaces over roughly 3,000 open cells rather than a 201 x 201 heightfield.

## Against the repository's reference budget

`maps/four-gates-city/performance-summary.md` documents a desktop LOD1 budget of 1.5M visible triangles and 512 MiB of texture memory, and 350k triangles and 192 MiB on mobile.

| | Sunmane LOD1 | Sunmane LOD2 |
|---|---:|---:|
| GLB bytes | 18,407,036 | 9,169,492 |
| Nodes | 1,041 | 312 |
| Unique mesh triangles | 229,363 | 136,047 |
| Peak primitives in frame | 725,655 | 471,071 |
| Texture memory | 22.64 MiB | 12.23 MiB |

Both sit well inside the documented desktop budget; LOD2 sits inside the mobile one. Sunmane carries far more unique geometry than Four Gates because its terrain is a sculpted 280 m heightfield with real ground cover rather than a terraced plateau, and because its architecture is authored rather than assembled from scaled primitives.

Draw calls remain the honest weak point: 2,807 at the default gameplay camera against 2,160 for LOD2, up from the pre-expansion figures because the desert, badland and mountain ground added several hundred more instanced props. That is the cost of instancing authored props as plain glTF nodes, which is what the current loader consumes. Batching the small props into per-chunk meshes would trade duplicated triangles for roughly 600 fewer draw calls; it is deliberately not done here because the loader has no multi-mesh path and triangles are the budget the repository documents, but it is the first thing to try if a low-end target proves draw-call bound.
