extends SceneTree

var failures := 0

func _init() -> void:
	_expect_bytes("empty frame", EloriaProtocol.encode(13), PackedByteArray([13, 1, 0]))
	_expect_bytes("move fixture", EloriaProtocol.move_to(0x1234, 0x5678),
		PackedByteArray([1, 5, 0, 0x34, 0x12, 0x78, 0x56]))
	_expect_bytes("sit fixture", EloriaProtocol.set_sitting(true),
		PackedByteArray([7, 2, 0, 1]))
	_expect_bytes("stand fixture", EloriaProtocol.set_sitting(false),
		PackedByteArray([7, 2, 0, 0]))
	_expect_bytes("chat fixture", EloriaProtocol.chat("Hello"),
		PackedByteArray([0, 7, 0, 72, 101, 108, 108, 111, 0]))
	_expect_bytes("touch actor fixture", EloriaProtocol.touch_actor(0x12345678),
		PackedByteArray([28, 5, 0, 0x78, 0x56, 0x34, 0x12]))
	_expect_bytes("npc response fixture", EloriaProtocol.npc_response(0x1234, 0x5678),
		PackedByteArray([29, 5, 0, 0x34, 0x12, 0x78, 0x56]))
	_expect(EloriaProtocol.actor_command_step(20) == Vector2i(0, 1), "walk north step")
	_expect(EloriaProtocol.actor_command_step(37) == Vector2i(-1, 1), "run northwest step")
	_expect(EloriaProtocol.actor_command_step(13) == Vector2i.ZERO, "sit has no step")
	_expect(EloriaProtocol.actor_command_direction(22) == Vector2i(1, 0),
		"walk command faces east")
	_expect(EloriaProtocol.actor_command_direction(40) == Vector2i(1, 0),
		"turn-only command faces east without moving")
	_expect_bytes("login fixture", EloriaProtocol.login("Test", "secret"),
		PackedByteArray([140, 13, 0, 84, 101, 115, 116, 32, 115, 101, 99, 114, 101, 116, 0]))
	_expect_bytes("create character fixture",
		EloriaProtocol.create_character("Test", "secret",
			{"skin": 1, "hair": 2, "shirt": 3, "pants": 4, "boots": 5,
			"actor_type": 0, "head": 2, "eyes": 6}),
		PackedByteArray([141, 21, 0, 84, 101, 115, 116, 32, 115, 101, 99, 114,
			101, 116, 0, 1, 2, 3, 4, 5, 0, 2, 6]))
	_expect_bytes("version fixture",
		EloriaProtocol.version(10, 31, PackedByteArray([1, 9, 7, 0]),
			PackedByteArray([127, 0, 0, 1]), 2000),
		PackedByteArray([10, 15, 0, 10, 0, 31, 0, 1, 9, 7, 0, 127, 0, 0, 1, 7, 208]))

	var combined := EloriaProtocol.encode(11)
	combined.append_array(EloriaProtocol.encode(5, PackedByteArray([9, 0])))
	var first := EloriaProtocol.try_decode(combined)
	_expect(first.status == "ok" and first.command == 11 and first.consumed == 3, "combined first")
	var second := EloriaProtocol.try_decode(combined.slice(first.consumed))
	_expect(second.status == "ok" and second.command == 5, "combined second")
	_expect(EloriaProtocol.try_decode(PackedByteArray([1, 5])).status == "incomplete",
		"fragmented header")
	_expect(EloriaProtocol.try_decode(PackedByteArray([1, 0, 0])).status == "error",
		"invalid length")

	var created := EloriaProtocol.decode_server(252, PackedByteArray())
	_expect(created.type == "create_character_ok", "character creation ok")
	var creation_error := EloriaProtocol.decode_server(253, _nul_bytes("Name exists"))
	_expect(creation_error.type == "create_character_error"
		and creation_error.message == "Name exists", "character creation error")
	var login_ok := EloriaProtocol.decode_server(250, PackedByteArray())
	_expect(login_ok.type == "login_ok", "login ok")
	var login_error := EloriaProtocol.decode_server(251, _nul_bytes("Bad login"))
	_expect(login_error.type == "login_error" and login_error.message == "Bad login", "login error")
	var yourself := EloriaProtocol.decode_server(3, PackedByteArray([0x34, 0x12]))
	_expect(yourself.actor_id == 0x1234, "you are")
	_expect(EloriaProtocol.decode_server(3, PackedByteArray()).type == "invalid", "short you are")
	var chat := EloriaProtocol.decode_server(0, PackedByteArray([3, 72, 105, 0]))
	_expect(chat.type == "chat" and chat.channel == 3 and chat.text == "Hi", "chat")
	var option_payload: PackedByteArray = PackedByteArray([4, 0, 66, 121, 101, 0,
		0x34, 0x12, 0x78, 0x56])
	var npc_options: Dictionary = EloriaProtocol.decode_server(31, option_payload)
	_expect(npc_options.type == "npc_options" and npc_options.options.size() == 1
		and npc_options.options[0].label == "Bye"
		and npc_options.options[0].response_id == 0x1234
		and npc_options.options[0].actor_id == 0x5678, "npc options")
	_expect(EloriaProtocol.decode_server(31, PackedByteArray([9, 0, 65])).type ==
		"invalid", "truncated npc option")
	var commands := EloriaProtocol.decode_server(2,
		PackedByteArray([0x34, 0x12, 20, 0x78, 0x56, 7]))
	_expect(commands.commands.size() == 2 and commands.commands[1].actor_id == 0x5678,
		"batched actor commands")

	var actor_payload := PackedByteArray([
		0x34, 0x12, 10, 0, 20, 0, 0, 0, 0xff, 0xff, 1, 7,
		100, 0, 90, 0, 1, 66, 111, 98, 0])
	var actor := EloriaProtocol.decode_server(1, actor_payload)
	_expect(actor.type == "actor_spawn" and actor.actor_id == 0x1234, "actor id")
	_expect(actor.x == 10 and actor.y == 20 and actor.rotation == -1, "actor transform")
	_expect(actor.name == "Bob" and actor.health == 90, "actor identity and health")
	_expect(EloriaProtocol.decode_server(1, PackedByteArray([1])).type == "invalid",
		"short actor")

	_expect(MapRegistry.normalize_server_map_id(" /MAPS\\StartMap.ELM ") ==
		"maps/startmap.elm", "map id normalization")
	var registry: Dictionary = {
		"maps/startmap.elm": {"manifest": "res://world.json"},
		"startmap.elm": {"alias": "maps/startmap.elm"}}
	var resolved: Dictionary = MapRegistry.resolve(registry, "STARTMAP.ELM")
	_expect(resolved.get("manifest", "") == "res://world.json"
		and resolved.get("registryKey", "") == "maps/startmap.elm", "map alias resolution")
	var registry_file: FileAccess = FileAccess.open("res://data/maps/registry.json", FileAccess.READ)
	_expect(registry_file != null, "production map registry opens")
	if registry_file != null:
		var parsed_registry: Variant = JSON.parse_string(registry_file.get_as_text())
		_expect(parsed_registry is Dictionary, "production map registry parses")
		if parsed_registry is Dictionary:
			var registry_root: Dictionary = parsed_registry as Dictionary
			var production_maps_value: Variant = registry_root.get("maps", {})
			if production_maps_value is Dictionary:
				var production_maps: Dictionary = production_maps_value as Dictionary
				var four_gates: Dictionary = MapRegistry.resolve(production_maps, "four_gates")
				_expect(not four_gates.is_empty(), "runtime four_gates map id resolves")
				_expect(str(four_gates.get("registryKey", "")) == "maps/startmap.elm",
					"runtime four_gates resolves to production start map")
				var transform: Dictionary = four_gates.get("coordinateTransform", {})
				_expect(is_equal_approx(float(transform.get("walkingHeight", 0.0)), 31.15),
					"Four Gates actors stand above the authored y=31 walk surface")
	var coordinate: CoordinateAdapter = CoordinateAdapter.new({
		"metresPerTile": 0.5, "serverOrigin": [100.0, 200.0],
		"origin": [10.0, 30.0, -5.0], "walkingHeight": 30.0,
		"invertServerY": true})
	var godot_position: Vector3 = coordinate.server_to_godot(102.0, 198.0)
	_expect(godot_position.is_equal_approx(Vector3(11.0, 30.0, -4.0)),
		"coordinate walking height is absolute")
	_expect(coordinate.godot_to_server(godot_position) == Vector2i(102, 198),
		"coordinate round trip")
	_expect(is_equal_approx(coordinate.direction_to_godot(Vector2i(0, 1)), 0.0),
		"server north faces Godot forward")
	_expect(is_equal_approx(coordinate.direction_to_godot(Vector2i(1, 0)), -PI / 2.0),
		"server east faces Godot right")

	var reduced_actor: Dictionary = ActorReducer.apply_command(actor, 21)
	_expect(int(reduced_actor.get("x", -1)) == 11
		and int(reduced_actor.get("y", -1)) == 21, "actor movement reducer")
	reduced_actor = ActorReducer.apply_command(reduced_actor, 13)
	_expect(bool(reduced_actor.get("sitting", false)), "actor sit reducer")
	reduced_actor = ActorReducer.apply_command(reduced_actor, 14)
	_expect(not bool(reduced_actor.get("sitting", true)), "actor stand reducer")

	print("protocol tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)

func _expect_bytes(label: String, actual: PackedByteArray, expected: PackedByteArray) -> void:
	_expect(actual == expected, label + ": " + actual.hex_encode())

func _nul_bytes(value: String) -> PackedByteArray:
	var bytes: PackedByteArray = value.to_utf8_buffer()
	bytes.append(0)
	return bytes

func _expect(condition: bool, label: String) -> void:
	if not condition:
		failures += 1
		push_error(label)
