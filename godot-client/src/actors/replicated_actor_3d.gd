class_name ReplicatedActor3D
extends CharacterBody3D

@export var walk_presentation_speed := 6.0
@export var run_presentation_speed := 9.0
@export var turn_speed_radians := 12.0
@export var initial_server_interval := 0.25
@export var interval_smoothing := 0.5
@export var arrival_margin := 1.05
@export var minimum_segment_duration := 0.06
@export var maximum_segment_duration := 0.75

var actor_id := -1
var server_target := Vector3.ZERO
var resolver: AnimationResolver
var animation_player: AnimationPlayer
var current_action: StringName = &"idle"
var _snap_pending := true
var _target_yaw := 0.0
var _presentation_speed := 6.0
var _segment_start := Vector3.ZERO
var _segment_elapsed := 0.0
var _segment_duration := 0.0
var _last_movement_update_msec := -1
var _smoothed_server_interval := 0.25
var _native_skeleton: Skeleton3D
var _attachment_bones: Dictionary = {}
var _equipment_config: Dictionary = {}
var _equipment_visuals: Dictionary = {}
var _equipment_nodes: Dictionary = {}
var _nameplate: Label3D

func configure(dto: Dictionary, adapter: CoordinateAdapter,
		model_config: Dictionary, animation_config: Dictionary,
		equipment_config: Dictionary = {}) -> Array[String]:
	actor_id = int(dto.actor_id)
	server_target = adapter.tile_center(int(dto.x), int(dto.y))
	position = server_target
	_segment_start = position
	_smoothed_server_interval = initial_server_interval
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
	_attachment_bones = (model_config.get("attachments", {}) as Dictionary).duplicate(true)
	_equipment_config = (equipment_config as Dictionary).duplicate(true)
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
			_native_skeleton = skeleton
			apply_appearance_variants(dto.get("appearance", {}) as Dictionary)
			var animation_path := _external_path(str(model_config.get("animationLibrary", "")))
			var imported := NativeAnimationImporter.import_library(self, animation_path, skeleton, model_config.get("boneAliases", {}))
			animation_player = imported.player
			errors.append_array(Array(imported.errors))
			if animation_player != null:
				if not animation_player.animation_finished.is_connected(
						_on_animation_finished):
					animation_player.animation_finished.connect(_on_animation_finished)
				errors.append_array(resolver.validate(imported.clips))
				play_action(&"idle")
	apply_equipment_visuals(dto.get("equipment_visuals", {}) as Dictionary,
		dto.get("equipment_fallback_parts", []) as Array)
	return errors

func apply_appearance_variants(appearance: Dictionary) -> void:
	if _native_skeleton == null or appearance.is_empty():
		return
	var skin_tint: Color = AppearanceVariants.skin_tint(int(appearance.get("skin", 0)))
	var hair_tint: Color = AppearanceVariants.hair_color(int(appearance.get("hair", 0)))
	var eye_tint: Color = AppearanceVariants.eye_color(int(appearance.get("eyes", 0)))
	var native_model: Node3D = get_node_or_null("NativeModel") as Node3D
	if native_model == null:
		return
	for node_value: Node in native_model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		var mesh_name: String = mesh_node.name.to_lower()
		if mesh_name == "eyes":
			_tint_mesh(mesh_node, eye_tint, true)
		elif mesh_name == "eyebrows":
			_tint_mesh(mesh_node, hair_tint)
		elif mesh_name.begins_with("superhero_"):
			_tint_mesh(mesh_node, skin_tint)
	_add_hair_variant(AppearanceVariants.hair_style(
		int(appearance.get("hair", 0))), hair_tint)

func _tint_mesh(mesh_node: MeshInstance3D, tint: Color,
		emissive: bool = false) -> void:
	if mesh_node.mesh == null or mesh_node.mesh.get_surface_count() == 0:
		return
	var source: Material = mesh_node.get_active_material(0)
	if source is not StandardMaterial3D:
		return
	var material: StandardMaterial3D = (source as StandardMaterial3D).duplicate()
	material.albedo_color = (source as StandardMaterial3D).albedo_color * tint
	if emissive:
		material.emission_enabled = true
		material.emission = tint * 0.28
	mesh_node.material_override = material

func _add_hair_variant(style: int, color: Color) -> void:
	if style == 0:
		return
	var attachment: BoneAttachment3D = _bone_attachment("Head", 9, style)
	if attachment == null:
		return
	attachment.name = "AppearanceHair_%d" % style
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.88
	_hair_piece(attachment, Vector3(0.0, 0.08, 0.015),
		Vector3(0.42, 0.22, 0.40), material)
	if style == 2:
		_hair_piece(attachment, Vector3(0.0, -0.08, 0.13),
			Vector3(0.36, 0.45, 0.24), material)
	elif style == 3:
		_hair_piece(attachment, Vector3(0.0, 0.19, 0.015),
			Vector3(0.15, 0.38, 0.18), material)

func _hair_piece(parent: Node3D, local_position: Vector3, local_scale: Vector3,
		material: StandardMaterial3D) -> void:
	var instance: MeshInstance3D = MeshInstance3D.new()
	instance.name = "HairPiece"
	var mesh: SphereMesh = SphereMesh.new()
	mesh.radius = 0.5
	mesh.height = 1.0
	mesh.radial_segments = 16
	mesh.rings = 8
	mesh.material = material
	instance.mesh = mesh
	instance.position = local_position
	instance.scale = local_scale
	parent.add_child(instance)

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
	_nameplate = label

func set_nameplate_visible(enabled: bool) -> void:
	if is_instance_valid(_nameplate):
		_nameplate.visible = enabled

func apply_server_state(dto: Dictionary, adapter: CoordinateAdapter, teleport := false) -> void:
	var next_target: Vector3 = adapter.tile_center(int(dto.x), int(dto.y))
	# Server movement contains tile coordinates only. Keep the last sampled
	# rendered-surface height until Main performs the ray sample for the new tile;
	# otherwise each packet temporarily pushes actors back to the flat manifest
	# fallback and can leave them visibly embedded in sculpted terrain.
	next_target.y = server_target.y
	var target_changed: bool = server_target.distance_squared_to(next_target) > 0.000001
	server_target = next_target
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
		_segment_start = server_target
		_segment_elapsed = 0.0
		_segment_duration = 0.0
		_last_movement_update_msec = -1
		_smoothed_server_interval = initial_server_interval
		_snap_pending = false
	elif target_changed:
		var now_msec: int = Time.get_ticks_msec()
		if _last_movement_update_msec >= 0:
			var observed_interval: float = float(
				now_msec - _last_movement_update_msec) / 1000.0
			if observed_interval <= maximum_segment_duration * 2.0:
				observed_interval = clampf(observed_interval, 0.05,
					maximum_segment_duration)
				_smoothed_server_interval = lerpf(_smoothed_server_interval,
					observed_interval, interval_smoothing)
			else:
				# A long stationary pause begins a new movement burst; do not
				# treat the idle time as the next step's network cadence.
				_smoothed_server_interval = initial_server_interval
		_last_movement_update_msec = now_msec
		_segment_start = global_position
		_segment_elapsed = 0.0
		_segment_duration = presentation_segment_duration(
			global_position.distance_to(server_target), _presentation_speed,
			_smoothed_server_interval, arrival_margin,
			minimum_segment_duration, maximum_segment_duration)
	if dto.has("command") and resolver != null:
		play_action(resolver.action_for_command(actor_command))
	apply_equipment_visuals(dto.get("equipment_visuals", {}) as Dictionary,
		dto.get("equipment_fallback_parts", []) as Array)

func apply_equipment_visuals(visuals: Dictionary, fallback_parts: Array = []) -> void:
	for raw_part: Variant in _equipment_visuals.keys():
		var old_part: int = int(raw_part)
		if not visuals.has(old_part) and not visuals.has(str(old_part)):
			_clear_equipment_part(old_part)
	for raw_part: Variant in visuals:
		var part: int = int(raw_part)
		var visual_id: int = int(visuals[raw_part])
		var allow_fallback: bool = fallback_parts.has(part)
		if int(_equipment_visuals.get(part, -1)) == visual_id and (
				not allow_fallback or _equipment_nodes.has(part)):
			continue
		_clear_equipment_part(part)
		_equipment_visuals[part] = visual_id
		_create_equipment_part(part, visual_id, allow_fallback)

func equipment_diagnostics() -> Dictionary:
	var native_count: int = 0
	var fallback_count: int = 0
	for nodes_value: Variant in _equipment_nodes.values():
		for node_value: Variant in nodes_value:
			var node: Node = node_value as Node
			if is_instance_valid(node):
				if node.has_meta("native_equipment"):
					native_count += 1
				else:
					fallback_count += 1
	return {"visuals": _equipment_visuals.duplicate(), "native": native_count,
		"fallback": fallback_count}

func _clear_equipment_part(part: int) -> void:
	var nodes_value: Variant = _equipment_nodes.get(part, [])
	if nodes_value is Array:
		for node_value: Variant in nodes_value:
			var node: Node = node_value as Node
			if is_instance_valid(node):
				node.queue_free()
	_equipment_nodes.erase(part)
	_equipment_visuals.erase(part)

func _create_equipment_part(part: int, visual_id: int, allow_fallback: bool) -> void:
	if _native_skeleton == null:
		return
	var parts: Dictionary = _equipment_config.get("parts", {}) as Dictionary
	var part_config: Dictionary = parts.get(str(part), {}) as Dictionary
	if part_config.is_empty():
		return
	var semantic: String = str(part_config.get("attachment", ""))
	var bones_value: Variant = _attachment_bones.get(semantic, "")
	var bones: Array[String] = []
	if bones_value is Array:
		for raw_bone: Variant in bones_value:
			bones.append(str(raw_bone))
	elif not str(bones_value).is_empty():
		bones.append(str(bones_value))
	var created: Array[Node] = []
	var aliases: Dictionary = _equipment_config.get("aliases", {}) as Dictionary
	var model_key: String = "%d:%d" % [part, visual_id]
	model_key = str(aliases.get(model_key, model_key))
	var models: Dictionary = _equipment_config.get("models", {}) as Dictionary
	var model_config: Dictionary = models.get(model_key, {}) as Dictionary
	if not model_config.is_empty() and not bones.is_empty():
		var native_model: Node3D = _load_native_equipment(str(model_config.get("scene", "")))
		if native_model != null:
			_apply_equipment_import(native_model, model_config.get("import", {}) as Dictionary)
			var native_attachment: BoneAttachment3D = _bone_attachment(bones[0], part, visual_id)
			if native_attachment != null:
				native_attachment.add_child(native_model)
				native_attachment.set_meta("native_equipment", true)
				created.append(native_attachment)
	if created.is_empty() and allow_fallback:
		for bone: String in bones:
			var fallback_attachment: BoneAttachment3D = _bone_attachment(bone, part, visual_id)
			if fallback_attachment == null:
				continue
			fallback_attachment.add_child(_equipment_fallback_mesh(
				str(part_config.get("fallback", "body"))))
			created.append(fallback_attachment)
	if created.is_empty():
		_equipment_nodes.erase(part)
	else:
		_equipment_nodes[part] = created

func _bone_attachment(bone: String, part: int, visual_id: int) -> BoneAttachment3D:
	if _native_skeleton == null or _native_skeleton.find_bone(bone) < 0:
		return null
	var attachment: BoneAttachment3D = BoneAttachment3D.new()
	attachment.name = "EquipmentPart_%d_Visual_%d_%s" % [part, visual_id, bone]
	attachment.bone_name = bone
	_native_skeleton.add_child(attachment)
	return attachment

func _load_native_equipment(path: String) -> Node3D:
	if path.is_empty():
		return null
	var document: GLTFDocument = GLTFDocument.new()
	var state: GLTFState = GLTFState.new()
	if document.append_from_file(_external_path(path), state) != OK:
		return null
	var generated: Node = document.generate_scene(state)
	return generated as Node3D if generated is Node3D else null

func _apply_equipment_import(model: Node3D, config: Dictionary) -> void:
	model.scale = Vector3.ONE * float(config.get("scale", 1.0))
	var translation_value: Variant = config.get("translation", [0, 0, 0])
	if translation_value is Array and (translation_value as Array).size() >= 3:
		var translation: Array = translation_value as Array
		model.position = Vector3(float(translation[0]), float(translation[1]),
			float(translation[2]))
	var rotation_value: Variant = config.get("rotationDegrees", [0, 0, 0])
	if rotation_value is Array and (rotation_value as Array).size() >= 3:
		var rotation: Array = rotation_value as Array
		model.rotation_degrees = Vector3(float(rotation[0]), float(rotation[1]),
			float(rotation[2]))

func _equipment_fallback_mesh(shape: String) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	instance.name = "MissingNativeEquipmentFallback"
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = Color(1.0, 0.1, 0.85, 0.85)
	material.emission_enabled = true
	material.emission = Color(0.7, 0.0, 0.5)
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	match shape:
		"weapon":
			var weapon: BoxMesh = BoxMesh.new()
			weapon.size = Vector3(0.08, 0.7, 0.08)
			instance.mesh = weapon
		"shield":
			var shield: CylinderMesh = CylinderMesh.new()
			shield.top_radius = 0.28
			shield.bottom_radius = 0.28
			shield.height = 0.06
			instance.mesh = shield
		"head":
			var head: SphereMesh = SphereMesh.new()
			head.radius = 0.2
			head.height = 0.35
			instance.mesh = head
		"feet":
			var foot: BoxMesh = BoxMesh.new()
			foot.size = Vector3(0.18, 0.12, 0.32)
			instance.mesh = foot
		_:
			var body: BoxMesh = BoxMesh.new()
			body.size = Vector3(0.32, 0.22, 0.18)
			instance.mesh = body
	instance.material_override = material
	return instance

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

func _on_animation_finished(_animation_name: StringName) -> void:
	# The server sends transition commands, not a second command for the resting
	# pose. Keep this explicit and data-driven through the action map.
	if current_action == &"sit":
		play_action(&"seated_idle")
	elif current_action == &"stand":
		play_action(&"idle")

func set_selected(value: bool) -> void:
	var ring: Node3D = get_node_or_null("SelectionRing") as Node3D
	if ring != null:
		ring.visible = value

func set_surface_height(value: float) -> void:
	server_target.y = value
	if _snap_pending or absf(global_position.y - value) > 0.5:
		global_position.y = value

static func presentation_segment_duration(distance: float, nominal_speed: float,
		observed_interval: float, margin: float, minimum_duration: float,
		maximum_duration: float) -> float:
	var nominal_duration: float = distance / maxf(nominal_speed, 0.001)
	var cadence_duration: float = observed_interval * margin
	return clampf(maxf(nominal_duration, cadence_duration),
		minimum_duration, maximum_duration)

func _physics_process(delta: float) -> void:
	if _snap_pending:
		global_position = server_target
		rotation.y = _target_yaw
		_segment_start = server_target
		_snap_pending = false
		return
	if _segment_duration > 0.0:
		_segment_elapsed = minf(_segment_elapsed + delta, _segment_duration)
		var progress: float = _segment_elapsed / _segment_duration
		global_position = _segment_start.lerp(server_target, progress)
		if progress >= 1.0:
			global_position = server_target
			_segment_duration = 0.0
	else:
		global_position = server_target
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
