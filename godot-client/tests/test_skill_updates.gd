extends SceneTree
## Replay the server's level-up sequence through state and the right HUD rail.

const P := preload("res://src/network/protocol.gd")
var failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var state := load("res://src/state/app_state.gd").new() as Node
	var hud := load("res://src/app/main.gd").new() as Control
	var rows := VBoxContainer.new()
	hud.add_child(rows)
	hud.set("skill_rows", rows)
	hud.call("_build_skill_rows")
	state.state_changed.connect(func(path: StringName) -> void:
		if path == &"stats":
			hud.call("_sync_skill_rows", state.get("stats")))
	var feedback: Array[Dictionary] = []
	state.floating_feedback_requested.connect(
		func(event: Dictionary) -> void: feedback.append(event))

	state.call("_on_packet", P.ServerMessage.HERE_YOUR_STATS, _snapshot(5, 9))
	_expect(_level(rows, "Attack") == "5" and _level(rows, "Defense") == "9",
		"login keeps unequal attack and defense levels separate")
	for example: Array in [["attack", 33, 6, "Attack"], ["defense", 35, 10, "Defense"]]:
		feedback.clear()
		state.call("_on_packet", P.ServerMessage.SEND_PARTIAL_STAT,
			PackedByteArray([int(example[1]), int(example[2]), 0, 0, 0]))
		var stats: Dictionary = state.get("stats")
		_expect(int(stats[str(example[0]) + "_base"]) == int(example[2]),
			"%s level-up updates its own base level" % example[0])
		_expect(feedback.size() == 1 and feedback[0].kind == "level"
			and feedback[0].skill == example[0] and feedback[0].level == example[2],
			"%s floating level-up names the skill that advanced" % example[0])
		# announce_levels follows the base notification with an authoritative
		# snapshot so current levels and next-level XP do not await another action.
		var feedback_count := feedback.size()
		state.call("_on_packet", P.ServerMessage.HERE_YOUR_STATS,
			_snapshot(6, 9 if example[0] == "attack" else 10))
		_expect(_level(rows, str(example[3])) == str(example[2]),
			"%s right HUD level refreshes synchronously with the level-up sequence" % example[0])
		_expect(feedback.size() == feedback_count,
			"the full refresh does not duplicate level-up feedback")
	_expect(_level(rows, "Attack") == "6" and _level(rows, "Defense") == "10",
		"defense advancing leaves the attack HUD level alone")
	state.free()
	hud.free()
	print("skill updates: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)

func _snapshot(attack: int, defense: int) -> PackedByteArray:
	var payload := PackedByteArray()
	payload.resize(230)
	# Fixed wire offsets from eloria.stats.stats_packet, independent of the
	# client's lookup tables. Full and partial XP offsets intentionally differ.
	payload.encode_s16(64, attack)
	payload.encode_s16(66, attack)
	payload.encode_s16(68, defense)
	payload.encode_s16(70, defense)
	return payload

func _level(rows: VBoxContainer, skill: String) -> String:
	return (rows.get_node("SkillRow%s/Value" % skill) as Label).text

func _expect(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
