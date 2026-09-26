@tool
extends EditorPlugin

const Catalog := preload("res://addons/map_authoring_workspace/territory_catalog.gd")
const Dock := preload("res://addons/map_authoring_workspace/territory_dock.gd")
const Preview := preload("res://addons/map_authoring_workspace/reference_preview.gd")
const Sculpt := preload("res://addons/map_authoring_workspace/terrain_sculpt_tool.gd")
const SCULPT_PLUGIN_META := &"map_authoring_sculpt_plugin"
const ASSET_PLUGIN_META := &"map_asset_palette_plugin"
const Settings := preload("res://addons/map_authoring_usability/usability_settings.gd")
const SCULPT_MODE_NAMES := ["Raise", "Lower", "Smooth", "Flatten"]
const SCULPT_MODE_KEYS := ["sculpt_raise", "sculpt_lower", "sculpt_smooth", "sculpt_flatten"]
## Ring colours per brush: cyan raise, orange lower, blue smooth, gold flatten.
const SCULPT_RING_COLORS := [Color(0.22, 0.94, 0.79), Color(1.0, 0.55, 0.25),
	Color(0.45, 0.65, 1.0), Color(1.0, 0.86, 0.35)]

var _catalog := Catalog.new()
var _entries: Array[Dictionary] = []
var _dock: EditorDock
var _host: MapAuthoringReferencePreview
var _sculpt: MapAuthoringTerrainSculptTool = Sculpt.new()
var _active_root: Node3D
var _elapsed := 0.0
var _sculpt_tearing_down := false


func _enter_tree() -> void:
	_dock = Dock.new()
	_dock.open_requested.connect(_open_scene)
	_dock.references_changed.connect(_show_references)
	_dock.refresh_requested.connect(_reload_sources)
	_dock.sculpt_toggled.connect(_on_sculpt_toggled)
	_dock.sculpt_pick_height_requested.connect(_sculpt.pick_flatten_height)
	_sculpt.status_changed.connect(_dock.show_sculpt_status)
	_sculpt.flatten_height_picked.connect(_dock.set_flatten_target)
	_sculpt.stroke_started.connect(_on_sculpt_started)
	_sculpt.stroke_ended.connect(_on_sculpt_ended)
	add_dock(_dock)
	get_editor_interface().get_base_control().set_meta(SCULPT_PLUGIN_META, self)
	set_input_event_forwarding_always_enabled()
	scene_changed.connect(_on_scene_changed)
	set_process(true)
	_reload_sources()
	_on_scene_changed(get_editor_interface().get_edited_scene_root())


func _exit_tree() -> void:
	_sculpt_tearing_down = true
	deactivate_terrain_sculpt()
	_sculpt.unbind()
	_remove_host()
	var base := get_editor_interface().get_base_control()
	if base.get_meta(SCULPT_PLUGIN_META, null) == self:
		base.remove_meta(SCULPT_PLUGIN_META)
	if _dock != null:
		remove_dock(_dock)
		_dock.queue_free()
		_dock = null


func _process(delta: float) -> void:
	_sculpt.tick(delta)
	_elapsed += delta
	if _elapsed < 0.75:
		return
	_elapsed = 0.0
	if _host != null and not _sculpt.is_dragging():
		_host.refresh_if_changed()


func _input(event: InputEvent) -> void:
	# Editor shortcuts can be handled before the 3D viewport forwards input.
	# Commit the current stroke first so Save/Undo never sees pending edits.
	if _sculpt.is_dragging() and event is InputEventKey and event.pressed and \
			not event.echo and event.ctrl_pressed and \
			event.keycode in [KEY_S, KEY_Z, KEY_Y]:
		_sculpt.finish_stroke()


func _handles(_object: Object) -> bool:
	return _active_root != null and _sculpt.is_enabled()


func _forward_3d_gui_input(camera: Camera3D, event: InputEvent) -> int:
	if not _sculpt.is_enabled():
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if _handle_sculpt_shortcut(event):
		return EditorPlugin.AFTER_GUI_INPUT_STOP
	var settings: Dictionary = _dock.sculpt_settings()
	if event is InputEventWithModifiers and not _sculpt.is_dragging():
		settings = _modified_settings(settings, (event as InputEventWithModifiers).ctrl_pressed)
		_sculpt.set_ring_color(SCULPT_RING_COLORS[int(settings.mode)])
		if event is InputEventMouseButton and event.pressed and \
				event.button_index == MOUSE_BUTTON_LEFT and event.ctrl_pressed and \
				int(settings.mode) == 3:
			# Ctrl+click with Flatten samples the target height under the brush.
			_sculpt.pick_flatten_height()
	return _sculpt.handle_input(camera, event, settings)


## The viewport hint lines for the active brush, top first; empty when idle. The
## Map Authoring Usability plugin draws them above its cursor readout.
func overlay_lines() -> PackedStringArray:
	if not _sculpt.is_enabled() or _dock == null:
		return PackedStringArray()
	var settings: Dictionary = _dock.sculpt_settings()
	var mode := int(settings.mode)
	var strength := "%.2f m/stamp" % float(settings.strength) if mode < 2 \
		else "%d%% blend" % roundi(float(settings.strength) * 100.0)
	return PackedStringArray([
		"Sculpt %s  ·  radius %.1f m  ·  strength %s  ·  softness %.2f%s" % [
			SCULPT_MODE_NAMES[mode], float(settings.radius), strength,
			float(settings.softness),
			"  ·  flatten to %.2f m" % float(settings.flatten_target) if mode == 3 else ""],
		("Drag: sculpt  ·  Ctrl+drag: %s  ·  1-4: brush  ·  %s/%s or Shift+wheel: radius  ·  " +
			"Shift+%s/%s: strength  ·  Esc: cancel stroke") % [
			"sample flatten height" if mode == 3 else "Raise/Lower swapped" if mode < 2 \
				else "smooth",
			Settings.shortcut_text("sculpt_smaller"), Settings.shortcut_text("sculpt_larger"),
			Settings.shortcut_text("sculpt_smaller"), Settings.shortcut_text("sculpt_larger")],
	])


## Brush keys while sculpting: 1-4 pick the brush, [ and ] (or Shift+wheel) size
## it, Shift+[ and Shift+] change strength. Rebindable in Editor Settings.
func _handle_sculpt_shortcut(event: InputEvent) -> bool:
	if event is InputEventMouseButton and event.pressed and event.shift_pressed and \
			event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
		var factor := float(Settings.value("sculpt/radius_factor"))
		_dock.scale_sculpt_radius(factor if event.button_index == MOUSE_BUTTON_WHEEL_UP \
			else 1.0 / factor)
		_after_sculpt_shortcut()
		return true
	if not event is InputEventKey or not event.pressed:
		return false
	for index in SCULPT_MODE_KEYS.size():
		if Settings.matches(SCULPT_MODE_KEYS[index], event):
			_dock.set_sculpt_mode(index)
			_after_sculpt_shortcut()
			return true
	var smaller := Settings.matches("sculpt_smaller", event)
	if smaller or Settings.matches("sculpt_larger", event):
		if event.shift_pressed:
			var factor := float(Settings.value("sculpt/strength_factor"))
			_dock.scale_sculpt_strength(1.0 / factor if smaller else factor)
		else:
			var factor := float(Settings.value("sculpt/radius_factor"))
			_dock.scale_sculpt_radius(1.0 / factor if smaller else factor)
		_after_sculpt_shortcut()
		return true
	return false


func _after_sculpt_shortcut() -> void:
	var settings: Dictionary = _dock.sculpt_settings()
	_sculpt.set_ring_color(SCULPT_RING_COLORS[int(settings.mode)])
	_dock.show_sculpt_status("%s brush, radius %.1f m." % [SCULPT_MODE_NAMES[int(settings.mode)],
		float(settings.radius)])
	update_overlays()


## Ctrl swaps Raise and Lower for the stroke it starts; other brushes keep theirs.
static func _modified_settings(settings: Dictionary, ctrl: bool) -> Dictionary:
	var result := settings.duplicate()
	if ctrl and int(result.mode) < 2:
		result.mode = 1 - int(result.mode)
	return result


func deactivate_terrain_sculpt() -> void:
	_sculpt.set_enabled(false)
	if _dock != null:
		_dock.set_sculpt_active(false)
	if is_inside_tree():
		update_overlays()


func _on_sculpt_toggled(enabled: bool) -> void:
	if enabled:
		var base := get_editor_interface().get_base_control()
		var asset_plugin: Variant = base.get_meta(ASSET_PLUGIN_META, null)
		if asset_plugin is Object and is_instance_valid(asset_plugin) and \
				asset_plugin.has_method("cancel_placement_for_terrain_sculpt"):
			asset_plugin.call("cancel_placement_for_terrain_sculpt")
		if base.has_meta(&"map_authoring_usability_plugin"):
			var usability: Object = base.get_meta(&"map_authoring_usability_plugin")
			if is_instance_valid(usability) and usability.has_method("cancel_path_drawing"):
				usability.call("cancel_path_drawing")
	_sculpt.set_enabled(enabled)
	_sculpt.set_ring_color(SCULPT_RING_COLORS[int(_dock.sculpt_settings().mode)])
	update_overlays()
	if enabled and _sculpt.is_enabled():
		get_editor_interface().set_main_screen_editor("3D")
	elif enabled:
		_dock.set_sculpt_active(false)
		_dock.show_sculpt_status("Open a valid saved authored territory to sculpt.")


func _on_sculpt_started() -> void:
	if _host != null:
		_host.set_sculpt_preview_active(true)


func _on_sculpt_ended() -> void:
	if _host != null:
		_host.set_sculpt_preview_active(false)
		if not _sculpt_tearing_down:
			_host.refresh_if_changed()


func _reload_sources() -> void:
	_sculpt_tearing_down = true
	deactivate_terrain_sculpt()
	_sculpt.unbind()
	_sculpt_tearing_down = false
	var selected: PackedStringArray = _dock.selected_reference_ids() \
		if _dock != null else PackedStringArray()
	_entries = _catalog.entries()
	var active_id := String(_active_root.get("region_id")) if _active_root != null else ""
	_dock.configure(_entries, active_id, selected)
	if not _catalog.errors.is_empty():
		_dock.show_status("Catalog error: " + " ".join(_catalog.errors))
		return
	if _host != null:
		_host.clear_source_cache()
		_show_references(selected)
		_bind_sculpt(_catalog.find(_entries, active_id))


func _on_scene_changed(scene_root: Node) -> void:
	_sculpt_tearing_down = true
	deactivate_terrain_sculpt()
	_sculpt.unbind()
	_remove_host()
	_sculpt_tearing_down = false
	_active_root = scene_root as Node3D if scene_root is Node3D and \
		scene_root.has_method("export_snapshot") else null
	var active_id := String(_active_root.get("region_id")) if _active_root != null else ""
	_dock.configure(_entries, active_id)
	_dock.set_sculpt_available(false, "Open a valid saved authored territory scene.")
	if _active_root == null:
		return
	var entry := _catalog.find(_entries, active_id)
	if entry.is_empty() or not bool(entry.editable):
		_dock.show_status("This scene is not a complete catalogued authored territory.")
		return
	var active_error := _catalog.active_scene_error(_active_root, entry)
	if not active_error.is_empty():
		_dock.show_status(active_error + " Expected: %s" % String(entry.scene_path))
		return
	_host = Preview.new()
	_active_root.add_child(_host, false, Node.INTERNAL_MODE_FRONT)
	_host.configure(_active_root, entry)
	_host.status_changed.connect(_dock.show_status)
	_bind_sculpt(entry)


func _bind_sculpt(entry: Dictionary) -> void:
	if _active_root == null or entry.is_empty() or not bool(entry.editable):
		return
	if String(_active_root.get("ownership_polygon_sha256")) != \
			String(entry.get("ownership_sha256", "")):
		_dock.set_sculpt_available(false,
			"Saved ownership boundary does not match the catalog; sculpt disabled.")
		return
	var terrain := _active_root.get_node_or_null("Terrain") as MapAuthoringTerrainControl
	if terrain == null or not _sculpt.bind(_active_root, terrain, entry,
			get_undo_redo()):
		_dock.set_sculpt_available(false,
			"Active terrain grid is unavailable; sculpt disabled.")
		return
	_dock.set_sculpt_available(true)


func _remove_host() -> void:
	if _host == null:
		return
	_host.clear()
	if is_instance_valid(_host.get_parent()):
		_host.get_parent().remove_child(_host)
	_host.queue_free()
	_host = null


func _open_scene(path: String) -> void:
	if path.is_empty() or not ResourceLoader.exists(path):
		_dock.show_status("Authored scene is unavailable: %s" % path)
		return
	get_editor_interface().open_scene_from_path(path)
	_dock.show_status("Opening saved authored scene: %s" % path)


func _show_references(ids: PackedStringArray) -> void:
	if _host == null:
		_dock.show_status("Open an authored territory before showing references.")
		return
	var references: Array[Dictionary] = []
	for id in ids:
		var entry := _catalog.find(_entries, id)
		if not entry.is_empty():
			references.append(entry)
	_host.set_references(references)
