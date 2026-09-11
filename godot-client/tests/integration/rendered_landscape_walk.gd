extends SceneTree

## Walks authored landscape routes with a temporary character on a real server.
## Movement and map changes are authoritative; captures check runtime grounding.

const TIMEOUT := 90.0
const SCREEN := Vector2i(1440, 900)
const GROUND_TOLERANCE := 0.6

var _failures := 0
var _artifacts := ""
var _main: Control
var _state: Node
var _network: Node
var _loader: WorldLoader
var _report: Dictionary = {"checks": [], "transitions": []}

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_artifacts = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifacts.is_empty():
		_artifacts = ProjectSettings.globalize_path("res://test-artifacts/transition")
	DirAccess.make_dir_recursive_absolute(_artifacts)
	root.size = SCREEN
	_main = (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(_main)
	await process_frame
	_state = root.get_node("AppState")
	_network = root.get_node("Network")

	var host: String = OS.get_environment("ELORIA_INTEGRATION_HOST")
	if host.is_empty():
		host = "127.0.0.1"
	var port_text: String = OS.get_environment("ELORIA_INTEGRATION_PORT")
	var port: int = int(port_text) if port_text.is_valid_int() else 2000
	var user: String = "LandscapeQA"
	var password: String = "qa_" + str(randi())

	(_main.get_node("LoginPanel/Content/Host") as LineEdit).text = host
	(_main.get_node("LoginPanel/Content/Port") as SpinBox).value = port
	_main.call("_on_connect_pressed")
	_expect(await _wait(func() -> bool:
		return str(_state.get("connection_state")) == "connected", TIMEOUT),
		"connected to the local test server")
	_main.call("_on_new_character_pressed")
	(_main.get_node("CreationPanel/Columns/Form/CreateName") as LineEdit).text = user
	(_main.get_node("CreationPanel/Columns/Form/CreatePassword") as LineEdit).text = password
	(_main.get_node("CreationPanel/Columns/Form/CreateConfirm") as LineEdit).text = password
	_main.call("_on_create_pressed")
	_expect(await _wait(func() -> bool:
		return bool(_state.get("authenticated")), TIMEOUT),
		"temporary character logged in")
	_loader = _main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot/WorldLoader") as WorldLoader
	_expect(await _wait(func() -> bool: return not str(_state.get("current_map")).is_empty(), TIMEOUT),
		"initial world arrived")
	# New characters now begin in a private tutorial. Leave through its normal
	# confirmation before the administrator requests an exterior test route.
	if str(_state.get("current_map")).begins_with("lantern_reach"):
		_network.call("send_chat", "#tutorial skip")
		_expect(await _wait(func() -> bool: return int(_state.get("popup").get("popup_id", -1)) == 4100, TIMEOUT),
			"tutorial skip confirmation arrived")
		_main.call("_on_popup_option_pressed", 1, 1)
		_expect(await _wait(func() -> bool: return str(_state.get("current_map")) == "four_gates", TIMEOUT),
			"temporary character left the tutorial")
	_network.call("send_chat", "#demigod")
	var specs: Array = JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("ELORIA_WALK_SPEC")))
	for route: Dictionary in specs:
		var map_id: String = str(route.get("map", "amberwood"))
		var start: Array = route.start
		_network.call("send_chat", "#invasion_assistant teleport %s %d %d" % [map_id, int(start[0]), int(start[1])])
		# Admin arrivals may move to a nearby unoccupied tile. Only fixtures
		# that explicitly allow it relax their start; route targets remain exact.
		var arrived: bool = await _wait(func() -> bool:
			return _near(map_id, start, int(route.get("startTolerance", 0))), 120)
		_expect(arrived, str(route.id) + " start")
		if not arrived: continue
		await _settle(20)
		_main.get("invasion_assistant_window").hide()
		_main.call("_on_popup_dismiss_pressed")
		var rig: Node3D = _main.get("camera_rig")
		rig.set("yaw_degrees", float(route.get("yaw", 0)))
		rig.set("pitch_degrees", -60.0)
		rig.set("distance", float(route.get("distance", 26)))
		var walked := 0
		for step: Dictionary in route.steps:
			var target: Array = step.tile
			var walk_timeout: float = float(step.get("walkTimeout", route.get("walkTimeout", 45)))
			var began: int = Time.get_ticks_msec()
			_issue_walk(step)
			var destination: String = str(step.get("destination", map_id))
			var reached: bool
			if step.has("destination"):
				var ready_to_enter := true
				if step.has("object"):
					ready_to_enter = await _wait(func() -> bool: return _near(map_id, target, 2), walk_timeout)
					if ready_to_enter:
						_network.call("use_map_object", int(step.object))
				reached = await _on_map(destination) if ready_to_enter else false
				if bool(step.get("clickNeighbor", false)) and reached:
					reached = await _wait(func() -> bool: return _at(destination, target), walk_timeout)
			else:
				reached = await _wait(func() -> bool: return _at(map_id, target), walk_timeout)
			if reached and step.has("useObject"):
				var chat_cursor: int = (_state.get("chat_lines") as Array).size()
				if bool(step.get("expectStorage", false)):
					_state.call("close_storage")
				_network.call("use_map_object", int(step.useObject))
				if bool(step.get("expectStorage", false)):
					reached = await _wait(func() -> bool:
						return bool((_state.get("storage") as Dictionary).get("open", false)), 10)
					_expect(reached, "%s / %s storage opened" % [route.id, step.get("label", str(walked))])
				if reached and step.has("expectText"):
					reached = await _wait(func() -> bool:
						return _chat_contains_after(chat_cursor, str(step.expectText)), 10)
					_expect(reached, "%s / %s interaction replied" % [route.id, step.get("label", str(walked))])
			if not _report.has("walk_steps"): _report["walk_steps"] = []
			(_report["walk_steps"] as Array).append({"route": route.id, "target": target,
				"map": str(_state.get("current_map")), "ok": reached,
				"used_object": int(step.get("useObject", -1)),
				"storage_open": bool((_state.get("storage") as Dictionary).get("open", false)),
				"seconds": (Time.get_ticks_msec() - began) / 1000.0,
				"actor": (_state.get("actors") as Dictionary).get(int(_state.get("local_actor_id")), {}).duplicate(true)})
			_expect(reached, "%s / %s (%d,%d)" % [route.id, step.get("label", str(walked)), int(target[0]), int(target[1])])
			if not reached:
				var current: Dictionary = (_state.get("actors") as Dictionary).get(int(_state.get("local_actor_id")), {})
				_report["failure_actor"] = current
				await _capture("failed-" + str(route.id) + "-" + str(walked) + ".png")
				break
			walked += 1
			await _settle(10)
			if step.has("capture"):
				# Network arrival precedes the interpolated body. Measure its final
				# footing once presentation has arrived, without relaxing grounding.
				_expect(await _wait(_presentation_arrived, 3), "presentation arrived: " + str(step.capture))
				var grounding: Dictionary = _ground(str(step.capture))
				_expect(bool(grounding.get("ok", false)), "grounded: " + str(step.capture))
				await _capture(str(step.capture) + ".png")
			if bool(step.get("expectStorage", false)):
				_state.call("close_storage")
			map_id = destination
		_report["routes_completed"] = int(_report.get("routes_completed", 0)) + int(walked == route.steps.size())
		_write_report()
	_write_report()
	print("Landscape route walk: ", "PASS" if _failures == 0 else "FAIL")
	_main.call("_on_disconnect_pressed")
	_main.get("exterior_stream").clear()
	while not _main.get("exterior_stream").is_idle():
		await process_frame
	await _settle(6)
	_main.queue_free()
	await process_frame
	quit(_failures)

func _issue_walk(step: Dictionary) -> void:
	var target: Array = step.tile
	if not bool(step.get("clickNeighbor", false)):
		_network.call("move_to", Vector2i(int(target[0]), int(target[1])), false)
		return
	var stream: ExteriorRegionStream = _main.get("exterior_stream")
	var resident: Dictionary = stream.residents[str(step.destination)]
	var far_adapter := (resident.manifest as WorldManifest).coordinate_adapter()
	var point: Vector3 = resident.root.transform * far_adapter.server_to_godot(float(target[0]) + .1, float(target[1]) + .1)
	var space: PhysicsDirectSpaceState3D = _main.get("gameplay_world").direct_space_state
	var query := PhysicsRayQueryParameters3D.create(Vector3(point.x, 400, point.z), Vector3(point.x, -200, point.z), ExteriorRegionStream.PREVIEW_SURFACE_LAYER)
	var hit := space.intersect_ray(query)
	_expect(not hit.is_empty(), "clicked neighbor has an actual rendered walking surface")
	if hit.is_empty(): return
	point = hit.position
	var camera: Camera3D = _main.get("gameplay_camera")
	var screen := camera.unproject_position(point)
	_expect(Rect2(Vector2.ZERO, Vector2(camera.get_viewport().size)).has_point(screen), "neighbor destination is visible in the gameplay camera")
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.position = screen
	_main.call("_handle_world_click", click, screen)

func _write_report() -> void:
	_report["failures"] = _failures
	var file := FileAccess.open(_artifacts.path_join("walk-report.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(_report, "  "))

func _near(map_id: String, tile: Array, tolerance: int) -> bool:
	if str(_state.get("current_map")) != map_id or _loader.world_root == null: return false
	var actor: Dictionary = (_state.get("actors") as Dictionary).get(int(_state.get("local_actor_id")), {})
	return not actor.is_empty() and abs(int(actor.get("x", -999))-int(tile[0])) <= tolerance and abs(int(actor.get("y", -999))-int(tile[1])) <= tolerance

func _at(map_id: String, tile: Array) -> bool:
	return _near(map_id, tile, 0)

func _on_map(name: String) -> bool:
	return await _wait(func() -> bool:
		return (str(_state.get("current_map")) == name
			and _loader.world_root != null
			and (_main.get("actor_nodes") as Dictionary).has(
				int(_state.get("local_actor_id")))), TIMEOUT)

func _chat_contains_after(cursor: int, expected: String) -> bool:
	var lines: Array = _state.get("chat_lines")
	for index in range(cursor, lines.size()):
		if str((lines[index] as Dictionary).get("text", "")).contains(expected):
			return true
	return false

func _presentation_arrived() -> bool:
	var actor: ReplicatedActor3D = (_main.get("actor_nodes") as Dictionary).get(int(_state.get("local_actor_id"))) as ReplicatedActor3D
	return is_instance_valid(actor) and actor.global_position.distance_to(actor.server_target) < 0.01

func _ground(label: String) -> Dictionary:
	var nodes: Dictionary = _main.get("actor_nodes") as Dictionary
	var actor: Node3D = nodes.get(int(_state.get("local_actor_id"))) as Node3D
	var result: Dictionary = {"label": label, "map": str(_state.get("current_map"))}
	if actor == null:
		result["ok"] = false
		(_report["transitions"] as Array).append(result)
		return result
	var space: PhysicsDirectSpaceState3D = _main.get("gameplay_world").direct_space_state
	var query := PhysicsRayQueryParameters3D.create(
		Vector3(actor.global_position.x, 400.0, actor.global_position.z),
		Vector3(actor.global_position.x, -200.0, actor.global_position.z),
		WorldLoader.NAVIGATION_SURFACE_LAYER)
	var hit: Dictionary = space.intersect_ray(query)
	result["actor_y"] = actor.global_position.y
	if hit.is_empty():
		result["ok"] = false
		result["error"] = "no navigation surface"
	else:
		result["surface_y"] = (hit["position"] as Vector3).y
		result["delta"] = actor.global_position.y - float(result["surface_y"])
		result["ok"] = absf(result["delta"]) <= GROUND_TOLERANCE
	(_report["transitions"] as Array).append(result)
	return result

func _wait(predicate: Callable, seconds: float) -> bool:
	var deadline: int = Time.get_ticks_msec() + roundi(seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if bool(predicate.call()):
			return true
		await process_frame
	return bool(predicate.call())

func _settle(frames: int) -> void:
	for _i: int in range(frames):
		await physics_frame
		await process_frame

func _capture(name: String) -> void:
	await _settle(4)
	_main.get("invasion_assistant_window").hide()
	await process_frame
	RenderingServer.force_draw(false)
	_expect(root.get_texture().get_image().save_png(_artifacts.path_join(name)) == OK,
		"saved " + name)

func _expect(condition: bool, message: String) -> void:
	(_report["checks"] as Array).append({"ok": condition, "check": message})
	if condition:
		print("PASS: ", message)
		return
	_failures += 1
	push_error("FAIL: " + message)
