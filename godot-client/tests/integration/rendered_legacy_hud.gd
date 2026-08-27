extends SceneTree

const SCREEN_SIZE := Vector2i(1280, 720)

var _artifact_directory := ""
var _failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_artifact_directory = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifact_directory.is_empty():
		_artifact_directory = ProjectSettings.globalize_path("res://test-artifacts/four-gates")
	_expect(DirAccess.make_dir_recursive_absolute(_artifact_directory) == OK,
		"artifact directory is writable")
	root.size = SCREEN_SIZE
	var scene_resource: Resource = load("res://src/app/main.tscn")
	_expect(scene_resource is PackedScene, "main HUD scene loads")
	if not scene_resource is PackedScene:
		_finish()
		return
	var main: Control = (scene_resource as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	(main.get_node("LoginBackground") as TextureRect).hide()
	(main.get_node("LoginPanel") as Control).hide()
	(main.get_node("GameView") as Control).show()
	var app_state: Node = root.get_node("AppState")
	app_state.set("authenticated", true)
	app_state.set("local_actor_id", 99)
	app_state.set("actors", {99: {
		"actor_id": 99, "x": 0, "y": 0, "rotation": 0, "actor_type": 1,
		"kind": 1, "name": "Ari", "health": 72, "max_health": 100,
		"alive": true, "sitting": false}})
	app_state.set("stats", {
		"health": 72, "max_health": 100, "ether": 33, "max_ether": 50,
		"action_points": 18, "max_action_points": 30, "food": 42,
		"carried": 205, "capacity": 320,
		"attack": 24, "defense": 21, "harvesting": 8, "alchemy": 12,
		"magic": 17, "potion": 9, "summoning": 4, "manufacturing": 14,
		"crafting": 11, "engineering": 3, "tailoring": 6, "ranging": 19,
		"overall": 22, "harvesting_base_level": 8,
		"harvesting_experience": 1480, "harvesting_experience_next": 2066})
	var chat_lines: Array = app_state.get("chat_lines") as Array
	chat_lines.clear()
	chat_lines.append({"channel": 3, "text": "Welcome to Four Gates."})
	chat_lines.append({"channel": 0, "text": "Legacy HUD layout ready."})
	app_state.set("game_minute", 91)
	app_state.set("game_minute_anchor_msec", Time.get_ticks_msec())
	main.call("_sync_world")
	main.call("_sync_stats")
	main.call("_sync_chat")
	for unused_frame: int in range(12):
		await process_frame
	var bottom_meters: HBoxContainer = main.get_node("%BottomMeters") as HBoxContainer
	_expect(bottom_meters.get_child(0).name == "ManaMeter"
		and bottom_meters.get_child(1).name == "FoodMeter"
		and bottom_meters.get_child(5).name == "ExperienceMeter",
		"lower HUD uses EL meter order")
	_expect((main.get_node("%FoodBottom") as ProgressBar).value == 42.0,
		"food meter is server driven")
	_expect((main.get_node("%OverheadPlayerName") as Label).text == "Ari",
		"zoom-stable player name is above overhead meters")
	main.call("_on_floating_feedback_requested", {
		"kind": "experience", "skill": "harvesting", "amount": 12})
	await _capture("legacy-hud.png")
	main.call("_open_actor_hud_menu", Vector2(510.0, 300.0))
	await _capture("legacy-hud-context-menu.png")
	_finish()

func _capture(file_name: String) -> void:
	for unused_frame: int in range(4):
		await process_frame
	RenderingServer.force_draw(false)
	var image_value: Variant = root.get_texture().get_image()
	if not image_value is Image:
		_expect(false, "rendered HUD screenshot is available")
		return
	var image: Image = image_value as Image
	_expect(not image.is_empty() and image.get_size() == SCREEN_SIZE,
		"rendered HUD screenshot has reference dimensions")
	var sampled_colors: Dictionary = {}
	for y: int in range(0, image.get_height(), 16):
		for x: int in range(0, image.get_width(), 16):
			sampled_colors[image.get_pixel(x, y).to_html()] = true
	_expect(sampled_colors.size() >= 48, "rendered HUD contains visual detail")
	_expect(image.save_png(_artifact_directory.path_join(file_name)) == OK,
		"saved " + file_name)

func _expect(condition: bool, message: String) -> void:
	if condition:
		print("PASS: ", message)
		return
	_failures += 1
	push_error("FAIL: " + message)

func _finish() -> void:
	var app_state: Node = root.get_node_or_null("AppState")
	if app_state != null:
		app_state.set("authenticated", false)
		app_state.set("local_actor_id", -1)
		(app_state.get("actors") as Dictionary).clear()
		(app_state.get("stats") as Dictionary).clear()
		(app_state.get("chat_lines") as Array).clear()
	print("rendered legacy HUD: ", "PASS" if _failures == 0 else "FAIL")
	quit(_failures)
