extends SceneTree
## Does the cape stay behind the body through an attack?
##
## The cape is Verlet cloth on three bone chains; an attack leans and twists
## the torso, and the swing carried the cloth around to the chest through the
## armour.  This wears a cape over a cuirass, plays each attack clip, lets the
## cloth modifier settle at a spread of phases, and captures the front so the
## chest can be checked for cape colour -- the direct symptom -- while also
## measuring how far any cape joint reaches ahead of the torso's back plane.

const ATTACKS := ["Sword_Attack", "Attack_Ground_Pound", "Punch_Cross"]
const CAPE_VISUAL := 5
const BODY_VISUAL := 184
## A joint may sit this far ahead of the spine plane before it counts as
## clipping: the plane runs down the middle of the torso, so a couple of
## centimetres is still inside the body, not on the breastplate.
const AHEAD_TOLERANCE := 0.03

var _failures := 0
var _artifacts := ""
var _main: Control
var _stage: Node3D
var _camera: Camera3D
var _adapter: CoordinateAdapter
var _model_config: Dictionary
var _animation_config: Dictionary
var _equipment_config: Dictionary

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_artifacts = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifacts.is_empty():
		_artifacts = ProjectSettings.globalize_path("res://test-artifacts/cape-clipping")
	DirAccess.make_dir_recursive_absolute(_artifacts)
	root.size = Vector2i(560, 720)
	_main = (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(_main)
	await process_frame
	_main.hide()
	await process_frame
	var models: Dictionary = _main.get("models") as Dictionary
	_equipment_config = _main.get("equipment_config") as Dictionary
	_model_config = models.get("luminous_male", {}) as Dictionary
	_animation_config = _main.call("_animation_for_model", _model_config) as Dictionary
	_adapter = CoordinateAdapter.new({"walkingHeight": 0.0})

	_stage = Node3D.new()
	root.add_child(_stage)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.85, 0.87, 0.9)
	env.environment.ambient_light_energy = 1.2
	_stage.add_child(env)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-30.0, 165.0, 0.0)
	_stage.add_child(key)
	_camera = Camera3D.new()
	_camera.current = true
	_camera.cull_mask = 3
	_stage.add_child(_camera)

	var actor := _spawn({str(2): CAPE_VISUAL, str(5): BODY_VISUAL})
	await _settle(actor)
	var skeleton: Skeleton3D = _skeleton_of(actor)
	var cape_bones: PackedInt32Array = _cape_bones(skeleton)
	var player: AnimationPlayer = actor.get("animation_player") as AnimationPlayer

	# Confirm the cloth is live: a cape joint must move between idle and a
	# mid-attack phase, or the test is measuring a static pose.
	var idle_ref: Vector3 = _joint(skeleton, cape_bones[cape_bones.size() - 1])
	player.play("Sword_Attack")
	player.seek(player.get_animation("Sword_Attack").length * 0.67, true)
	for _f: int in range(6):
		await process_frame
	var moved: float = idle_ref.distance_to(
		_joint(skeleton, cape_bones[cape_bones.size() - 1]))
	print("cloth live check: hem moved %.3f m from idle to mid-attack" % moved)
	actor.play_action(&"idle")
	for _f: int in range(20):
		await process_frame
	await _capture(actor, "cape-idle-back.png", true)

	for clip: String in ATTACKS:
		if not player.has_animation(clip):
			continue
		var length: float = player.get_animation(clip).length
		var worst := -1.0
		var worst_phase := 0.0
		for step: int in range(13):
			var phase: float = float(step) / 12.0
			player.play(clip)
			player.seek(phase * length, true)
			for _f: int in range(6):
				await process_frame
			var ahead: float = _worst_ahead(skeleton, cape_bones)
			if ahead > worst:
				worst = ahead
				worst_phase = phase
		# Photograph the worst phase from the front.
		player.play(clip)
		player.seek(worst_phase * length, true)
		for _f: int in range(6):
			await process_frame
		await _capture(actor, "cape-%s.png" % clip.to_lower(), false)
		await _capture(actor, "cape-%s-back.png" % clip.to_lower(), true)
		var verdict: String = "ok" if worst <= AHEAD_TOLERANCE else "CLIPS"
		print("  %-22s worst joint %+.3f m ahead at phase %.2f  %s"
			% [clip, worst, worst_phase, verdict])
		if worst > AHEAD_TOLERANCE:
			_failures += 1

	print("rendered cape clipping: ", "PASS" if _failures == 0
		else "FAIL (%d)" % _failures)
	_main.queue_free()
	await process_frame
	quit(_failures)

func _capture(actor: ReplicatedActor3D, name: String, back: bool) -> void:
	var skeleton: Skeleton3D = _skeleton_of(actor)
	var chest: Vector3 = skeleton.global_transform * skeleton.get_bone_global_pose(
		skeleton.find_bone("spine_03")).origin
	# A +z camera sees this rig's back (the model carries a 180 correction),
	# so the chest is viewed from -z and the back from +z.
	var z: float = 1.9 if back else -1.9
	_camera.global_position = chest + Vector3(0.0, 0.0, z)
	_camera.look_at(chest, Vector3.UP)
	for _f: int in range(3):
		await process_frame
	var image: Image = root.get_texture().get_image()
	image.save_png(_artifacts.path_join(name))

func _worst_ahead(skeleton: Skeleton3D, cape_bones: PackedInt32Array) -> float:
	var to_world: Transform3D = skeleton.global_transform
	var anchor: int = skeleton.find_bone("spine_03")
	var neck: int = skeleton.find_bone("neck_01")
	var sl: int = skeleton.find_bone("upperarm_l")
	var sr: int = skeleton.find_bone("upperarm_r")
	var anchor_pos: Vector3 = to_world * skeleton.get_bone_global_pose(anchor).origin
	var up: Vector3 = (to_world * skeleton.get_bone_global_pose(neck).origin - anchor_pos).normalized()
	var side: Vector3 = (to_world * skeleton.get_bone_global_pose(sl).origin
		- to_world * skeleton.get_bone_global_pose(sr).origin).normalized()
	var forward: Vector3 = side.cross(up).normalized()
	var hang: Vector3 = to_world * skeleton.get_bone_global_pose(cape_bones[0]).origin - anchor_pos
	hang -= up * hang.dot(up)
	if forward.dot(hang) > 0.0:
		forward = -forward
	var plane: float = anchor_pos.dot(forward)
	var worst := -1.0
	for bone: int in cape_bones:
		worst = maxf(worst, (to_world * skeleton.get_bone_global_pose(bone).origin).dot(forward) - plane)
	return worst

func _joint(skeleton: Skeleton3D, bone: int) -> Vector3:
	return skeleton.global_transform * skeleton.get_bone_global_pose(bone).origin

func _cape_bones(skeleton: Skeleton3D) -> PackedInt32Array:
	var bones := PackedInt32Array()
	for chain: String in ["l", "c", "r"]:
		for link: int in range(1, 5):
			var bone: int = skeleton.find_bone("cape_%s_%02d" % [chain, link])
			if bone >= 0:
				bones.append(bone)
	return bones

func _skeleton_of(actor: ReplicatedActor3D) -> Skeleton3D:
	var model: Node = actor.get_node_or_null("NativeModel")
	for node_value: Node in model.find_children("*", "Skeleton3D", true, false):
		return node_value as Skeleton3D
	return null

func _spawn(visuals: Dictionary) -> ReplicatedActor3D:
	var actor := ReplicatedActor3D.new()
	_stage.add_child(actor)
	actor.configure({
		"actor_id": 8100, "x": 0, "y": 0, "rotation": 0, "kind": 1,
		"name": "cape", "appearance": {}, "equipment_visuals": visuals,
	}, _adapter, _model_config, _animation_config, _equipment_config)
	actor.server_target = Vector3.ZERO
	actor.global_position = Vector3.ZERO
	actor.rotation.y = 0.0
	return actor

func _settle(actor: ReplicatedActor3D) -> void:
	actor.play_action(&"idle")
	for _f: int in range(20):
		await process_frame
