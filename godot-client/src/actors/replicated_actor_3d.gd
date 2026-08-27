class_name ReplicatedActor3D
extends CharacterBody3D

@export var walk_presentation_speed := 6.0
@export var run_presentation_speed := 9.0
@export var turn_speed_radians := 12.0

var actor_id := -1
var server_target := Vector3.ZERO
var resolver: AnimationResolver
var animation_player: AnimationPlayer
var current_action: StringName = &"idle"
var _snap_pending := true
var _target_yaw := 0.0
var _presentation_speed := 6.0

func configure(dto: Dictionary, adapter: CoordinateAdapter,
		model_config: Dictionary, animation_config: Dictionary) -> Array[String]:
	actor_id = int(dto.actor_id)
	server_target = adapter.tile_center(int(dto.x), int(dto.y))
	position = server_target
	rotation.y = adapter.rotation_to_godot(int(dto.rotation))
	_target_yaw = rotation.y
	collision_layer = 2
	collision_mask = 0
	var selection_shape: CollisionShape3D = CollisionShape3D.new()
	selection_shape.name = "SelectionCollision"
	var capsule_shape: CapsuleShape3D = CapsuleShape3D.new()
	capsule_shape.radius = 0.45
	capsule_shape.height = 1.9
	selection_shape.shape = capsule_shape
	selection_shape.position.y = 0.95
	add_child(selection_shape)
	var selection_ring: MeshInstance3D = MeshInstance3D.new()
	selection_ring.name = "SelectionRing"
	var ring: TorusMesh = TorusMesh.new()
	ring.inner_radius = 0.48
	ring.outer_radius = 0.58
	var ring_material: StandardMaterial3D = StandardMaterial3D.new()
	ring_material.albedo_color = Color(0.95, 0.76, 0.18, 0.9)
	ring_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ring_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	ring.material = ring_material
	selection_ring.mesh = ring
	selection_ring.position.y = 0.05
	selection_ring.visible = false
	add_child(selection_ring)
	_add_nameplate(dto)
	resolver = AnimationResolver.new(animation_config)
	var source_path := _external_path(str(model_config.get("scene", "")))
	var errors := _load_native_scene(source_path)
	if not errors.is_empty():
		_add_fallback_visual(dto)
	if errors.is_empty():
		_apply_import_adapter(model_config.get("import", {}))
		var visual_error: String = _validate_native_visual()
		if not visual_error.is_empty():
			errors.append(visual_error)
			_add_fallback_visual(dto)
		var skeleton := find_child("*", true, false) as Skeleton3D
		if skeleton == null:
			for node in find_children("*", "Skeleton3D", true, false):
				skeleton = node as Skeleton3D
				break
		if skeleton == null:
			errors.append("Skeleton3D missing")
		else:
			var animation_path := _external_path(str(model_config.get("animationLibrary", "")))
			var imported := NativeAnimationImporter.import_library(self, animation_path, skeleton, model_config.get("boneAliases", {}))
			animation_player = imported.player
			errors.append_array(Array(imported.errors))
			if animation_player != null:
				errors.append_array(resolver.validate(imported.clips))
				play_action(&"idle")
	return errors

func render_diagnostics() -> Dictionary:
	var meshes: Array[Dictionary] = []
	for node_value: Node in find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		meshes.append({
			"path": str(mesh_node.get_path()),
			"visible": mesh_node.visible,
			"visible_in_tree": mesh_node.is_visible_in_tree(),
			"layers": mesh_node.layers,
			"aabb": mesh_node.get_aabb(),
			"material_override": mesh_node.material_override != null,
		})
	var native_model: Node3D = get_node_or_null("NativeModel") as Node3D
	return {
		"actor_id": actor_id,
		"server_target": server_target,
		"final_global_position": global_position,
		"native_model_transform": native_model.transform if native_model != null else Transform3D.IDENTITY,
		"meshes": meshes,
	}

func _add_fallback_visual(dto: Dictionary) -> void:
	var mesh_instance: MeshInstance3D = MeshInstance3D.new()
	mesh_instance.name = "MissingModelFallback"
	var capsule: CapsuleMesh = CapsuleMesh.new()
	capsule.radius = 0.32
	capsule.height = 1.7
	var material: StandardMaterial3D = StandardMaterial3D.new()
	var kind: int = int(dto.get("kind", 0))
	material.albedo_color = Color(0.92, 0.56, 0.18) if kind == 2 else Color(0.75, 0.18, 0.78)
	capsule.material = material
	mesh_instance.mesh = capsule
	mesh_instance.position.y = 0.85
	add_child(mesh_instance)

func _add_nameplate(dto: Dictionary) -> void:
	var label: Label3D = Label3D.new()
	label.name = "Nameplate"
	label.text = str(dto.get("name", "Unknown actor"))
	label.position.y = 2.15
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.font_size = 28
	label.outline_size = 6
	label.modulate = Color(1.0, 1.0, 1.0, 1.0)
	add_child(label)

func apply_server_state(dto: Dictionary, adapter: CoordinateAdapter, teleport := false) -> void:
	server_target = adapter.tile_center(int(dto.x), int(dto.y))
	var actor_command: int = int(dto.get("command", -1))
	var command_direction: Vector2i = EloriaProtocol.actor_command_direction(actor_command)
	if command_direction != Vector2i.ZERO:
		_target_yaw = adapter.direction_to_godot(command_direction)
	else:
		_target_yaw = adapter.rotation_to_godot(int(dto.rotation))
	_presentation_speed = walk_presentation_speed
	if actor_command >= 30 and actor_command <= 37:
		_presentation_speed = run_presentation_speed
	if teleport or global_position.distance_to(server_target) > 8.0:
		global_position = server_target
		rotation.y = _target_yaw
		_snap_pending = false
	if dto.has("command") and resolver != null:
		play_action(resolver.action_for_command(actor_command))

func play_action(action: StringName) -> void:
	if animation_player == null or resolver == null:
		return
	var clip := resolver.clip_for_action(action)
	if clip.is_empty() or not animation_player.has_animation(clip):
		return
	animation_player.speed_scale = resolver.playback_speed_for_action(action)
	if current_action == action and animation_player.is_playing():
		return
	current_action = action
	animation_player.play(clip)

func set_selected(value: bool) -> void:
	var ring: Node3D = get_node_or_null("SelectionRing") as Node3D
	if ring != null:
		ring.visible = value

func set_surface_height(value: float) -> void:
	server_target.y = value
	if _snap_pending or absf(global_position.y - value) > 0.5:
		global_position.y = value

func _physics_process(delta: float) -> void:
	if _snap_pending:
		global_position = server_target
		rotation.y = _target_yaw
		_snap_pending = false
		return
	global_position = global_position.move_toward(server_target, _presentation_speed * delta)
	rotation.y = rotate_toward(rotation.y, _target_yaw, turn_speed_radians * delta)

func _load_native_scene(path: String) -> Array[String]:
	if path.is_empty():
		return ["model scene path missing"]
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	var error := document.append_from_file(path, state)
	if error != OK:
		return ["model glTF import failed: " + error_string(error), path]
	var model := document.generate_scene(state)
	if model == null:
		return ["model glTF scene generation failed"]
	model.name = "NativeModel"
	add_child(model)
	return []

func _apply_import_adapter(config: Dictionary) -> void:
	var model := get_node_or_null("NativeModel") as Node3D
	if model == null:
		return
	model.scale = Vector3.ONE * float(config.get("scale", 1.0))
	model.rotation_degrees = Vector3(
		float(config.get("rotationDegreesX", 0.0)),
		float(config.get("rotationDegreesY", 0.0)),
		float(config.get("rotationDegreesZ", 0.0)))
	# The protocol position is a foot point. Normalize the imported visual at
	# its root without flattening or rewriting the glTF hierarchy/skeleton.
	var bounds: AABB = _native_visual_bounds(model)
	if bounds.size.y > 0.0:
		model.position.y = -bounds.position.y

func _validate_native_visual() -> String:
	var native_model: Node3D = get_node_or_null("NativeModel") as Node3D
	if native_model == null:
		return "native model root missing"
	var visible_meshes: int = 0
	for node_value: Node in native_model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		if mesh_node.mesh != null and mesh_node.visible and mesh_node.layers != 0:
			visible_meshes += 1
	return "native model has no renderable meshes" if visible_meshes == 0 else ""

func _native_visual_bounds(model: Node3D) -> AABB:
	var combined: AABB = AABB()
	var initialized: bool = false
	for node_value: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		if mesh_node.mesh == null:
			continue
		var relative: Transform3D = model.global_transform.affine_inverse() * mesh_node.global_transform
		var mesh_bounds: AABB = relative * mesh_node.get_aabb()
		combined = combined.merge(mesh_bounds) if initialized else mesh_bounds
		initialized = true
	return combined

static func _external_path(path: String) -> String:
	return ProjectSettings.globalize_path(path) if path.begins_with("res://") else path
