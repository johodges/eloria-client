# Look pass region files

Each map or continent region that looks different from the look pass's
defaults has one file here, `<id>.json`. `LookProfile` reads a file the first
time the id is asked for and keeps it for the rest of the session (the cache
is locked, because chunks are painted on the loader's worker threads). Every
constant in `look_profile.gd` is the default for every map; a file only says
where its map differs. **A map without a file is drawn with the defaults**,
so a missing file is never an error.

`tests/look/test_look_regions.gd` checks every file here: it must parse, name
itself, and hold nothing unknown or mistyped. Run it after editing a file:

```
Godot --headless --path godot-client --script res://tests/look/test_look_regions.gd
```

A file with a problem still loads: the bad key is left out (the default is
used) and the client prints `look region <id>: ...` as a warning.

## Which id

`<id>` is the manifest's asset id (`asset.id` in its `world.json`), which is
what `LookGround.region_of` and `LookGrade` use:

- A continent region: its id, for example `amberwood`, `grey_moors`,
  `manymouth_delta`. Its chunks (`<region>__chunk_<x>_<z>`) and its preview
  copy as a neighbour read the same file.
- A standalone map: its id, for example `lantern_reach`, `bellwatch`.
- An interior: its asset id, which is **not always its registry key**. For
  example, registry `drowned_crown` is asset `crownwater_insides`,
  `sunmane_wind_caves` is `sunmane_insides`, `resonant_vault` is
  `amethyst_barrens_insides`, `whitehorn_glacier_temple` is
  `whitehorn_insides`, `grey_moor_barrows` is `grey_moors_insides`,
  `manymouth_flooded_labyrinth` is `manymouth_delta_insides`,
  `ssarathi_royal_archive` is `ssarathi_insides`, and `amberwood_estate` is
  `amberwood_insides`. The look pass only grades and paints maps that declare
  an enabled sun, so most interiors never read a file.

## Format

```json
{
	"id": "lantern_reach",
	"schema": 1,
	"grade": {"exposure": 1.6, "exposure_forward": 1.04},
	"ground": {"verge_value_green": 0.82, "verge_green_red_forward": 0.55},
	"grass": {"root": [0.05, 0.14, 0.05], "tip": [0.4, 0.55, 0.22], "value_forward": 1.7},
	"sky": {"top": [0.16, 0.42, 0.8], "horizon": [0.66, 0.82, 0.9]},
	"water": {"decode_albedo": {"res://src/world/lantern_water.gdshader": 2.5}},
	"foliage": {"crown_materials": ["foliage_green"], "tree_words": ["palm"]},
	"notes": {"ground": "why the trims are what they are"}
}
```

- `id` must be the file's own name. `schema` is 1. `notes` is prose for
  whoever retunes the region. It can be a string or an object keyed by
  section. Write down what you measured, so the next person does not undo it.
- **Numbers** are plain JSON numbers. JSON has no integers as far as Godot is
  concerned: every number arrives as a float, and the loader turns every
  value into a float or a Color before any code sees it. So `2` and `2.0` are
  the same, and no code compares raw JSON arrays.
- **Colours** are display (sRGB) components as a `Color()` constant takes
  them, `[r, g, b]` (or `[r, g, b, a]`), or `"#rrggbb"`. Use the array form to
  keep a value exact. A hex colour rounds to 1/255.
- **Renderer suffixes.** Any number or colour key may also be written with
  `_forward` or `_compat`. In Forward+ `<key>_forward` wins over `<key>`. In
  the compatibility renderer (the OpenGL fallback, and CI's rendered tests)
  `<key>_compat` wins over `<key>`. The bare key applies in both. The tables
  (`grass.layers`, `water.decode_albedo`, the `foliage` lists) take no suffix.

## Sections

| Section | Key | What it does | Default |
|---|---|---|---|
| `grade` | `exposure`, `saturation` | Multiplies the grade's exposure and saturation (`LookGrade`). **Only for a map never streamed beside another** (an island, a tutorial map, an instance): a trim changes when the active map changes, which on the continent would step at every crossing. A continent region's `grade` section is ignored, with a warning. | 1 |
| `ground` | `path_luma`, `path_tint` (colour), `path_chroma`, `verge_value_green`, `verge_value_earth`, `verge_saturation`, `verge_green_red` | Trims the painted ground (`LookGround._set_paint`); baked into a chunk's materials when it loads. | Forward+: `GROUND_FORWARD`, else the `PATH_*` / `VERGE_*` constants |
| `grass` | `root`, `tip` (colours), `value` | The region's grass palette, root to tip, and its value trim, measured against its painted ground (tufts at 0.9-1.05 of the ground under them). Any of the three gives the region its own palette slot; missing colours come from `GRASS_PALETTE_DEFAULT`. | `GRASS_PALETTE_DEFAULT`, value 1 |
| `grass` | `layers` (table word to 0..1) | How grassy a biome layer is, by a word in its texture's file name, read before `GRASS_LAYER_WORDS` for this region's biome blends only. | `GRASS_LAYER_WORDS` |
| `sky` | `top`, `horizon` (colours) | The sky painted over a map that **declares no sky** (`LookSky`). A map with its own `environment.sky` ignores this. | `SKY_FALLBACK` (the binder's 3d7ec2 / bcc9cd) |
| `water` | `decode_albedo` (table shader path to value) | Forward+ only: a sea shader whose colours were picked in the compatibility renderer is told to decode them to linear albedo, at this value (`LookGround.decode_water`). Only maps outside the continent run it. | none |
| `foliage` | `crown_materials`, `tree_words`, `shrub_words`, `untamed_words` (lists of strings) | Extends `CROWN_MATERIALS`, `KIT_TREE_WORDS`, `KIT_SHRUB_WORDS` and `KIT_UNTAMED_WORDS` for this region's roots (`LookFoliage`). A crown material is an authored leaf material's name, compared exactly. The words are matched against the hyphen-separated words of a `kit-...` node name. | the lists in `look_profile.gd` |

## Rules learned on the pilot

- A **ground trim on ground that runs on unchanged into the neighbour draws
  the region's border as a straight seam**. Four Gates' Forward+ verge trims
  did this across the south gate field, a 13-level step. Trim a region only
  where its ground itself changes at the border, as Amberwood's moss floor
  does against Four Gates' grass. Renderer-wide changes belong in
  `GROUND_FORWARD`, not in a region. After adding a ground trim, render a
  shot across each border.
- **Grass palettes are per region, not per chunk.** The shader holds
  `GRASS_PALETTE_SLOTS` (32) palettes. Slot 0 is the default. A region with
  its own palette takes the next slot the first time the client meets it,
  and keeps it.
- The **authored leaf materials** (`foliage_amber`, `_rust`, `_gold`,
  `undergrowth`) are the continent exporter's own and shared by many
  regions, so they stay in `CROWN_MATERIALS`. Add a region's other leaf
  materials, such as `foliage_green`, `foliage_dead` or
  `fg_foliage_broadleaf`, in its `foliage.crown_materials`. Keep in mind
  that a material shared with a neighbour is painted there only if the
  neighbour's file lists it too.
- **Interiors are never graded or painted**, unless their manifest declares
  an enabled sun. A handful do: `sunmane_insides`, `crownwater_insides`,
  `ssarathi_insides`, and the Sunmane gauntlet.

## Seeing what the generic classifier does with a map

`tests/look/probe_look_classes.gd` loads maps as the client does, with the
look on, and writes JSON describing what happened to each surface:

- which ground surfaces were painted, and as what: terrain, biome verge,
  pale paving, worn cobble, a glaze patch, or a road deck;
- which ground surfaces were left alone, and why: a bridge's timber, a water
  shader, a threshold, and so on;
- how grassy each biome layer texture counts;
- what the grass beds grew;
- which foliage-looking meshes were painted as crowns and which were not,
  with the reason;
- the water materials;
- points on the painted roads, for placing survey shots.

Read it before writing a region file. Anything listed as "no crown material
or kit word" is what `foliage` can add, and a biome texture that "matched
default" is what `grass.layers` can weigh. Run it like this:

```
ELORIA_PROBE_TARGETS=targets.json ELORIA_INVENTORY_OUT=out.json ELORIA_NO_MAP_CACHE=1 \
  Godot --audio-driver Dummy --path godot-client --script res://tests/look/probe_look_classes.gd
```

`targets.json` is `[{"map": "<registry id>", "x": 0, "z": 0}]`. The point is
where the actor stands, in the map's own frame.

## The pilot files

| File | What it holds |
|---|---|
| `lantern_reach.json` | Grade trims (island), ground trims, coastal grass palette, fallback sky, sea decode |
| `four_gates.json` | Grass palette only; its old ground trims became `GROUND_FORWARD` |
| `amberwood.json` | Ground trims (dim ochre roads, a lighter earthy verge), straw grass palette |

They reproduce, value for value, the constants they replaced
(`MAP_TRIMS`, `GROUND_TRIMS`, `GRASS_PALETTES`, `SKY_FALLBACKS` and
`DISPLAY_ALBEDO_WATER` in `look_profile.gd` before 2026-09-30).
`test_look_regions.gd` pins those values.
