# Map load times

What a region costs to load, phase by phase, what was done about it, and what
is left. Companion to `runtime-performance.md`, which covers the frame rather
than the load.

The client loads a region by handing Godot's runtime glTF importer an absolute
path to a 19-33 MB `world.glb`, then walking the result: material passes,
declared collision, walk surfaces, navigation polygons and static batching.
`WorldLoader.load_world()` does all of it on the main thread, so a load is a
freeze, and the freeze was up to eight seconds.

## Measuring

`WorldLoader` times its own steps into `load_phases`, a microsecond per phase
in the order it runs them. `tests/integration/map_load_phases.gd` reads that
over every region and writes the table below as JSON:

```
Godot --headless --path . --script res://tests/integration/map_load_phases.gd
```

`ELORIA_PHASE_REGIONS` picks regions, `ELORIA_PHASE_REPEATS` sets how many
loads the median is taken over (3 by default), `ELORIA_ARTIFACT_DIR` says where
the JSON goes.

Three traps, all of which cost time here before they were understood:

* **Headless frames are padded** to `OS.low_processor_usage_mode_sleep_usec`,
  6.9 ms by default, because no window can draw. Every script in this file
  sets it to 1 and `Engine.max_fps` to 0. `sunmane_performance.gd` still
  reports 6.90 ms a frame for exactly this reason; its frame column is not a
  measurement.
* **This machine is shared** with about a dozen other agent sessions. A single
  load's wall time moves by a tenth either way, and the glTF parse column below
  moved 15% between two runs of the same code. Everything here is a median of
  three, and a difference under 10% is not a difference.
* **`GLTFState.HANDLE_BINARY_DISCARD_TEXTURES` does not skip decoding.** It
  drops the texture after Godot has decoded the image, so parsing with it is
  within noise of parsing without it, and it cannot be used to price the
  embedded PNGs. Pulling the image buffers out of the container and decoding
  them by hand can, and does: see the texture row in the options table.

## Where a load went

Median of three loads per region, headless, milliseconds, before this pass.
`manifest` is reading and validating `world.json`; `parse` is
`GLTFDocument.append_from_file`; `mipmaps` is the mip chain the loader rebuilds
over the imported images; `generateScene` is Godot's own scene builder;
`attach` is `add_child`; `index` is the single walk of the import; the rest are
the loader's own passes.

| region | manifest | parse | mipmaps | generateScene | attach | index | materials | collision | walkSurfaces | batching | **total** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| four_gates | 21.7 | 403.8 | 61.3 | 127.3 | 8.3 | 3.8 | 4.3 | 5.0 | 300.1 | 31.5 | **970** |
| mirrorhold | 27.9 | 405.7 | 47.7 | 173.4 | 11.6 | 3.7 | 2.1 | 64.3 | 495.2 | 19.4 | **1 263** |
| crownwater | 29.4 | 453.4 | 46.9 | 98.9 | 12.0 | 3.0 | 1.1 | 11.8 | 514.4 | 10.0 | **1 158** |
| whitehorn_range | 26.5 | 333.9 | 31.3 | 139.5 | 16.5 | 6.6 | 3.6 | 28.1 | 501.9 | 33.6 | **1 119** |
| amethyst_barrens | 28.3 | 309.4 | 31.1 | 79.6 | 4.7 | 1.5 | 1.0 | 14.5 | 465.2 | 14.3 | **955** |
| sunmane_steppe | 25.0 | 170.0 | 15.7 | 90.0 | 6.0 | 1.2 | 1.2 | 72.8 | 131.8 | 7.7 | **528** |
| amberwood | 25.3 | 434.9 | 46.3 | 3 437.8 | 17.7 | 11.7 | 8.5 | 229.6 | 428.4 | 39.9 | **4 675** |
| grey_moors | 18.4 | 420.4 | 46.6 | 2 220.1 | 18.8 | 9.3 | 5.8 | 88.1 | 492.6 | 29.2 | **3 348** |
| westhaven | 18.2 | 393.4 | 47.2 | 188.0 | 9.2 | 5.1 | 3.0 | 82.5 | 443.6 | 24.3 | **1 215** |
| verdant_stair | 24.6 | 620.4 | 46.7 | 6 144.5 | 34.1 | 23.1 | 12.6 | 13.2 | 705.6 | 60.1 | **7 926** |
| ssarathi_ruins | 23.7 | 496.1 | 61.4 | 202.4 | 12.5 | 11.5 | 5.5 | 6.7 | 669.7 | 41.3 | **1 545** |
| manymouth_delta | 27.3 | 652.3 | 55.9 | 1 845.3 | 19.8 | 18.6 | 10.0 | 7.6 | 739.6 | 66.6 | **3 405** |
| **twelve regions** | **296** | **5 094** | **538** | **14 747** | **171** | **99** | **59** | **624** | **5 888** | **378** | **28 106** |

Navigation polygons are 0.7 ms across all twelve: no shipped region declares
any, and the walk surfaces do that job.

The first frame drawn with the region in the tree is 3-8 ms, so texture upload
and the initial cull are not where the load is. Reading the glb off disk into a
buffer is 15-36 ms, so neither is I/O; the page cache is warm on every run here
and a cold first read on a slow disk is not measured.

And what a region is made of. `widest` is the largest sibling list in the
built tree, which turns out to be the column that matters:

| region | glb MB | nodes | mesh nodes | widest | batches | bodies | images | decoded MB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| four_gates | 23.2 | 4 255 | 3 028 | 1 276 | 241 | 456 | 95 | 60.0 |
| mirrorhold | 21.4 | 2 838 | 2 342 | 1 736 | 63 | 137 | 109 | 52.0 |
| crownwater | 31.9 | 2 437 | 1 402 | 440 | 29 | 217 | 89 | 44.0 |
| whitehorn_range | 18.6 | 4 970 | 3 813 | 1 951 | 164 | 41 | 86 | 40.6 |
| amethyst_barrens | 24.7 | 1 209 | 851 | 405 | 44 | 65 | 87 | 40.0 |
| sunmane_steppe | 18.4 | 1 625 | 1 050 | 1 106 | 44 | 259 | 30 | 10.4 |
| amberwood | 32.8 | 11 545 | 9 106 | 7 935 | 321 | 897 | 114 | 56.5 |
| grey_moors | 29.6 | 7 930 | 7 524 | 6 748 | 118 | 65 | 106 | 55.2 |
| westhaven | 28.5 | 4 235 | 3 526 | 1 816 | 167 | 66 | 106 | 55.0 |
| verdant_stair | 28.8 | 15 818 | 12 243 | 9 449 | 284 | 432 | 103 | 49.7 |
| ssarathi_ruins | 23.7 | 7 724 | 5 256 | 2 370 | 182 | 55 | 104 | 51.5 |
| manymouth_delta | 31.6 | 12 668 | 9 347 | 5 874 | 314 | 253 | 107 | 53.9 |

## What generate_scene was doing

`generate_scene` was 52% of the twelve-region load and effectively all of the
two worst regions. The third pass wrote it off as Godot's own code and not
addressable from here. It is addressable, and it is not the geometry.

`GLTFDocument` adds every node in the package with a readable name.
`Node.add_child(node, true)` checks the proposed name against the children the
parent already holds, so building a sibling list of *n* nodes costs the square
of *n*. The regions are built wide, and the cost tracks the width and nothing
else:

| region | widest sibling list | mesh nodes | generateScene |
| --- | ---: | ---: | ---: |
| four_gates | 1 276 | 3 028 | 127 ms |
| grey_moors | 6 748 | 7 524 | 2 220 ms |
| manymouth_delta | 5 874 | 9 347 | 1 845 ms |
| amberwood | 7 935 | 9 106 | 3 438 ms |
| verdant_stair | 9 449 | 12 243 | 6 145 ms |

Verdant Stair has four times Four Gates' nodes and forty-eight times its scene
build. Bucketing the wide list under empty grouping nodes and building the same
package again, in a scratch probe over `GLTFState` before `generate_scene`:

| bucket size | groups added | generateScene, Amberwood | geometry |
| --- | ---: | ---: | --- |
| as shipped | 0 | 3 755 ms | - |
| 512 | 18 | 294 ms | identical |
| 256 | 34 | 230 ms | identical |
| 128 | 67 | 204 ms | identical |
| 64 | 136 | 177 ms | identical |
| 32 | 271 | 172 ms | identical |

"Identical" is a hash over every mesh instance's name, mesh, surface count,
world transform and visibility. The regrouping itself was 8-15 ms.

## What landed

**`WorldLoader` buckets an over-wide sibling list before the scene is built.**
Any list wider than `MAX_SIBLINGS` (512) - the scene roots included, which is
the shape Sunmane Steppe has, with a thousand props and no parent among them -
is split into buckets of about sqrt(n) empty `Node3D` groups, so neither the
buckets nor the list of them is left wide. The groups carry an identity
transform and no geometry.

Nothing on screen changes. A mesh keeps its name, its mesh, its materials, its
layers, its shadow casting and its world placement; only its depth in the tree
changes, and every pass in the loader and every consumer of the loaded world -
the batching, the occluder fade, the interior cutaway, the secret sections, the
collision declarations - reaches nodes by a recursive search or by name.
`rendering.regroupWideSiblings` in a world manifest turns it off, beside
`batchStaticInstances`, and `rendering.maxSiblings` moves the limit. A package
carrying a skin or a skeleton is skipped whatever the manifest says, because
Godot places a `Skeleton3D` from where its joints sit among their siblings;
none of the 56 shipped packages has one.

Median of three loads per region, headless, milliseconds:

| region | before | after | | generateScene before | after |
| --- | ---: | ---: | ---: | ---: | ---: |
| four_gates | 970 | 770 | -21% | 127 | 57 |
| mirrorhold | 1 263 | 921 | -27% | 173 | 53 |
| crownwater | 1 158 | 1 011 | -13% | 99 | 80 |
| whitehorn_range | 1 119 | 919 | -18% | 140 | 61 |
| amethyst_barrens | 955 | 970 | +2% | 80 | 78 |
| sunmane_steppe | 528 | 510 | -3% | 90 | 56 |
| amberwood | 4 675 | 1 363 | **-71%** | 3 438 | 160 |
| grey_moors | 3 348 | 1 184 | **-65%** | 2 220 | 127 |
| westhaven | 1 215 | 1 100 | -9% | 188 | 92 |
| verdant_stair | 7 926 | 1 186 | **-85%** | 6 145 | 164 |
| ssarathi_ruins | 1 545 | 1 011 | -35% | 202 | 91 |
| manymouth_delta | 3 405 | 1 309 | **-62%** | 1 845 | 144 |
| **twelve regions** | **28 106** | **12 255** | **-56%** | **14 747** | **1 161** |

Crownwater and Amethyst Barrens are the two the pass leaves alone: their widest
lists are 440 and 405, under the limit, and their movement is this machine's
noise. The worst region in the game went from 7.9 s to 1.2 s, and no region is
now over 1.4 s.

The regrouping costs 15.6 ms on Amberwood and adds 113 nodes to an 11 545-node
import; across the twelve it is 158 ms and about 700 nodes.

Where the twelve-region load stands afterwards:

| | before | after |
| --- | ---: | ---: |
| generate_scene | 14 747 | 1 161 |
| walk surfaces | 5 888 | 4 765 |
| glTF parse | 5 094 | 4 309 |
| declared collision | 624 | 581 |
| mip chains | 538 | 417 |
| static batching | 378 | 317 |
| manifest | 296 | 311 |
| regrouping | - | 158 |
| everything else | 541 | 236 |
| **total** | **28 106** | **12 255** |

The parse and walk-surface columns did not move for any reason of this pass;
the differences there are the two runs, on a machine a dozen sessions share.

**Guards.** `tests/test_runtime_performance.gd` checks the pass on a synthetic
`GLTFState`: no sibling list wider than the limit survives, every node keeps
its ancestor and its order among its siblings, a group is an empty identity
transform, and a map that switches the pass off or a package that carries a
skin is left untouched. `tests/integration/map_regrouping.gd` proves the
picture: it loads Four Gates and Sunmane Steppe through the production loader,
rebuilds the same packages straight through `GLTFDocument` with no regrouping,
and compares - the same 3 028 and 1 050 mesh instances, sharing the same 184
and 258 meshes, each with the same name, mesh, surface count, layers, shadow
casting and world transform.

## The options, measured

Everything below was measured on this base after the regrouping landed, except
where it says estimated.

| option | saving | cost | risk | on screen |
| --- | --- | --- | --- | --- |
| **Regroup wide sibling lists** (landed) | 15.9 s of 28.1 s across twelve; 6.7 s off Verdant Stair | ~40 lines in `WorldLoader`, 158 ms and 700 nodes across twelve | low - the tree is deeper by one level | nothing |
| **Parse and build on a worker thread** | hides 400-610 ms of a 500-1 400 ms load; total unchanged | a thread, a deferred attach, and a decision about what the client shows meanwhile | medium - `GLTFDocument` off-thread is unsupported territory, though it worked in every probe | nothing, if the loading screen already covers the freeze |
| **Cache the built region as a PackedScene** | 49% of what is left: 1 318 -> 664 ms Amberwood, 1 244 -> 567 ms Verdant Stair | first visit +640 to +960 ms; ~30 MB a region, ~360 MB for the twelve; an invalidation contract | medium-high - a cached tree can drift from what the loader would build | nothing, if the cache is right; something silent and undiagnosable if it is stale |
| **Cheaper walk-surface collision** | up to 4.8 s across twelve, the largest item left | unknown; the shapes are two thirds of it and they are the grounding contract | high - this is what holds the player up | nothing, if the shapes are the same |
| **Fewer nodes at build time** | little: Sunmane's own LOD2 package has 318 mesh instances against 1 050 and loads in 380 ms against 459 | a toolkit change and a regeneration of every package | low | LOD2 is a different, coarser map; a MultiMesh bake would not be |
| **Compressed textures at build time** | ~180 ms a region: 150-175 ms of PNG decode and ~30 ms of mip building | `KHR_texture_basisu` in the toolkit, and a decision about quality | low | **yes** - compression artefacts, and the mip chain would come from the package rather than from the loader |
| **Load the region in cells** | perceived only; the player's cell could appear in a fraction of the time | the loader, the collision passes, the batching and every fixture that waits on `world_root` | high | **yes** - the far side of the region arrives late |

### (a) Threaded loading

Feasible, and cheap. A scratch probe ran `append_from_file`, the regrouping and
`generate_scene` on a `Thread` while the main thread served frames:

| region | on the worker | main-thread frames served | slowest main-thread frame | `add_child` on the main thread | nodes |
| --- | ---: | ---: | ---: | ---: | ---: |
| four_gates | 397 ms | 129 240 | 0.97 ms | 6.1 ms | 3 137 |
| amberwood | 607 ms | 194 244 | 0.83 ms | 15.1 ms | 9 543 |
| verdant_stair | 597 ms | 187 858 | 1.22 ms | 21.2 ms | 14 767 |

The main thread never blocked and attaching a fifteen-thousand-node tree is
21 ms. Godot 4 allows building nodes off the tree on a worker and adding them
on the main thread, and the mesh and texture resources the parse creates go
through the rendering server's own command queue.

What would still be on the main thread is the material passes, the collision,
the walk surfaces and the batching - about 500 ms of Amberwood's 1 363 - because
`Node3D.global_transform` needs the node to be in the tree and the batching
reads it. Moving those too means computing the transforms by hand and attaching
last, which is a larger change than this one.

Every fixture already polls `loader.world_root` in an `await process_frame`
loop rather than assuming the tree is there when `load_world` returns
(`rendered_crownwater`, `rendered_day_night`, `rendered_ground_markers`,
`rendered_interiors`, `rendered_map_transition`, `rendered_sunmane_steppe`,
`sunmane_caves`, `sunmane_grounding`, `sunmane_minimap`,
`sunmane_performance`, `client_benchmarks`, and the rest), so the seam is
already the right one. This was **not landed**: it hides a freeze rather than
shortening it, the freeze is now 0.5-1.4 s rather than up to 8 s, and it wants
a decision about what the client shows while the worker runs.

### (b) Fewer nodes before the parse

The reason for this option was `generate_scene`, and that reason is gone. What
is left to win is the parse, which is proportional to the buffers rather than
the nodes: Sunmane Steppe's own LOD2 package has 318 mesh instances against
1 050 - a 70% cut - and loads in 380 ms against 459 ms, a 17% cut. Baking
repeats into MultiMesh at build time would not help the parse at all and would
lose the per-instance nodes the manifest, the occluder fade and the tooling all
reach for.

### (c) A cached native scene

Measured end to end in a scratch probe: load the region through `WorldLoader`,
set the owners, `PackedScene.pack()`, `ResourceSaver.save()` with
`FLAG_COMPRESS`, then read it back and instantiate it.

| region | fresh load | own | pack | save | cache file | read | instantiate | **warm load** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| four_gates | 735 ms | 3.0 | 79.6 | 556.5 | 32.9 MB | 275.7 | 100.2 | **376 ms** |
| amberwood | 1 318 ms | 8.6 | 252.5 | 702.9 | 42.0 MB | 439.4 | 224.3 | **664 ms** |
| verdant_stair | 1 244 ms | 11.9 | 347.3 | 639.4 | 34.4 MB | 364.9 | 202.4 | **567 ms** |
| sunmane_steppe | 490 ms | 1.3 | 50.4 | 204.9 | 14.3 MB | 131.8 | 59.2 | **191 ms** |

The geometry round-trips exactly - the probe compared every mesh instance's
name, mesh, surface count, world origin and visibility - and a `PackedScene`
instantiates with `_add_child_nocheck`, so it never pays the name check the
regrouping is about. Two things a landed version would have to deal with:

* **The batch links do not survive.** `WorldLoader` stamps every batched mesh
  with a `static_batch` metadata entry naming the `MultiMeshInstance3D` that
  now draws it, and `OccluderFade` reads it to lift one instance back out while
  it fades. Metadata is stored in a scene, but a `Node` in it is not a
  `Resource` and comes back null, silently, so `OccluderFade` would fade a mesh
  that is not the one being drawn. The probe worked around it by taking the
  links off before packing; a landed version would have to write them as node
  paths and re-resolve them after instantiating.
* **The key.** The cache is only correct while the package, the manifest and
  every pass in the loader are the ones that built it. A size-and-mtime key
  over both files plus a format version in the loader is the obvious contract,
  and the failure mode when someone forgets to raise the version is a map that
  is subtly wrong with nothing in the log.

Worth doing if a second visit to a region has to be instant. Not worth doing
for another 600 ms once the worst region is 1.4 s.

### (d) Cells and streaming

The batching already sorts instances into 180 m cells, but it does that after
the whole package is parsed and built, which is the part that costs. Streaming
would mean splitting the package itself, which is a build-time change to every
region, a rewrite of the loader's passes (collision and walk surfaces are
declared per node name over the whole map), and a new contract for every
fixture that waits for `world_root` and then looks for a node by name. It is
the largest change here and the only one that changes what the player sees.

### (e) Textures

Embedded textures are decoded during the parse and there is no flag that avoids
it. Pulled out of the container and decoded by hand:

| region | images | PNG MB | decode | decoded MB | mip build |
| --- | ---: | ---: | ---: | ---: | ---: |
| four_gates | 95 | 11.9 | 174 ms | 60.0 | 32 ms |
| amberwood | 114 | 12.3 | 175 ms | 56.5 | 32 ms |
| verdant_stair | 103 | 9.3 | 150 ms | 49.7 | 30 ms |
| sunmane_steppe | 30 | 3.7 | 42 ms | 10.4 | 5 ms |

So about 180 ms a region, or 2.2 s across the twelve, of the 12.3 s that is
left - a seventh of the load, for the pixels. Shipping the textures
VRAM-compressed with mip chains already built would take most of it and would
also cut the texture memory a region holds (14-80 MB), but it is a visible
change: compression is lossy and the mip chain would come from the package
instead of from `_build_texture_mipmaps`. **Not landed, and it should not be
landed as a patch** - it is a decision about how the maps look.

### (f) Walk-surface collision, the largest item left

Not on the original list, but it is now 4.8 s of the 12.3 s across twelve and
the biggest single phase. A scratch probe split it:

| region | surface nodes | distinct meshes | faces (k) | building the shapes | hanging the bodies |
| --- | ---: | ---: | ---: | ---: | ---: |
| four_gates | 27 | 24 | 111 | 144 ms | 83 ms |
| crownwater | 189 | 49 | 214 | 276 ms | 133 ms |
| amberwood | 35 | 25 | 235 | 253 ms | 121 ms |
| verdant_stair | 83 | 55 | 246 | 293 ms | 150 ms |
| sunmane_steppe | 102 | 102 | 95 | 84 ms | 34 ms |
| manymouth_delta | 213 | 132 | 264 | 342 ms | 161 ms |

Two thirds is `Mesh.create_trimesh_shape()` and the BVH the physics server
builds under it, at about a microsecond a triangle; a third is creating a
`StaticBody3D` and a `CollisionShape3D` per node and adding them to a world
that is already in the tree, at about 0.75 ms a body. The shapes are already
built once per mesh rather than once per node - that was the third pass. What
is left to try is building the bodies before the world is attached rather than
after, so the physics server sees them once rather than one at a time into a
live broadphase, and moving the shape building to the worker thread option (a)
would need anyway. Both want `sunmane_grounding.gd` and `sunmane_caves.gd`
run against them, because this is what holds the player up.

## Recommendation

1. **Landed: regroup wide sibling lists.** 56% of the twelve-region load, no
   disk, no cache to invalidate, nothing on screen. Done.
2. **Threaded parse and scene build.** Measured feasible and cheap; hides
   400-610 ms of the 500-1 400 ms that is left. Wants a decision about what the
   client shows while the worker runs, and a run of the whole `rendered_*`
   set - the seam is already `load_completed` and every fixture already polls
   `world_root`, so nothing in `tests/` should need to change.
3. **Walk-surface collision.** The largest phase left. Try attaching the world
   after the collision passes rather than before, and measure again.
4. **Cached PackedScene.** Another 49% of what is left, for 360 MB and an
   invalidation contract. Worth it only if returning to a region has to be
   instant.
5. **Compressed textures at build time.** 180 ms a region, and a decision about
   how the maps look rather than a patch.
6. **Cells and streaming.** The largest change, the least certain payoff, and
   the only one the player would see.

## Open questions

* The bucket is `sqrt(n)` on the theory that the groups and the buckets should
  be the same width. 64, 128 and 256 were all within 60 ms of each other on
  Amberwood, so the choice is not load-bearing, but it has not been measured on
  a package built differently from these.
* `MAX_SIBLINGS` is 512 so that a package under that width is handed to Godot
  exactly as it was authored. That leaves Crownwater and Amethyst Barrens, at
  440 and 405, paying about 30 and 25 ms of name checking they need not. The
  limit could go to 256 for that; it has not been measured whether it is worth
  the extra depth.
* Nothing here measures a cold disk. Every number is with the page cache warm,
  which is what a second load in a session sees and not what a first launch
  sees.
* The 6.90 ms a frame that `sunmane_performance.gd` reports is the headless
  idle pad, not a frame time, and has been in its output since before this
  work.
