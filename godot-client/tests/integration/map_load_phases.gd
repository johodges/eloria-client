extends SceneTree
## Where a map load goes, phase by phase, for every region the client ships.
##
## `tests/integration/client_benchmarks.gd` says what a region's load costs in
## total and in memory. This says which step is paying, because that is the
## only thing that decides what is worth changing: the third pass found that
## Godot's own `generate_scene` was two and a half of Amberwood's four seconds
## and nothing else came close, and a table like this is what said so.
##
## `WorldLoader` now times its own steps into `load_phases`, so the numbers
## below are the production path rather than a re-implementation of it. Three
## extra probes are taken here because the loader cannot take them without
## doing the work twice:
##
##   fileRead      - the glb off disk into a buffer, which is the floor under
##                   the parse and says how much of it is I/O;
##   parseNoImages - the same parse with `HANDLE_BINARY_DISCARD_TEXTURES`. It
##                   is within noise of the real parse, which is the finding:
##                   the flag drops the textures after Godot has decoded them,
##                   so it does not measure what decoding costs. Decoding the
##                   region's PNGs by hand is 150-175 ms of a 330-470 ms parse;
##                   `HANDLE_BINARY_DISCARD_TEXTURES` saves none of it;
##   firstFrame    - the first frame drawn with the region in the tree, which
##                   is where texture upload and the initial cull land.
##
## Run it headless for the phase split (the numbers are CPU either way, and a
## windowed run's first frame is the compositor's), and windowed when the first
## frame and the upload matter:
##
##     Godot --headless --path . --script res://tests/integration/map_load_phases.gd
##     Godot --audio-driver Dummy --rendering-method gl_compatibility --path . \
##           --script res://tests/integration/map_load_phases.gd
##
## Environment:
##   ELORIA_ARTIFACT_DIR    where the JSON goes (default res://test-artifacts/benchmarks)
##   ELORIA_PHASE_REGIONS   comma list of registry ids (default all twelve)
##   ELORIA_PHASE_REPEATS   loads per region, median kept (default 3)
##   ELORIA_PHASE_OUTPUT    the file name inside the artifact directory
##   ELORIA_PHASE_LABEL     a name for the run, written into the report

const REGIONS: Array[String] = [
	"four_gates", "mirrorhold", "crownwater", "whitehorn_range",
	"amethyst_barrens", "sunmane_steppe", "amberwood", "grey_moors",
	"westhaven", "verdant_stair", "ssarathi_ruins", "manymouth_delta",
]

const REGISTRY := "res://data/maps/registry.json"

## The loader's own phase names, in the order it runs them.
const PHASES: Array[StringName] = [
	&"manifest", &"parse", &"mipmaps", &"regroup", &"generateScene", &"attach",
	&"index", &"materials", &"collision", &"walkSurfaces", &"navigation",
	&"batching",
]

const SETTLE_FRAMES := 12

var _failures := 0
var _artifacts := ""

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	# Headless frames are padded to the idle sleep, which would swamp the
	# first-frame probe and every settle below it.
	OS.low_processor_usage_mode_sleep_usec = 1
	Engine.max_fps = 0
	root.size = Vector2i(1280, 720)

	_artifacts = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifacts.is_empty():
		_artifacts = ProjectSettings.globalize_path("res://test-artifacts/benchmarks")
	_expect(DirAccess.make_dir_recursive_absolute(_artifacts) == OK,
		"artifact directory is writable")

	var repeats: int = maxi(1, int(OS.get_environment("ELORIA_PHASE_REPEATS")))
	if OS.get_environment("ELORIA_PHASE_REPEATS").strip_edges().is_empty():
		repeats = 3
	var registry: Dictionary = _json(REGISTRY).get("maps", {}) as Dictionary

	var stage := Node3D.new()
	root.add_child(stage)
	var world_environment := WorldEnvironment.new()
	world_environment.environment = Environment.new()
	stage.add_child(world_environment)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	stage.add_child(sun)
	var camera := Camera3D.new()
	camera.far = 900.0
	camera.current = true
	stage.add_child(camera)
	var loader := WorldLoader.new()
	loader.name = "WorldLoader"
	stage.add_child(loader)
	await _settle(SETTLE_FRAMES)

	var report: Dictionary = {
		"label": OS.get_environment("ELORIA_PHASE_LABEL"),
		"display": DisplayServer.get_name(),
		"renderer": str(ProjectSettings.get_setting(
			"rendering/renderer/rendering_method")),
		"godot": "%d.%d.%d" % [Engine.get_version_info()["major"],
			Engine.get_version_info()["minor"], Engine.get_version_info()["patch"]],
		"repeats": repeats,
		"unixTime": int(Time.get_unix_time_from_system()),
		"phases": PHASES,
		"regions": [],
	}

	print("%-18s %8s %8s %8s %8s %8s %8s %8s %8s %8s" % [
		"region", "total", "parse", "mips", "generate", "index", "collide",
		"walks", "batch", "frame1"])
	for region: String in _regions():
		var measured: Dictionary = await _measure_region(loader, registry, region, repeats)
		(report["regions"] as Array).append(measured)

	loader.unload_world()
	stage.queue_free()
	await _settle(4)

	var name: String = OS.get_environment("ELORIA_PHASE_OUTPUT")
	if name.is_empty():
		name = "map-load-phases-%s.json" % (
			"headless" if DisplayServer.get_name() == "headless" else "windowed")
	var file := FileAccess.open(_artifacts.path_join(name), FileAccess.WRITE)
	_expect(file != null, "the report is writable")
	if file != null:
		file.store_string(JSON.stringify(report, "  "))
		file.close()
		print("wrote ", _artifacts.path_join(name))
	print("map load phases: ", "PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	quit(_failures)

func _regions() -> Array:
	var raw: String = OS.get_environment("ELORIA_PHASE_REGIONS")
	if raw.strip_edges().is_empty():
		return REGIONS
	var out: Array = []
	for part: String in raw.split(",", false):
		out.append(part.strip_edges())
	return out

func _measure_region(loader: WorldLoader, registry: Dictionary, region: String,
		repeats: int) -> Dictionary:
	var entry: Dictionary = MapRegistry.resolve(registry, region)
	if entry.is_empty():
		_expect(false, region + " resolves in the map registry")
		return {"id": region, "error": "registry_miss"}
	var manifest_path: String = ProjectSettings.globalize_path(
		str(entry.get("manifest", "")))
	var manifest: WorldManifest = WorldManifest.load_file(manifest_path)
	if not _expect(manifest.is_valid(), region + " has a valid manifest"):
		return {"id": region, "error": "manifest_invalid"}
	var glb_path: String = manifest.glb_path()

	var probes: Dictionary = _probe_glb(glb_path)

	# Every phase of every repeat, so the median is taken per phase over the
	# same loads rather than assembled from different ones.
	var samples: Array = []
	var shape: Dictionary = {}
	var first_frames := PackedFloat64Array()
	for pass_index: int in range(repeats):
		loader.load_world(manifest_path)
		var deadline: int = Time.get_ticks_msec() + 180000
		while loader.world_root == null and Time.get_ticks_msec() < deadline:
			await process_frame
		if not _expect(loader.world_root != null, region + " loads"):
			return {"id": region, "error": "load_failed"}
		var frame_started: int = Time.get_ticks_usec()
		await process_frame
		first_frames.append(float(Time.get_ticks_usec() - frame_started) / 1000.0)
		samples.append(loader.load_phases.duplicate())
		if shape.is_empty():
			shape = _shape(loader.world_root)
		await _settle(SETTLE_FRAMES)
		loader.unload_world()
		await _settle(4)

	var result: Dictionary = {
		"id": region,
		"asset": manifest.asset_id(),
		"glbMegabytes": snappedf(float(probes["glbBytes"]) / 1048576.0, 0.01),
		"samples": samples,
		"firstFrameMilliseconds": snappedf(_median(first_frames), 0.1),
	}
	result.merge(probes)
	result.merge(shape)
	var medians: Dictionary = {}
	for phase: StringName in PHASES + [&"total"] as Array:
		var values := PackedFloat64Array()
		for sample_value: Variant in samples:
			values.append(float((sample_value as Dictionary).get(phase, 0)) / 1000.0)
		medians[phase] = snappedf(_median(values), 0.1)
	result["medianMilliseconds"] = medians

	print("%-18s %8.1f %8.1f %8.1f %8.1f %8.1f %8.1f %8.1f %8.1f %8.1f" % [
		region, medians[&"total"], medians[&"parse"], medians[&"mipmaps"],
		medians[&"generateScene"], medians[&"index"], medians[&"collision"],
		medians[&"walkSurfaces"], medians[&"batching"],
		result["firstFrameMilliseconds"]])
	print("    %5d mesh nodes  %5d nodes  %3d batches  %4d bodies  widest parent %d children  %d images %.1f MB decoded  read %.0f ms  parse-no-images %.0f ms" % [
		shape.get("meshInstances", 0), shape.get("nodes", 0),
		shape.get("staticBatches", 0), shape.get("collisionBodies", 0),
		shape.get("widestParent", 0), probes["images"],
		float(probes["imageBytes"]) / 1048576.0,
		probes["fileReadMilliseconds"], probes["parseNoImagesMilliseconds"]])
	return result

## The three probes the loader cannot take without doing its work twice: the
## file off disk, the same parse with the embedded textures discarded, and how
## much decoded image data the package carries.
func _probe_glb(glb_path: String) -> Dictionary:
	var started: int = Time.get_ticks_usec()
	var file := FileAccess.open(glb_path, FileAccess.READ)
	var bytes: int = 0
	if file != null:
		var buffer: PackedByteArray = file.get_buffer(file.get_length())
		bytes = buffer.size()
		file.close()
	var read_us: int = Time.get_ticks_usec() - started

	started = Time.get_ticks_usec()
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	state.handle_binary_image = GLTFState.HANDLE_BINARY_DISCARD_TEXTURES
	var error: Error = document.append_from_file(glb_path, state)
	var parse_us: int = Time.get_ticks_usec() - started
	if error != OK:
		parse_us = 0

	# The decoded size of what the real parse builds, taken from a parse that
	# keeps the images. This one is not timed; it is the size column.
	var counted := GLTFState.new()
	var images: int = 0
	var image_bytes: int = 0
	if GLTFDocument.new().append_from_file(glb_path, counted) == OK:
		for value: Variant in counted.get_images():
			var texture: ImageTexture = value as ImageTexture
			if texture == null:
				continue
			var image: Image = texture.get_image()
			if image == null:
				continue
			images += 1
			image_bytes += image.get_data().size()
	return {
		"glbBytes": bytes,
		"fileReadMilliseconds": snappedf(float(read_us) / 1000.0, 0.1),
		"parseNoImagesMilliseconds": snappedf(float(parse_us) / 1000.0, 0.1),
		"images": images,
		"imageBytes": image_bytes,
	}

## What the region is made of, and the widest sibling list in it. Godot's
## `add_child` uniques a name against the parent's existing children, so a
## parent with thousands of children is the shape that makes `generate_scene`
## worse than linear.
func _shape(world_root: Node3D) -> Dictionary:
	var nodes: int = 0
	var mesh_instances: int = 0
	var batches: int = 0
	var bodies: int = 0
	var widest: int = 0
	var stack: Array[Node] = [world_root]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		nodes += 1
		if node is MeshInstance3D:
			mesh_instances += 1
		elif node is MultiMeshInstance3D:
			batches += 1
		elif node is StaticBody3D:
			bodies += 1
		widest = maxi(widest, node.get_child_count())
		for child: Node in node.get_children():
			stack.append(child)
	return {
		"nodes": nodes,
		"meshInstances": mesh_instances,
		"staticBatches": batches,
		"collisionBodies": bodies,
		"widestParent": widest,
	}

func _median(values: PackedFloat64Array) -> float:
	if values.is_empty():
		return 0.0
	var ordered := values.duplicate()
	ordered.sort()
	return ordered[ordered.size() / 2]

func _settle(frames: int) -> void:
	for frame: int in range(frames):
		await process_frame

func _json(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed as Dictionary if parsed is Dictionary else {}

func _expect(condition: bool, message: String) -> bool:
	if condition:
		print("ok   ", message)
	else:
		printerr("FAIL ", message)
		_failures += 1
	return condition
