extends SceneTree
## A cached region draws what a built one draws.
##
## `tests/test_map_cache.gd` proves the cached tree has the same nodes, meshes,
## placements, visibility, collision and batch links as the built one. That is
## a structural argument, and structure is not the picture: the regrouping pass
## changed 245 pixels of 7.4 million without moving a single mesh, because the
## order two coplanar surfaces are drawn in decides which one wins a depth tie.
## So the cache gets the same instrument, pointed at the same question: load a
## region the slow way, photograph it from eight fixed viewpoints, load it out
## of the cache, photograph it again, and count the pixels between them.
##
## **Byte-identity is not the bar, because nothing reaches it.** Two loads of
## the same package through the same code, in the same process, move 60-90
## pixels of 518 400 in every view: each load builds its own meshes and
## materials, the renderer sorts opaque draws by the RIDs those got, and where
## two surfaces meet the camera at the same depth the tie falls to whichever
## sorted first. That is the floor, and it is measured here rather than assumed
## - a run photographs the region twice the slow way before it photographs it
## once from the cache. What the cache has to do is not stand out against that
## floor: the assertion is that the cached load moves no more than three times
## the pixels a rebuild does.
##
## The failure this is really watching for is not subtle. The cache is packed
## three frames after the load, by which time the interior cutaway, the secret
## sections and the occluder fade have all had the tree; baking one of those in
## would leave a wall missing or a rock permanently made of glass, which is
## tens of thousands of pixels, not tens. `test_map_cache.gd` also catches it
## deterministically, by hiding a mesh and hanging a material on another one
## before the write and proving neither survives; this is the picture that says
## so.
##
## Nothing in the shot moves. There are no actors, no weather, no occluder fade
## and no day-night cycle; the camera is placed from the region's own bounds,
## so the framing is a property of the package and is identical for every load
## of it.
##
## Must be run windowed. Headless has no renderer, so every capture would be
## the same empty buffer and every comparison would pass:
##
##     Godot --audio-driver Dummy --rendering-method gl_compatibility --path . \
##           --script res://tests/integration/map_cache_render.gd
##
## Environment:
##   ELORIA_CACHE_RENDER_MAPS  comma list of registry ids
##                             (default four_gates,verdant_stair,amberwood)
##   ELORIA_ARTIFACT_DIR       where a failing pair of images is written

const REGISTRY := "res://data/maps/registry.json"
const DEFAULT_MAPS := "four_gates,verdant_stair,amberwood"
const SCREEN_SIZE := Vector2i(960, 540)
const VIEWS := 8
## Frames between placing the camera and reading the buffer. The first frame
## with a region in the tree is the upload and the pipeline builds; a handful
## after it are the same picture.
const SETTLE_FRAMES := 6

var _failures := 0
var _artifacts := ""
var _loader: WorldLoader
var _camera: Camera3D
## The map under test, so the loads below read as one sentence each.
var _manifest_path := ""

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	OS.low_processor_usage_mode_sleep_usec = 1
	Engine.max_fps = 0
	root.size = SCREEN_SIZE
	_artifacts = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifacts.is_empty():
		_artifacts = ProjectSettings.globalize_path("res://test-artifacts/map-cache")
	DirAccess.make_dir_recursive_absolute(_artifacts)

	if DisplayServer.get_name() == "headless":
		printerr("FAIL map_cache_render must be run windowed; headless draws nothing")
		quit(1)
		return

	var registry: Dictionary = _json(REGISTRY).get("maps", {}) as Dictionary
	var stage := Node3D.new()
	root.add_child(stage)
	var world_environment := WorldEnvironment.new()
	var environment := Environment.new()
	# A flat background and a fixed ambient term, so the only thing that can
	# differ between two captures is the geometry and how it is lit.
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.08, 0.10, 0.14)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.35, 0.37, 0.42)
	environment.ambient_light_energy = 1.0
	world_environment.environment = environment
	stage.add_child(world_environment)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	sun.rotation = Vector3(deg_to_rad(-52.0), deg_to_rad(37.0), 0.0)
	stage.add_child(sun)
	_camera = Camera3D.new()
	_camera.far = 4000.0
	_camera.current = true
	stage.add_child(_camera)
	_loader = WorldLoader.new()
	_loader.name = "WorldLoader"
	stage.add_child(_loader)
	await _settle(SETTLE_FRAMES)

	for identifier: String in _maps():
		await _check_map(registry, identifier)

	_loader.unload_world()
	stage.queue_free()
	await _settle(2)
	print("map cache render: ", "PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	quit(_failures)

func _maps() -> PackedStringArray:
	var raw: String = OS.get_environment("ELORIA_CACHE_RENDER_MAPS")
	if raw.strip_edges().is_empty():
		raw = DEFAULT_MAPS
	var out := PackedStringArray()
	for part: String in raw.split(",", false):
		out.append(part.strip_edges())
	return out

func _check_map(registry: Dictionary, identifier: String) -> void:
	var entry: Dictionary = MapRegistry.resolve(registry, identifier)
	if not _expect(not entry.is_empty(), identifier + " resolves in the map registry"):
		return
	_manifest_path = ProjectSettings.globalize_path(str(entry.get("manifest", "")))

	# One: the region built from its package, with the cache switched off so
	# there is no question about which path ran.
	OS.set_environment(MapSceneCache.DISABLE_ENVIRONMENT, "1")
	if not await _load(identifier + " built from the package"):
		return
	if not _expect(_loader.cache_status == &"disabled",
			"%s: the reference load is a real one (%s)" % [
				identifier, _loader.cache_status]):
		return
	var framings: Array[Transform3D] = _framings(_loader.world_root)
	var built: Array[PackedByteArray] = await _photograph(framings)

	# Two: the same load again, to establish that two runs of the same code
	# agree. Without this a difference below could be the machine.
	if not await _load(identifier + " built a second time"):
		return
	var again: Array[PackedByteArray] = await _photograph(framings)
	var control: int = _pixels_moved(built, again)
	print("ok   %s: the noise floor is %d pixels of %d (%.4f%%) between two builds"
		% [identifier, control, _total_pixels(),
			100.0 * float(control) / float(_total_pixels())])

	# Three: the cache. The first load writes it, the second reads it.
	OS.set_environment(MapSceneCache.DISABLE_ENVIRONMENT, "")
	MapSceneCache.forget_setting()
	if not await _load(identifier + " with the cache on"):
		return
	_expect(_loader.cache_status in [&"miss", &"hit"],
		"%s: the cache is on for the cached run (%s)" % [
			identifier, _loader.cache_status])
	var wanted: String = _loader.cache_file
	var deadline: int = Time.get_ticks_msec() + 120000
	while not FileAccess.file_exists(wanted) and Time.get_ticks_msec() < deadline:
		await process_frame
	if not _expect(FileAccess.file_exists(wanted),
			"%s: the entry is on disk" % identifier):
		return
	if not await _load(identifier + " read back from the cache"):
		return
	if not _expect(_loader.loaded_from_cache,
			"%s: the compared load came from the cache (%s)" % [
				identifier, _loader.cache_status]):
		return
	var cached: Array[PackedByteArray] = await _photograph(framings)

	var measured: int = _pixels_moved(built, cached)
	var allowed: int = maxi(control * 3, control + 500)
	var passed: bool = _expect(measured <= allowed,
		("%s: the cached region draws the built one to within the noise - "
			+ "%d pixels of %d moved (%.4f%%), against %d for two builds") % [
			identifier, measured, _total_pixels(),
			100.0 * float(measured) / float(_total_pixels()), control])
	if not passed:
		_report(identifier, "cached", built, cached)
	_loader.unload_world()
	await _settle(2)

## How far apart two sets of captures are, and both images of every view that
## moved, so a failure is a picture rather than a number.
func _report(identifier: String, label: String, left: Array[PackedByteArray],
		right: Array[PackedByteArray]) -> void:
	var total: int = SCREEN_SIZE.x * SCREEN_SIZE.y
	for view: int in mini(left.size(), right.size()):
		if left[view] == right[view]:
			continue
		var pixels: int = _pixels_differing(left[view], right[view])
		printerr("     %s view %d: %d of %d pixels differ (%.4f%%)" % [
			identifier, view, pixels, total,
			100.0 * float(pixels) / float(maxi(1, total))])
		_save(left[view], "%s-view%d-built.png" % [identifier, view])
		_save(right[view], "%s-view%d-%s.png" % [identifier, view, label])

func _load(label: String) -> bool:
	_loader.unload_world()
	await _settle(2)
	_loader.load_world(_manifest_path)
	var deadline: int = Time.get_ticks_msec() + 180000
	while _loader.world_root == null and Time.get_ticks_msec() < deadline:
		await process_frame
	return _expect(_loader.world_root != null, label + " loads")

## Eight viewpoints around the region, derived from its own bounds so the
## framing is a property of the package rather than of this file, and identical
## for every load of it.
func _framings(world: Node3D) -> Array[Transform3D]:
	var bounds := AABB()
	var first := true
	for node: Node in world.find_children("*", "VisualInstance3D", true, false):
		var visual: VisualInstance3D = node as VisualInstance3D
		var box: AABB = visual.global_transform * visual.get_aabb()
		if first:
			bounds = box
			first = false
		else:
			bounds = bounds.merge(box)
	var centre: Vector3 = bounds.get_center()
	var reach: float = maxf(8.0, maxf(bounds.size.x, bounds.size.z) * 0.42)
	var height: float = centre.y + maxf(bounds.size.y * 0.6, reach * 0.55)
	var out: Array[Transform3D] = []
	for view: int in VIEWS:
		var angle: float = TAU * float(view) / float(VIEWS)
		var eye := Vector3(centre.x + cos(angle) * reach, height,
			centre.z + sin(angle) * reach)
		var transform := Transform3D(Basis(), eye)
		out.append(transform.looking_at(centre, Vector3.UP))
	return out

func _photograph(framings: Array[Transform3D]) -> Array[PackedByteArray]:
	var out: Array[PackedByteArray] = []
	for framing: Transform3D in framings:
		_camera.global_transform = framing
		await _settle(SETTLE_FRAMES)
		# Read after the draw the last settle frame asked for, rather than
		# during the next one: `get_texture()` on a window hands back whatever
		# is in the buffer, and mid-frame that is the previous view.
		await RenderingServer.frame_post_draw
		var image: Image = root.get_texture().get_image()
		out.append(PackedByteArray() if image == null else image.get_data())
	return out

## Pixels that moved across all eight views.
func _pixels_moved(left: Array[PackedByteArray],
		right: Array[PackedByteArray]) -> int:
	var moved: int = 0
	for view: int in mini(left.size(), right.size()):
		if left[view] != right[view]:
			moved += maxi(0, _pixels_differing(left[view], right[view]))
	return moved

func _total_pixels() -> int:
	return SCREEN_SIZE.x * SCREEN_SIZE.y * VIEWS

## How many pixels of a view moved, counted only when a view has already been
## found to differ. Four bytes a pixel, RGBA8.
func _pixels_differing(left: PackedByteArray, right: PackedByteArray) -> int:
	if left.size() != right.size():
		return -1
	var pixels: int = 0
	var index: int = 0
	while index + 3 < left.size():
		if left[index] != right[index] or left[index + 1] != right[index + 1] \
				or left[index + 2] != right[index + 2] \
				or left[index + 3] != right[index + 3]:
			pixels += 1
		index += 4
	return pixels

func _save(data: PackedByteArray, name: String) -> void:
	var image: Image = Image.create_from_data(SCREEN_SIZE.x, SCREEN_SIZE.y,
		false, Image.FORMAT_RGBA8, data)
	if image != null:
		image.save_png(_artifacts.path_join(name))

func _settle(frames: int) -> void:
	for frame: int in frames:
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
