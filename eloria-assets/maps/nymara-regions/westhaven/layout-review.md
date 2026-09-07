# Westhaven layout review — 2026-09-07

Final combined tests, complete-route checks and fresh reproduction results
are recorded in the [three-region review](../LAYOUT-PASS-2026-09-07.md).
The checkpoint counts below record this region's earlier individual pass.

This document records the Westhaven pass and the shared recipes and server
tools needed to rebuild it. The subsequent Mirrorhold pass has its own
[layout review](../mirrorhold/layout-review.md).

The port retains its terraced headland, warm roofs, stone quays, campanile and
two offshore rocks. The cart climb now closes a loop from the working quay to
the upland road; a crown link reaches the north gate, and short lanes serve the
farm, watch and delta road. The Yard Bridge crosses the shipyard gully. The
Lamp Causeway follows the tidal saddle with a sloping deck and piers, ending
on slightly lower stone landings. These connections are authored geometry.

Gullscar has a smaller farmhouse above a sheltered basin, two planted strips
and a cistern. Wheat and Sage occupy those strips, including the old resource
nodes whose IDs are retained. Shore resources use the bay and tidal shelves.
Boars and rams occupy the farm fringe, crabs and herons the bay, and hounds the
outer upland. The thirteen existing wildlife spawns are retained. The quay
groups the information board, shared storage, crafting station and combat
practice; ferry and road waygates retain their existing roles.

Town house placement now rejects overlapping roof envelopes. The gate's
turrets sit within its cap rather than sharing its top plane. Window fronts
stand clear of their timber frames. New roads, mitred causeways and planted
rows live in the shared amberwood.routecraft toolkit and use existing
procedural materials. No material block or imported asset was added.

## Evidence

| Check | Result |
| --- | --- |
| Client half-metre grid, flooded from the default quay arrival with climb limit 2 | 666,415 of 773,316 walkable cells reachable: **86.2%**, up from 476,972 of 698,755 (**68.3%**) |
| Exterior crossing trigger tiles | All four reachable in the client grid |
| Interior door trigger tiles | Six mainland/Lamp Rock doors reachable; Gullstone remains a separate island |
| New bridge anchors and both crop strips | Reachable from the default arrival |
| Independent rebuild | Identical SHA-256 for world.glb, world-lod2.glb, world.json, collision.bin, minimap.webp and camera-views.json |
| glTF validator | Exterior and LOD2: zero errors or warnings |
| Runtime grounding | 331,776 tiles sampled, zero grounding misses, zero errors |
| Coplanar overlap scan | 2,167.2 m², down from 7,028.8 m² (69.2% less); none reported on the new gate, causeways or fields |
| Client Python suite | 148 failures, 101 passed, 7,039 subtests passed; failure count matches the measured baseline |

The final server suite passes: **1,500 tests and 351 subtests**. Its Westhaven
collision export also reproduces byte-for-byte against the final profile.
Generated ferry return tiles are excluded from collision inputs on layout-authored
regions; otherwise the previous arrival could shift the next export by a few tiles.

The exterior is 29.86 MB and 994,606 instanced triangles. LOD2 is 17.57 MB and
812,822 triangles. The minimap and offline capture renderer now resolve
alpha-tested ground material names; previously those surfaces silently used
material zero, making turf and paths look like timber.

## Visual review

All 28 offline and Godot camera views were refreshed. Godot used the GL
Compatibility renderer and --environment=manifest. The eye-level review led
to widening the farm basin, reducing the farmhouse, clearing the quay court,
and correcting the causeway camera to sample its sloping walking skin.

[Cart ascent](references/godot-captures/21-cart-ascent.webp),
[Gullscar fields](references/godot-captures/22-gullscar-fields.webp),
[Lamp approach](references/godot-captures/23-lamp-approach.webp),
[Yard crossing](references/godot-captures/24-yard-crossing.webp),
[service court](references/godot-captures/25-harbour-court.webp).

[Concept comparison](references/comparisons/aerial-comparison.webp) and
[landmark contact sheet](references/comparisons/landmark-contact-sheet.webp).

The aerial remains nearly vertical while the concept is oblique. The engine
harness shows package geometry; service objects are spawned by the full
client, so the service-court capture shows its available space.

## Limits and next work

The remaining overlap is in older mole, quay, hall, roof and ship meshes.
Runtime verification also reports 300 large adjacent height changes at cliffs
and decks, and 23 sampled collision/surface mismatches around coastal edges.
This is a layout improvement, not a claim that the asset cleanup is finished.

Gullstone still has no physical connection to the mainland. Its interior and
secrets routes are retained; a direct harbour-to-island ferry remains future
work. Mirrorhold's isolated Sanctuary Road was subsequently connected through its
lake promenade. Verdant Stair's Ssarathi approach is now connected by the
surveyed terrace ascent. See the [three-region review](../LAYOUT-PASS-2026-09-07.md)
for the final combined checks.

The full continent portal command rejects two unchanged Crownwater doors
(basilica-undercroft, customs-door). Region-scoped rebuild options were
added so that checking and rebuilding Westhaven does not rewrite unrelated
region outputs. No Crownwater geometry or collision was patched.

## Rebuilding this pass

Use the normal exterior/interior/export sequence and all three collision
corrections in the order documented in CONTINENT.md, followed by secrets_build.
On the server, sync the changed exterior with sync_authored_collision.py
--region westhaven; sync changed composed maps by their own IDs when needed.
Generate the served maps, then use continent_portals.py --region westhaven,
author_region_content.py all --region westhaven, and the normal relocation
pass. The scoped portal operation includes both ends of affected links.

The content generator reads explicit world-space habitat and service positions
from contentLayout. Generated harvest clusters are excluded from subsequent
placement inputs, and scoped writes preserve the boundary between original
nodes and generated clusters. The server also retains wide intermediate height
values until stage selection; settling one outlier no longer flattens the map
to 63 units or truncates relief above 50.8 metres.
