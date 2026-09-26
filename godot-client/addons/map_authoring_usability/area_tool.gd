@tool
extends RefCounted
## Drag-to-size tools that create ordinary authored controls, one undo step each:
## - "ground": a ground region (Ground/Regions/<id>, the same control the
##   territories already use) with a chosen surface, shape, feather (blend
##   width), opacity and priority. It must stay inside the land the territory
##   owns, and a territory holds at most 127 because the terrain preview draws
##   no more.
## - "plateau": a terrain patch (Terrain/Patches/<id>). Set levels the ground to
##   a height above the clicked point, Add raises or lowers it by a delta. Every
##   terrain sample it touches must be editable ground clear of the protected
##   border band the sculpt brush also respects; the patch schema itself does not
##   enforce that. A plateau does not make ground walkable: the 0.65 grade,
##   water and structure rules still apply when it is baked.
## Press where the centre goes, drag out the size, release to create. The tool
## stays armed for the next one; Esc or right-click stops.

const Probe := preload("res://addons/map_authoring_usability/terrain_probe.gd")
const Settings := preload("res://addons/map_authoring_usability/usability_settings.gd")
const GROUND_SCRIPT := preload("res://src/dev/map_authoring_region/ground_region_control.gd")
const PATCH_SCRIPT := preload("res://src/dev/map_authoring_region/terrain_patch.gd")
const NODE_NAME := "__MapAuthoringAreaDraft"
const MAX_GROUND_REGIONS := 127
const MIN_SIZE := 1.0
const PROTECTED_WEIGHT := 0.999
const COLORS := {"ground": Color(0.55, 0.9, 0.45), "plateau": Color(0.95, 0.7, 0.35)}

var kind := ""
## ground: surface (Resource) or preset (String), shape, blend_width, opacity,
## priority. plateau: operation ("set" or "add"), shape, feather, height.
var options := {}
var last_message := ""
var _root: Node3D
var _polygon := PackedVector2Array()
var _protection: Dictionary = {}
var _anchor := Vector3.INF
var _hover: Variant = null
var _node: MeshInstance3D
var _mesh: ImmediateMesh


func is_active() -> bool:
	return not kind.is_empty() and _root != null and is_instance_valid(_root)


## Starts a "ground" or "plateau" tool. `polygon` is the owned land in
## territory-local X/Z; `protection` is the sculpt tool's protection_fields().
func start(root: Node3D, tool_kind: String, tool_options: Dictionary,
		polygon: PackedVector2Array, protection: Dictionary) -> bool:
	cancel()
	if root == null or Probe.region_terrain(root) == null:
		last_message = "Open a territory with region terrain first."
		return false
	if tool_kind == "ground" and polygon.size() < 3:
		last_message = ("The land this territory owns is not known here; open the territory " +
			"from the Territories dock so its ownership is loaded.")
		return false
	if tool_kind == "plateau" and protection.is_empty():
		last_message = ("Border protection is not loaded; open the territory from the " +
			"Territories dock (or Refresh sources) before stamping terrain.")
		return false
	kind = tool_kind
	options = tool_options.duplicate()
	_root = root
	_polygon = polygon
	_protection = protection
	last_message = "Press where the %s's centre goes and drag out its size." % (
		"ground region" if kind == "ground" else "plateau")
	_redraw()
	return true


func cancel() -> void:
	kind = ""
	_anchor = Vector3.INF
	_hover = null
	if _node != null and is_instance_valid(_node):
		if _node.get_parent() != null:
			_node.get_parent().remove_child(_node)
		_node.queue_free()
	_node = null
	_root = null


## Input while the tool is active. Returns an EditorPlugin.AFTER_GUI_INPUT_* value.
func handle_input(camera: Camera3D, event: InputEvent, undo_redo: EditorUndoRedoManager) -> int:
	if not is_active():
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if event is InputEventMouseMotion:
		_hover = _ground_point(camera, (event as InputEventMouseMotion).position)
		_redraw()
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if event is InputEventKey and event.pressed:
		var key := event as InputEventKey
		if key.keycode == KEY_ESCAPE and not key.echo:
			if _anchor.is_finite():
				_anchor = Vector3.INF
				last_message = "Draft discarded; press to start another."
			else:
				var drawn := kind
				cancel()
				last_message = "Stopped drawing %s." % ("ground regions" if drawn == "ground" else "plateaus")
			_redraw()
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		if Settings.matches("path_narrower", key) or Settings.matches("path_wider", key):
			var field := "blend_width" if kind == "ground" else "feather"
			var factor := 1.05 if key.shift_pressed else 1.25
			options[field] = clampf(float(options.get(field, 3.0)) *
				(1.0 / factor if Settings.matches("path_narrower", key) else factor), 0.0, 64.0)
			_redraw()
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		if kind == "plateau" and (Settings.matches("raise", key) or Settings.matches("lower", key)):
			var step := 0.1 if key.shift_pressed else 0.5
			options["height"] = float(options.get("height", 0.0)) + (step
				if Settings.matches("raise", key) else -step)
			_redraw()
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		return EditorPlugin.AFTER_GUI_INPUT_PASS
	if event is InputEventMouseButton:
		var button := event as InputEventMouseButton
		if button.button_index == MOUSE_BUTTON_RIGHT and button.pressed:
			var drawn := kind
			cancel()
			last_message = "Stopped drawing %s." % ("ground regions" if drawn == "ground" else "plateaus")
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		if button.button_index != MOUSE_BUTTON_LEFT or button.alt_pressed:
			return EditorPlugin.AFTER_GUI_INPUT_PASS
		var point: Variant = _ground_point(camera, button.position)
		if button.pressed:
			if point == null:
				last_message = "That press missed the terrain."
				return EditorPlugin.AFTER_GUI_INPUT_STOP
			_anchor = point as Vector3
			_hover = point
			_redraw()
			return EditorPlugin.AFTER_GUI_INPUT_STOP
		if _anchor.is_finite():
			var corner: Vector3 = point as Vector3 if point is Vector3 else _hover as Vector3 \
				if _hover is Vector3 else _anchor
			create(undo_redo, _anchor, corner)
			_anchor = Vector3.INF
			_redraw()
			return EditorPlugin.AFTER_GUI_INPUT_STOP
	return EditorPlugin.AFTER_GUI_INPUT_PASS


## Creates the control from a centre and a dragged corner (world points).
## Returns the new node, or null with last_message saying why.
func create(undo_redo: EditorUndoRedoManager, centre_world: Vector3,
		corner_world: Vector3) -> Node3D:
	var inverse := _root.global_transform.affine_inverse()
	var centre: Vector3 = inverse * centre_world
	var corner: Vector3 = inverse * corner_world
	var size := Vector2(maxf(absf(corner.x - centre.x) * 2.0, MIN_SIZE),
		maxf(absf(corner.z - centre.z) * 2.0, MIN_SIZE))
	return commit_ground(undo_redo, centre, size) if kind == "ground" \
		else commit_plateau(undo_redo, centre, size)


## A ground region at territory-local `centre` (ground height taken there).
func commit_ground(undo_redo: EditorUndoRedoManager, centre: Vector3, size: Vector2) -> Node3D:
	var error := ground_error(centre, size)
	if not error.is_empty():
		last_message = error
		return null
	var ground := _root.get_node_or_null("Ground") as Node3D
	var regions := _root.get_node_or_null("Ground/Regions") as Node3D
	var new_ground := ground == null
	var new_regions := regions == null
	if new_ground:
		ground = Node3D.new()
		ground.name = "Ground"
	if new_regions:
		regions = Node3D.new()
		regions.name = "Regions"
	var region: Node3D = GROUND_SCRIPT.new()
	var identity := fresh_id(regions if not new_regions else null, "ground", "region_id")
	region.name = identity
	region.set("region_id", identity)
	region.set("shape", int(options.get("shape", 0)))
	region.set("size", size)
	region.set("blend_width", float(options.get("blend_width", 3.0)))
	region.set("opacity", float(options.get("opacity", 0.9)))
	region.set("priority", int(options.get("priority", 10)))
	region.set("surface", _surface())
	region.set("enabled", true)
	var height := Probe.height_at(_root, _root.global_transform * centre)
	var world := _root.global_transform * Vector3(centre.x, height if not is_nan(height) else centre.y,
		centre.z)
	undo_redo.create_action("Add ground region %s" % identity, UndoRedo.MERGE_DISABLE, _root)
	if new_ground:
		undo_redo.add_do_method(_root, &"add_child", ground, true)
		undo_redo.add_do_method(ground, &"set_owner", _root)
		undo_redo.add_do_reference(ground)
	if new_regions:
		undo_redo.add_do_method(ground, &"add_child", regions, true)
		undo_redo.add_do_method(regions, &"set_owner", _root)
		undo_redo.add_do_reference(regions)
	undo_redo.add_do_method(regions, &"add_child", region, true)
	undo_redo.add_do_method(region, &"set_owner", _root)
	undo_redo.add_do_property(region, &"global_position", world)
	undo_redo.add_do_reference(region)
	undo_redo.add_undo_method(regions, &"remove_child", region)
	if new_regions:
		undo_redo.add_undo_method(ground, &"remove_child", regions)
	if new_ground:
		undo_redo.add_undo_method(_root, &"remove_child", ground)
	undo_redo.commit_action()
	last_message = "Added ground region %s (%.0f x %.0f m, %s)." % [identity, size.x, size.y,
		String(options.get("surface_label", "surface"))]
	return region


## Why a ground region there is refused, or "".
func ground_error(centre: Vector3, size: Vector2) -> String:
	var regions := _root.get_node_or_null("Ground/Regions")
	var count := 0
	if regions != null:
		for child in regions.get_children():
			if child.get_script() == GROUND_SCRIPT:
				count += 1
	if count >= MAX_GROUND_REGIONS:
		return ("This territory already has %d ground regions, the most the terrain preview " +
			"draws. Reuse or merge existing ones.") % count
	if _surface() == null:
		return "Choose a surface for the ground region first."
	var reach := Vector2(size.x * 0.5, size.y * 0.5) + Vector2.ONE * float(
		options.get("blend_width", 3.0))
	for point in outline(Vector2(centre.x, centre.z), reach, int(options.get("shape", 0)), 32):
		if not Geometry2D.is_point_in_polygon(point, _polygon):
			return "The region (with its feather) must stay inside the land this territory owns."
	return ""


## A terrain patch centred at territory-local `centre`.
func commit_plateau(undo_redo: EditorUndoRedoManager, centre: Vector3, size: Vector2) -> Node3D:
	var terrain := Probe.region_terrain(_root)
	var to_terrain: Transform3D = terrain.global_transform.affine_inverse() * _root.global_transform
	var local: Vector3 = to_terrain * centre
	var ground := float(terrain.call("height_at_local", local.x, local.z))
	var operation := String(options.get("operation", "set"))
	var height := float(options.get("height", 3.0))
	var patch_y := (ground + height) if operation == "set" else height
	if operation == "set" and is_nan(ground):
		last_message = "The plateau's centre is off the terrain."
		return null
	var patch: Node3D = PATCH_SCRIPT.new()
	patch.set("shape", int(options.get("shape", 0)))
	patch.set("operation", 1 if operation == "set" else 0)
	patch.set("size", size)
	patch.set("feather", float(options.get("feather", 6.0)))
	var patch_to_terrain := Transform3D(Basis.IDENTITY, Vector3(local.x, patch_y, local.z))
	var error := plateau_error(patch, patch_to_terrain)
	if not error.is_empty():
		patch.free()
		last_message = error
		return null
	var patches := terrain.get_node_or_null("Patches") as Node3D
	var new_patches := patches == null
	if new_patches:
		patches = Node3D.new()
		patches.name = "Patches"
	var identity := fresh_id(patches if not new_patches else null, "stamp", "patch_id")
	patch.name = identity
	patch.set("patch_id", identity)
	undo_redo.create_action("Stamp plateau %s" % identity, UndoRedo.MERGE_DISABLE, _root)
	if new_patches:
		undo_redo.add_do_method(terrain, &"add_child", patches, true)
		undo_redo.add_do_method(patches, &"set_owner", _root)
		undo_redo.add_do_reference(patches)
	undo_redo.add_do_method(patches, &"add_child", patch, true)
	undo_redo.add_do_method(patch, &"set_owner", _root)
	undo_redo.add_do_property(patch, &"global_transform", terrain.global_transform * patch_to_terrain)
	undo_redo.add_do_reference(patch)
	undo_redo.add_undo_method(patches, &"remove_child", patch)
	if new_patches:
		undo_redo.add_undo_method(terrain, &"remove_child", patches)
	undo_redo.commit_action()
	last_message = ("Stamped %s: %s %.1f m over %.0f x %.0f m. It shapes the terrain; walkability " +
		"still follows the grade and water rules.") % [identity,
		"level at" if operation == "set" else "raise by", patch_y, size.x, size.y]
	return patch


## Why a patch with this transform is refused (it would touch a locked or
## faded border sample), or "".
func plateau_error(patch: Node3D, patch_to_terrain: Transform3D) -> String:
	var locked: PackedByteArray = _protection.locked
	var weights: PackedFloat32Array = _protection.weights
	var origin: Vector2 = _protection.origin
	var grid: Vector2i = _protection.grid
	var cell := float(_protection.cell)
	var size: Vector2 = patch.get("size")
	var reach := maxf(size.x, size.y) * 0.75 + cell
	var centre := Vector2(patch_to_terrain.origin.x, patch_to_terrain.origin.z)
	var x0 := clampi(floori((centre.x - reach - origin.x) / cell), 0, grid.x - 1)
	var x1 := clampi(ceili((centre.x + reach - origin.x) / cell), 0, grid.x - 1)
	var z0 := clampi(floori((centre.y - reach - origin.y) / cell), 0, grid.y - 1)
	var z1 := clampi(ceili((centre.y + reach - origin.y) / cell), 0, grid.y - 1)
	var touched := 0
	var refused := 0
	for z in range(z0, z1 + 1):
		for x in range(x0, x1 + 1):
			var sample := Vector2(origin.x + float(x) * cell, origin.y + float(z) * cell)
			if float(patch.call("weight_at_transform", sample, patch_to_terrain)) <= 0.0:
				continue
			touched += 1
			var index := z * grid.x + x
			if locked[index] != 0 or weights[index] < PROTECTED_WEIGHT:
				refused += 1
	if touched == 0:
		return "The plateau is too small to reach any terrain sample; drag it larger."
	if refused > 0:
		return ("The plateau reaches the protected border band (%d of its %d terrain samples); " +
			"move it inward or make it smaller.") % [refused, touched]
	return ""


## `<prefix>-NN`, unique among `container`'s children (by `field` and name).
static func fresh_id(container: Node, prefix: String, field: String) -> String:
	var used := {}
	if container != null:
		for child in container.get_children():
			used[String(child.name)] = true
			if child.get(field) != null:
				used[String(child.get(field))] = true
	var index := 1
	while used.has("%s-%02d" % [prefix, index]):
		index += 1
	return "%s-%02d" % [prefix, index]


## Points around an ellipse or rectangle footprint in X/Z.
static func outline(centre: Vector2, half: Vector2, shape: int, segments: int) -> PackedVector2Array:
	var points := PackedVector2Array()
	if shape == 1:
		for corner: Vector2 in [Vector2(-1, -1), Vector2(1, -1), Vector2(1, 1), Vector2(-1, 1)]:
			points.append(centre + corner * half)
		return points
	for index in segments:
		var angle := TAU * float(index) / float(segments)
		points.append(centre + Vector2(cos(angle) * half.x, sin(angle) * half.y))
	return points


func hint_lines() -> PackedStringArray:
	if not is_active():
		return PackedStringArray()
	var shape := "rectangle" if int(options.get("shape", 0)) == 1 else "ellipse"
	var head := ""
	if kind == "ground":
		head = "Ground region  ·  %s  ·  %s  ·  feather %.1f m  ·  opacity %.2f  ·  priority %d" % [
			String(options.get("surface_label", "surface")), shape,
			float(options.get("blend_width", 3.0)), float(options.get("opacity", 0.9)),
			int(options.get("priority", 10))]
	else:
		head = "Plateau  ·  %s  ·  %s %.1f m  ·  feather %.1f m" % [shape,
			"level at ground +" if String(options.get("operation", "set")) == "set" else "raise by",
			float(options.get("height", 3.0)), float(options.get("feather", 6.0))]
	return PackedStringArray([head, last_message,
		("Press and drag: centre then size  ·  %s/%s: feather%s  ·  Esc: discard  ·  right-click: stop") % [
			Settings.shortcut_text("path_narrower"), Settings.shortcut_text("path_wider"),
			"  ·  PgUp/PgDn: height" if kind == "plateau" else ""]])


func _surface() -> Resource:
	var surface: Variant = options.get("surface")
	if surface is Resource:
		return surface
	var preset := String(options.get("preset", ""))
	if preset.is_empty():
		return null
	return MapAuthoringSurface.from_preset(preset)


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
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.no_depth_test = true
		_node.material_override = material
		_root.add_child(_node, false, Node.INTERNAL_MODE_BACK)
		_node.global_transform = Transform3D.IDENTITY
	_mesh.clear_surfaces()
	if not _anchor.is_finite() or not _hover is Vector3:
		return
	var inverse := _root.global_transform.affine_inverse()
	var centre: Vector3 = inverse * _anchor
	var corner: Vector3 = inverse * (_hover as Vector3)
	var half := Vector2(maxf(absf(corner.x - centre.x), MIN_SIZE * 0.5),
		maxf(absf(corner.z - centre.z), MIN_SIZE * 0.5))
	var color: Color = COLORS.get(kind, Color.WHITE)
	var feather := float(options.get("blend_width" if kind == "ground" else "feather", 3.0))
	_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
	var shape := int(options.get("shape", 0))
	_draw_outline(outline(Vector2(centre.x, centre.z), half, shape, 48), color)
	if kind == "plateau" and feather > 0.0:
		var inner := Vector2(maxf(half.x - feather, 0.05), maxf(half.y - feather, 0.05))
		_draw_outline(outline(Vector2(centre.x, centre.z), inner, shape, 48), Color(color, 0.5))
	elif kind == "ground" and feather > 0.0:
		_draw_outline(outline(Vector2(centre.x, centre.z), half + Vector2.ONE * feather, shape, 48),
			Color(color, 0.45))
	_mesh.surface_end()


func _draw_outline(points: PackedVector2Array, color: Color) -> void:
	for index in points.size():
		var a := points[index]
		var b := points[(index + 1) % points.size()]
		var steps := clampi(ceili(a.distance_to(b) / 1.5), 1, 64)
		for step in steps:
			var p := a.lerp(b, float(step) / float(steps))
			var q := a.lerp(b, float(step + 1) / float(steps))
			_mesh.surface_set_color(color)
			_mesh.surface_add_vertex(_draped(p))
			_mesh.surface_set_color(color)
			_mesh.surface_add_vertex(_draped(q))


func _draped(point: Vector2) -> Vector3:
	var world := _root.global_transform * Vector3(point.x, 0.0, point.y)
	var height := Probe.height_at(_root, world)
	return Vector3(world.x, (height if not is_nan(height) else world.y) + 0.15, world.z)
