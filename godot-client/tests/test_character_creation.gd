extends SceneTree
## Exercise the real selectors, rendered skin materials, and creation bytes.

var failures := 0
var checks := 0

func _init() -> void:
	call_deferred("run")

func expect(ok: bool, message: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		push_error(message)

func choose(control: OptionButton, index: int) -> void:
	control.select(index)
	control.item_selected.emit(index)

func run() -> void:
	root.size = Vector2i(1280, 720)
	var main := (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	main.get_node("%LoginPanel").hide()
	main.get_node("%CreationPanel").show()
	var race := main.get_node("%CreateRace") as OptionButton
	var sex := main.get_node("%CreateGender") as OptionButton
	var skin := main.get_node("%CreateSkin") as OptionButton
	var hair := main.get_node("%CreateHair") as OptionButton
	var eyes := main.get_node("%CreateEyes") as OptionButton
	expect(race.item_count == 8 and sex.item_count == 2, "eight races and two separate sex choices")
	expect(race.get_item_text(race.selected) == "Human" and sex.get_selected_id() == 0, "Human replaces Luminous and retains the initial female actor")
	expect(skin.get_selected_id() == 1, "Human retains its pale beige default")
	var human_index := race.selected
	var models: Dictionary = main.get("models")
	var options: Array = main.get("creation_options")
	var actor_types: Dictionary = {}
	var previous_sex := str(sex.get_selected_metadata())
	for race_index in range(race.item_count):
		choose(race, race_index)
		var culture := str(race.get_selected_metadata())
		expect(str(sex.get_selected_metadata()) == previous_sex, "changing race preserves sex: " + culture)
		var expected_skin := 1 if culture == "luminous" else 0
		expect(skin.get_selected_id() == expected_skin, "race switch selects its default skin: " + culture)
		for sex_index in range(sex.item_count):
			choose(sex, sex_index)
			var actor_type := sex.get_selected_id()
			actor_types[actor_type] = true
			var matches := options.filter(func(option: Dictionary) -> bool: return int(option.actorType) == actor_type)
			expect(matches.size() == 1, "selected actor type exists exactly once")
			var model: Dictionary = models[matches[0].model]
			expect(model.culture == culture and model.gender == sex.get_selected_metadata(), "race and sex resolve the matching model")
			var actor := main.get("preview_actor") as ReplicatedActor3D
			expect(actor.get("_model_config") == model, "preview uses the selected race and sex")
			expect(skin.get_selected_id() == expected_skin, "sex change preserves race default")
			var look: Dictionary = main.call("_creation_appearance")
			look["actor_type"] = actor_type
			var packet := EloriaProtocol.create_character("Preview", "secret", look)
			var tail := packet.slice(packet.size() - 8)
			expect(tail[0] == expected_skin and tail[5] == actor_type, "creation bytes preserve race, sex and default skin")
			var materials: Dictionary = actor.get("_skin_materials")
			expect(not materials.is_empty(), "preview has real skin materials")
			for material: ShaderMaterial in materials.values():
				expect(bool(material.get_shader_parameter("recolor_skin")) == (expected_skin != 0), "race default keeps the authored texture")
			if sex_index == 1:
				await capture(culture)
		# Customize the skin, then change sex in both directions.
		choose(skin, skin.get_item_index(6))
		hair.select(hair.get_item_index(4))
		eyes.select(eyes.get_item_index(4))
		var customized: Dictionary = main.call("_creation_appearance")
		for sex_index in [0, 1]:
			choose(sex, sex_index)
			expect(main.call("_creation_appearance") == customized, "sex changes preserve all customized appearance values")
		# Leave Race default selected so returning to Human must choose a valid tone.
		if culture != "luminous":
			choose(skin, skin.get_item_index(0))
		previous_sex = str(sex.get_selected_metadata())
	expect(actor_types.keys().size() == 16, "all sixteen existing actor types remain selectable")
	# A customized skin must also reset on a non-human to non-human switch.
	choose(skin, skin.get_item_index(8))
	choose(race, 0)
	expect(skin.get_selected_id() == 0, "changing non-human race resets a custom skin")
	choose(race, human_index)
	expect(skin.get_selected_id() == 1 and skin.get_item_index(0) == -1, "returning to Human selects a valid human tone")
	for window_size: Vector2i in [Vector2i(1280, 720), Vector2i(1920, 1080)]:
		root.size = window_size
		for frame in range(3):
			await process_frame
		var race_rect := race.get_global_rect()
		var sex_rect := sex.get_global_rect()
		expect(is_equal_approx(race_rect.position.y, sex_rect.position.y) and race_rect.end.x <= sex_rect.position.x, "race and sex boxes sit side by side")
		expect(main.get_global_rect().encloses(race_rect) and main.get_global_rect().encloses(sex_rect), "both selectors fit the window")
	await capture("character-creation-ui")
	main.queue_free()
	await process_frame
	NativeAnimationImporter.clear()
	# Release the local material references before the renderer shuts down.
	call_deferred("finish")

func finish() -> void:
	print("CHARACTER_CREATION: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)

func capture(filename: String) -> void:
	var directory := OS.get_environment("ELORIA_CREATION_CAPTURE_DIR")
	if directory.is_empty() or DisplayServer.get_name() == "headless":
		return
	DirAccess.make_dir_recursive_absolute(directory)
	for frame in range(4):
		await process_frame
	await RenderingServer.frame_post_draw
	expect(root.get_texture().get_image().save_png(directory.path_join(filename + ".png")) == OK, "saved creation preview " + filename)
