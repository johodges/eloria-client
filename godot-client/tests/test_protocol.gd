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
	_expect_bytes("private message fixture", EloriaProtocol.private_message("Alice Hello"),
		PackedByteArray([2, 13, 0, 65, 108, 105, 99, 101, 32, 72, 101, 108, 108, 111, 0]))
	_expect_bytes("private reply fixture", EloriaProtocol.private_message("/Hello"),
		PackedByteArray([2, 8, 0, 47, 72, 101, 108, 108, 111, 0]))
	_expect_bytes("touch actor fixture", EloriaProtocol.touch_actor(0x12345678),
		PackedByteArray([28, 5, 0, 0x78, 0x56, 0x34, 0x12]))
	_expect_bytes("npc response fixture", EloriaProtocol.npc_response(0x1234, 0x5678),
		PackedByteArray([29, 5, 0, 0x34, 0x12, 0x78, 0x56]))
	_expect_bytes("inspect inventory fixture", EloriaProtocol.look_at_inventory_item(7),
		PackedByteArray([19, 2, 0, 7]))
	_expect_bytes("use inventory fixture", EloriaProtocol.use_inventory_item(7),
		PackedByteArray([31, 2, 0, 7]))
	_expect_bytes("move inventory fixture", EloriaProtocol.move_inventory_item(7, 9),
		PackedByteArray([20, 3, 0, 7, 9]))
	_expect_bytes("cast spell fixture", EloriaProtocol.cast_spell([3, 23]),
		PackedByteArray([39, 4, 0, 2, 3, 23]))
	_expect_bytes("attack actor fixture", EloriaProtocol.attack_actor(0x12345678),
		PackedByteArray([40, 5, 0, 0x78, 0x56, 0x34, 0x12]))
	_expect_bytes("trade request fixture", EloriaProtocol.trade_with(0x12345678),
		PackedByteArray([32, 5, 0, 0x78, 0x56, 0x34, 0x12]))
	_expect_bytes("trade inventory offer fixture",
		EloriaProtocol.put_inventory_on_trade(7, 0x12345678),
		PackedByteArray([36, 7, 0, 1, 7, 0x78, 0x56, 0x34, 0x12]))
	_expect_bytes("trade offer removal fixture",
		EloriaProtocol.remove_trade_item(3, 0x12345678),
		PackedByteArray([37, 6, 0, 3, 0x78, 0x56, 0x34, 0x12]))
	_expect_bytes("trade accept destinations fixture", EloriaProtocol.accept_trade(),
		PackedByteArray([33, 17, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]))
	var storage_destinations: PackedByteArray = PackedByteArray()
	storage_destinations.resize(16)
	storage_destinations.fill(1)
	storage_destinations[3] = 2
	_expect_bytes("trade per-slot storage destination fixture",
		EloriaProtocol.accept_trade(storage_destinations), PackedByteArray([
			33, 17, 0, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]))
	_expect_bytes("trade reject fixture", EloriaProtocol.reject_trade(),
		PackedByteArray([34, 1, 0]))
	_expect_bytes("trade exit fixture", EloriaProtocol.exit_trade(),
		PackedByteArray([35, 1, 0]))
	_expect_bytes("trade inspection fixture", EloriaProtocol.look_at_trade_item(3, true),
		PackedByteArray([38, 3, 0, 3, 1]))
	_expect_bytes("storage category fixture", EloriaProtocol.get_storage_category(4),
		PackedByteArray([44, 2, 0, 4]))
	_expect_bytes("storage deposit fixture", EloriaProtocol.deposit_storage(7, 0x12345678),
		PackedByteArray([45, 6, 0, 7, 0x78, 0x56, 0x34, 0x12]))
	_expect_bytes("storage withdrawal fixture", EloriaProtocol.withdraw_storage(
		0x1234, 0x56789abc), PackedByteArray([
			46, 7, 0, 0x34, 0x12, 0xbc, 0x9a, 0x78, 0x56]))
	_expect_bytes("storage inspection fixture", EloriaProtocol.look_at_storage_item(0x1234),
		PackedByteArray([47, 3, 0, 0x34, 0x12]))
	_expect_bytes("inspect ground bag fixture", EloriaProtocol.inspect_bag(7),
		PackedByteArray([25, 2, 0, 7]))
	_expect_bytes("close ground bag fixture", EloriaProtocol.close_bag(),
		PackedByteArray([26, 1, 0]))
	_expect_bytes("pick up ground item fixture",
		EloriaProtocol.pick_up_ground_item(3, 0x12345678),
		PackedByteArray([23, 6, 0, 3, 0x78, 0x56, 0x34, 0x12]))
	_expect_bytes("drop inventory item fixture",
		EloriaProtocol.drop_inventory_item(7, 0x12345678),
		PackedByteArray([22, 6, 0, 7, 0x78, 0x56, 0x34, 0x12]))
	_expect_bytes("knowledge inspection fixture", EloriaProtocol.get_knowledge_info(0x1234),
		PackedByteArray([41, 3, 0, 0x34, 0x12]))
	_expect_bytes("manufacturing fixture", EloriaProtocol.manufacture([
		{"slot": 7, "quantity": 0x1234}, {"slot": 2, "quantity": 3}], 255),
		PackedByteArray([30, 9, 0, 2, 7, 0x34, 0x12, 2, 3, 0, 255]))
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
	var appearance_visuals: Dictionary = AppearanceVariants.equipment_visuals(2, {
		"head": 1, "pants": 1, "shirt": 1, "boots": 1})
	_expect(int(appearance_visuals.get(AppearanceVariants.PART_HEAD, -1)) == 106
		and int(appearance_visuals.get(AppearanceVariants.PART_PANTS, -1)) == 105
		and int(appearance_visuals.get(AppearanceVariants.PART_SHIRT, -1)) == 106
		and int(appearance_visuals.get(AppearanceVariants.PART_BOOTS, -1)) == 105,
		"Whitehorn appearance choices prefer culture-matched native wearables")
	_expect(AppearanceVariants.equipment_visuals(2, {
		"head": 0, "pants": 0, "shirt": 0, "boots": 0}).is_empty(),
		"zero appearance choices leave optional wearables hidden")
	_expect(AppearanceVariants.skin_tint(0) != AppearanceVariants.skin_tint(1)
		and AppearanceVariants.eye_color(0) != AppearanceVariants.eye_color(1)
		and AppearanceVariants.hair_style(6) == 2,
		"skin, eye, and hair choices produce distinct variants")
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
	var colored_pm: Dictionary = EloriaProtocol.decode_server(0,
		PackedByteArray([1, 128, 91, 80, 77, 32, 102, 114, 111, 109, 32, 65, 108,
			105, 99, 101, 58, 32, 104, 105, 93, 0]))
	_expect(colored_pm.type == "chat" and colored_pm.channel == 1
		and colored_pm.text == "[PM from Alice: hi]",
		"personal channel strips legacy color controls")
	var unicode_chat: Dictionary = EloriaProtocol.decode_server(0,
		PackedByteArray([0, 128, 72, 195, 169, 108, 111, 0]))
	_expect(unicode_chat.text == "Hélo", "chat sanitizer preserves UTF-8 sequences")
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
	var actor_wear: Dictionary = EloriaProtocol.decode_server(52,
		PackedByteArray([0x34, 0x12, 2, 25]))
	_expect(actor_wear.type == "actor_wear" and actor_wear.actor_id == 0x1234
		and actor_wear.part == 2 and actor_wear.visual_id == 25,
		"actor wear equipment fields")
	var actor_unwear: Dictionary = EloriaProtocol.decode_server(53,
		PackedByteArray([0x34, 0x12, 2]))
	_expect(actor_unwear.type == "actor_unwear" and actor_unwear.actor_id == 0x1234
		and actor_unwear.part == 2, "actor unwear equipment fields")
	_expect(EloriaProtocol.decode_server(52, PackedByteArray([1, 0, 2])).type == "invalid",
		"malformed actor wear rejected")
	var actor_damage: Dictionary = EloriaProtocol.decode_server(47,
		PackedByteArray([0x34, 0x12, 7, 0]))
	_expect(actor_damage.type == "actor_damage" and actor_damage.actor_id == 0x1234
		and actor_damage.amount == 7, "actor damage fields")
	var actor_heal: Dictionary = EloriaProtocol.decode_server(48,
		PackedByteArray([0x34, 0x12, 5, 0]))
	_expect(actor_heal.type == "actor_heal" and actor_heal.amount == 5,
		"actor heal fields")
	var actor_max_health: Dictionary = EloriaProtocol.decode_server(73,
		PackedByteArray([0x34, 0x12, 120, 0]))
	_expect(actor_max_health.type == "actor_max_health"
		and actor_max_health.max_health == 120, "actor maximum-health fields")
	_expect(EloriaProtocol.decode_server(47, PackedByteArray([1, 0, 2])).type == "invalid",
		"malformed actor damage rejected")

	var actor_payload := PackedByteArray([
		0x34, 0x12, 10, 0, 20, 0, 0, 0, 0xff, 0xff, 1, 7,
		100, 0, 90, 0, 1, 66, 111, 98, 0])
	var actor := EloriaProtocol.decode_server(1, actor_payload)
	_expect(actor.type == "actor_spawn" and actor.actor_id == 0x1234, "actor id")
	_expect(actor.x == 10 and actor.y == 20 and actor.rotation == -1, "actor transform")
	_expect(actor.name == "Bob" and actor.health == 90, "actor identity and health")
	_expect(EloriaProtocol.decode_server(1, PackedByteArray([1])).type == "invalid",
		"short actor")
	var extended_actor_payload := PackedByteArray([
		0x35, 0x12, 11, 0, 21, 0, 0, 0, 0xfe, 0xff, 0x33, 0x01, 7,
		120, 0, 88, 0, 2, 84, 111, 114, 97, 110, 0])
	var extended_actor := EloriaProtocol.decode_server(247, extended_actor_payload)
	_expect(extended_actor.type == "actor_spawn"
		and extended_actor.actor_type == 307 and extended_actor.actor_id == 0x1235,
		"extended Nymara actor type")
	_expect(extended_actor.x == 11 and extended_actor.y == 21
		and extended_actor.rotation == -2 and extended_actor.name == "Toran",
		"extended Nymara actor fields")
	var equipment_config_file: FileAccess = FileAccess.open(
		"res://data/actors/equipment.json", FileAccess.READ)
	_expect(equipment_config_file != null, "equipment part registry opens")
	if equipment_config_file != null:
		var equipment_config_value: Variant = JSON.parse_string(equipment_config_file.get_as_text())
		_expect(equipment_config_value is Dictionary, "equipment part registry parses")
		if equipment_config_value is Dictionary:
			var equipment_parts: Dictionary = (equipment_config_value as Dictionary).get("parts", {})
			_expect(equipment_parts.size() == 8
				and str((equipment_parts.get("0", {}) as Dictionary).get("attachment", "")) == "right_hand"
				and str((equipment_parts.get("1", {}) as Dictionary).get("attachment", "")) == "left_hand",
				"weapon and shield use explicit native skeleton anchors")

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

	var walk_segment := ReplicatedActor3D.presentation_segment_duration(
		1.0, 6.0, 0.25, 1.05, 0.06, 0.75)
	_expect(is_equal_approx(walk_segment, 0.2625),
		"actor interpolation spans the 250 ms server cadence")
	var fast_segment := ReplicatedActor3D.presentation_segment_duration(
		1.0, 9.0, 0.125, 1.05, 0.06, 0.75)
	_expect(is_equal_approx(fast_segment, 0.13125),
		"actor interpolation adapts to double-speed cadence")
	var catchup_segment := ReplicatedActor3D.presentation_segment_duration(
		3.0, 6.0, 0.10, 1.05, 0.06, 0.75)
	_expect(is_equal_approx(catchup_segment, 0.5),
		"batched actor steps retain nominal catch-up speed")
	var capped_segment := ReplicatedActor3D.presentation_segment_duration(
		20.0, 6.0, 0.25, 1.05, 0.06, 0.75)
	_expect(is_equal_approx(capped_segment, 0.75),
		"large corrections cannot interpolate indefinitely")

	var reduced_actor: Dictionary = ActorReducer.apply_command(actor, 21)
	_expect(int(reduced_actor.get("x", -1)) == 11
		and int(reduced_actor.get("y", -1)) == 21, "actor movement reducer")
	reduced_actor = ActorReducer.apply_command(reduced_actor, 13)
	_expect(bool(reduced_actor.get("sitting", false)), "actor sit reducer")
	reduced_actor = ActorReducer.apply_command(reduced_actor, 14)
	_expect(not bool(reduced_actor.get("sitting", true)), "actor stand reducer")
	var animation_actor: ReplicatedActor3D = ReplicatedActor3D.new()
	animation_actor.resolver = AnimationResolver.new({"actions": {
		"idle": "Idle", "sit": "Sit", "seated_idle": "Seated", "stand": "Stand"}})
	var animation_player_fixture: AnimationPlayer = AnimationPlayer.new()
	var animation_library_fixture: AnimationLibrary = AnimationLibrary.new()
	for clip_name: String in ["Idle", "Sit", "Seated", "Stand"]:
		var clip_fixture: Animation = Animation.new()
		clip_fixture.length = 1.0
		animation_library_fixture.add_animation(clip_name, clip_fixture)
	animation_player_fixture.add_animation_library("", animation_library_fixture)
	animation_actor.animation_player = animation_player_fixture
	animation_actor.current_action = &"sit"
	animation_actor.call("_on_animation_finished", &"Sit")
	_expect(animation_actor.current_action == &"seated_idle",
		"completed sit transition advances to seated idle")
	animation_actor.current_action = &"stand"
	animation_actor.call("_on_animation_finished", &"Stand")
	_expect(animation_actor.current_action == &"idle",
		"completed stand transition returns to idle")
	reduced_actor = ActorReducer.apply_command(reduced_actor, 18)
	_expect(bool(reduced_actor.get("in_combat", false)), "actor enters combat")
	reduced_actor = ActorReducer.apply_command(reduced_actor, 19)
	_expect(not bool(reduced_actor.get("in_combat", true)), "actor leaves combat")
	reduced_actor = ActorReducer.apply_command(reduced_actor, 3)
	_expect(not bool(reduced_actor.get("alive", true))
		and int(reduced_actor.get("health", -1)) == 0, "actor death is authoritative")

	var stats_payload: PackedByteArray = PackedByteArray()
	stats_payload.resize(230)
	stats_payload.encode_s16(84, 18)
	stats_payload.encode_s16(86, 25)
	stats_payload.encode_s16(88, 12)
	stats_payload.encode_s16(90, 20)
	stats_payload.encode_s16(92, -7)
	var stats_event: Dictionary = EloriaProtocol.decode_server(18, stats_payload)
	_expect(stats_event.type == "stats" and int(stats_event.values.health) == 18
		and int(stats_event.values.max_health) == 25
		and int(stats_event.values.food) == -7, "full character stats")
	var partial_event: Dictionary = EloriaProtocol.decode_server(49,
		PackedByteArray([46, 0xfb, 0xff, 0xff, 0xff]))
	_expect(partial_event.type == "partial_stats" and int(partial_event.values.food) == -5,
		"signed partial food update")

	var inventory_payload: PackedByteArray = PackedByteArray([
		2,
		0x34, 0x12, 5, 0, 0, 0, 0, 12,
		0x78, 0x56, 0x2c, 0x01, 0, 0, 7, 6])
	var inventory_event: Dictionary = EloriaProtocol.decode_server(19, inventory_payload)
	_expect(inventory_event.type == "inventory" and inventory_event.items.size() == 2,
		"full inventory snapshot")
	_expect(int(inventory_event.items[0].image_id) == 0x1234
		and int(inventory_event.items[0].quantity) == 5
		and int(inventory_event.items[0].slot) == 0
		and bool(inventory_event.items[0].inventory_usable), "inventory item fields and flags")
	var inventory_update: Dictionary = EloriaProtocol.decode_server(21,
		PackedByteArray([0x34, 0x12, 4, 0, 0, 0, 0, 12]))
	_expect(inventory_update.type == "inventory_update"
		and int(inventory_update.item.quantity) == 4, "incremental inventory quantity")
	var inventory_remove: Dictionary = EloriaProtocol.decode_server(22,
		PackedByteArray([0, 7]))
	_expect(inventory_remove.type == "inventory_remove"
		and inventory_remove.slots == [0, 7], "batched inventory removal")
	var item_text: Dictionary = EloriaProtocol.decode_server(20,
		PackedByteArray([130, 80, 111, 116, 105, 111, 110, 0]))
	_expect(item_text.type == "inventory_text" and item_text.text == "Potion",
		"inventory inspection text")
	var ground_bag: Dictionary = EloriaProtocol.decode_server(27,
		PackedByteArray([0x34, 0x12, 0x78, 0x56, 7]))
	_expect(ground_bag.type == "ground_bag" and ground_bag.x == 0x1234
		and ground_bag.y == 0x5678 and ground_bag.bag_id == 7,
		"new ground bag fields")
	var ground_bags: Dictionary = EloriaProtocol.decode_server(28,
		PackedByteArray([2, 10, 0, 20, 0, 3, 30, 0, 40, 0, 4]))
	_expect(ground_bags.type == "ground_bags" and ground_bags.bags.size() == 2
		and ground_bags.bags[1].x == 30 and ground_bags.bags[1].bag_id == 4,
		"ground bag snapshot fields")
	var ground_items: Dictionary = EloriaProtocol.decode_server(23,
		PackedByteArray([2, 0x34, 0x12, 5, 0, 0, 0, 3,
			0x78, 0x56, 9, 0, 0, 0, 7]))
	_expect(ground_items.type == "ground_items" and ground_items.items.size() == 2
		and ground_items.items[0].image_id == 0x1234
		and ground_items.items[1].quantity == 9
		and ground_items.items[1].position == 7, "ground bag item fields")
	var ground_item_update: Dictionary = EloriaProtocol.decode_server(24,
		PackedByteArray([3, 0, 4, 0, 0, 0, 2]))
	_expect(ground_item_update.type == "ground_item"
		and ground_item_update.item.position == 2, "incremental ground item fields")
	_expect(EloriaProtocol.decode_server(25, PackedByteArray([3])).type ==
		"ground_item_remove" and EloriaProtocol.decode_server(26, PackedByteArray()).type ==
		"ground_bag_close" and EloriaProtocol.decode_server(29, PackedByteArray([7])).type ==
		"ground_bag_destroy", "ground bag lifecycle events")
	_expect(EloriaProtocol.decode_server(27, PackedByteArray([1])).type == "invalid"
		and EloriaProtocol.decode_server(28, PackedByteArray([1, 2])).type == "invalid"
		and EloriaProtocol.decode_server(23, PackedByteArray([1, 2])).type == "invalid"
		and EloriaProtocol.decode_server(26, PackedByteArray([0])).type == "invalid",
		"malformed ground bag packets rejected")
	var knowledge_list_event: Dictionary = EloriaProtocol.decode_server(55,
		PackedByteArray([0x09, 0x80]))
	_expect(knowledge_list_event.type == "knowledge_list"
		and knowledge_list_event.known == [0, 3, 15]
		and knowledge_list_event.capacity == 16, "knowledge ownership bitset")
	var new_knowledge_event: Dictionary = EloriaProtocol.decode_server(56,
		PackedByteArray([0x34, 0x12]))
	_expect(new_knowledge_event.type == "new_knowledge"
		and new_knowledge_event.index == 0x1234, "new knowledge index")
	var knowledge_text_event: Dictionary = EloriaProtocol.decode_server(57,
		PackedByteArray([77, 101, 116, 97, 108, 108, 117, 114, 103, 121, 0]))
	_expect(knowledge_text_event.type == "knowledge_text"
		and knowledge_text_event.text == "Metallurgy", "knowledge inspection text")
	_expect(EloriaProtocol.decode_server(56, PackedByteArray([1])).type == "invalid"
		and EloriaProtocol.decode_server(57, PackedByteArray()).type == "invalid",
		"malformed knowledge packets rejected")
	var trade_partner: Dictionary = EloriaProtocol.decode_server(41,
		PackedByteArray([1, 65, 108, 105, 99, 101, 0]))
	_expect(trade_partner.type == "trade_partner" and trade_partner.name == "Alice"
		and trade_partner.storage_available, "trade partner fields")
	var trade_inventory: Dictionary = EloriaProtocol.decode_server(40, inventory_payload)
	_expect(trade_inventory.type == "trade_inventory"
		and trade_inventory.items.size() == 2, "trade source inventory snapshot")
	var trade_object: Dictionary = EloriaProtocol.decode_server(35,
		PackedByteArray([0x34, 0x12, 5, 0, 0, 0, 1, 3, 1]))
	_expect(trade_object.type == "trade_object" and trade_object.image_id == 0x1234
		and trade_object.quantity == 5 and trade_object.source_type == 1
		and trade_object.slot == 3 and trade_object.other, "trade offer fields")
	var trade_remove: Dictionary = EloriaProtocol.decode_server(39,
		PackedByteArray([5, 0, 0, 0, 3, 0]))
	_expect(trade_remove.type == "trade_remove" and trade_remove.quantity == 5
		and trade_remove.slot == 3 and not trade_remove.other, "trade removal fields")
	var trade_accept: Dictionary = EloriaProtocol.decode_server(36, PackedByteArray([1]))
	_expect(trade_accept.type == "trade_accept" and trade_accept.other,
		"trade partner acceptance field")
	var trade_reject: Dictionary = EloriaProtocol.decode_server(37, PackedByteArray([0]))
	_expect(trade_reject.type == "trade_reject" and not trade_reject.other,
		"trade own rejection field")
	_expect(EloriaProtocol.decode_server(38, PackedByteArray()).type == "trade_exit",
		"trade exit event")
	_expect(EloriaProtocol.decode_server(35, PackedByteArray([1])).type == "invalid"
		and EloriaProtocol.decode_server(36, PackedByteArray()).type == "invalid"
		and EloriaProtocol.decode_server(38, PackedByteArray([0])).type == "invalid",
		"malformed trade packets rejected")
	var storage_categories: Dictionary = EloriaProtocol.decode_server(67,
		PackedByteArray([2, 0, 71, 101, 110, 101, 114, 97, 108, 0,
			4, 70, 108, 111, 119, 101, 114, 115, 0]))
	_expect(storage_categories.type == "storage_categories"
		and storage_categories.categories.size() == 2
		and storage_categories.categories[1].id == 4
		and storage_categories.categories[1].name == "Flowers",
		"storage category fields")
	var storage_items: Dictionary = EloriaProtocol.decode_server(68,
		PackedByteArray([0, 4, 0x34, 0x12, 5, 0, 0, 0, 0x78, 0x56]))
	_expect(storage_items.type == "storage_items" and storage_items.category_id == 4
		and not storage_items.update and storage_items.items.size() == 1
		and storage_items.items[0].position == 0x5678,
		"storage item fields")
	var storage_text: Dictionary = EloriaProtocol.decode_server(69,
		PackedByteArray([132, 83, 97, 102, 101, 0]))
	_expect(storage_text.type == "storage_text" and storage_text.text == "Safe",
		"storage inspection text")
	_expect(EloriaProtocol.decode_server(67, PackedByteArray([1, 0, 65])).type == "invalid"
		and EloriaProtocol.decode_server(68, PackedByteArray([0, 1, 2])).type == "invalid"
		and EloriaProtocol.decode_server(69, PackedByteArray()).type == "invalid",
		"malformed storage packets rejected")
	var cooldown_event: Dictionary = EloriaProtocol.decode_server(77,
		PackedByteArray([7, 30, 0, 12, 0, 2, 60, 0, 1, 0]))
	_expect(cooldown_event.type == "item_cooldowns"
		and cooldown_event.cooldowns.size() == 2
		and int(cooldown_event.cooldowns[0].slot) == 7
		and int(cooldown_event.cooldowns[0].maximum_seconds) == 30
		and int(cooldown_event.cooldowns[0].remaining_seconds) == 12,
		"batched item cooldown fields")
	_expect(EloriaProtocol.decode_server(77, PackedByteArray([1, 2])).type == "invalid",
		"malformed item cooldown rejected")
	var sigils_event: Dictionary = EloriaProtocol.decode_server(42,
		PackedByteArray([8, 0, 128, 0, 2, 0, 0, 0]))
	_expect(sigils_event.type == "sigils" and sigils_event.owned == [3, 23, 33],
		"two-word sigil ownership mask")
	_expect(EloriaProtocol.decode_server(42, PackedByteArray([8, 0, 0, 0])).type == "invalid",
		"malformed sigil mask rejected")
	var spell_result: Dictionary = EloriaProtocol.decode_server(70, PackedByteArray([4, 1]))
	_expect(spell_result.type == "spell_result" and spell_result.status == 4
		and spell_result.spell_id == 1, "spell target result fields")
	_expect(EloriaProtocol.decode_server(70, PackedByteArray([1])).type == "invalid",
		"malformed spell result rejected")
	var active_spell: Dictionary = EloriaProtocol.decode_server(44, PackedByteArray([3, 90]))
	_expect(active_spell.type == "active_spell" and active_spell.buff_id == 3
		and active_spell.duration_seconds == 90, "active spell duration fields")
	_expect(EloriaProtocol.decode_server(19, PackedByteArray([1, 0])).type == "invalid",
		"malformed inventory snapshot rejected")
	var knowledge_catalog_file: FileAccess = FileAccess.open(
		"res://data/knowledge/catalog.json", FileAccess.READ)
	_expect(knowledge_catalog_file != null, "knowledge catalog opens")
	if knowledge_catalog_file != null:
		var knowledge_catalog_value: Variant = JSON.parse_string(
			knowledge_catalog_file.get_as_text())
		_expect(knowledge_catalog_value is Dictionary, "knowledge catalog parses")
		if knowledge_catalog_value is Dictionary:
			var knowledge_entries: Array = (knowledge_catalog_value as Dictionary).get(
				"entries", []) as Array
			_expect(knowledge_entries.size() == 385
				and str(knowledge_entries[0]) == "Metallurgy"
				and str(knowledge_entries[1]) == "Metal Smelting",
				"knowledge catalog matches the audited server insertion order")
	var manufacturing_catalog_file: FileAccess = FileAccess.open(
		"res://data/manufacturing/recipes.json", FileAccess.READ)
	_expect(manufacturing_catalog_file != null, "manufacturing catalog opens")
	if manufacturing_catalog_file != null:
		var manufacturing_value: Variant = JSON.parse_string(
			manufacturing_catalog_file.get_as_text())
		_expect(manufacturing_value is Dictionary, "manufacturing catalog parses")
		if manufacturing_value is Dictionary:
			var manufacturing_data: Dictionary = manufacturing_value as Dictionary
			var manufacturing_recipes: Array = manufacturing_data.get("recipes", []) as Array
			var sources: Dictionary = manufacturing_data.get("sources", {}) as Dictionary
			_expect(manufacturing_recipes.size() == 389
				and str((manufacturing_recipes[0] as Dictionary).get("output", "")) == "Fire Essence"
				and str(sources.get("recipesSha256", "")) ==
					"e6d3c8988effb22f11cce1dcb553097860e066b0ca85eaa7bb01390809160d4e",
				"manufacturing catalog matches the audited unmodified server data")
			var catalog: ManufacturingCatalog = ManufacturingCatalog.new()
			catalog.configure(manufacturing_data)
			var ready: Dictionary = catalog.availability(0, {
				4: {"image_id": 42, "quantity": 1},
				5: {"image_id": 31, "quantity": 1},
				6: {"image_id": 35, "quantity": 1}}, [], {"food": 45, "ether": 0})
			var ready_selection: Array = ready.get("selection", []) as Array
			_expect((ready.get("reasons", []) as Array).is_empty()
				and ready_selection.size() == 3
				and int((ready_selection[0] as Dictionary).get("slot", -1)) == 4,
				"recipe resolves authoritative inventory slots and quantities")
			var missing: Dictionary = catalog.availability(0, {}, [],
				{"food": 45, "ether": 0})
			_expect((missing.get("reasons", []) as Array).size() == 3,
				"missing ingredients explicitly block manufacturing")
			var ambiguous: Dictionary = catalog.availability(173, {
				0: {"image_id": 50, "quantity": 1},
				1: {"image_id": 140, "quantity": 3}}, [], {"food": 45, "ether": 0})
			_expect(str((ambiguous.get("reasons", []) as Array)[0]).contains(
				"automatic selection is unavailable"),
				"ambiguous legacy item artwork never guesses an authoritative item")
	var atlas_config_file: FileAccess = FileAccess.open(
		"res://data/items/atlases.json", FileAccess.READ)
	_expect(atlas_config_file != null, "legacy item atlas registry opens")
	if atlas_config_file != null:
		var atlas_config_value: Variant = JSON.parse_string(atlas_config_file.get_as_text())
		_expect(atlas_config_value is Dictionary, "legacy item atlas registry parses")
		if atlas_config_value is Dictionary:
			var atlas: ItemAtlas = ItemAtlas.new()
			atlas.configure(atlas_config_value as Dictionary)
			var first_icon: Texture2D = atlas.icon_for(0)
			var last_icon: Texture2D = atlas.icon_for(124)
			_expect(first_icon is AtlasTexture and first_icon.get_size() == Vector2(50, 50),
				"first legacy item icon resolves at native aspect")
			_expect(last_icon is AtlasTexture and last_icon.get_size() == Vector2(50, 50),
				"fifth legacy item atlas resolves")
			_expect(not atlas.supports(125) and atlas.icon_for(125) != null
				and atlas.uses_substitute(125),
				"unsupported legacy item image receives the configured visible fallback")
			_expect(atlas.icon_for(114) != null and atlas.uses_substitute(114),
				"known legacy item image receives its data-driven Eloria substitute")
			var guard_spear_icon: AtlasTexture = atlas.icon_for(114) as AtlasTexture
			var guard_shield_icon: AtlasTexture = atlas.icon_for(397) as AtlasTexture
			var guard_cape_icon: AtlasTexture = atlas.icon_for(460) as AtlasTexture
			_expect(guard_spear_icon != null and guard_spear_icon.region.position == Vector2(150, 100),
				"Four Gates guard spear uses the configured independent weapon artwork")
			_expect(guard_shield_icon != null and guard_shield_icon.region.position == Vector2(50, 150),
				"Four Gates guard shield uses the configured independent shield artwork")
			_expect(guard_cape_icon != null and guard_cape_icon.region.position == Vector2(200, 200),
				"Four Gates guard cape uses the configured independent cloak artwork")
	var spell_config_file: FileAccess = FileAccess.open(
		"res://data/spells/catalog.json", FileAccess.READ)
	_expect(spell_config_file != null, "spell catalog opens")
	if spell_config_file != null:
		var spell_config_value: Variant = JSON.parse_string(spell_config_file.get_as_text())
		_expect(spell_config_value is Dictionary, "spell catalog parses")
		if spell_config_value is Dictionary:
			var spell_catalog: SpellCatalog = SpellCatalog.new()
			spell_catalog.configure(spell_config_value as Dictionary)
			var heal: Dictionary = spell_catalog.spell(0)
			var heal_sigils: Array = heal.get("sigils", []) as Array
			_expect(heal_sigils.size() == 2 and int(heal_sigils[0]) == 3
				and int(heal_sigils[1]) == 23,
				"Heal uses the audited ordered sigil sequence")
			var heal_icon: Texture2D = spell_catalog.icon_for(0)
			_expect(heal_icon is AtlasTexture and heal_icon.get_size() == Vector2(64, 64),
				"legacy spell icon resolves at native aspect")
			var ready_reasons: Array[String] = spell_catalog.unavailable_reasons(0,
				[3, 23], {"magic": 0, "ether": 5}, {0: {
					"image_id": 59, "quantity": 1}})
			_expect(ready_reasons.is_empty(), "owned Heal requirements are locally ready")
			var blocked_reasons: Array[String] = spell_catalog.unavailable_reasons(0,
				[3], {"magic": 0, "ether": 4}, {})
			_expect(blocked_reasons.size() == 3, "missing sigil, mana, and reagent are explicit")

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
