extends SceneTree

var failures: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var scene_resource: Resource = load("res://src/app/main.tscn")
	_expect(scene_resource is PackedScene, "main scene loads")
	if not scene_resource is PackedScene:
		quit(failures)
		return
	var main: Control = (scene_resource as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	var game_view: Control = main.get_node("GameView") as Control
	var login_panel: Control = main.get_node("LoginPanel") as Control
	var new_character: Button = main.get_node("LoginPanel/Content/NewCharacter") as Button
	var status: Label = main.get_node("LoginPanel/Content/Status") as Label
	var container: SubViewportContainer = main.get_node("GameView/ViewportContainer") as SubViewportContainer
	var camera_rig: IsometricCameraController = main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot/CameraRig") as IsometricCameraController
	game_view.show()
	_expect(container.mouse_filter == Control.MOUSE_FILTER_STOP,
		"world viewport receives gameplay mouse input")
	_expect(container.gui_input.is_connected(Callable(main, "_on_world_gui_input")),
		"world viewport input handler is connected")
	var viewport_rect: Rect2 = root.get_visible_rect()
	_expect(viewport_rect.encloses(login_panel.get_global_rect()),
		"login panel fits the reference viewport")
	_expect(viewport_rect.encloses(new_character.get_global_rect()),
		"create-character action is visible")
	_expect(viewport_rect.encloses(status.get_global_rect()), "login status is visible")
	var host: LineEdit = main.get_node("LoginPanel/Content/Host") as LineEdit
	_expect(host.text == "18.235.240.60", "development server is the default endpoint")
	var creation_panel: Control = main.get_node("CreationPanel") as Control
	var create_button: Button = main.get_node(
		"CreationPanel/Columns/Form/Actions/Create") as Button
	var back_button: Button = main.get_node(
		"CreationPanel/Columns/Form/Actions/Back") as Button
	login_panel.hide()
	creation_panel.show()
	await process_frame
	_expect(viewport_rect.encloses(creation_panel.get_global_rect()),
		"character-creation panel fits the reference viewport")
	_expect(viewport_rect.encloses(create_button.get_global_rect()),
		"create-character submit action is visible")
	_expect(viewport_rect.encloses(back_button.get_global_rect()),
		"character-creation back action is visible")
	creation_panel.hide()
	game_view.show()

	var right_down: InputEventMouseButton = InputEventMouseButton.new()
	right_down.button_index = MOUSE_BUTTON_RIGHT
	right_down.pressed = true
	main.call("_on_world_gui_input", right_down)
	var motion: InputEventMouseMotion = InputEventMouseMotion.new()
	motion.relative = Vector2(40.0, 12.0)
	var initial_yaw: float = camera_rig.yaw_degrees
	main.call("_on_world_gui_input", motion)
	_expect(not is_equal_approx(camera_rig.yaw_degrees, initial_yaw),
		"right drag rotates camera")
	var right_up: InputEventMouseButton = InputEventMouseButton.new()
	right_up.button_index = MOUSE_BUTTON_RIGHT
	right_up.pressed = false
	main.call("_on_world_gui_input", right_up)

	var wheel: InputEventMouseButton = InputEventMouseButton.new()
	wheel.button_index = MOUSE_BUTTON_WHEEL_UP
	wheel.pressed = true
	var initial_distance: float = camera_rig.distance
	main.call("_on_world_gui_input", wheel)
	_expect(camera_rig.distance < initial_distance, "mouse wheel zooms camera")

	var middle_down: InputEventMouseButton = InputEventMouseButton.new()
	middle_down.button_index = MOUSE_BUTTON_MIDDLE
	middle_down.pressed = true
	main.call("_on_world_gui_input", middle_down)
	var pan_motion: InputEventMouseMotion = InputEventMouseMotion.new()
	pan_motion.relative = Vector2(25.0, -10.0)
	main.call("_on_world_gui_input", pan_motion)
	_expect(camera_rig.pan_offset.length() > 0.0, "middle drag pans camera")

	print("world input tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	main.queue_free()
	await process_frame
	quit(failures)

func _expect(value: bool, label: String) -> void:
	if value:
		return
	failures += 1
	push_error("FAIL: " + label)
