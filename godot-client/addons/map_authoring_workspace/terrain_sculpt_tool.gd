@tool
class_name MapAuthoringTerrainSculptTool
extends RefCounted

signal status_changed(message: String)
signal flatten_height_picked(height: float)
signal stroke_started
signal stroke_ended

const BRUSH := preload("res://src/dev/map_authoring_region/terrain_sculpt_brush.gd")
const OWNERSHIP := preload("res://src/dev/map_authoring_region/ownership_source.gd")
const PREVIEW_INTERVAL := 0.14
const RING_SEGMENTS := 48

var _root: Node3D
var _terrain: MapAuthoringTerrainControl
var _undo_redo: Object
var _entry: Dictionary = {}
var _base := PackedFloat32Array()
var _base_sha := ""
var _locked := PackedByteArray()
var _boundary_weights := PackedFloat32Array()
var _ring: MeshInstance3D
var _ring_mesh: ImmediateMesh
var _ring_material: StandardMaterial3D
var _enabled := false
var _picking_height := false
var _dragging := false
var _changed := false
var _preview_dirty := false
var _before: Resource
var _pending: Resource
var _last_sample := Vector2.INF
var _preview_elapsed := 0.0
var _settings := {}
var _hover_reason := ""


func bind(root: Node3D, terrain: MapAuthoringTerrainControl,
		entry: Dictionary, undo_redo: Object) -> bool:
	unbind()
	if root == null or terrain == null or undo_redo == null or \
			not entry.get("ownership_polygon") is PackedVector2Array:
		return false
	if not OWNERSHIP.entry_error(root, entry).is_empty():
		return false
	_root = root
	_terrain = terrain
	_entry = entry.duplicate(true)
	_undo_redo = undo_redo
	_base = _terrain.base_heights()
	_base_sha = _terrain.base_sha256()
	var fields := boundary_fields(_entry.ownership_polygon,
		_entry.translation, _terrain.origin, _terrain.grid_size,
		_terrain.cell_metres, _root.global_transform.affine_inverse() *
		_terrain.global_transform)
	_locked = fields.locked
	_boundary_weights = fields.weights
	if _locked.size() != _base.size() or _base.is_empty():
		unbind()
		return false
	_ring_mesh = ImmediateMesh.new()
	_ring = MeshInstance3D.new()
	_ring.name = "__TerrainSculptCursor"
	_ring.mesh = _ring_mesh
	_ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_ring_material = StandardMaterial3D.new()
	_ring_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_ring_material.no_depth_test = true
	_ring_material.albedo_color = Color(0.22, 0.94, 0.79)
	_ring.material_override = _ring_material
	_ring.visible = false
	_terrain.add_child(_ring, false, Node.INTERNAL_MODE_FRONT)
	return true


func unbind() -> void:
	cancel_stroke()
	_enabled = false
	_picking_height = false
	if is_instance_valid(_ring):
		_ring.queue_free()
	_ring = null
	_ring_mesh = null
	_ring_material = null
	_root = null
	_terrain = null
	_undo_redo = null
	_entry.clear()
	_base.clear()
	_base_sha = ""
	_locked.clear()
	_boundary_weights.clear()
	_hover_reason = ""


func set_enabled(enabled: bool) -> void:
	if not enabled:
		cancel_stroke()
		_picking_height = false
		if is_instance_valid(_ring):
			_ring.visible = false
	_enabled = enabled and _terrain != null
	if _enabled:
		status_changed.emit("Drag on the active terrain. Borders protected; Alt/RMB/MMB navigate.")
	else:
		_hover_reason = ""


func is_enabled() -> bool:
	return _enabled


func is_dragging() -> bool:
	return _dragging


func pick_flatten_height() -> void:
	if _enabled:
		_picking_height = true
		status_changed.emit("Click editable terrain to sample the flatten target.")


func tick(delta: float) -> void:
	if not _dragging or not is_instance_valid(_terrain):
		return
	# The viewport may miss a mouse release outside its bounds.
	if not Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		finish_stroke()
		return
	if not _preview_dirty:
		return
	_preview_elapsed += delta
	if _preview_elapsed >= PREVIEW_INTERVAL:
		if _terrain.apply_sculpt_layer(_pending):
			_preview_dirty = false
		_preview_elapsed = 0.0


func handle_input(camera: Camera3D, event: InputEvent,
		settings: Dictionary) -> int:
	if not _enabled or not is_instance_valid(_terrain) or camera == null:
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if event is InputEventKey and event.pressed and not event.echo and \
			event.ctrl_pressed and event.keycode in [KEY_S, KEY_Z, KEY_Y]:
		if _dragging:
			finish_stroke()
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if event is InputEventKey and event.pressed and not event.echo and \
			event.keycode == KEY_ESCAPE:
		if _dragging:
			cancel_stroke()
		elif _picking_height:
			_picking_height = false
		else:
			return EditorPlugin.AFTER_GUI_INPUT_PASS
		return EditorPlugin.AFTER_GUI_INPUT_STOP
	if event is InputEventMouseMotion:
		if event.alt_pressed or (_dragging and \
			(event.button_mask & MOUSE_BUTTON_MASK_LEFT) == 0):
			if _dragging:
				finish_stroke()
			return EditorPlugin.AFTER_GUI_INPUT_PASS
		var active_settings: Dictionary = _settings if _dragging else settings
		var hover := _hover(camera, event.position,
			float(active_settings.get("radius", 8.0)))
		if _dragging:
			if hover.ok:
				_sample_drag(hover.hit, _settings)
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		var reason := "" if hover.ok else String(hover.reason)
		if reason != _hover_reason:
			_hover_reason = reason
			status_changed.emit(reason if not reason.is_empty() else
				"Ready to sculpt the active terrain. Borders protected.")
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if event is InputEventMouseButton:
		if event.button_index in [MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE]:
			if event.pressed and _dragging:
				finish_stroke()
			return EditorPlugin.AFTER_GUI_INPUT_PASS
		if event.button_index != MOUSE_BUTTON_LEFT or event.alt_pressed:
			if event.alt_pressed and _dragging:
				finish_stroke()
			return EditorPlugin.AFTER_GUI_INPUT_PASS
		if not event.pressed:
			if _dragging:
				finish_stroke()
				return EditorPlugin.AFTER_GUI_INPUT_STOP
			return EditorPlugin.AFTER_GUI_INPUT_PASS
		var hover := _hover(camera, event.position, float(settings.get("radius", 8.0)))
		if not hover.ok:
			status_changed.emit(String(hover.reason))
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		if _picking_height:
			_picking_height = false
			flatten_height_picked.emit(_terrain.to_local(hover.hit).y)
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		_start_stroke(hover.hit, settings)
		return EditorPlugin.AFTER_GUI_INPUT_STOP
	return EditorPlugin.AFTER_GUI_INPUT_PASS


func _start_stroke(hit: Vector3, settings: Dictionary) -> void:
	_before = _terrain.sculpt_layer
	_pending = _before
	_settings = settings.duplicate(true)
	_last_sample = Vector2.INF
	_changed = false
	_preview_dirty = false
	_preview_elapsed = 0.0
	_dragging = true
	stroke_started.emit()
	_sample_drag(hit, _settings)


func _sample_drag(hit: Vector3, settings: Dictionary) -> void:
	var local := _terrain.to_local(hit)
	var at := Vector2(local.x, local.z)
	var spacing := maxf(_terrain.cell_metres * 0.5,
		float(settings.get("radius", 8.0)) * 0.18)
	if _last_sample.is_finite() and at.distance_to(_last_sample) < spacing:
		return
	var start := _last_sample if _last_sample.is_finite() else at
	var count := clampi(ceili(start.distance_to(at) / spacing), 1, 32)
	for step in range(1, count + 1):
		var point := start.lerp(at, float(step) / float(count))
		var candidate: Resource = BRUSH.apply_stamp(_base, _pending,
			_base_sha, _terrain.origin, _terrain.grid_size,
			_terrain.cell_metres, point, int(settings.get("mode", 0)),
			float(settings.get("radius", 8.0)),
			float(settings.get("strength", 0.35)),
			float(settings.get("softness", 0.65)),
			float(settings.get("flatten_target", NAN)), _locked,
			_boundary_weights)
		if candidate != null:
			_pending = candidate
			_changed = true
			_preview_dirty = true
	_last_sample = at


func finish_stroke() -> void:
	if not _dragging:
		return
	_dragging = false
	if _changed and is_instance_valid(_terrain) and is_instance_valid(_root):
		if _preview_dirty and not _terrain.apply_sculpt_layer(_pending):
			_terrain.apply_sculpt_layer(_before)
			_clear_stroke()
			stroke_ended.emit()
			status_changed.emit("Terrain preview could not be applied; stroke cancelled.")
			return
		if _undo_redo is EditorUndoRedoManager:
			_undo_redo.create_action("Sculpt terrain", UndoRedo.MERGE_DISABLE,
				_root)
		else:
			_undo_redo.create_action("Sculpt terrain", UndoRedo.MERGE_DISABLE)
		_undo_redo.add_do_method(_terrain, &"apply_sculpt_layer", _pending)
		_undo_redo.add_undo_method(_terrain, &"apply_sculpt_layer", _before)
		# The pending preview is already current; a second do would rebuild it.
		_undo_redo.commit_action(false)
		status_changed.emit("Terrain sculpt saved in this scene's undo history. Ctrl+S saves it.")
	else:
		status_changed.emit("No editable terrain sample changed.")
	_clear_stroke()
	stroke_ended.emit()


func cancel_stroke() -> void:
	if not _dragging:
		return
	if _changed and is_instance_valid(_terrain):
		_terrain.apply_sculpt_layer(_before)
	_clear_stroke()
	stroke_ended.emit()
	status_changed.emit("Terrain stroke cancelled; no undo step was added.")


func _clear_stroke() -> void:
	_dragging = false
	_changed = false
	_preview_dirty = false
	_before = null
	_pending = null
	_last_sample = Vector2.INF
	_settings.clear()
	_preview_elapsed = 0.0


func _hover(camera: Camera3D, position: Vector2, radius: float) -> Dictionary:
	var hit: Variant = _terrain.terrain_hit_world(
		camera.project_ray_origin(position), camera.project_ray_normal(position))
	if not hit is Vector3:
		_ring.visible = false
		return {"ok": false, "reason": "Brush ray missed the active terrain."}
	var local: Vector3 = _terrain.to_local(hit)
	var x := roundi((local.x - _terrain.origin.x) / _terrain.cell_metres)
	var z := roundi((local.z - _terrain.origin.y) / _terrain.cell_metres)
	if x < 0 or z < 0 or x >= _terrain.grid_size.x or z >= _terrain.grid_size.y:
		_ring.visible = false
		return {"ok": false, "reason": "Outside the active terrain grid."}
	var index := z * _terrain.grid_size.x + x
	if _locked[index] != 0 or _boundary_weights[index] <= 0.0:
		_ring.visible = false
		return {"ok": false, "reason": "Borders protected: move the brush inside the editable area."}
	_draw_ring(local, radius)
	return {"ok": true, "hit": hit}


func _draw_ring(local: Vector3, radius: float) -> void:
	_ring_mesh.clear_surfaces()
	_ring_mesh.surface_begin(Mesh.PRIMITIVE_LINE_STRIP)
	for index in range(RING_SEGMENTS + 1):
		var angle := TAU * float(index) / float(RING_SEGMENTS)
		var x := local.x + cos(angle) * radius
		var z := local.z + sin(angle) * radius
		var y := _terrain.height_at_local(x, z)
		_ring_mesh.surface_add_vertex(Vector3(x,
			y + 0.15 if is_finite(y) else local.y + 0.15, z))
	_ring_mesh.surface_end()
	_ring.visible = true


static func boundary_fields(polygon: PackedVector2Array,
		translation: Vector3, origin: Vector2, grid: Vector2i,
		cell: float, terrain_to_root := Transform3D.IDENTITY) -> Dictionary:
	var locked := PackedByteArray()
	var weights := PackedFloat32Array()
	if polygon.size() < 3 or grid.x < 2 or grid.y < 2 or cell <= 0.0:
		return {"locked": locked, "weights": weights}
	locked.resize(grid.x * grid.y)
	weights.resize(locked.size())
	var hard := 2.0 * cell
	var fade := 2.0 * cell
	for z in grid.y:
		for x in grid.x:
			var index := z * grid.x + x
			if x < 2 or z < 2 or x >= grid.x - 2 or z >= grid.y - 2:
				locked[index] = 1
				continue
			var local := Vector3(origin.x + float(x) * cell, 0.0,
				origin.y + float(z) * cell)
			var root_point: Vector3 = terrain_to_root * local
			var point := Vector2(root_point.x + translation.x,
				root_point.z + translation.z)
			if not Geometry2D.is_point_in_polygon(point, polygon):
				locked[index] = 1
				continue
			var distance := INF
			for edge in polygon.size():
				var first: Vector2 = polygon[edge]
				var second: Vector2 = polygon[(edge + 1) % polygon.size()]
				var segment := second - first
				var t := clampf((point - first).dot(segment) /
					maxf(segment.length_squared(), 0.000001), 0.0, 1.0)
				distance = minf(distance, point.distance_to(first + segment * t))
			if distance <= hard:
				locked[index] = 1
				continue
			var amount := clampf((distance - hard) / fade, 0.0, 1.0)
			weights[index] = amount * amount * (3.0 - 2.0 * amount)
	return {"locked": locked, "weights": weights}
