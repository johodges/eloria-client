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
## in parallel on the WorkerThreadPool before the document is parsed: the file
## is decoded by its magic bytes and given its mip chain once, and the texture
## GLTFDocument creates from it is the finished one. An image another map
## already holds in `ExternalTexturePool` is not decoded at all. Nothing in the
## preparation touches the RenderingServer, so it is safe on any thread; see
## eloria-chunk-streaming-client-traps for what happens when a worker does.
##
## Everything here is static: the extension instance is shared by every import
## running at once (the main thread's primed cells, a chunk worker, neighbour
## territories), so per-import state lives in the `GLTFState`.

const EXTENSION_SCRIPT := "res://src/world/map_image_extension.gd"

## `ELORIA_VRAM_TEXTURES`: "0" turns the pre-compressed sidecars off, unset
## (or anything else) is automatic, "force" uses them whatever the renderer
## reports (headless tests). Images are prepared off the importing thread in
## every mode.
const ENVIRONMENT := "ELORIA_VRAM_TEXTURES"
enum Mode { AUTO, OFF, FORCE }
const MODE_NAMES: Array[String] = ["auto", "off", "force"]

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

const _PNG := [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]

static var _mutex := Mutex.new()
static var _registered := false
static var _extension: GLTFDocumentExtension
static var _mode := -1

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
		print(status_line())
	return true

static func is_registered() -> bool:
	_mutex.lock()
	var result := _registered
	_mutex.unlock()
	return result

## The one line the client logs when the extension is registered.
static func status_line() -> String:
	return "vram_textures mode=%s formats=0 index=none" % mode_name()

## Forgets the cached mode, for tests that change the environment between
## cases. The registration is kept: it is process-wide.
static func reconfigure() -> void:
	_mutex.lock()
	_mode = -1
	_mutex.unlock()

## What WorldLoader hands the extension through `GLTFState`: the manifest's
## URI -> sha256 map. Empty for a package without external images, which the
## extension then skips.
static func plan_for(manifest_data: Dictionary) -> Dictionary:
	var resources: Variant = manifest_data.get("externalResources", {})
	if not resources is Dictionary or (resources as Dictionary).is_empty():
		return {}
	return {"resources": resources}

## Prepares one image job on whatever thread runs it (a WorkerThreadPool task).
## `job` holds `sha` and `source` (absolute path); this fills `image` (the
## finished Image with its mip chain, or null), `kind` ("decoded" or
## "failed"), `mime` (what the bytes are) and `onMainThread`.
static func prepare(job: Dictionary) -> void:
	job["onMainThread"] = OS.get_thread_caller_id() == OS.get_main_thread_id()
	var decoded := decode_source(str(job.source))
	job["mime"] = decoded.mime
	job["image"] = decoded.image
	job["kind"] = "decoded" if decoded.image != null else "failed"

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
