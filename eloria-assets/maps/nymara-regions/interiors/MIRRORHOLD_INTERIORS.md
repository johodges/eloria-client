# Mirrorhold interiors

Three interiors, authored to answer questions the exterior raises rather than
to add generic dungeon. Built by `mirrorhold/source/build_interiors.py` from
`mirrorhold/source/interiors_mirrorhold.py`, on the shared interiors toolkit.

| id | name | entered from | class |
| --- | --- | --- | --- |
| `mirrorhold_lens_vault` | The Lens Vault | the orrery drum, summit | workshop |
| `mirrorhold_cistern` | The Mirror Cistern | the fountain plaza | works |
| `mirrorhold_stair_cellars` | The Stair Cellars | the cliff town | cellar |

## Why these three

The region is an observatory of mirrors on a glacier mountain. Each interior
explains something the exterior only asserts:

**The Lens Vault** is where the mirrors are made, so the instrument on the
summit has a workshop under it. Its plan is a working sequence rather than a
loop — grind, anneal, then test against the still pool in the well. The
instrument of record is a *liquid* mirror: a shaft over black water, which is
a real technique and the literal reading of the region's name.

**The Mirror Cistern** is the waterworks. Glacier meltwater arrives loaded with
rock flour — which is what makes the lake turquoise and what would ruin a
reflecting basin — so it is dropped through a settling basin, filter beds, and
finally a stilling floor wide and shallow enough to go glass-flat. It explains
both the terrace pools and the colour of the lake in one room.

**The Stair Cellars** are the lived-in counterweight: rubble instead of dressed
stone, glacier ice bedded in sawdust, a niche shrine, and a long stair down to
a barred water gate the citadel would rather not inventory.

## Areas

| interior | areas |
| --- | --- |
| Lens Vault | stairhead, sighting floor (meridian line, oculus), grinding room (laps, blank racks, drive shaft), annealing room (ice-lined), mirror well (liquid mirror, -7.2 m), chart aisle |
| Mirror Cistern | sluice hall (gates), settling basin (baffles, spoil), stilling floor (walkway, columns in water), filter racks, pump gallery |
| Stair Cellars | cellar head, common cellar, cold larder (ice store), rock shrine, water gate (-8.4 m, boat) |

Sixteen rooms and nine connecting passages in total.

## Verification

Each package carries `world.glb`, `world.json`, `collision.bin`, its validator
report and `client-check-report.json`.

| | tris | GLB | walkable cells | validator | in-engine |
| --- | --- | --- | --- | --- | --- |
| Lens Vault | 11,180 | 5.40 MB | 7,652 | 0 errors | PASS |
| Mirror Cistern | 8,230 | 4.52 MB | 8,424 | 0 errors | PASS |
| Stair Cellars | 6,620 | 4.51 MB | 4,384 | 0 errors | PASS |

The in-engine column is `_toolkit/region_client_check.gd`: Godot loads the
package through the project's own `WorldLoader` and casts `main.gd`'s grounding
ray at **every** cell the collision grid marks walkable. All three report zero
cells without a surface, and both spawns per interior land within 0.05 m of
their manifest height.

That check was extended for this work. Its previous pass condition — every tile
in the bounding box must have floor — is right for a region, whose terrain
covers everything, and wrong for an interior, which is rooms inside solid rock
and whose box is mostly *meant* to have no floor. It now tests the contract
that holds for both: every cell the collision grid calls walkable must have a
surface under it. Re-run against both regions afterwards, which still pass.

## Captures

`references/godot-captures/` in each package: real Godot 4.7.2 frames on a
Vulkan device, one per area plus a plan overview, generated from the manifest's
own space list by `_toolkit/interior_views.py` rather than maintained by hand.

The capture harness now honours what a package declares — `sky: "none"`, the
ambient and fog block, and the point lights standing in its lamps — instead of
lighting every package with an outdoor sun. An interior lit as though it were
outdoors is not a picture of anything that will exist.

## Known gaps

- **No concept art.** These three are inventions: the repository has interior
  concept packages for `drowned_crown` and `resonant_vault`, but neither is
  Mirrorhold's (see below), and there is no board for these. Nothing here was
  compared against concept art because there is none to compare against.
- **Names are placeholders**, as everywhere else in this region.
- **No server maps.** These need `maps/nymara/mirrorhold_*.elm` entries and
  portal pairs in `config/eloria/maps.txt` before they are reachable in play.
  The client registry entries are in place.
- **Lighting is declared, not baked.** The manifests carry point lights; there
  are no lightmaps.

## The two interiors that are not Mirrorhold's

`drowned_crown` and `resonant_vault` both had entrances from Mirrorhold in an
earlier pass of this region. Both were wrong, in different ways:

- **`resonant_vault`** declares `parentRegion: amethyst_barrens` and the server
  links it to `four_gates`. Mirrorhold had no claim on it at all; the portal
  was mine and has been removed.
- **`drowned_crown`** declares `parentRegion: crownwater`, but
  `config/eloria/maps.txt` has linked it to `mirrorhold` since before any of
  this work:

  ```
  portal | mirrorhold | 58 | 100 | drowned_crown | 58 | 12
  portal | drowned_crown | 58 | 10 | mirrorhold | 58 | 98
  ```

  The concept data and the server disagree, and they have disagreed from the
  start. The Crownwater session is authoring it as a Crownwater interior.
  Mirrorhold's portal to it is **left in place and marked contested** rather
  than removed: deleting a link the server still serves would resolve the
  conflict in one direction on no authority. This needs a decision from whoever
  owns the concept data, and then one edit in one place.
