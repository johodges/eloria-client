extends SceneTree
## Exercise the real HUD, including input routing and a fresh scene reload.
var failures := 0
var captures := ""
const SETTINGS := "user://eloria_hud.cfg"

func _init() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="): captures = arg.trim_prefix("--capture=")
	call_deferred("run")

func check(value: bool, message: String) -> void:
	if not value:
		failures += 1
		push_error("FAIL: " + message)

func settle() -> void:
	for frame in range(5): await process_frame

func scene() -> Control:
	var main := (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(main)
	main.get_node("LoginPanel").hide()
	main.get_node("GameView").show()
	return main

func capture(filename: String) -> void:
	if captures.is_empty(): return
	await settle()
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(captures)
	root.get_texture().get_image().save_png(captures.path_join(filename))

func run() -> void:
	root.size = Vector2i(1280, 720)
	var original := FileAccess.get_file_as_string(SETTINGS) if FileAccess.file_exists(SETTINGS) else ""
	var clean := ConfigFile.new()
	clean.load(SETTINGS)
	if clean.has_section_key("hud", "spell_quickbar"): clean.erase_section_key("hud", "spell_quickbar")
	clean.set_value("hud", "ui_scale", 1.0)
	clean.set_value("hud", "combat_hud_position", Vector2(16, 100))
	clean.save(SETTINGS)
	var main := scene()
	await settle()
	var bar = main.casting_bar
	var items: Control = main.get_node("GameView/ItemQuickbar")
	var rail: Control = main.get_node("GameView/RightRail")
	var bottom: Control = main.get_node("GameView/Quickbar")
	check(bar.docked and bar.panel.visible and not bar.launcher.visible, "the fresh HUD shows the attached spell bar")
	check(bar.buttons.size() == 12, "all twelve saved shortcuts are present")
	check(absf(bar.panel.get_global_rect().end.x - rail.global_position.x) < 1, "the dock joins the HUD rail beside the item slots")
	for path in ["ItemQuickbar", "ResourceHud", "RailMeters", "ClockFrame", "CompassFrame", "ChatInput"]:
		check(not bar.panel.get_global_rect().intersects(main.get_node("GameView/" + path).get_global_rect()), "the attached spell bar leaves " + path + " clear")
	check(bar.panel.get_global_rect().end.y < bottom.global_position.y, "the attached bar clears the bottom HUD")
	for button: Button in bar.buttons:
		check(bar._scroll.get_global_rect().encloses(button.get_global_rect()), "every spell is visible at 1280 by 720")
	main.spell_loadout.assign_slot(0, 1, 10)
	var app := root.get_node("AppState")
	app.actors[42] = {"name": "Mira", "kind": 1, "alive": true, "health": 40}
	app.select_actor(42)
	await settle()
	var slot: Button = bar.buttons[0]
	var target: Label = slot.get_node("Target")
	var power: Label = slot.get_node("Power")
	check(target.text == "T" and power.text == "10", "badges retain the target letter and two-digit power")
	check(target.has_theme_stylebox_override("normal") and power.has_theme_stylebox_override("normal"), "both corner labels have opaque backings")
	check(not target.get_rect().intersects(power.get_rect()), "target and power ten fit in separate corners")
	check(slot.tooltip_text.contains("Target: Mira") and slot.tooltip_text.contains("Power 10"), "the tooltip expands the current recipient and power")
	check(slot.modulate.a == 1 and target.modulate.a == 1, "unavailable spells do not fade their corner badges")
	await capture("docked.png")
	# Drag through the same viewport events a player sends, rather than
	# setting position directly. An ordinary grip click must keep it attached.
	var grip_position: Vector2 = bar.grip.get_global_rect().get_center()
	var hover := InputEventMouseMotion.new()
	hover.position = grip_position
	hover.global_position = grip_position
	root.push_input(hover, true)
	mouse(grip_position, true)
	mouse(grip_position, false)
	await settle()
	check(bar.docked, "clicking the grip does not detach the bar")
	mouse(grip_position, true)
	var motion := InputEventMouseMotion.new()
	motion.position = grip_position + Vector2(-250, 12)
	motion.global_position = motion.position
	motion.relative = Vector2(-250, 12)
	motion.button_mask = MOUSE_BUTTON_MASK_LEFT
	root.push_input(motion, true)
	mouse(motion.position, false)
	await settle()
	check(not bar.docked and bar.panel.position.x < items.position.x - 150, "dragging the grip detaches and moves the bar")
	var detached: Vector2 = bar.panel.position
	var saved := ConfigFile.new()
	saved.load(SETTINGS)
	var layout: Dictionary = saved.get_value("hud", "spell_quickbar", {})
	check(not bool(layout.get("docked", true)) and layout.get("position") == detached, "drag release saves detached placement")
	await capture("detached.png")
	main.free()
	await settle()
	main = scene()
	await settle()
	bar = main.casting_bar
	check(not bar.docked and bar.panel.position.is_equal_approx(detached), "a new scene restores the detached bar position")
	bar.call("_dock_menu_action", 0)
	await settle()
	items = main.get_node("GameView/ItemQuickbar")
	rail = main.get_node("GameView/RightRail")
	check(bar.docked and absf(bar.panel.get_global_rect().end.x - rail.global_position.x) < 1, "Attach to HUD returns the bar beside item slots")
	bar.dock_menu.get_popup().id_pressed.emit(2)
	await settle()
	check(bar.settings_popup.visible, "the compact menu opens ring and casting settings")
	bar.ring_size_picker.item_selected.emit(bar.ring_size_picker.get_item_index(125))
	check(main.spell_loadout.ring_size == 125, "the menu keeps the ring size control functional")
	bar.close_button.pressed.emit()
	await settle()
	check(not bar.settings_popup.visible and bar.panel.visible, "Done dismisses settings without hiding the bar")
	# Resize the actual HUD canvas, then test a high UI scale as well.
	for dimensions in [Vector2i(960, 600), Vector2i(1600, 900)]:
		root.size = dimensions
		await settle()
		check(Rect2(Vector2.ZERO, main.size).encloses(bar.panel.get_rect()), "the attached bar fits after resizing to " + str(dimensions))
		check(absf(bar.panel.get_global_rect().end.x - rail.global_position.x) < 1, "the resized dock remains next to items")
	main.call("_on_ui_scale_changed", 1.5)
	await settle()
	check(Rect2(Vector2.ZERO, main.size).encloses(bar.panel.get_rect()), "the bar remains accessible at 150 percent HUD scale")
	bar.set_expanded(false)
	await settle()
	main.free()
	await settle()
	main = scene()
	await settle()
	bar = main.casting_bar
	check(bar.docked and not bar.panel.visible and bar.launcher.visible, "attachment and explicit hiding both survive a reload")
	bar.launcher.pressed.emit()
	await settle()
	check(bar.panel.visible and not bar.launcher.visible, "the HUD launcher reopens the saved dock")
	main.free()
	await settle()
	var restore := FileAccess.open(SETTINGS, FileAccess.WRITE)
	restore.store_string(original)
	restore.close()
	NativeAnimationImporter.clear()
	GlbSceneCache.clear()
	print("spell bar docking: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)

func mouse(where: Vector2, pressed: bool) -> void:
	var event := InputEventMouseButton.new()
	event.position = where
	event.global_position = where
	event.button_index = MOUSE_BUTTON_LEFT
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
	event.pressed = pressed
	root.push_input(event, true)
