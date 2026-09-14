# Nymara: the diagonal mountain spine

The continent is authored in one coordinate system before any territory is
exported. X runs east, Z runs south, and sea level is Y = 0. Named territories
are server and content identities. Their boundaries do not determine the
height, water level, ground colour, or vegetation of the landscape.

**QA state: thirteenth publication (2026-09-14), verified with one open live suite.**
Master `120f488856c160586654e925887cbef1611a9c18a40923806cd677ab966165b1`
(unchanged since the twelfth), publication
`494ffb6089326c451030fd924d89418851b6f12eda86888e4fcc30194f90c6fa`
(`work-output/diagonal-continent/after/thirteenth-freeze.json`), after origin/develop
was merged into both branches and the frozen profile baseline advanced to it.
On these bytes the strict contracts passed with 0 failures over 3,660
placements, the full audit passed and verified the publication, the 24
primary, 9 supplement and 2 atlas gameplay views were captured with the
published registry and no overrides (`final-review/`, `final-repairs/`), and
six of the seven native loopback suites walked their 168 routes with 0
failures on a real server; the interior round-trip suite completed 12 of 72
routes and then the machine was put to sleep for 75 minutes (the harness
watchdog recorded the gap and the server closed the idle connection), while
the same 72 routes walked with 0 failures on the twelfth publication,
whose geometry this one shares (`after/live-walk/final-live-summary.json`).
Known limitations are listed in `STATUS-2026-09-13-takeover.md`: road cores
steeper than 0.65 that the server routes around, boats
inside rigid assemblies not settled on water, and props that floated in their
regional surveys keeping that offset. Any later change to a shaping or export
source returns this notice to provisional until the same chain is repeated.

`diagonal-plan.json` describes the coast, connected mountain chain, river
catchments, islands, territory centres, and placement controls. `landscape.py`
evaluates the common height and climate fields. No territory border enters
those functions. `world_layout.py` samples the surface at two metres, fits
settlement footings, and finds roads through manageable ground. `content.py`
places retained architecture and discoveries, then scatters woodland and
related rock formations using moisture, slope, road, and exposure fields.

The northern high country feeds the wet western basin. Amberwood occupies
the sheltered slopes below the snowline; Grey Moors occupies the wetter
western uplands. Mirrorhold controls a pass through the spine. Amethyst and
Sunmane share its dry eastern side, with gradual grassland and dry-soil
transitions. The mountain chain diminishes into the southern limestone
uplands, while the western rivers divide into the Manymouth estuary and
Crownwater islands. Rivers reach the sea through actual low ground.

The eastern coast has dry grassland and coastal downs between the mineral lee
and the sea. Northern snow, upland heath, and sheltered woodland overlap by
height and exposure rather than changing at a territory edge. Mirror Lake is
an inland water body with its own surveyed level and an outlet into the western
watershed. Its harbour follows that lake datum; coastal harbours follow sea
level. The upper rivers have low flood shelves before their broader valley
shoulders rise. Later road and foundation grading restores a ten-metre natural
bank apron, feathering to 42 metres, with a smooth 32-metre exclusion around
real hard footings. Retained support conflicts are reported for visual and
collision review; this protection is not proof that every bank is finished.

This is designed fantasy geography, not a geological or hydrological
simulation. Ridges, drainage, and settlement approaches are editable design
controls. Coherent broad shapes take priority over uniform terrain noise.

## Authored sources and exports

Use these source responsibilities when changing the world:

| Source | Authority |
| --- | --- |
| `diagonal-plan.json`, `landscape.py` | Shared coast, mountain spine, drainage, natural ground, climate and biome materials. |
| Regional `build_*.py` recipes and shared toolkit | Original reusable architecture, authored object names, linked content and foundation surveys. |
| `build_library.py` | Certified reconstruction of retained assets from those recipes, with trusted intermediate caches. |
| `assemblies.py`, `content.py` | Connected structure grouping, common transforms, actual footing categories, mapped content and ecological placement. |
| `crown_support.py`, `westhaven_support.py`, `manymouth_support.py`, `mirror_support.py` | Local island, harbour, landing and bank support fitted to retained structures. |
| `mirror_streets.py`, `four_gates_support.py` | Civic circulation, actual building footings and the graded east-gate approach. |
| `mirror_access_geometry.py` | Low stone bank ramps and the physical opening onto the sanctuary walkway. |
| `mirror_lake_support.py`, `ssarathi_bank_support.py` | Containing lake shores and natural river banks fitted around retained walking floors. |
| `manymouth_boats.py` | Actual hull contact with water or ground for independent decorative dugouts. |
| `amberwood_support.py`, `amberwood_access.py` | Woodland workyard paths, coherent camp layout and visible canopy/root entrance construction. |
| `manymouth_access.py` | Visible tidal fishing boardwalks linking retained porches and the landing. |
| `manymouth_village_streets.py` | Graded timber streets connecting the other delta hamlets to their actual porch floors. |
| `grey_crossings.py` | Retirement of the three duplicate Grey Moors boardwalk spans, the four pinned server positions they anchored, and their landmark identities on the actual continental crossing floors. |
| `four_gates_sage.py` | The six Four Gates tutorial Sage records pinned 48 tiles from the arrival beside the plaza approach, keeping their surveyed layout. |
| `door_approaches.py` | Authored road ends for doors inside retained pavilions (the Shrine of the Nine Lost on the South Quay), shared by the server-declared discovery branch to the same door, so the road meets the pavilion's open side and no deck is built onto its threshold. |
| `crossing_contracts.py` | Contracts-stage declaration of each continental bridge floor's two standing points from the served collision fold, with every floor's walkable parts reported. |
| `ferry_export.py`, `ferry_support.py` | Actual quay/boat fit and preservation of its complete shoreline footprint through road grading. |
| `world_layout.py` | Ownership polygons, server address envelopes, common road grading, foundation reconciliation and drainage protection. |
| `bridge_export.py` | One union of visible continental bridge decks, fitted to the common road surface and actual banks. |
| `terrain_export.py` | Shared terrain faces and physically clipped shorelines, partitioned from the complete world surface. |
| `build_continent.py`, `scene_io.py` | Global composition, master scene, named packages, independent loading cells and shared image dependencies. |
| `crossings.py`, `export_contracts.py` | Reciprocal crossing lanes and authoritative standing positions derived from actual exported walking surfaces. |
| `../../../tools/publish_diagonal_continent.py` | Coordinated client/server publication, remaps, package digests and save-migration data. |
| `atlas_export.py` | Actual-master overview, matching territory crops and Tab-map publication. |

Edit the responsible authored sources and rebuild their dependent stages.
Generated GLBs, collision files, manifests, ELMs and atlas crops are outputs.
The frozen legacy geography/profile is a coordinate reference, not the new
continent's layout or a second copy of visible terrain.

`build_library.py` rebuilds reusable architecture from the original regional
sources and shared toolkit. Frozen `legacy-geography.json` and
`legacy-contracts.json` supply the old composition's foundation reference.
The library's old terrain is sampled for placement offsets and never drawn
in the new world. Source and output hashes certify each reusable library.

`build_continent.py` assembles a complete global scene and writes
`generated/continent.glb`. It exports the same scene into named ownership
polygons and 96-metre streaming cells. Terrain faces and bridge decks are
cut at ownership boundaries; buildings stay whole and are assigned once.
All chunk geometry remains in its territory's local coordinate system.
The complete GLB is a reproducible review artifact, not a runtime load.

The twelve named territories retain their identities and content contracts.
Their irregular ownership shapes are independent of the 96-metre loading
grid. A building assigned by its bounds centre can extend beyond that cell;
its manifest records its actual bounds so it can load before becoming visible.
Do not clip a connected building to the loading grid or duplicate it into
neighbouring cells. Chunk count is an export result, not a fixed contract.

Runtime assets are each territory's `world.json`, `world.glb`, `collision.bin`,
and `chunks/<x>_<z>/world.glb` plus its manifest. Shared PNGs are stored by
SHA256 under `shared-assets/`. Chunk manifests declare their image dependencies
and separate geometry memory from image memory; the client counts identical
images once per territory and pools their GPU textures.

`continent_chunk_stream.gd` loads independent cells around the real focus;
current manifests request 240 metres of preload and retain to 320 metres,
subject to 64 cells and an estimated 256 MiB resident budget per territory
stream. Those estimates include geometry and shared resources; they are not
measured process or GPU memory. Actual loading, retirement, adjacent-territory
adoption and cold arrivals require client proof. Named manifests declare
`geometryMode: continent-chunks-v1`; old regional rebuild entrypoints must not
replace these packages with standalone legacy terrain.

The addressable server envelope remains square because the existing ELM
format uses square map cells. Rendered and walkable territory ownership is
nonrectangular. An envelope can include sea or another territory's bounding
box without granting movement there. Compact retained settlements and their
surroundings occupy only part of these envelopes; open hills, rivers and sea
provide the geographic transitions between them.

`crossings.py` surveys seven exact metre-cell lanes at each road crossing.
Reciprocal arrivals share the same global cell centre. Reverse departure
triggers sit on the opposite side, preventing immediate return loops.
Short invisible threshold floors support the final step across an ownership
boundary; they do not duplicate visible terrain. Other shared boundaries
are declared as visual adjacencies without adding travel portals.

Island connections without a continuous road remain explicit ferries. Their
fixtures require the exact authoritative receiving tile and its global metre
coordinate at the tile centre. A visible neighbouring shore does not imply
that water can be crossed on foot. Cross-territory click targets must be
verified through the real client and server, including resumed movement.

## Connected settlements and approaches

Architecture that shares a floor, quay, courtyard, stair or bridge uses one
coordinated assembly transform. Linked doors and metadata use that transform
as well. Do not reground separate roof, wall, deck or fountain meshes to
independent terrain samples. Actual footing cores retain support, while
suspended canopy platforms and walkways do not manufacture ground underneath
themselves. Foliage is not a foundation constraint.

Mirrorhold's fortress, streets, lake harbour and associated content share its
city survey and lake datum. Four Gates keeps its civic complex coherent;
Manymouth keeps connected boardwalks and temple/hamlet groups while allowing
water beneath raised floors. These local supports must blend back into the
common watershed without making former rectangular map bases.

Manymouth's local timber streets meet actual retained porch heights and avoid
house bodies. Paddy, fishing, town and outlying hamlets keep separate street
networks rather than sharing a flat platform. The Temple quay bank interpolates
between its real floor aprons and blends into the higher eastern hamlet.
Source tests cover exported diagonal precision, bounded street grades and
floor contacts; the final named geometry must also pass the complete 99-floor
standing and connectivity audit. Independent dugout boats use full hull
contact with water or land, while ferry boats keep their surveyed moorings.

Crownwater's causeway city uses **17 named islands** matched to its retained
source survey. `crown_support.py` limits that survey to island shelves, fits
bridgeheads, repairs two specified stale causeway profiles as whole bridges,
and reserves crossing corridors against ferry placement. The surrounding sea
remains shared continental geography. Westhaven separates its working harbour
and lighthouse into coherent maritime assemblies: quays, yards, warehouses,
boats and associated doors keep their common relationships. Irregular local
support envelopes fit the shore, and actual submerged hull geometry determines
berth clearance. Verify both harbours from water and from their street
approaches after changing these supports.

Ferry selection tests ranked coastal sites against a complete quay and moored
boat footprint. Existing working quays and causeways are excluded; selected
landings remain at least 20 metres apart so automatic destination triggers
are distinct. Trial terrain/contact edits are rolled back before selection.
The selected fit preserves the terrain vertices beneath the complete quay and
boat, including a full terrain-triangle margin. Road grading approaches this
shoreline constraint. Composition checks all final quay and mooring fits again
before caching the world; an earlier successful candidate is insufficient.

Grey Moors retires exactly three surveyed boardwalk spans (gate, centre and
south) whose retained floors duplicated the continental bridge union at the
headwater outlet and the southern pool. The other spans, both causeway
bridges and the boardwalk cache discovery remain. Four server records that
had used those spans as nearest deformation anchors keep their expected
global positions through explicit authored points, and the three generic
`Grey Moor Crossing` landmark identities are re-associated at export with the
actual emitted crossing floors. The Moor pools and their banks are not
reshaped by this correction.

Mirrorhold's lake-path correction uses the exposed upper walking surface.
Lower sleepers and structural supports do not justify excavating terrain.
Only the inherited local bank overlap is lowered, with a short shoulder;
the lake bed, levels and connected city geometry remain intact.

Visible interior doors receive narrow approach routes. Composition also reads
the frozen authoritative `maps.txt` portal entries and exterior returns,
including hidden rooms absent from client portal markers. Mapped destinations
receive branch trails with a 1.65-metre half-width from an existing public road. Nearby duplicate
destinations share a branch. These are authored discoveries with accessible
approaches; collision export must not conceal a disconnected entrance by
carving an invisible corridor or moving it away from its building. The entrance
profile hash is part of composition freshness.

## Rebuild

Use Python with NumPy, SciPy, and Pillow, the shared toolkit's native raster
library, and the paired server dependencies. Godot is required for client
tests and visual proof. The pipeline enforces a common processor affinity
of at most eight logical cores and one numerical-library worker per process.
Two library processes may run concurrently within that same CPU allocation.
The eight-core limit is shared by concurrent work, not eight additional cores
per process. Launch independent diagnostics through the same affinity-limited
task wrapper; do not start uncapped build or numerical workers alongside it.

From the client checkout:

```powershell
python eloria-assets/maps/nymara-regions/_continent/build_pipeline.py --server C:/path/to/server --data C:/path/to/generated-data --artifacts C:/path/to/review-output --cores 8
```

Stages are `libraries`, `compose`, `geometry`, `contracts`, `publish`, `atlas`,
and `verify`. Use `--stage` to run one stage and `--library` to reuse an existing
certified cache. `compose` must run again after landscape, placement, or road
sources change. Export-only fixes can reuse its checked composition cache.
Generated caches are trusted local build artifacts, never interchange files.

With no `--stage`, this command runs the entire sequence, including publication
to the supplied paired server and client packages. Use individual stages for
provisional geometry review. Composition freshness checks the plan, all
shaping modules (`landscape`, `world_layout`, `content`, `assemblies`,
`crown_support`, `westhaven_support`, `ferry_export`, `ferry_support`,
`mirror_support`, `manymouth_support`, `mirror_streets`, `four_gates_support`,
`amberwood_support`, `amberwood_access`, `mirror_lake_support`,
`ssarathi_bank_support`, `manymouth_boats`, `terrain_export`, `scene_io`,
`grey_crossings`, `four_gates_sage`, `door_approaches`),
the composition algorithm, the authoritative
entrance profile and each retained library certificate. A changed source must
be recomposed rather than accepted by editing a certificate.

Geometry export independently records `geometrySources` in `export.json` for
`build_continent.py`, `scene_io.py`, `terrain_export.py`, `bridge_export.py`,
`ferry_export.py`, `crossings.py`, `amberwood_access.py`, `manymouth_access.py`,
`manymouth_village_streets.py`, `collision_export.py`, `mirror_access_geometry.py`
and `grey_crossings.py`, and checks that none changed during the
build. The audit requires these current export hashes as well as the
composition certificates. Bridge export changes can reuse the composed world;
Ferry code also participates in landing selection and requires composition.
Terrain export and scene decoding participate in actual boat flotation and
ground contact, so changes to either also require fresh composition.
Village streets use the collision module's actual triangle slope and water
sampling, so that module is also a geometry export dependency.
The contract stage checks the exact composition, master and named GLB hashes
before reading terrain, so a newer landform cannot be paired with an older mesh.

The contract stage uses actual upward walking surfaces, half-metre collision
samples, structural intersections, and the server's height-stage rules. It
samples the same clipped shoreline and continuous hydraulic plane as the
visible water mesh, including elevated riverbank corners. Its raster cache
includes those surface sources and water-domain controls. It requires
arrivals, doors, services, resources, encounters, and all road lanes
to connect to the inhabited arrival. A failed contract produces a diagnostic;
it does not carve invisible routes through cliffs or move a doorway far from
its building.

`legacy-server-profile/` preserves the original coordinate authority.
`publication-history/` records exact prior remaps so a revised build can move
from currently served coordinates without deforming them twice. Interior-local
coordinates remain local; exterior return positions follow the new landscape.
Each territory's `terrainRevision` is `diagonal-spine-v1:<sha256>` derived from
its emitted GLB, collision bytes and height encoding, folded server grid,
address origin/dimensions, continent translation, safe arrival and mapped
content positions. The release label alone is insufficient after another
terrain edit. Identical exports keep the same revision, including after a
first publication; bookkeeping-only baseline changes do not alter it. Named
and chunk manifests receive the same territory revision. Runtime migration
returns saved exterior characters in changed territories to their own
collision-verified arrival once, preserving progression and interior saves.
Historical daily-quest bookmarks are retained; there is no invented nonlinear
mapping from old gathering locations to unrelated new ground.

Publication updates the paired server profile, registry, exterior connection
tables, returns, collision, generated ELMs, invasion positions, and package
digests. The atlas stage renders the actual complete master once, crops every
territory on the same pixel lattice, and publishes the Tab continent image and
hit polygons. It never uses a concept image as the playable atlas.

## Validation sequence

1. Run the relevant `_continent/tests` and client/server contract tests under
   the common CPU limit. Rebuild affected libraries, compose, then export
   geometry. Inspect retained assembly reports and drainage conflicts before
   treating the scene as ready for contracts.
2. Run `audit_continent.py --geometry-only --output <review>/geometry-audit.json`
   against the current export. This provisional mode derives ownership,
   translations, envelopes and provenance from actual named manifests and
   `export.json`; it does not require an already published canonical layout.
   It exhaustively compares the master, source terrain, named territories and
   independent chunks for exact face ownership, shared position/normal/UV/colour
   membership, materials and external image hashes. It does not certify a live
   server or current collision publication.
3. Review gameplay-camera captures and the master overview. Check riverbanks,
   approaches, canopy obstruction, city floors, bridge silhouettes, island
   bridgeheads and occupied harbours. Bridge export checks a single shared
   deck union, actual bank fit, emitted triangle grade and hidden threshold
   support; inspect its reports rather than using a centreline slope alone.
4. Run `contracts` against the actual exported surfaces. Its report must cover
   every required arrival, lane, entrance/return and content standing point.
   Then run coordinated `publish`, `atlas` and `verify`. Full
   `audit_continent.py --server <paired-server> --output <review>/continent-audit.json`
   additionally checks canonical/client/server publication and height alignment.
   Pipeline `verify` also checks the Tab-map build; it does not run all the
   independent tests or the live walking harness.
5. Generate fixtures with
   `eloria-assets/tools/generate_continent_walk_proof.py --server <paired-server> --data <ELM-directory> --output <review>/walk`.
   Require its package, geographic adjacency, reciprocal lane, ferry and
   independent server path audits to pass. Inspect `allContentAccess` for
   exhaustive content claims; representative fixtures alone are insufficient.
   Counts come from the current publication and actual ownership adjacencies.
6. Run `godot-client/tests/integration/rendered_landscape_walk.gd` in the real
   client against that server, setting `ELORIA_WALK_SPEC`, `ELORIA_ARTIFACT_DIR`
   and the integration host/port for each generated fixture set. Prove centre
   and shoulder crossings, neighbouring-map clicks, services/resources,
   interior round trips and ferry round trips. Check exact ferry actor-spawn
   tile/global centre before a subsequent move, cold-arrival focus and active
   collision, grounding, camera overlaps, retained target movement and actual
   loading/retirement behaviour. Capture matching before/after viewpoints and
   record measured performance limitations.

Keep reports with their input hashes and do not mutate their inputs during a
proof. A geometry-only pass, generated route fixture or diagnostic camera
survey is useful evidence within its scope; none substitutes for the final
paired publication and live route proof. Update the provisional QA notice only
after those artifacts have been reviewed together.

## Regional design responsibilities

| Territory identity | Geographic and inhabited role | Next regional art pass |
| --- | --- | --- |
| Whitehorn Range (`whitehorn_range`) | Highest northern spine, headwaters, alpine refuges and cave approaches. | Use connected rocky shoulders, sparse exposed vegetation and snow pockets. Keep headwater banks readable and let conifers enter sheltered lower slopes gradually. |
| Grey Moors (`grey_moors`) | Wet western uplands, old crossings and scattered shelter. | Group peat hollows and damp heath around drainage; preserve open grazing, distant silhouettes and modest groves instead of turning the moors into Amberwood. |
| Amberwood (`amberwood`) | Sheltered woodland and inhabited canopy country below the snowline. | Establish uneven age/density, clear village approaches and low riverside shelves. Protect trunks and ground stairs while leaving real air beneath elevated platforms. |
| Amethyst Barrens (`amethyst_barrens`) | Dry northern lee, mineral workings and exposed stony routes. | Build related mineral formations with debris and sparse hardy plants; weather the same mountain shoulders into dry gravel before reaching steppe. |
| Mirrorhold (`mirrorhold`) | Fortified pass city and inland lake harbour. | Preserve its coordinated streets and roof silhouettes; fit civic terraces and lake edges to local geography, with clear gates and readable lake-to-pass approaches. |
| Sunmane Steppe (`sunmane_steppe`) | Eastern grasslands and broad overland travel beneath coastal downs. | Emphasise long grasses, grazing/open combat space, sparse dry-country groves and greener drainage. Keep a grassland/coastal buffer between bare mineral ground and sea. |
| Four Gates (`four_gates`) | Principal western road junction and convenient civic service hub. | Make roads widen at useful shared spaces; add restrained yards, cultivated plots and work areas around coherent civic floors, with open sightlines to gate landmarks. |
| Westhaven (`westhaven`) | Working western harbour, lighthouse and sea trade. | Connect quays to warehouses, fish market, ropewalk and yards. Read water depth, tidal margins and harbour machinery at gameplay distance; preserve boat/shore relationships. |
| Manymouth Delta (`manymouth_delta`) | Western distributaries, raised boardwalk town, paddies and fishing hamlets. | Let reeds cluster at sheltered banks and fields follow wet ground. Preserve navigable water beneath floors and readable temple/hamlet approaches without filling the delta. |
| Crownwater (`crownwater`) | Seventeen-island causeway city and southwestern sea connections. | Refine bridgehead shelves, quays and sheltered landings around individual islands; retain open water, island silhouettes and the formal causeway network's deliberate order. |
| Verdant Stair (`verdant_stair`) | Humid southern limestone uplands below the declining spine. | Group wooded terraces, exposed limestone and moist clefts; route paths with the relief and leave open landform views between groves. |
| Ssarathi Ruins (`ssarathi_ruins`) | Southern ruins and wet lowlands below the limestone chain. | Keep temple, pyramid, vault entrance and ritual plaza as a coherent complex. Use old masonry, roots and quieter overgrown branches to make danger emerge beyond the approach. |

Further art passes should modify the shared landform and these local activities
before adding small dressing. Keep settlement service routes easy to read,
leave combat room and quiet ground, and let danger emerge from exposure,
terrain and discoveries rather than identical rings around every arrival.
Always re-export the complete continent after changes that affect a shared
ridge, drainage line, road, material field, or ownership boundary.

The reusable principles are shared geography, connected assembly support,
ecological grouping, purposeful routes, readable silhouettes and quiet space.
Reuse those rules and the shared toolkit while varying soil, vegetation,
building activity, water edges and landmark rhythm by the table above. Work
from broad landforms to routes, major structures, vegetation and finally
surface detail, revisiting earlier steps from the gameplay camera. Neither
equal territory sizes nor a repeated settlement/attraction template is a goal.
