# Crownwater: concept versus build

Sheets in `references/comparisons/`:

- `aerial-comparison.webp` - the aerial concept beside the build's aerial
- `panel-comparison.webp` - all ten detail-board panels
- `capture-contact-sheet.webp` - all 23 client captures

**Every build capture is a real Godot 4.7.2 client frame**, produced by
`godot-client/tests/integration/rendered_crownwater.gd` through the client's own
`WorldLoader` and `WorldEnvironmentBinder`. They are not offline previews. This
is the one thing about these images a reader would otherwise have to take on
trust, so it is stated on every sheet.

## The detail board is truncated and no panel comparison was possible

`references/00-concept-detail-board.png` is exactly 786,445 bytes and its zlib
stream fails partway. **91 of 793 pixel rows decode** - 11% of the image, not
even the whole of panel 1.

The production guide predicted this defect but understates it: it says "only the
top row of five panels decodes". For Crownwater, no complete panel decodes.

Consequences, stated plainly:

- The concept half of `panel-comparison.webp` is a **written description**, not
  artwork. Each panel says so on its face and carries the description the build
  was worked from.
- The toolkit's `_toolkit/make_comparison.py` was **not** used, because against
  a truncated board it does not fail - it silently crops garbage and presents it
  as concept art, which is worse than not building the sheet.
  `source/make_sheets.py` builds the same sheets and refuses to fabricate.
- The board *was* supplied to this session out-of-band and was legible there.
  The architecture, the panel framings and the `PANELS` descriptions in
  `source/views.py` were all worked from it. What could not be done is produce a
  side-by-side image, because the pixels are not on disk.

**To get a real panel comparison, re-supply an intact
`00-concept-detail-board.png` and re-run `source/make_sheets.py`.** No rebuild is
needed; the sheet builder will detect the intact board and crop it.

The aerial comparison is unaffected - `crownwater_region_concept.png` is intact
and is a genuine side-by-side.

## Evaluation against the brief's criteria

| Criterion | Assessment |
| --- | --- |
| Overall geography, composition, silhouette | **Close.** A crowned central island, a ring of eight pavilion islets, a wider scatter of eight outer islets, and a stone causeway network stitching them together over shallow water. The concept's radial structure is the build's structure. |
| Landmark presence and relative scale | **Partial.** Ten landmarks: cathedral, campanile, eight pavilions, plus lighthouse and watch tower. The cathedral reads as the dominant silhouette at 33 m. The concept has *many more buildings per island* - clusters of halls, towers and terraces where the build has one pavilion and open ground. This is the largest single gap. |
| Architectural shape language | **Close.** Marble walls, verdigris copper domes, gilt finials, round-headed colonnades, arcaded belfries, balustraded causeways. The vocabulary is right even where the quantity is not. |
| Material and colour fidelity | **Good.** Four authored recipes carry it: veined marble, patinated copper, gold leaf, mosaic tesserae, plus lagoon sand and lagoon water. The concept's teal-and-gold-over-white signature reads at both aerial and eye level. |
| Water character | **Good.** Bright turquoise over a pale carbonate floor, darkening into the moat ring and the two approach channels. The turquoise comes from an authored water texture over a deliberately pale lagoon floor, not from a tint - a tint cannot brighten. |
| Integration with water | **Good.** Every island meets the water through built masonry - quay face, coping and apron - rather than a beach, which is what the concept does. |
| Causeways and bridges | **Good.** 22 crossings on real arched masonry, decks walkable, balustraded, spanning only the open water between island edges. |
| Vegetation | **Partial.** Palms and clipped hedges, ~500 instances. The concept is markedly lusher, with planting spilling over terraces and between buildings. The garden islet's concentric beds read; the rest is sparse. |
| Player-scale detail | **Partial.** Bollards, mooring rings, lamp standards, banner poles, moored boats, market stalls and the compass-rose inlay hold up at 1.7 m. Away from the harbour and the crown plaza the islands are thin. |
| Terrain | **Adequate but the weakest element.** Island edges are visibly stepped where the plateau falloff meets the 2 m terrain grid, and the waterline is faceted at 3.5 m. Neither is present in the concept. |
| Lighting and atmosphere | **Good.** Verified in-client rather than asserted: high sun, low fog, bright sky, and the palette holds. Golden-hour variant declared and captured. |
| Navigation readability | **Good.** Every island is reachable by causeway, decks own their cells, and the ring plus spokes make the route structure legible from the air. |
| Performance | **Comfortable.** 1,271,396 instanced triangles over 331,776 m2 - about 3.8 per square metre, against Amberwood's 9.5 and inside the repository's 1.5 M desktop guideline. |

## The honest headline

The build matches the concept most closely at the **composition and material**
level - the radial archipelago, the causeway network, the marble-and-verdigris
palette and the turquoise water are all genuinely there, and they are there in a
real client frame rather than an offline preview.

It matches least closely at **density**. The concept is a *city*: every island
carries a cluster of buildings, terraces and planting. The build gives most
islands a single pavilion on open ground. Nothing about the toolkit or the
approach prevents fixing that - it is a further population pass over
`populate.py`, using kit that already exists - but it is not done, and the
aerial comparison shows it immediately.

The second gap is **terrain finish**: stepped island edges and a faceted
waterline are the artefacts a reviewer will notice first at close range.

Read the sheets as evidence of what is actually built and where the remaining
art distance is, not as a claim that the two images match.
