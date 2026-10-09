# Landfall (`sw_isle`), continent v2

The landing island of continent v2: new players arrive here, `#beam` brings them here and they respawn here
after death. It is built from the Meshy "Isles of Enchantment" model at 8,000 m east-west, whose roads,
rivers and topography are authoritative.

- `sw_isle.tscn`: the authored territory scene. Open it in the editor: on this branch `project.godot` sets
  `map_authoring/territory_catalog_path` to the v2 catalog, so the Territories dock binds the ownership
  window and the sculpt, heightmap-import, ground and plateau tools work as for any territory.
- `../../continent-v2/viewer/sw_isle_view.tscn`: the same scene with a sky, a sun and the sea.
- `base-heights.f32le`, `base-colors.rgba8`: the map-team base, written once by
  `godot-client/tools/bootstrap_continent_v2_territory.py` from the 8 km island products
  (`terrain-provenance.json` has the inputs, hashes and rules). Later edits go in patches, paths and the
  sculpt layer, never into these files. The road earthworks are in the sculpt layer inside the window; outside
  it, where the sculpt tool cannot write, the base keeps the product's graded road corridors.
- `region-authoring-spec.json`: frame and server address. The territory is registered only in the v2
  catalog, `world_authoring/continent-v2/territories.json`; the shared twelve-territory catalog does not
  list it, and on this branch the editor reads the v2 catalog instead of the shared one.

The ownership window (x 399-2437, z 6221-8259 in continent metres) is the largest single 2,048-tile server
map over the main island, which is 2,080 x 2,334 m. The terrain grid covers the whole island group so the
east islet, the SE islet village and the east pier are visible. The owner split the island three ways
(2026-10-02, decisions D2a-D2c):
- sw_isle owns this window. It moved 30 m north from z 6251-8289 (D2b) so it owns the north beach; the move
  changed no base vertex and no sculpt cell, only the server frame: origin (1023, 993), collision origin
  (-1023, 993) local metres, so every served `y` is 30 lower than before.
- The Tollholms (`tollholms`) owns the land east of x 2437: the SE islet with the village Tollholm, Ringholm
  (the east islet's east part) and the outer east pier with the Toll Tower, B15 and the ferry berth.
- The Gull Skerries (`gull_skerries`) owns the south tip, its two islets and the west cliff strip.
Crossings: an open land seam on the Ringholm plateau (R32), an open land seam on the south plateau, and two
seam moles (`Terrain/Patches/seam-mole-knob` for R42, `seam-mole-pier` for the east pier), each a rectangular
Set patch declared identically in both scenes. Decks never cross a border.

## Terrain conditioning

The bootstrap repairs the island product's render artefacts before it writes the base (the polish workflow's
fix plan; parameters in `source-data/work/sw8_condition.json`, rules and counts in `terrain-provenance.json`).
The bootstrap writes this README only when it is missing; it is maintained by hand.

- **Colours.** The Meshy texture does not cover the off-plate cells, and the product gave them albedo 0: black
  shards wherever the upsampling lifted them over the sea. They now take the nearest covered dry texel at or
  above 0 m, and below it the nearest covered sea texel darkened towards the seabed colour with depth. Where the
  product cut painted lakes and rivers down to their levels, the Meshy water paint coloured the walls it left;
  water-hued texels near inland water that are not under their own water (and wet ones at the foot or brink of
  a drop over 3 m) take the nearest dry, non-water-hued texel, pulled towards rock grey on faces steeper than 1.
  Above or below sea is read on the conditioned base, with the sculpt layer's effective heights where the
  snapshot `sw8_sculpt_eff2.npy` has them.
- **Heights.** Two product artefacts are repaired, never on a protected cell (the sculpt-indexed cells
  `sw8_sculpt_cells2.npy`, the road corridors, the castle compound and town pads, the north-tower and lighthouse
  pads): the off-plate ring (the upsampling's +1 to +7 m ridge a few metres off every coast) is lowered to the
  shelf beyond it and to -0.5 m at most, sparing the corridors' 2-cell margin too; the high-rim inland pockets
  (shafts 10-31 m below the sea inside rims 47-148 m high, from inland river nodes the product put at level 0)
  are raised to their rim's 10th percentile. Low-rim pockets (the west creek mouth, the SE lagoon) stay.
- **Coast band (owner-approved, 2026-10-02).** The product clamped each painted cell on its own (sea to -0.5 m or
  lower, land lifted to a flat +0.5 m), which drew a 2 m staircase and white sheets along the shore, and the Meshy
  plate kept a rim trench (the "moat", down to -47 m) under the sea. From the painted shoreline the open sea now
  shelves as the Nymara toolkit's sea shelf (-(0.3 + 0.22 d (1 + 0.012 d)), floor -16 m): exactly within 16 m of
  the shore, as a floor beyond it, so the moat is filled and the product's shallower off-plate shelf stays. Low
  land within 24 m of the shore water ramps up from the waterline (cliff feet kept), the product's +0.5 m lift
  becomes a beach slope, and a light blur crosses the band; the painted classes are re-asserted, so the coastline
  keeps its sign. Besides the protection above, the keep flags `sw8_keep4_2.npy` (built footprints of structures,
  ground under the deck strips, deck landings; `editor-pass/polish/t2/gen_keep.py`) are never changed.
- **L12 gorge (owner-approved, 2026-10-02).** The product cut the painted lake and rivers straight down to their
  nodes' levels, so L12's outlet (R093, then R070 to cove C04) became 40-70 m slots in the NE mesa, stepped at
  84 / 78 / 58 m with fins between them. L12 stays at 47.57 m. R093's bed joins the lake bed (46.57 m); R070 gets
  one monotonic floor 7 m either side of its line, from the lake bed down to 44.4 m at the lip over C04, where
  the ground drops to the cove (the waterfall). Pits under the lake and the other inland water are filled to a
  bed 1 m under their surface, and so are the holes the product left beside the floor. Where the lake, the reach
  or the channel stands at the brink of the sea-level inlet a 0.3 m lip berm holds the water, so it spills only at
  the lip. Within 60 m of the water a cut-only slope limit of 2 (63 degrees) lays the walls back, measured from the
  water only (never from the sea), never below 0.3 m over the nearest water's surface (the water meets a bank),
  and never steeper than the same slope away from the protection, built footprints and deck landings, so the
  roads on the mesa rim keep a bank. Steep faces cut more than 2 m open are tinted towards rock grey
  (`colors.cutFaces`). The outlet stream itself is the `l12-outlet` river path (surface 1 m over the floor).
- **L12 water regions (fix plan P5, 2026-10-02).** The terrace pools (1a/1b at 84.2, 2a/2b at 77.85, 4a/4b at
  58.5, 5a/5b at 57.7) are gone: their terraces were product carve, and the monotonic floor removed the 58 m one,
  so the outlet stream replaces them. l12-b is trimmed clear of the inlet brink and l12-c to the R075 inlet. The
  terrain follows the water exactly: inland bed outside every water ellipse of the box and outside the stream's
  ribbon becomes a bank 0.3 m over the water, the stream keeps its bed only 2.5 m inside its ribbon's edge (at
  least 1.5 m either side of its line), and the channel's floor outside the ribbon is banked too, short of the
  lip. The ribbon's widths are fitted to the ground (`editor-pass/polish/t2/p5_design.py --terrain`: at most the
  distance to a drop beside it less 3 m), 6 m where it passes the inlet brink and 15 m elsewhere, and the rule
  reads them from `sw8_condition.json` (`gorge.stream`), so ribbon and bed agree. Change one, re-run both.
- **North-court crevice (owner-approved, 2026-10-02).** The crevice in the 87.01 m north-tower court (84 painted
  river cells cut 1.7-94 m deep) is levelled with the court: `heights.padHoles` sets the cells a protected pad
  encloses but does not cover to the median height of the pad round them, and the colour conditioning gives
  them (and the teal river-paint texels within 3 cells) the colour of the nearest painted land. The inland-shaft
  rule no longer keeps a box out for it, and north-court-pond-1 is gone.
- **Gorge-mouth fins (owner-approved, 2026-10-02).** The outlet stream's bank between the stream (45-47 m) and the
  sea-level inlet was a 3-11 m blade. `heights.finBanks` raises the inlet cells within reach of that bank to a
  talus (0.3 m at the toe, 2.0 per metre, at most 16 m at the face; the toe at most 7 m out and never past 0.45 of
  the inlet's local half-width, the waterfall's plunge pool kept), a water-shape change the owner approved; sea
  stacks stretched upright to under the stream's bed, boulders and coastal rocks clad the face (scene pieces with
  `polishLayer` fin-cladding, `editor-pass/polish/g2/fins.py`).
- **SE lighthouse peninsula shore (owner-approved, 2026-10-02).** The N10 pad was a flat 2.5 m table cut on the
  painted per-cell shoreline. `heights.padShore` smooths the painted land into an outline and, within 14 m inside
  it, lowers the ground on a smoothstep to 0.3 m at the outline; the lighthouse pad is released, but not the road
  corridors, the keep flags, the quay and court paving or the built pieces on the pad (`keepRects`,
  `keepCircles`), and the beach falls away from them no steeper than 0.45. The sea keeps the coast band's shelf.
  With `outlineSign` (fix:game-look) the coast follows that outline rather than the painted per-cell classes, whose
  2 m teeth the first pass kept: outside the kept cells and their banks, painted land beyond it becomes sea and
  painted sea within it land (246 and 134 cells), and the ground within `waterlineMetres` (2 m) of it is set from its
  signed distance (toeMetres x d / 2 m), so the rendered waterline is interpolated along the curve between the 2 m
  vertices (its length on the changed shore 876 -> 755 m, axis-aligned share 0.51 -> 0.23). A gentle fixed-seed
  wobble (`outlineNoise`) keeps the smoothed edge off a ruler line; the lobe's 48 m east edge stays nearly straight.
- **Ground materials.** The base surface multiplies the Meshy vertex colours by a luminance-only detail tile
  (`src/dev/map_authoring_pilot/style/textures/terrain-detail-luma.png`) and shades it with the same relief's normal
  map (`terrain-detail-normal.png`, normal_scale 0.8), both at a 6 m repeat with linear anisotropic mipmaps
  (texture_filter 5). Both are procedural (`editor-pass/polish/g4/make_ground_detail.py`, game-look fix stage):
  periodic band-limited clumps (0.9-2.2 m) and tufts (0.28-0.6 m) plus the coastal-limestone-gravel pack's grit,
  about a linear median of 0.86 with the 2nd-98th percentile at -38 / +13 %, so the grain survives the game camera's
  mipmaps (the first recipe's +-15 % fine grit measured luma std 7 of 255 and left the ground smooth khaki). The ground regions use their presets' intended repeats on the terrain's 0.17/m
  preview UV (gravel and moss 4 m, grass 4.2 m, sand 5 m; `editor-pass/rescale_region_uv.gd`); Stone and the
  masonry presets keep their authored 0.8 (7.35 m) until the owner picks the cobble look, because at their own
  1.25 m the flags read as sand at the game camera. Rock (gravel) regions lie on cliff tops and scree benches,
  not on faces steeper than 45 degrees, where their top-down texture stretches (fix plan P6,
  `editor-pass/polish/t2/p6_refit.py`): 27 were refitted to the benches beside their cliffs, and 12 with no bench
  of 600 m2 were dropped, so the territory uses 115 of its 127 region slots. Sand regions keep grades under 0.5.
- **Rebind.** The sculpt layer binds its deltas to the base file's sha256, so every base change is followed, in the
  same commit, by `work-output/continent-v2/sw_isle/editor-pass/rebind_sculpt_layer.gd` (headless editor; stage
  the new base with `NEW_BASE` and leave the old one on disk while the scene opens: a scene whose layer is bound
  to another base takes over 12 minutes to open) and `run_bootstrap.sh --check`.

## Editor kit

`assets/prototypes/kit-*.glb` is the isle's palette kit (120 prototypes; textures content-addressed in
`assets/textures/`). It is written by the tools in `eloria-assets/maps/continent-v2/sw_isle/source/`:

- `seat_fixes.py` copies the 19 accepted Meshy pieces (batch 1 and the N8 redesign under
  `work-output/continent-v2/meshy/`; N18 r1 only as the buried fallback cliff) and applies the reviews' local
  seating fixes to the copies (`work-output/continent-v2/meshy/seated/`, with `seat_fixes_report.json`):
  repaints of named defects, palette pulls, crown top-light, the N18/N19 rock moved to the warm grey of the
  reuse coastal rocks, N9's needle faces, N12's re-cut 12.0 m module with
  piers to -8 m, N13's posts to -6 m, N10's +-X kerb openings widened to about 8.4 m, coincident twin faces.
  Deck and platform tops of N10, N12 and N13, and N5's raised passage paving (0.08-0.17 m, which as solid
  geometry closed the gate to the served walk), are split into `Walk_` child nodes; each root node carries
  `extras.eloria` (piece id, origin kind, the reviews' collider primitives, seating notes).
- `prepare_meshy_kit.py --input <seated>` seats those 19 (node transforms baked; sizes checked; the
  normaliser's plan origin kept; the WATERLINE set N10, N12, N13 and N14 keeps its waterline or deck-top origin)
  and copies the 95 owner-approved reuse models byte for byte from the region kits that seated them (`SHARED`),
  with Four Gates' sanctuary beacon and flame as `kit-sanctuary-beacon-1` and `kit-sanctuary-beacon-flame-1`.
  It also derives the west gate's stone-ramp modules (`VARIANTS`): `kit-sw-causeway-arch-ramp-g053` and
  `-g037` are the prepared N12 scaled x0.8799 along the span and sheared up a 0.5282 or 0.3708 grade about the
  deck-top origin (rampant arches: deck, parapets and crowns follow the grade, the piers stay vertical), with
  the cut ends capped and the `Walk_` deck sheared with them. For the coast's deck dressing it derives
  (`DERIVED`) the legacy `kit-sw-causeway-arch-tier`, N12 without its parapets (its deck is renamed out of
  `Walk_`). Landfall no longer places these tiers: `repair_causeways.py` continues each top span's four
  legs down to the resolved terrain, repeating the accepted stone UV band, and closes the deck and
  parapet joints with decorative stone infills. These generated supports and joints have no `Walk_`
  child and use collision role `none`; the original walk and solid meshes remain unchanged. The tool
  records its terrain digest and every changed streamed chunk in `causeway-repair-record.json`.
  `prepare_meshy_kit.py` also derives
  `kit-sw-trestle-pier-span-long24` / `-long40`, N13 with its four bent posts lengthened to -24 / -40 m for the
  seabed trenches under the piers.
  The polish pass adds 7 more reuse models at no credits (the L12 gorge lip's waterfall sheet from Ssarathi,
  two Crownwater harbour banners, Westhaven's barrel and crate stacks, Four Gates' apple cart and feed sacks)
  and derives `kit-sw-curtain-revetment`, N3 cut at its wall walk (no merlons), a plain 11.2 m x 5 m course of
  the curtain wall's masonry that faces the castle pad's scarp and the west-gate ditch walls.
  The garden town adds 8 more at no credits: Crownwater's marble balustrade, garden hedge, pergola, rose arch,
  topiary cone, flower planter and reflecting pool, and Four Gates' sundial plinth. The town places the
  balustrade, the reflecting pool and the garden follies solid; hedges, topiary, pergolas, arches, planters and
  the sundial walk-through, as Crownwater and Four Gates place them.
  The owner's AC-4(b) call (a) of 2026-10-04 adds the gate module (`GATES`) `kit-sw-causeway-arch-span-gate`:
  the prepared N12 with its -Z parapet opened between module X -2.5 and 3.0, a pier post at each side (the end
  half-post and its mirror, at X -4.04..-2.5 and 3.0..4.54, their faces toward the opening given the posts'
  outer-face texture) and the parapet kept beyond them, so it still runs into the bank at the abutment end; the
  deck's paving copied out to the slab edge in the opening on a seam it shares with the deck (no crack, no
  T-junction); and a step stone (a block of the parapet's stone, tread 0.5 m and foot 1.6 m under the deck, X
  -2.5..0) below the opening. The opened slab edge's kerb band (down to 1.3 m under the deck) and the step are in
  the `Walk_` child; the spandrel below stays solid. It replaces B14's west abutment span 061 at its own transform
  (step `gate-061`), so the beach SE of the causeway's west end (AC-4(b) patch 406) is reached through a gap three
  tiles wide on the served fold. The high post can stand no nearer the low one: from X 2.0 or 2.5 it closes the
  deck tiles beside the opening's third row.
  The owner's call (b) of the same day accepts the CV3 ramp's neck at the B14 west end as it is, 3 tiles on the
  served fold at (1510-1512, 1384): **widen it at the next ground change there** (any sculpt, re-grade or
  bootstrap re-run touching the ramp or the ground between it and the bay-floor pocket behind it). The AC-4(b)
  pack's synthetic foot fan (ground at x 1500-1509 graded between rows 1383 and 1389) takes the local cut from 3 to
  13 tiles; measure the new export with the pack's `subsets.neck` / `localneck.local_cut` (method:
  `work-output/continent-v2/sw_isle/editor-pass/README.md`, section "AC-4(b) owner calls"), and keep the span 077
  and the gate's posts out of the widened throat.
  `prepare-meshy-kit.json` records every input and output digest; `--check` verifies them.
- `kit-sw-garden-paving-<ix>-<iz>`: the garden town's walks and lanes in the courts' limestone (game-look fix
  stage, 2026-10-02). The road shader can only darken its brown earth texture (the bake caps the worn tint at 1)
  and the editor draws at most 127 ground regions, so the curved `gt-` walks are kit pieces instead: flat strips
  along the ribbons as drawn (their width plus 0.25 m either side, round ends, the Weathered limestone masonry at
  the courts' 7.35 m repeat and tint, turned along the walk), one piece per 96 m publish chunk so each streams
  with the ground it covers, placed once at its own origin, walk-neutral. `eloria-assets/maps/continent-v2/
  sw_isle/source/garden_paving.py` writes them from `garden-paving.json` (the ribbons and the ground under them);
  `--check` verifies the outputs against `garden-paving-record.json`.

Small props (benches, urns, notice boards, lantern posts, wells, stalls, market canopies, skeps, net frames,
mooring posts, quay steps, landing stages, the beacon) start walk-through in the palette, as trees, shrubs and
ground cover do; buildings, castle pieces, rocks, cliffs, boats and spans start solid.

**Collider primitives are documentation only.** The boxes, cylinders and wedges in each root's `extras.eloria`
come from the asset reviews and are kept for reference; the map framework has no primitive-collider path. The
served export (`collision_export.py`, `_mesh_groups` and `structural_mask`) blocks a half-cell wherever a
*solid* placement's real triangle crosses the actor prism, and every `Walk_` subtree is a walk surface, never
solid. A placement's own collision role decides: the dressed causeway and pier spans are solid (their parapets
and rails bound the walk; their `Walk_` decks are walked), the extended legs and joint dressing are walk-through. The
VARIANTS and DERIVED pieces carry no extras of their own.
