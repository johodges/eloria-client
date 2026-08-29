# Verify a region package through the real client path, in-engine.
#
# `verify_runtime.py` reproduces the grounding contract offline, in Python,
# from the GLB. This does the same thing the other way round: it loads the
# package with the project's own WorldLoader, lets it build collision and
# navigation exactly as the game does, and casts main.gd's grounding ray
# (y = 400 down to y = -100, on NAVIGATION_SURFACE_LAYER) against the physics
# world. If the two agree, the offline check is trustworthy for this package.
#
# Run from the godot-client directory:
#   Godot_v4.7.2-stable_win64_console.exe --path . --headless \
#     --script ../eloria-assets/maps/nymara-regions/_toolkit/region_client_check.gd -- \
#     --manifest=<abs path to world.json> [--step=4] [--report=<abs path>]
extends SceneTree

const RAY_TOP := 400.0
const RAY_BOTTOM := -100.0


func _args() -> Dictionary:
	var out := {}
	for raw in OS.get_cmdline_user_args():
		var arg := str(raw)
		if arg.begins_with("--") and arg.contains("="):
			var parts := arg.substr(2).split("=", true, 1)
			out[parts[0]] = parts[1]
	return out


func _init() -> void:
	var opts := _args()
	var manifest_path: String = opts.get("manifest", "")
	if manifest_path == "":
		printerr("[client-check] need --manifest=<world.json>")
		quit(2)
		return
	var step: int = int(opts.get("step", "4"))
	var report_path: String = opts.get("report", "")

	var root := get_root()
	var world_root := Node3D.new()
	world_root.name = "WorldRoot"
	root.add_child(world_root)

	var loader := WorldLoader.new()
	world_root.add_child(loader)
	loader.load_world(manifest_path)

	var manifest: Dictionary = loader.manifest.data
	if manifest.is_empty():
		printerr("[client-check] WorldLoader produced no manifest")
		quit(2)
		return
	var warnings: Array = loader.manifest.warnings
	print("[client-check] loader warnings=%d" % warnings.size())
	for w in warnings:
		print("    warning: ", w)

	# Collision and navigation bodies only exist once the physics server has
	# stepped; querying before that reports an empty world.
	for i in 4:
		await process_frame
	await physics_frame
	await physics_frame

	var space := world_root.get_world_3d().direct_space_state

	var transform: Dictionary = manifest.get("coordinateTransform", {})
	var adapter := CoordinateAdapter.new(transform)
	var cells: int = int(manifest.get("bounds", {}).get("serverCells", 0))
	if cells <= 0:
		var collision: Dictionary = manifest.get("collision", {})
		cells = int(round(float(collision.get("width", 0))
			* float(collision.get("cellMetres", 0.5))))
	if cells <= 0:
		printerr("[client-check] cannot determine the server grid size")
		quit(2)
		return
	print("[client-check] server grid %dx%d, sampling every %d tiles" % [cells, cells, step])

	# A combined insides map is mostly deliberate void: several interiors on one
	# map with blackspace between them, in the Eternal Lands convention. "Every
	# tile must ground" is the right test for a region and the wrong one for
	# that - it reports 85% misses and fails a map that is correct.
	#
	# So when the manifest declares `spaces`, which only an interior package
	# does, the criterion becomes "every tile *inside an authored space* must
	# ground". That is the part that matters, it is precise, and it reads data
	# already in the manifest rather than a flag somebody has to remember to
	# pass.
	var spaces: Array = []
	for value in (manifest.get("spaces", {}) as Dictionary).values():
		var entry := value as Dictionary
		spaces.append(Rect2(float(entry["x0"]), float(entry["z0"]),
			float(entry["x1"]) - float(entry["x0"]),
			float(entry["z1"]) - float(entry["z0"])))
	var void_expected := not spaces.is_empty()
	if void_expected:
		print("[client-check] interior package: %d authored spaces, "
			% spaces.size() + "tiles outside them are expected void")

	var sampled := 0
	var misses := 0
	var in_space := 0
	var in_space_misses := 0
	var miss_examples: Array = []
	var lowest := INF
	var highest := -INF
	for ty in range(0, cells, step):
		for tx in range(0, cells, step):
			var world_position: Vector3 = adapter.server_to_godot(float(tx), float(ty))
			var from := Vector3(world_position.x, RAY_TOP, world_position.z)
			var to := Vector3(world_position.x, RAY_BOTTOM, world_position.z)
			var query := PhysicsRayQueryParameters3D.create(
				from, to, WorldLoader.NAVIGATION_SURFACE_LAYER)
			var hit: Dictionary = space.intersect_ray(query)
			sampled += 1
			var inside := false
			if void_expected:
				var point := Vector2(world_position.x, world_position.z)
				for rect in spaces:
					if (rect as Rect2).has_point(point):
						inside = true
						break
				if inside:
					in_space += 1
			var position_value: Variant = hit.get("position")
			if position_value is Vector3:
				var y: float = (position_value as Vector3).y
				lowest = minf(lowest, y)
				highest = maxf(highest, y)
			else:
				misses += 1
				if inside:
					in_space_misses += 1
					if miss_examples.size() < 12:
						miss_examples.append([tx, ty,
							snappedf(world_position.x, 0.1),
							snappedf(world_position.z, 0.1)])
				elif not void_expected and miss_examples.size() < 12:
					miss_examples.append([tx, ty,
						snappedf(world_position.x, 0.1), snappedf(world_position.z, 0.1)])
	if void_expected:
		print("[client-check] inside authored spaces: %d sampled, %d misses"
			% [in_space, in_space_misses])

	print("[client-check] grounding: %d tiles sampled, %d misses (%.2f%%)"
		% [sampled, misses, 100.0 * float(misses) / maxf(1.0, float(sampled))])
	if misses > 0:
		print("[client-check] miss examples (tile_x, tile_y, x, z): ", miss_examples)
	else:
		print("[client-check] surface height range: %.2f .. %.2f" % [lowest, highest])

	# Spawns: the manifest's stated Y should be where the client actually puts
	# an actor standing on that tile.
	var spawn_errors := 0
	var spawn_rows: Array = []
	for entry in manifest.get("spawnPoints", []):
		var spawn: Dictionary = entry
		var position: Array = spawn.get("position", [])
		if position.size() != 3:
			continue
		var from := Vector3(float(position[0]), RAY_TOP, float(position[2]))
		var to := Vector3(float(position[0]), RAY_BOTTOM, float(position[2]))
		var query := PhysicsRayQueryParameters3D.create(
			from, to, WorldLoader.NAVIGATION_SURFACE_LAYER)
		var hit: Dictionary = space.intersect_ray(query)
		var position_value: Variant = hit.get("position")
		if position_value is Vector3:
			var delta: float = absf((position_value as Vector3).y - float(position[1]))
			spawn_rows.append({"id": spawn.get("id", "?"),
				"manifestY": float(position[1]),
				"clientY": snappedf((position_value as Vector3).y, 0.001),
				"deltaMetres": snappedf(delta, 0.001)})
			if delta > 0.25:
				spawn_errors += 1
		else:
			spawn_rows.append({"id": spawn.get("id", "?"), "clientY": null,
				"deltaMetres": null})
			spawn_errors += 1
	for row in spawn_rows:
		print("[client-check] spawn ", row)

	# Opt-in: bind the manifest's own environment block through the shipped
	# WorldEnvironmentBinder and report the key light's actual emission vector.
	#
	# This exists because `environment.sun.direction` is the direction the light
	# TRAVELS, not where the sun sits: the binder aims the node's -Z at the
	# declared vector and a DirectionalLight3D emits along -Z, so a positive Y
	# component lights the world from underneath. No offline preview can show
	# that, and a capture harness using its own neutral sky cannot either, so a
	# manifest can ship with an inverted key light and nothing catches it.
	# Amberwood declares [-0.46, 0.50, 0.73] and is in exactly that state.
	var sun_report: Dictionary = {}
	if bool(opts.get("check-sun", "0") == "1"):
		var world_env := WorldEnvironment.new()
		world_root.add_child(world_env)
		var sun_light := DirectionalLight3D.new()
		world_root.add_child(sun_light)
		var bound: bool = WorldEnvironmentBinder.apply(
			loader.manifest, world_env, sun_light, world_root)
		var travel: Vector3 = -sun_light.global_transform.basis.z
		sun_report = {
			"environmentBound": bound,
			"travelDirection": [snappedf(travel.x, 0.001),
				snappedf(travel.y, 0.001), snappedf(travel.z, 0.001)],
			"lightsFromBelow": bound and travel.y > 0.0,
			"energy": sun_light.light_energy,
		}
		print("[client-check] sun ", sun_report)
		if sun_report["lightsFromBelow"]:
			printerr("[client-check] sun.direction has a positive Y: this "
				+ "manifest lights the world from underneath")

	var grounding_ok := in_space_misses == 0 if void_expected else misses == 0
	var ok := grounding_ok and spawn_errors == 0
	print("[client-check] %s" % ("PASS" if ok else "FAIL"))

	if report_path != "":
		var report := {
			"manifest": manifest_path,
			"engine": Engine.get_version_info().get("string", ""),
			"renderingDriver": "headless" if DisplayServer.get_name() == "headless"
				else RenderingServer.get_video_adapter_name(),
			"loaderWarnings": warnings,
			"serverCells": cells,
			"sampleStep": step,
			"tilesSampled": sampled,
			"groundingMisses": misses,
			"voidExpected": void_expected,
			"tilesInsideAuthoredSpaces": in_space,
			"missesInsideAuthoredSpaces": in_space_misses,
			"missExamples": miss_examples,
			"surfaceHeightRange": [lowest, highest],
			"spawns": spawn_rows,
			"sun": sun_report,
			"pass": ok,
		}
		var file := FileAccess.open(report_path, FileAccess.WRITE)
		if file != null:
			file.store_string(JSON.stringify(report, "  ") + "\n")
			file.close()
			print("[client-check] wrote ", report_path)

	quit(0 if ok else 1)
