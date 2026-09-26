extends SceneTree
## Editor-mode checks for the map authoring usability layer on a tiny disposable
## region fixture: the fast terrain probe, the cursor readout and grid, ghost
## placement with its hotkeys and keep-placing, batch selection tools, prefabs,
## undo/redo, and that no helper node is ever saved.
##
## Godot_v4.7.2-stable_win64_console.exe --editor --headless --path . \
##     --script res://tests/test_map_authoring_usability_editor.gd

const REGION := preload("res://src/dev/map_authoring_region/region_control.gd")
const TERRAIN := preload("res://src/dev/map_authoring_region/terrain_control.gd")
const OVERRIDE := preload("res://src/dev/map_authoring_region/asset_surface_override.gd")
const Catalog := preload("res://addons/map_asset_palette/asset_catalog.gd")
const Placement := preload("res://addons/map_asset_palette/placement.gd")
const Prefabs := preload("res://addons/map_asset_palette/prefab_library.gd")
const Thumbnails := preload("res://addons/map_asset_palette/thumbnail_renderer.gd")
const Probe := preload("res://addons/map_authoring_usability/terrain_probe.gd")
const Settings := preload("res://addons/map_authoring_usability/usability_settings.gd")
const Tools := preload("res://addons/map_authoring_usability/selection_tools.gd")
const UsabilityPlugin := preload("res://addons/map_authoring_usability/plugin.gd")
const TimeOfDay := preload("res://addons/map_authoring_usability/time_of_day_preview.gd")
const TopDown := preload("res://addons/map_authoring_usability/top_down_capture.gd")
const Markers := preload("res://addons/map_asset_palette/marker_library.gd")
const Walkability := preload("res://addons/map_authoring_usability/walkability_overlay.gd")
const MARKER := preload("res://src/dev/map_authoring_region/gameplay_marker.gd")
const WATER := preload("res://src/dev/map_authoring_region/water_region_control.gd")
const DIR := "res://test-artifacts/map-usability"
const HEIGHT_PATH := DIR + "/fixture-heights.f32le"
const SCENE_PATH := DIR + "/fixture.tscn"
const RELOAD_PATH := DIR + "/fixture-saved.tscn"
const PREFAB_DIR := DIR + "/prefabs"
const GRID := Vector2i(41, 41)
const SETTING_KEYS := ["placement/keep_placing", "placement/snap_to_grid", "grid/step",
	"grid/cursor_grid", "placement/random_rotation", "placement/size_variation",
	"placement/align_to_surface", "viewport/show_cursor_readout", "time_of_day/minute",
	"markers/show", "markers/labels"]

var failures := 0
var _saved_settings := {}
var _editor: Object
var _undo: EditorUndoRedoManager


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	if not Engine.is_editor_hint():
		push_error("map authoring usability test requires --editor")
		quit(1)
		return
	_editor = Engine.get_singleton("EditorInterface")
	var base := _editor.call("get_base_control") as Control
	var palette: Object = null
	var usability: Object = null
	for _attempt in 300:
		if base != null and base.has_meta(&"map_asset_palette_plugin") and \
				base.has_meta(&"map_authoring_usability_plugin"):
			palette = base.get_meta(&"map_asset_palette_plugin")
			usability = base.get_meta(&"map_authoring_usability_plugin")
			break
		await create_timer(0.1).timeout
	_expect(palette != null and usability != null and
		bool(_editor.call("is_plugin_enabled", "map_authoring_usability")),
		"project enables the Map Assets and Map Authoring Usability plugins")
	if palette == null or usability == null:
		_finish()
		return
	var settings := _editor.call("get_editor_settings") as EditorSettings
	_expect(settings.has_setting("map_authoring/grid/step") and
		settings.has_shortcut("map_authoring/rotate_left") and
		settings.has_shortcut("map_authoring/drop_to_ground"),
		"preferences and rebindable shortcuts are registered in Editor Settings")
	for key: String in SETTING_KEYS:
		_saved_settings[key] = Settings.value(key)
	Settings.set_value("placement/keep_placing", true)
	Settings.set_value("placement/snap_to_grid", false)
	Settings.set_value("grid/step", 1.0)
	Settings.set_value("grid/cursor_grid", Settings.CursorGrid.ALWAYS)
	Settings.set_value("placement/random_rotation", false)
	Settings.set_value("placement/size_variation", 0.0)
	Settings.set_value("placement/align_to_surface", false)
	Settings.set_value("viewport/show_cursor_readout", true)
	Prefabs.directory = PREFAB_DIR
	_remove_tree(PREFAB_DIR)
	_undo = _editor.call("get_editor_undo_redo") as EditorUndoRedoManager

	var root := await _open_fixture()
	if root == null:
		_finish()
		return
	var entry := _entry(Catalog.entries(), "mirror_reed")
	_expect(not entry.is_empty(), "the native catalog still offers mirror_reed")
	var thumbnail_mesh := Thumbnails.merged_mesh(entry)
	_expect(thumbnail_mesh != null and thumbnail_mesh.get_surface_count() > 0 and
		thumbnail_mesh.surface_get_material(0) != null,
		"library thumbnails merge an asset's visible meshes with their materials")
	_test_probe(root)
	_test_describe_point(root)
	_test_adjusted_transform(root, entry)
	var camera := Camera3D.new()
	root.add_child(camera)
	_aim(camera, root, Vector2(20.0, 20.0))
	var placed := _test_ghost_placement(palette, root, entry, camera)
	_test_cursor_readout_and_grid(usability, root, camera)
	if placed.size() == 2:
		_test_selection_tools(usability, root, placed)
		_test_prefab(palette, root, placed, camera)
	var sculpt: Object = (_editor.call("get_base_control") as Control).get_meta(
		&"map_authoring_sculpt_plugin") \
		if (_editor.call("get_base_control") as Control).has_meta(&"map_authoring_sculpt_plugin") \
		else null
	_expect(sculpt != null, "the Territories plugin is active for the sculpt keys")
	if sculpt != null:
		_test_sculpt_keys(sculpt, usability, root, camera)
	_test_time_of_day(usability, root)
	await _test_top_down(usability, root)
	_test_marker_palette(palette, usability, root, camera)
	_test_walkability(usability, root)
	_test_path_drawing(palette, usability, root, camera, entry)
	usability.call("set_time_preview", true, 90.0)
	usability.call("set_walkability_mode", Walkability.Mode.LIVE)
	usability.call("start_path_drawing", "road")
	_aim(camera, root, Vector2(12.0, 30.0))
	usability.call("_forward_3d_gui_input", camera,
		_click(camera.get_viewport().get_visible_rect().size * 0.5))
	await _test_save_excludes_helpers(palette, usability, root, entry, camera)
	usability.call("cancel_path_drawing")
	usability.call("set_walkability_mode", Walkability.Mode.OFF)
	usability.call("set_time_preview", false)
	if sculpt != null:
		sculpt.get("_sculpt").call("unbind")
	palette.call("_cancel_placement")
	camera.queue_free()
	_finish()


func _test_sculpt_keys(sculpt: Object, usability: Object, root: Node3D,
		camera: Camera3D) -> void:
	# The fixture is not in the territory catalog, so bind the brush the way
	# test_terrain_sculpt_editor.gd does, then drive the real plugin's input.
	var tool: Object = sculpt.get("_sculpt")
	var dock: Object = sculpt.get("_dock")
	var terrain := root.get_node("Terrain")
	var entry := {"ownership_polygon": PackedVector2Array([Vector2(0, 0), Vector2(40, 0),
		Vector2(40, 40), Vector2(0, 40)]), "translation": Vector3.ZERO,
		"ownership_sha256": String(root.get("ownership_polygon_sha256")), "editable": true}
	var bound: bool = tool.call("bind", root, terrain, entry, _undo)
	dock.call("set_sculpt_available", true)
	dock.call("set_sculpt_active", true)
	tool.call("set_enabled", true)
	_expect(bound and bool(tool.call("is_enabled")), "the sculpt brush binds to the fixture")
	if not bound:
		return
	dock.call("set_sculpt_mode", 0)
	var start: Dictionary = dock.call("sculpt_settings")
	var results := [
		sculpt.call("_forward_3d_gui_input", camera, _key(KEY_2)),
		sculpt.call("_forward_3d_gui_input", camera, _key(KEY_BRACKETRIGHT)),
		sculpt.call("_forward_3d_gui_input", camera, _key(KEY_BRACKETRIGHT, true)),
		sculpt.call("_forward_3d_gui_input", camera, _wheel(true)),
	]
	var changed: Dictionary = dock.call("sculpt_settings")
	var ring: StandardMaterial3D = tool.get("_ring_material")
	_expect(results.all(func(value: int) -> bool: return value == EditorPlugin.AFTER_GUI_INPUT_STOP) and
		int(changed.mode) == 1 and
		is_equal_approx(float(changed.radius), snappedf(snappedf(float(start.radius) * 1.25,
			0.5) * 1.25, 0.5)) and float(changed.strength) > float(start.strength) and
		ring.albedo_color.is_equal_approx(Color(1.0, 0.55, 0.25)),
		"2 picks Lower, ] and Shift+wheel grow the brush, Shift+] strengthens it, ring turns orange")
	var hints: PackedStringArray = sculpt.call("overlay_lines")
	_expect(hints.size() == 2 and "Sculpt Lower" in hints[0] and "radius" in hints[0],
		"sculpt hint lines describe the active brush")
	dock.call("set_sculpt_mode", 0)
	var centre := camera.get_viewport().get_visible_rect().size * 0.5
	var hit: Vector3 = Probe.ray_hit(root, camera.project_ray_origin(centre),
		camera.project_ray_normal(centre)) as Vector3
	var before := Probe.height_at(root, hit)
	var press := _click(centre)
	press.ctrl_pressed = true
	sculpt.call("_forward_3d_gui_input", camera, press)
	var drag := InputEventMouseMotion.new()
	drag.position = centre
	drag.button_mask = MOUSE_BUTTON_MASK_LEFT
	drag.ctrl_pressed = true
	sculpt.call("_forward_3d_gui_input", camera, drag)
	var release := _click(centre)
	release.pressed = false
	sculpt.call("_forward_3d_gui_input", camera, release)
	var after := Probe.height_at(root, hit)
	_expect(after < before - 0.05,
		"Ctrl+drag with Raise lowers the ground (%.3f -> %.3f m)" % [before, after])
	var history := _undo.get_history_undo_redo(_undo.get_object_history_id(root))
	history.undo()
	_expect(absf(Probe.height_at(root, hit) - before) < 0.0001,
		"the inverted stroke is one ordinary sculpt undo step")
	dock.call("set_sculpt_mode", 3)
	var pick := _click(centre)
	pick.ctrl_pressed = true
	sculpt.call("_forward_3d_gui_input", camera, pick)
	var target := float((dock.call("sculpt_settings") as Dictionary).flatten_target)
	_expect(absf(target - before) < 0.06,
		"Ctrl+click with Flatten samples the height under the brush (%.2f m)" % target)
	usability.call("_refresh_hover")
	dock.call("set_sculpt_mode", 0)
	tool.call("set_enabled", false)
	dock.call("set_sculpt_active", false)


func _test_time_of_day(usability: Object, root: Node3D) -> void:
	_expect(TimeOfDay.describe(180.0) == "3:00 noon" and TimeOfDay.describe(0.0) == "0:00 midnight" and
		TimeOfDay.describe(90.0) == "1:30 dawn",
		"time labels use the game clock (360-minute day, noon at 3:00)")
	var on: bool = usability.call("set_time_preview", true, 180.0)
	var state := usability.call("time_preview_state") as Dictionary
	var holder := state.nodes as Node3D
	var sun := holder.get_node("Sun") as DirectionalLight3D if holder != null else null
	var noon_energy := sun.light_energy if sun != null else 0.0
	_expect(on and holder != null and holder.owner == null and
		not root.get_children().has(holder) and root.get_children(true).has(holder) and
		String(state.manifest).is_empty(),
		"the preview adds internal, unsaved sun/moon/environment (fallback daylight here)")
	usability.call("set_time_preview", true, 0.0)
	var moon := holder.get_node("Moon") as DirectionalLight3D if holder != null else null
	_expect(sun != null and sun.light_energy < noon_energy and moon != null and moon.visible,
		"midnight dims the sun and raises the moon, as DayNightBinder does in game")
	# A real territory manifest: Sunmane's published world.json is the noon reference.
	var region := String(root.get("region_id"))
	root.set("region_id", "sunmane_steppe")
	usability.call("set_time_preview", false)
	usability.call("set_time_preview", true, 180.0)
	state = usability.call("time_preview_state") as Dictionary
	var real_sun := (state.nodes as Node3D).get_node("Sun") as DirectionalLight3D \
		if state.nodes != null else null
	var manifest := WorldManifest.load_file(TimeOfDay.manifest_path_for("sunmane_steppe"))
	var declared := float(((manifest.data.environment as Dictionary).sun as Dictionary).energy)
	_expect(String(state.manifest).ends_with("sunmane_steppe/world.json") and real_sun != null and
		is_equal_approx(real_sun.light_energy, declared),
		"a catalogued territory previews its own manifest sun (noon energy %.2f)" % declared)
	usability.call("set_time_preview", false)
	root.set("region_id", region)
	_expect(not bool((usability.call("time_preview_state") as Dictionary).active) and
		root.get_children(true).all(func(node: Node) -> bool:
			return not String(node.name).begins_with("__MapAuthoringTimeOfDay")),
		"switching the preview off removes every preview node")
	var authored := Node3D.new()
	var saved_sun := DirectionalLight3D.new()
	authored.add_child(saved_sun)
	saved_sun.owner = authored
	var refused := TimeOfDay.new()
	_expect(not refused.enable(authored, 180.0) and "Sun" in refused.last_message,
		"scenes that save their own Sun (the pilot) keep their authored lighting")
	authored.free()


func _test_top_down(usability: Object, root: Node3D) -> void:
	var framing := TopDown.plan(root, 2.0)
	var camera_transform: Transform3D = framing.camera_transform
	_expect(framing.size == Vector2i(80, 80) and
		(framing.rect as Rect2).is_equal_approx(Rect2(0, 0, 40, 40)) and
		TopDown.pixel_for(framing, Vector3(10.0, 0.0, 30.0)).is_equal_approx(Vector2(20, 60)) and
		(-camera_transform.basis.z).is_equal_approx(Vector3.DOWN) and
		camera_transform.basis.y.is_equal_approx(Vector3.FORWARD) and
		camera_transform.basis.x.is_equal_approx(Vector3.RIGHT),
		"top-down framing covers the terrain grid north-up, east right, 2 px per metre")
	var polygon := PackedVector2Array([Vector2(5, 5), Vector2(30, 5), Vector2(30, 35),
		Vector2(5, 20)])
	var clipped := TopDown.plan(root, 2.0, polygon)
	var mask := TopDown.ownership_mask(clipped, polygon)
	_expect((clipped.rect as Rect2).is_equal_approx(Rect2(5, 5, 25, 30)) and
		clipped.size == Vector2i(50, 60) and
		is_equal_approx(mask.get_pixelv(Vector2i(TopDown.pixel_for(clipped,
			Vector3(20, 0, 15)))).a, 1.0) and
		is_zero_approx(mask.get_pixelv(Vector2i(TopDown.pixel_for(clipped,
			Vector3(7, 0, 32)))).a),
		"ownership clipping frames the polygon and masks out land the territory does not own")
	var huge := TopDown.plan(root, 1000.0)
	_expect((huge.size as Vector2i).x <= TopDown.MAX_SIDE and
		absf(float(huge.pixels_per_metre) - float(TopDown.MAX_SIDE) / 40.0) < 0.001,
		"very high resolutions are clamped to %d px per side" % TopDown.MAX_SIDE)
	var result: Dictionary = await usability.call("capture_top_down",
		DIR + "/capture.png", 2.0, false)
	_expect(result.has("error") and not bool((usability.call("time_preview_state") as Dictionary).active) and
		root.get_children(true).all(func(node: Node) -> bool:
			return not String(node.name).begins_with("__MapAuthoringTopDownCapture")),
		"a capture without a renderer fails cleanly and leaves no lights or viewport behind")


func _open_fixture() -> Node3D:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(DIR))
	var file := FileAccess.open(ProjectSettings.globalize_path(HEIGHT_PATH), FileAccess.WRITE)
	file.big_endian = false
	for z in GRID.y:
		for x in GRID.x:
			file.store_float(5.0 + 2.0 * sin(float(x) * 0.35) + 1.5 * cos(float(z) * 0.27) +
				0.002 * float(x * z))
	file.close()
	var fixture: Variant = REGION.new()
	fixture.name = "UsabilityFixture"
	fixture.region_id = "usability_fixture"
	fixture.metres_per_tile = 1.0
	fixture.server_origin = Vector2i(100, 200)
	fixture.server_cells = GRID
	var polygon_rows := [[0.0, 0.0], [40.0, 0.0], [40.0, 40.0], [0.0, 40.0]]
	fixture.ownership_polygon_sha256 = JSON.stringify(polygon_rows).sha256_text()
	fixture.authority_gameplay = false
	var terrain: Variant = TERRAIN.new()
	terrain.name = "Terrain"
	terrain.origin = Vector2.ZERO
	terrain.grid_size = GRID
	terrain.cell_metres = 1.0
	terrain.base_heights_path = HEIGHT_PATH
	terrain.preview_enabled = true
	terrain.base_surface = MapAuthoringSurface.from_preset(MapAuthoringTexturePresets.GRASS)
	fixture.add_child(terrain)
	terrain.owner = fixture
	for container in ["Roads", "Rivers", "Bridges", "AuthoredAssets", "Gameplay",
			"GeneratedPreview"]:
		var node := Node3D.new()
		node.name = container
		fixture.add_child(node)
		node.owner = fixture
	var harvestables := Node3D.new()
	harvestables.name = "Harvestables"
	fixture.get_node("Gameplay").add_child(harvestables)
	harvestables.owner = fixture
	var crystal: Node3D = MARKER.new()
	crystal.name = "crystal-01"
	crystal.set("record_id", "crystal-01")
	crystal.set("kind", "harvestable")
	crystal.set("label", "Crystal")
	crystal.set("extras", {"extent": [4, 4], "harvestHook": "harvest.test", "kind": "mineral",
		"propPosition": [1, 2, 3]})
	crystal.position = Vector3(6.0, 6.0, 34.0)
	harvestables.add_child(crystal)
	crystal.owner = fixture
	var lakes := Node3D.new()
	lakes.name = "WaterRegions"
	fixture.add_child(lakes)
	lakes.owner = fixture
	var lake: Node3D = WATER.new()
	lake.name = "test-lake"
	lake.set("water_id", "test-lake")
	lake.set("radii", Vector2(4.0, 4.0))
	lakes.add_child(lake)
	lake.owner = fixture
	var packed := PackedScene.new()
	var saved: bool = packed.pack(fixture) == OK and ResourceSaver.save(packed, SCENE_PATH) == OK
	fixture.free()
	_expect(saved, "disposable region fixture saves")
	_editor.call("open_scene_from_path", SCENE_PATH)
	await process_frame
	await process_frame
	var root := _editor.call("get_edited_scene_root") as Node3D
	_expect(root != null and root.get_script() == REGION and root.has_node("Terrain"),
		"editor opens the region fixture as the edited scene")
	return root if root != null and root.get_script() == REGION else null


func _test_probe(root: Node3D) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var mismatches := 0
	var max_error := 0.0
	var probe_usec := 0
	var reference_usec := 0
	for _index in 40:
		var origin := Vector3(rng.randf_range(-10.0, 50.0), rng.randf_range(15.0, 60.0),
			rng.randf_range(-10.0, 50.0))
		var target := Vector3(rng.randf_range(0.0, 40.0), 0.0, rng.randf_range(0.0, 40.0))
		var direction := (target - origin).normalized()
		var started := Time.get_ticks_usec()
		var fast: Variant = Probe.ray_hit(root, origin, direction, 2048.0)
		probe_usec += Time.get_ticks_usec() - started
		started = Time.get_ticks_usec()
		var exact: Variant = root.call("authoring_ground_intersection", origin, direction, 2048.0)
		reference_usec += Time.get_ticks_usec() - started
		if (fast == null) != (exact == null):
			mismatches += 1
		elif fast != null:
			max_error = maxf(max_error, (fast as Vector3).distance_to(exact as Vector3))
	_expect(mismatches == 0 and max_error < 0.001,
		"fast probe agrees with the region's exact triangle test (max error %.6f m)" % max_error)
	print("  probe %d µs vs whole-grid test %d µs for 40 oblique rays" % [probe_usec,
		reference_usec])
	_expect(probe_usec < reference_usec,
		"fast probe walks only the cells a ray crosses (%d µs vs %d µs)" % [probe_usec,
			reference_usec])
	var height_error := 0.0
	for _index in 20:
		var point := Vector3(rng.randf_range(0.5, 39.5), 0.0, rng.randf_range(0.5, 39.5))
		var vertical: Variant = root.call("authoring_ground_intersection",
			point + Vector3.UP * 100.0, Vector3.DOWN, 200.0)
		height_error = maxf(height_error, absf(Probe.height_at(root, point) -
			(vertical as Vector3).y))
	_expect(height_error < 0.0001 and is_nan(Probe.height_at(root, Vector3(-5, 0, -5))) and
		Probe.ray_hit(root, Vector3(20, 30, 20), Vector3.UP) == null,
		"height lookups match vertical rays and stay empty off the terrain")


func _test_describe_point(root: Node3D) -> void:
	var info := Probe.describe_point(root, root.global_transform * Vector3(3.4, 7.0, 5.6))
	_expect(bool(info.has_tile) and info.tile == Vector2i(103, 194) and
		(info.local as Vector3).is_equal_approx(Vector3(3.4, 7.0, 5.6)),
		"cursor readout uses the snapshot tile conversion (floor(x+ox), floor(oy-z))")


func _test_adjusted_transform(root: Node3D, entry: Dictionary) -> void:
	var created := Placement.instantiate_entry(entry)
	var wrapper := root.call("prepare_palette_asset", entry, created.node) as Node3D
	var ground := Probe.ray_hit(root, Vector3(20.0, 60.0, 20.0), Vector3.DOWN) as Vector3
	var legacy := Placement.ground_transform(wrapper, entry, ground)
	_expect(Placement.adjusted_ground_transform(wrapper, entry, ground).is_equal_approx(legacy),
		"adjusted placement with no adjustments equals the existing ground transform")
	var turned := Placement.adjusted_ground_transform(wrapper, entry, ground, 90.0)
	var lifted := Placement.adjusted_ground_transform(wrapper, entry, ground, 0.0, 0.5)
	var grown := Placement.adjusted_ground_transform(wrapper, entry, ground, 0.0, 0.0, 1.5)
	var normal := Vector3(0.3, 1.0, -0.2).normalized()
	var tilted := Placement.adjusted_ground_transform(wrapper, entry, ground, 0.0, 0.0, 1.0,
		normal)
	_expect(turned.basis.x.is_equal_approx(Basis(Vector3.UP, PI * 0.5) * legacy.basis.x) and
		absf(_bottom(wrapper, turned) - ground.y) < 0.001,
		"a turn rotates about world up and keeps the visible base on the ground")
	_expect(absf(_bottom(wrapper, lifted) - ground.y - 0.5) < 0.001,
		"lift raises the grounded asset by exactly that many metres")
	_expect(absf(_height(wrapper, grown) - 1.5 * _height(wrapper, legacy)) < 0.001 and
		absf(_bottom(wrapper, grown) - ground.y) < 0.001,
		"size scales on top of the catalog height and stays grounded")
	_expect(tilted.basis.y.normalized().is_equal_approx(normal),
		"align to slope points the asset's up along the surface normal")
	wrapper.free()


func _test_ghost_placement(palette: Object, root: Node3D, entry: Dictionary,
		camera: Camera3D) -> Array[Node3D]:
	var placed: Array[Node3D] = []
	var centre := camera.get_viewport().get_visible_rect().size * 0.5
	palette.call("_arm_placement", entry)
	var motion := InputEventMouseMotion.new()
	motion.position = centre
	var motion_result: int = palette.call("_forward_3d_gui_input", camera, motion)
	palette.call("_refresh_hover")
	var ghost := (palette.call("placement_state") as Dictionary).ghost as Node3D
	# Compatibility ignores GeometryInstance3D.transparency, so the ghost must carry
	# its own alpha-blended surface materials.
	var see_through := ghost != null and ghost.find_children("*", "MeshInstance3D", true,
		false).any(func(node: Node) -> bool:
			var material := (node as MeshInstance3D).get_surface_override_material(0)
			return material is BaseMaterial3D and \
				(material as BaseMaterial3D).transparency != BaseMaterial3D.TRANSPARENCY_DISABLED and \
				(material as BaseMaterial3D).albedo_color.a < 1.0)
	_expect(motion_result == EditorPlugin.AFTER_GUI_INPUT_PASS and ghost != null and
		ghost.get_parent() == root and ghost.owner == null and
		not root.get_children().has(ghost) and root.get_children(true).has(ghost) and see_through,
		"a see-through ghost follows the cursor as an internal, ownerless node")
	var results := [
		palette.call("_forward_3d_gui_input", camera, _key(KEY_Q)),
		palette.call("_forward_3d_gui_input", camera, _key(KEY_E, true)),
		palette.call("_forward_3d_gui_input", camera, _key(KEY_PAGEUP)),
		palette.call("_forward_3d_gui_input", camera, _key(KEY_PAGEDOWN, true)),
		palette.call("_forward_3d_gui_input", camera, _key(KEY_HOME)),
		palette.call("_forward_3d_gui_input", camera, _wheel(true)),
	]
	var state := palette.call("placement_state") as Dictionary
	_expect(results.all(func(value: int) -> bool: return value == EditorPlugin.AFTER_GUI_INPUT_STOP) and
		is_equal_approx(float(state.yaw), 29.0) and is_equal_approx(float(state.lift), 0.2) and
		is_equal_approx(float(state.size), 1.1),
		"Q/E and Shift+wheel turn, PgUp/PgDn raise, Home grows, Shift gives fine steps")
	var assets := root.get_node("AuthoredAssets")
	var before := assets.get_child_count()
	var ghost_transform := ghost.global_transform
	var click_result: int = palette.call("_forward_3d_gui_input", camera, _click(centre))
	state = palette.call("placement_state") as Dictionary
	var first := assets.get_child(assets.get_child_count() - 1) as Node3D \
		if assets.get_child_count() > before else null
	_expect(click_result == EditorPlugin.AFTER_GUI_INPUT_STOP and bool(state.armed) and
		first != null and first.global_transform.is_equal_approx(ghost_transform) and
		not String(first.get("asset_id")).is_empty(),
		"a click places exactly what the ghost showed and keep-placing stays armed")
	palette.call("_forward_3d_gui_input", camera, _key(KEY_BACKSPACE))
	state = palette.call("placement_state") as Dictionary
	var reset := is_zero_approx(float(state.yaw)) and is_zero_approx(float(state.lift)) and \
		is_equal_approx(float(state.size), 1.0)
	palette.call("_forward_3d_gui_input", camera, _key(KEY_G))
	var snapped_on := bool(Settings.value("placement/snap_to_grid"))
	# The headless editor viewport is tiny, so aim the camera rather than the cursor.
	_aim(camera, root, Vector2(12.3, 27.7))
	palette.call("_forward_3d_gui_input", camera, _click(centre))
	var second := assets.get_child(assets.get_child_count() - 1) as Node3D \
		if assets.get_child_count() > before + 1 else null
	var local := root.global_transform.affine_inverse() * second.global_position \
		if second != null else Vector3(0.5, 0, 0.5)
	palette.call("_forward_3d_gui_input", camera, _key(KEY_G))
	_expect(reset and snapped_on and not bool(Settings.value("placement/snap_to_grid")) and
		second != null and absf(local.x - roundf(local.x)) < 0.0001 and
		absf(local.z - roundf(local.z)) < 0.0001,
		"Backspace resets adjustments and G toggles snapping to the 1 m territory grid")
	var ids := {}
	for child in assets.get_children():
		ids[String(child.get("asset_id"))] = true
	_expect(ids.size() == assets.get_child_count(),
		"consecutive placements receive distinct asset ids")
	palette.call("_forward_3d_gui_input", camera, _click(centre, MOUSE_BUTTON_RIGHT))
	state = palette.call("placement_state") as Dictionary
	_expect(not bool(state.armed) and state.ghost == null and
		root.get_children(true).all(func(node: Node) -> bool:
			return not String(node.name).begins_with("__MapAssetGhost")),
		"right-click stops placing and removes the ghost")
	var history := _undo.get_history_undo_redo(_undo.get_object_history_id(root))
	history.undo()
	var undone := assets.get_child_count() == before + 1
	history.redo()
	_expect(undone and assets.get_child_count() == before + 2,
		"each placement is its own undo step")
	if first != null:
		placed.append(first)
	if second != null:
		placed.append(second)
	return placed


func _test_cursor_readout_and_grid(usability: Object, root: Node3D, camera: Camera3D) -> void:
	var motion := InputEventMouseMotion.new()
	motion.position = camera.get_viewport().get_visible_rect().size * 0.5
	usability.call("_forward_3d_gui_input", camera, motion)
	usability.call("_refresh_hover")
	var state := usability.call("hover_state") as Dictionary
	var text := String(usability.call("readout_text"))
	var expected := Probe.describe_point(root, state.hit as Vector3) \
		if state.hit is Vector3 else {}
	var tile_text := "tile %d, %d" % [expected.tile.x, expected.tile.y] \
		if not expected.is_empty() else "?"
	_expect(tile_text in text and "height" in text and "X " in text,
		"cursor readout shows territory metres, server tile and height (%s)" % text)
	var grid := state.grid as MeshInstance3D
	var vertices := 0
	if grid != null and grid.mesh != null and grid.mesh.get_surface_count() > 0:
		vertices = (grid.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
	_expect(grid != null and grid.visible and grid.owner == null and
		not root.get_children().has(grid) and vertices > 200,
		"the cursor grid drapes an internal, unsaved line mesh over the terrain (%d vertices)" %
			vertices)
	Settings.set_value("grid/cursor_grid", Settings.CursorGrid.OFF)
	usability.call("_refresh_hover")
	_expect(not grid.visible, "the cursor grid can be switched off")
	Settings.set_value("grid/cursor_grid", Settings.CursorGrid.ALWAYS)


func _test_selection_tools(usability: Object, root: Node3D, placed: Array[Node3D]) -> void:
	var selection := _editor.call("get_selection") as EditorSelection
	var history := _undo.get_history_undo_redo(_undo.get_object_history_id(root))
	_expect(Tools.placements(root, [root.get_node("Terrain"), root.get_node("AuthoredAssets"),
		root]).is_empty() and Tools.placements(root, placed).size() == 2,
		"batch tools only accept placements, never terrain, containers or the root")
	# The first placement was lifted 0.2 m with PgUp; raise it further, then drop.
	var first := placed[0]
	first.global_position += Vector3.UP * 3.0
	var raised_transform := first.global_transform
	var ground := Probe.height_at(root, first.global_position)
	selection.clear()
	for node in placed:
		selection.add_node(node)
	var dropped: int = usability.call("run_tool", UsabilityPlugin.MenuId.DROP_TO_GROUND)
	var landed_transform := first.global_transform
	var landed := absf(_bottom(first, landed_transform) - ground) < 0.001 and \
		landed_transform.basis.is_equal_approx(raised_transform.basis)
	history.undo()
	var raised := first.global_transform.is_equal_approx(raised_transform)
	history.redo()
	_expect(dropped == 1 and landed and raised and
		first.global_transform.is_equal_approx(landed_transform),
		"Drop to ground re-seats a lifted asset on the terrain as one undo step")
	var before: Array[Transform3D] = []
	for node in placed:
		before.append(node.global_transform)
	usability.call("run_tool", UsabilityPlugin.MenuId.ROTATE_EACH)
	var rotated := true
	for index in placed.size():
		var node := placed[index]
		rotated = rotated and node.global_position.is_equal_approx(before[index].origin) and \
			node.global_transform.basis.x.is_equal_approx(
				Basis(Vector3.UP, PI * 0.5) * before[index].basis.x)
	_expect(rotated, "Rotate each turns every asset 90° about its own pivot")
	var bases: Array[float] = []
	for node in placed:
		bases.append(_bottom(node, node.global_transform))
	usability.call("run_tool", UsabilityPlugin.MenuId.RANDOM_SIZE)
	var kept := true
	for index in placed.size():
		kept = kept and absf(_bottom(placed[index], placed[index].global_transform) -
			bases[index]) < 0.001
	_expect(kept, "Random size keeps each asset's visible base where it was")
	selection.clear()


func _test_prefab(palette: Object, root: Node3D, placed: Array[Node3D], camera: Camera3D) -> void:
	var selection := _editor.call("get_selection") as EditorSelection
	var assets := root.get_node("AuthoredAssets")
	var mesh_path := _first_mesh_path(placed[0])
	var override: Resource = OVERRIDE.new()
	override.mesh_node_path = mesh_path
	override.surface = MapAuthoringSurface.new()
	var overrides: Array[Resource] = [override]
	placed[0].set("material_overrides", overrides)
	_expect((placed[0].get("material_overrides") as Array).size() == 1,
		"fixture asset carries a local material override before it is saved as a prefab")
	selection.clear()
	for node in placed:
		selection.add_node(node)
	var result := palette.call("save_selection_as_prefab", "Test Pair") as Dictionary
	var path := PREFAB_DIR + "/test_pair.tscn"
	_expect(String(result.get("path", "")) == path and FileAccess.file_exists(path) and
		int(result.get("members", 0)) == 2 and
		Prefabs.entries().any(func(entry: Dictionary) -> bool:
			return String(entry.id) == "prefab:test_pair"),
		"Save selection writes a prefab that the library lists")
	var prefab_entry := _entry(Prefabs.entries(), "prefab:test_pair")
	var old_ids := {}
	for child in assets.get_children():
		old_ids[String(child.get("asset_id"))] = true
	var before := assets.get_child_count()
	palette.call("_arm_placement", prefab_entry)
	var point := camera.get_viewport().get_visible_rect().size * 0.5
	_aim(camera, root, Vector2(28.0, 10.0))
	var motion := InputEventMouseMotion.new()
	motion.position = point
	palette.call("_forward_3d_gui_input", camera, motion)
	palette.call("_refresh_hover")
	var ghost := (palette.call("placement_state") as Dictionary).ghost as Node3D
	_expect(ghost != null and ghost.get_child_count() == 2 and ghost.owner == null,
		"a prefab ghost previews every member")
	palette.call("_forward_3d_gui_input", camera, _click(point))
	_aim(camera, root, Vector2(9.0, 12.0))
	palette.call("_forward_3d_gui_input", camera, _click(point))
	palette.call("_cancel_placement")
	var fresh: Array[Node] = []
	for index in range(before, assets.get_child_count()):
		fresh.append(assets.get_child(index))
	var fresh_ids := {}
	for node in fresh:
		fresh_ids[String(node.get("asset_id"))] = true
	var linked := fresh.all(func(node: Node) -> bool:
		var content: Node = node.call("content_root")
		return content != null and not content.scene_file_path.is_empty() and \
			node.owner == root and content.owner == root)
	_expect(fresh.size() == 4 and fresh_ids.size() == 4 and
		fresh_ids.keys().all(func(id: String) -> bool: return not old_ids.has(id)) and linked,
		"placing a prefab twice creates linked assets with fresh, unique ids")
	var surfaces := {}
	for node in fresh:
		for item: Resource in node.get("material_overrides"):
			surfaces[item.get_instance_id()] = true
			if item.get("surface") != null:
				surfaces[(item.get("surface") as Resource).get_instance_id()] = true
	var override_counts := fresh.map(func(node: Node) -> int:
		return (node.get("material_overrides") as Array).size())
	_expect(surfaces.size() == 4 and not surfaces.has(override.get_instance_id()),
		"every placed prefab copy owns an independent material override (%d ids, %s)" % [
			surfaces.size(), override_counts])
	var history := _undo.get_history_undo_redo(_undo.get_object_history_id(root))
	history.undo()
	var one_step := assets.get_child_count() == before + 2
	history.redo()
	_expect(one_step and assets.get_child_count() == before + 4,
		"each prefab placement is a single undo step")
	selection.clear()


func _test_save_excludes_helpers(palette: Object, usability: Object, root: Node3D,
		entry: Dictionary, camera: Camera3D) -> void:
	palette.call("_arm_placement", entry)
	var motion := InputEventMouseMotion.new()
	motion.position = camera.get_viewport().get_visible_rect().size * 0.5
	palette.call("_forward_3d_gui_input", camera, motion)
	palette.call("_refresh_hover")
	usability.call("_forward_3d_gui_input", camera, motion)
	usability.call("_refresh_hover")
	var packed := PackedScene.new()
	var saved: bool = packed.pack(root) == OK and ResourceSaver.save(packed, RELOAD_PATH) == OK
	var text := FileAccess.get_file_as_string(RELOAD_PATH)
	var reopened := (load(RELOAD_PATH) as PackedScene).instantiate()
	get_root().add_child(reopened)
	await process_frame
	var helpers := reopened.find_children("__Map*", "", true, false)
	_expect(saved and not "__MapAuthoringMarkerOverlay" in text and
		not "__MapAuthoringWalkability" in text and not "__MapAuthoringPathDraft" in text and
		'path_id = "road-01"' in text and 'record_id = "crystal-02"' in text,
		"new markers and roads are saved; marker pins, walkability tint and path drafts never are")
	_expect(saved and not "__MapAssetGhost" in text and not "__MapAuthoringCursorGrid" in text and
		not "__MapAuthoringTimeOfDay" in text and not "DirectionalLight3D" in text and
		helpers.is_empty() and reopened.get_node("AuthoredAssets").get_child_count() ==
		root.get_node("AuthoredAssets").get_child_count(),
		"save/reopen keeps every placed asset and never the ghost or cursor grid")
	reopened.queue_free()
	await process_frame


func _test_marker_palette(palette: Object, usability: Object, root: Node3D,
		camera: Camera3D) -> void:
	var entries := Markers.entries(root)
	var template := {}
	for candidate in entries:
		if String(candidate.label) == "Harvestable: Crystal (mineral)":
			template = candidate
	var kinds := {}
	for candidate in entries:
		kinds[String(candidate.marker_kind)] = true
	_expect(kinds.size() == Markers.KINDS.size() and not kinds.has("runtime_point") and
		not template.is_empty() and String(template.marker_label) == "Crystal" and
		(template.marker_extras as Dictionary).has("harvestHook") and
		not (template.marker_extras as Dictionary).has("propPosition"),
		"marker palette offers every exported kind plus templates from the territory's own markers")
	var dock: Object = palette.get("_dock")
	dock.call("select_category", Markers.CATEGORY)
	_expect(String(template.id) in (dock.call("visible_entry_ids") as PackedStringArray),
		"the Map Assets dock lists gameplay markers under their own category")
	palette.call("_arm_placement", template)
	_aim(camera, root, Vector2(16.0, 26.0))
	var centre := camera.get_viewport().get_visible_rect().size * 0.5
	var motion := InputEventMouseMotion.new()
	motion.position = centre
	palette.call("_forward_3d_gui_input", camera, motion)
	palette.call("_refresh_hover")
	var ghost := (palette.call("placement_state") as Dictionary).ghost as Node3D
	_expect(ghost != null and ghost.owner == null and
		not ghost.find_children("*", "MeshInstance3D", true, false).is_empty(),
		"a marker ghost is a see-through pin in the kind's colour")
	palette.call("_forward_3d_gui_input", camera, _click(centre))
	var created := root.get_node_or_null("Gameplay/Harvestables/crystal-02") as Node3D
	var ground := Probe.height_at(root, created.global_position) if created != null else NAN
	_expect(created != null and created.get_script() == MARKER and
		String(created.get("record_id")) == "crystal-02" and String(created.get("label")) == "Crystal" and
		(created.get("extras") as Dictionary).get("harvestHook") == "harvest.test" and
		not (created.get("extras") as Dictionary).has("propPosition") and
		absf(created.global_position.y - ground) < 0.001 and created.owner == root,
		"a click places a harvestable with a fresh id, copied conventions and no copied position")
	var history := _undo.get_history_undo_redo(_undo.get_object_history_id(root))
	history.undo()
	var removed := root.get_node_or_null("Gameplay/Harvestables/crystal-02") == null
	history.redo()
	_expect(removed and root.get_node_or_null("Gameplay/Harvestables/crystal-02") != null,
		"each marker placement is one undo step")
	var spawn := {}
	for candidate in entries:
		if String(candidate.marker_kind) == "spawn":
			spawn = candidate
	palette.call("_arm_placement", spawn)
	palette.call("_forward_3d_gui_input", camera, _key(KEY_Q))
	palette.call("_forward_3d_gui_input", camera, _key(KEY_Q))
	_aim(camera, root, Vector2(24.0, 30.0))
	palette.call("_forward_3d_gui_input", camera, _click(centre))
	palette.call("_cancel_placement")
	var spawns := root.get_node_or_null("Gameplay/Spawns")
	var spawn_marker := spawns.get_child(0) as Node3D if spawns != null and \
		spawns.get_child_count() > 0 else null
	_expect(spawn_marker != null and String(spawn_marker.get("kind")) == "spawn" and
		(spawn_marker.get("facing") as Vector3).is_equal_approx(
			Basis(Vector3.UP, deg_to_rad(30.0)) * Vector3.FORWARD),
		"a spawn creates its container and Q/E turn its facing (30° here)")
	usability.call("poll_overlays")
	var overlay := usability.call("marker_overlay_state") as Dictionary
	var pins := overlay.node as Node3D
	var mesh := (pins.get_node("Pins") as MeshInstance3D).mesh if pins != null else null
	_expect(pins != null and pins.owner == null and not root.get_children().has(pins) and
		int(overlay.labels) == Markers.markers(root).size() and mesh != null and
		mesh.get_surface_count() > 0,
		"every marker gets a coloured pin and a name label in an internal overlay")
	Settings.set_value("markers/show", false)
	usability.call("poll_overlays")
	_expect((usability.call("marker_overlay_state") as Dictionary).node == null,
		"marker pins can be switched off")
	Settings.set_value("markers/show", true)
	usability.call("poll_overlays")


func _test_walkability(usability: Object, root: Node3D) -> void:
	var shown: bool = usability.call("set_walkability_mode", Walkability.Mode.PUBLISHED)
	var state := usability.call("walkability_state") as Dictionary
	_expect(not shown and int(state.mode) == Walkability.Mode.OFF and
		"published" in String(state.message).to_lower(),
		"a territory without a published grid says so instead of tinting nothing")
	# The fast path (terrain cells twice the tile size, as in production's 2 m / 1 m)
	# must equal the pipeline rule tile by tile; here 1 m cells over 0.5 m tiles.
	var terrain := root.get_node("Terrain")
	var heights: PackedFloat32Array = terrain.call("effective_heights")
	var grid: Vector2i = terrain.get("grid_size")
	var width := (grid.x - 1) * 2
	var rows := (grid.y - 1) * 2
	var classes := PackedByteArray()
	classes.resize(width * rows)
	classes.fill(Walkability.Tile.WALKABLE)
	var data := {"heights": heights, "grid": grid, "cell": 1.0, "tile": 0.5,
		"width": width, "rows": rows, "classes": classes}
	Walkability._grade_pass(data)
	var mismatches := 0
	var steep_tiles := 0
	for row in rows:
		for column in width:
			var worst := 0.0
			for half: Vector2 in [Vector2(0.25, 0.25), Vector2(0.75, 0.25), Vector2(0.25, 0.75),
					Vector2(0.75, 0.75)]:
				var fx := (float(column) + half.x) / 2.0
				var fz := (float(row) + half.y) / 2.0
				var ix := mini(floori(fx), grid.x - 2)
				var iz := mini(floori(fz), grid.y - 2)
				var u := fx - float(ix)
				var v := fz - float(iz)
				var a := heights[iz * grid.x + ix]
				var b := heights[iz * grid.x + ix + 1]
				var c := heights[(iz + 1) * grid.x + ix]
				var d := heights[(iz + 1) * grid.x + ix + 1]
				var dx := b - a if u + v <= 1.0 else d - c
				var dz := c - a if u + v <= 1.0 else d - b
				worst = maxf(worst, sqrt(dx * dx + dz * dz))
			var expected := worst > Walkability.MAX_GRADE
			steep_tiles += 1 if expected else 0
			if expected != ((data.classes as PackedByteArray)[row * width + column] ==
					Walkability.Tile.STEEP):
				mismatches += 1
	_expect(mismatches == 0 and steep_tiles > 0,
		"the fast grade pass marks exactly the tiles whose half-cells exceed grade 0.65 (%d steep)" %
			steep_tiles)
	# Live mode on the fixture itself (1 m cells take the general path).
	var lake := root.get_node("WaterRegions/test-lake") as Node3D
	var lake_ground := Probe.height_at(root, Vector3(30.0, 0.0, 30.0))
	lake.global_position = Vector3(30.0, lake_ground + 1.2, 30.0)
	var asset := root.get_node("AuthoredAssets").get_child(0) as Node3D
	asset.set("collision_role", "solid")
	shown = usability.call("set_walkability_mode", Walkability.Mode.LIVE)
	usability.call("rebuild_walkability")
	state = usability.call("walkability_state") as Dictionary
	var overlay := state.node as MeshInstance3D
	var walk := Walkability.new()
	walk.set_mode(root, Walkability.Mode.LIVE)
	var lake_tile := walk.live_tile(Vector3(30.5, 0.0, 30.5))
	var dry_tile := walk.live_tile(Vector3(30.5, 0.0, 20.5))
	var asset_tile := walk.live_tile(asset.global_position)
	var steep_sample := -1
	for row in range(0, 40, 3):
		for column in range(0, 40, 3):
			var point := Vector3(float(column) + 0.5, 0.0, float(row) + 0.5)
			var tile := walk.live_tile(point)
			if tile == Walkability.Tile.STEEP:
				steep_sample = int(walk.grade_at(point) > Walkability.MAX_GRADE)
	var description := String(usability.call("walkability_describe", asset.global_position))
	_expect(shown and overlay != null and overlay.owner == null and overlay.visible and
		overlay.mesh == (terrain.get_node("__TerrainPreview") as MeshInstance3D).mesh and
		lake_tile == Walkability.Tile.WATER and dry_tile != Walkability.Tile.WATER and
		asset_tile == Walkability.Tile.BLOCKED and steep_sample == 1 and
		String(asset.name) in description,
		"live walkability marks steep ground, deep water and solid assets (%s)" % description)
	walk.release()
	asset.set("collision_role", "none")
	shown = usability.call("set_walkability_mode", Walkability.Mode.CHANGES)
	_expect(not shown, "changes since publish needs a published grid to compare with")
	# A real published grid: Sunmane's collision.bin, as the server walks it.
	var region := String(root.get("region_id"))
	root.set("region_id", "sunmane_steppe")
	var published := Walkability.published_grid(root)
	root.set("region_id", region)
	var fraction := 0.0
	if not published.has("error"):
		var bytes: PackedByteArray = published.bytes
		fraction = float(bytes.size() - bytes.count(0)) / float(bytes.size())
	_expect(not published.has("error") and int(published.width) == 1584 and
		int(published.rows) == 1584 and is_equal_approx(float(published.cell), 0.5) and
		absf(fraction - float(published.walkable_fraction)) < 0.000001,
		"the published grid loads Sunmane's EWCG exactly (%.4f walkable, as its manifest records)" %
			fraction)
	usability.call("set_walkability_mode", Walkability.Mode.OFF)
	_expect((usability.call("walkability_state") as Dictionary).node == null,
		"switching the overlay off removes its tint")


func _test_path_drawing(palette: Object, usability: Object, root: Node3D, camera: Camera3D,
		entry: Dictionary) -> void:
	var centre := camera.get_viewport().get_visible_rect().size * 0.5
	palette.call("_arm_placement", entry)
	var started: bool = usability.call("start_path_drawing", "road")
	var tool: RefCounted = usability.call("path_draw_tool")
	_expect(started and bool(tool.call("is_active")) and
		not bool((palette.call("placement_state") as Dictionary).armed),
		"drawing a road stops asset placement")
	var clicked: Array[Vector3] = []
	for xz in [Vector2(10.0, 10.0), Vector2(20.0, 15.0), Vector2(33.0, 8.0)]:
		_aim(camera, root, xz)
		usability.call("_forward_3d_gui_input", camera, _click(centre))
		clicked.append(Probe.ray_hit(root, Vector3(xz.x, 60.0, xz.y), Vector3.DOWN) as Vector3)
	usability.call("_forward_3d_gui_input", camera, _key(KEY_BACKSPACE))
	clicked.pop_back()
	_aim(camera, root, Vector2(28.0, 25.0))
	usability.call("_forward_3d_gui_input", camera, _click(centre))
	clicked.append(Probe.ray_hit(root, Vector3(28.0, 60.0, 25.0), Vector3.DOWN) as Vector3)
	usability.call("_forward_3d_gui_input", camera, _key(KEY_BRACKETRIGHT))
	var draft := root.get_children(true).filter(func(node: Node) -> bool:
		return String(node.name).begins_with("__MapAuthoringPathDraft"))
	_expect(draft.size() == 1 and (draft[0] as Node).owner == null and
		(tool.get("points") as Array).size() == 3 and is_equal_approx(float(tool.get("width")), 5.0),
		"clicks add draped points, Backspace removes the last, ] widens the draft")
	var result: int = usability.call("_forward_3d_gui_input", camera, _key(KEY_ENTER))
	var road := root.get_node_or_null("Roads/road-01") as Path3D
	var matches := road != null and road.curve != null and road.curve.point_count == 3
	if matches:
		for index in 3:
			var world: Vector3 = road.global_transform * road.curve.get_point_position(index)
			matches = matches and world.distance_to(clicked[index]) < 0.05
	_expect(result == EditorPlugin.AFTER_GUI_INPUT_STOP and matches and road.owner == root and
		String(road.get("path_id")) == "road-01" and String(road.get("kind")) == "road" and
		String(road.get("routing_role")) == "required" and
		bool((road.get("properties") as Dictionary).get("terrainConform", false)) and
		is_equal_approx(float(road.get("default_width")), 5.0) and
		(road.call("snapshot_points") as Array).size() >= 3 and
		not bool(tool.call("is_active")) and road.get("surface") is MapAuthoringSurface and
		(road.get("surface") as MapAuthoringSurface).material_mode ==
			MapAuthoringSurface.MaterialMode.ROAD_SHADER,
		"Enter creates road-01 through the clicked ground points, terrain-shaped, with a road surface")
	var history := _undo.get_history_undo_redo(_undo.get_object_history_id(root))
	history.undo()
	var gone := root.get_node_or_null("Roads/road-01") == null
	history.redo()
	_expect(gone and root.get_node_or_null("Roads/road-01") != null,
		"a drawn road is one undo step")
	usability.call("start_path_drawing", "river")
	for xz in [Vector2(5.0, 30.0), Vector2(15.0, 36.0)]:
		_aim(camera, root, xz)
		usability.call("_forward_3d_gui_input", camera, _click(centre))
	usability.call("_forward_3d_gui_input", camera, _click(centre, MOUSE_BUTTON_RIGHT))
	var river := root.get_node_or_null("Rivers/river-01")
	_expect(river != null and String(river.get("kind")) == "river" and
		String(river.get("routing_role")) == "decorative",
		"right-click finishes a decorative river-01")
	# A click beside an existing road point joins it exactly.
	usability.call("start_path_drawing", "road")
	var first: Vector3 = road.global_transform * road.curve.get_point_position(0)
	_aim(camera, root, Vector2(first.x + 1.2, first.z - 0.8))
	usability.call("_forward_3d_gui_input", camera, _click(centre))
	var joined := (tool.get("points") as Array)
	_expect(joined.size() == 1 and (joined[0] as Vector3).is_equal_approx(first),
		"a click within 2.5 m of a path point snaps onto it")
	usability.call("_forward_3d_gui_input", camera, _key(KEY_ESCAPE))
	_expect(not bool(tool.call("is_active")) and root.get_node_or_null("Roads/road-02") == null and
		root.get_children(true).all(func(node: Node) -> bool:
			return not String(node.name).begins_with("__MapAuthoringPathDraft")),
		"Escape discards a draft without adding anything")


func _aim(camera: Camera3D, root: Node3D, xz: Vector2) -> void:
	var target := Probe.ray_hit(root, Vector3(xz.x, 60.0, xz.y), Vector3.DOWN) as Vector3
	camera.global_position = target + Vector3(0.0, 30.0, 0.01)
	camera.look_at(target, Vector3.FORWARD)


func _bottom(node: Node3D, transform: Transform3D) -> float:
	var bounds := Placement.mesh_bounds(node)
	return transform.origin.y + (Transform3D(transform.basis, Vector3.ZERO) *
		(bounds.bounds as AABB)).position.y


func _height(node: Node3D, transform: Transform3D) -> float:
	var bounds := Placement.mesh_bounds(node)
	return (Transform3D(transform.basis, Vector3.ZERO) * (bounds.bounds as AABB)).size.y


func _first_mesh_path(asset: Node3D) -> String:
	var content: Node = asset.call("content_root")
	for node in content.find_children("*", "MeshInstance3D", true, false):
		return String(content.get_path_to(node))
	return ""


func _key(keycode: Key, shift: bool = false) -> InputEventKey:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.pressed = true
	event.shift_pressed = shift
	return event


func _wheel(up: bool) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_WHEEL_UP if up else MOUSE_BUTTON_WHEEL_DOWN
	event.pressed = true
	event.shift_pressed = true
	return event


func _click(position: Vector2, button: MouseButton = MOUSE_BUTTON_LEFT) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.button_index = button
	event.pressed = true
	event.position = position
	return event


func _entry(entries: Array[Dictionary], id: String) -> Dictionary:
	for entry in entries:
		if String(entry.id) == id:
			return entry
	return {}


func _remove_tree(path: String) -> void:
	var absolute := ProjectSettings.globalize_path(path)
	var folder := DirAccess.open(absolute)
	if folder == null:
		return
	for file_name in folder.get_files():
		DirAccess.remove_absolute(absolute.path_join(file_name))
	DirAccess.remove_absolute(absolute)


func _expect(condition: bool, message: String) -> bool:
	if condition:
		print("PASS: ", message)
		return true
	failures += 1
	push_error("FAIL: " + message)
	return false


func _finish() -> void:
	for key: String in _saved_settings:
		Settings.set_value(key, _saved_settings[key])
	Prefabs.directory = Prefabs.PREFAB_DIRECTORY
	_remove_tree(PREFAB_DIR)
	for path in [HEIGHT_PATH, SCENE_PATH, RELOAD_PATH]:
		if FileAccess.file_exists(path):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	print("map authoring usability editor: ",
		"PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)
