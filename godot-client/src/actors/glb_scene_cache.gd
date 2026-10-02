class_name GlbSceneCache
extends RefCounted
## Loads each glTF scene exactly once and hands out instances of the cached
## result.
##
## In-project actor assets prefer Godot's imported PackedScene. Besides avoiding
## a runtime parse, that path retains the importer's generated mesh LODs, shadow
## meshes, compression and texture mip chains. External authoring/test files and
## lean checkouts without an import cache keep the raw GLTFDocument fallback.
##
## Instances share their mesh, skin and material resources, which also removes
## the duplicate GPU uploads the per-actor parse produced. Per-actor tinting
## goes through `material_override`, so sharing the source materials cannot leak
## one actor's appearance into another.

static var _scenes: Dictionary = {}
static var _failed: Dictionary = {}

static func missing(paths: PackedStringArray) -> PackedStringArray:
	var out := PackedStringArray()
	for path: String in paths:
		path = _canonical_path(path)
		if not _scenes.has(path) and not _failed.has(path):
			out.append(path)
	return out

static func prepare(paths: PackedStringArray) -> Dictionary:
	# Worker-owned resources. The main thread publishes them only on arrival.
	var result: Dictionary = {}
	for path: String in paths:
		path = _canonical_path(path)
		var scene := _build(path)
		if scene != null:
			result[path] = scene
	return result

static func install_prepared(scenes: Dictionary) -> void:
	for path: String in scenes:
		if not _scenes.has(path):
			_scenes[path] = scenes[path]

## Returns a fresh instance of `path`, or null when the file cannot be imported.
static func instantiate(path: String) -> Node3D:
	path = _canonical_path(path)
	if path.is_empty() or _failed.has(path):
		return null
	var packed: PackedScene = _scenes.get(path) as PackedScene
	if packed == null:
		packed = _build(path)
		if packed == null:
			_failed[path] = true
			return null
		_scenes[path] = packed
	return packed.instantiate() as Node3D

## Drops every cached scene. Call when leaving a session so the next map is not
## charged for models it no longer uses.
static func clear() -> void:
	_scenes.clear()
	_failed.clear()

static func cached_scene_count() -> int:
	return _scenes.size()

static func _canonical_path(path: String) -> String:
	return ProjectSettings.globalize_path(path) if path.begins_with("res://") else path

static func _build(path: String) -> PackedScene:
	var imported := _imported_actor_scene(path)
	if imported != null:
		return imported
	return _build_raw(path)

## ResourceLoader resolves the `.import` remap in an editor checkout and the
## equivalent remap in an exported PCK. Restricting this preference to actor
## assets leaves the world-authoring cache's external-file semantics unchanged.
static func _imported_actor_scene(path: String) -> PackedScene:
	var resource_path := ProjectSettings.localize_path(path)
	if not resource_path.begins_with("res://assets/actors/"):
		return null
	var extension := resource_path.get_extension().to_lower()
	if extension != "glb" and extension != "gltf":
		return null
	if not ResourceLoader.exists(resource_path, "PackedScene"):
		return null
	return ResourceLoader.load(resource_path, "PackedScene",
		ResourceLoader.CACHE_MODE_REUSE) as PackedScene

static func _build_raw(path: String) -> PackedScene:
	var document: GLTFDocument = GLTFDocument.new()
	var state: GLTFState = GLTFState.new()
	if document.append_from_file(path, state) != OK:
		return null
	var generated: Node = document.generate_scene(state)
	if generated == null:
		return null
	if generated is not Node3D:
		generated.free()
		return null
	_claim(generated, generated)
	var packed: PackedScene = PackedScene.new()
	var packed_error: Error = packed.pack(generated)
	generated.free()
	if packed_error != OK:
		push_warning("glb cache: pack failed for %s (%s)" % [
			path, error_string(packed_error)])
		return null
	return packed

# PackedScene.pack() only stores nodes owned by the packed root.
static func _claim(node: Node, scene_owner: Node) -> void:
	for child: Node in node.get_children():
		child.owner = scene_owner
		_claim(child, scene_owner)
