class_name ReplicatedActor3D
extends CharacterBody3D

@export var interpolation_seconds := 0.12

var actor_id := -1
var server_target := Vector3.ZERO
var resolver: AnimationResolver
var animation_player: AnimationPlayer
var current_action: StringName = &"idle"
var _snap_pending := true

func configure(dto: Dictionary, adapter: CoordinateAdapter,
		model_config: Dictionary, animation_config: Dictionary) -> Array[String]:
	actor_id = int(dto.actor_id)
	server_target = adapter.tile_center(int(dto.x), int(dto.y))
	position = server_target
	rotation.y = adapter.rotation_to_godot(int(dto.rotation))
	resolver = AnimationResolver.new(animation_config)
	var source_path := _external_path(str(model_config.get("scene", "")))
	var errors := _load_native_scene(source_path)
	if not errors.is_empty():
		_add_fallback_visual(dto)
	if errors.is_empty():
		_apply_import_adapter(model_config.get("import", {}))
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
	var label: Label3D = Label3D.new()
	label.name = "Nameplate"
	label.text = str(dto.get("name", "Unknown actor"))
	label.position.y = 2.05
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	add_child(label)

func apply_server_state(dto: Dictionary, adapter: CoordinateAdapter, teleport := false) -> void:
	server_target = adapter.tile_center(int(dto.x), int(dto.y))
	rotation.y = adapter.rotation_to_godot(int(dto.rotation))
	if teleport or global_position.distance_to(server_target) > 8.0:
		global_position = server_target
		_snap_pending = false
	if dto.has("command"):
		play_action(resolver.action_for_command(int(dto.command)))

func play_action(action: StringName) -> void:
	if animation_player == null or resolver == null:
		return
	var clip := resolver.clip_for_action(action)
	if clip.is_empty() or not animation_player.has_animation(clip):
		return
	if current_action == action and animation_player.is_playing():
		return
	current_action = action
	animation_player.play(clip)

func _physics_process(delta: float) -> void:
	if _snap_pending:
		global_position = server_target
		_snap_pending = false
		return
	var weight := clampf(delta / maxf(interpolation_seconds, 0.001), 0.0, 1.0)
	global_position = global_position.lerp(server_target, weight)

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

static func _external_path(path: String) -> String:
	return ProjectSettings.globalize_path(path) if path.begins_with("res://") else path
