extends SceneTree

## Map images: prepared once, with their mip chain, before GLTFDocument
## uploads them (src/world/vram_textures.gd, map_image_extension.gd).
##
## Uses the committed package in tests/fixtures/vram (see make_fixture.py):
## six external, content-addressed images in every role plus one embedded
## image the client must leave to GLTFDocument.
##
## Run: Godot_v4.7.2-stable_win64_console.exe --headless --path . \
##         --script res://tests/test_vram_textures.gd

const VramTextures := preload("res://src/world/vram_textures.gd")
const ExternalTexturePool := preload("res://src/world/external_texture_pool.gd")

const FIXTURE := "res://tests/fixtures/vram"
const EXTERNAL_IMAGES := 6
const EMBEDDED_INDEX := 6

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _expect(ok: bool, message: String) -> bool:
	if not ok:
		failures += 1
		push_error("FAIL: " + message)
	else:
		print("PASS: ", message)
	return ok

func _run() -> void:
	OS.set_environment("ELORIA_LOOK", "0")
	OS.set_environment("ELORIA_NO_MAP_CACHE", "1")
	OS.low_processor_usage_mode_sleep_usec = 1
	VramTextures.ensure_registered()
	_check_sniff()
	_check_untouched_without_plan()
	_check_prepared_matches_legacy()
	_check_serial_equals_parallel()
	await _check_pool_sharing()
	await _check_worker_load()
	print("vram textures tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(1 if failures > 0 else 0)

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

func _manifest() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(FIXTURE.path_join("world.json")))

## Parses the fixture GLB. With `plan`, the way WorldLoader does.
func _parse(plan: bool) -> GLTFState:
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	if plan:
		state.set_additional_data(VramTextures.PLAN_KEY, VramTextures.plan_for(_manifest()))
	_expect(document.append_from_file(FIXTURE.path_join("world.glb"), state) == OK,
		"the fixture parses (plan=%s)" % plan)
	return state

## Develop's path for one parsed image: read it back and build the chain.
func _legacy_image(texture: Texture2D) -> Image:
	var image := texture.get_image()
	if image != null and not image.has_mipmaps():
		if image.is_compressed():
			image.decompress()
		image.generate_mipmaps()
	return image

func _same_image(a: Image, b: Image) -> bool:
	return a != null and b != null and a.get_format() == b.get_format() \
		and a.get_size() == b.get_size() and a.get_mipmap_count() == b.get_mipmap_count() \
		and a.get_data() == b.get_data()

func _stats(state: GLTFState) -> Dictionary:
	var value: Variant = state.get_additional_data(VramTextures.STATS_KEY)
	return value if value is Dictionary else {}

func _done(state: GLTFState) -> Dictionary:
	var value: Variant = state.get_additional_data(VramTextures.DONE_KEY)
	return value if value is Dictionary else {}

# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------

func _check_sniff() -> void:
	var resources: Dictionary = _manifest().externalResources
	var kinds := {}
	for uri: String in resources:
		var mime := VramTextures.sniff(FileAccess.get_file_as_bytes(FIXTURE.path_join(uri)))
		kinds[uri.get_extension() + ":" + mime] = true
	_expect(kinds.has("jpg:image/jpeg") and kinds.has("png:image/png") and kinds.size() == 2,
		"images are typed by their bytes: %s" % [kinds.keys()])
	_expect(VramTextures.sniff(PackedByteArray([1, 2, 3])) == "", "unknown bytes are not typed")

func _check_untouched_without_plan() -> void:
	var state := _parse(false)
	var images: Array = state.get_json().images
	_expect(state.get_additional_data(VramTextures.STATS_KEY) == null
		and state.get_additional_data(VramTextures.DONE_KEY) == null,
		"a GLB without a plan is left to GLTFDocument (actor GLBs are untouched)")
	_expect(str(images[0].uri).begins_with("shared-assets/") and not images[0].has("mimeType"),
		"and its image descriptors are as written")

func _check_prepared_matches_legacy() -> void:
	var legacy := _parse(false)
	var planned := _parse(true)
	var stats := _stats(planned)
	var done := _done(planned)
	_expect(int(stats.get("imagesPrepared", -1)) == EXTERNAL_IMAGES
		and int(stats.get("imagesFailed", -1)) == 0 and int(stats.get("imagesPooled", -1)) == 0,
		"every external image is prepared before the parse: %s" % [stats])
	_expect(int(stats.get("imagesPreparedOnMainThread", -1)) == 0,
		"the preparation ran on the WorkerThreadPool, not the main thread")
	_expect(done.size() == EXTERNAL_IMAGES and not done.has(EMBEDDED_INDEX),
		"the extension produced the external images and left the embedded one")
	var images: Array = planned.get_json().images
	var restored := true
	for index: int in EXTERNAL_IMAGES:
		restored = restored and str(images[index].uri).begins_with("shared-assets/") \
			and not images[index].has("mimeType")
	_expect(restored, "the original URIs are restored after the parse")
	var legacy_images := legacy.get_images()
	var planned_images := planned.get_images()
	var equal := 0
	for index: int in EXTERNAL_IMAGES:
		var mine := planned_images[index].get_image()
		if mine.has_mipmaps() and _same_image(mine, _legacy_image(legacy_images[index])):
			equal += 1
	_expect(equal == EXTERNAL_IMAGES,
		"prepared images equal develop's decode + mip chain in format, size, mips and bytes (%d/%d)"
		% [equal, EXTERNAL_IMAGES])
	_expect(not planned_images[EMBEDDED_INDEX].get_image().has_mipmaps(),
		"the embedded image is still GLTFDocument's (the loader adds its chain later)")

func _check_serial_equals_parallel() -> void:
	var planned := _parse(true)
	var resources: Dictionary = _manifest().externalResources
	var images: Array = planned.get_json().images
	var equal := 0
	for index: int in EXTERNAL_IMAGES:
		var job := {"sha": str(resources[images[index].uri]),
			"source": ProjectSettings.globalize_path(FIXTURE.path_join(images[index].uri))}
		VramTextures.prepare(job)
		if _same_image(job.image, planned.get_images()[index].get_image()):
			equal += 1
	_expect(equal == EXTERNAL_IMAGES,
		"a serial preparation gives the same images as the parallel one (%d/%d)" % [equal, EXTERNAL_IMAGES])

## A second load while the first is resident: every external image comes from
## the pool, nothing is decoded, and no 1x1 placeholder survives share().
func _check_pool_sharing() -> void:
	var first := WorldLoader.new()
	root.add_child(first)
	first.load_world(FIXTURE.path_join("world.json"))
	_expect(first.world_root != null, "the fixture loads through WorldLoader")
	_expect(int(first.load_phases.get(&"imagesPrepared", -1)) == EXTERNAL_IMAGES,
		"the loader reports the prepared images in load_phases")
	var builder := WorldLoader.prepare_detached(FIXTURE.path_join("world.json"), false)
	_expect(int(builder.load_phases.get(&"imagesPooled", -1)) == EXTERNAL_IMAGES
		and int(builder.load_phases.get(&"imagesPrepared", -1)) == 0,
		"a second load takes every external image from the pool: %s" % [builder.load_phases])
	var first_textures := _textures(first.world_root)
	var second_textures := _textures(builder.world_root)
	var shared := 0
	var placeholders := 0
	for name: String in second_textures:
		var texture: Texture2D = second_textures[name]
		if texture.get_width() <= 1:
			placeholders += 1
		if name != "embedded" and first_textures.get(name) == texture:
			shared += 1
	_expect(placeholders == 0, "no 1x1 placeholder survives share()")
	_expect(shared == second_textures.size() - 1,
		"the second load binds the first load's textures (%d of %d)" % [shared, second_textures.size() - 1])
	var resident: Dictionary = builder.release_world()
	builder.free()
	(resident.root as Node).free()
	first.unload_world()
	first.queue_free()
	await process_frame

## Base colour textures by material name.
func _textures(world: Node) -> Dictionary:
	var found := {}
	for node: Node in world.find_children("*", "MeshInstance3D", true, false):
		var mesh := (node as MeshInstance3D).mesh
		for surface: int in mesh.get_surface_count():
			var material := mesh.surface_get_material(surface) as BaseMaterial3D
			if material != null and material.albedo_texture != null:
				found[material.resource_name] = material.albedo_texture
	return found

func _check_worker_load() -> void:
	var thread := Thread.new()
	thread.start(WorldLoader.prepare_detached.bind(FIXTURE.path_join("world.json"), false))
	var deadline := Time.get_ticks_msec() + 20000
	while thread.is_alive() and Time.get_ticks_msec() < deadline:
		await process_frame
	if not _expect(not thread.is_alive(), "a worker-thread load finishes"):
		return
	var builder: WorldLoader = thread.wait_to_finish()
	_expect(int(builder.load_phases.get(&"imagesPrepared", -1)) == EXTERNAL_IMAGES
		and int(builder.load_phases.get(&"imagesPreparedOnMainThread", -1)) == 0,
		"a load from a Thread prepares its images and none on the main thread: %s" % [builder.load_phases])
	var resident: Dictionary = builder.release_world()
	builder.free()
	if resident.root != null:
		(resident.root as Node).free()
