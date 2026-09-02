extends SceneTree

const AssistantScript := preload("res://src/ui/invasion_assistant.gd")

var failures := 0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var assistant = AssistantScript.new()
	root.add_child(assistant)
	var commands: Array[String] = []
	assistant.command_requested.connect(func(command: String) -> void: commands.append(command))
	var registry_file := FileAccess.open("res://data/maps/registry.json", FileAccess.READ)
	if registry_file != null:
		var registry_json: Dictionary = JSON.parse_string(registry_file.get_as_text()) as Dictionary
		assistant.configure_registry(registry_json.get("maps", {}) as Dictionary)
	assistant.apply_update({
		"kind": "index", "selected_map": "ember",
		"totals": {"players": 1, "invasions": 2, "active_groups": 1},
		"maps": [{"id": "ember", "name": "Emberhaven",
			"file": "maps/ember.elm", "players": 1, "invasions": 2,
			"active_groups": 1}]})
	_expect(assistant.map_list.item_count == 1, "map index populates")
	assistant.apply_update({
		"kind": "map",
		"map": {"id": "ember", "name": "Emberhaven", "file": "maps/ember.elm",
			"width": 256, "height": 192},
		"locations": [{"name": "Ashfall Ridge", "kind": "invasion_spawn",
			"x": 80, "y": 90}],
		"players": [{"name": "Master", "x": 30, "y": 40, "combat_level": 45}],
		"creatures": [{"name": "Ash Wyrm", "x": 75, "y": 88,
			"health": 150, "max_health": 180, "tier": "Formidable", "boss": true}]})
	_expect(assistant.map_canvas.state.players.size() == 1, "player marker populates")
	_expect(assistant.map_canvas.state.creatures[0].boss, "boss marker populates")
	_expect(not assistant.teleport_button.disabled, "teleport enables for a loaded map")
	_expect(assistant._map_texture("four_gates") != null,
		"minimap loads directly from the external asset workspace")
	root.size = Vector2i(960, 540)
	assistant._fit_to_viewport()
	_expect(assistant.size.x <= root.size.x and assistant.size.y <= root.size.y,
		"assistant stays within the viewport")

	assistant.apply_update({"kind": "groups", "groups": [{
		"name": "ashfall", "description": "Ashfall Ridge", "map_id": "ember",
		"map_name": "Emberhaven", "minimum": 4, "maximum": 8, "points": 1,
		"creatures": ["ash_wyrm"], "composition": [{"type": "ash_wyrm",
			"name": "Ash Wyrm", "quantity": 4}],
		"locations": [{"x": 80, "y": 90, "quantity": 4}],
		"strength": 120, "active": false, "alive": 0,
		"boss": "The Cinder Maw", "boss_type": "ash_wyrm",
		"boss_name": "The Cinder Maw", "health_multiplier": 1.0,
		"dynamic": true}]})
	_expect(assistant.group_list.item_count == 1, "spawn groups populate")
	assistant._on_group_selected(0)
	_expect(not assistant.group_spawn.disabled, "defined group can be spawned")
	_expect(not assistant.group_save.disabled, "dynamic group is editable")
	assistant.apply_update({"kind": "monsters", "monsters": [{
		"type": "ash_wyrm", "name": "Ash Wyrm", "tier": "Formidable",
		"rating": 120, "combat_level": 60, "level": 10, "health": 180,
		"ether": 30, "attack": 40, "defense": 20, "damage_min": 6,
		"damage_max": 12, "armor_min": 2, "armor_max": 5,
		"configured": true}]})
	_expect(assistant.monster_list.item_count == 1, "monster catalog populates")
	assistant._on_monster_selected(0)
	assistant.monster_quantity.value = 3
	assistant._add_monster_to_group()
	_expect(commands[-1] == "#invasion_assistant group add ashfall|ash_wyrm|3|80|90",
		"selected monster can be added to a selected live group")
	assistant._spawn_monster_here()
	_expect(commands[-1] == "#invasion_assistant monster spawn ash_wyrm|3",
		"selected monster can be quick-spawned at the invasion master's location")
	commands.clear()
	assistant.tabs.current_tab = 0
	assistant.show()
	assistant._process(5.1)
	_expect(commands.has("#invasion_assistant map ember"),
		"visible map refreshes periodically")
	assistant._teleport()
	_expect(commands[-1].begins_with("#invasion_assistant teleport ember "),
		"teleport requests an immediate server-authoritative refresh response")
	assistant.god_storage_button.pressed.emit()
	_expect(commands[-1] == "#god_storage",
		"header button opens the invasion-master god storage")
	assistant.queue_free()
	if failures == 0:
		print("invasion assistant tests passed")
	quit(failures)


func _expect(condition: bool, message: String) -> void:
	if condition:
		return
	failures += 1
	push_error("FAIL: " + message)
