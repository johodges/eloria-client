# Verdant Stair: concept versus build

Sheets, in `references/comparisons/`:

* `aerial-comparison.webp` — the aerial concept above the build's overview
* `panel-comparison.webp` — all ten close-up panels, concept left, build right
* `landmark-contact-sheet.webp` — the further landmark, traversal and
  golden-hour captures

**Which renderer.** The delivered sheets are built from
`references/godot-captures/` — **real frames from Godot 4.7.2**, Vulkan,
Forward+, loaded through the project's own `WorldLoader` from the same
`world.glb` the client ships, at the camera positions the offline pass
computed. Each sheet says so in its own caption. `references/captures/` holds
the offline previews from `_toolkit/amberwood/render.py`; those are the
iteration set, and any sheet built from them is captioned "offline preview
renderer" instead.

This is the first region package whose comparison sheets are client frames
rather than authoring previews. It also means the frames carry the client's
shadowing and tonemapping, which is why they are darker than the offline set —
see the lighting row below.

## Evaluation against the brief's criteria

| Criterion | Assessment |
| --- | --- |
| Overall geography, composition, silhouette | **Close in structure, thinner in density.** The diagonal is right: lagoon in the low south-west, eight terraces climbing north-east, temple on the summit shelf, cliff risers with falls between. The concept's terraces are *covered* in building; the build's are mostly canopy with courts in it. |
| Landmark presence and relative scale | **Good.** All twenty-two checklist items are present, grounded and connected by route (`coverage-map.md`). The temple reads as the dominant silhouette; the aqueduct spans a real 14 m gorge. |
| Canopy depth and vegetation variation | **Adequate, and the weakest material in the region.** Five species over three detail tiers, plus tree ferns, palms, frond clumps and 1,472 vine curtains. The leaf clusters are large flat cards and read as blobs at close range — this is the toolkit's canopy technique, shared with Amberwood, and it is the first thing a reviewer will notice at 1.7 m. |
| Architectural shape language | **Close.** Tiered jade roofs with upturned gilt eaves, carved piers on stepped plinths, coursed battered retaining walls, turned balusters, colonnades. Panels 7 and 10 are the strongest match on the sheet. |
| Integration with rock, roots, water and terraces | **Good.** Retaining walls hold the courts they stand under; the root bridge's roots dip below its own deck and hang aerial roots; vines fall down the risers; the cenote stair is cut into the shaft wall rather than free-standing. |
| Material and colour fidelity | **Close on stone and jade, thin on flowers.** The jade, carved jade, mossy stone and turquoise water all land. The concept's scattered red and pink flowering trees are absent entirely. |
| Prop and environmental density | **Good on the terraces, sparse in the wild.** 24 arcades, 41 balustrade runs, market stalls, boats, camps, 1,107 ground-dressing pieces. Between the routes it is jungle and little else. |
| Terrain, coastline, water, vegetation character | **Good.** Eight authored terraces, four gorges, six watercourses, fifteen falls placed where a stream actually crosses a riser, a lagoon with a real inlet and a mangrove bight. |
| Player-scale detail | **Mixed.** The waygate, the water shrine and the town hold up at eye height (panels 7 and 10). The Grand Stair does not read from its own foot — see below. |
| Lighting and atmosphere | **Partial, and honestly reported.** The client frames are noticeably darker than both the concept and the offline previews: the canopy self-shadows heavily under a real directional light, and this region's ground albedos are deliberately dark wet limestone. The package now declares its own sun, ambient and exposure and the capture harness honours them, which recovered most of it; it is still a duller picture than the painting. |
| Navigation readability | **Good.** Twenty-five routes graded into the terrain and cleared of trees, a stair on every riser, signposts where routes meet. |
| Repetition and procedural artefacts | **Acceptable.** Species, scale and rotation vary per instance; terrain material boundaries are dithered; terrace-edge geometry is instanced from four wall variants and three arcade lengths, which is visible if you look for it. |
| Performance and LOD | **Measured, over the guideline.** 3.54 M instanced triangles over 576 m × 576 m — 10.7 per square metre, against Amberwood's 9.4 and Mirrorhold's 3.8, and about 2.4× the repository's stated 1.5 M desktop guideline. `world-lod2.glb` ships at 1.15 M (67% fewer); nothing in the loader selects between them. |

## Panel by panel

Read off `panel-comparison.webp`. Three of ten land, four are partial, three do
not work.

| Panel | Verdict | Why |
| --- | --- | --- |
| 1 lagoon landing | **weak** | The strand, quay pavilion and terraces are in frame; the boat and the turquoise water are not. The camera cannot stand offshore — the clearance search refuses a position below sea level — so it ends up looking along the beach instead of across the inlet. |
| 2 grand stair | **weak** | The flight exists and is walkable, but from its own foot the frame is filled by the riser cliff beside it. The stair needs a camera on its axis with enough standoff, and the clearance search keeps choosing openness over subject. |
| 3 cenote | **partial** | Terraces, paving and water read from the rim; the helical shaft does not. The stair is cut into the shaft wall, so from above it reads as terracing rather than as a descent. |
| 4 root bridge | **partial** | The gorge and the span are both there; the frame is dark and the banyan roots do not separate from the cliff behind them. |
| 5 rope bridge | **weak** | The vine-hung riser dominates and the bridge is out of frame. The target height is measured above the *local* ground, which at a gorge crossing is the floor seventeen metres below the deck — fixed once, and the camera still favours the cliff. |
| 6 canopy village | **good** | Thatched stilt huts, plank walkway and banyans on a terrace. The closest of the ten to its panel in subject and in framing. |
| 7 water shrine | **good** | Carved jade piers, guardians, stepped plinths and the pool. The strongest architectural match on the sheet. |
| 8 jungle trail | **partial** | Canopy, understory and a hut; the trail itself is not the subject of the frame. |
| 9 terrace overview | **partial** | The stacked terraces, pools and canopy read; the aqueducts and stairs the panel foregrounds do not. |
| 10 relief study | **good** | Jade columns, carved meander, mossy paving, rope and timber at reading distance. |

## The honest headline

The region is structurally finished and runtime-correct: the terrain grounds at
zero misses across all 331,776 reachable server tiles, both offline and inside
Godot; the GLB validates clean; every landmark, route and population marker is
placed and verified.

What it is not is as *dense* as the painting. The concept is an architectural
picture — terraces stacked with building, aqueducts and stairs threading
between them, flowering trees everywhere — and the build is a jungle massif
with terraces cut into it and a town, a temple and a shrine on them. Closing
that gap is more architecture per terrace, not a different approach, and the
triangle budget has no room for it at the current canopy technique.

Three of the ten panel comparisons fail on **framing**, not on missing content:
the Grand Stair, the rope crossing and the lagoon all exist, are walkable and
verify, but the automatic camera placement picks openness over subject and puts
a cliff in front of each. That is a capture problem worth a targeted fix — a
per-view "must see this node" constraint — rather than a modelling one.
