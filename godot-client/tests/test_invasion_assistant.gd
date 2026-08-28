extends SceneTree

const AssistantScript := preload("res://src/ui/invasion_assistant.gd")

var failures := 0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var assistant = AssistantScript.new()
	root.add_child(assistant)
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

	assistant.apply_update({"kind": "groups", "groups": [{
		"name": "ashfall", "description": "Ashfall Ridge", "map_id": "ember",
		"map_name": "Emberhaven", "minimum": 4, "maximum": 8, "points": 1,
		"creatures": ["ash_wyrm"], "strength": 120, "active": true,
		"alive": 2, "boss": "The Cinder Maw", "health_multiplier": 1.0}]})
	_expect(assistant.group_list.item_count == 1, "spawn groups populate")
	assistant.apply_update({"kind": "monsters", "monsters": [{
		"type": "ash_wyrm", "name": "Ash Wyrm", "tier": "Formidable",
		"rating": 120, "combat_level": 60, "level": 10, "health": 180,
		"ether": 30, "attack": 40, "defense": 20, "damage_min": 6,
		"damage_max": 12, "armor_min": 2, "armor_max": 5,
		"configured": true}]})
	_expect(assistant.monster_list.item_count == 1, "monster catalog populates")
	assistant.queue_free()
	if failures == 0:
		print("invasion assistant tests passed")
	quit(failures)


func _expect(condition: bool, message: String) -> void:
	if condition:
		return
	failures += 1
	push_error("FAIL: " + message)
