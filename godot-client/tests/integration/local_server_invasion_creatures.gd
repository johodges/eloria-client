extends SceneTree

# Cross-repository acceptance test. Start the independent eloria-server profile
# locally, then run this script with ELORIA_INTEGRATION_HOST/PORT. The test
# creates one throwaway character, issues a real #invasion command for every
# production creature, and constructs each received actor through the normal
# client presentation pipeline.
const TIMEOUT_SECONDS := 12.0
const USERNAME := "CreatureVerifier"
const PASSWORD := "LocalCreaturePass"
const ROSTER: Array[Dictionary] = [
	{"actor_type": 400, "slug": "mirrorfin_otter"},
	{"actor_type": 401, "slug": "reedhorn_stag"},
	{"actor_type": 402, "slug": "gate_turtle"},
	{"actor_type": 403, "slug": "lakeglass_drake"},
	{"actor_type": 404, "slug": "snowcrest_hare"},
	{"actor_type": 405, "slug": "glacier_ram"},
	{"actor_type": 406, "slug": "iceback_ursid"},
	{"actor_type": 407, "slug": "rimeclaw"},
	{"actor_type": 408, "slug": "crystal_mite"},
	{"actor_type": 409, "slug": "resonant_hound"},
	{"actor_type": 410, "slug": "stormglass_grazer"},
	{"actor_type": 411, "slug": "prism_wyrm"},
	{"actor_type": 412, "slug": "dunrunner"},
	{"actor_type": 413, "slug": "steppe_aurochs"},
	{"actor_type": 414, "slug": "sunmane_cat"},
	{"actor_type": 415, "slug": "dustscale_drake"},
	{"actor_type": 416, "slug": "amberhart"},
	{"actor_type": 417, "slug": "rootback_boar"},
	{"actor_type": 418, "slug": "moor_wisp_hound"},
	{"actor_type": 419, "slug": "barrow_quillbeast"},
	{"actor_type": 420, "slug": "canopy_glider"},
	{"actor_type": 421, "slug": "cenote_toader"},
	{"actor_type": 422, "slug": "scalevine_stalker"},
	{"actor_type": 423, "slug": "sunscale_basilisk"},
	{"actor_type": 424, "slug": "mangrove_crab"},
	{"actor_type": 425, "slug": "mudskipper_beast"},
	{"actor_type": 426, "slug": "delta_crocodile"},
	{"actor_type": 427, "slug": "floodmaw"},
]

var _failures := 0
var _models: Dictionary
var _equipment: Dictionary
var _animations: Dictionary


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var host: String = OS.get_environment("ELORIA_INTEGRATION_HOST")
	if host.is_empty():
		host = "127.0.0.1"
	var port_text: String = OS.get_environment("ELORIA_INTEGRATION_PORT")
	var port: int = int(port_text) if port_text.is_valid_int() else 2000
	_models = _read_json("res://data/actors/models.json")
	_equipment = _read_json("res://data/actors/equipment.json")
	_animations = _read_json("res://data/animations/creature.json")
	_expect(not _models.is_empty(), "client model registry loads")
	_expect(not _animations.is_empty(), "creature animation mapping loads")
	await _verify_server_roster(host, port)
	print("local server invasion creatures: ", "PASS" if _failures == 0 else "FAIL")
	quit(_failures)


func _verify_server_roster(host: String, port: int) -> void:
	var state := {
		"connected": false,
		"created": false,
		"logged_in": false,
		"error": "",
		"actors": {},
		"chat": [],
	}
	var network := EloriaNetworkClient.new()
	network.name = "InvasionCreatureRoundTrip"
	network.connection_state_changed.connect(func(value: String) -> void:
		state["connected"] = value == "connected")
	network.protocol_error.connect(func(message: String) -> void:
		state["error"] = message)
	var packet_handler: Callable = func(command: int, payload: PackedByteArray) -> void:
		var event: Dictionary = EloriaProtocol.decode_server(command, payload)
		match str(event.get("type", "")):
			"create_character_ok":
				state["created"] = true
			"create_character_error":
				state["error"] = str(event.get("message", "creation rejected"))
			"login_ok":
				state["logged_in"] = true
			"login_error":
				state["error"] = str(event.get("message", "login rejected"))
			"actor_spawn":
				var actor_type: int = int(event.get("actor_type", -1))
				if actor_type >= 400 and actor_type <= 427:
					(state["actors"] as Dictionary)[actor_type] = event.duplicate(true)
			"chat":
				(state["chat"] as Array).append(str(event.get("text", "")))
			"ping_request":
				network.send_frame(EloriaProtocol.encode(
					EloriaProtocol.ClientMessage.PING_RESPONSE))
	network.packet_received.connect(packet_handler)
	root.add_child(network)
	_expect(network.connect_to_server(host, port) == OK,
		"begins local TCP connection")
	_expect(await _wait_for(func() -> bool:
		return bool(state.connected) or not str(state.error).is_empty()),
		"connects to local server")
	if not bool(state.connected):
		_fail("connection error: " + str(state.error))
		network.queue_free()
		return
	_expect(network.create_character(USERNAME, PASSWORD, {
		"skin": 1, "hair": 2, "shirt": 3, "pants": 4,
		"boots": 5, "actor_type": 1, "head": 0, "eyes": 1,
	}) == OK, "creates authorized throwaway character")
	_expect(await _wait_for(func() -> bool:
		return bool(state.created) or not str(state.error).is_empty()),
		"server accepts throwaway character")
	if not bool(state.created):
		_fail("character creation error: " + str(state.error))
		network.disconnect_from_server()
		network.queue_free()
		return
	_expect(network.login(USERNAME, PASSWORD) == OK, "sends local login")
	_expect(await _wait_for(func() -> bool:
		return bool(state.logged_in) or not str(state.error).is_empty()),
		"logs into local four_gates map")
	if not bool(state.logged_in):
		_fail("login error: " + str(state.error))
		network.disconnect_from_server()
		network.queue_free()
		return
	for entry: Dictionary in ROSTER:
		await _invade_and_construct(network, state, entry)
	network.disconnect_from_server()
	network.queue_free()
	for unused_frame: int in range(3):
		await process_frame


func _invade_and_construct(network: EloriaNetworkClient, state: Dictionary,
		entry: Dictionary) -> void:
	var actor_type: int = int(entry.actor_type)
	var slug: String = str(entry.slug)
	(state.actors as Dictionary).erase(actor_type)
	var chat_start: int = (state.chat as Array).size()
	_expect(network.send_chat(
		"#invasion 792 480 four_gates %s 1" % slug) == OK,
		"issues #invasion for %s" % slug)
	_expect(await _wait_for(func() -> bool:
		return ((state.actors as Dictionary).has(actor_type)
			or not str(state.error).is_empty())),
		"receives actor type %d from the server" % actor_type)
	if not (state.actors as Dictionary).has(actor_type):
		_fail("server did not spawn %s: %s" % [slug, state.error])
		return
	var dto: Dictionary = (state.actors as Dictionary)[actor_type] as Dictionary
	_expect(int(dto.get("actor_type", -1)) == actor_type,
		"server preserves actor type %d" % actor_type)
	var resolved_model: String = str((_models.get("actorTypes", {}) as Dictionary).get(
		str(actor_type), ""))
	_expect(resolved_model == slug,
		"actor type %d resolves to bespoke %s model" % [actor_type, slug])
	var model_config: Dictionary = (_models.get("models", {}) as Dictionary).get(
		resolved_model, {}) as Dictionary
	var actor := ReplicatedActor3D.new()
	actor.name = "ServerInvaded_%s" % slug
	root.add_child(actor)
	var errors: Array[String] = actor.configure(
		dto, CoordinateAdapter.new({"walkingHeight": 0.0}), model_config,
		_animations, _equipment)
	for unused_frame: int in range(4):
		await process_frame
	_expect(errors.is_empty(), slug + " constructs without client errors: "
		+ ", ".join(errors))
	_expect(actor.get_node_or_null("NativeModel") != null,
		slug + " loads its native GLB")
	_expect(actor.get_node_or_null("MissingModelFallback") == null,
		slug + " does not create the magenta fallback")
	var diagnostics: Dictionary = _mesh_diagnostics(actor)
	_expect(int(diagnostics.vertices) > 5000,
		slug + " exceeds the production geometry floor")
	_expect(int(diagnostics.textured_surfaces) >= 3,
		slug + " exposes PBR base-color textures across primary surfaces")
	_expect(int(diagnostics.normal_surfaces) >= 3,
		slug + " exposes normal maps across primary surfaces")
	actor.queue_free()
	await process_frame
	_expect(network.send_chat("#clear_invasion") == OK,
		"clears %s before the next comparison" % slug)
	_expect(await _wait_for(func() -> bool:
		for index: int in range(chat_start, (state.chat as Array).size()):
			if "cleared" in str((state.chat as Array)[index]).to_lower():
				return true
		return false), "server confirms %s was cleared" % slug)


func _mesh_diagnostics(actor: ReplicatedActor3D) -> Dictionary:
	var vertices := 0
	var textured_surfaces := 0
	var normal_surfaces := 0
	for node_value: Node in actor.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		if mesh_node.mesh == null or mesh_node.name == "SelectionRing":
			continue
		for surface: int in range(mesh_node.mesh.get_surface_count()):
			vertices += mesh_node.mesh.surface_get_array_len(surface)
			var material: Material = mesh_node.get_active_material(surface)
			if material is StandardMaterial3D:
				var standard := material as StandardMaterial3D
				if standard.albedo_texture != null:
					textured_surfaces += 1
				if standard.normal_enabled and standard.normal_texture != null:
					normal_surfaces += 1
	return {
		"vertices": vertices,
		"textured_surfaces": textured_surfaces,
		"normal_surfaces": normal_surfaces,
	}


func _read_json(path: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed as Dictionary if parsed is Dictionary else {}


func _wait_for(predicate: Callable) -> bool:
	var deadline := Time.get_ticks_msec() + int(TIMEOUT_SECONDS * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if predicate.call():
			return true
		await process_frame
	return bool(predicate.call())


func _expect(condition: bool, message: String) -> void:
	if condition:
		print("PASS: ", message)
		return
	_fail(message)


func _fail(message: String) -> void:
	_failures += 1
	push_error("FAIL: " + message)
