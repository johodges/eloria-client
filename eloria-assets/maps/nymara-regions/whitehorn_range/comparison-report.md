# Whitehorn Range comparison report

Concept sources against the build. Sheets are in `references/comparisons/`.

**Every capture except `90-godot-client-spawn.png` is from the toolkit's offline
C rasteriser, not from Godot.** They are an art-direction tool. The one real
client frame is labelled below and is lit by the check harness, not the game.

## Aerial — `comparisons/aerial-comparison.webp`

Source: `eloria-assets/concepts/nymara-regions/whitehorn_range_region_concept.png`
(intact, 622 KB). This is the composition authority and it was matched
structurally rather than pixel for pixel.

| Concept element | In the build | Notes |
| --- | --- | --- |
| Bowl opening south, rising north | yes | `add_slope` + boundary ridges; 6 m to 180 m |
| Glacier temple high at the north end | yes | on a cut shelf at z = -309 |
| Central glacier tongue running south | yes | authored ICE route, 45 m wide, with 77 seracs |
| Gorge crossed by rope bridges | yes | one cut across the map, two spans |
| Cairn-lined approach from the south | yes | 177 cairns |
| Ice cave, west | yes | teal-lit mouth |
| Mine, east | yes | timbered portal with rails |
| Frozen cascades off the shoulders | yes | two |
| Conifers on the lower slopes only | yes | 870, gated below the snow line |
| Peaks ringing the region | **partially** | see gaps below |

### Where the aerial does not match

Honest list, in order of how much it matters.

1. **The boundary reads as a rectangular lip with square corners.** This is
   the largest visual departure, and the aerial shows it plainly: the
   south-west and south-east corners are visibly right-angled. `clamp_edges`
   raises a continuous rim on a rectangular foot, so on a region walled on all
   four sides — which Whitehorn is, having no coast — the world boundary reads
   as the edge of a table rather than as mountains. The concept has individual
   summits with sky between them.

   It is not inherent to a heightfield. The fix is a ridged wall on an
   irregular foot rather than an axis-aligned ramp: `add_ridge` along a wandering
   boundary polyline, with summit domes at intervals, so the silhouette breaks
   up and the corners round off. The Mirrorhold build has since written exactly
   this as `region._close_world`, and adopting it is the single highest-value
   change available to this region's terrain. It is deliberately **not** done
   here, because it would mean rewriting the world boundary after the package
   was verified and pushed; it should be the first thing done next.
2. **Relief is gentler than the painting.** The concept implies near-vertical
   faces; the build tops out around a 1.2 gradient because anything steeper
   stops being walkable and starts breaking the grounding contract.
3. **Surface boundaries stair-step.** The terrain cell is 2 m and material is
   assigned per cell, so class edges are visible as small rectangles from the
   air. `dither_boundaries` is turned down to 0.18 because a heavier dither made
   it worse, not better.
4. **The concept's structures are more numerous.** It suggests small buildings
   scattered on several ledges; the build has the temple, gate, three shrines,
   three watch posts and three camps.

## Detail board — `comparisons/panel-comparison.webp`

**The concept side of this sheet is a placeholder.** The supplied
`references/00-concept-detail-board.png` is truncated to 786,445 bytes and does
not decode at all. The panels below were worked from the board as shown in the
authoring conversation, so the build follows it — but the sheet cannot prove
that until an intact board is dropped at that path, after which
`make_comparison.py` regenerates it unchanged in every other respect.

| # | Panel | Capture | Built |
| --- | --- | --- | --- |
| 1 | Cairn-lined approach road | `01-approach-road` | road, cairns, gate, temple visible up-valley |
| 2 | Temple facade, glowing arch, statues, braziers, inlaid plaza | `02-glacier-temple` | marble facade, blue crystal portal, arch ring, two robed figures on plinths, flanking columns, four brass braziers, circular brass inlay, snow cap and icicle fringe |
| 3 | Rope-and-plank bridge | `03-rope-bridge` | 34 m span, four cables, hangers, plank deck, timber posts, rubble abutments |
| 4 | Statue shrine in an arched alcove | `04-gate-shrine` | recessed marble alcove, arch ring, statue, steps, two brazier blocks |
| 5 | Cairn field on a ridge | `05-cairn-ridge` | 44-cairn cluster plus waystones |
| 6 | Ice cave mouth | `06-ice-cave` | ice mass, tapered throat, broken-ice rim, icicle fringe |
| 7 | Timbered mine entrance with rails | `07-mine-portal` | stone surround, timber frame and lintel, dark adit, rails, sleepers, spoil heaps |
| 8 | Frozen waterfall with waystones | `08-frozen-cascade` | 20 m lobed icefall, icicle fringe, waystones at the foot |
| 9 | High overlook panorama | `09-high-overlook` | view north across the glacier to the temple |
| 10 | Material study: rope, brass, ice, stone | `10-material-study` | bridge anchor close-up: rope cable, iron cap, timber, ice, dressed stone |

### Panel-level gaps

- **Panel 10 is the weakest.** The board shows a gem-set clasp and a chalice as
  hero props; the build answers with a bridge-anchor material study. No
  jewellery or vessel props were authored — they are inventory-scale objects
  and there is no prop kit entry for them.
- **Panel 1's party of travellers** is not represented. Actors are server-owned
  and never baked into the static mesh.
- **Panel 7's hanging lanterns** are absent; the mine portal has the frame,
  rails and spoil but no lighting props.
- **Panel 2's plaza is smaller** relative to the facade than the board implies.

## Other views — `comparisons/landmark-contact-sheet.webp`

Thirteen views that answer no panel: spawn grounding, gorge edge, upper bridge,
temple forecourt, glacier snout and head, mine yard, south gate, pine shelf,
north shrine, west watch, east camp, snow line, plus two golden-hour passes.

## Real client frame

`references/captures/90-godot-client-spawn.png` — Godot 4.7.2, through
`WorldLoader.load_world()`, OpenGL compatibility renderer, RTX 5080. It shows
the geometry loading and rendering in-engine. Its lighting is a bare
directional light and procedural sky created by `tools/region_client_check.gd`,
**not** the game's environment, so it is evidence of load correctness and not of
final appearance.
