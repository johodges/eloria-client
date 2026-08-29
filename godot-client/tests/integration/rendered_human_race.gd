extends SceneTree
## Render the preview races through the client's own creation viewport.
##
## `rendered_character_creation_models.gd` walks `creationOptions`, which is
## keyed on server actor types.  A race the server has not allocated an actor
## type for yet is registered under `previewModels` instead, so it never
## appears there and nothing renders it in the client at all -- which is how a
## race can pass every structural test and still not have been looked at.
##
## This builds the same preview actor the creation panel builds, in the same
## SubViewport, under the same camera and the same three-light rig, and
## captures it: several angles, the runtime appearance variants, and a few
## frames out of the shared animation clips.  Comparison models are rendered
## from the same setup so a sheet can be judged rather than described.

const SCREEN_SIZE := Vector2i(1280, 720)
const COMPARISON := ["luminous_female", "luminous_male"]
## The race rigs are authored facing +Z and the visual root takes a half turn
## onto Godot's forward, so the preview yaw that shows a face is a half turn
## from zero, not zero.  Getting this wrong renders a contact sheet of backs.
const ANGLES := {"front": 3.1416, "three-quarter": 3.7416, "profile": 4.7124,
	"back": 0.0}
const CLIPS := ["Idle_Subtle", "Walk", "Run_Anime", "Crouch_Walk"]

var _artifact_directory := ""
var _failures := 0
var _main: Control
var _viewport: SubViewport
var _models: Dictionary = {}
var _equipment: Dictionary = {}


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_artifact_directory = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifact_directory.is_empty():
		_artifact_directory = ProjectSettings.globalize_path(
			"res://test-artifacts/human-race")
	_expect(DirAccess.make_dir_recursive_absolute(_artifact_directory) == OK,
		"artifact directory is writable")
	root.size = SCREEN_SIZE

	var scene: Resource = load("res://src/app/main.tscn")
	_expect(scene is PackedScene, "creation scene loads")
	if scene is not PackedScene:
		_finish()
		return
	_main = (scene as PackedScene).instantiate() as Control
	root.add_child(_main)
	for _frame: int in range(4):
		await process_frame
	(_main.get_node("LoginPanel") as Control).hide()
	(_main.get_node("GameView") as Control).hide()
	(_main.get_node("CreationPanel") as Control).show()
	_viewport = _main.get_node(
		"CreationPanel/Columns/CharacterPreview/Viewport") as SubViewport

	var registry: Dictionary = _json("res://data/actors/models.json")
	_models = registry.get("models", {}) as Dictionary
	_equipment = _json("res://data/actors/equipment.json")
	var previews: Array = registry.get("previewModels", [])
	_expect(not previews.is_empty(), "the registry lists a preview race")

	var subjects: Array[String] = []
	for entry: Variant in previews:
		subjects.append(str(entry))
	subjects.append_array(COMPARISON)

	for model_id: String in subjects:
		await _shoot_angles(model_id)
	for entry: Variant in previews:
		await _shoot_appearance(str(entry))
		await _shoot_motion(str(entry))
	_finish()


## Build the preview actor the creation panel would build, for a model id
## rather than for an actor type: a preview race has no actor type to look up.
func _pose(model_id: String, appearance: Dictionary,
		dressed: bool = false) -> ReplicatedActor3D:
	var previous: ReplicatedActor3D = _main.get("preview_actor") as ReplicatedActor3D
	if is_instance_valid(previous):
		previous.free()
	var actor := ReplicatedActor3D.new()
	(_main.get("preview_root") as Node3D).add_child(actor)
	_main.set("preview_actor", actor)
	var config: Dictionary = _models.get(model_id, {}) as Dictionary
	var animation: Dictionary = _json(str(config.get("animationMap", "")))
	# The creation panel dresses the preview in generic equipment over the top
	# of the race's own wardrobe.  That is the right default for a player
	# choosing a character and the wrong one for reviewing a race, because the
	# garments it hides are the ones this race authored; `dressed` renders it
	# both ways.
	var visuals: Dictionary = {}
	if dressed:
		visuals = {
			AppearanceVariants.PART_PANTS: int(appearance.get("pants", 0)),
			AppearanceVariants.PART_SHIRT: int(appearance.get("shirt", 0)),
			AppearanceVariants.PART_BOOTS: int(appearance.get("boots", 0))}
	var dto := {"actor_id": 0, "x": 0, "y": 0, "rotation": 0, "kind": 1,
		"name": "Preview", "appearance": appearance,
		"equipment_visuals": visuals}
	var errors := actor.configure(dto, CoordinateAdapter.new(
		{"walkingHeight": 0.0}), config, animation, _equipment)
	_expect(errors.is_empty(), model_id + " configures cleanly: " + str(errors))
	return actor


## What the actor actually occupies, ignoring the selection ring, health bar
## and map dot, which are UI in world space and would otherwise decide the
## framing.
func _bounds(actor: ReplicatedActor3D) -> AABB:
	var box := AABB()
	var started := false
	for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node as MeshInstance3D
		if mesh_node.name in ["SelectionRing", "HealthBarBackground",
				"HealthBarFill", "MapDot"]:
			continue
		var world: AABB = mesh_node.global_transform * mesh_node.get_aabb()
		box = world if not started else box.merge(world)
		started = true
	return box


## The panel's own camera always looks at a fixed waist-height point at a
## distance the player drags, which frames a figure differently at every yaw
## and cannot frame a head at all.  Framing off the actor's own bounds instead
## keeps one framing across every angle and every model, which is the whole
## point of a comparison sheet.
func _frame(actor: ReplicatedActor3D, yaw: float, head: bool = false) -> void:
	var camera: Camera3D = _main.get("preview_camera") as Camera3D
	var box := _bounds(actor)
	var focus: Vector3 = box.get_center()
	var distance: float = box.size.y * 1.28
	if head:
		focus = Vector3(box.position.x + box.size.x * .5,
			box.end.y - box.size.y * .075, box.position.z + box.size.z * .5)
		distance = box.size.y * .21
	camera.position = focus + Vector3(sin(yaw) * distance,
		distance * (.03 if head else .10), cos(yaw) * distance)
	camera.look_at(focus)


func _shoot_angles(model_id: String) -> void:
	var actor := _pose(model_id, _appearance(0))
	for _frame_index: int in range(2):
		await process_frame
	for label: String in ANGLES:
		_frame(actor, float(ANGLES[label]))
		await _capture("%s-%s.png" % [model_id, label])
	_frame(actor, 3.3416, true)
	await _capture("%s-head.png" % model_id)
	actor = _pose(model_id, _appearance(0), true)
	for _frame_index: int in range(2):
		await process_frame
	_frame(actor, 3.7416)
	await _capture("%s-equipped.png" % model_id)


func _shoot_appearance(model_id: String) -> void:
	for variant: int in range(4):
		var actor := _pose(model_id, _appearance(variant))
		for _frame_index: int in range(2):
			await process_frame
		_frame(actor, 3.6416)
		await _capture("%s-appearance-%d.png" % [model_id, variant])


func _shoot_motion(model_id: String) -> void:
	var actor := _pose(model_id, _appearance(0))
	for _frame_index: int in range(2):
		await process_frame
	_frame(actor, 3.7416)
	var player: AnimationPlayer = actor.animation_player
	_expect(player != null, model_id + " has an animation player")
	if player == null:
		return
	for clip: String in CLIPS:
		if not player.has_animation(clip):
			_expect(false, model_id + " is missing clip " + clip)
			continue
		player.play(clip)
		player.seek(player.get_animation(clip).length * 0.35, true)
		await _capture("%s-clip-%s.png" % [model_id, clip.to_lower()])


func _appearance(variant: int) -> Dictionary:
	return {"skin": variant, "hair": variant, "eyes": variant,
		"shirt": variant, "pants": variant, "boots": variant, "head": variant}


func _capture(file_name: String) -> void:
	for _frame: int in range(3):
		await process_frame
	RenderingServer.force_draw(false)
	var texture: ViewportTexture = _viewport.get_texture()
	if texture == null:
		_expect(false, "preview texture is available for " + file_name)
		return
	var image: Image = texture.get_image()
	_expect(image != null and not image.is_empty(), "rendered " + file_name)
	if image == null or image.is_empty():
		return
	var colours: Dictionary = {}
	var stride: int = 4 if file_name.ends_with("-head.png") else 12
	for y: int in range(0, image.get_height(), stride):
		for x: int in range(0, image.get_width(), stride):
			colours[image.get_pixel(x, y).to_html()] = true
	_expect(colours.size() >= 32, file_name + " contains model detail")
	_expect(image.save_png(_artifact_directory.path_join(file_name)) == OK,
		"saved " + file_name)


func _expect(condition: bool, label: String) -> void:
	if condition:
		print("ok   " + label)
	else:
		_failures += 1
		print("FAIL " + label)


func _finish() -> void:
	print("human race render: %s (%d failures)"
		% ["PASS" if _failures == 0 else "FAIL", _failures])
	quit(1 if _failures > 0 else 0)


static func _json(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed if parsed is Dictionary else {}
