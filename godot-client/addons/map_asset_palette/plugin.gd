@tool
extends EditorPlugin

const Dock := preload("res://addons/map_asset_palette/map_asset_dock.gd")
const Placement := preload("res://addons/map_asset_palette/placement.gd")
const RAY_LENGTH := 2048.0
const SCULPT_PLUGIN_META := &"map_authoring_sculpt_plugin"
const ASSET_PLUGIN_META := &"map_asset_palette_plugin"

var _dock: EditorDock
var _pending_entry: Dictionary = {}
var _edited_root: Node


func _enter_tree() -> void:
	get_editor_interface().get_base_control().set_meta(ASSET_PLUGIN_META, self)
	_dock = Dock.new()
	_dock.configure(get_editor_interface())
	_dock.place_requested.connect(_arm_placement)
	_dock.add_at_center_requested.connect(_add_at_view_center)
	_dock.placement_cancel_requested.connect(_cancel_placement)
	add_dock(_dock)
	set_input_event_forwarding_always_enabled()
	scene_changed.connect(_on_scene_changed)
	_on_scene_changed(get_editor_interface().get_edited_scene_root())


func _exit_tree() -> void:
	_pending_entry.clear()
	var base := get_editor_interface().get_base_control()
	if base.get_meta(ASSET_PLUGIN_META, null) == self:
		base.remove_meta(ASSET_PLUGIN_META)
	if _dock != null:
		remove_dock(_dock)
		_dock.queue_free()
		_dock = null


func _handles(_object: Object) -> bool:
	return _pilot_root() != null


func _forward_3d_gui_input(camera: Camera3D, event: InputEvent) -> int:
	if _pending_entry.is_empty() or _pilot_root() == null:
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if event is InputEventKey and event.pressed and not event.echo and \
			event.keycode == KEY_ESCAPE:
		_cancel_placement()
		return EditorPlugin.AFTER_GUI_INPUT_STOP
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_RIGHT:
			_cancel_placement()
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.alt_pressed:
				return EditorPlugin.AFTER_GUI_INPUT_PASS
			var hit := _terrain_hit(camera, event.position)
			if hit != null:
				var entry := _pending_entry.duplicate(true)
				_cancel_placement()
				_place_entry(entry, hit as Vector3)
			else:
				_dock.show_message("That ray did not hit the authored terrain. Choose another point.")
			return EditorPlugin.AFTER_GUI_INPUT_STOP
	return EditorPlugin.AFTER_GUI_INPUT_PASS


func _arm_placement(entry: Dictionary) -> void:
	if _pilot_root() == null:
		_dock.show_message("Open a map authoring scene before placing assets.")
		return
	var sculpt_plugin: Variant = get_editor_interface().get_base_control().get_meta(
		SCULPT_PLUGIN_META, null)
	if sculpt_plugin is Object and is_instance_valid(sculpt_plugin) and \
			sculpt_plugin.has_method("deactivate_terrain_sculpt"):
		sculpt_plugin.call("deactivate_terrain_sculpt")
	_pending_entry = entry.duplicate(true)
	_dock.set_placement_armed(true, String(entry.label))
	get_editor_interface().set_main_screen_editor("3D")


func _cancel_placement() -> void:
	_pending_entry.clear()
	if _dock != null:
		_dock.set_placement_armed(false)


func cancel_placement_for_terrain_sculpt() -> void:
	_cancel_placement()


func _add_at_view_center(entry: Dictionary) -> void:
	_cancel_placement()
	var viewport := get_editor_interface().get_editor_viewport_3d(0)
	var camera := viewport.get_camera_3d() if viewport != null else null
	if camera == null:
		_dock.show_message("Open the 3D view before adding an asset at its center.")
		return
	var hit := _terrain_hit(camera, viewport.get_visible_rect().size * 0.5)
	if hit == null:
		_dock.show_message("The center of the 3D view does not hit the authored terrain.")
		return
	_place_entry(entry, hit as Vector3)


func _terrain_hit(camera: Camera3D, screen_position: Vector2) -> Variant:
	var pilot := _pilot_root()
	if pilot == null:
		return null
	var origin := camera.project_ray_origin(screen_position)
	var direction := camera.project_ray_normal(screen_position)
	return pilot.call("authoring_ground_intersection", origin, direction, RAY_LENGTH)


func _place_entry(entry: Dictionary, ground_position: Vector3) -> Node3D:
	var pilot := _pilot_root()
	if pilot == null:
		return null
	var created := Placement.instantiate_entry(entry)
	var node := created.get("node") as Node3D
	if node == null:
		_dock.show_message(String(created.get("error", "The selected asset could not be loaded.")))
		return null
	if pilot.has_method("prepare_palette_asset"):
		node = pilot.call("prepare_palette_asset", entry, node) as Node3D
		if node == null:
			_dock.show_message("The authoring region could not prepare this asset.")
			return null
	var transform := Placement.ground_transform(node, entry, ground_position)
	var placed := Placement.commit_with_undo(get_undo_redo(), pilot, entry, node,
		bool(created.get("starter", false)), transform)
	if placed == null:
		node.free()
		_dock.show_message("Could not create the saved AuthoredAssets container.")
		return null
	var selection := get_editor_interface().get_selection()
	selection.clear()
	selection.add_node(placed)
	get_editor_interface().edit_node(placed)
	get_editor_interface().set_main_screen_editor("3D")
	_dock.show_message("Placed %s. Use the normal move, rotate, and scale tools." %
		String(entry.label))
	return placed


func _on_scene_changed(scene_root: Node) -> void:
	_edited_root = scene_root
	_cancel_placement()
	if _dock != null:
		_dock.set_scene_available(_pilot_root() != null)


func _pilot_root() -> Node3D:
	var root := get_editor_interface().get_edited_scene_root() if is_inside_tree() else _edited_root
	if root is Node3D and root.has_method("authoring_ground_intersection"):
		return root as Node3D
	return null
