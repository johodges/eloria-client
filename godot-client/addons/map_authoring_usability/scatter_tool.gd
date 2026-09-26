@tool
extends RefCounted
## Scatter: paints ordinary asset wrappers of one palette entry along a brush
## stroke. The seed is used only while placing; what is saved is the wrappers
## themselves, exactly as if each had been placed by hand (fresh asset ids,
## the entry's collision role suggestion), so the bake and snapshot see
## nothing new. This is not a foliage runtime (no density map, no LOD).
##
## A stamp is taken where the stroke starts and every brush radius along it.
## Each stamp tries density × area points spread uniformly over the brush disc
## and keeps those at least the minimum spacing from every point already kept
## and from placed copies of the same entry, inside the land the territory
## owns. The stroke is one undo step. The same seed and stroke give the same
## points; each committed stroke moves to the next seed.

const Probe := preload("res://addons/map_authoring_usability/terrain_probe.gd")
const Settings := preload("res://addons/map_authoring_usability/usability_settings.gd")
const Placement := preload("res://addons/map_asset_palette/placement.gd")
const ASSET_SCRIPT := preload("res://src/dev/map_authoring_region/asset_control.gd")
const NODE_NAME := "__MapAuthoringScatterDraft"
const CONTAINER_NAME := "AuthoredAssets"
## Attempts per wanted point before a stamp gives up (spacing rejects some).
const ATTEMPTS := 8
const MAX_PER_STROKE := 400
const COLOR := Color(0.6, 1.0, 0.55)

## radius (m), density (per 100 m²), spacing (m), random_turn (bool),
## size_variation (0-0.5), seed (int).
var options := {}
var entry := {}
var last_message := ""
var strokes := 0
var _root: Node3D
var _polygon := PackedVector2Array()
var _rng := RandomNumberGenerator.new()
var _points := PackedVector2Array()
var _taken := PackedVector2Array()
var _last_stamp := Vector2.INF
var _painting := false
var _hover: Variant = null
var _node: MeshInstance3D
var _mesh: ImmediateMesh


func is_active() -> bool:
	return not entry.is_empty() and _root != null and is_instance_valid(_root)


## Arms the tool for `palette_entry` (an ordinary asset entry).
func start(root: Node3D, palette_entry: Dictionary, tool_options: Dictionary,
		polygon: PackedVector2Array) -> bool:
	cancel()
	if root == null or Probe.region_terrain(root) == null or not root.has_method("prepare_palette_asset"):
		last_message = "Open a territory with region terrain to scatter assets."
		return false
	if palette_entry.is_empty() or bool(palette_entry.get("prefab", false)) or \
			not String(palette_entry.get("marker_kind", "")).is_empty():
		last_message = "Choose an asset in the Map Assets dock first (not a marker or prefab)."
		return false
	if polygon.size() < 3:
		last_message = ("The land this territory owns is not known here; open the territory " +
			"from the Territories dock so its ownership is loaded.")
		return false
	entry = palette_entry.duplicate(true)
	options = tool_options.duplicate()
	_root = root
	_polygon = polygon
	last_message = "Press and drag to scatter %s (seed %d)." % [String(entry.get("label", "")),
		stroke_seed()]
	return true


func cancel() -> void:
	entry = {}
	_painting = false
	_points = PackedVector2Array()
	_taken = PackedVector2Array()
	_hover = null
	if _node != null and is_instance_valid(_node):
		if _node.get_parent() != null:
			_node.get_parent().remove_child(_node)
		_node.queue_free()
	_node = null
	_root = null


func radius() -> float:
	return clampf(float(options.get("radius", 6.0)), 0.5, 64.0)


func spacing() -> float:
	return maxf(float(options.get("spacing", 1.5)), 0.1)


## The seed of the next stroke: the chosen seed, then one more per stroke.
func stroke_seed() -> int:
	return int(options.get("seed", 1)) + strokes


func points() -> PackedVector2Array:
	return _points


func handle_input(camera: Camera3D, event: InputEvent, undo_redo: EditorUndoRedoManager) -> int:
	if not is_active():
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if event is InputEventMouseMotion:
		_hover = _ground_point(camera, (event as InputEventMouseMotion).position)
		if _painting and _hover is Vector3:
			extend_stroke(_local(_hover as Vector3))
		_redraw()
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if event is InputEventKey and event.pressed:
		var key := event as InputEventKey
		if key.keycode == KEY_ESCAPE and not key.echo:
			if _painting:
				_painting = false
				_points = PackedVector2Array()
				last_message = "Stroke discarded; press to start another."
			else:
				cancel()
				last_message = "Stopped scattering."
			_redraw()
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		if Settings.matches("path_narrower", key) or Settings.matches("path_wider", key):
			var factor := 1.05 if key.shift_pressed else 1.25
			options["radius"] = clampf(radius() * (1.0 / factor
				if Settings.matches("path_narrower", key) else factor), 0.5, 64.0)
			_redraw()
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		if Settings.matches("raise", key) or Settings.matches("lower", key):
			var step := 1.0 if key.shift_pressed else 5.0
			options["density"] = clampf(float(options.get("density", 10.0)) + (step
				if Settings.matches("raise", key) else -step), 0.5, 400.0)
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if event is InputEventMouseButton:
		var button := event as InputEventMouseButton
		if button.button_index == MOUSE_BUTTON_RIGHT and button.pressed:
			cancel()
			last_message = "Stopped scattering."
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		if button.button_index != MOUSE_BUTTON_LEFT or button.alt_pressed:
			return EditorPlugin.AFTER_GUI_INPUT_PASS
		var point: Variant = _ground_point(camera, button.position)
		if button.pressed:
			if point == null:
				last_message = "That press missed the terrain."
				return EditorPlugin.AFTER_GUI_INPUT_STOP
			begin_stroke(_local(point as Vector3))
			_redraw()
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		if _painting:
			if point is Vector3:
				extend_stroke(_local(point as Vector3))
			commit(undo_redo)
			_redraw()
			return EditorPlugin.AFTER_GUI_INPUT_STOP
	return EditorPlugin.AFTER_GUI_INPUT_PASS


## Starts a stroke at territory-local `start`: seeds the generator and stamps.
func begin_stroke(start: Vector3) -> void:
	_painting = true
	_points = PackedVector2Array()
	_rng.seed = hash([stroke_seed(), String(entry.get("id", ""))])
	_taken = existing_points(_root, String(entry.get("id", "")))
	_last_stamp = Vector2(start.x, start.z)
	_stamp(_last_stamp)


## Adds a stamp every brush radius along the way to territory-local `to`.
func extend_stroke(to: Vector3) -> void:
	if not _painting:
		return
	var target := Vector2(to.x, to.z)
	var step := radius()
	var offset := target - _last_stamp
	var count := floori(offset.length() / step)
	for index in count:
		_last_stamp += offset.normalized() * step
		_stamp(_last_stamp)


func _stamp(centre: Vector2) -> void:
	if _points.size() >= MAX_PER_STROKE:
		return
	var found := stamp_points(_rng, centre, radius(), float(options.get("density", 10.0)),
		spacing(), _taken, _polygon)
	for point in found:
		if _points.size() >= MAX_PER_STROKE:
			break
		_points.append(point)
		_taken.append(point)


## Points for one stamp: density (per 100 m²) × disc area of them wanted, each
## drawn uniformly over the disc and kept when at least `min_spacing` from every
## point in `taken` (and from each other) and inside `polygon`.
static func stamp_points(rng: RandomNumberGenerator, centre: Vector2, disc_radius: float,
		density: float, min_spacing: float, taken: PackedVector2Array,
		polygon: PackedVector2Array) -> PackedVector2Array:
	var wanted := roundi(density * PI * disc_radius * disc_radius / 100.0)
	var result := PackedVector2Array()
	var nearby := PackedVector2Array()
	for point in taken:
		if point.distance_to(centre) <= disc_radius + min_spacing:
			nearby.append(point)
	for _attempt in wanted * ATTEMPTS:
		if result.size() >= wanted:
			break
		var angle := rng.randf() * TAU
		var distance := sqrt(rng.randf()) * disc_radius
		var candidate := centre + Vector2(cos(angle), sin(angle)) * distance
		var clear := polygon.size() < 3 or Geometry2D.is_point_in_polygon(candidate, polygon)
		for other in nearby:
			if not clear:
				break
			clear = other.distance_to(candidate) >= min_spacing
		if clear:
			result.append(candidate)
			nearby.append(candidate)
	return result


## X/Z of placed copies of `entry_id` (so a second stroke does not stack).
static func existing_points(root: Node3D, entry_id: String) -> PackedVector2Array:
	var result := PackedVector2Array()
	var container := root.get_node_or_null(CONTAINER_NAME) if root != null else null
	if container == null:
		return result
	var inverse := root.global_transform.affine_inverse()
	for child in container.get_children():
		if child.get_script() == ASSET_SCRIPT and String(child.get("catalog_asset_id")) == entry_id:
			var local: Vector3 = inverse * (child as Node3D).global_position
			result.append(Vector2(local.x, local.z))
	return result


## Places a wrapper at every point of the stroke, as one undo step.
func commit(undo_redo: EditorUndoRedoManager) -> Array[Node3D]:
	var placed: Array[Node3D] = []
	var stroke := _points
	_painting = false
	_points = PackedVector2Array()
	if stroke.is_empty():
		last_message = "Nothing scattered: the brush found no room (spacing, owned land)."
		return placed
	var container := _root.get_node_or_null(CONTAINER_NAME) as Node3D
	var new_container := container == null
	if new_container:
		container = Node3D.new()
		container.name = CONTAINER_NAME
	var used := {}
	if not new_container:
		for child in container.get_children():
			if child.get_script() == ASSET_SCRIPT:
				used[String(child.get("asset_id"))] = true
	# The look of each copy comes from the same seeded generator as its spot.
	var looks := RandomNumberGenerator.new()
	looks.seed = hash([stroke_seed(), "looks"])
	var variation := clampf(float(options.get("size_variation", 0.0)), 0.0, 0.5)
	var transforms: Array[Transform3D] = []
	for point in stroke:
		var created := Placement.instantiate_entry(entry)
		var content := created.get("node") as Node3D
		if content == null:
			continue
		var wrapper := _root.call("prepare_palette_asset", entry, content) as Node3D
		if wrapper == null:
			content.free()
			continue
		var identity := fresh_asset_id(String(wrapper.get("asset_id")), used)
		used[identity] = true
		wrapper.set("asset_id", identity)
		wrapper.set("node_name", "Authored_%s" % identity.replace(":", "_").replace("-", "_"))
		var yaw := looks.randf() * 360.0 if bool(options.get("random_turn", true)) else 0.0
		var size := 1.0 + looks.randf_range(-variation, variation)
		var world := _root.global_transform * Vector3(point.x, 0.0, point.y)
		var height := Probe.height_at(_root, world)
		if is_nan(height):
			wrapper.free()
			continue
		transforms.append(Placement.adjusted_ground_transform(wrapper, entry,
			Vector3(world.x, height, world.z), yaw, 0.0, size))
		placed.append(wrapper)
	if placed.is_empty():
		last_message = "Nothing scattered: the asset could not be loaded."
		return placed
	undo_redo.create_action("Scatter %d %s" % [placed.size(), String(entry.get("label", ""))],
		UndoRedo.MERGE_DISABLE, _root)
	if new_container:
		undo_redo.add_do_method(_root, &"add_child", container, true)
		undo_redo.add_do_method(container, &"set_owner", _root)
		undo_redo.add_do_reference(container)
	for index in placed.size():
		var wrapper := placed[index]
		undo_redo.add_do_method(container, &"add_child", wrapper, true)
		undo_redo.add_do_method(wrapper, &"set_owner", _root)
		for child in wrapper.get_children():
			undo_redo.add_do_method(child, &"set_owner", _root)
		undo_redo.add_do_property(wrapper, &"global_transform", transforms[index])
		undo_redo.add_do_reference(wrapper)
	for index in range(placed.size() - 1, -1, -1):
		undo_redo.add_undo_method(container, &"remove_child", placed[index])
	if new_container:
		undo_redo.add_undo_method(_root, &"remove_child", container)
	undo_redo.commit_action()
	last_message = "Scattered %d %s (seed %d). One undo step removes them." % [placed.size(),
		String(entry.get("label", "")), stroke_seed()]
	strokes += 1
	return placed


## `base` with its -NNN counter moved past every id in `used`.
static func fresh_asset_id(base: String, used: Dictionary) -> String:
	if not used.has(base):
		return base
	var stem := base
	var separator := base.rfind("-")
	if separator > 0 and base.substr(separator + 1).is_valid_int():
		stem = base.substr(0, separator)
	var index := 1
	var candidate := "%s-%03d" % [stem, index]
	while used.has(candidate):
		index += 1
		candidate = "%s-%03d" % [stem, index]
	return candidate


func hint_lines() -> PackedStringArray:
	if not is_active():
		return PackedStringArray()
	return PackedStringArray([
		"Scatter %s  ·  radius %.1f m  ·  %.0f per 100 m²  ·  spacing %.1f m  ·  seed %d%s" % [
			String(entry.get("label", "")), radius(), float(options.get("density", 10.0)), spacing(),
			stroke_seed(), "  ·  %d in this stroke" % _points.size() if _painting else ""],
		last_message,
		"Press and drag to paint  ·  %s/%s: radius  ·  PgUp/PgDn: density  ·  Esc: discard  ·  right-click: stop" % [
			Settings.shortcut_text("path_narrower"), Settings.shortcut_text("path_wider")]])


func _local(world: Vector3) -> Vector3:
	return _root.global_transform.affine_inverse() * world


func _ground_point(camera: Camera3D, screen: Vector2) -> Variant:
	var hit: Variant = Probe.ray_hit(_root, camera.project_ray_origin(screen),
		camera.project_ray_normal(screen), 4096.0)
	return hit if hit is Vector3 else null


func _redraw() -> void:
	if not is_active():
		return
	if _node == null or not is_instance_valid(_node):
		_mesh = ImmediateMesh.new()
		_node = MeshInstance3D.new()
		_node.name = NODE_NAME
		_node.mesh = _mesh
		_node.top_level = true
		_node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var material := StandardMaterial3D.new()
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.vertex_color_use_as_albedo = true
		material.no_depth_test = true
		_node.material_override = material
		_root.add_child(_node, false, Node.INTERNAL_MODE_BACK)
		_node.global_transform = _root.global_transform
	_mesh.clear_surfaces()
	var lines := PackedVector3Array()
	if _hover is Vector3:
		var centre := _local(_hover as Vector3)
		for index in 40:
			var a := TAU * float(index) / 40.0
			var b := TAU * float(index + 1) / 40.0
			lines.append(_draped(Vector2(centre.x, centre.z) + Vector2(cos(a), sin(a)) * radius()))
			lines.append(_draped(Vector2(centre.x, centre.z) + Vector2(cos(b), sin(b)) * radius()))
	for point in _points:
		lines.append(_draped(point + Vector2(-0.3, 0.0)))
		lines.append(_draped(point + Vector2(0.3, 0.0)))
		lines.append(_draped(point + Vector2(0.0, -0.3)))
		lines.append(_draped(point + Vector2(0.0, 0.3)))
	if lines.is_empty():
		return
	_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
	for vertex in lines:
		_mesh.surface_set_color(COLOR)
		_mesh.surface_add_vertex(vertex)
	_mesh.surface_end()


func _draped(point: Vector2) -> Vector3:
	var world := _root.global_transform * Vector3(point.x, 0.0, point.y)
	var height := Probe.height_at(_root, world)
	return _local(Vector3(world.x, height if not is_nan(height) else world.y, world.z)) + 		Vector3(0.0, 0.2, 0.0)
