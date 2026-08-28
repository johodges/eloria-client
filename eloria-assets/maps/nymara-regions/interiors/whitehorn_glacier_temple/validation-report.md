# Whitehorn Glacier Temple validation report

What was checked, and what was not.

## Automated checks

| Check | Command | Result |
| --- | --- | --- |
| glTF 2.0 validity | `_toolkit/validate_gltf.py world.glb` | **0 errors, 0 warnings** |
| Runtime contract | `_toolkit/verify_runtime.py --package .` | **0 errors**, 1 warning |
| In-engine grounding | `_toolkit/region_client_check.gd` | **PASS**, 15,129 tiles, 0 misses on walkable cells |
| Determinism | two builds | `world.glb`, `world.json`, `collision.bin` byte-identical |
| Collision dimensions | — | 246 × 222, both multiples of six |

## The one warning, and why it is not a defect

```
[warning] GROUNDING_RAY_MISS: 9892 server tiles have no walk surface under them
```

An interior is rooms inside rock. `verify_runtime` samples the whole bounding
square, and 65% of this one is legitimately not floor. Amberwood's four
interiors carry the same warning for the same reason.

The check that distinguishes a real defect from expected rock is whether the
misses land on cells the package's **own** collision grid marks walkable. They
do not:

```
[client-check] grounding: 15129 tiles sampled, 9892 misses (65.38%)
[client-check]   of those, 0 are on cells collision.bin marks walkable;
                 9892 are blocked cells and expected
[client-check] PASS
```

## A real defect this found, and the rule that came out of it

The first in-engine run reported **11 misses on walkable cells**, all along the
sanctuary stair. The cause is quantisation, and it is worth writing down because
it will catch anyone building an interior:

The collision grid is half-metre. The server samples tile centres a **metre**
apart. A corridor of half-width `h` centred on an integer therefore marks the
cell centred at `h − 0.25` walkable, while the grounding ray at the next whole
tile — at distance `⌈h⌉` — finds nothing. Any half-width in the open interval
(1.75, 2.00) produces that gap: **the server lets a player stand where the
client cannot ground them**, which is exactly the fall-through the production
guide warns about.

Widths of 3.6 m (h = 1.8) and 4.0 m (h = 2.0) are precisely the bad cases. This
package now uses 3.4 (h = 1.7), 4.4 (h = 2.2), 4.6 and 5.0 throughout, and the
rule is recorded in a comment beside the passage table in
`source/interiors_temple.py`.

**Two of Amberwood's four shipped interiors have this defect**, measured with
the same harness against the packages currently on `develop`:

| package | misses on walkable cells |
| --- | ---: |
| `amberwood_motherroot` | 36 |
| `amberwood_amber_hall` | 19 |
| `amberwood_gate_undercroft` | 0 |
| `amberwood_cinder_chapel` | 0 |

Not fixed here: they are another region's packages, Amberwood was regenerated
only recently and must stay byte-reproducible, and changing its geometry to
close these needs its own commit and its own verification. Reported so somebody
can pick it up.

## Toolkit change

`_toolkit/region_client_check.gd` previously failed a package if **any** sampled
tile missed. That is the right rule for a region, which has ground under every
tile, and the wrong one for an interior, which does not — it failed every
correctly-built interior and so could never have found the defect above.

It now reads the package's own `collision.bin` (via the `originMetres` the
interior manifests publish) and judges on walkable cells only, reporting both
numbers. Packages that publish no grid origin — the regions — keep the old
strict criterion exactly, so nothing regresses there.

## What is NOT verified

1. **No client frame.** The in-engine check runs headless, which has no
   renderer. Everything in `references/` is the offline rasteriser. Nobody has
   looked at this interior rendered by the game.
2. **No portal transition test.** The region manifest's
   `whitehorn-glacier-temple-door` portal and this package's
   `exit-to-whitehorn` name each other correctly, but no client has walked
   through either. No server was run.
3. **The interior's own detail board is truncated.** The supplied
   `references/00-concept-detail-board.png` is 786,446 bytes and does not
   decode, so there are no panel images to compare against. The ten subjects
   come from `concept.json`'s explicit list and from the parent region's intact
   board, which covers the temple facade, the shrine alcove, the ice cave and
   the mine at player scale. A panel-by-panel comparison sheet is therefore not
   possible for this package; the preview sheet is one frame per room instead.
4. **Every name is invented**, as with the region above.
5. **The server has not registered this map key** beyond the existing
   `whitehorn_glacier_temple` interior entry, which is a 32-tile procedural
   placeholder. This package fits inside it — 123 × 123 m against the 192 m the
   interior maps allow — so no server change is needed for extent, but the
   server's own generated collision for that key does not match this geometry.
6. **Performance is measured, not profiled.** 38,929 triangles and 7.2 MB;
   frame rate untested.
