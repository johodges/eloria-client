extends SceneTree
## Guards the HUD settings that survive a session.
##
## The minimap's position and scale were persisted but its visibility was not,
## so every session began with the map hidden and Alt+M was the only way back.
## These assertions run two fresh scene instances so the setting is proved to
## travel through the settings file rather than through a live variable.

const SETTINGS_PATH := "user://eloria_hud.cfg"

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	root.size = Vector2i(1280, 720)
	var saved: Dictionary = _read_settings()

	var first: Node = (load("res://src/app/main.tscn") as PackedScene).instantiate()
	root.add_child(first)
	await process_frame
	var first_minimap: Control = first.get_node("GameView/MinimapFrame") as Control
	_expect(not first_minimap.visible, "the minimap ships hidden")
	first.call("_toggle_minimap")
	_expect(first_minimap.visible and bool(first.get("_minimap_visible")),
		"showing the minimap records that it is visible")
	var stored := ConfigFile.new()
	_expect(stored.load(SETTINGS_PATH) == OK
		and bool(stored.get_value("hud", "minimap_visible", false)),
		"showing the minimap writes its visibility to the settings file")
	first.queue_free()
	await process_frame

	# A second instance must come back with the minimap visible without the
	# player pressing Alt+M again.
	var second: Node = (load("res://src/app/main.tscn") as PackedScene).instantiate()
	root.add_child(second)
	await process_frame
	var second_minimap: Control = second.get_node("GameView/MinimapFrame") as Control
	_expect(bool(second.get("_minimap_visible")),
		"a new session loads the remembered minimap visibility")
	_expect(not second_minimap.visible,
		"the minimap stays hidden while the login screen is up")
	second.call("_on_login_succeeded")
	await process_frame
	_expect(second_minimap.visible,
		"entering the world restores the remembered visible minimap")
	var map_viewport: SubViewport = second.get_node("%MapViewport")
	_expect(map_viewport.render_target_update_mode != SubViewport.UPDATE_ALWAYS,
		"restoring the minimap does not put its viewport back on continuous redraw")
	second.call("_toggle_minimap")
	_expect(not second_minimap.visible and not bool(second.get("_minimap_visible")),
		"hiding the minimap records that it is hidden")
	var rehidden := ConfigFile.new()
	_expect(rehidden.load(SETTINGS_PATH) == OK
		and not bool(rehidden.get_value("hud", "minimap_visible", true)),
		"hiding the minimap is persisted too, not just showing it")
	second.queue_free()
	await process_frame

	_restore_settings(saved)
	print("hud persistence tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)

func _read_settings() -> Dictionary:
	var config := ConfigFile.new()
	if config.load(SETTINGS_PATH) != OK:
		return {}
	var values: Dictionary = {}
	for section: String in config.get_sections():
		for key: String in config.get_section_keys(section):
			values[section + "/" + key] = config.get_value(section, key)
	return values

func _restore_settings(values: Dictionary) -> void:
	var config := ConfigFile.new()
	for path: String in values:
		config.set_value(path.get_slice("/", 0), path.get_slice("/", 1), values[path])
	config.save(SETTINGS_PATH)

func _expect(value: bool, label: String) -> void:
	if value:
		return
	failures += 1
	push_error("FAIL: " + label)
