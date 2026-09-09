extends SceneTree
var failures := 0
var requests: Array[Dictionary] = []

func _init() -> void: call_deferred("run")
func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error("FAIL: " + message)

func run() -> void:
	var catalog := SpellCatalog.new()
	catalog.configure(JSON.parse_string(FileAccess.get_file_as_string("res://data/spells/catalog.json")))
	var model = preload("res://src/ui/spell_loadout.gd").new()
	model.configure(catalog)
	DirAccess.make_dir_recursive_absolute("res://test-artifacts/magic-casting")
	model.path = "res://test-artifacts/magic-casting/loadout-%d.cfg" % Time.get_ticks_usec()
	model.load_profile("server-one/alice")
	model.assign_slot(0, 1, 4)
	model.assign_slot(1, 1, 2)
	model.remember_power(1, 3)
	check(model.slots[0].power == 4 and model.slots[1].power == 2, "two copies of a spell retain independent powers")
	model.load_profile("server-one/bob")
	check(model.slots[0].id == 0 and model.slots[0].power == 1, "a new character starts with defaults")
	model.load_profile("server-one/alice")
	check(model.slots[0] == {"id": 1, "power": 4} and model.power_for(1) == 3, "character preferences survive reload")
	model.assign_slot(-1, 6, 4)
	model.assign_slot(0, 999999, 4)
	check(model.slots[0].id == 1, "invalid drops cannot overwrite a slot")
	model.assign_slot(1, -1, 1)
	check(model.slots[1].id == -1, "slots can be cleared")
	DirAccess.remove_absolute(model.path)
	var selection = load("res://src/ui/magic_selection.gd").new()
	selection.catalog = catalog
	selection.request_sender = func(data: Dictionary) -> Error:
		requests.append(data.duplicate(true))
		return OK
	selection.target_validator = func(_spell_id: int, actor_id: int) -> bool: return actor_id == 42
	root.add_child(selection)
	root.get_node("AppState").actors[42] = {"name": "Practice ally", "alive": true, "health": 40, "kind": 1}
	selection.begin(1, 4, 42)
	check(requests.back() == {"op": "cast", "id": 1, "power": 4, "target_id": 42}, "Prepared mode casts directly on a valid selected actor")
	check(selection.pending.is_empty() and root.get_node("Network").magic_pending.is_empty(), "direct casts leave no pending selection")
	check(root.get_node("AppState").selected_actor_id == 42, "casting retains the selected recipient")
	selection.begin(1, 4, 42)
	check(requests.size() == 2, "repeat casts require no target reselection or cancel packet")
	selection.begin(1, 4, 99)
	check(not selection.pending.is_empty() and requests.size() == 2, "invalid selected recipients arm targeting without changing scope")
	selection.begin(69, 3)
	check(requests.back().op == "cancel" and selection.pending.id == 69, "a new spell replaces pending targeting")
	selection.confirm_location(Vector2i(8, 9))
	check(requests.back() == {"op": "cast", "id": 69, "power": 3, "x": 8, "y": 9}, "area confirmation preserves spell and power")
	selection.target_mode = "aimed"
	var before := requests.size()
	selection.begin(1, 2, 42)
	check(requests.size() == before and not selection.pending.is_empty(), "Aimed mode waits even with a selected target")
	selection.confirm_actor(42)
	check(requests.back().target_id == 42 and requests.back().power == 2, "explicit target click casts the chosen variant")
	selection.begin(5, 1)
	selection.cancel()
	before = requests.size()
	selection.confirm_location(Vector2i(1, 1))
	check(requests.size() == before and root.get_node("AppState").pending_spell_target.is_empty(), "cancelled aiming cannot cast later")
	selection.begin(0, 2)
	check(requests.back() == {"op": "cast", "id": 0, "power": 2}, "self spells cast immediately in both modes")
	selection.queue_free()
	await process_frame
	# Instantiate the real application to verify the bar-to-cast integration.
	var main := (load("res://src/app/main.tscn") as PackedScene).instantiate()
	root.add_child(main)
	await process_frame
	main.magic_selection.request_sender = func(data: Dictionary) -> Error:
		requests.append(data.duplicate(true))
		return OK
	var app_state := root.get_node("AppState")
	app_state.actors[77] = {"name": "Wild creature", "kind": 3, "alive": true, "health": 100}
	check(not main.call("_spell_target_candidate", 1, 77), "a healing shortcut does not automatically select hostile wildlife")
	check(main.call("_spell_target_candidate", 6, 77), "a damage shortcut accepts a living selected creature")
	check(not main.call("_spell_target_candidate", 14, 77), "Ether Drain does not automatically target a creature")
	app_state.select_actor(-1)
	main.spell_loadout.assign_slot(0, 0, 4)
	root.get_node("AppState").spell_power["heal"] = {"limit": 3}
	main.call("_cast_spell_slot", 0)
	check(requests.back().id == 0 and requests.back().power == 3, "the live bar uses saved power capped to the server limit")
	main.spells_window.call("_on_spell_pressed", 1)
	main.spells_window.power_picker.value = 2
	main.call("_cast_spell_by_id", 1)
	check(main.magic_selection.pending.power == 2, "book casting uses its own remembered power")
	main.magic_selection.cancel()
	var bar: Control = main.casting_bar
	check(bar.buttons.size() == 12, "all twelve shortcuts have visible prepared slots")
	bar.buttons[1].spell_dropped.emit(69, 3)
	check(main.spell_loadout.slots[1] == {"id": 69, "power": 3}, "dragging a variant assigns the actual casting slot")
	main.spells_window.edit_prepared_slot(1)
	check(main.spells_window.selected_spell_id == 69 and main.spells_window.power_picker.value == 3, "editing a slot restores its spell and saved power")
	main.spells_window.close()
	main.game_view.show()
	main.spell_loadout.set_mode("wheel")
	check(main.magic_selection.target_mode == "prepared", "wheel mode uses selected recipients")
	main.call("_input", key_event(KEY_ALT))
	check(main.spell_wheel.visible, "live input opens the character wheel on Alt")
	before = requests.size()
	main.call("_input", key_event(KEY_1))
	main.call("_unhandled_input", key_event(KEY_1))
	check(main.spell_wheel.stage == "effects" and requests.size() == before, "Alt+1 enters Healing without firing a quick slot")
	main.call("_input", key_event(KEY_1))
	main.call("_input", key_event(KEY_2))
	check(main.magic_selection.pending.get("id") == 1, "live wheel routes Heal Target into the existing targeting controller")
	main.call("_input", key_event(KEY_ALT, false))
	check(main.magic_selection.pending.get("id") == 1, "releasing Alt after a choice preserves armed targeting")
	main.magic_selection.cancel()
	main.free()
	await process_frame
	await test_wheel(catalog)
	await test_wheel_mouse_routing()
	NativeAnimationImporter.clear()
	GlbSceneCache.clear()
	print("magic casting prototype: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)

func key_event(code: Key, pressed := true, echo := false) -> InputEventKey:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	event.pressed = pressed
	event.alt_pressed = true
	event.echo = echo
	return event

func test_wheel(catalog: SpellCatalog) -> void:
	var model = load("res://src/ui/spell_loadout.gd").new()
	model.configure(catalog)
	model.set_mode("wheel")
	var wheel = load("res://src/ui/spell_wheel.gd").new()
	wheel.loadout = model
	wheel.anchor_provider = func() -> Vector2: return Vector2(510, 310)
	var chosen: Array[int] = []
	wheel.spell_chosen.connect(func(id: int): chosen.append(id))
	root.add_child(wheel)
	await process_frame
	wheel.handle_event(key_event(KEY_ALT))
	check(wheel.visible and wheel.center.is_equal_approx(Vector2(510, 310)), "wheel is anchored around the character")
	wheel.handle_event(key_event(KEY_1, true, true))
	check(wheel.stage == "classes", "key repeat cannot skip a wheel stage")
	wheel.handle_event(key_event(KEY_1))
	wheel.handle_event(key_event(KEY_ALT, false))
	check(not wheel.visible and chosen.is_empty(), "releasing Alt without a leaf never casts")
	wheel.handle_event(key_event(KEY_ALT))
	wheel.handle_event(key_event(KEY_1))
	wheel.handle_event(key_event(KEY_1))
	check(wheel.entries[0].id == 0 and wheel.entries[1].id == 1 and wheel.entries[2].id == 22 and wheel.entries[3].id == 21, "target positions are Self, Target, Allies, Burst")
	wheel.handle_event(key_event(KEY_5))
	check(wheel.visible and chosen.is_empty(), "unavailable scopes cannot accidentally cast")
	wheel.handle_event(key_event(KEY_2))
	wheel.handle_event(key_event(KEY_2))
	wheel.handle_event(key_event(KEY_ALT, false))
	check(chosen == [1] and not wheel.visible, "a complete Alt sequence emits one exact spell, including repeated keys and release")
	wheel.open_wheel()
	wheel.buttons[0].pressed.emit()
	wheel.buttons[0].pressed.emit()
	wheel.buttons[2].pressed.emit()
	check(chosen == [1, 22], "mouse buttons choose the same class, family, and target as keys")
	wheel.open_wheel()
	wheel.choose(2)
	wheel.change_page(1)
	check(wheel.page == 1 and not wheel.entries.is_empty(), "all Offense families are paginated")
	wheel.choose(0)
	wheel.go_back()
	check(wheel.stage == "effects" and wheel.page == 1, "back from a target preserves the current family page")
	wheel.handle_event(key_event(KEY_ESCAPE))
	check(not wheel.visible and chosen.size() == 2, "Escape dismisses without selecting")
	wheel.handle_event(key_event(KEY_ALT))
	wheel.call("_notification", Control.NOTIFICATION_APPLICATION_FOCUS_OUT)
	check(not wheel.visible and not wheel.handle_event(key_event(KEY_ALT, false)), "focus loss clears Alt ownership")
	wheel.can_open = func() -> bool: return false
	check(not wheel.handle_event(key_event(KEY_ALT)) and not wheel.visible, "typing or a modal can suppress opening")
	wheel.can_open = Callable()
	wheel.open_wheel(true)
	wheel.handle_event(key_event(KEY_TAB))
	check(not wheel.visible, "Alt+Tab releases the wheel")
	# Walk the actual visible menus, including singleton utility families, and
	# assert every catalog spell is reachable exactly once.
	var reachable: Array[int] = []
	for class_index in range(wheel.CLASSES.size()):
		var family_count: int = wheel.effects_for(wheel.CLASSES[class_index]).size()
		for family_index in range(family_count):
			wheel.open_wheel()
			wheel.choose(class_index)
			wheel.change_page(family_index / wheel.PAGE_SIZE)
			var choice_count := chosen.size()
			wheel.choose(family_index % wheel.PAGE_SIZE)
			if chosen.size() > choice_count: reachable.append(chosen.back())
			else:
				for entry: Dictionary in wheel.entries:
					if entry.has("id"): reachable.append(int(entry.id))
	var expected := catalog.spell_ids()
	expected.sort()
	reachable.sort()
	check(reachable == expected, "every catalog spell is reachable exactly once through the wheel")
	model.set_mode("aimed")
	check(not wheel.visible and not wheel.handle_event(key_event(KEY_ALT)), "other casting modes retain their Alt bindings")
	wheel.free()
	await process_frame

func test_wheel_mouse_routing() -> void:
	var lab := (load("res://src/dev/magic_practice.tscn") as PackedScene).instantiate()
	root.add_child(lab)
	lab.loadout.set_mode("wheel")
	root.get_node("AppState").select_actor(2)
	await process_frame
	root.push_input(key_event(KEY_ALT), true)
	check(lab.wheel.visible, "viewport input opens the practice wheel")
	var initial_tile: Vector2i = lab.actors[1].tile
	await click_at(lab.wheel.buttons[0].get_global_rect().get_center())
	check(lab.wheel.stage == "effects", "GUI routes a class click to the wheel")
	await click_at(lab.wheel.buttons[0].get_global_rect().get_center())
	check(lab.wheel.stage == "targets", "GUI routes a family click to the wheel")
	await click_at(lab.wheel.buttons[1].get_global_rect().get_center())
	check(not lab.wheel.visible and lab.actors[2].health == 45, "GUI target click casts once on the selected recipient")
	check(lab.actors[1].tile == initial_tile, "wheel clicks cannot move the character underneath")
	root.push_input(key_event(KEY_ALT, false), true)
	check(lab.actors[2].health == 45, "Alt release after a mouse choice never casts twice")
	var entry := LineEdit.new()
	lab.add_child(entry)
	entry.grab_focus()
	root.push_input(key_event(KEY_ALT), true)
	check(not lab.wheel.visible, "a focused text field prevents Alt opening the wheel")
	root.push_input(key_event(KEY_ALT, false), true)
	lab.free()
	await process_frame

func click_at(point: Vector2) -> void:
	var motion := InputEventMouseMotion.new()
	motion.position = point
	motion.global_position = point
	root.push_input(motion, true)
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = point
		event.global_position = point
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = pressed
		event.alt_pressed = true
		root.push_input(event, true)
		await process_frame
