extends SceneTree
var failures := 0
var requests: Array[Dictionary] = []
func _init() -> void: call_deferred("run")
func check(value: bool, message: String) -> void:
	if not value:
		failures += 1
		push_error("FAIL: " + message)
func key(code: Key, pressed := true) -> InputEventKey:
	var result := InputEventKey.new()
	result.keycode = code
	result.physical_keycode = code
	result.pressed = pressed
	result.alt_pressed = true
	return result
func run() -> void:
	root.size = Vector2i(1280, 720)
	var lab := (load("res://src/dev/magic_practice.tscn") as PackedScene).instantiate()
	root.add_child(lab)
	lab.trial_preferences_path = ""
	lab.loadout.profile = ""
	lab.loadout.set_wheel_power(3)
	lab.selector.request_sender = func(data: Dictionary) -> Error:
		requests.append(data.duplicate(true))
		return OK
	var state := root.get_node("AppState")
	for variant in ["quick", "orbit"]:
		lab.trial_preferences = {"scopes": {}, "powers": {}, "pins": {}}
		lab.set_wheel_variant(variant)
		var wheel: Control = lab.wheel
		state.select_actor(2)
		root.push_input(key(KEY_ALT), true)
		await process_frame
		check(wheel.visible, variant + " opens through real Alt input")
		var frozen: Vector2 = wheel.center
		lab.actors[1].tile += Vector2i(1, 0)
		await process_frame
		check(wheel.center == frozen, variant + " stays fixed while the character moves")
		if variant == "quick":
			var sector: Button = wheel.buttons[0]
			await move_to_sector(sector)
			await create_timer(0.25).timeout
			check(wheel.stage == "effects" and wheel.category == "Healing", "hover enters Healing without a click")
		else:
			wheel.handle_event(key(KEY_E))
			check(wheel.category == "Offense", "Orbit class letters switch the inner ring")
			wheel.handle_event(key(KEY_Q))
		check(wheel.resolve_spell("heal") == 1, "first Heal uses an eligible selected recipient")
		check(wheel._preview.text.contains("Tavin"), "preview names the selected recipient")
		var before := requests.size()
		wheel.change_power(1)
		wheel.select_scope("target")
		check(requests.size() == before, "hover, power, and target controls do not cast")
		await click_sector(wheel.buttons[0])
		check(requests.back() == {"op": "cast", "id": 1, "power": 4, "target_id": 2}, variant + " one click casts the previewed spell and power")
		root.push_input(key(KEY_ALT, false), true)
		state.select_actor(3)
		root.push_input(key(KEY_ALT), true)
		root.push_input(key(KEY_SPACE), true)
		check(requests.back().get("target_id") == 3 and requests.back().power == 4, "repeat uses the current recipient and previous power")
		root.push_input(key(KEY_ALT, false), true)
		wheel.open_wheel()
		wheel.enter_class("Healing")
		check(wheel.power_for(1) == 4, "family power is remembered")
		wheel.select_scope("burst")
		wheel.choose(0)
		check(lab.selector.pending.get("id") == 21, "Burst still asks for ground placement")
		lab.selector.confirm_location(Vector2i(12, 7))
		check(requests.back().get("x") == 12 and requests.back().power == 4, "ground confirmation preserves chosen power")
		wheel.open_wheel()
		wheel.enter_class("Healing")
		check(wheel.resolve_spell("heal") == 21, "last target type is remembered per family")
		before = requests.size()
		wheel.handle_event(key(KEY_ALT, false))
		check(requests.size() == before and not wheel.visible, "release cancels unfinished selection")
		wheel.open_wheel()
		wheel.enter_class("Offense")
		check(wheel.pinned_families("Offense").size() == 6, "Offense begins with six stable pinned families")
		var initial: Array[String] = wheel.pinned_families("Offense")
		wheel.effect = initial[0]
		wheel.toggle_pin()
		wheel.change_page(1)
		var add: String = wheel.entries[0].value
		wheel.effect = add
		wheel.toggle_pin()
		check(add in wheel.pinned_families("Offense") and wheel.pinned_families("Offense").size() == 6, "a family from More can replace an unpinned family")
		var reachable: Array[String] = wheel.pinned_families("Offense")
		reachable.append_array(wheel._remaining())
		var expected: Array[String] = wheel.effects_for("Offense")
		reachable.sort()
		expected.sort()
		check(reachable == expected, "pinning leaves every family reachable")
		var saved: Array[String] = wheel.pinned_families("Offense")
		state.spell_power["heal"] = {"limit": 2}
		wheel.enter_class("Healing")
		check(wheel.power_for(1) == 2, "remembered power respects a lower server limit")
		check(wheel.pinned_families("Offense") == saved, "limits cannot reorder pins")
		state.spell_power["heal"] = {"limit": 10}
		wheel.reset()
	# Trial switching does not replace the baseline implementation or lose pins.
	lab.set_wheel_variant("baseline")
	check(lab.wheel.get_script() == load("res://src/ui/spell_wheel.gd"), "baseline uses the original wheel")
	lab.set_wheel_variant("orbit")
	check(lab.wheel.preferences == lab.trial_preferences, "switching trials preserves comparison preferences")
	lab.free()
	await process_frame
	print("magic wheel trials: ", "PASS" if failures == 0 else "FAIL")
	quit(failures)
func move_to_sector(button: Button) -> void:
	var event := InputEventMouseMotion.new()
	event.position = button.global_position + Vector2.ONE * button.outer + Vector2.from_angle(button.angle) * (button.inner + button.outer) / 2
	event.global_position = event.position
	root.push_input(event, true)
	await process_frame
func click_sector(button: Button) -> void:
	var point: Vector2 = button.global_position + Vector2.ONE * button.outer + Vector2.from_angle(button.angle + button.spread * 0.30) * (button.inner + button.outer) / 2
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = point
		event.global_position = point
		event.pressed = pressed
		event.button_index = MOUSE_BUTTON_LEFT
		event.alt_pressed = true
		root.push_input(event, true)
		await process_frame
