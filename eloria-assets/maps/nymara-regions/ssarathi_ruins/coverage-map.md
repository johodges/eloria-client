# Ssarathi Ruins coverage map

What the concept art contains, and what the build does about each of it. The
aerial (`references/01-concept-aerial-overview.png`) is the composition
authority; the ten-panel board (`references/00-concept-detail-board.png`) is the
player-scale authority.

## The ten panels

| # | Panel subject | Built as | Reachable | Capture |
| --- | --- | --- | --- | --- |
| 1 | Long paved causeway receding north between drowned ruins to a distant temple | The great causeway: a 27 m-wide jade-paved embankment on the axis at design x = 20, running 240 m from the south water gate to the temple terrace, flanked by six serpent columns in pairs, kerbed both sides, lamp-lit | yes, it is the region's spine | `01-great-causeway` |
| 2 | Stepped jade-and-gold temple front with flanking waterfalls and serpent volutes | `ssaratharch.ziggurat_temple`: five battered stages, 72 m base, 35 m of mass on a 21 m terraced precinct, scale-tiled cornices, gilt string courses, stair up the south face with serpent volutes either side, summit shrine with sun finial | yes, stair to the summit | `02-temple-facade`, `26-temple-summit` |
| 3 | Recessed portal closed by a great circular sun-disc door, steps below | `ssaratharch.vault_portal` on the tier-2 forecourt: stepped reveal, 8.8 m gilt sun disc with rayed relief, concentric gilt ring, flanking guardian faces, walkable threshold | yes, the axis ends here | `03-sun-vault` |
| 4 | Arched stone bridge over a clear flowing channel, lily pads at the banks | `ssaratharch.arch_bridge` at the great causeway's crossing of `channel_main`: 42 m span, solid elevations whose underside follows the intrados, walkable deck, balustrades, shell keystones. Six further spans of the same kit carry the other street crossings | yes, and it is the only walkable geometry that is not terrain | `04-channel-bridge` |
| 5 | Circular terraced court with concentric pools, ringed by broken columns | The ritual plaza: a 96 m paved rim holding a 57 m pool at −1.05 m, ringed by an 18-column colonnade at 11 m with a third broken, rim shrine, lily rafts on the pool | yes | `05-ritual-plaza` |
| 6 | Lily-covered pool court with tall paired columns and a stepped rim | The lily court, west of the axis: 78 m rim, 45 m pool at −0.85 m, 14 columns at 10 m, dense lily cover | yes | `06-lily-court` |
| 7 | Tall stele carrying a gold sun face, standing high above the ruins | `ssaratharch.sun_stela` on a 13.5 m rock knoll: three-course walkable plinth, 15 m slab, gilt-framed sun disc on its south face, serpent volutes down both edges | yes, a switchback ramp climbs the knoll | `07-sun-stela` |
| 8 | Broken overgrown arch with massive tree roots over it and rubble below | `ssaratharch.ruin_arch_rooted` on a raised jungle mound in the south-east: two coursed piers of unequal height, a broken arch ring with a wedge missing near the crown, fallen voussoirs, fourteen strangler roots, the tree they come from, vine curtains | yes | `08-root-arch` |
| 9 | Elevated view over the causeway network with a waterfall on the left | The north-west overlook, framing the street grid, the courts and the greater fall | it is a camera, not a place | `09-falls-overlook` |
| 10 | Macro: jade scale tiling, gilt scrollwork, a shell boss and a carved stone face | Three relics staged on the temple terrace — a shell boss, a gilt sun disc and a carved guardian face — plus the `ssarathi_jade_scale` recipe itself, which is drawn as real overlapping scales rather than a noise field precisely because this panel is a close-up of it | yes | `10-relic-macro` |

## The aerial, element by element

| Concept element | Built |
| --- | --- |
| Shallow turquoise water covering most of the basin | Water plane at y = 0 over a basin floor at −1.55 m; 58% of the playable footprint is under water, most of it under 2 m |
| Lily pads across the open water | 66 lily rafts plus 18 in the pool courts, from a 3x3 alpha atlas; placed only where the water is 0.25–2.2 m deep |
| Raised stone causeways stitching the city | 17 routes: the great causeway, five lateral streets, eleven spurs — all terrain embankments, 182 kerb sections |
| Dense masses of ruined building between them | 69 generated blocks carrying 55 ruin buildings and 21 towers; the massing pass |
| Stepped temple dominating the north-centre | yes, see panel 2 |
| Waterfalls off the cliffs behind it | Two: the greater fall (26 m) on the north wall, the lesser fall (20 m) on the north-east |
| Round colonnaded pool courts either side of the axis | Two, see panels 5 and 6 |
| Serpent-coiled columns | Six on the axis, two at the serpent gate, plus a coiled serpent on each water-gate pylon and volutes on every temple stage |
| Obelisks and spires throughout | 9 free-standing obelisks, 4 per temple stage, 21 ruin towers |
| Timber docks and jetties | Eight jetties across three landings (east, west, south), decking walkable |
| Small canvas market | 11 stalls plus a shrine on the east platform |
| Jungle closing every horizon | 2,089 trees and palms of two species over three detail tiers, 348 undergrowth clumps; the rim rises out of the water on all four sides into rock walls |
| Drowned lower town — paving visible under the water | The drowned quarter, west of the axis: a 90 m moss-stone terrace at −0.70 m with four sunken floors, 9 drowned columns and 17 rubble heaps |
| Vine and root overgrowth on the masonry | Vine curtains on the temple's stage faces, on every ruin building and tower, and on the shrines; 30 trees growing through the ruin blocks |

## Runtime coverage

| | |
| --- | --- |
| Spawn points | 3 — arrival quay (default), great causeway, temple terrace |
| Landmarks | 14 |
| Interactives | 8 |
| NPC markers | 13 |
| Harvestables | 33 |
| Portals | 4 (verdant_stair, manymouth_delta, grey_moors, westhaven) |
| Roads | 17 route polylines |
| Water bodies | 1 basin, 3 named channels, 7 bridges |
| Walk-surface node groups | 24 `Walk_` + 5 `Terrain_` |

## What the concept has that the build does not

Stated here rather than left to be discovered:

* **Vertical density.** The painting's skyline is full of multi-storey towers,
  spires and tiered facades. The build has 21 towers and a scatter of obelisks
  against the concept's dozens, and its ruin blocks are mostly one storey.
  This is the largest remaining gap and it is visible in the aerial comparison.
* **Boats.** The concept has punts and moored craft on the water. None are
  built; the docks have bollards and no hulls.
* **Figures.** The concept's staffage is not modelled — NPCs are server-side
  markers.
* **The suspended platform** in the upper-left of the aerial, apparently a
  bridge or shrine held above the water on a single pier, is not built.
* **Carved relief at facade scale.** Panel 2's temple front is covered in
  figurative carving; the build has scale tiling, string courses, volutes and
  guardian faces, and no figurative relief.
