class_name WorldLoader
extends Node3D

const WORLD_COLLISION_LAYER := 1
const NAVIGATION_SURFACE_LAYER := 8

# Static-instance batching. A region such as Four Gates imports ~1700 mesh
# nodes that between them reference only 42 meshes, so almost every draw call
# repeats geometry the GPU already holds. Groups of identical opaque meshes are
# collapsed into one MultiMeshInstance3D per spatial cell, which keeps frustum
# culling meaningful while cutting draw calls by more than an order of
# magnitude. The rendered result is the same geometry with the same materials
# at the same transforms.
const BATCH_MINIMUM_INSTANCES := 4
const BATCH_CELL_METRES := 180.0
# Stamped on every source node a batch swallowed, naming the MultiMeshInstance3D
# that now draws it and its slot in that multimesh. A batched prop is otherwise
# untraceable from the node the rest of the client still holds, and OccluderFade
# has to reach the slot to lift one instance back out while it fades.
const BATCH_META := "static_batch"
const BATCH_INDEX_META := "static_batch_index"
# The same link written as a path from the imported root, which is the half of
# it that survives being packed into a scene.
#
# Node metadata is stored in a PackedScene, but a Node is not a Resource, and a
# Variant holding one is dropped on the way out - not nulled, dropped: after a
# round trip the key is not in `get_meta_list()` at all. A cached region whose
# batched props had only the object link would leave OccluderFade unable to
# find the MultiMesh drawing them, so it would fade a node that is not drawing
# and the prop in front of the player would stay solid. A NodePath is a
# built-in type and survives, so both are written and `_resolve_batch_links()`
# turns the path back into the object after a cache load.
const BATCH_PATH_META := "static_batch_path"

# The widest sibling list a package may hand Godot's scene builder.
#
# `GLTFDocument.generate_scene()` adds every node with a readable name, and
# that path checks the proposed name against the children the parent already
# holds, so it is quadratic in the width of a sibling list. The regions are
# built wide - Amberwood hangs 7 935 nodes off one parent, Verdant Stair 9 449
# - and that is where their load went: 3.9 s and 4.2 s of scene building
# against Four Gates' 117 ms for 1 276 siblings. Bucketing an over-wide list
# under empty grouping nodes before the scene is generated takes those two to
# 209 ms and 180 ms and costs about 9 ms.
#
# The groups carry an identity transform and no geometry, so every mesh keeps
# the world placement, name, mesh and visibility it had; only its depth in the
# tree changes, and every pass in this file and every consumer of the loaded
# world reaches nodes by a recursive search or by name. A list at or under
# this width is left exactly as the package built it: a thousand siblings cost
# a millisecond, and an untouched tree is the one the package author sees.
const MAX_SIBLINGS := 512
# Grouping nodes are named after the parent they were split out of. No node in
# any shipped package starts with this prefix, which is what keeps the name
# index the collision declarations are resolved through unambiguous.
const GROUP_NAME_PREFIX := "WorldGroup_"

# How many frames after a load the cache is packed and written.
#
# Not zero, and not "deferred": writing an entry costs 350-1050 ms on the frame
# it lands on, and deferring by one frame would put that inside the frame that
# draws the region for the first time - exactly the frame the player is waiting
# on. Three frames puts it in the arrival instead, where the transition is
# still resolving and the wait is already expected, and it is paid once per
# region for the life of an install. See `_write_cache` for why none of it can
# go on a worker thread.
const CACHE_WRITE_DELAY_FRAMES := 3
# Compression on the cache file: a slower write for a third of the disk.
#
# Measured on Four Gates, packing once and saving both ways: compressed is
# 32.9 MB, saves in 600 ms and reads in 285; uncompressed is 87.8 MB, saves in
# 74 ms and reads in 136. Across the twelve regions that is 383 MB against
# 1.02 GB, and across all 53 packages a player could visit, roughly 1.2 GB
# against 3.2 GB.
#
# Compressed, because disk is the resource the player did not agree to spend
# and there is no eviction policy to spend it against; the write it pays for is
# one hitch per region per install, and the read it costs is 150 ms on a load
# that is still 40% faster than building the region. Flip this if that trade
# ever reads the other way - nothing else has to change, because an entry
# written either way is read by the same call.
const CACHE_COMPRESS := true

signal load_started(manifest_path: String)
signal load_completed(manifest: WorldManifest)
signal load_failed(errors: Array[String])

var manifest: WorldManifest
var coordinate_adapter: CoordinateAdapter
var world_root: Node3D

## True when the region in the tree was read back from the map cache rather
## than parsed out of its package. Read by the benchmarks and by the tests that
## prove a second visit hits.
var loaded_from_cache := false

## What the last load did about the cache, one of `&"disabled"`, `&"miss"`,
## `&"hit"`, `&"unreadable"` or `&"no_digest"`. A miss is the normal state of a
## first visit; `&"unreadable"` means a file was there and did not load, which
## is the only one of the five worth looking into.
var cache_status: StringName = &"disabled"

## The file the last load read or would write. Empty when the package could not
## be hashed or the cache is off.
var cache_file := ""

## The package digest of the region in the tree - the same value the server
## sends in ELORIA_MAP_DIGEST, and the thing the cache key is derived from.
var package_digest := ""

## Microseconds the last load spent in each of its steps, in the order they
## ran, plus `total`. A map load is a handful of long steps over a package the
## client did not author, and which of them a region is paying for is not
## guessable from the outside: Four Gates builds three thousand mesh nodes in
## 88 ms and Amberwood nine thousand in 2.6 s. Reading the clock a dozen times
## costs nothing against a load measured in seconds, so the loader always says
## where it went and `tests/integration/map_load_phases.gd` only has to read it.
var load_phases: Dictionary = {}

## Trimesh shapes built during the load in progress, keyed by the mesh they
## were built from, so a mesh a region places hundreds of times is walked once.
## Cleared when the load finishes; the shapes themselves stay alive under the
## bodies that hold them.
var _collision_shapes: Dictionary = {}

func load_world(manifest_path: String) -> void:
	unload_world()
	var began: int = Time.get_ticks_usec()
	var mark: int = began
	load_phases = {}
	print_debug("world_load stage=manifest_open path=", manifest_path)
	load_started.emit(manifest_path)
	manifest = WorldManifest.load_file(manifest_path)
	if not manifest.is_valid():
		push_error("world_load stage=manifest_validate errors=%s" % [manifest.errors])
		load_failed.emit(manifest.errors)
		return
	var resolved_glb_path: String = manifest.glb_path()
	print_debug("world_load stage=manifest_valid asset=", manifest.asset_id(),
		" glb_path=", resolved_glb_path)
	coordinate_adapter = manifest.coordinate_adapter()
	mark = _phase(&"manifest", mark)

	# The package's own bytes, which are both the cache key and the value the
	# server's ELORIA_MAP_DIGEST is checked against. 56-91 ms on an 18-33 MB
	# region, which is the price of the whole contract: an entry that does not
	# match the package on disk is never read, so a client update rebuilds
	# itself with nothing to remember.
	package_digest = MapSceneCache.package_digest(manifest_path, resolved_glb_path)
	MapSceneCache.note_local_digest(manifest.asset_id(), package_digest)
	cache_file = MapSceneCache.cache_path(manifest.asset_id(), package_digest)
	mark = _phase(&"digest", mark)
	if _load_from_cache(mark, began):
		return

	var document: GLTFDocument = GLTFDocument.new()
	var state: GLTFState = GLTFState.new()
	var error: Error = document.append_from_file(resolved_glb_path, state)
	if error != OK:
		push_error("world_load stage=glb_import error=%s path=%s" % [
			error_string(error), resolved_glb_path])
		load_failed.emit(["glb_import_failed: " + error_string(error), resolved_glb_path])
		return
	print_debug("world_load stage=glb_imported path=", resolved_glb_path)
	mark = _phase(&"parse", mark)
	var mipped: int = _build_texture_mipmaps(state)
	print_debug("world_load stage=texture_mipmaps rebuilt=", mipped)
	mark = _phase(&"mipmaps", mark)
	var groups: int = _regroup_wide_siblings(state)
	if groups > 0:
		print_debug("world_load stage=regroup groups=", groups)
	mark = _phase(&"regroup", mark)
	var generated: Node = document.generate_scene(state)
	if generated == null:
		push_error("world_load stage=scene_generate error=null_scene path=%s" % resolved_glb_path)
		load_failed.emit(["glb_scene_generation_failed"])
		return
	world_root = generated as Node3D
	if world_root == null:
		push_error("world_load stage=scene_generate error=root_not_node3d path=%s" % resolved_glb_path)
		load_failed.emit(["glb_scene_root_not_node3d"])
		return
	mark = _phase(&"generateScene", mark)
	world_root.name = "ImportedWorld_" + manifest.asset_id()
	add_child(world_root)
	print_debug("world_load stage=scene_attached node=", world_root.get_path(),
		" children=", world_root.get_child_count(), " transform=", world_root.transform)
	mark = _phase(&"attach", mark)
	# One walk of the import, not five. A region imports up to fifteen thousand
	# nodes and every pass below wanted either the mesh instances or a node by
	# name; each of them used to ask the scene tree for its own copy of the
	# list. The passes see exactly the nodes they saw before: the bodies the
	# collision passes add are not MeshInstance3D, so nothing they add belongs
	# in this list, and the batching pass took its list before it created any
	# batch.
	var index: Dictionary = _index_import()
	var mesh_instances: Array = index["meshInstances"] as Array
	mark = _phase(&"index", mark)
	_apply_material_passes(mesh_instances)
	mark = _phase(&"materials", mark)
	_apply_collision_declarations(index["byName"] as Dictionary)
	mark = _phase(&"collision", mark)
	_apply_rendered_walk_surfaces(mesh_instances)
	mark = _phase(&"walkSurfaces", mark)
	_apply_navigation_collision()
	mark = _phase(&"navigation", mark)
	# Must run last: it skips anything that carries collision, so the collision
	# passes above decide what stays an individually culled MeshInstance3D.
	_batch_static_instances(mesh_instances)
	_collision_shapes.clear()
	mark = _phase(&"batching", mark)
	# What the loader produced, before anything else in the client has been
	# handed it. See `_snapshot_for_cache`.
	if cache_status == &"miss":
		_snapshot_for_cache()
	mark = _phase(&"cacheSnapshot", mark)
	load_phases[&"total"] = mark - began
	load_completed.emit(manifest)
	if cache_status == &"miss":
		_cache_write_countdown = CACHE_WRITE_DELAY_FRAMES
		set_process(true)

# --------------------------------------------------------------------------
# The map cache
# --------------------------------------------------------------------------

## Frames left before the queued cache write runs, or 0 for none.
var _cache_write_countdown := 0
## The tree the loader itself produced, and the parts of it a consumer is
## allowed to change afterwards. See `_snapshot_for_cache`.
var _cache_nodes: Array[Node] = []
var _cache_visible := PackedByteArray()
var _cache_overrides: Dictionary = {}

## Reads the region back from the cache, if there is an entry for exactly this
## package and this format version. Returns true when the world is in the tree
## and `load_completed` has been emitted, which is the caller's signal to stop.
##
## Every failure here falls through to the ordinary load. A cache is an
## optimisation; a client that cannot read one still has the package.
func _load_from_cache(mark: int, began: int) -> bool:
	if not MapSceneCache.is_enabled():
		cache_status = &"disabled"
		return false
	if cache_file.is_empty():
		# The package could not be hashed, so it cannot be keyed either.
		cache_status = &"no_digest"
		return false
	if not FileAccess.file_exists(cache_file):
		cache_status = &"miss"
		return false
	# IGNORE_DEEP so a second load in one session builds its own meshes and
	# materials rather than handing back the ones the last load is still
	# holding. That is what a fresh load does, and the point of the cache is to
	# be indistinguishable from one.
	var packed: PackedScene = ResourceLoader.load(
		cache_file, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE_DEEP) as PackedScene
	mark = _phase(&"cacheRead", mark)
	if packed == null:
		push_warning("map cache: %s did not load; rebuilding" % cache_file)
		DirAccess.remove_absolute(cache_file)
		cache_status = &"unreadable"
		return false
	var restored: Node3D = packed.instantiate() as Node3D
	if restored == null:
		push_warning("map cache: %s is not a Node3D; rebuilding" % cache_file)
		DirAccess.remove_absolute(cache_file)
		cache_status = &"unreadable"
		return false
	world_root = restored
	world_root.name = "ImportedWorld_" + manifest.asset_id()
	add_child(world_root)
	mark = _phase(&"cacheInstantiate", mark)
	var relinked: int = _resolve_batch_links()
	mark = _phase(&"cacheLinks", mark)
	loaded_from_cache = true
	cache_status = &"hit"
	print_debug("world_load stage=cache_hit file=", cache_file,
		" batches_relinked=", relinked)
	load_phases[&"total"] = mark - began
	load_completed.emit(manifest)
	return true

## Turns every batch link back from a path into the MultiMeshInstance3D it
## names, and returns how many it resolved.
##
## Runs after a cache load, where the object half of the link did not survive
## the round trip. Harmless on a freshly parsed tree, where it re-resolves the
## links to the same nodes they already point at.
func _resolve_batch_links() -> int:
	var resolved := 0
	for node: Node in world_root.find_children("*", "MeshInstance3D", true, false):
		if not node.has_meta(BATCH_PATH_META):
			continue
		var path: NodePath = node.get_meta(BATCH_PATH_META) as NodePath
		var batch: MultiMeshInstance3D = world_root.get_node_or_null(
			path) as MultiMeshInstance3D
		if batch == null:
			# The batch it names is gone, so the mesh is drawing itself again.
			node.remove_meta(BATCH_PATH_META)
			if node.has_meta(BATCH_META):
				node.remove_meta(BATCH_META)
			node.visible = true
			push_warning("map cache: batch %s missing for %s" % [path, node.name])
			continue
		node.set_meta(BATCH_META, batch)
		resolved += 1
	return resolved

## What the loader produced, taken while the tree is still only the loader's.
##
## The cache has to hold the region as the loader built it, and by the time the
## write runs the rest of the client has had the tree for three frames: the
## interior cutaway may have hidden a wall the camera is looking through, the
## secret sections may have hidden a section, and the occluder fade may have
## swapped a translucent material onto whatever is between the camera and the
## player. Baking any of those in would make the cached region quietly
## different from a fresh one - a rock that is permanently glass.
##
## So the two things a consumer can change are recorded here, while nothing but
## the loader has touched the tree, and put back for the length of the pack.
## Nodes a consumer *adds* need no handling: `PackedScene.pack` only stores
## nodes owned by the packed root, the owners are set from this list, and
## anything not in it is left out for free.
func _snapshot_for_cache() -> void:
	_cache_nodes = world_root.find_children("*", "", true, false)
	var count: int = _cache_nodes.size()
	_cache_visible.resize(count)
	_cache_overrides.clear()
	for index: int in count:
		var node: Node = _cache_nodes[index]
		var spatial: Node3D = node as Node3D
		_cache_visible[index] = 1 if spatial == null or spatial.visible else 0
		var mesh_instance: MeshInstance3D = node as MeshInstance3D
		if mesh_instance == null:
			continue
		var overrides: Array[Material] = []
		var any := false
		for surface: int in mesh_instance.get_surface_override_material_count():
			var material: Material = mesh_instance.get_surface_override_material(surface)
			overrides.append(material)
			any = any or material != null
		if any:
			_cache_overrides[index] = overrides

func _release_snapshot() -> void:
	_cache_nodes.clear()
	_cache_visible.resize(0)
	_cache_overrides.clear()

func _process(_delta: float) -> void:
	if _cache_write_countdown <= 0:
		set_process(false)
		return
	_cache_write_countdown -= 1
	if _cache_write_countdown > 0:
		return
	set_process(false)
	_write_cache()

## Packs the region and writes it, three frames after the load.
##
## Both halves are on the main thread, and the second half is not by choice.
##
## The pack has to be: it reads the scene tree. The save was on a worker
## `Thread` first, because it is the larger half and appears to touch nothing
## but the `PackedScene` - and it worked, until the client was asked to quit
## while one was in flight. `ResourceSaver.save` of a scene full of imported
## `ArrayMesh`es reaches the rendering server to get their surface arrays back,
## and off the main thread that is a synchronous request the main thread has to
## serve. At shutdown the main thread stops serving, the worker never returns,
## and `wait_to_finish()` waits for it forever: a client that will not close.
## Measured, not deduced - `Godot --script` on a probe that loads a region and
## quits five frames later hangs every time, with the worker stopped inside
## `ResourceSaver.save`.
##
## So it is done here, and it is a real cost: 350-1050 ms on the frame it lands
## on, once per region for the life of an install. Three frames after
## `load_completed` is chosen to put it inside the arrival - the player is
## already waiting, the transition is still resolving - rather than under their
## feet a minute later. `CACHE_COMPRESS` is the dial if that is the wrong
## trade: uncompressed saves in about an eighth of the time and takes 2.7x the
## disk.
func _write_cache() -> void:
	if not is_instance_valid(world_root) or cache_file.is_empty():
		_release_snapshot()
		return
	if not MapSceneCache.ensure_directory():
		_release_snapshot()
		return
	var began: int = Time.get_ticks_usec()
	var undo: Array = _restore_pristine()
	for node: Node in _cache_nodes:
		if is_instance_valid(node):
			node.owner = world_root
	var packed := PackedScene.new()
	var error: Error = packed.pack(world_root)
	_undo_pristine(undo)
	load_phases[&"cachePack"] = Time.get_ticks_usec() - began
	_release_snapshot()
	if error != OK:
		push_warning("map cache: pack failed for %s (%s)" % [
			cache_file, error_string(error)])
		return
	_save_entry(packed, cache_file,
		manifest.asset_id() if manifest != null else "")

## Writes the packed region.
##
## The file lands under a temporary name and is renamed into place, so a write
## that does not finish - the disk fills, the process is killed - leaves no
## half a region for the next launch to read as a whole one.
func _save_entry(packed: PackedScene, path: String, map_id: String) -> void:
	var began: int = Time.get_ticks_usec()
	var staging: String = MapSceneCache.staging_path(path)
	var flags: int = ResourceSaver.FLAG_COMPRESS if CACHE_COMPRESS else 0
	var error: Error = ResourceSaver.save(packed, staging, flags)
	if error != OK:
		push_warning("map cache: save failed for %s (%s)" % [path, error_string(error)])
		DirAccess.remove_absolute(staging)
		return
	DirAccess.remove_absolute(path)
	error = DirAccess.rename_absolute(staging, path)
	if error != OK:
		push_warning("map cache: could not place %s (%s)" % [path, error_string(error)])
		DirAccess.remove_absolute(staging)
		return
	var pruned: int = MapSceneCache.prune(map_id, path)
	load_phases[&"cacheSave"] = Time.get_ticks_usec() - began
	print("world_load stage=cache_written file=", path, " milliseconds=",
		(Time.get_ticks_usec() - began) / 1000, " stale_removed=", pruned)

## Puts back what the loader left, and returns what to undo afterwards.
func _restore_pristine() -> Array:
	var undo: Array = []
	for index: int in _cache_nodes.size():
		var node: Node = _cache_nodes[index]
		if not is_instance_valid(node):
			continue
		var spatial: Node3D = node as Node3D
		if spatial != null:
			var wanted: bool = _cache_visible[index] == 1
			if spatial.visible != wanted:
				undo.append([spatial, "visible", spatial.visible])
				spatial.visible = wanted
		var mesh_instance: MeshInstance3D = node as MeshInstance3D
		if mesh_instance == null:
			continue
		var wanted_overrides: Variant = _cache_overrides.get(index)
		for surface: int in mesh_instance.get_surface_override_material_count():
			var current: Material = mesh_instance.get_surface_override_material(surface)
			var pristine: Material = null
			if wanted_overrides is Array and surface < (wanted_overrides as Array).size():
				pristine = (wanted_overrides as Array)[surface] as Material
			if current == pristine:
				continue
			undo.append([mesh_instance, surface, current])
			mesh_instance.set_surface_override_material(surface, pristine)
	return undo

func _undo_pristine(undo: Array) -> void:
	for entry_value: Variant in undo:
		var entry: Array = entry_value as Array
		var node: Node = entry[0] as Node
		if not is_instance_valid(node):
			continue
		if entry[1] is String:
			(node as Node3D).visible = bool(entry[2])
		else:
			(node as MeshInstance3D).set_surface_override_material(
				int(entry[1]), entry[2] as Material)

## Records the microseconds since `started` under `name` and returns the clock
## reading that closed it, which is the next phase's start.
func _phase(name: StringName, started: int) -> int:
	var now: int = Time.get_ticks_usec()
	load_phases[name] = now - started
	return now

## Splits every sibling list wider than `MAX_SIBLINGS` under empty grouping
## nodes, so Godot's scene builder never pays its quadratic name check on one.
## Returns how many groups were added. See MAX_SIBLINGS for what this is worth.
##
## Runs on the parsed glTF rather than on the built tree, because the cost is
## in the building: by the time there are nodes to reparent it has been paid.
##
## Packages that carry a skin or a skeleton are left alone. Godot decides where
## a Skeleton3D goes from the joints' place among their siblings, and a rig is
## small enough that it would never be split anyway; skipping the whole package
## is a cheaper promise to keep than a rule about which lists may be split.
func _regroup_wide_siblings(state: GLTFState) -> int:
	var rendering: Dictionary = _rendering_settings()
	if not bool(rendering.get("regroupWideSiblings", true)):
		return 0
	if not state.get_skins().is_empty() or not state.get_skeletons().is_empty():
		return 0
	var limit: int = maxi(16, int(rendering.get("maxSiblings", MAX_SIBLINGS)))
	var nodes: Array = state.get_nodes()
	# Only the nodes the package brought: the groups appended below are built
	# narrow, so revisiting them would find nothing to do.
	var parsed: int = nodes.size()
	var added := 0
	# The scene root Godot generates is a parent too, and a package whose nodes
	# are all roots - Sunmane Steppe's thousand props are - hangs every one of
	# them off it.
	var roots: PackedInt32Array = state.root_nodes
	if roots.size() > limit:
		var root_groups: PackedInt32Array = _bucket_siblings(nodes, roots, -1)
		state.root_nodes = root_groups
		added += root_groups.size()
	for index: int in range(parsed):
		var node: GLTFNode = nodes[index] as GLTFNode
		if node == null:
			continue
		var children: PackedInt32Array = node.get_children()
		if children.size() <= limit:
			continue
		var groups: PackedInt32Array = _bucket_siblings(nodes, children, index)
		node.set_children(groups)
		added += groups.size()
	if added > 0:
		state.set_nodes(nodes)
	return added

## Splits `children` into buckets of about sqrt(n), appends a grouping node per
## bucket to `nodes`, and returns the indices of those groups.
##
## sqrt is where the two costs meet: smaller buckets leave the groups
## themselves a wide sibling list, larger ones leave the buckets wide, and the
## builder pays the same quadratic on either. 7 935 children become 90 groups
## of 90.
func _bucket_siblings(nodes: Array, children: PackedInt32Array,
		parent: int) -> PackedInt32Array:
	var bucket: int = maxi(1, int(ceil(sqrt(float(children.size())))))
	var groups := PackedInt32Array()
	var cursor := 0
	while cursor < children.size():
		var group := GLTFNode.new()
		group.set_name("%s%d_%d" % [GROUP_NAME_PREFIX, parent + 1, groups.size()])
		group.parent = parent
		var slice := PackedInt32Array()
		var stop: int = mini(cursor + bucket, children.size())
		while cursor < stop:
			slice.append(children[cursor])
			cursor += 1
		group.set_children(slice)
		nodes.append(group)
		var group_index: int = nodes.size() - 1
		for child_index: int in slice:
			(nodes[child_index] as GLTFNode).parent = group_index
		groups.append(group_index)
	return groups

## The map's `rendering` block, or an empty one. Both the batching and the
## regrouping are per-map switches a package can turn off.
func _rendering_settings() -> Dictionary:
	if manifest == null:
		return {}
	var value: Variant = manifest.data.get("rendering", {})
	return value as Dictionary if value is Dictionary else {}

## The import's mesh instances, and the first node of each name. Both lists the
## load passes need, taken in a single traversal.
func _index_import() -> Dictionary:
	var mesh_instances: Array = []
	var by_name: Dictionary = {}
	for node: Node in world_root.find_children("*", "", true, false):
		if not by_name.has(node.name):
			by_name[node.name] = node
		if node is MeshInstance3D:
			mesh_instances.append(node)
	return {"meshInstances": mesh_instances, "byName": by_name}

## GLTFDocument builds its textures at runtime with no mip chain, so every
## roof and every stretch of ground aliased against the pixel grid and swam as
## the camera moved. The images the state carries are the same objects the
## generated materials will reference, so rebuilding them here reaches the
## whole map. Must run before generate_scene().
func _build_texture_mipmaps(state: GLTFState) -> int:
	var rebuilt := 0
	for texture_value: Variant in state.get_images():
		var texture: ImageTexture = texture_value as ImageTexture
		if texture == null:
			continue
		var image: Image = texture.get_image()
		if image == null or image.is_empty() or image.has_mipmaps():
			continue
		if image.is_compressed() and image.decompress() != OK:
			continue
		image.generate_mipmaps()
		texture.set_image(image)
		rebuilt += 1
	return rebuilt

## The two material passes a freshly imported map needs, over one list of its
## mesh instances. Each is described below; a material is touched once by
## either, whichever instance reaches it first.
##
## Anisotropic sampling: a mip chain on its own blurs ground seen at a grazing
## angle, which is most of an isometric view. Anisotropic sampling is what
## keeps the far end of a road readable rather than smeared.
##
## Vertex coverage: a ground class is cut against its neighbour by an alpha
## test on the coverage the map stores in COLOR_0's alpha, which is what lets a
## diagonal road read as a diagonal instead of a flight of steps the width of a
## terrain cell. Godot's glTF importer brings the colours in and sets the alpha
## mode, but leaves `vertex_color_use_as_albedo` off, and without it the vertex
## alpha never reaches the shader and every class draws over its whole quad.
##
## Only alpha-tested materials get the coverage flag, and only where the mesh
## carries colours. Turning it on elsewhere would multiply albedo by a colour
## the mesh does not have, and Godot substitutes white for a missing COLOR_0,
## so it is harmless but pointless; restricting it keeps the flag where it
## means something. The colours the ground carries are white apart from their
## alpha, so albedo is unchanged.
##
## Returns how many materials the coverage flag reached.
func _apply_material_passes(mesh_instances: Array) -> int:
	var applied := 0
	var filtered: Dictionary = {}
	var covered: Dictionary = {}
	for node_value: Variant in mesh_instances:
		var mesh: Mesh = (node_value as MeshInstance3D).mesh
		if mesh == null:
			continue
		for surface: int in range(mesh.get_surface_count()):
			var material: BaseMaterial3D = mesh.surface_get_material(
				surface) as BaseMaterial3D
			if material == null:
				continue
			var id: int = material.get_instance_id()
			if not filtered.has(id):
				filtered[id] = true
				material.texture_filter = (
					BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC)
			if covered.has(id):
				continue
			if (mesh.surface_get_format(surface) & Mesh.ARRAY_FORMAT_COLOR) == 0:
				continue
			if material.transparency != BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
				continue
			covered[id] = true
			material.vertex_color_use_as_albedo = true
			applied += 1
	return applied

func unload_world() -> void:
	# A map change while a cache write is still queued drops the write: the
	# tree it would pack is about to be freed, and the region will be built
	# again the next time it is entered, which is the state it was in before.
	_cache_write_countdown = 0
	set_process(false)
	_release_snapshot()
	if is_instance_valid(world_root):
		world_root.queue_free()
	world_root = null
	loaded_from_cache = false
	cache_status = &"disabled"
	cache_file = ""
	package_digest = ""
	_collision_shapes.clear()
	manifest = null
	coordinate_adapter = null

func _apply_collision_declarations(by_name: Dictionary) -> void:
	var collision: Dictionary = manifest.data.get("collision", {})
	var declared: Array = collision.get("nodeNames", [])
	if declared.is_empty():
		return
	# A map may declare collision on the geometry the player sees, or on separate
	# proxy boxes tucked inside it. A proxy is a physics volume, never a surface:
	# drawn, it sits millimetres inside the wall it stands for and the two fight
	# for the same pixels. The shape is still built from the proxy's mesh, and
	# CollisionShape3D is not a VisualInstance3D, so hiding the node it hangs off
	# costs nothing in physics.
	var proxies: bool = bool(collision.get("nodesAreProxies", false))
	# `by_name` is the index taken by the single walk in load_world: one walk of
	# a 15 000-node import instead of one walk per declared name.
	for node_name in declared:
		var node: Node = by_name.get(str(node_name)) as Node
		if node is MeshInstance3D:
			_create_static_collision(node as MeshInstance3D)
			if proxies:
				(node as MeshInstance3D).visible = false
		elif node == null:
			manifest.warnings.append("collision node not found: " + str(node_name))

func _apply_navigation_collision() -> void:
	var navigation: Dictionary = manifest.data.get("navigation", {})
	var navmesh_value: Variant = navigation.get("navmesh", {})
	if not navmesh_value is Dictionary:
		return
	var navmesh: Dictionary = navmesh_value as Dictionary
	var polygons_value: Variant = navmesh.get("polygons", [])
	if not polygons_value is Array:
		return
	var body: StaticBody3D = StaticBody3D.new()
	body.name = "NavigationSurfaceCollision"
	# Keep walk surfaces separate from gates, bridges, and other authored
	# collision. Actor grounding and MOVE_TO picking must never snap to the top
	# of structural collision merely because it is the first ray hit.
	body.collision_layer = NAVIGATION_SURFACE_LAYER
	body.collision_mask = 0
	for polygon_value: Variant in polygons_value as Array:
		if not polygon_value is Dictionary:
			continue
		var polygon: Dictionary = polygon_value as Dictionary
		var vertices_value: Variant = polygon.get("vertices", [])
		if not vertices_value is Array:
			continue
		var raw_vertices: Array = vertices_value as Array
		if raw_vertices.size() < 3:
			continue
		var vertices: Array[Vector3] = []
		for raw_vertex: Variant in raw_vertices:
			if raw_vertex is Array and (raw_vertex as Array).size() >= 3:
				var values: Array = raw_vertex as Array
				vertices.append(Vector3(float(values[0]), float(values[1]), float(values[2])))
		if vertices.size() < 3:
			continue
		var faces: PackedVector3Array = PackedVector3Array()
		for index: int in range(1, vertices.size() - 1):
			faces.append(vertices[0])
			faces.append(vertices[index])
			faces.append(vertices[index + 1])
		var shape: ConcavePolygonShape3D = ConcavePolygonShape3D.new()
		shape.set_faces(faces)
		var collision: CollisionShape3D = CollisionShape3D.new()
		collision.name = "Nav_" + str(polygon.get("id", body.get_child_count()))
		collision.shape = shape
		body.add_child(collision)
	if body.get_child_count() == 0:
		body.queue_free()
		manifest.warnings.append("navigation polygons did not produce collision")
		return
	world_root.add_child(body)

func _batch_static_instances(mesh_instances: Array) -> void:
	var rendering: Dictionary = _rendering_settings()
	if not bool(rendering.get("batchStaticInstances", true)):
		return
	var minimum: int = maxi(2, int(rendering.get("batchMinimumInstances",
		BATCH_MINIMUM_INSTANCES)))
	var cell_size: float = maxf(1.0, float(rendering.get("batchCellMetres",
		BATCH_CELL_METRES)))
	var groups: Dictionary = {}
	for node_value: Variant in mesh_instances:
		var mesh_instance: MeshInstance3D = node_value as MeshInstance3D
		if not _is_batchable(mesh_instance):
			continue
		var origin: Vector3 = mesh_instance.global_transform.origin
		var key: String = "%d|%d|%d|%d|%d|%d|%d" % [
			mesh_instance.mesh.get_instance_id(), mesh_instance.layers,
			mesh_instance.cast_shadow, mesh_instance.gi_mode,
			floori(origin.x / cell_size), floori(origin.y / cell_size),
			floori(origin.z / cell_size)]
		if not groups.has(key):
			groups[key] = []
		(groups[key] as Array).append(mesh_instance)
	var batches: int = 0
	var collapsed: int = 0
	for key_value: Variant in groups:
		var members: Array = groups[key_value] as Array
		if members.size() < minimum:
			continue
		_create_batch(members, batches)
		batches += 1
		collapsed += members.size()
	if batches > 0:
		print_debug("world_load stage=static_batching batches=", batches,
			" instances=", collapsed)

func _is_batchable(mesh_instance: MeshInstance3D) -> bool:
	var mesh: Mesh = mesh_instance.mesh
	if mesh == null or mesh.get_surface_count() == 0:
		return false
	# Anything that carries collision, an animation target, a skin or an author
	# override keeps its own node so lookups, physics and skinning are untouched.
	if mesh_instance.get_child_count() > 0:
		return false
	if mesh_instance.skin != null or not mesh_instance.skeleton.is_empty():
		return false
	if mesh_instance.material_override != null or mesh_instance.material_overlay != null:
		return false
	if not mesh_instance.visible or not mesh_instance.is_visible_in_tree():
		return false
	if mesh_instance.visibility_range_end > 0.0:
		return false
	for surface: int in mesh_instance.get_surface_override_material_count():
		# MultiMeshInstance3D has no per-surface overrides to carry these onto.
		if mesh_instance.get_surface_override_material(surface) != null:
			return false
	for surface: int in mesh.get_surface_count():
		var material: Material = mesh.surface_get_material(surface)
		if material == null:
			continue
		if material is not BaseMaterial3D:
			return false
		# Blended surfaces are sorted per instance; batching them would change
		# the draw order and therefore the picture.
		if (material as BaseMaterial3D).transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
			return false
	return true

func _create_batch(members: Array, index: int) -> void:
	var reference: MeshInstance3D = members[0] as MeshInstance3D
	var multimesh: MultiMesh = MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.mesh = reference.mesh
	multimesh.instance_count = members.size()
	var batch: MultiMeshInstance3D = MultiMeshInstance3D.new()
	batch.name = "StaticBatch_%d_%s" % [index, reference.name]
	batch.multimesh = multimesh
	batch.layers = reference.layers
	batch.cast_shadow = reference.cast_shadow
	batch.gi_mode = reference.gi_mode
	world_root.add_child(batch)
	batch.global_transform = Transform3D.IDENTITY
	# Taken after add_child, which is what settles the name: a package that
	# already carries a node called StaticBatch_0_Rock would have had this one
	# renamed, and a path written before that would point at the wrong node.
	var batch_path: NodePath = world_root.get_path_to(batch)
	for member_index: int in members.size():
		var member: MeshInstance3D = members[member_index] as MeshInstance3D
		multimesh.set_instance_transform(member_index, member.global_transform)
		# The source node stays in the tree so name lookups, manifest
		# declarations and tooling keep resolving; it simply stops drawing.
		member.visible = false
		member.set_meta(BATCH_META, batch)
		member.set_meta(BATCH_PATH_META, batch_path)
		member.set_meta(BATCH_INDEX_META, member_index)

func _apply_rendered_walk_surfaces(mesh_instances: Array) -> void:
	var navigation: Dictionary = manifest.data.get("navigation", {})
	var prefixes_value: Variant = navigation.get("surfaceNodePrefixes", [])
	if not prefixes_value is Array:
		return
	var prefixes: Array = prefixes_value as Array
	for node_value: Variant in mesh_instances:
		var mesh_instance: MeshInstance3D = node_value as MeshInstance3D
		var node_name: String = mesh_instance.name
		var matches_surface: bool = false
		for prefix_value: Variant in prefixes:
			if node_name.begins_with(str(prefix_value)):
				matches_surface = true
				break
		if matches_surface:
			_create_static_collision(mesh_instance, NAVIGATION_SURFACE_LAYER,
				"_WalkSurfaceCollision")

func _create_static_collision(mesh_instance: MeshInstance3D,
		layer: int = WORLD_COLLISION_LAYER, suffix: String = "_Collision") -> void:
	if mesh_instance.mesh == null:
		return
	var body := StaticBody3D.new()
	body.name = mesh_instance.name + suffix
	body.collision_layer = layer
	var shape := CollisionShape3D.new()
	shape.shape = _trimesh_shape(mesh_instance.mesh)
	body.add_child(shape)
	mesh_instance.add_child(body)

## The trimesh shape for `mesh`, built once per mesh per load.
##
## A region names the same handful of meshes over and over: Amberwood declares
## collision on 862 nodes that between them reference 91 meshes, and the walk
## surfaces of a region repeat too. `create_trimesh_shape()` walks every
## triangle and the physics server builds a BVH per shape, so building one per
## node paid for the same geometry ten times over - 638 ms of Amberwood's load
## and 528 ms of Verdant Stair's.
##
## Sharing is exact rather than approximate: the faces are in the mesh's own
## space and the placement lives on the CollisionShape3D's parent, which is
## what lets one shape stand under many bodies, and is how an instanced scene
## has always worked. The table is per load, so a map change does not hold the
## last map's geometry.
func _trimesh_shape(mesh: Mesh) -> ConcavePolygonShape3D:
	var key: int = mesh.get_instance_id()
	var cached: ConcavePolygonShape3D = _collision_shapes.get(key) as ConcavePolygonShape3D
	if cached != null:
		return cached
	var built: ConcavePolygonShape3D = mesh.create_trimesh_shape()
	_collision_shapes[key] = built
	return built
