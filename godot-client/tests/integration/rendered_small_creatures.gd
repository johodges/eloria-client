extends SceneTree
## Compare the real creature bodies with their original import size and check
## that health/name anchors follow the larger body through server scale changes.
var failures := 0
var models: Dictionary
var stage: Node3D
var adapter := CoordinateAdapter.new()

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	root.size = Vector2i(1280, 720)
	models = (JSON.parse_string(FileAccess.get_file_as_string(
		"res://data/actors/models.json")) as Dictionary).models
	stage = Node3D.new()
	root.add_child(stage)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("665b46")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = 0.7
	stage.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-45, -30, 0)
	stage.add_child(light)
	var camera := Camera3D.new()
	camera.cull_mask = 3
	camera.position = Vector3(0, 5, 10)
	stage.add_child(camera)
	camera.look_at(Vector3(0, 0.8, 0))
	camera.current = true
	var index := 0
	for species: String in ["rabbit", "squirrel", "red_fox", "black_bear"]:
		var original := _actor(species, 2)
		var enlarged := _actor(species, 5)
		original.position = Vector3(-3.3 + index * 2.2, 0, -1)
		enlarged.position = Vector3(-3.3 + index * 2.2, 0, 1)
		var original_model := original.get_node("NativeModel") as Node3D
		var enlarged_model := enlarged.get_node("NativeModel") as Node3D
		var multiplier := 1.0 if species == "black_bear" else 2.0
		_expect(enlarged_model.scale.is_equal_approx(original_model.scale * multiplier),
			"%s body scale: %.1fx" % [species, multiplier])
		var initial_height := enlarged.head_height()
		enlarged.set_server_scale(3.0)
		_expect(enlarged_model.scale.is_equal_approx(original_model.scale * multiplier * 3),
			"%s server scaling preserves the species boost" % species)
		enlarged.set_server_scale(1.0)
		_expect(is_equal_approx(initial_height, enlarged.head_height()),
			"%s restores its body height without compounding the boost" % species)
		var nameplate := enlarged.get_node("Nameplate") as Label3D
		_expect(is_equal_approx(nameplate.position.y,
			enlarged.head_height() + ReplicatedActor3D.NAMEPLATE_CLEARANCE),
			"%s label clears its enlarged body" % species)
		_expect(nameplate.modulate == Color.YELLOW and not nameplate.shaded,
			"%s uses full-bright yellow text" % species)
		_expect(nameplate.outline_modulate == Color.BLACK,
			"%s uses an opaque black outline" % species)
		enlarged.set_overhead_fade(0.5)
		_expect(is_equal_approx(nameplate.modulate.a, 0.5), "distance fade still applies")
		enlarged.set_overhead_fade(1.0)
		index += 1
	var invasion := _actor("rabbit", 5, 14)
	_expect((invasion.get_node("Nameplate") as Label3D).modulate
		== EloriaProtocol.el_text_colour(14), "invasion names retain their server color")
	invasion.queue_free()
	if DisplayServer.get_name() != "headless":
		for frame: int in range(16):
			await process_frame
		await RenderingServer.frame_post_draw
		var picture := root.get_texture().get_image()
		var bright_pixels := 0
		for y: int in range(picture.get_height()):
			for x: int in range(picture.get_width()):
				var color := picture.get_pixel(x, y)
				if color.r > 0.9 and color.g > 0.9 and color.b < 0.2:
					bright_pixels += 1
		_expect(bright_pixels > 100, "render contains bright yellow creature lettering")
		var path := OS.get_environment("ELORIA_ARTIFACT_DIR")
		if not path.is_empty():
			DirAccess.make_dir_recursive_absolute(path)
			picture.save_png(path.path_join("small-creatures.png"))
	print("small creature presentation: ", "PASS" if failures == 0 else "FAIL")
	stage.queue_free()
	await process_frame
	quit(failures)

func _actor(species: String, kind: int, name_colour := 0) -> ReplicatedActor3D:
	var config: Dictionary = models[species]
	var actor := ReplicatedActor3D.new()
	stage.add_child(actor)
	var errors := actor.configure({"actor_id": stage.get_child_count(), "x": 0,
		"y": 0, "rotation": 0, "kind": kind, "name_colour": name_colour,
		"name": species.capitalize(), "health": 10, "max_health": 10}, adapter,
		config, JSON.parse_string(FileAccess.get_file_as_string(config.animationMap)))
	_expect(errors.is_empty(), "%s loads: %s" % [species, errors])
	actor.set_physics_process(false)
	actor.set_health_visible(true)
	return actor

func _expect(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)
