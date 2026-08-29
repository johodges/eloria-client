extends SceneTree
## Guards the reference windows.
##
## Help is generated from the client's own input map and console table rather
## than written out, so it cannot drift from what the keys and commands
## actually are. Links collects what the server said and invents nothing.
## Notes belong to the player and never leave the machine.

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
	var app_state: Node = root.get_node("/root/AppState")
	var window: Control = main.get("reference_window") as Control
	var panel: PanelContainer = window.get_node("ReferenceWindow") as PanelContainer
	var resource_rail: Control = main.get_node("GameView/ResourceHud") as Control
	await process_frame

	_expect(not panel.visible, "the reference window starts closed")
	main.call("_on_reference_pressed")
	await process_frame
	_expect(panel.visible, "the button opens it")
	_expect((window.call("tab_titles") as Array)
			== ["Help", "Notes", "Links", "Encyclopedia"],
		"it carries the four pages: %s" % str(window.call("tab_titles")))
	var rect: Rect2 = panel.get_global_rect()
	_expect(rect.position.x >= 0.0 and rect.position.y >= 0.0
		and rect.end.x <= 1280.0 and rect.end.y <= 720.0
		and not rect.intersects(resource_rail.get_global_rect()),
		"it fits 1280x720 clear of the resource rail: %s" % rect)

	# Help is generated, so it says what the keys and commands really are.
	var help: RichTextLabel = window.get_node(
		"ReferenceWindow/ReferenceBody/ReferenceTabs/Help/HelpScroll/HelpText"
		) as RichTextLabel
	_expect(help != null and help.text.contains("toggle inventory")
		and help.text.contains("#calc"),
		"help lists both a bound key and a console command")
	for command: Variant in ConsoleCommands.COMMANDS:
		_expect(help.text.contains(str(command)),
			"help lists %s" % str(command))
	# Rebinding changes the help, because the help is read from the bindings.
	# The original is put back below: these suites share one settings file,
	# and a test that leaves a key moved breaks the next one.
	var original: Array[InputEvent] = InputMap.action_get_events(
		"toggle_inventory").duplicate()
	var before: String = help.text
	var settings: Control = main.get("settings_window") as Control
	settings.call("begin_capture", "toggle_inventory")
	var pressed := InputEventKey.new()
	pressed.pressed = true
	pressed.physical_keycode = KEY_F7
	main.call("_unhandled_input", pressed)
	await process_frame
	_expect(help.text != before and help.text.contains("F7"),
		"a rebound key shows up in the help without anyone editing it")

	# Links: what the server said, once each, nothing invented.
	app_state.call("_on_packet", 0, _line("Toran: the roads are at https://eloria.example/roads today"))
	app_state.call("_on_packet", 0, _line("Salina: mirror of https://eloria.example/roads"))
	app_state.call("_on_packet", 0, _line("Pell: nothing to see here"))
	await process_frame
	var links: Array = window.call("known_links") as Array
	_expect(links.size() == 1 and str(links[0]) == "https://eloria.example/roads",
		"an address said twice is listed once, and a line without one adds"
			+ " nothing: %s" % str(links))
	_expect(ConsoleCommands.urls_in("see www.eloria.example/a, then go").size() == 1,
		"a bare www address is found and its trailing comma is not part of it")
	_expect(ConsoleCommands.urls_in("no address here").is_empty(),
		"and a line with none finds none")

	# Notes belong to the player and are kept.
	var notes: TextEdit = window.get_node(
		"ReferenceWindow/ReferenceBody/ReferenceTabs/Notes/NotesEdit") as TextEdit
	notes.text = "Reed bank is north of the falls."
	window.call("_on_notes_changed")
	await process_frame
	var config := ConfigFile.new()
	_expect(config.load(str(main.get("SETTINGS_PATH"))) == OK
		and str(config.get_value("notes", "text", "")).contains("Reed bank"),
		"the note is written to the client's own settings file")

	# The encyclopedia is real content, not an empty shell.
	_expect(int(window.call("entry_count")) >= 5,
		"the encyclopedia has entries: %d" % int(window.call("entry_count")))
	var body: RichTextLabel = window.get_node(
		"ReferenceWindow/ReferenceBody/ReferenceTabs/Encyclopedia/EntryBody"
		) as RichTextLabel
	_expect(not body.text.strip_edges().is_empty(),
		"and shows one when the window opens")
	window.call("_show_entry", 1)
	_expect(body.text != "" and body.text.length() > 80,
		"selecting another entry shows its text")

	InputMap.action_erase_events("toggle_inventory")
	for event: InputEvent in original:
		InputMap.action_add_event("toggle_inventory", event)
	main.call("_save_hud_settings")
	_expect(not InputMap.action_get_events("toggle_inventory").is_empty(),
		"the key this suite moved is put back for the next one")

	var cancel: InputEventKey = InputMap.action_get_events(
		"cancel")[0].duplicate() as InputEventKey
	cancel.pressed = true
	main.call("_unhandled_input", cancel)
	await process_frame
	_expect(not panel.visible, "cancel closes it")

	print("reference window tests: ",
		"PASS" if failures == 0 else "FAIL (%d)" % failures)
	main.queue_free()
	await process_frame
	quit(failures)

func _line(text: String) -> PackedByteArray:
	var bytes := PackedByteArray([0])
	bytes.append_array(text.to_utf8_buffer())
	bytes.append(0)
	return bytes

func _expect(value: bool, label: String) -> bool:
	if not value:
		failures += 1
		push_error("FAIL: " + label)
	return value
