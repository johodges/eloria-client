# Westhaven: comparison report

The build against the concept art, panel by panel. An honest reading, not a
score sheet.

The sheets are in `references/comparisons/`:

- `aerial-comparison.webp` — the concept aerial above the build's aerial
- `panel-comparison.webp` — all ten detail-board panels against their captures
- `landmark-contact-sheet.webp` — every capture in the set

**The build frames in these sheets are real Godot 4.7.2 client frames**, drawn
through the project's own `WorldLoader` with the Vulkan driver on Forward+.
They are not offline previews. The sheet says so on its own caption line, and
the provenance is recorded per frame in `references/godot-captures/index.json`.

The offline previews from the toolkit's C rasteriser are also shipped, in
`references/captures/`, using the same camera table. They are an authoring aid.
Where the two differ — the offline set is warmer and lower-contrast — that is a
difference between two renderers.

## The aerial

**What matches.** The composition transfers. A dense terracotta-roofed city on
a south-facing headland; a continuous quay across its foot; a curved mole
closing a harbour; finger piers and moored ships; two rocky masses out in the
water to the south, each with a light; open green upland with tree belts and
switchbacked roads to the north-east; a sandy bay biting into the east coast.
Everything in the painting is in the map and in the right place, because the
reading grid maps 1:1.

**What does not match.**

1. **Projection.** The concept is a three-quarter oblique from the south-west;
   the build's aerial is near-vertical. They cannot be overlaid. A matching
   oblique would compare better but would hide half the map behind the city,
   and this shot's job is coverage.
2. **Vertical drama.** The painting's skyline is spikier. Its towers and spires
   are proportionally taller and thinner than anything here, and it has perhaps
   three times as many of them. The build reads flatter from above.
3. **Density of shipping.** The painting has roughly twenty vessels and a dozen
   small jetties in the harbour. The build has nine hulls and two piers.
4. **Colour temperature.** The painting is a warm golden afternoon over
   saturated turquoise. The client frame is cooler and greyer. Some of that is
   the sun and fog values in `environment`, which are a first pass and not
   art-directed against the painting.
5. **Ground texture variety.** The painting's upland is a patchwork of ochre,
   olive and dry gold. The build's salt turf is one recipe with noise, so the
   upland reads more uniform.

## The ten panels

| # | subject | verdict |
| --- | --- | --- |
| 1 | arched harbour gate | **Partial.** The arch, piers, cutwaters and flanking towers are there and the proportion is close. The panel's gate spans open water with ships passing under it; the build's stands at the mouth of the west inlet with its feet nearer the shore, so it reads as a gatehouse more than a water gate. |
| 2 | lighthouse on a wave-battered rock | **Good.** Battered tower, string courses, corbelled gallery with an iron rail, glazed lantern, lead dome, keeper's house. The rock reads as rock. Missing: the surf. There is no spray or breaking-wave geometry anywhere in the region, and the panel is half made of it. |
| 3 | cobbled street climbing through an arch | **Partial.** The granite setts, the climb and the warehouse frontage are right. The panel's defining feature is an arch *over* the street with buildings continuing above it; the build has an open ramp street between buildings and no arch across it. |
| 4 | ship alongside with a gantry | **Good.** Pier on piles with a planked deck, shear-legs gantry with a crate on the fall, a two-masted hull alongside. Rigging is much simpler than the panel's. |
| 5 | timber cargo crane | **Good.** The treadwheel crane is the closest single object in the region to its panel: A-frames, spoked wheel, raked jib, laden net. |
| 6 | hull under construction on the stocks | **Good.** Keel, raked stem and sternpost, fifteen open frames, three garboard strakes a side, shores and keel blocks. You can see through it, which is the point. |
| 7 | fish stalls under awnings in an arcade | **Good.** Arcade with arches and a tiled roof, nine stalls with striped awnings, catch on the trestles, baskets. |
| 8 | sea wall bastion with a banner | **Partial.** The bastion is there — battered drum, merlons, banner mast, stair from the mole deck — and reads correctly. The framing looks down onto it from along the mole rather than up at it from the water, and again there is no surf on the outer face, which is most of the panel's drama. |
| 9 | rooftop terrace over a brass dome | **Good.** Colonnaded drum, ribbed brass dome, lantern and finial, balustraded terrace, city and sea beyond. |
| 10 | dockside still-life | **Weak.** The composed cluster is there — crates, barrels, sacks, fishing gear — but the panel is a tight macro of a copper-bound crate, coiled rope, chain and fish on sailcloth, and the build has no coiled-rope and no chain prop. The capture reads as a wide quay shot with props in it, not as a still-life. |

Four of ten are good, five partial, one weak.

## What would most improve the match

In the order I would do it:

1. **Surf.** Three panels (2, 8, and the aerial's whole southern half) are
   substantially made of breaking water, and the region has none. Foam
   geometry or a shoreline shader against the two rocks and the mole's outer
   face would do more for the concept match than anything else on this list.
2. **A rope-and-chain prop and a proper macro set-up** for panel 10.
3. **An arch over the market stair** for panel 3.
4. **Art-directing `environment`** against the painting rather than by
   reasoning. The sun, fog and saturation values are a first pass.
5. **More towers.** The painting's skyline has many more vertical accents than
   the four the build carries.
6. **More shipping and small jetties** along the quay.

## What this report does not say

It does not say the map is finished art. It says which subjects are present,
which are recognisable and which are not, judged by looking at the captures
beside the concept. Composition, proportion and colour are reported as I read
them; someone who owns the art direction should disagree with some of it.
