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
	var original_max_fps: int = Engine.max_fps

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
	var first_settings: Control = first.get("settings_window") as Control
	var fps_option: OptionButton = first_settings.find_child("fps_limit", true, false) as OptionButton
	fps_option.select(fps_option.get_item_index(120))
	fps_option.item_selected.emit(fps_option.selected)
	first.queue_free()
	await process_frame
	Engine.max_fps = 0

	# A second instance must come back with the minimap visible without the
	# player pressing Alt+M again.
	var second: Node = (load("res://src/app/main.tscn") as PackedScene).instantiate()
	root.add_child(second)
	await process_frame
	var second_settings: Control = second.get("settings_window") as Control
	var restored_fps: OptionButton = second_settings.find_child("fps_limit", true, false) as OptionButton
	_expect(Engine.max_fps == 120 and restored_fps.get_selected_id() == 120,
		"a new session applies the saved FPS limit and restores the dropdown before login")
	restored_fps.select(restored_fps.get_item_index(0))
	restored_fps.item_selected.emit(restored_fps.selected)
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
	# The minimap's appearance is a set of choices a player makes once and
	# expects to keep: which marks are drawn, how big they are, and what shape
	# and size the window is. Each is written by the menu that changes it, so
	# they are proved through the file rather than through a live variable.
	second.call("_on_minimap_marker_type_toggled",
		(second.get("MINIMAP_MARKER_TYPES") as Array).find(&"harvest"))
	second.call("_on_minimap_marker_scale_selected", 4)
	second.call("_on_minimap_shape_selected", 1)
	second.call("_on_minimap_border_selected", 0)
	var appearance := ConfigFile.new()
	var border_steps: Array = second.get("MINIMAP_BORDER_STEPS") as Array
	var marker_scales: Array = second.get("MINIMAP_MARKER_SCALES") as Array
	_expect(appearance.load(SETTINGS_PATH) == OK
		and not bool(appearance.get_value("hud", "minimap_marker_harvest", true))
		and bool(appearance.get_value("hud", "minimap_marker_player", false))
		and str(appearance.get_value("hud", "minimap_shape", "")) == "round"
		and is_equal_approx(float(appearance.get_value(
			"hud", "minimap_marker_scale", 0.0)), float(marker_scales[-1]))
		and is_equal_approx(float(appearance.get_value(
			"hud", "minimap_border", 0.0)), float(border_steps[0])),
		"the minimap's marker and appearance choices are written to the file")
	second.queue_free()
	await process_frame
	Engine.max_fps = 144

	var third: Node = (load("res://src/app/main.tscn") as PackedScene).instantiate()
	root.add_child(third)
	await process_frame
	var third_settings: Control = third.get("settings_window") as Control
	var unlimited_fps: OptionButton = third_settings.find_child("fps_limit", true, false) as OptionButton
	_expect(Engine.max_fps == 0 and unlimited_fps.get_selected_id() == 0,
		"Unlimited also survives a new session and removes the engine frame cap")
	var third_overlay: Control = third.get("minimap_marker_overlay") as Control
	_expect(str(third.get("_minimap_shape")) == "round"
		and is_equal_approx(float(third.get("_minimap_marker_scale")),
			float(marker_scales[-1]))
		and is_equal_approx(float(third.get("_minimap_border")),
			float(border_steps[0])),
		"a new session comes back with the remembered minimap appearance")
	_expect(third_overlay != null
		and not bool(third_overlay.call("type_enabled", &"harvest"))
		and bool(third_overlay.call("type_enabled", &"creature")),
		"the remembered marker switches reach the overlay that draws them")
	var third_menu: PopupMenu = third.get("_minimap_marker_type_menu") as PopupMenu
	var harvest_index: int = (third.get("MINIMAP_MARKER_TYPES") as Array).find(&"harvest")
	_expect(third_menu != null and not third_menu.is_item_checked(harvest_index)
		and third_menu.is_item_checked(0),
		"the menu opens ticked to what was remembered rather than to the defaults")
	third.queue_free()
	await process_frame

	_restore_settings(saved)
	Engine.max_fps = original_max_fps
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
