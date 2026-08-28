class_name GlbSceneCache
extends RefCounted
## Parses each external .glb exactly once and hands out instances of the cached
## result.
##
## Every actor that entered view used to run GLTFDocument.append_from_file() for
## its 2.3 MB race mesh, again for its hair variant, and again for each native
## equipment model. Parsing is the dominant cost of bringing an actor into the
## world and the result is identical every time, so it is cached here.
##
## Instances share their mesh, skin and material resources, which also removes
## the duplicate GPU uploads the per-actor parse produced. Per-actor tinting
## goes through `material_override`, so sharing the source materials cannot leak
## one actor's appearance into another.

static var _scenes: Dictionary = {}
static var _failed: Dictionary = {}

## Returns a fresh instance of `path`, or null when the file cannot be imported.
static func instantiate(path: String) -> Node3D:
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

static func _build(path: String) -> PackedScene:
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
