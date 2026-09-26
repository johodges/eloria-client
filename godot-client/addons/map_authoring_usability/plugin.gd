@tool
extends EditorPlugin
## Viewport quality-of-life for map authoring scenes:
## - a cursor readout (territory metres, server tile, ground height),
## - the "smart grid" that drapes over the terrain under the cursor,
## - a Map tools menu with undoable batch edits for selected placements,
## - a time-of-day lighting preview and a top-down map capture,
## - readable gameplay markers, a walkability overlay, and road/river drawing,
## - rebindable shortcuts and preferences in Editor Settings > Map Authoring.
## Nothing here is saved into scenes; every helper node is internal and ownerless.

const Settings := preload("res://addons/map_authoring_usability/usability_settings.gd")
const Probe := preload("res://addons/map_authoring_usability/terrain_probe.gd")
const CursorGrid := preload("res://addons/map_authoring_usability/cursor_grid.gd")
const Tools := preload("res://addons/map_authoring_usability/selection_tools.gd")
const PalettePlugin := preload("res://addons/map_asset_palette/plugin.gd")
const TimeOfDay := preload("res://addons/map_authoring_usability/time_of_day_preview.gd")
const TopDown := preload("res://addons/map_authoring_usability/top_down_capture.gd")
const MarkerOverlay := preload("res://addons/map_authoring_usability/marker_overlay.gd")
const Walkability := preload("res://addons/map_authoring_usability/walkability_overlay.gd")
const PathDraw := preload("res://addons/map_authoring_usability/path_draw_tool.gd")
const POLL_SECONDS := 0.5
const ASSET_PLUGIN_META := &"map_asset_palette_plugin"
const SCULPT_PLUGIN_META := &"map_authoring_sculpt_plugin"
const USABILITY_PLUGIN_META := &"map_authoring_usability_plugin"
const RAY_LENGTH := 2048.0

enum MenuId {
	DROP_TO_GROUND,
	ROTATE_EACH,
	RANDOM_TURN,
	RANDOM_SIZE,
	SAVE_PREFAB,
	GRID_OFF,
	GRID_WHILE_PLACING,
	GRID_ALWAYS,
	READOUT,
	TIME_OF_DAY,
	CAPTURE_TOP_DOWN,
	SHOW_MARKERS,
	MARKER_LABELS,
	WALK_OFF,
	WALK_PUBLISHED,
	WALK_LIVE,
	WALK_CHANGES,
	DRAW_ROAD,
	DRAW_RIVER,
}

var _menu: MenuButton
var _grid := CursorGrid.new()
var _rng := RandomNumberGenerator.new()
var _hover_camera: Camera3D
var _hover_position := Vector2.ZERO
var _hover_dirty := false
var _hover_hit: Variant = null
var _hover_info: Dictionary = {}
var _hover_inside := false
var _time := TimeOfDay.new()
var _time_button: Button
var _time_panel: PopupPanel
var _time_toggle: CheckButton
var _time_slider: HSlider
var _time_label: Label
var _time_status: Label
var _capture_dialog: ConfirmationDialog
var _capture_path: LineEdit
var _capture_ppm: SpinBox
var _capture_references: CheckBox
var _capture_clip: CheckBox
var _capture_estimate: Label
var _capture_file_dialog: EditorFileDialog
var _capturing := false
var _markers := MarkerOverlay.new()
var _walk := Walkability.new()
var _draw := PathDraw.new()
var _walk_mode := Walkability.Mode.OFF
var _poll_elapsed := 0.0


func _enter_tree() -> void:
	Settings.register()
	_rng.randomize()
	get_editor_interface().get_base_control().set_meta(USABILITY_PLUGIN_META, self)
	_menu = MenuButton.new()
	_menu.text = "Map tools"
	_menu.flat = true
	_menu.tooltip_text = "Batch tools for selected placements and map editor view options."
	_menu.switch_on_hover = true
	_build_menu(_menu.get_popup())
	_menu.about_to_popup.connect(_sync_menu)
	add_control_to_container(EditorPlugin.CONTAINER_SPATIAL_EDITOR_MENU, _menu)
	_build_time_controls()
	add_control_to_container(EditorPlugin.CONTAINER_SPATIAL_EDITOR_MENU, _time_button)
	_build_capture_dialog()
	set_input_event_forwarding_always_enabled()
	set_force_draw_over_forwarding_enabled()
	scene_changed.connect(_on_scene_changed)


func _exit_tree() -> void:
	_grid.release()
	_time.disable()
	_markers.release()
	_walk.release()
	_draw.cancel()
	if _time_button != null:
		remove_control_from_container(EditorPlugin.CONTAINER_SPATIAL_EDITOR_MENU, _time_button)
		_time_button.queue_free()
		_time_button = null
	for dialog: Node in [_capture_dialog, _capture_file_dialog]:
		if is_instance_valid(dialog):
			dialog.queue_free()
	_capture_dialog = null
	_capture_file_dialog = null
	var base := get_editor_interface().get_base_control()
	if base.has_meta(USABILITY_PLUGIN_META) and base.get_meta(USABILITY_PLUGIN_META) == self:
		base.remove_meta(USABILITY_PLUGIN_META)
	if _menu != null:
		remove_control_from_container(EditorPlugin.CONTAINER_SPATIAL_EDITOR_MENU, _menu)
		_menu.queue_free()
		_menu = null


func _handles(_object: Object) -> bool:
	return false


func _process(delta: float) -> void:
	if _hover_dirty:
		_hover_dirty = false
		_refresh_hover()
	_poll_elapsed += delta
	if _poll_elapsed >= POLL_SECONDS:
		_poll_elapsed = 0.0
		poll_overlays()


## Refreshes the marker pins and the live walkability after edits settle.
func poll_overlays() -> void:
	var root := _authoring_root()
	if root == null:
		_markers.release()
		return
	if bool(Settings.value("markers/show")):
		_markers.refresh(root, bool(Settings.value("markers/labels")))
	else:
		_markers.release()
	var sculpt := _sculpt_plugin()
	var dragging := false
	if sculpt != null and sculpt.get("_sculpt") != null:
		dragging = bool(sculpt.get("_sculpt").call("is_dragging"))
	_walk.poll(dragging)


func _forward_3d_gui_input(camera: Camera3D, event: InputEvent) -> int:
	if _authoring_root() == null:
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if _draw.is_active():
		var drawn_before := _draw.points.size()
		var result := _draw.handle_input(camera, event, get_undo_redo())
		if not _draw.is_active() and drawn_before >= 2 and _draw.last_message.begins_with("Added"):
			_select_last_path()
		if _draw.last_message != "":
			_status(_draw.last_message)
		update_overlays()
		if event is InputEventMouseMotion:
			_hover_camera = camera
			_hover_position = (event as InputEventMouseMotion).position
			_hover_inside = true
			_hover_dirty = true
		return result
	if event is InputEventMouseMotion:
		_hover_camera = camera
		_hover_position = (event as InputEventMouseMotion).position
		_hover_inside = true
		_hover_dirty = true
	elif event is InputEventMouseButton or event is InputEventKey:
		# Placement adjustments (turn, lift, snap) change what the grid shows.
		_hover_dirty = true
	return EditorPlugin.AFTER_GUI_INPUT_PASS


func _forward_3d_force_draw_over_viewport(overlay: Control) -> void:
	if _authoring_root() == null:
		return
	var font := overlay.get_theme_default_font()
	var font_size := overlay.get_theme_default_font_size()
	var line_height := font.get_height(font_size) + 6.0
	var bottom := overlay.size.y - line_height * 0.5
	var text := readout_text() if bool(Settings.value("viewport/show_cursor_readout")) else ""
	if not text.is_empty():
		var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
		var top := bottom - line_height
		overlay.draw_rect(Rect2(8.0, top, width + 16.0, line_height), Color(0.0, 0.0, 0.0, 0.55))
		overlay.draw_string(font, Vector2(16.0, top + line_height - 8.0), text,
			HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0.72, 0.95, 0.86))
		bottom = top
	_draw_walkability_legend(overlay, font, font_size)
	# Drawing, placement and sculpt hints sit above the readout. Drawing them here
	# (this plugin force-draws) keeps them visible when nothing is selected.
	if _draw.is_active():
		PalettePlugin.draw_overlay_lines(overlay, _draw.hint_lines(), bottom)
		return
	for plugin: Object in [_palette_plugin(), _sculpt_plugin()]:
		if plugin != null and plugin.has_method("overlay_lines"):
			var hints: PackedStringArray = plugin.call("overlay_lines")
			if not hints.is_empty():
				PalettePlugin.draw_overlay_lines(overlay, hints, bottom)
				return


func _draw_walkability_legend(overlay: Control, font: Font, font_size: int) -> void:
	var items: Array = _walk.legend() if _walk.is_active() else []
	if items.is_empty():
		return
	var title := "Walkability: %s" % ["", "published grid (exact)", "live suggestion",
		"changes since publish"][int(_walk_mode)]
	var line_height := font.get_height(font_size) + 4.0
	var width := font.get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	for item: Array in items:
		width = maxf(width, font.get_string_size(String(item[0]), HORIZONTAL_ALIGNMENT_LEFT,
			-1, font_size).x + 22.0)
	var origin := Vector2(overlay.size.x - width - 28.0, 44.0)
	overlay.draw_rect(Rect2(origin, Vector2(width + 20.0, line_height * float(items.size() + 1) +
		8.0)), Color(0.0, 0.0, 0.0, 0.6))
	overlay.draw_string(font, origin + Vector2(10.0, line_height - 2.0), title,
		HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0.95, 0.95, 0.95))
	for index in items.size():
		var item: Array = items[index]
		var top := origin.y + line_height * float(index + 1) + 4.0
		overlay.draw_rect(Rect2(origin.x + 10.0, top + 3.0, 12.0, 12.0), item[1] as Color)
		overlay.draw_string(font, Vector2(origin.x + 30.0, top + line_height - 6.0),
			String(item[0]), HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0.9, 0.9, 0.9))


## The one-line status shown at the bottom-left of the 3D view.
func readout_text() -> String:
	if _hover_hit == null or _hover_info.is_empty():
		return ""
	var local: Vector3 = _hover_info.local
	var parts := PackedStringArray()
	parts.append("X %.2f  Z %.2f m" % [local.x, local.z])
	if bool(_hover_info.get("has_tile", false)):
		var tile: Vector2i = _hover_info.tile
		parts.append("tile %d, %d" % [tile.x, tile.y])
	parts.append("height %.2f m" % local.y)
	var walk := _walk.describe(local)
	if not walk.is_empty():
		parts.append(walk)
	var root := _authoring_root()
	if root != null:
		var count := Tools.placements(root,
			get_editor_interface().get_selection().get_selected_nodes()).size()
		if count > 0:
			parts.append("%d selected" % count)
	return "  ·  ".join(parts)


func hover_state() -> Dictionary:
	return {"hit": _hover_hit, "info": _hover_info.duplicate(true),
		"grid": _grid.node()}


## Runs a Map tools action on the current selection; returns how many changed.
func run_tool(id: int) -> int:
	var root := _authoring_root()
	if root == null:
		_toast("Open a map authoring scene first.")
		return 0
	var selection := get_editor_interface().get_selection().get_selected_nodes()
	if id == MenuId.SAVE_PREFAB:
		var palette := _palette_plugin()
		if palette == null:
			_toast("Enable the Map Asset Palette plugin to save prefabs.")
			return 0
		var result: Dictionary = palette.call("save_selection_as_prefab", "")
		if result.has("error"):
			_toast(String(result.error))
			return 0
		_toast("Saved prefab %s. Rename or delete it in %s." % [
			String(result.get("path", "")).get_file(), String(result.get("path", "")).get_base_dir()])
		return int(result.get("members", 0))
	var nodes := Tools.placements(root, selection)
	if nodes.is_empty():
		_toast("Select placed assets, scenery or gameplay markers first.")
		return 0
	var undo := get_undo_redo()
	var changed := 0
	match id:
		MenuId.DROP_TO_GROUND:
			changed = Tools.drop_to_ground(undo, root, nodes)
		MenuId.ROTATE_EACH:
			changed = Tools.rotate_each(undo, root, nodes, 90.0)
		MenuId.RANDOM_TURN:
			changed = Tools.randomize_turn(undo, root, nodes, _rng)
		MenuId.RANDOM_SIZE:
			var variation := float(Settings.value("placement/size_variation"))
			changed = Tools.randomize_size(undo, root, nodes,
				variation if variation > 0.0 else 0.15, _rng)
	if changed == 0 and id == MenuId.DROP_TO_GROUND:
		_toast("The selection already rests on the ground.")
	return changed


func _build_menu(popup: PopupMenu) -> void:
	popup.clear()
	var settings := Settings.editor_settings()
	_add_tool_item(popup, "Drop selection to ground", MenuId.DROP_TO_GROUND, "drop_to_ground",
		settings)
	_add_tool_item(popup, "Rotate each 90° (own pivot)", MenuId.ROTATE_EACH, "rotate_each",
		settings)
	popup.add_item("Random turn for each", MenuId.RANDOM_TURN)
	popup.add_item("Random size for each", MenuId.RANDOM_SIZE)
	popup.add_separator()
	_add_tool_item(popup, "Save selection as prefab", MenuId.SAVE_PREFAB, "save_prefab", settings)
	popup.add_separator("Cursor grid")
	popup.add_radio_check_item("Off", MenuId.GRID_OFF)
	popup.add_radio_check_item("While placing", MenuId.GRID_WHILE_PLACING)
	popup.add_radio_check_item("Always", MenuId.GRID_ALWAYS)
	popup.add_separator()
	popup.add_check_item("Cursor readout (metres, tile, height)", MenuId.READOUT)
	popup.add_separator("Gameplay markers")
	popup.add_check_item("Show markers (coloured pins)", MenuId.SHOW_MARKERS)
	popup.add_check_item("Marker labels", MenuId.MARKER_LABELS)
	popup.add_separator("Walkability overlay")
	popup.add_radio_check_item("Off", MenuId.WALK_OFF)
	popup.add_radio_check_item("Published grid (exact)", MenuId.WALK_PUBLISHED)
	popup.add_radio_check_item("Live suggestion from authoring", MenuId.WALK_LIVE)
	popup.add_radio_check_item("Changes since publish", MenuId.WALK_CHANGES)
	popup.add_separator("Paths")
	_add_tool_item(popup, "Draw road", MenuId.DRAW_ROAD, "draw_road", settings)
	_add_tool_item(popup, "Draw river", MenuId.DRAW_RIVER, "draw_river", settings)
	popup.add_separator()
	popup.add_item("Time of day preview…", MenuId.TIME_OF_DAY)
	popup.add_item("Capture top-down image…", MenuId.CAPTURE_TOP_DOWN)
	popup.id_pressed.connect(_on_menu_id)


func _add_tool_item(popup: PopupMenu, text: String, id: int, shortcut_key: String,
		settings: EditorSettings) -> void:
	popup.add_item(text, id)
	var path := Settings.PREFIX + shortcut_key
	if settings != null and settings.has_shortcut(path):
		popup.set_item_shortcut(popup.get_item_index(id), settings.get_shortcut(path), true)


func _sync_menu() -> void:
	var popup := _menu.get_popup()
	var mode := int(Settings.value("grid/cursor_grid"))
	popup.set_item_checked(popup.get_item_index(MenuId.GRID_OFF), mode == Settings.CursorGrid.OFF)
	popup.set_item_checked(popup.get_item_index(MenuId.GRID_WHILE_PLACING),
		mode == Settings.CursorGrid.WHILE_PLACING)
	popup.set_item_checked(popup.get_item_index(MenuId.GRID_ALWAYS),
		mode == Settings.CursorGrid.ALWAYS)
	popup.set_item_checked(popup.get_item_index(MenuId.READOUT),
		bool(Settings.value("viewport/show_cursor_readout")))
	popup.set_item_checked(popup.get_item_index(MenuId.SHOW_MARKERS),
		bool(Settings.value("markers/show")))
	popup.set_item_checked(popup.get_item_index(MenuId.MARKER_LABELS),
		bool(Settings.value("markers/labels")))
	for pair: Array in [[MenuId.WALK_OFF, Walkability.Mode.OFF],
			[MenuId.WALK_PUBLISHED, Walkability.Mode.PUBLISHED],
			[MenuId.WALK_LIVE, Walkability.Mode.LIVE], [MenuId.WALK_CHANGES, Walkability.Mode.CHANGES]]:
		popup.set_item_checked(popup.get_item_index(int(pair[0])), _walk_mode == int(pair[1]))


func _on_menu_id(id: int) -> void:
	match id:
		MenuId.GRID_OFF:
			Settings.set_value("grid/cursor_grid", Settings.CursorGrid.OFF)
		MenuId.GRID_WHILE_PLACING:
			Settings.set_value("grid/cursor_grid", Settings.CursorGrid.WHILE_PLACING)
		MenuId.GRID_ALWAYS:
			Settings.set_value("grid/cursor_grid", Settings.CursorGrid.ALWAYS)
		MenuId.READOUT:
			Settings.set_value("viewport/show_cursor_readout",
				not bool(Settings.value("viewport/show_cursor_readout")))
		MenuId.SHOW_MARKERS:
			Settings.set_value("markers/show", not bool(Settings.value("markers/show")))
			poll_overlays()
		MenuId.MARKER_LABELS:
			Settings.set_value("markers/labels", not bool(Settings.value("markers/labels")))
			poll_overlays()
		MenuId.WALK_OFF:
			set_walkability_mode(Walkability.Mode.OFF)
		MenuId.WALK_PUBLISHED:
			set_walkability_mode(Walkability.Mode.PUBLISHED)
		MenuId.WALK_LIVE:
			set_walkability_mode(Walkability.Mode.LIVE)
		MenuId.WALK_CHANGES:
			set_walkability_mode(Walkability.Mode.CHANGES)
		MenuId.DRAW_ROAD:
			start_path_drawing("road")
		MenuId.DRAW_RIVER:
			start_path_drawing("river")
		MenuId.TIME_OF_DAY:
			_show_time_panel()
		MenuId.CAPTURE_TOP_DOWN:
			_show_capture_dialog()
		_:
			run_tool(id)
	_refresh_hover()


func _refresh_hover() -> void:
	var root := _authoring_root()
	if root == null or _hover_camera == null or not is_instance_valid(_hover_camera) or \
			not _hover_inside:
		_clear_hover()
		return
	var origin := _hover_camera.project_ray_origin(_hover_position)
	var direction := _hover_camera.project_ray_normal(_hover_position)
	_hover_hit = Probe.ray_hit(root, origin, direction, RAY_LENGTH)
	if _hover_hit is Vector3:
		_hover_info = Probe.describe_point(root, _hover_hit as Vector3)
	else:
		_hover_info = {}
	_update_grid(root)
	update_overlays()


func _update_grid(root: Node3D) -> void:
	var mode := int(Settings.value("grid/cursor_grid"))
	var placing := false
	var palette := _palette_plugin()
	if palette != null:
		placing = bool((palette.call("placement_state") as Dictionary).get("armed", false))
	var show := _hover_hit is Vector3 and (mode == Settings.CursorGrid.ALWAYS or
		(mode == Settings.CursorGrid.WHILE_PLACING and placing))
	if not show:
		_grid.hide()
		return
	var snap_on := bool(Settings.value("placement/snap_to_grid"))
	_grid.show_at(root, _hover_hit as Vector3, float(Settings.value("grid/step")),
		int(Settings.value("grid/radius_cells")),
		Color(1.0, 0.86, 0.45, 0.9) if snap_on else Color(0.92, 0.96, 1.0, 0.85),
		snap_on and placing)


func _clear_hover() -> void:
	_hover_hit = null
	_hover_info = {}
	_hover_inside = false
	_grid.hide()
	if is_inside_tree():
		update_overlays()


func _sculpt_plugin() -> Object:
	var base := get_editor_interface().get_base_control()
	if not base.has_meta(SCULPT_PLUGIN_META):
		return null
	var value: Variant = base.get_meta(SCULPT_PLUGIN_META)
	return value if value is Object and is_instance_valid(value) else null


func _palette_plugin() -> Object:
	var base := get_editor_interface().get_base_control()
	if not base.has_meta(ASSET_PLUGIN_META):
		return null
	var value: Variant = base.get_meta(ASSET_PLUGIN_META)
	return value if value is Object and is_instance_valid(value) else null


func _authoring_root() -> Node3D:
	if not is_inside_tree():
		return null
	var root := get_editor_interface().get_edited_scene_root()
	if root is Node3D and root.has_method("authoring_ground_intersection"):
		return root as Node3D
	return null


func _toast(message: String) -> void:
	var toaster := get_editor_interface().get_editor_toaster()
	if toaster != null:
		toaster.push_toast(message)
	else:
		print(message)


func _on_scene_changed(root: Node) -> void:
	_clear_hover()
	_draw.cancel()
	_markers.release()
	var mode := _walk_mode
	_walk.release()
	if mode != Walkability.Mode.OFF:
		set_walkability_mode(mode)
	poll_overlays()
	# The preview follows the open scene; a scene with saved lighting turns it off.
	if _time.is_active() or (_time_toggle != null and _time_toggle.button_pressed):
		set_time_preview(true)


# Time of day ---------------------------------------------------------------

## Turns the lighting preview on or off, optionally at a game minute (0-360,
## noon 180). Returns whether the preview is showing afterwards.
func set_time_preview(enabled: bool, game_minute: float = NAN) -> bool:
	if not is_nan(game_minute):
		Settings.set_value("time_of_day/minute", fposmod(game_minute, 360.0))
	var minute := float(Settings.value("time_of_day/minute"))
	var active := false
	if enabled:
		var root := _authoring_root()
		if _time.is_active() and root != null and _time.nodes().get_parent() == root:
			_time.set_minute(minute)
			active = true
		else:
			active = _time.enable(root, minute)
	else:
		_time.disable()
		_time.last_message = "Preview off: the editor's own lighting is shown."
	_sync_time_controls()
	return active


func time_preview_state() -> Dictionary:
	return {"active": _time.is_active(), "minute": _time.minute(), "nodes": _time.nodes(),
		"manifest": _time.manifest_path, "message": _time.last_message}


func _build_time_controls() -> void:
	_time_button = Button.new()
	_time_button.flat = true
	_time_button.tooltip_text = ("Preview this territory's in-game lighting at any hour. " +
		"Editor only: nothing is saved or baked.")
	_time_button.pressed.connect(_show_time_panel)
	_time_panel = PopupPanel.new()
	var column := VBoxContainer.new()
	column.custom_minimum_size = Vector2(360, 0)
	column.add_theme_constant_override("separation", 6)
	_time_panel.add_child(column)
	_time_toggle = CheckButton.new()
	_time_toggle.text = "Preview time of day"
	_time_toggle.toggled.connect(func(on: bool) -> void: set_time_preview(on))
	column.add_child(_time_toggle)
	var row := HBoxContainer.new()
	_time_slider = HSlider.new()
	_time_slider.min_value = 0.0
	_time_slider.max_value = 359.75
	_time_slider.step = 0.25
	_time_slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_time_slider.value_changed.connect(func(value: float) -> void:
		set_time_preview(_time_toggle.button_pressed or _time.is_active(), value))
	row.add_child(_time_slider)
	_time_label = Label.new()
	_time_label.custom_minimum_size = Vector2(110, 0)
	row.add_child(_time_label)
	column.add_child(row)
	var presets := HBoxContainer.new()
	for preset: String in TimeOfDay.PRESETS:
		var button := Button.new()
		button.text = preset
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.pressed.connect(func() -> void:
			set_time_preview(true, float(TimeOfDay.PRESETS[preset])))
		presets.add_child(button)
	column.add_child(presets)
	_time_status = Label.new()
	_time_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_time_status.custom_minimum_size = Vector2(340, 0)
	column.add_child(_time_status)
	get_editor_interface().get_base_control().add_child(_time_panel)
	_sync_time_controls()


func _show_time_panel() -> void:
	_sync_time_controls()
	var anchor := _time_button.get_screen_position() + Vector2(0.0, _time_button.size.y)
	_time_panel.popup(Rect2i(Vector2i(anchor), Vector2i(360, 0)))


func _sync_time_controls() -> void:
	if _time_button == null:
		return
	var minute := float(Settings.value("time_of_day/minute"))
	var active := _time.is_active()
	_time_button.text = "Time: %s" % TimeOfDay.describe(minute) if active else "Time: editor light"
	_time_toggle.set_pressed_no_signal(active)
	_time_slider.set_value_no_signal(minute)
	_time_label.text = TimeOfDay.describe(minute)
	var source := _time.manifest_path.get_file() if not _time.manifest_path.is_empty() \
		else "a plain clear-day fallback"
	_time_status.text = _time.last_message if not active else \
		"%s\nLighting from %s (%s)." % [_time.last_message,
			_time.manifest_path.get_base_dir().get_file() + "/" + source \
				if not _time.manifest_path.is_empty() else source,
			"same curve as the game's day/night cycle"]


# Top-down capture ----------------------------------------------------------

## Captures the open territory from above; see top_down_capture.gd. While no
## time preview is on, the territory is lit at noon from its manifest for the
## shot and the preview is switched off again afterwards.
func capture_top_down(path: String, pixels_per_metre: float,
		include_references: bool, clip_to_ownership: bool = true) -> Dictionary:
	var root := _authoring_root()
	if root == null:
		return {"error": "Open a map authoring scene first."}
	if _capturing:
		return {"error": "A capture is already running."}
	_capturing = true
	var temporary_light := not _time.is_active() and TimeOfDay.saved_lighting(root).is_empty()
	if temporary_light:
		_time.enable(root, 180.0)
	var label := ("manifest %s" % TimeOfDay.describe(_time.minute())) if _time.is_active() \
		else "scene lighting"
	var result: Dictionary = await TopDown.capture(root, path, pixels_per_metre,
		include_references, label, clip_to_ownership)
	if temporary_light:
		_time.disable()
	_capturing = false
	_sync_time_controls()
	return result


func _build_capture_dialog() -> void:
	_capture_dialog = ConfirmationDialog.new()
	_capture_dialog.title = "Capture top-down image"
	_capture_dialog.ok_button_text = "Capture"
	var column := VBoxContainer.new()
	column.custom_minimum_size = Vector2(460, 0)
	_capture_dialog.add_child(column)
	var path_row := HBoxContainer.new()
	_capture_path = LineEdit.new()
	_capture_path.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	path_row.add_child(_capture_path)
	var browse := Button.new()
	browse.text = "Browse…"
	browse.pressed.connect(func() -> void:
		_capture_file_dialog.current_path = _capture_path.text
		_capture_file_dialog.popup_file_dialog())
	path_row.add_child(browse)
	column.add_child(_labelled("Save PNG to", path_row))
	var options := HBoxContainer.new()
	_capture_ppm = SpinBox.new()
	_capture_ppm.min_value = 0.25
	_capture_ppm.max_value = 8.0
	_capture_ppm.step = 0.25
	_capture_ppm.suffix = "px/m"
	_capture_ppm.value_changed.connect(func(_value: float) -> void: _update_capture_estimate())
	options.add_child(_capture_ppm)
	_capture_references = CheckBox.new()
	_capture_references.text = "Include neighbour references"
	options.add_child(_capture_references)
	column.add_child(_labelled("Resolution", options))
	_capture_clip = CheckBox.new()
	_capture_clip.text = "Only the land this territory owns (clip to its ownership polygon)"
	_capture_clip.toggled.connect(func(_on: bool) -> void: _update_capture_estimate())
	column.add_child(_capture_clip)
	_capture_estimate = Label.new()
	_capture_estimate.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_capture_estimate)
	_capture_dialog.confirmed.connect(_run_capture_from_dialog)
	_capture_file_dialog = EditorFileDialog.new()
	_capture_file_dialog.file_mode = EditorFileDialog.FILE_MODE_SAVE_FILE
	_capture_file_dialog.access = EditorFileDialog.ACCESS_FILESYSTEM
	_capture_file_dialog.filters = PackedStringArray(["*.png ; PNG image"])
	_capture_file_dialog.file_selected.connect(func(chosen: String) -> void:
		_capture_path.text = chosen)
	var base := get_editor_interface().get_base_control()
	base.add_child(_capture_dialog)
	base.add_child(_capture_file_dialog)


func _labelled(text: String, control: Control) -> Control:
	var row := VBoxContainer.new()
	var label := Label.new()
	label.text = text
	row.add_child(label)
	row.add_child(control)
	return row


func _show_capture_dialog() -> void:
	var root := _authoring_root()
	if root == null:
		_toast("Open a map authoring scene first.")
		return
	var region := String(root.get("region_id")) if root.get("region_id") != null \
		else String(root.name).to_snake_case()
	var folder := OS.get_system_dir(OS.SYSTEM_DIR_PICTURES).path_join("Eloria map captures")
	_capture_path.text = folder.path_join("%s-top-down.png" % region)
	_capture_ppm.set_value_no_signal(float(Settings.value("capture/pixels_per_metre")))
	_capture_references.button_pressed = bool(Settings.value("capture/include_references"))
	_capture_clip.set_pressed_no_signal(bool(Settings.value("capture/clip_to_ownership")))
	_update_capture_estimate()
	_capture_dialog.popup_centered()


func _update_capture_estimate() -> void:
	var root := _authoring_root()
	if root == null or _capture_estimate == null:
		return
	var polygon := TopDown.ownership_polygon_local(root) if _capture_clip.button_pressed \
		else PackedVector2Array()
	var framing := TopDown.plan(root, _capture_ppm.value, polygon)
	if framing.has("error"):
		_capture_estimate.text = String(framing.error)
		return
	if _capture_clip.button_pressed and polygon.is_empty():
		_capture_estimate.text = "No ownership polygon for this scene; the whole terrain grid is captured. "
	else:
		_capture_estimate.text = ""
	var rect: Rect2 = framing.rect
	_capture_estimate.text += ("%d × %d px covering %.0f × %.0f m, north up. A JSON sidecar " +
		"records the bounds and metres per pixel. Lighting: %s.") % [framing.size.x,
		framing.size.y, rect.size.x, rect.size.y,
		TimeOfDay.describe(_time.minute()) + " preview" if _time.is_active() \
			else "noon from the territory manifest"]


func _run_capture_from_dialog() -> void:
	Settings.set_value("capture/pixels_per_metre", _capture_ppm.value)
	Settings.set_value("capture/include_references", _capture_references.button_pressed)
	Settings.set_value("capture/clip_to_ownership", _capture_clip.button_pressed)
	var result: Dictionary = await capture_top_down(_capture_path.text, _capture_ppm.value,
		_capture_references.button_pressed, _capture_clip.button_pressed)
	if result.has("error"):
		_toast("Top-down capture failed: %s" % String(result.error))
	else:
		_toast("Saved %s (%d × %d) and its .json sidecar." % [String(result.path),
			result.size.x, result.size.y])


# Markers, walkability and paths --------------------------------------------

## Shows a walkability mode (see walkability_overlay.gd) on the open territory.
func set_walkability_mode(mode: int) -> bool:
	_walk_mode = mode
	var shown := _walk.set_mode(_authoring_root(), mode)
	if mode != Walkability.Mode.OFF and not shown:
		_walk_mode = Walkability.Mode.OFF
	if not _walk.last_message.is_empty() and mode != Walkability.Mode.OFF:
		_status(_walk.last_message)
	update_overlays()
	return shown


func rebuild_walkability() -> void:
	_walk.rebuild()
	update_overlays()


func walkability_state() -> Dictionary:
	return {"mode": _walk_mode, "active": _walk.is_active(), "node": _walk.node(),
		"live": _walk.live_data(), "published": _walk.published_data(),
		"message": _walk.last_message}


func walkability_describe(local: Vector3) -> String:
	return _walk.describe(local)


func marker_overlay_state() -> Dictionary:
	return {"node": _markers.node(), "labels": _markers.label_count()}


## Starts click-to-draw for a "road" or "river"; placement and sculpting stop.
func start_path_drawing(kind: String) -> bool:
	var root := _authoring_root()
	var palette := _palette_plugin()
	if palette != null and palette.has_method("cancel_placement_for_terrain_sculpt"):
		palette.call("cancel_placement_for_terrain_sculpt")
	var sculpt := _sculpt_plugin()
	if sculpt != null and sculpt.has_method("deactivate_terrain_sculpt"):
		sculpt.call("deactivate_terrain_sculpt")
	var started := _draw.start(root, kind)
	_status(_draw.last_message)
	if started:
		get_editor_interface().set_main_screen_editor("3D")
	update_overlays()
	return started


func cancel_path_drawing() -> void:
	if _draw.is_active():
		_draw.cancel()
		update_overlays()


func path_draw_tool() -> RefCounted:
	return _draw


func _select_last_path() -> void:
	var root := _authoring_root()
	if root == null:
		return
	var newest: Node = null
	for container_name in ["Roads", "Rivers"]:
		var container := root.get_node_or_null(container_name)
		if container != null and container.get_child_count() > 0:
			var candidate := container.get_child(container.get_child_count() - 1)
			if String(candidate.name) in _draw.last_message:
				newest = candidate
	if newest == null:
		return
	var selection := get_editor_interface().get_selection()
	selection.clear()
	selection.add_node(newest)
	get_editor_interface().edit_node(newest)


func _status(message: String) -> void:
	var palette := _palette_plugin()
	var dock: Object = palette.get("_dock") if palette != null else null
	if dock != null and dock.has_method("show_message"):
		dock.call("show_message", message)
