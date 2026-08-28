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

	# The contract is not "every tile in the bounding box has floor" - that is
	# only true of a region, whose terrain covers everything. An interior is
	# rooms inside solid rock, and most of its box legitimately has no floor.
	# What must hold for both is that every cell the collision grid calls
	# walkable has a surface the ray can find.
	var collision: Dictionary = manifest.get("collision", {})
	var grid := PackedByteArray()
	var grid_w := int(collision.get("width", 0))
	var grid_h := int(collision.get("height", 0))
	var cell_m := float(collision.get("cellMetres", 0.5))
	var bin_path := manifest_path.get_base_dir().path_join(
		str(collision.get("binary", "collision.bin")))
	if FileAccess.file_exists(bin_path):
		var raw := FileAccess.get_file_as_bytes(bin_path)
		if raw.size() >= 16 + grid_w * grid_h:
			grid = raw.slice(16, 16 + grid_w * grid_h)
	if grid.is_empty():
		printerr("[client-check] could not read the collision grid at ", bin_path)
		quit(2)
		return

	# Cell (0,0) is the north-west corner: column 0 is the -X edge and row 0 is
	# the +Z edge. Interiors record that corner directly; a region's grid is
	# anchored on its server origin instead.
	var origin_value: Variant = collision.get("originMetres")
	var origin_x := 0.0
	var origin_z := 0.0
	if origin_value is Array and (origin_value as Array).size() == 2:
		origin_x = float((origin_value as Array)[0])
		origin_z = float((origin_value as Array)[1])
	else:
		var corner: Vector3 = adapter.server_to_godot(0.0, 0.0)
		origin_x = corner.x
		origin_z = corner.z
	print("[client-check] collision grid %dx%d at %.2f m, origin (%.1f, %.1f)"
		% [grid_w, grid_h, cell_m, origin_x, origin_z])

	var sampled := 0
	var walkable := 0
	var misses := 0
	var miss_examples: Array = []
	var lowest := INF
	var highest := -INF
	for row in range(0, grid_h, step):
		for col in range(0, grid_w, step):
			sampled += 1
			if grid[row * grid_w + col] == 0:
				continue          # blocked: no floor is expected here
			walkable += 1
			var wx := origin_x + (float(col) + 0.5) * cell_m
			var wz := origin_z - (float(row) + 0.5) * cell_m
			var from := Vector3(wx, RAY_TOP, wz)
			var to := Vector3(wx, RAY_BOTTOM, wz)
			var query := PhysicsRayQueryParameters3D.create(
				from, to, WorldLoader.NAVIGATION_SURFACE_LAYER)
			var hit: Dictionary = space.intersect_ray(query)
			var position_value: Variant = hit.get("position")
			if position_value is Vector3:
				var y: float = (position_value as Vector3).y
				lowest = minf(lowest, y)
				highest = maxf(highest, y)
			else:
				misses += 1
				if miss_examples.size() < 12:
					miss_examples.append([col, row, snappedf(wx, 0.1), snappedf(wz, 0.1)])

	print("[client-check] %d cells sampled, %d walkable, %d with no surface (%.2f%%)"
		% [sampled, walkable, misses,
		   100.0 * float(misses) / maxf(1.0, float(walkable))])
	if misses > 0:
		print("[client-check] miss examples (col, row, x, z): ", miss_examples)
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

	var ok := misses == 0 and spawn_errors == 0
	print("[client-check] %s" % ("PASS" if ok else "FAIL"))

	if report_path != "":
		var report := {
			"manifest": manifest_path,
			"engine": Engine.get_version_info().get("string", ""),
			"renderingDriver": "headless" if DisplayServer.get_name() == "headless"
				else RenderingServer.get_video_adapter_name(),
			"loaderWarnings": warnings,
			"sampleStep": step,
			"cellsSampled": sampled,
			"walkableCellsTested": walkable,
			"walkableCellsWithNoSurface": misses,
			"missExamples": miss_examples,
			"surfaceHeightRange": [lowest, highest],
			"spawns": spawn_rows,
			"pass": ok,
		}
		var file := FileAccess.open(report_path, FileAccess.WRITE)
		if file != null:
			file.store_string(JSON.stringify(report, "  ") + "\n")
			file.close()
			print("[client-check] wrote ", report_path)

	quit(0 if ok else 1)
