# The Whitehorn Glacier Temple

The interior reached from the Glacier Temple's blue portal on the Whitehorn
Range map. Nine connected spaces answering the ten subjects the concept package
names, built with the shared interior kit and this region's own exterior kit.

## The idea

**The glacier is eating the monastery.**

The monks cut a temple into the mountain and then followed a silver vein north,
straight into the ice. The building nearest the door is intact and level. The
further in you go the more the ice has taken:

* the prayer colonnade's outer wall is cracked and bulging, with ice pushing
  through the joints and fallen ashlar below it;
* the last built arch at the north end is half-swallowed by a lobe of ice, and
  the pair of columns beside it are already off plumb;
* beyond it the masonry stops entirely and the rooms are cut in blue ice;
* deepest of all, an older colonnade stands in the altar chamber twenty metres
  from where it was built — still in two rows, still evenly spaced, every
  column leaning the same way, because they are all riding the same ice.

That gives every room a reason to look the way it does and gives the plan a
direction of travel: order behind you, ice ahead.

## Plan

```
                             mining      chasm       glacier
                             gallery <-- bridge  <-- altar
                                                        ^
                                                    ice arch
                                                        ^
votive <-- nave --> colonnade --> stair --> upper sanctuary
             ^
         snow entry  (spawn)
```

| space | floor | what it is |
| --- | ---: | --- |
| `snow_entry` | 0.0 | The narthex inside the portal. Snow blows past the door and never melts, so the threshold is drifted and the first metres of marble are under it. Benches, a boot scraper, two braziers. |
| `nave` | 0.0 | The monastery hall, vaulted, with a meltwater channel running its length to a grated cistern — the temple's water supply, and the reason this is the only room with a drain. Fourteen columns, banners, a brass gong. |
| `colonnade` | 0.0 | The prayer colonnade, and the first room that shows the ice. |
| `votive` | −0.8 | A low rubble room of dark niches, each with a lamp and a token left by someone who came up the pass. Cairns of remembrance, the same piece as the roadside ones outside. |
| `upper_sanctuary` | 7.0 | The one room the ice has not reached, and the only one with daylight: a slab of glacier ice in a silver frame where the monks cut through to the mountain face. Reliquary, silver bell, and the ice/granite/silver material study. |
| `ice_arch` | −1.5 | Where the building stops. |
| `glacier_altar` | −3.0 | A 13 m chamber inside the ice. An altar cut from the ice with a marble mensa and a crystal, ice pillars floor to ceiling, a dense icicle ceiling, and the carried colonnade. |
| `chasm_bridge` | −3.0 | A crevasse the ice opened straight through the workings, spanned by `kit.rope_bridge` — the identical piece the exterior uses on the gorge, so indoors and outdoors share one carpentry. |
| `mining_gallery` | −6.5 | What the monks were actually doing up here. Timbered sets, rails and sleepers, an ore cart, spoil, and the silver vein in the north face. |

## Runtime files

| File | What it is |
| --- | --- |
| `world.glb` | Self-contained glTF 2.0 scene, 38,929 triangles, 17 materials, 7.2 MB. |
| `world.json` | Manifest: bounds, coordinate transform, spawns, collision, navigation, 9 landmarks, 6 interactives, 4 NPC markers, 10 harvestables, 28 lights, 17 spaces, environment. |
| `collision.bin` | `EWCG v1`, 246 × 222 half-metre cells, 20,828 walkable (38.1%). The height step is fitted to this interior's own vertical range rather than the region's, so the six-bit field spans −6.7 m to +7.0 m without clamping. |
| `references/00-interior-preview-sheet.webp` | Nine offline-rendered rooms, one per space. |
| `references/godot-client-check.json` | In-engine grounding report. |

## Building it

```sh
cd ../../whitehorn_range/source
python3 build_interiors.py
python3 preview_interior.py glacier_temple /tmp/sheet.png
python3 ../../_toolkit/verify_runtime.py --package ../../interiors/whitehorn_glacier_temple
```

Deterministic: two builds produce byte-identical `world.glb`, `world.json` and
`collision.bin`.

## Verification

| Check | Result |
| --- | --- |
| `validate_gltf.py` | **0 errors, 0 warnings** |
| `verify_runtime.py` | **0 errors**, 1 warning |
| Godot 4.7.2 through the real `WorldLoader` | **PASS** — all 15,129 tiles sampled, **0 misses on any cell `collision.bin` marks walkable**; both spawns ground within 0.05 m |

The `verify_runtime` warning is `GROUNDING_RAY_MISS`: 9,892 of the 15,129 tiles
in the bounding square have no walk surface. That is what an interior is — rooms
inside rock — and every one of those tiles is a cell the collision grid marks
blocked. See `validation-report.md`.
