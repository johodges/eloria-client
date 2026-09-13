extends SceneTree
## Repeatable landscape survey in the complete client, using its actual camera,
## environment, static batching, ground sampler, minimap and occluder fade.
## ELORIA_SURVEY_SPEC points at JSON [{map,id,x,z,yaw?,distance?}].
var main: Control
var state: Node
var out: String
var report: Array = []

static func _override_registry(registry: Dictionary, data: Dictionary, path: String, specs: Array) -> Dictionary:
	var entry := MapRegistry.resolve(registry, str(data.get("asset", {}).get("id", "")))
	if entry.is_empty() or path.is_empty() or not data.get("coordinateTransform") is Dictionary:
		return {"error": "Candidate manifest has no unique registry target/path/coordinate transform"}
	var key := str(entry.registryKey)
	var selected := false
	for spec: Dictionary in specs:
		if str(MapRegistry.resolve(registry, str(spec.get("map", ""))).get("registryKey", "")) == key:
			selected = true
	if not selected:
		return {"error": "Candidate registry target is absent from the requested survey: " + key}
	# Resolve aliases exactly as the production loader does. Four's asset id
	# is four-gates, whose alias points to the actual four_gates registry row.
	registry[key]["manifest"] = path
	registry[key]["coordinateTransform"] = data.coordinateTransform.duplicate(true)
	return {"registryKey": key, "manifest": path}

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	out = OS.get_environment("ELORIA_ARTIFACT_DIR")
	DirAccess.make_dir_recursive_absolute(out)
	root.size = Vector2i(1440, 900)
	main = (load("res://src/app/main.tscn") as PackedScene).instantiate()
	root.add_child(main)
	await process_frame
	state = root.get_node("AppState")
	var specs: Array = JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("ELORIA_SURVEY_SPEC")))
	var override_path := OS.get_environment("ELORIA_SURVEY_MANIFEST")
	var override_key := ""
	if not override_path.is_empty():
		var override_data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(override_path))
		var registry: Dictionary = main.get("map_registry")
		var applied := _override_registry(registry, override_data, override_path, specs)
		if applied.has("error"):
			push_error(str(applied.error))
			quit(2)
			return
		override_key = str(applied.registryKey)
		print("SURVEY_OVERRIDE selected asset=", override_data.asset.id,
			" registry_key=", override_key, " manifest=", override_path)
	state.set("authenticated", true)
	main.get("login_panel").hide()
	main.get("creation_panel").hide()
	main.get("game_view").show()
	state.call("_on_packet", 5, PackedByteArray([180, 0]))
	for spec: Dictionary in specs:
		if state.get("current_map") != spec.map:
			state.set("current_map", spec.map)
			main.call("_load_server_map")
			var loader: WorldLoader = main.get("world_loader")
			var deadline := Time.get_ticks_msec() + 180000
			while loader.world_root == null and Time.get_ticks_msec() < deadline:
				await process_frame
			if loader.world_root == null:
				push_error("Map failed to load: " + str(spec.map))
				quit(2)
				return
		var active_loader: WorldLoader = main.get("world_loader")
		if not override_key.is_empty() and str(MapRegistry.resolve(main.get("map_registry"), spec.map).get("registryKey", "")) == override_key:
			var actual := ProjectSettings.globalize_path(active_loader.manifest.source_path).replace("\\", "/").simplify_path()
			var expected := ProjectSettings.globalize_path(override_path).replace("\\", "/").simplify_path()
			if actual != expected:
				push_error("Candidate override was not loaded: expected=" + expected + " actual=" + actual)
				quit(2)
				return
			print("SURVEY_OVERRIDE loaded registry_key=", override_key, " manifest=", actual,
				" glb=", active_loader.manifest.glb_path())
		var adapter: CoordinateAdapter = main.get("adapter")
		var tile: Vector2i = adapter.godot_to_server(Vector3(float(spec.x), 0, float(spec.z)))
		var actors := {1: {"actor_id": 1, "x": tile.x, "y": tile.y,
			"rotation": 0, "actor_type": 0, "kind": 1, "name": "Traveller",
			"health": 100, "max_health": 100, "alive": true, "appearance": {}}}
		state.set("local_actor_id", 1)
		state.set("actors", actors)
		state.call("mark_all_actors_changed")
		main.call("_sync_world")
		var rig: Node3D = main.get("camera_rig")
		rig.set("yaw_degrees", float(spec.get("yaw", 0)))
		rig.set("pitch_degrees", -60.0)
		rig.set("distance", float(spec.get("distance", 26)))
		# Let camera interpolation and the HUD's one-second FPS window settle
		# after a large package load before taking a composition/performance view.
		for i in 120:
			await physics_frame
			await process_frame
		# A border capture must include the actual resident neighbor. Time-based
		# camera settling alone can finish before a cold background import.
		var stream: ExteriorRegionStream = main.get("exterior_stream")
		var candidates := stream._candidates(rig.get("focus"))
		var wanted := stream._wanted_neighbours(candidates)
		for candidate: Dictionary in candidates:
			if (wanted.has(str(candidate.map)) and float(candidate.distance) <= stream.preload_distance
					and (bool(candidate.seamless) or bool(candidate.visual_only))):
				var deadline := Time.get_ticks_msec() + 60000
				while not stream.residents.has(str(candidate.map)) and Time.get_ticks_msec() < deadline:
					await process_frame
				if not stream.residents.has(str(candidate.map)):
					push_error("Neighbor failed to preload for survey")
					quit(2)
					return
		var actor: Node3D = main.get("actor_nodes").get(1)
		var times: Array = []
		for i in 30:
			var start := Time.get_ticks_usec()
			await process_frame
			times.append((Time.get_ticks_usec() - start) / 1000.0)
		RenderingServer.force_draw(false)
		root.get_texture().get_image().save_png(out.path_join(str(spec.id) + ".png"))
		report.append({"id":spec.id,"map":spec.map,"tile":[tile.x,tile.y],
			"manifest_source":active_loader.manifest.source_path,"glb_path":active_loader.manifest.glb_path(),
			"actor":[actor.position.x,actor.position.y,actor.position.z] if actor else [],
			"resident_maps":stream.residents.keys(), "preload_distance":stream.preload_distance,
			"camera":str(rig.call("camera_diagnostics")), "frame_ms":times,
			"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
			"primitives":Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)})
		print("SURVEY saved ", spec.id)
	var file := FileAccess.open(out.path_join("survey.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  "))
	main.call("_on_disconnect_pressed")
	main.get("exterior_stream").clear()
	while not main.get("exterior_stream").is_idle():
		await process_frame
	for i in 6:
		await process_frame
	main.queue_free()
	await process_frame
	quit()
