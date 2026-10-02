extends RefCounted

## How the map loader produces the textures of a content-addressed map image.
##
## A map package names its images by URI and lists each one in its manifest's
## `externalResources` with the sha256 of the file. Left to itself,
## `GLTFDocument` decodes every such image on the importing thread, uploads it
## without mips, and `WorldLoader._build_texture_mipmaps` (or
## `ExternalTexturePool.share`) then reads it back from the GPU, builds the mip
## chain and uploads it a second time. A `.jpg` URI without a `mimeType` is
## also tried as PNG first, which is where the "Not a PNG file" lines came from.
##
## `map_image_extension.gd` replaces that with one preparation per image, done
## in parallel on the WorkerThreadPool before the document is parsed, and the
## texture GLTFDocument creates from it is the finished one. An image another
## map already holds in `ExternalTexturePool` is not prepared at all. Nothing in
## the preparation touches the RenderingServer, so it is safe on any thread; see
## eloria-chunk-streaming-client-traps for what happens when a worker does.
##
## ## Sidecars: textures that stay VRAM-compressed
##
## Decoded, every map image is RGBA8 on the GPU (4 bytes a pixel and a third
## more for mips): a dressed hub held 460-600 MiB of them against a 256 MiB
## chunk budget. The package therefore carries, beside each directory of
## shared images, a `vram/` folder made by tools/build_vram_textures.py:
## `<sha>.<recipe>.evt` (a 16-byte EVT1 header and a zstd frame holding a DDS
## with its whole mip chain, already BC7 / BC5 / BC1) and `index.json`. When
## the renderer can sample a sidecar's format, the image is that sidecar,
## uploaded as it is: no decode, no mips to build, a quarter (BC7, BC5) or an
## eighth (BC1) of the memory. Any doubt - no index, a schema or recipe
## version this client does not know, a missing or corrupt file, a size or
## format that disagrees with the index, a format the GPU lacks - and that
## image is decoded from its JPEG/PNG as before, so a package without sidecars
## (a dev checkout that never ran the tool) behaves exactly as develop did.
##
## The client never compresses anything itself: the export templates have no
## BC encoder (tests/test_build_vram_textures.py holds that line).
##
## Everything here is static: the extension instance is shared by every import
## running at once (the main thread's primed cells, a chunk worker, neighbour
## territories), so per-import state lives in the `GLTFState`.

const EXTENSION_SCRIPT := "res://src/world/map_image_extension.gd"

## `ELORIA_VRAM_TEXTURES`: "0" turns the sidecars off (and with them the
## budget correction), unset (or anything else) is automatic, "force" uses
## them whatever the renderer reports (tests). Images are prepared off the
## importing thread in every mode.
const ENVIRONMENT := "ELORIA_VRAM_TEXTURES"
enum Mode { AUTO, OFF, FORCE }
const MODE_NAMES: Array[String] = ["auto", "off", "force"]
## Set to "1", the client logs `self_test()`'s line at startup: the package
## smoke launch reads it to prove the shipped binary decodes a sidecar.
const SELF_TEST_ENVIRONMENT := "ELORIA_VRAM_SELF_TEST"

## GLTFState additional-data keys. WorldLoader writes the plan; the extension
## writes the rest; ExternalTexturePool and WorldLoader read DONE and POOLED.
const PLAN_KEY := &"eloria_map_plan"
## Image index -> true for every image the extension produced with its mip
## chain (or as a pooled placeholder). Nothing reads those back from the GPU.
const DONE_KEY := &"eloria_vram_done"
## Image index -> the pooled texture that replaces its 1x1 placeholder.
const POOLED_KEY := &"eloria_vram_pooled"
## Counters copied into `WorldLoader.load_phases`.
const STATS_KEY := &"eloria_vram_stats"

## What tools/build_vram_textures.py writes. A different schema or recipe
## version is refused whole (one warning) and every image falls back.
const INDEX_SCHEMA := 1
const RECIPE_VERSION := 1
const SIDECAR_DIRECTORY := "vram"
const INDEX_FILE := "index.json"
const HEADER_BYTES := 16
const FLAG_ZSTD := 1
## A header claiming more than this is corrupt, not a texture.
const MAX_RAW_BYTES := 268435456
## The directory every shipped map's shared images live in. Its index is read
## at registration for the startup line and the chunk budget; others are read
## when a map first names an image in them.
const SHARED_ASSETS := "res://../eloria-assets/maps/nymara-regions/_continent/shared-assets"

const FORMAT_BITS := {"bc1": 1, "bc5": 2, "bc7": 4}
const ALL_FORMATS := 7
const IMAGE_FORMATS := {"bc1": Image.FORMAT_DXT1, "bc5": Image.FORMAT_RGTC_RG,
	"bc7": Image.FORMAT_BPTC_RGBA}

const _PNG := [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]

static var _mutex := Mutex.new()
static var _registered := false
static var _extension: GLTFDocumentExtension
static var _mode := -1
## The formats the renderer samples natively (FORMAT_BITS), -1 until read on
## the main thread.
static var _formats := -1
## Test hook (`force_formats`), -1 when unused.
static var _formats_override := -1
## Normalised source directory -> {status, entries, sha256, entries_by_sha}.
static var _indexes: Dictionary = {}
## Source sha -> its index entry, across every index read (the chunk budget
## knows a sha, not a directory). Content addressing makes the sha enough.
static var _by_sha: Dictionary = {}
## Sidecar shas already warned about, so a broken file says so once.
static var _warned: Dictionary = {}

# --------------------------------------------------------------------------
# Mode, formats, registration
# --------------------------------------------------------------------------

## The mode, read from the environment once per process (see `reconfigure`).
static func mode() -> int:
	_mutex.lock()
	if _mode < 0:
		var value := OS.get_environment(ENVIRONMENT).strip_edges().to_lower()
		_mode = Mode.OFF if value == "0" else (Mode.FORCE if value == "force" else Mode.AUTO)
	var result := _mode
	_mutex.unlock()
	return result

static func mode_name() -> String:
	return MODE_NAMES[mode()]

## The sidecar formats this client may upload as they are (FORMAT_BITS).
##
## Forward+ and Mobile ask the RenderingDevice whether it samples each block
## format (BC1 and BC7 in both their UNORM and sRGB views, which is how Godot
## creates a colour texture); Compatibility asks the GL driver through
## `has_os_feature`. Read on the main thread, once; a worker asking first gets
## 0 (decode), which is correct and slower.
static func usable_formats() -> int:
	var current_mode := mode()
	if current_mode == Mode.OFF:
		return 0
	_mutex.lock()
	var override := _formats_override
	var known := _formats
	_mutex.unlock()
	if override >= 0:
		return override
	if current_mode == Mode.FORCE:
		return ALL_FORMATS
	if known >= 0:
		return known
	if OS.get_thread_caller_id() != OS.get_main_thread_id():
		return 0
	known = _detect_formats()
	_mutex.lock()
	_formats = known
	_mutex.unlock()
	return known

static func _detect_formats() -> int:
	var mask := 0
	var device := RenderingServer.get_rendering_device()
	if device != null:
		var usage := RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT | RenderingDevice.TEXTURE_USAGE_CAN_UPDATE_BIT
		if device.texture_is_format_supported_for_usage(RenderingDevice.DATA_FORMAT_BC1_RGB_UNORM_BLOCK, usage) \
				and device.texture_is_format_supported_for_usage(RenderingDevice.DATA_FORMAT_BC1_RGB_SRGB_BLOCK, usage):
			mask |= FORMAT_BITS.bc1
		if device.texture_is_format_supported_for_usage(RenderingDevice.DATA_FORMAT_BC5_UNORM_BLOCK, usage):
			mask |= FORMAT_BITS.bc5
		if device.texture_is_format_supported_for_usage(RenderingDevice.DATA_FORMAT_BC7_UNORM_BLOCK, usage) \
				and device.texture_is_format_supported_for_usage(RenderingDevice.DATA_FORMAT_BC7_SRGB_BLOCK, usage):
			mask |= FORMAT_BITS.bc7
		return mask
	if RenderingServer.has_os_feature("s3tc"):
		mask |= FORMAT_BITS.bc1
	if RenderingServer.has_os_feature("rgtc"):
		mask |= FORMAT_BITS.bc5
	if RenderingServer.has_os_feature("bptc"):
		mask |= FORMAT_BITS.bc7
	return mask

static func format_names(mask: int) -> String:
	var names := PackedStringArray()
	for name: String in FORMAT_BITS:
		if mask & int(FORMAT_BITS[name]):
			names.append(name)
	return "+".join(names) if not names.is_empty() else "none"

## Registers the map image extension with GLTFDocument, once per process.
##
## Registration edits GLTFDocument's static extension list, which an import
## running on another thread iterates, so it only ever happens on the main
## thread: main.gd calls this before the first load, and WorldLoader.load_world
## calls it again (a no-op) for tests that load a map without main. A worker
## that finds it unregistered loads the old way, which is correct and slower.
static func ensure_registered() -> bool:
	if OS.get_thread_caller_id() != OS.get_main_thread_id():
		return is_registered()
	_mutex.lock()
	var fresh := not _registered
	_registered = true
	_mutex.unlock()
	if fresh:
		var script: GDScript = load(EXTENSION_SCRIPT)
		_extension = script.new() as GLTFDocumentExtension
		GLTFDocument.register_gltf_document_extension(_extension)
		usable_formats()
		index_for_directory(SHARED_ASSETS)
		print(status_line())
		if OS.get_environment(SELF_TEST_ENVIRONMENT) == "1":
			print(self_test())
	return true

static func is_registered() -> bool:
	_mutex.lock()
	var result := _registered
	_mutex.unlock()
	return result

## `vram_textures mode=<auto|off|force> formats=<bc1+bc5+bc7|none>
## index=<entries|missing|rejected:reason>`, for the shared images' index.
static func status_line() -> String:
	var shared := index_for_directory(SHARED_ASSETS)
	var index := str(shared.entries) if shared.status == "ok" else str(shared.status)
	return "vram_textures mode=%s formats=%s index=%s" % [mode_name(), format_names(usable_formats()), index]

## Forgets the mode, the formats, every index read and every warning, for
## tests that change the environment or the files between cases. The
## registration is kept: it is process-wide.
static func reconfigure() -> void:
	_mutex.lock()
	_mode = -1
	_formats = -1
	_formats_override = -1
	_indexes.clear()
	_by_sha.clear()
	_warned.clear()
	_mutex.unlock()

## Test hook: pretend the renderer samples exactly `mask` (FORMAT_BITS).
static func force_formats(mask: int) -> void:
	_mutex.lock()
	_formats_override = mask
	_mutex.unlock()

# --------------------------------------------------------------------------
# The index
# --------------------------------------------------------------------------

static func _normalise(directory: String) -> String:
	return ProjectSettings.globalize_path(directory).replace("\\", "/").simplify_path()

## The index beside the images in `source_directory` (its `vram/index.json`),
## read once per directory: {status: "ok" | "missing" | "rejected:<why>",
## entries, sha256, images: sha -> entry}. An entry carries the index's own
## fields (ints cast: JSON numbers arrive as floats) plus `path`, the sidecar.
static func index_for_directory(source_directory: String) -> Dictionary:
	var key := _normalise(source_directory)
	_mutex.lock()
	var known: Variant = _indexes.get(key)
	_mutex.unlock()
	if known is Dictionary:
		return known
	var info := _read_index(key)
	_mutex.lock()
	if _indexes.has(key):
		info = _indexes[key]
	else:
		_indexes[key] = info
		for sha: String in info.images:
			if not _by_sha.has(sha):
				_by_sha[sha] = info.images[sha]
	_mutex.unlock()
	return info

static func _read_index(directory: String) -> Dictionary:
	var info := {"status": "missing", "entries": 0, "sha256": "", "images": {}}
	var path := directory.path_join(SIDECAR_DIRECTORY).path_join(INDEX_FILE)
	if not FileAccess.file_exists(path):
		return info
	var bytes := FileAccess.get_file_as_bytes(path)
	var hashing := HashingContext.new()
	hashing.start(HashingContext.HASH_SHA256)
	hashing.update(bytes)
	info.sha256 = hashing.finish().hex_encode()
	var parsed: Variant = JSON.parse_string(bytes.get_string_from_utf8())
	var reason := ""
	if not parsed is Dictionary:
		reason = "unreadable"
	elif int((parsed as Dictionary).get("schema", -1)) != INDEX_SCHEMA:
		reason = "schema %s" % str((parsed as Dictionary).get("schema"))
	elif int((parsed as Dictionary).get("recipeVersion", -1)) != RECIPE_VERSION:
		reason = "recipeVersion %s" % str((parsed as Dictionary).get("recipeVersion"))
	elif not (parsed as Dictionary).get("images") is Dictionary:
		reason = "no images"
	if not reason.is_empty():
		info.status = "rejected:" + reason
		push_warning("vram_textures: ignoring %s (%s); map images decode as before" % [path, reason])
		return info
	var images: Dictionary = {}
	var listed: Dictionary = (parsed as Dictionary).images
	for sha: Variant in listed:
		var raw: Variant = listed[sha]
		if not raw is Dictionary or str(sha).length() != 64:
			continue
		var source: Dictionary = raw
		var format := str(source.get("format", ""))
		var file := str(source.get("file", ""))
		if not FORMAT_BITS.has(format) or file.is_empty() or "/" in file or "\\" in file or ".." in file:
			continue
		images[str(sha)] = {"sha": str(sha), "file": file, "format": format,
			"recipe": str(source.get("recipe", "")),
			"width": int(source.get("width", 0)), "height": int(source.get("height", 0)),
			"mipmaps": int(source.get("mipmaps", 0)), "gpuBytes": int(source.get("gpuBytes", 0)),
			"rawBytes": int(source.get("rawBytes", 0)), "fileBytes": int(source.get("fileBytes", 0)),
			"sha256": str(source.get("sha256", "")),
			"path": directory.path_join(SIDECAR_DIRECTORY).path_join(file)}
	info.status = "ok"
	info.entries = images.size()
	info.images = images
	return info

## The sidecar entry for `sha` in `source_directory`'s index, when this client
## would upload it: the mode is not off and the renderer samples its format.
## Empty otherwise, which means "decode the source".
static func sidecar_entry(sha: String, source_directory: String) -> Dictionary:
	if mode() == Mode.OFF:
		return {}
	var info := index_for_directory(source_directory)
	var entry: Dictionary = (info.images as Dictionary).get(sha, {})
	if entry.is_empty() or not (usable_formats() & int(FORMAT_BITS[entry.format])):
		return {}
	return entry

## What MapSceneCache's key must also carry for a package with external
## images: a cached map keeps the textures it was packed with, so an entry
## built from decoded images must not be read once sidecars apply, nor the
## reverse. The mode, the usable formats and each image directory's index
## (its status and the sha256 of its bytes). Empty for a package without
## external images, whose key it leaves unchanged.
static func cache_token(manifest_data: Dictionary, glb_directory: String) -> String:
	var resources: Variant = manifest_data.get("externalResources", {})
	if not resources is Dictionary or (resources as Dictionary).is_empty():
		return ""
	var parts := PackedStringArray(["vram", mode_name(), str(usable_formats())])
	if mode() != Mode.OFF:
		var directories: Dictionary = {}
		for uri: Variant in resources:
			directories[_normalise(glb_directory.path_join(str(uri)).get_base_dir())] = true
		var sorted: Array = directories.keys()
		sorted.sort()
		for directory: String in sorted:
			var info := index_for_directory(directory)
			parts.append("%s:%s" % [str(info.status), str(info.sha256)])
	return "|".join(parts)

## Any index's entry for `sha` (empty when no index read so far lists it).
static func lookup(sha: String) -> Dictionary:
	_mutex.lock()
	var entry: Dictionary = _by_sha.get(sha, {})
	_mutex.unlock()
	return entry

## What one shared image really holds on the GPU once resident, for
## ContinentChunkStream's budget. The publisher writes every image as RGBA8
## with mips (scene_io.py: w*h*4*4/3), which is what a decoded image costs and
## stays the answer whenever this client would decode it: sidecars off, no
## index entry, or a format the renderer lacks. An image uploaded from its
## sidecar costs the sidecar's GPU bytes (a quarter for BC7/BC5, an eighth for
## BC1). Per sha, not a factor, because only the client knows which of those
## applies to each image; and here rather than in the publisher, so no map is
## republished and an older client or a fallback machine never under-counts.
static func resident_bytes(sha: String, published: int) -> int:
	if mode() == Mode.OFF:
		return published
	index_for_directory(SHARED_ASSETS)
	var entry := lookup(sha)
	if entry.is_empty() or not (usable_formats() & int(FORMAT_BITS[entry.format])):
		return published
	return int(entry.gpuBytes)

# --------------------------------------------------------------------------
# Preparing one image
# --------------------------------------------------------------------------

## What WorldLoader hands the extension through `GLTFState`: the manifest's
## URI -> sha256 map. Empty for a package without external images, which the
## extension then skips.
static func plan_for(manifest_data: Dictionary) -> Dictionary:
	var resources: Variant = manifest_data.get("externalResources", {})
	if not resources is Dictionary or (resources as Dictionary).is_empty():
		return {}
	return {"resources": resources}

## Prepares one image job on whatever thread runs it (a WorkerThreadPool task).
## `job` holds `sha`, `source` (absolute path) and optionally `sidecar` (an
## entry from `sidecar_entry`); this fills `image` (the finished Image with its
## mip chain, or null), `kind` ("sidecar", "decoded" or "failed"), `mime`,
## `rejected` (why a sidecar was not used) and `onMainThread`.
static func prepare(job: Dictionary) -> void:
	job["onMainThread"] = OS.get_thread_caller_id() == OS.get_main_thread_id()
	var sidecar: Dictionary = job.get("sidecar", {})
	if not sidecar.is_empty():
		var loaded := decode_sidecar(sidecar)
		if loaded.image != null:
			job["image"] = loaded.image
			job["kind"] = "sidecar"
			job["mime"] = "image/vnd-ms.dds"
			return
		job["rejected"] = loaded.reason
		_warn_once(str(job.sha), "vram_textures: sidecar %s unusable (%s); decoding %s" % [
			str(sidecar.file), loaded.reason, str(job.source).get_file()])
	var decoded := decode_source(str(job.source))
	job["mime"] = decoded.mime
	job["image"] = decoded.image
	job["kind"] = "decoded" if decoded.image != null else "failed"

## Reads and checks one sidecar: the file's sha256 against the index, the
## header, the zstd frame against the size the header promises, and the DDS's
## size, format and mip count against the index. Returns {image, reason}.
static func decode_sidecar(entry: Dictionary) -> Dictionary:
	var bytes := FileAccess.get_file_as_bytes(str(entry.path))
	if bytes.is_empty():
		return {"image": null, "reason": "missing"}
	var hashing := HashingContext.new()
	hashing.start(HashingContext.HASH_SHA256)
	hashing.update(bytes)
	if hashing.finish().hex_encode() != str(entry.sha256):
		return {"image": null, "reason": "sha256"}
	if bytes.size() <= HEADER_BYTES or bytes.slice(0, 4).get_string_from_ascii() != "EVT1":
		return {"image": null, "reason": "header"}
	var raw_size := bytes.decode_u32(4)
	var flags := bytes.decode_u32(8)
	if raw_size <= 0 or raw_size > MAX_RAW_BYTES:
		return {"image": null, "reason": "header"}
	var dds := bytes.slice(HEADER_BYTES)
	if flags & FLAG_ZSTD:
		dds = dds.decompress(raw_size, FileAccess.COMPRESSION_ZSTD)
	if dds.size() != raw_size:
		return {"image": null, "reason": "size"}
	var image := Image.new()
	if image.load_dds_from_buffer(dds) != OK or image.is_empty():
		return {"image": null, "reason": "dds"}
	if image.get_width() != int(entry.width) or image.get_height() != int(entry.height) \
			or image.get_format() != int(IMAGE_FORMATS[str(entry.format)]) \
			or image.get_mipmap_count() != int(entry.mipmaps):
		return {"image": null, "reason": "mismatch %dx%d format %d mips %d" % [image.get_width(),
			image.get_height(), image.get_format(), image.get_mipmap_count()]}
	return {"image": image, "reason": ""}

static func _warn_once(sha: String, message: String) -> void:
	_mutex.lock()
	var fresh := not _warned.has(sha)
	_warned[sha] = true
	_mutex.unlock()
	if fresh:
		push_warning(message)

## Decodes an image file by its leading bytes rather than its extension or a
## declared type, and gives it the mip chain the client has always built
## (`Image.generate_mipmaps`). Returns {image: Image or null, mime: String}.
static func decode_source(path: String) -> Dictionary:
	var bytes := FileAccess.get_file_as_bytes(path)
	var mime := sniff(bytes)
	var image := Image.new()
	var error: Error = FAILED
	match mime:
		"image/png":
			error = image.load_png_from_buffer(bytes)
		"image/jpeg":
			error = image.load_jpg_from_buffer(bytes)
		"image/webp":
			error = image.load_webp_from_buffer(bytes)
	if error != OK or image.is_empty():
		return {"image": null, "mime": mime}
	if image.is_compressed() and image.decompress() != OK:
		return {"image": null, "mime": mime}
	if not image.has_mipmaps():
		image.generate_mipmaps()
	return {"image": image, "mime": mime}

## The image type its first bytes declare: PNG, JPEG or WebP, else "".
static func sniff(bytes: PackedByteArray) -> String:
	if bytes.size() >= 8:
		var png := true
		for index: int in _PNG.size():
			if bytes[index] != _PNG[index]:
				png = false
				break
		if png:
			return "image/png"
	if bytes.size() >= 3 and bytes[0] == 0xFF and bytes[1] == 0xD8 and bytes[2] == 0xFF:
		return "image/jpeg"
	if bytes.size() >= 12 and bytes.slice(0, 4).get_string_from_ascii() == "RIFF" \
			and bytes.slice(8, 12).get_string_from_ascii() == "WEBP":
		return "image/webp"
	return ""

## Decodes the smallest sidecar of `source_directory`'s index and checks it,
## for the package smoke launch: the shipped binary must read what the tool
## wrote. Decoding only - the upload is proven by a windowed run.
static func self_test(source_directory := SHARED_ASSETS) -> String:
	var info := index_for_directory(source_directory)
	if info.status != "ok" or int(info.entries) == 0:
		return "vram_textures self_test failed index=%s" % str(info.status)
	var smallest: Dictionary = {}
	for entry: Dictionary in (info.images as Dictionary).values():
		if smallest.is_empty() or int(entry.fileBytes) < int(smallest.fileBytes):
			smallest = entry
	var loaded := decode_sidecar(smallest)
	if loaded.image == null:
		return "vram_textures self_test failed %s %s" % [str(smallest.file), loaded.reason]
	var image: Image = loaded.image
	return "vram_textures self_test ok entries=%d format=%s mips=%d" % [int(info.entries),
		str(smallest.format), image.get_mipmap_count()]
