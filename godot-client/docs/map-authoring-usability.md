# Map editor usability

The map editor still runs inside Godot, but the placement and viewport tools now work more like a dedicated map editor. Three plugins are involved:

- **Map Assets** (`addons/map_asset_palette`): the asset library, ghost placement, and prefabs.
- **Map Authoring Usability** (`addons/map_authoring_usability`): the cursor readout, the cursor grid, the **Map tools** menu, the time-of-day preview and the top-down capture.
- **Territories** (`addons/map_authoring_workspace`): now also has sculpt brush keys; see [terrain-sculpting.md](terrain-sculpting.md).

Everything in this document works in production region scenes and in the pilot. None of it changes the save, snapshot, or bake contracts. Ghosts and grids are internal, ownerless nodes, so they are never packed into a scene. Every edit goes through Godot's normal undo history, which you can see and jump through in the **History** dock next to FileSystem.

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
| **Time of day preview…** | Opens the time panel (see below). |
| **Capture top-down image…** | Saves a map image of the territory (see below). |

Each item is a single undo step. The items can be given keys under **Editor Settings > Shortcuts > Map Authoring**; they are unbound by default.

## Prefabs

### Save a prefab

1. Select placed assets.
2. Type a name next to **Save selection** in Map Assets, then press it (or use **Map tools > Save selection as prefab**).

The prefab is written to `res://world_authoring/prefabs/<name>.tscn`, and **Folder** shows it in the FileSystem dock.

### Place a prefab

Place a prefab like any other asset: the ghost shows every member, and turn, lift, size and snap apply to the whole group.

- Members follow the terrain. Each member keeps the height above the ground it had when the prefab was saved, so a camp placed on a slope still sits on the ground.
- Each placement creates ordinary, independent assets. They get fresh asset ids and their own copies of local material overrides.
- Placing a prefab is one undo step. The prefab file itself never enters a bake or snapshot.

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
- top-down framing and ownership clipping;
- that no helper node (ghost, grid, preview lights) is ever saved.

```powershell
& 'C:/Users/User/Desktop/eloria-project/eloria-client/godot-client/Godot_v4.7.2-stable_win64_console.exe' --editor --headless --path . --script res://tests/test_map_authoring_usability_editor.gd
```

The test restores every Editor Settings value it changes.

## Not in this editor yet

The partner editor also paints water, grass, ground textures, walkability, named places, sounds and cliff "plateaus". Each of those needs a new source control and a new snapshot/bake contract, which the map team owns. They are proposals, not features. Image heightmap import and map annotations are also not implemented.
