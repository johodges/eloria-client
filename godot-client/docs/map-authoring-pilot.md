# Map authoring pilot

This is a small, isolated Godot 4.7.2 example for editing a map with immediate viewport feedback. It does not alter the production startup scene, load the continent pipeline, connect to a multiplayer server, or publish map data.

![Map authoring pilot play preview](images/map-authoring-pilot.png)

## Open it

From `godot-client`, run:

```powershell
& 'C:/Users/User/Desktop/eloria-project/eloria-client/godot-client/Godot_v4.7.2-stable_win64_console.exe' --editor --path . 'res://src/dev/map_authoring_pilot/map_authoring_pilot.tscn'
```

Or double-click `open-map-authoring-pilot.bat` in `godot-client`.

Godot may import project assets on the first launch. Select the `MapAuthoringPilot` root to edit terrain, water, road, bridge, preview, and export parameters in the Inspector. Use the normal 3D tools to edit these saved controls:

- `AuthoredControls/Road`: edit the `Curve3D` points in the viewport.
- `BridgeStart` and `BridgeEnd`: move the bridge anchors.
- `Building`: move or rotate the open-front cabin and its attached entrance.
- `Building/Entrance` and `Spawn`: adjust the attached doorway endpoint and route start.
- `AuthoredScenery`: move the saved shore rocks, grass clumps, wind pine, sign, or cabin lantern with the normal transform tools. These cosmetic nodes stay outside `GeneratedPreview`, so regeneration does not erase their placements.

## Edit the Last Lantern look

The root's **Visual Style** field points to `src/dev/map_authoring_pilot/style/last_lantern_style.tres`. To make a variant, open that resource from the Inspector and use **Save As** to create a personal `.tres`, then assign the copy to **Visual Style**. Keep one style assigned on the pilot root: it feeds both generated map meshes and saved `AuthoredScenery` props. Editing the checked-in shared resource changes every scene that uses it.

Expand these fields on the personal style in the Inspector:

- **Terrain Material** controls the textured grass tint, normal strength, roughness, and ORM response.
- **Worn Path Material** is a `ShaderMaterial`; edit `worn_tint`, `texture_scale`, `roughness_multiplier`, `normal_strength`, and `edge_feather` under **Shader Parameters**.
- **Timber**, **Stone**, and **Slate Material** control the bridge, cabin, roof, and matching authored props. Their triplanar density is under **UV1 > Scale**.
- **Water Material** exposes `deep_color`, `shallow_color`, `foam_color`, and `river_half_width` under **Shader Parameters**.

The terrain and road start at `GROUND_UV_SCALE = 0.24`, and the bridge deck starts at `TIMBER_UV_SCALE = 0.5`, near the top of `map_authoring_pilot.gd`. Change those constants for code-wide texture density. Triplanar timber, stone, and slate use the style resource's **UV1 Scale**, so they remain editable without changing the generator. Parameter edits update every mesh sharing that material immediately. Replacing a nested material reference is detected by the editor debounce and refreshes the generated meshes and authored scenery.

Lighting is saved in the scene rather than generated. Select `Sun` to edit direction, colour, energy, and shadows; select `Environment` and expand its resource to edit the cool ambient/background values. The warm pool is `AuthoredScenery/CabinLantern/WarmLight`, where the Inspector exposes colour, energy, range, and shadows. Select the lantern or another prop's parent node to move the complete authored instance.

The bridge markers' Y values are explicit offsets above their sampled banks. Road curve Y is intentionally plan-only in this pilot; the road preview follows the same chosen floor height that is exported, so raising a visual curve cannot create an unexported second floor.

Changes refresh after a short debounce. For an explicit rebuild, set `Refresh Scope` on the root and press **Refresh selected feature**. Preview geometry is generated below `GeneratedPreview`; it is deliberately not scene-owned and is never a source of saved edits. Undo and redo the normal Path3D, Marker3D, transform, and Inspector edits, then save the scene as usual. Reopening it regenerates the preview from those saved authored controls.

For code-first work, edit `src/dev/map_authoring_pilot/map_authoring_pilot.gd`: `_terrain_height` defines the sampled terrain, `_build_road` and `_build_bridge` define their preview meshes, and `_encoded_floor` chooses the one exported floor. Save the script and use **Refresh selected feature**; if Godot has not reloaded a tool-script change, close and reopen the scene. Keep the `MapAuthoringPilot` and `AuthoredControls` transforms at identity and move the named controls below them, so the saved control coordinates continue to match the export frame.

## Play and export

Press F6 with the pilot scene open. **Start walk** (or Enter) runs the yellow local walker from the spawn to the entrance. **Reset** (or R) returns it to the spawn. **Toggle walkability** (or V) shows or hides the conspicuous overlay: green is reachable from the spawn; red is blocked, too steep, or disconnected from it. The overlay starts hidden so the terrain, water, road, bridge, and doorway remain easy to inspect.

The walker and overlay use the same 48 × 48 one-metre grid. Each tile is conservatively folded from the same 96 × 96 half-metre height grid written by export: any blocked half-metre sample blocks the whole server tile; otherwise the greatest encoded height wins. A legal step changes by at most two 0.2 m height units.

Press **Export EWCG + JSON** on the scene root. The default output is `user://map_authoring_pilot/export`, shown in the runtime status and Godot output. It contains:

- `collision.bin`: EWCG-v2, 96 × 96 row-major bytes at 0.5 m per cell.
- `world.json`: the coordinate, height encoding, server fold, and validation probes.

The sample contains rolling terrain, a water channel, an editable road, a gently arched bridge, and a movable building entrance. The local walker proves only this offline sample's grid and height-step rules. It is not proof of multiplayer movement, production continent composition, streamed-region handoff, or the full server map conversion.

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

The style textures reuse the Sunmane Steppe ground, timber, and stone source set. Preserve the original Eloria CC-BY-4.0 attribution recorded in `src/dev/map_authoring_pilot/style/ATTRIBUTION.md` when copying or redistributing them. This pilot deliberately reuses only that modest material set and does not import the Last Lantern tutorial scene, quest, or asset-building pipeline.
