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
const DIR := "res://test-artifacts/map-usability"
const HEIGHT_PATH := DIR + "/fixture-heights.f32le"
const SCENE_PATH := DIR + "/fixture.tscn"
const RELOAD_PATH := DIR + "/fixture-saved.tscn"
const PREFAB_DIR := DIR + "/prefabs"
const GRID := Vector2i(41, 41)
const SETTING_KEYS := ["placement/keep_placing", "placement/snap_to_grid", "grid/step",
	"grid/cursor_grid", "placement/random_rotation", "placement/size_variation",
	"placement/align_to_surface", "viewport/show_cursor_readout", "time_of_day/minute"]

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
	usability.call("set_time_preview", true, 90.0)
	await _test_save_excludes_helpers(palette, usability, root, entry, camera)
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
	terrain.preview_enabled = false
	fixture.add_child(terrain)
	terrain.owner = fixture
	for container in ["Roads", "Rivers", "Bridges", "AuthoredAssets", "Gameplay",
			"GeneratedPreview"]:
		var node := Node3D.new()
		node.name = container
		fixture.add_child(node)
		node.owner = fixture
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
	_expect(saved and not "__MapAssetGhost" in text and not "__MapAuthoringCursorGrid" in text and
		not "__MapAuthoringTimeOfDay" in text and not "DirectionalLight3D" in text and
		helpers.is_empty() and reopened.get_node("AuthoredAssets").get_child_count() ==
		root.get_node("AuthoredAssets").get_child_count(),
		"save/reopen keeps every placed asset and never the ghost or cursor grid")
	reopened.queue_free()
	await process_frame


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
