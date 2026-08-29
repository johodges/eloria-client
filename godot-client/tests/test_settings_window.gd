extends SceneTree
## Guards the tabbed settings window and the key-rebinding UI.
##
## The client had one flat panel and 26 fixed input actions that could not be
## rebound at all. Everything here is about this machine and this screen: the
## gameplay tab sends the server's own commands rather than deciding anything,
## and nothing else leaves the client.

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	root.size = Vector2i(1280, 720)
	var main: Control = (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	(main.get_node("GameView") as Control).show()
	(main.get_node("LoginPanel") as Control).hide()
	var window: Control = main.get("settings_window") as Control
	var panel: PanelContainer = window.get_node("SettingsWindow") as PanelContainer
	var resource_rail: Control = main.get_node("GameView/ResourceHud") as Control
	await process_frame

	_expect(not panel.visible, "the settings window starts closed")
	main.call("_on_more_settings_pressed")
	await process_frame
	_expect(panel.visible, "the settings button opens it")
	_expect((window.call("tab_titles") as Array)
			== ["Graphics", "Camera", "Gameplay", "Controls"],
		"it is tabbed: %s" % str(window.call("tab_titles")))
	var rect: Rect2 = panel.get_global_rect()
	_expect(rect.position.x >= 0.0 and rect.position.y >= 0.0
		and rect.end.x <= 1280.0 and rect.end.y <= 720.0
		and not rect.intersects(resource_rail.get_global_rect()),
		"it fits 1280x720 clear of the resource rail: %s" % rect)

	# Every bindable action exists, so no row can be dead.
	for group: Variant in window.get("BINDABLE"):
		for action: Variant in (window.get("BINDABLE") as Dictionary)[group]:
			_expect(InputMap.has_action(str(action)),
				"%s is a real action" % str(action))

	# Rebinding, through the same path a key press takes.
	var original: Array[InputEvent] = InputMap.action_get_events("toggle_sit")
	window.call("begin_capture", "toggle_sit")
	_expect(str(window.get("capturing")) == "toggle_sit",
		"the window is waiting for a key")
	var pressed := InputEventKey.new()
	pressed.pressed = true
	pressed.physical_keycode = KEY_F9
	pressed.shift_pressed = true
	main.call("_unhandled_input", pressed)
	await process_frame
	_expect(str(window.get("capturing")).is_empty(),
		"the capture ends when a key arrives")
	var rebound: Array[InputEvent] = InputMap.action_get_events("toggle_sit")
	_expect(rebound.size() == 1
		and (rebound[0] as InputEventKey).physical_keycode == KEY_F9
		and (rebound[0] as InputEventKey).shift_pressed,
		"the action now answers the key that was pressed, modifiers included")
	var stored: Dictionary = window.call("stored_bindings") as Dictionary
	_expect(str(stored.get("toggle_sit", "")) == "Shift+F9",
		"the binding is stored as text a settings file can hold: %s"
			% str(stored.get("toggle_sit", "")))

	# Escape keeps what was there.
	window.call("begin_capture", "toggle_sit")
	var escape := InputEventKey.new()
	escape.pressed = true
	escape.physical_keycode = KEY_ESCAPE
	main.call("_unhandled_input", escape)
	await process_frame
	_expect((InputMap.action_get_events("toggle_sit")[0] as InputEventKey
			).physical_keycode == KEY_F9,
		"Escape keeps the binding rather than clearing it")

	# And a stored set comes back.
	InputMap.action_erase_events("toggle_sit")
	InputMap.action_add_event("toggle_sit", original[0] if not original.is_empty()
		else InputEventKey.new())
	window.call("restore_bindings", {"toggle_sit": "Ctrl+F8"})
	var restored: InputEventKey = InputMap.action_get_events(
		"toggle_sit")[0] as InputEventKey
	_expect(restored.physical_keycode == KEY_F8 and restored.ctrl_pressed
		and not restored.shift_pressed,
		"a stored binding is read back exactly")
	_expect(int(window.call("restore_bindings", {"not_an_action": "F1"})) == 0,
		"a stored binding for an action that no longer exists is skipped")
	# A settings file an older build wrote could hold something this build
	# cannot read. That must leave the action alone, not unbind it.
	window.call("restore_bindings", {"toggle_sit": "", "toggle_map": "nonsense"})
	_expect(not InputMap.action_get_events("toggle_sit").is_empty()
		and not InputMap.action_get_events("toggle_map").is_empty(),
		"an unreadable stored binding leaves the action exactly as it was")

	# The presentation switches actually change what is drawn.
	var effects_before: int = (main.get("world_effects") as Array).size()
	main.call("_on_client_setting_changed", "Graphics", "particles", false)
	var app_state: Node = root.get_node("/root/AppState")
	app_state.set("authenticated", true)
	app_state.call("_on_packet", 51, _hex(
		"5b00020004000000000001000001020304050b001e14071400120001416c696365"
		+ "000040ff0600"))
	main.call("_sync_world")
	await process_frame
	app_state.call("_on_packet", 79, PackedByteArray([17, 0x5b, 0]))
	await process_frame
	_expect((main.get("world_effects") as Array).size() == effects_before,
		"turning effects off stops them being drawn at all")
	main.call("_on_client_setting_changed", "Graphics", "particles", true)
	app_state.call("_on_packet", 79, PackedByteArray([17, 0x5b, 0]))
	await process_frame
	_expect((main.get("world_effects") as Array).size() > effects_before,
		"and turning them back on restores them")

	main.call("_on_client_setting_changed", "Camera", "rotation_sensitivity", 0.5)
	_expect(is_equal_approx(
		float((main.get("camera_rig") as Node).get("rotation_sensitivity")), 0.5),
		"a camera slider reaches the camera")

	# Cancel closes it like every other window.
	var cancel: InputEventKey = InputMap.action_get_events(
		"cancel")[0].duplicate() as InputEventKey
	cancel.pressed = true
	main.call("_unhandled_input", cancel)
	await process_frame
	_expect(not panel.visible, "cancel closes the settings window")

	print("settings window tests: ",
		"PASS" if failures == 0 else "FAIL (%d)" % failures)
	main.queue_free()
	await process_frame
	quit(failures)

func _hex(value: String) -> PackedByteArray:
	var bytes := PackedByteArray()
	for index: int in range(0, value.length(), 2):
		bytes.append(value.substr(index, 2).hex_to_int())
	return bytes

func _expect(value: bool, label: String) -> bool:
	if not value:
		failures += 1
		push_error("FAIL: " + label)
	return value
