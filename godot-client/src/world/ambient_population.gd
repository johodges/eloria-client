class_name AmbientPopulation
extends Node3D
## Spawns a map's declared ambient livestock and wildlife at runtime.
##
## These are scenery animals, not networked actors: they carry no actor id, no
## collision and no server state, so they must never be fused into the static
## world mesh where they would become part of the collision surface. Declaring
## them in the manifest and instancing them here keeps the static package clean
## while letting a region read as inhabited.
##
## Networked creatures and NPCs remain the server's business and continue to
## arrive through the normal actor path; the manifest records the placements a
## server profile should own under `runtimePopulation`.

const MODEL_CATALOG := "res://data/actors/models.json"
const NAVIGATION_LAYER := 8

var _scenes: Dictionary = {}
var _spawned: Array[Node3D] = []

func populate(manifest: WorldManifest, space: PhysicsDirectSpaceState3D) -> int:
	clear()
	var declared: Variant = manifest.data.get("ambientPopulation")
	if declared is not Dictionary:
		return 0
	var groups: Variant = (declared as Dictionary).get("groups", [])
	if groups is not Array:
		return 0
	var catalog := _load_catalog()
	var spawned := 0
	for raw_group: Variant in groups as Array:
		if raw_group is not Dictionary:
			continue
		var group: Dictionary = raw_group as Dictionary
		var scene: PackedScene = _scene_for(str(group.get("model", "")), catalog)
		if scene == null:
			push_warning("ambient population: unknown model " + str(group.get("model", "")))
			continue
		var centre: Vector3 = _vector(group.get("center", [0, 0, 0]))
		var radius: float = float(group.get("radius", 6.0))
		var count: int = int(group.get("count", 1))
		var animation: String = str(group.get("animation", "Idle_A"))
		var scale: float = float(group.get("scale", 1.0))
		var rng := RandomNumberGenerator.new()
		rng.seed = int(group.get("seed", 1))
		for index in count:
			var instance: Node3D = scene.instantiate() as Node3D
			if instance == null:
				continue
			var angle := rng.randf() * TAU
			var reach := radius * sqrt(rng.randf())
			var position := Vector3(centre.x + cos(angle) * reach, centre.y,
				centre.z + sin(angle) * reach)
			add_child(instance)
			instance.scale = Vector3.ONE * scale * rng.randf_range(0.94, 1.06)
			instance.rotation.y = rng.randf() * TAU
			instance.global_position = _grounded(position, space)
			_play(instance, animation, rng.randf() * 4.0)
			_spawned.append(instance)
			spawned += 1
	return spawned

func clear() -> void:
	for node: Node3D in _spawned:
		if is_instance_valid(node):
			node.queue_free()
	_spawned.clear()

func _grounded(position: Vector3, space: PhysicsDirectSpaceState3D) -> Vector3:
	if space == null:
		return position
	var query := PhysicsRayQueryParameters3D.create(
		Vector3(position.x, position.y + 200.0, position.z),
		Vector3(position.x, position.y - 200.0, position.z), NAVIGATION_LAYER)
	var hit := space.intersect_ray(query)
	var found: Variant = hit.get("position")
	if found is Vector3:
		return found as Vector3
	return position

func _play(instance: Node3D, animation: String, offset: float) -> void:
	var players := instance.find_children("*", "AnimationPlayer", true, false)
	if players.is_empty():
		return
	var player := players[0] as AnimationPlayer
	if not player.has_animation(animation):
		animation = "Idle_A"
	if not player.has_animation(animation):
		return
	var clip := player.get_animation(animation)
	clip.loop_mode = Animation.LOOP_LINEAR
	player.play(animation)
	# Offset each animal so a herd does not breathe in lockstep.
	player.seek(fmod(offset, maxf(clip.length, 0.1)), true)

func _load_catalog() -> Dictionary:
	var file := FileAccess.open(MODEL_CATALOG, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if parsed is not Dictionary:
		return {}
	var models: Variant = (parsed as Dictionary).get("models", {})
	return models as Dictionary if models is Dictionary else {}

func _scene_for(model: String, catalog: Dictionary) -> PackedScene:
	if model.is_empty():
		return null
	if _scenes.has(model):
		return _scenes[model] as PackedScene
	var entry: Variant = catalog.get(model)
	if entry is not Dictionary:
		return null
	var path: String = str((entry as Dictionary).get("scene", ""))
	if path.is_empty() or not ResourceLoader.exists(path):
		return null
	# Godot imports a .glb as a PackedScene, which is what the actor runtime
	# already loads these models as.
	var packed: PackedScene = load(path) as PackedScene
	if packed == null:
		push_warning("ambient population: %s did not import as a PackedScene" % path)
		return null
	_scenes[model] = packed
	return packed

static func _vector(value: Variant) -> Vector3:
	if value is Array and (value as Array).size() >= 3:
		var values: Array = value as Array
		return Vector3(float(values[0]), float(values[1]), float(values[2]))
	return Vector3.ZERO
