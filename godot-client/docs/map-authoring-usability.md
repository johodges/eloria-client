# Map editor usability

The map editor still runs inside Godot, but the placement and viewport tools now work more like a dedicated map editor. Three plugins are involved:

- **Map Assets** (`addons/map_asset_palette`): the asset library with its drop-in model folder, ghost placement, and prefabs.
- **Map Authoring Usability** (`addons/map_authoring_usability`): the cursor readout, the cursor grid, the **Map tools** menu, the toolbar toggles, the selection bar, groups and copies, readable gameplay markers, the walkability overlay, road and river drawing, ground regions and plateaus, the play-test walker, the **Minimap** dock, the low-spec view, the time-of-day preview and the top-down capture.
- **Territories** (`addons/map_authoring_workspace`): now also has sculpt brush keys (see [terrain-sculpting.md](terrain-sculpting.md)), heightmap import and a **Browse…** map picker.

The map team's answers on what each tool may write are in [map-team-editor-contracts.md](map-team-editor-contracts.md).

Everything in this document works in production region scenes, and everything except the terrain-based tools works in the pilot. None of it changes the save, snapshot, or bake contracts. Ghosts, grids, pins, the walker and every other helper are ownerless nodes, so they are never packed into a scene. The only new thing a scene saves besides ordinary controls is the group tag on grouped objects; the snapshot's geometry and gameplay records ignore it, although saving the scene changes its source hash as any save does. Every edit goes through Godot's normal undo history, which you can see and jump through in the **History** dock next to FileSystem.

## Toolbar

The 3D toolbar has one-click toggles next to **Map tools** and **Time**:

| Button | What it switches |
|---|---|
| **Grid** | The cursor grid all the time (off: only while placing). |
| **Snap** | Grid snapping for placement, copies and drawn points (same as G). |
| **Ground**, **Plateau** | Open the ground-region or plateau options (see below). |
| **Pins** | Gameplay marker pins and labels. |
| **Walk** | The walkability overlay mode (a small menu). |
| **Play** | The play-test walker. |
| **Low spec** | The low-spec view. |

The buttons and the **Map tools** menu always agree; either can be used.

## Place assets

### Choose and arm an asset

1. Open **Map Assets**. The library is a thumbnail grid; switch **Grid** off for a plain list.
2. Search, or pick a category. Prefabs appear in their own **Prefabs** category.
3. Select an asset and press **Place on terrain**, or double-click the asset.

Thumbnails are rendered from the models themselves and cached in the editor cache folder, so only the first open of the library takes time.

### Place it

A see-through, blue-tinted ghost follows the cursor over the terrain. It shows exactly what the next click will create.

| Input | Action |
|---|---|
| Click | Place the asset. With **Keep placing** on (the default), you stay in placement mode, so you can click again and again. |
| Right-click or Escape | Stop placing. |
| Alt+drag | Orbit the camera, as usual. |
| Q / E, or Shift+mouse wheel | Turn the asset (15° steps). |
| Page Up / Page Down | Raise or lower it (0.25 m steps). |
| Home / End | Grow or shrink it (10% steps). |
| Shift with any of the keys above | Use fine steps: 1°, 0.05 m or 1%. |
| Backspace | Reset turn, height and size. |
| G | Toggle snapping to the territory grid. |

Two text lines at the bottom of the 3D view show the current turn, lift, size and snap, and list these keys.

### Placement options

The **Placement options** section of the dock has these settings:

- **Keep placing**: stay in placement mode after each click.
- **Random turn**: give each placed asset a random turn.
- **Size ±**: vary each placed asset's size by up to this percentage.
- **Align to slope**: tilt the asset so it follows the terrain slope.
- **Snap to grid** and **Grid**: snap placement to the grid, and set its spacing in metres. The default is 1 m, which is one server tile in production regions.

The ghost is re-rolled after every click, so it always shows what the next click will create.

These options are per-user preferences stored under **Editor Settings > Map Authoring**. Every key in the table above can be rebound under **Editor Settings > Shortcuts > Map Authoring**.

### Add your own models (no JSON)

Any `.glb`, `.tscn` or `.scn` file under `res://assets/world/library/` is a palette asset. A first-level subfolder names its category: `library/Rocks/boulder.glb` is listed as **Boulder** under **Library: Rocks**; files directly in `library/` are under **Library**. Press **Refresh** after adding files yourself.

**Import models…** does the copying for you: type a category (for example `Rocks`) and pick one or more `.glb`/`.gltf` files anywhere on disk. A `.glb` is copied as it is; a `.gltf` is converted to one self-contained `.glb`, because the bake accepts only static GLB sources. Nothing is overwritten, and the palette lists the models once Godot has imported them. A `.gltf` dropped into the folder by hand is not listed; Refresh says so. **Folder** shows the library in the FileSystem dock.

Library assets place like catalog ones. Their catalog id is `library:<category>/<name>`, and the scene path goes into the snapshot like any other asset's. Being listed is not the same as being admitted to production: prefer self-contained static GLB models with a Node3D root, metre-scale geometry and PBR textures; the bake still checks surfaces and paths. The collision role starts from the category name (`solid` when it contains "structure", "interactive" or "landmark", otherwise `none`). Treat that as a suggestion, choose `walk_surface` deliberately, and leave collision changes to the map team's review.

### What gets created

Assets are placed as before. They become `MapAuthoringAssetControl` wrappers under `AuthoredAssets`, with a fresh asset id, the catalog id, the scene path and the default collision role. Grounding uses the visible mesh bounds, and each click is one undo step.

## Cursor readout and grid

### Cursor readout

While the cursor is over authored terrain, the bottom-left of the 3D view shows:

- territory-local X and Z in metres;
- the server tile, using the snapshot conversion `floor(x/metres_per_tile + server_origin.x)`, `floor(server_origin.y - z/metres_per_tile)`;
- the ground height;
- the number of selected placements.

### Cursor grid

The cursor grid is a small grid that drapes over the terrain around the cursor and follows its height. It turns gold while snapping and marks the exact snap point.

Choose when it appears with **Map tools > Cursor grid**: **Off**, **While placing** (the default) or **Always**. **Map tools > Cursor readout** hides the text line.

The grid needs region terrain. The pilot has no fast height query, so the grid is not shown there.

## Map tools menu

**Map tools** in the 3D toolbar works on the current selection. It only ever touches assets, cosmetic scenery and gameplay markers. Terrain patches, paths, bridges, water and ground regions are never moved by it.

| Item | What it does |
|---|---|
| **Drop selection to ground** | Re-seats each object's visible base on the terrain under it. Use it after sculpting, because objects do not reground automatically. |
| **Rotate each 90°** | Turns every object about its own pivot, not the selection centre. |
| **Random turn for each**, **Random size for each** | Scatter variation. Random size keeps each object's base on the ground. It uses the **Size ±** amount, or ±15% when that is 0. |
| **Save selection as prefab** | Saves the selection as a prefab (see below). |
| **Group selection**, **Ungroup** | See [Groups and copies](#groups-and-copies). |
| **Duplicate with fresh ids** | Copies the selection one grid step south-east with new ids (see below). |
| **Play test** | Starts or stops the play-test walker. |
| **Low spec view** | Switches the low-spec view. |
| **Time of day preview…** | Opens the time panel (see below). |
| **Capture top-down image…** | Saves a map image of the territory (see below). |

Each item is a single undo step. The items can be given keys under **Editor Settings > Shortcuts > Map Authoring**; they are unbound by default.

## Selection bar

While placed assets, scenery or markers are selected, a bar under the 3D view shows what is selected and lets you type exact values:

- **X / Y / Z**: territory-local metres (the same frame as the cursor readout).
- **Turn**: degrees about the vertical axis. **Size**: uniform scale; a single asset keeps its visible base on the ground.
- With several objects the bar shows their centre. Typing X, Y or Z moves them together; **Turn by** and **Scale by** turn or scale the whole selection about its centre and then reset to 0 and 1.
- Buttons: **Drop**, **Rotate 90°**, **Duplicate**, **Group**, **Ungroup**, **Edit members** and **Save prefab**.

Every change is one undo step.

## Groups and copies

**Groups.** Select two or more placed objects and press **Ctrl+G** in the 3D view (or **Group** in the selection bar or Map tools). Clicking any member then selects the whole group, so it moves, turns and copies as one. **Ctrl+Shift+G** ungroups.

- **Pick one member:** double-click it, or press **Edit members**. The group stays open for single picks until you select something outside it.
- **What is saved:** each member keeps its place in `AuthoredAssets` or `Gameplay`; a group is only a `map_authoring_group` tag in the members' node metadata (not the asset's exported `metadata` dictionary). The snapshot's object and gameplay records ignore it; saving the scene still changes its source hash, as any save does.
- Ctrl+G and Ctrl+Shift+G group only while the 3D view has keyboard focus (click in it first). Elsewhere Godot's own **Group Selected Nodes** shortcut, which makes clicks on children select their parent, takes those keys. The **Group** button always does the map group.

**Copies.** Hold **Alt** and drag a selected object: a ghost of the selection follows the cursor and the copies are dropped where you release (Esc cancels). **Duplicate** in the selection bar or Map tools copies one grid step away instead. Either way the copies are one undo step and are selected afterwards.

- Every copy gets a fresh asset id or marker record id, its own copies of local material overrides, and new group ids (a copied group becomes a new group).
- Each copy keeps its height above the ground, so copies on a slope sit on the ground.
- A marker that follows a copied asset follows the copy; a marker copied without its asset stops following. Runtime bindings are never copied, and a copied default spawn is not a default spawn.
- Other marker fields (portal destinations, linked nodes, extras) are copied as they are; check them in the Inspector.
- With **Snap** on, the drag moves in whole grid steps.

**Godot's Ctrl+D.** It keeps the original asset and record ids, and the snapshot rejects two objects with one id. In the 3D view, Ctrl+D on placed objects is therefore redirected: it duplicates them in place with fresh ids. A duplicate made another way (the Scene dock's Duplicate) is caught within a second: a warning appears at the top of the 3D view and **Map tools > Give duplicated copies fresh ids** fixes it in one undo step. Only the copies change; the originals keep their ids. Ids are compared the way the snapshot compares them (assets together, each gameplay kind on its own), and duplicates a scene already had when it opened, such as Manymouth's retained `stelae-court` pair, are left alone.

Alt+drag on empty ground, or while placing, still orbits the camera.

## Prefabs

### Save a prefab

1. Select placed assets.
2. Type a name next to **Save selection** in Map Assets, then press it (or use **Map tools > Save selection as prefab**).

The prefab is written to `res://world_authoring/prefabs/<name>.tscn`, and **Folder** shows it in the FileSystem dock.

### Place a prefab

Prefabs hold placed assets only. Selected gameplay markers and other controls are left out, and the message says how many.

Place a prefab like any other asset: the ghost shows every member, and turn, lift, size and snap apply to the whole group.

- Members follow the terrain. Each member keeps the height above the ground it had when the prefab was saved, so a camp placed on a slope still sits on the ground.
- Each placement creates ordinary, independent assets. They get fresh asset ids and their own copies of local material overrides.
- Placing a prefab is one undo step. The prefab file itself never enters a bake or snapshot.

## Gameplay markers

### Place markers

**Map Assets** has a **Gameplay markers** category. It offers one plain entry for each marker kind the region snapshot exports:

- Spawn point
- Portal
- NPC
- Harvestable
- Interactive
- Landmark
- Herd / ambient animals

**Templates.** The open territory also adds templates copied from its own markers, for example "Harvestable: Crystal (mineral)". A template copies that group's label (for harvestables) and extras, such as the harvest hook, extent, NPC role or herd model. Position-specific extras are never copied: prop positions, destination tiles and rotations.

**Placing.** Markers place like assets: a coloured ghost pin follows the cursor, and snapping, lift and keep-placing all work. Q/E turn a spawn's or portal's facing.

**What gets created.** Each new marker gets a fresh record id of the form `<label>-NN`, unique in the territory. It goes into its kind's `Gameplay` container, and each marker placement is one undo step.

**Follow-up in the Inspector:**
- Portals still need **Destination Map** and **Destination Spawn**.
- NPCs start unnamed.

**Runtime points are left out.** They bind certified server records, so they are never created in the editor.

### Readable markers

Every gameplay marker is drawn as a coloured pin with its label (or record id):

| Colour | Kind |
|---|---|
| Green | Spawn |
| Violet | Portal |
| Blue | NPC |
| Orange | Harvestable |
| Cyan | Interactive |
| Gold | Landmark |
| Pink | Herd |
| Grey | Runtime point |

- Spawns and portals show a facing arrow.
- Harvestables show their extent, and herds show their radius.
- Labels fade out beyond 140 m.
- Switch pins or labels off under **Map tools > Gameplay markers**.

## Walkability overlay

**Map tools > Walkability overlay** tints the terrain in one of three modes.

| Mode | What it shows |
|---|---|
| **Published grid (exact)** | The served grid from the territory's published `collision.bin` (EWCG-v2, half-metre cells), exactly as the server walks it after the last publish. |
| **Live suggestion from authoring** | A 1 m-tile estimate from the current scene, using the bake's rules in `collision_export.py`. Rebuilds itself about half a second after edits settle; not during a sculpt stroke. |
| **Changes since publish** | Tiles where the live suggestion disagrees with the published grid: what the next bake is likely to open (green) or close (magenta). |

A legend sits at the top right of the 3D view. The cursor readout adds the tile's published state and its live class: "too steep (grade 0.82)", "blocked by Camp00_Cart", "deck of Harbour_Stair".

The live suggestion classifies each tile as follows:

- **Grade.** The terrain triangle's slope must be at most 0.65. This is computed exactly from the saved heights, and a tile takes the worst of the triangles its half-cells fall in, like the served grid's fold.
- **Water.** A tile is blocked when it is more than 0.35 m under water. Water means:
  - the sea level from the territory's manifest (or the continent plan);
  - authored rivers, using their point heights as the water surface;
  - water regions.
- **Structures.** Solid assets block the actor's body, from 0.06 m to 2.10 m above the ground. The live suggestion estimates this from each mesh's bounding box; the bake tests the actual triangles against the body at every half-metre cell and also blocks the inside of closed meshes, so pens, fences and archways are exact only in the published grid.
- **Decks.** Walk-surface assets use their upward triangles within the grade limit; procedural bridges use their deck quads.
- **Ownership.** Only land inside the territory's ownership polygon is shown.

How close it gets, measured against the published grids of three territories:

| Territory | Tiles agreeing with the published grid |
|---|---|
| Sunmane Steppe | about 98% |
| Verdant Stair | about 97% |
| Westhaven | about 98% |

It builds in 0.1–0.25 s.

Where it differs:

- **Open structures.** Pens and fences are over-blocked, because they are estimated by their boxes.
- **Planned water.** Lakes and rivers that exist only in the continent plan are missing, because the authoring scene doesn't contain them.
- **Bake-only rules.** Seam and gate halos are not reproduced.

Use **Published grid** for the truth, and **Changes since publish** to judge an edit.

## Draw roads and rivers

**Map tools > Draw road** (or **Draw river**) lays out a new path by clicking on the terrain:

| Input | Action |
|---|---|
| Click | Add a point. The draft drapes over the ground at its full width while you draw. |
| Double-click, Enter or right-click | Finish. |
| Backspace | Remove the last point. |
| Esc | Discard the draft. |
| `[` / `]` | Change the width (Shift gives fine steps). |
| G | Toggle grid snapping. |

A click within 2.5 m of an existing path point snaps onto it exactly, so new paths join cleanly.

**Extend a road.** Start drawing on either end of an existing road (or river) and the new points are added to that path instead of a new one: it keeps its id, surface, width and settings. Starting on the last point appends; starting on the first point adds the new points in front. The extension is one undo step. To start a separate path at an end, Ctrl+click it.

Finishing creates an ordinary `MapAuthoringRegionPath` under `Roads` or `Rivers`, as one undo step:

- **Id:** a fresh `road-NN` or `river-NN`.
- **Replacements:** no route or plan-feature replacement, since the bake only suppresses a composer route that a path names exactly.
- **Routing role:** `required` for roads and `decorative` for rivers. The baseline pipeline only validates this role.
- **Shape terrain:** on for roads, with feather 2, as new roads should be.
- **Surface:**
  - roads: the territory's road surface, or a Worn earth road surface from the same factory the bake checks;
  - rivers: default water.
- **Point heights:** taken from the ground under each click. A road grades the ground between them. A river's heights are its water surface, and the river carves its channel below.

Afterwards Godot's Path3D tools and the Inspector edit the path as usual.

Drawing, asset placement and sculpting are mutually exclusive; starting one stops the others.

## Play test

**Play** (or **Map tools > Play test**) puts a stand-in character on the open territory:

| Input | Action |
|---|---|
| Click the ground | Place the walker, then walk it there on the next clicks. |
| Shift+click | Place the walker somewhere else. |
| R | Switch between walking and running. |
| F | Centre the 3D view on the walker. |
| Esc or right-click | Stop the play test. |

The route is the one the server would take:

- **Grid.** The server walks one-metre tiles. Its grid is folded from the territory's published package (`collision.bin`): a tile is blocked when any of its four half-metre cells is, otherwise it takes the highest, and heights become codes at the map's stage (1.4 m on Sunmane, 4.8 m on Whitehorn). The walker repeats that fold; on 26 September 2026 it matched the server's grids byte for byte on all twelve territories. On a map with less than 12.4 m of relief the server may choose a coarser stage, and the message says so.
- **Steps.** Neighbours are tried N, NE, E, SE, S, SW, W, NW. A step needs both tiles walkable and a code change of at most 2 (`max_walk_height_change`); a diagonal also needs both of its orthogonal steps. The search gives up after 100 000 tiles, a route is at most 512 steps (click again to go on), and a click on a blocked tile goes to the nearest walkable tile within 19.
- **Pace.** 600 ms a metre walking and 200 ms running, times √2 on a diagonal.
- **Heights.** The walker stands on the terrain, or on the published deck height where a bridge or floor is higher.

A territory that has never been published uses the live walkability suggestion with the same rules; those routes are estimates. The live server also accounts for other players and creatures, doors and portals, storage-body footprints and a few legacy floors, which the walker does not. Loading the grid takes about 0.1 s on Sunmane; routes take 30–600 ms, and up to about a second when the search runs out.

The walker, its route line and goal ring are never saved. Starting placement, sculpting, road drawing or a ground tool ends the play test.

## Paint ground regions

**Ground** (or **Map tools > Paint ground regions…**) opens the options: a surface (one the territory already uses, or a texture preset), the shape, feather, opacity and priority. **Start drawing**, then press where a region's centre goes and drag out its size. Each release adds an ordinary ground region control under `Ground/Regions` with a fresh `ground-NN` id, one undo step each; the tool stays armed until Esc (with no draft) or right-click. `[` and `]` change the feather.

- A shared surface file is reused as it is, so later edits to it change every region using it; a surface embedded in another region is copied, and a preset makes a new local surface.
- The region and its feather must stay inside the land the territory owns.
- A territory holds at most 127 ground regions, the most the terrain preview draws; the tool refuses more.

## Stamp plateaus

**Plateau** (or **Map tools > Stamp plateaus…**) creates terrain patches under `Terrain/Patches` the same way: press at the centre, drag out the size. **Level at a height (Set)** flattens the ground to the chosen height above the point you pressed; **Raise or lower (Add)** moves it by a delta. Page Up and Page Down change the height, and `[` / `]` the feather. Each stamp is a `stamp-NN` patch, one undo step.

- A stamp may only touch ground the sculpt brush could edit fully: none of its terrain samples may be locked or in the faded border band. The tool refuses a stamp that reaches them, and it only starts once the Territories dock has loaded the territory's borders.
- Patches apply before road and river shaping, so a road running through a plateau still grades its own corridor.
- A plateau shapes terrain only: it does not make ground walkable (the 0.65 grade, water and structure rules still apply) and cannot make caves or overhangs.

## Import a heightmap

**Territories > Import heightmap…** writes a greyscale image into the terrain's sparse sculpt layer. Choose the image, **Replace heights** or **Offset heights (add)**, the height black maps to and the height white maps to (there is no implied scale), and the area it covers in terrain metres (it starts as the whole terrain grid). The image's top row is north.

- **Replace** sets each editable sample to the image's height; **Offset** adds the image's height to what is there.
- Borders are protected as for the brush: locked samples never change and the fade band blends in. The original base height file is never rewritten, and the layer stays bound to it, so a changed base rejects the layer.
- It is one undo step, saved with the scene like any sculpt. Patches and road and river shaping still apply on top, so the finished ground can differ from the image where those are.

## Minimap

The **Minimap** dock shows the open territory from above, north up, clipped to the land it owns:

- the 3D camera as a blue dot with its view direction;
- the selection as orange squares;
- gameplay markers in their pin colours (when **Pins** is on);
- the play-test walker and its route.

Click or drag on the minimap to move the 3D view there. The view centres on the spot and keeps its angle and zoom; the selection is left as it was.

The picture is rendered from the scene when a territory opens, at 0.5 px/m (**Editor Settings > Map Authoring > Minimap**), lit at noon unless the time preview is on, so it shows unpublished source edits. The authoring terrain preview renders much darker than the game, for a reason not yet diagnosed, so the dock brightens its copy of the picture; that is compensation, not a fix, and top-down captures are left as rendered. Press **Refresh** after large edits. The overlays follow the scene continuously.

## Open a territory by map

**Territories > Browse…** shows every territory as its published minimap. Click one to open its authored scene. The open territory and territories without an authored source are shown but cannot be picked.

## Low spec view

**Low spec** makes big territories lighter to work in:

- the 3D view renders at half resolution (Godot's own **View > Half Resolution**);
- placed assets, scenery and generated preview meshes more than 200 m from the camera are not drawn (**Editor Settings > Map Authoring > Performance > Far Asset Metres**);
- Godot's frame-time readout is shown, and the cursor readout adds frames per second.

The distance culling is set on the renderer directly, so no node property changes and nothing is saved. Switching it off restores each mesh's own visibility range and the view options as they were. The setting is remembered and reapplied when a territory opens.

## Time of day preview

The **Time** button in the 3D toolbar opens a small panel. Turn on **Preview time of day**, then drag the slider or press **Midnight**, **Dawn**, **Noon** or **Dusk**.

- **Same lighting as the game.** The territory's published manifest (`world.json`) supplies the noon sky, sun, ambient light and fog. `DayNightBinder` then moves them to the chosen hour, which is the game's own day/night curve.
- **Game clock.** A day is 360 game minutes, shown like the in-game clock: noon is 3:00 and midnight is 0:00.
- **Moon.** At night the moon takes over as the only directional light, as in the game. Night deliberately stays readable, because the game floors its ambient light.
- **Editor only.** The sun, moon and environment are internal, ownerless nodes, so they are never saved or baked. The preview follows you when you switch territory scenes.
- **Scenes with their own lighting.** Scenes that save their own Sun or WorldEnvironment, such as the pilot, are left alone, because that is authored lighting. The panel explains why the preview is unavailable there.
- **No manifest.** A territory without a readable manifest gets a plain clear-day fallback.

## Top-down capture

**Map tools > Capture top-down image…** saves a clean, north-up picture of the open territory. Use it for minimap work or as a tracing reference. The dialog sets:

- **Save PNG to:** by default `Pictures/Eloria map captures/<region>-top-down.png`, outside the project.
- **Resolution in px/m:** 1 px/m makes one pixel one server tile. Images are capped at 8192 px per side.
- **Include neighbour references:** off by default.
- **Only the land this territory owns:** on by default. The terrain grid is a rectangle larger than the territory, so this crops the image to the ownership polygon and makes land outside it transparent.

What the capture does:

- **Lighting.** It uses the time-of-day preview if that is on; otherwise noon from the manifest.
- **What is left out.** Fog is left out and ambient light gets the in-game minimap's floor. The ghost, cursor grid and sculpt ring are hidden during the shot.
- **Sidecar.** A `.json` file next to the PNG records the territory-local bounds, metres per pixel, orientation, height range and lighting, so any pixel maps back to authoring metres and server tiles.
- **Helpers stay out.** Marker pins, the walkability tint and path drafts are hidden during the shot.

The image shows the authoring preview as the editor renders it, not the published `world.glb`.

## Tests

The focused editor test builds a disposable 41×41 region fixture under `res://test-artifacts/map-usability/`. It checks:

- that the fast terrain probe matches the exact triangle ray test;
- the tile readout and the placement transforms;
- ghost placement, the hotkeys and keep-placing;
- snapping and undo;
- the cursor grid;
- the batch tools and prefabs;
- the sculpt brush keys, Ctrl inversion and Flatten sampling;
- the time-of-day preview, on both the fallback and Sunmane's real manifest;
- marker templates, placement, facing and the readable-marker overlay;
- the walkability grade rule tile by tile, live water, structures and decks, and Sunmane's real published grid;
- road and river drawing, endpoint snapping, road extension at either end, undo and discard;
- groups (Ctrl+G, selection expansion, double-click to open), Duplicate and Alt+drag copies with fresh ids;
- the selection bar's fields and buttons;
- the play-test walker: the published-grid fold and five routes checked against results from the server's own fold functions and a replica of its A*, legal server steps on the fixture, walking and running pace, refusal of cut-off goals, the nearest-free-tile redirect, and Sunmane's 792 x 792 fold;
- the contract guards: copied default spawns, the Ctrl+D redirect, shared-id detection and fixing (per section, pre-existing duplicates kept), and prefabs leaving markers out;
- ground regions and plateaus (sizes, surfaces, ownership and border refusals, the 127 limit, undo) and heightmap import (Replace and Offset, orientation, border protection, stale layers, untouched base bytes);
- the minimap's framing, pixel mapping, overlays and camera jump;
- the territory picker's thumbnails and open request;
- the library folder and model import, including `.gltf` conversion and skipping;
- the low-spec view and the toolbar toggles;
- top-down framing and ownership clipping;
- that no helper node (ghost, grid, preview lights, walker, copy ghost, focus helper) is ever saved, and that group tags are.

```powershell
& 'C:/Users/User/Desktop/eloria-project/eloria-client/godot-client/Godot_v4.7.2-stable_win64_console.exe' --editor --headless --path . --script res://tests/test_map_authoring_usability_editor.gd
```

The test waits for the editor to finish its first scan before opening the fixture, and restores every Editor Settings value it changes.

`tests/test_terrain_sculpt_editor.gd` now uses an isolated catalog, manifest and authoring spec under `test-artifacts/terrain-sculpt/`, checks that the edited scene is exactly its fixture before any input or save, and stops without saving otherwise.

## Not in this editor yet

The map team's answers (see [map-team-editor-contracts.md](map-team-editor-contracts.md)) set the order and the owners:

- **Polygon lakes, ponds and shorelines** come after an explicit polygon-water contract; plan water will be shown read-only first.
- **Grass and foliage painting** needs a foliage runtime budget first; a scatter tool that places ordinary assets could come sooner.
- **Map annotations** are proposed as an editor-only `<region>.editor-notes.json` beside the scene.
- **Named place labels** on the in-game map need a label schema, client rendering and a naming policy.
- **Lights, particles and sound emitters** exist in manifests today, owned by the map team, but have no scene controls or snapshot section yet.
- **NPC walking paths** need a server patrol feature first.
- **Walkability overrides** come last, and only as areas that remove walkability; forcing ground walkable is not planned.
