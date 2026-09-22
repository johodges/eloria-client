# Map authoring pilot

This is a small, isolated Godot 4.7.2 example for editing a map with immediate viewport feedback. It does not alter the production startup scene, load the continent pipeline, connect to a multiplayer server, or publish map data.

![Map authoring pilot play preview](images/map-authoring-pilot.png)

The edited-control example below bends `River` east and raises `WestHeight`; both changes exist only in the capture's in-memory scene.

![Bent river and raised terrain handle preview](images/map-authoring-controls.png)

## Open it

From `godot-client`, run:

```powershell
& 'C:/Users/User/Desktop/eloria-project/eloria-client/godot-client/Godot_v4.7.2-stable_win64_console.exe' --editor --path . 'res://src/dev/map_authoring_pilot/map_authoring_pilot.tscn'
```

Or double-click `open-map-authoring-pilot.bat` in `godot-client`.

Godot may import project assets on the first launch. Select the `MapAuthoringPilot` root to edit terrain, water, road, bridge, preview, and export parameters in the Inspector. The root's **Edit road points**, **Edit river points**, and **Edit terrain heights** buttons select the matching saved control and switch the 3D viewport to it. The controls are:

- `AuthoredControls/Road`: a native `Path3D` whose `Curve3D` controls the worn path.
- `AuthoredControls/River`: a native `Path3D` whose `Curve3D` controls the river channel, terrain cut, visible water, and blocked export cells.
- `AuthoredControls/TerrainHeights`: a group of `Marker3D` height handles. Move a handle up or down for a smooth radial height offset, and edit its **Influence Radius** in the Inspector. Move it in X/Z, duplicate it, or delete it to change where local shaping applies.
- `BridgeStart` and `BridgeEnd`: move the bridge anchors.
- `Building`: move or rotate the open-front cabin and its attached entrance.
- `Building/Entrance` and `Spawn`: adjust the attached doorway endpoint and route start.
- `AuthoredScenery`: move the saved shore rocks, grass clumps, wind pine, sign, or cabin lantern with the normal transform tools. These cosmetic nodes stay outside `GeneratedPreview`, so regeneration does not erase their placements.

To edit either path, select its `Path3D` node and work in the 3D viewport. In **Select Points** mode, Ctrl+left-click the curve or empty space to add or split a point, and right-click an existing point to delete it. The dedicated **Add Point** mode also splits when you click the curve and appends when you click empty space; **Delete Point** mode removes a clicked point. Ctrl+Z uses Godot's native undo. **Top View** is recommended because road and river authoring is in X/Z; point Y is intentionally ignored. The river's visible water and blocked-cell mask resolve to the pilot's half-metre export samples. These controls follow the Godot 4.5 stable `Path3D` editor behavior verified in [`path_3d_editor_plugin.cpp`](https://github.com/godotengine/godot/blob/4.5-stable/editor/scene/3d/path_3d_editor_plugin.cpp).

Moving a terrain handle in Y creates a local offset rather than changing the map-wide baseline. **Terrain Base Height** and **Terrain Relief** on `MapAuthoringPilot` remain the global controls. Duplicate or delete handles in the Scene tree, use the normal move tool for Y and X/Z, and press Ctrl+S to save the authored nodes.

## Edit the Last Lantern look

The root's **Visual Style** field points to `src/dev/map_authoring_pilot/style/last_lantern_style.tres`. Expand it in the Inspector and choose a texture from the native **Terrain Texture**, **Road Texture**, **Woodwork Texture**, **Stonework Texture**, and **Roof Texture** dropdowns. **Woodwork Texture** covers the cabin walls, trim, bridge deck, and matching timber props. The viewport updates after the short editor debounce; press Ctrl+S to save the choices with the scene.

Each dropdown offers **Custom**, **Grass**, **Worn earth**, **Timber**, **Stone**, **Thatch**, **Textile**, **Canvas**, **Metal**, **Leather**, **Hide**, **Bone**, **Crystal**, **Cavern**, and **Slate**. These choices reuse the Sunmane PBR texture families already licensed for Eloria. The road always keeps its feathered-edge shader while changing the selected base-colour, normal, and ORM textures.

Before experimenting, use **Save As** on the style resource to create a personal `.tres`, then assign the copy to **Visual Style**. Keep one style assigned on the pilot root: it feeds both generated map meshes and saved `AuthoredScenery` props. Editing the checked-in shared resource changes every scene that uses it.

Use **Custom** in a slot when you want to assign a material directly. Enable **Show Advanced Materials** to expose all six material resources without changing their selected presets. The advanced fields control texture tint, normal strength, roughness, ORM response, triplanar **UV1 > Scale**, and the road and water shader parameters. Advanced edits remain intact across refresh and save/reopen. Switching away from a texture and back during the editing session recovers its current material, so Inspector undo also restores Custom materials and advanced tweaks.

The terrain and road start at `GROUND_UV_SCALE = 0.24`, and the bridge deck starts at `TIMBER_UV_SCALE = 0.5`, near the top of `map_authoring_pilot.gd`. Change those constants for code-wide texture density. Triplanar wall, woodwork, stonework, and roof materials use the style resource's **UV1 Scale**. Parameter edits update every mesh sharing that material immediately.

Lighting is saved in the scene rather than generated. Select `Sun` to edit direction, colour, energy, and shadows; select `Environment` and expand its resource to edit the cool ambient/background values. The warm pool is `AuthoredScenery/CabinLantern/WarmLight`, where the Inspector exposes colour, energy, range, and shadows. Select the lantern or another prop's parent node to move the complete authored instance.

The bridge markers' Y values are explicit offsets above their sampled banks. Road and river curve Y values are intentionally plan-only in this pilot; the road preview follows the exported floor, and river water stays at the root's **Water Level**. Raising a curve point therefore cannot create an unexported second floor or locally raise the water.

Moving the river does not move the bridge. Reposition `BridgeStart` and `BridgeEnd` manually when the crossing changes. Arbitrary river or terrain-height edits can also invalidate the walking route, so use **Start walk** or the walkability overlay after reshaping the crossing. With fewer than two river points, the pilot safely shows no river water or channel cut and exports no river-blocked cells. With fewer than two road points, it shows no road surface. Restore or add points to resume either preview.

Changes refresh after a short debounce. For an explicit rebuild, set `Refresh Scope` on the root and press **Refresh selected feature**. Preview geometry is generated below `GeneratedPreview`; it is deliberately not scene-owned and is never a source of saved edits. Edit `AuthoredControls/Road`, `AuthoredControls/River`, and `AuthoredControls/TerrainHeights`, not their generated meshes. Undo and redo the normal Path3D, Marker3D, transform, and Inspector edits, then save the scene as usual. Reopening it regenerates the preview from those saved authored controls.

`AuthoredScenery` remains independent of terrain shaping. After moving the river or terrain handles, manually reposition or reground cosmetic rocks, grass, trees, signs, and the lantern if their saved placements no longer fit the surface.

For code-first work, edit `src/dev/map_authoring_pilot/map_authoring_pilot.gd`: `_terrain_height` combines global terrain and `TerrainHeights`, `_build_road`, `_build_water`, and `_build_bridge` define preview meshes, and `_encoded_floor` chooses the one exported floor. Each handle uses `src/dev/map_authoring_pilot/terrain_height_handle.gd`, whose public authoring property is `influence_radius`. Save the script and use **Refresh selected feature**; if Godot has not reloaded a tool-script change, close and reopen the scene. Keep the `MapAuthoringPilot` and `AuthoredControls` transforms at identity and move the named controls below them, so the saved control coordinates continue to match the export frame.

## Play and export

Press F6 with the pilot scene open. **Start walk** (or Enter) runs the yellow local walker from the spawn to the entrance. **Reset** (or R) returns it to the spawn. **Toggle walkability** (or V) shows or hides the conspicuous overlay: green is reachable from the spawn; red is blocked, too steep, or disconnected from it. The overlay starts hidden so the terrain, water, road, bridge, and doorway remain easy to inspect.

The walker and overlay use the same 48 × 48 one-metre grid. Each tile is conservatively folded from the same 96 × 96 half-metre height grid written by export: any blocked half-metre sample blocks the whole server tile; otherwise the greatest encoded height wins. A legal step changes by at most two 0.2 m height units.

Press **Export EWCG + JSON** on the scene root. The default output is `user://map_authoring_pilot/export`, shown in the runtime status and Godot output. It contains:

- `collision.bin`: EWCG-v2, 96 × 96 row-major bytes at 0.5 m per cell.
- `world.json`: the coordinate, height encoding, server fold, and validation probes.

The sample contains rolling terrain, a curve-authored water channel, local terrain-height handles, an editable road, a gently arched bridge, and a movable building entrance. The local walker proves only this offline sample's grid and height-step rules. It is not proof of multiplayer movement, production continent composition, streamed-region handoff, or the full server map conversion.

The saved rocks, grass, tree, sign, and lantern are decorative in this pilot. They intentionally add no collision and are kept clear of the validated route. If a production prop should block movement, author that change in the collision/export contract and validate it separately rather than assuming the visible mesh is solid.

To check an export through the real server movement classes without starting a server, run:

```powershell
python tools/map_authoring_pilot_adapter.py src/dev/map_authoring_pilot/example_export/world.json --server-root C:\path\to\eloria-server
```

For the default Inspector export on Windows, the manifest is normally under `$env:APPDATA\Godot\app_userdata\Eloria\map_authoring_pilot\export\world.json`. The adapter reads only the local `world.json` and `collision.bin`, imports the chosen server checkout's actual `CollisionMap` and `World.find_path`, starts no server, changes no production map or configuration, and needs no network.

## Focused validation

```powershell
& 'C:/Users/User/Desktop/eloria-project/eloria-client/godot-client/Godot_v4.7.2-stable_win64_console.exe' --headless --path . --script res://tests/test_map_authoring_pilot.gd
```

The smoke test checks that curve, scenery, visual-style, and material edits survive regeneration and save/reopen, generated preview nodes remain nonpersistent, the checked export fixture remains byte/JSON equivalent, the conservative server grid has the expected shape, and every step from spawn across the bridge to the entrance is legal on that same grid.

The texture-preset test checks every named choice, isolated material instances, road-edge shader preservation, generated mesh and scenery assignments, the compact Inspector property list, and Custom or advanced edits across refresh and save/reopen:

```powershell
& 'C:/Users/User/Desktop/eloria-project/eloria-client/godot-client/Godot_v4.7.2-stable_win64_console.exe' --headless --path . --script res://tests/test_map_authoring_pilot_texture_presets.gd
```

The focused visual-control test additionally edits road and river point counts, bends the river and verifies the visible water and exported collision move with it, changes terrain-handle height/radius/XZ and checks generated terrain plus encoded height cells, exercises degenerate paths, and saves/reopens the authored controls:

```powershell
& 'C:/Users/User/Desktop/eloria-project/eloria-client/godot-client/Godot_v4.7.2-stable_win64_console.exe' --headless --path . --script res://tests/test_map_authoring_pilot_visual_controls.gd
```

The style textures reuse the Sunmane Steppe PBR source families already licensed for Eloria. Preserve the original CC-BY-4.0 attribution recorded in `src/dev/map_authoring_pilot/style/ATTRIBUTION.md` when copying or redistributing them. This pilot does not import the Last Lantern tutorial scene, quest, or asset-building pipeline.
