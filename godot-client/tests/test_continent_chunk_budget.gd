extends SceneTree

## The chunk stream's byte budget counts a shared image at what it really
## holds on the GPU: its sidecar's bytes when this client uploads the sidecar,
## the publisher's RGBA8 figure otherwise (VramTextures.resident_bytes, read
## by ContinentChunkStream.configure).
##
## Uses the committed sidecar index of tests/fixtures/vram: four images with
## sidecars (BC7 base, BC7 cutout, BC5 normal, BC1 ORM) and three excluded.
##
## Run: Godot_v4.7.2-stable_win64_console.exe --headless --path . \
##         --script res://tests/test_continent_chunk_budget.gd

const VramTextures := preload("res://src/world/vram_textures.gd")

const FIXTURE := "res://tests/fixtures/vram"
const SCRATCH := "user://continent-chunk-budget-test"
const GEOMETRY := 1000
## w*h*4*4/3 for a 64 px image, as scene_io.py writes it.
const PUBLISHED := 21845

var failures := 0
var _index: Dictionary
var _by_recipe: Dictionary = {}
var _excluded: Array = []

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
	_index = JSON.parse_string(FileAccess.get_file_as_string(
		FIXTURE.path_join("shared-assets/vram/index.json")))
	for sha: String in _index.images:
		_by_recipe[str(_index.images[sha].recipe)] = sha
	_excluded = (_index.excluded as Dictionary).keys()

	_check_resident_bytes()
	_check_selection()
	_check_territory_indexes()
	_set_mode("")
	_remove_tree(SCRATCH)
	print("continent chunk budget tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(1 if failures > 0 else 0)

func _set_mode(value: String, read_index := true) -> void:
	OS.set_environment(VramTextures.ENVIRONMENT, value)
	VramTextures.reconfigure()
	if read_index:
		VramTextures.index_for_directory(FIXTURE.path_join("shared-assets"))

func _gpu(recipe: String) -> int:
	return int(_index.images[_by_recipe[recipe]].gpuBytes)

func _check_resident_bytes() -> void:
	_set_mode("force")
	var base: String = _by_recipe.base
	_expect(VramTextures.resident_bytes(base, PUBLISHED) == _gpu("base") and _gpu("base") * 3 < PUBLISHED,
		"a sidecar image counts its BC7 bytes (%d of %d)" % [_gpu("base"), PUBLISHED])
	_expect(VramTextures.resident_bytes(_by_recipe.orm, PUBLISHED) == _gpu("orm")
		and _gpu("orm") * 7 < PUBLISHED, "an ORM counts its BC1 bytes (%d)" % _gpu("orm"))
	var excluded_ok := true
	for sha: String in _excluded:
		excluded_ok = excluded_ok and VramTextures.resident_bytes(sha, PUBLISHED) == PUBLISHED
	_expect(excluded_ok, "an excluded image keeps the published RGBA8 figure")
	_expect(VramTextures.resident_bytes("f".repeat(64), 12345) == 12345, "an unknown sha keeps the published figure")

	_set_mode("force")
	VramTextures.force_formats(VramTextures.FORMAT_BITS.bc1 | VramTextures.FORMAT_BITS.bc5)
	_expect(VramTextures.resident_bytes(base, PUBLISHED) == PUBLISHED
		and VramTextures.resident_bytes(_by_recipe.normal, PUBLISHED) == _gpu("normal"),
		"a format the renderer lacks keeps the published figure; one it samples does not")

	_set_mode("0")
	_expect(VramTextures.resident_bytes(base, PUBLISHED) == PUBLISHED, "=0 keeps every published figure")

## Five cells nearest-first, one image each; only the first is framed. Under a
## 40 000-byte budget the published (RGBA8) figures admit one cell; the real
## ones admit the four whose images have sidecars and stop at the excluded one.
## With `images_in`, the territory manifest names the fixture images it holds
## (externalResources, as published territories do) in that directory.
func _territory(images_in := "") -> WorldManifest:
	var chunks := []
	var shas: Array = [_by_recipe.base, _by_recipe.base_alpha, _by_recipe.normal, _by_recipe.orm, _excluded[0]]
	for index: int in shas.size():
		var x := 100.0 + 20.0 * index if index > 0 else 0.0
		chunks.append({"id": "c%d" % index, "manifest": "c%d/world.json" % index,
			"bounds": {"min": [x, 0, -1], "max": [x + 1, 1, 1]},
			"estimatedResidentBytes": GEOMETRY + PUBLISHED, "geometryResidentBytes": GEOMETRY,
			"sharedResourceResidentBytes": {shas[index]: PUBLISHED}})
	var manifest := WorldManifest.new()
	manifest.source_path = (images_in if not images_in.is_empty() else FIXTURE).path_join("territory.json")
	manifest.data = {"streamingChunks": {"schemaVersion": "1.0", "coordinateSpace": "territory-local",
		"maximumResidentBytes": 40000, "chunks": chunks}}
	if not images_in.is_empty():
		manifest.data["asset"] = {"id": "budget_territory", "glb": "world.glb"}
		manifest.data["externalResources"] = JSON.parse_string(FileAccess.get_file_as_string(
			images_in.path_join("world.json"))).externalResources
	return manifest

## The cells an arrival loads synchronously: prime() keeps develop's set (the
## published figures' budget) even when the real figures admit more, so the
## arrival freeze is no longer than develop's; the extra cells go to the worker.
func _blocking(mode: String, read_index := true) -> Array:
	_set_mode(mode, read_index)
	var stream := ContinentChunkStream.new()
	stream.configure(_territory(), false)
	var ids := []
	for entry: Dictionary in stream.selection(Vector3.ZERO):
		if not bool(entry.get("beyond_budget", false)) and bool(entry.get("blocking", true)):
			ids.append(str(entry.id))
	stream.free()
	return ids

func _check_blocking() -> void:
	var develop := _blocking("0")
	_expect(develop == ["c0"], "develop's budget loads one cell synchronously: %s" % [develop])
	var corrected := _blocking("force")
	_expect(corrected == develop,
		"with the real figures the arrival still loads only develop's cells synchronously: %s" % [corrected])
	# A budget the published figures also clear: every admitted cell blocks.
	_set_mode("force")
	var stream := ContinentChunkStream.new()
	stream.configure(_territory(), false)
	stream.maximum_resident_bytes = 1 << 30
	var all_blocking := true
	for entry: Dictionary in stream.selection(Vector3.ZERO):
		all_blocking = all_blocking and bool(entry.blocking)
	stream.free()
	_expect(all_blocking, "under a budget that admits everything as published, every cell blocks as before")

func _selected(mode: String, read_index := true) -> Array:
	_set_mode(mode, read_index)
	var stream := ContinentChunkStream.new()
	stream.configure(_territory(), false)
	var ids := []
	for entry: Dictionary in stream.selection(Vector3.ZERO):
		ids.append("%s%s" % [entry.id, "*" if entry.get("beyond_budget", false) else ""])
	stream.free()
	return ids

func _check_selection() -> void:
	var published := _selected("0")
	_expect(published == ["c0"], "with the RGBA8 figures the budget admits one cell: %s" % [published])
	var real := _selected("force")
	_expect(real == ["c0", "c1", "c2", "c3"],
		"with the sidecars' bytes it admits the four compressed cells: %s" % [real])
	# No index for these images: exactly today's selection.
	var unindexed := _selected("force", false)
	_expect(unindexed == published, "with no index the selection is develop's exactly: %s" % [unindexed])
	_check_blocking()
	_set_mode("force")
	VramTextures.force_formats(0)
	var stream := ContinentChunkStream.new()
	stream.configure(_territory(), false)
	var ids := []
	for entry: Dictionary in stream.selection(Vector3.ZERO):
		ids.append(str(entry.id))
	stream.free()
	_expect(ids == published, "with no usable format the selection is develop's exactly: %s" % [ids])

func _ids(stream: ContinentChunkStream) -> Array:
	var ids := []
	for entry: Dictionary in stream.selection(Vector3.ZERO):
		ids.append(str(entry.id))
	return ids

## The budget reads the indexes its territory's manifest names, at configure,
## wherever the images live: no chunk import, no prior read, and not the one
## fixed SHARED_ASSETS path (which a template run outside the package layout,
## or a move of the shared images, would not resolve).
func _check_territory_indexes() -> void:
	_set_mode("force", false)
	var stream := ContinentChunkStream.new()
	stream.configure(_territory(FIXTURE), false)
	var ids := _ids(stream)
	stream.free()
	_expect(ids == ["c0", "c1", "c2", "c3"],
		"configure reads the index of the images its territory names, with nothing read before: %s" % [ids])
	_expect(not VramTextures._indexes.has(VramTextures._normalise(VramTextures.SHARED_ASSETS)),
		"and the budget never reads the fixed shared-assets path")
	var moved := _copy_fixture("moved")
	_set_mode("force", false)
	stream = ContinentChunkStream.new()
	stream.configure(_territory(moved), false)
	ids = _ids(stream)
	stream.free()
	_expect(ids == ["c0", "c1", "c2", "c3"], "the same with the images and sidecars in another directory: %s" % [ids])
	_set_mode("0", false)
	stream = ContinentChunkStream.new()
	stream.configure(_territory(FIXTURE), false)
	ids = _ids(stream)
	stream.free()
	_expect(ids == ["c0"] and VramTextures._indexes.is_empty(), "=0 reads no index and keeps develop's selection: %s" % [ids])

## A copy of the fixture package (manifest, GLB, images, sidecars) under user://.
func _copy_fixture(name: String) -> String:
	var target := SCRATCH.path_join(name)
	_remove_tree(target)
	for relative: String in ["", "shared-assets", "shared-assets/vram"]:
		DirAccess.make_dir_recursive_absolute(target.path_join(relative))
		for file: String in DirAccess.get_files_at(FIXTURE.path_join(relative)):
			DirAccess.copy_absolute(FIXTURE.path_join(relative).path_join(file), target.path_join(relative).path_join(file))
	return target

func _remove_tree(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return
	for directory: String in DirAccess.get_directories_at(path):
		_remove_tree(path.path_join(directory))
	for file: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(file))
	DirAccess.remove_absolute(path)
