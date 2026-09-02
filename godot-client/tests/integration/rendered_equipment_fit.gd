extends SceneTree
## Rendered A/B evidence for generated-equipment fit.
##
## For each wearable slot, two luminous_male actors stand side by side through
## the client's own actor build path: the left one wearing the authored
## reference piece for that slot, the right one the generated piece that is
## supposed to match it. Both go through the same runtime retarget
## (`_rebound_skin` / `_bone_fit`), so any visual difference between the two is
## a difference between the assets themselves.

const SCREEN_SIZE := Vector2i(1280, 720)

## slot label -> [part, authored visual, generated visual]
const PAIRS := {
	"body": [5, 100, 184],
	"legs": [4, 100, 171],
	"boots": [6, 100, 192],
	"boots2": [6, 100, 200],
	"helm": [3, 100, 109],
	"helm2": [3, 100, 117],
}

var _artifacts := ""
var _failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_artifacts = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifacts.is_empty():
		_artifacts = ProjectSettings.globalize_path("res://test-artifacts/equipment-fit")
	_expect(DirAccess.make_dir_recursive_absolute(_artifacts) == OK,
		"artifact directory is writable")
	root.size = SCREEN_SIZE

	var main: Control = (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	main.hide()
	await process_frame

	var models: Dictionary = main.get("models") as Dictionary
	var equipment_config: Dictionary = main.get("equipment_config") as Dictionary
	var race: String = OS.get_environment("ELORIA_FIT_RACE")
	if race.is_empty():
		race = "luminous_male"
	var model_config: Dictionary = models.get(race, {}) as Dictionary
	_expect(not model_config.is_empty(), race + " is in the model registry")

	var stage := Node3D.new()
	root.add_child(stage)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color(0.42, 0.45, 0.5)
	environment.environment.ambient_light_energy = 1.1
	stage.add_child(environment)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-38.0, 142.0, 0.0)
	key.light_energy = 1.5
	stage.add_child(key)
	var camera := Camera3D.new()
	camera.current = true
	camera.fov = 40.0
	# Gameplay layers only, or the actors' map-only discs end up in frame.
	camera.cull_mask = 3
	stage.add_child(camera)

	var adapter := CoordinateAdapter.new({"walkingHeight": 0.0})
	var animation_config: Dictionary = main.call("_animation_for_model", model_config) as Dictionary
	var next_id := 9000
	var pair_x := 0.0
	var slots: Array = PAIRS.keys()
	for slot: String in slots:
		var config: Array = PAIRS[slot] as Array
		var part: int = int(config[0])
		for side: int in range(2):
			var visual: int = int(config[1 + side])
			var actor := ReplicatedActor3D.new()
			stage.add_child(actor)
			var dto := {
				"actor_id": next_id, "x": 0, "y": 0, "rotation": 0,
				"kind": 1, "name": "%s %d:%d" % [slot, part, visual],
				"appearance": {},
				"equipment_visuals": {str(part): visual},
			}
			next_id += 1
			var errors: Array[String] = actor.configure(dto, adapter, model_config,
				animation_config, equipment_config)
			_expect(errors.is_empty(), "%s %d:%d builds without errors: %s" % [
				slot, part, visual, errors])
			actor.server_target = Vector3(pair_x + (side * 1.4) - 0.7, 0.0, 0.0)
			actor.global_position = actor.server_target
			actor.rotation.y = PI
			var diagnostics: Dictionary = actor.equipment_diagnostics()
			print("diagnostics %s %d:%d -> %s" % [slot, part, visual, diagnostics])
			_expect(int(diagnostics.get("native", 0)) > 0
				and int(diagnostics.get("fallback", 0)) == 0,
				"%s %d:%d attaches natively" % [slot, part, visual])
		pair_x += 5.0

	for _settle: int in range(24):
		await process_frame

	# Freeze every skeleton at its rest pose first: at rest the retarget
	# collapses to identity, so a piece that is already wrong here has wrong
	# binds, while a piece that is right here but wrong once idle plays has
	# weights that break under pose.
	var actors: Array[Node] = []
	for child: Node in stage.get_children():
		if child is ReplicatedActor3D:
			actors.append(child)
	for actor_node: Node in actors:
		var actor := actor_node as ReplicatedActor3D
		if actor.animation_player != null:
			actor.animation_player.stop()
		var skeleton: Skeleton3D = actor.get_skeleton()
		if skeleton != null:
			skeleton.reset_bone_poses()
	for _settle: int in range(4):
		await process_frame
	for actor_node: Node in actors:
		_audit_skinning(actor_node as ReplicatedActor3D)
	pair_x = 0.0
	for slot: String in slots:
		var centre := Vector3(pair_x, 0.95, 0.0)
		camera.global_position = centre + Vector3(0.0, 0.45, 3.4)
		camera.look_at(centre, Vector3.UP)
		for _settle: int in range(3):
			await process_frame
		await _capture("equipfit-%s-rest.png" % slot,
			"%s at skeleton rest pose: authored (left) vs generated (right)" % slot)
		pair_x += 5.0

	for actor_node: Node in actors:
		var actor := actor_node as ReplicatedActor3D
		actor.play_action(&"idle")
	for _settle: int in range(24):
		await process_frame

	pair_x = 0.0
	for slot: String in slots:
		var centre := Vector3(pair_x, 0.95, 0.0)
		camera.global_position = centre + Vector3(0.0, 0.45, 3.4)
		camera.look_at(centre, Vector3.UP)
		for _settle: int in range(3):
			await process_frame
		await _capture("equipfit-%s-%s.png" % [OS.get_environment("ELORIA_FIT_RACE"), slot] if not OS.get_environment("ELORIA_FIT_RACE").is_empty() else "equipfit-%s.png" % slot,
			"%s: authored (left) vs generated (right)" % slot)
		var focus_part: int = int((PAIRS[slot] as Array)[0])
		var focus_height := 0.55
		if focus_part == 5:
			focus_height = 1.25
		elif focus_part == 3:
			focus_height = 1.62
		var close := Vector3(pair_x, focus_height, 0.0)
		camera.global_position = close + Vector3(0.6, 0.25, 1.9)
		camera.look_at(close, Vector3.UP)
		for _settle: int in range(3):
			await process_frame
		await _capture("equipfit-%s-close.png" % slot,
			"%s close-up: authored (left) vs generated (right)" % slot)
		pair_x += 5.0

	print("rendered equipment fit evidence: ",
		"PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	stage.queue_free()
	main.queue_free()
	await process_frame
	quit(_failures)

## CPU cross-check of what the renderer should be drawing: with the skeleton
## frozen at rest, every bind composed with its bone's pose must be identity,
## and a CPU-skinned marker vertex must land exactly on its authored position.
func _audit_skinning(actor: ReplicatedActor3D) -> void:
	var skeleton: Skeleton3D = actor.get_skeleton()
	if skeleton == null:
		return
	for child: Node in skeleton.get_children():
		var clone := child as MeshInstance3D
		if clone == null or not clone.has_meta("native_equipment"):
			continue
		var skin: Skin = clone.skin
		if skin == null:
			print("AUDIT %s: no skin (socketed)" % clone.name)
			continue
		var worst := 0.0
		var worst_bone := ""
		for index: int in range(skin.get_bind_count()):
			var bone_name: String = skin.get_bind_name(index)
			var bone: int = skeleton.find_bone(bone_name)
			if bone < 0:
				print("AUDIT %s: bind %d name %s NOT FOUND" % [clone.name, index, bone_name])
				continue
			var product: Transform3D = skeleton.get_bone_global_pose(bone) * skin.get_bind_pose(index)
			var drift: float = product.origin.length()
			drift = maxf(drift, (product.basis.x - Vector3.RIGHT).length())
			drift = maxf(drift, (product.basis.y - Vector3.UP).length())
			drift = maxf(drift, (product.basis.z - Vector3.BACK).length())
			if drift > worst:
				worst = drift
				worst_bone = bone_name
		var arrays: Array = clone.mesh.surface_get_arrays(0)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var vertex_bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
		var vertex_weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
		var marker := 0
		for index: int in range(vertices.size()):
			if absf(vertices[index].x) > absf(vertices[marker].x):
				marker = index
		var skinned := Vector3.ZERO
		var weight_sum := 0.0
		for slot: int in range(4):
			var bind: int = vertex_bones[marker * 4 + slot]
			var weight: float = vertex_weights[marker * 4 + slot]
			weight_sum += weight
			var bone: int = skeleton.find_bone(skin.get_bind_name(bind))
			skinned += weight * (skeleton.get_bone_global_pose(bone)
				* skin.get_bind_pose(bind) * vertices[marker])
		print("AUDIT %s: worst pose*bind drift %.6f at %s; marker v%d authored %s cpu-skinned %s wsum %.4f" % [
			clone.name, worst, worst_bone, marker,
			vertices[marker], skinned, weight_sum])

func _capture(name: String, description: String) -> void:
	await process_frame
	var image: Image = root.get_texture().get_image()
	_expect(image != null and image.get_size() == SCREEN_SIZE,
		"%s is a full frame" % name)
	if image == null:
		return
	_expect(image.save_png(_artifacts.path_join(name)) == OK, "%s is written" % name)
	print("capture ", name, ": ", description)

func _expect(value: bool, label: String) -> bool:
	if not value:
		_failures += 1
		push_error("FAIL: " + label)
	return value
