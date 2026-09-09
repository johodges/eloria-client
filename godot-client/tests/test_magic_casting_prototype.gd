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
	main.free()
	await process_frame
	NativeAnimationImporter.clear()
	GlbSceneCache.clear()
	print("magic casting prototype: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)
