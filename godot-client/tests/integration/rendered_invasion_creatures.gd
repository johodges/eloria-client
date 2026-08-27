extends SceneTree

const SCREEN_SIZE := Vector2i(1280, 720)
const ROSTER: Array[Dictionary] = [
	{"actor_type": 400, "slug": "mirrorfin_otter", "label": "Mirrorfin Otter"},
	{"actor_type": 401, "slug": "reedhorn_stag", "label": "Reedhorn Stag"},
	{"actor_type": 402, "slug": "gate_turtle", "label": "Four Gates Turtle"},
	{"actor_type": 403, "slug": "lakeglass_drake", "label": "Lakeglass Drake"},
	{"actor_type": 404, "slug": "snowcrest_hare", "label": "Snowcrest Hare"},
	{"actor_type": 405, "slug": "glacier_ram", "label": "Glacier Ram"},
	{"actor_type": 406, "slug": "iceback_ursid", "label": "Iceback Ursid"},
	{"actor_type": 407, "slug": "rimeclaw", "label": "Rimeclaw"},
	{"actor_type": 408, "slug": "crystal_mite", "label": "Crystal Mite"},
	{"actor_type": 409, "slug": "resonant_hound", "label": "Resonant Hound"},
	{"actor_type": 410, "slug": "stormglass_grazer", "label": "Stormglass Grazer"},
	{"actor_type": 411, "slug": "prism_wyrm", "label": "Prism Wyrm"},
	{"actor_type": 412, "slug": "dunrunner", "label": "Dunrunner"},
	{"actor_type": 413, "slug": "steppe_aurochs", "label": "Steppe Aurochs"},
	{"actor_type": 414, "slug": "sunmane_cat", "label": "Sunmane Cat"},
	{"actor_type": 415, "slug": "dustscale_drake", "label": "Dustscale Drake"},
	{"actor_type": 416, "slug": "amberhart", "label": "Amberhart"},
	{"actor_type": 417, "slug": "rootback_boar", "label": "Rootback Boar"},
	{"actor_type": 418, "slug": "moor_wisp_hound", "label": "Moor Wisp Hound"},
	{"actor_type": 419, "slug": "barrow_quillbeast", "label": "Barrow Quillbeast"},
	{"actor_type": 420, "slug": "canopy_glider", "label": "Canopy Glider"},
	{"actor_type": 421, "slug": "cenote_toader", "label": "Cenote Toader"},
	{"actor_type": 422, "slug": "scalevine_stalker", "label": "Scalevine Stalker"},
	{"actor_type": 423, "slug": "sunscale_basilisk", "label": "Sunscale Basilisk"},
	{"actor_type": 424, "slug": "mangrove_crab", "label": "Mangrove Crab"},
	{"actor_type": 425, "slug": "mudskipper_beast", "label": "Mudskipper Beast"},
	{"actor_type": 426, "slug": "delta_crocodile", "label": "Delta Crocodile"},
	{"actor_type": 427, "slug": "floodmaw", "label": "Floodmaw"},
]

var _artifact_directory := ""
var _failures := 0
var _results: Array[Dictionary] = []
var _stage: Node3D
var _camera: Camera3D
var _models: Dictionary
var _equipment: Dictionary
var _animations: Dictionary


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_artifact_directory = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifact_directory.is_empty():
		_artifact_directory = ProjectSettings.globalize_path(
			"res://test-artifacts/invasion-creatures")
	_expect(DirAccess.make_dir_recursive_absolute(_artifact_directory) == OK,
		"invasion creature artifact directory is writable")
	root.size = SCREEN_SIZE
	_models = _read_json("res://data/actors/models.json")
	_equipment = _read_json("res://data/actors/equipment.json")
	_animations = _read_json("res://data/animations/creature.json")
	_expect(not _models.is_empty(), "client model registry loads")
	_expect(not _animations.is_empty(), "creature animation mapping loads")
	_setup_stage()
	for entry: Dictionary in ROSTER:
		await _render_creature(entry)
	var report := FileAccess.open(_artifact_directory.path_join("validation.json"),
		FileAccess.WRITE)
	_expect(report != null, "invasion creature validation report is writable")
	if report != null:
		report.store_string(JSON.stringify({
			"roster": _results,
			"failures": _failures,
			"renderSize": [SCREEN_SIZE.x, SCREEN_SIZE.y],
		}, "  ") + "\n")
	print("rendered invasion creatures: ", "PASS" if _failures == 0 else "FAIL")
	quit(_failures)


func _setup_stage() -> void:
	_stage = Node3D.new()
	_stage.name = "InvasionCreatureStage"
	root.add_child(_stage)
	var world_environment := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("182129")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("c6d6df")
	environment.ambient_light_energy = 0.58
	environment.tonemap_mode = Environment.TONE_MAPPER_ACES
	world_environment.environment = environment
	_stage.add_child(world_environment)
	var key_light := DirectionalLight3D.new()
	key_light.rotation_degrees = Vector3(-48.0, -32.0, 0.0)
	key_light.light_color = Color("ffe2bd")
	key_light.light_energy = 1.25
	key_light.shadow_enabled = true
	_stage.add_child(key_light)
	var fill_light := DirectionalLight3D.new()
	fill_light.rotation_degrees = Vector3(-24.0, 138.0, 0.0)
	fill_light.light_color = Color("86ccea")
	fill_light.light_energy = 0.38
	_stage.add_child(fill_light)
	var floor := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(32.0, 32.0)
	var floor_material := StandardMaterial3D.new()
	floor_material.albedo_color = Color("343f46")
	floor_material.roughness = 0.92
	plane.material = floor_material
	floor.mesh = plane
	_stage.add_child(floor)
	_camera = Camera3D.new()
	_camera.name = "ReviewCamera"
	_camera.fov = 37.0
	_camera.current = true
	_stage.add_child(_camera)


func _render_creature(entry: Dictionary) -> void:
	var actor_type: int = int(entry.actor_type)
	var slug: String = str(entry.slug)
	var label: String = str(entry.label)
	var resolved_model: String = str((_models.get("actorTypes", {}) as Dictionary).get(
		str(actor_type), ""))
	_expect(resolved_model == slug,
		"invasion actor %d resolves to bespoke %s model" % [actor_type, slug])
	var model_config: Dictionary = (_models.get("models", {}) as Dictionary).get(
		resolved_model, {}) as Dictionary
	var actor := ReplicatedActor3D.new()
	actor.name = "Invaded_%s" % slug
	_stage.add_child(actor)
	var errors: Array[String] = actor.configure({
		"actor_id": actor_type * 100,
		"x": 0,
		"y": 0,
		"rotation": 3,
		"actor_type": actor_type,
		"kind": 3,
		"name": label,
		"enhanced": true,
	}, CoordinateAdapter.new({"walkingHeight": 0.0}), model_config, _animations,
		_equipment)
	for unused_frame: int in range(10):
		await process_frame
	_expect(errors.is_empty(), label + " imports with no client errors: " + ", ".join(errors))
	_expect(actor.get_node_or_null("NativeModel") != null,
		label + " uses the native client model path")
	_expect(actor.get_node_or_null("MissingModelFallback") == null,
		label + " never creates the magenta fallback")
	var nameplate: Label3D = actor.get_node_or_null("Nameplate") as Label3D
	if nameplate != null:
		nameplate.position.y = 2.75
	var diagnostics: Dictionary = _mesh_diagnostics(actor)
	_expect(int(diagnostics.vertices) > 5000,
		label + " exceeds the production geometry floor")
	_expect(int(diagnostics.textured_surfaces) >= 3,
		label + " exposes PBR base-color textures across primary surfaces")
	_expect(int(diagnostics.normal_surfaces) >= 3,
		label + " exposes normal maps across primary surfaces")
	var bounds: AABB = diagnostics.bounds as AABB
	_frame_actor(actor, bounds)
	for unused_frame: int in range(4):
		await process_frame
	RenderingServer.force_draw(false)
	var image: Image = root.get_texture().get_image()
	_expect(image != null and not image.is_empty() and image.get_size() == SCREEN_SIZE,
		label + " renders at the review resolution")
	var sampled_colors: Dictionary = {}
	if image != null and not image.is_empty():
		for y: int in range(80, image.get_height() - 60, 12):
			for x: int in range(120, image.get_width() - 120, 12):
				sampled_colors[image.get_pixel(x, y).to_html()] = true
		_expect(sampled_colors.size() >= 96,
			label + " rendered frame contains production material detail")
		_expect(image.save_png(_artifact_directory.path_join(
			"%03d-%s.png" % [actor_type, slug])) == OK,
			"saved invasion review for " + label)
	_results.append({
		"actorType": actor_type,
		"model": resolved_model,
		"label": label,
		"clientErrors": errors,
		"vertices": diagnostics.vertices,
		"triangles": diagnostics.triangles,
		"meshInstances": diagnostics.mesh_instances,
		"texturedSurfaces": diagnostics.textured_surfaces,
		"normalSurfaces": diagnostics.normal_surfaces,
		"bounds": {
			"position": [bounds.position.x, bounds.position.y, bounds.position.z],
			"size": [bounds.size.x, bounds.size.y, bounds.size.z],
		},
		"sampledColors": sampled_colors.size(),
	})
	actor.queue_free()
	await process_frame


func _mesh_diagnostics(actor: ReplicatedActor3D) -> Dictionary:
	var combined := AABB()
	var initialized := false
	var vertices := 0
	var triangles := 0
	var mesh_instances := 0
	var textured_surfaces := 0
	var normal_surfaces := 0
	for node_value: Node in actor.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		if mesh_node.mesh == null or mesh_node.name == "SelectionRing":
			continue
		mesh_instances += 1
		var relative: Transform3D = actor.global_transform.affine_inverse() * mesh_node.global_transform
		var mesh_bounds: AABB = relative * mesh_node.get_aabb()
		combined = combined.merge(mesh_bounds) if initialized else mesh_bounds
		initialized = true
		for surface: int in range(mesh_node.mesh.get_surface_count()):
			vertices += mesh_node.mesh.surface_get_array_len(surface)
			triangles += mesh_node.mesh.surface_get_array_index_len(surface) / 3
			var material: Material = mesh_node.get_active_material(surface)
			if material is StandardMaterial3D:
				var standard := material as StandardMaterial3D
				if standard.albedo_texture != null:
					textured_surfaces += 1
				if standard.normal_enabled and standard.normal_texture != null:
					normal_surfaces += 1
	return {
		"bounds": combined,
		"vertices": vertices,
		"triangles": triangles,
		"mesh_instances": mesh_instances,
		"textured_surfaces": textured_surfaces,
		"normal_surfaces": normal_surfaces,
	}


func _frame_actor(actor: ReplicatedActor3D, bounds: AABB) -> void:
	var target: Vector3 = actor.global_transform * bounds.get_center()
	var extent: float = maxf(bounds.size.x, maxf(bounds.size.y, bounds.size.z))
	var distance: float = maxf(3.3, extent * 1.55)
	_camera.global_position = target + Vector3(distance * .72, distance * .34, -distance)
	_camera.look_at(target + Vector3(0.0, bounds.size.y * .04, 0.0), Vector3.UP)


func _read_json(path: String) -> Dictionary:
	var text: String = FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(text)
	return parsed as Dictionary if parsed is Dictionary else {}


func _expect(condition: bool, message: String) -> void:
	if condition:
		print("PASS: ", message)
		return
	_failures += 1
	push_error("FAIL: " + message)
