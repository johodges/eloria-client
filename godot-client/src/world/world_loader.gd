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

signal load_started(manifest_path: String)
signal load_completed(manifest: WorldManifest)
signal load_failed(errors: Array[String])

var manifest: WorldManifest
var coordinate_adapter: CoordinateAdapter
var world_root: Node3D

## Trimesh shapes built during the load in progress, keyed by the mesh they
## were built from, so a mesh a region places hundreds of times is walked once.
## Cleared when the load finishes; the shapes themselves stay alive under the
## bodies that hold them.
var _collision_shapes: Dictionary = {}

func load_world(manifest_path: String) -> void:
	unload_world()
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
	var document: GLTFDocument = GLTFDocument.new()
	var state: GLTFState = GLTFState.new()
	var error: Error = document.append_from_file(resolved_glb_path, state)
	if error != OK:
		push_error("world_load stage=glb_import error=%s path=%s" % [
			error_string(error), resolved_glb_path])
		load_failed.emit(["glb_import_failed: " + error_string(error), resolved_glb_path])
		return
	print_debug("world_load stage=glb_imported path=", resolved_glb_path)
	var mipped: int = _build_texture_mipmaps(state)
	print_debug("world_load stage=texture_mipmaps rebuilt=", mipped)
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
	world_root.name = "ImportedWorld_" + manifest.asset_id()
	add_child(world_root)
	print_debug("world_load stage=scene_attached node=", world_root.get_path(),
		" children=", world_root.get_child_count(), " transform=", world_root.transform)
	# One walk of the import, not five. A region imports up to fifteen thousand
	# nodes and every pass below wanted either the mesh instances or a node by
	# name; each of them used to ask the scene tree for its own copy of the
	# list. The passes see exactly the nodes they saw before: the bodies the
	# collision passes add are not MeshInstance3D, so nothing they add belongs
	# in this list, and the batching pass took its list before it created any
	# batch.
	var index: Dictionary = _index_import()
	var mesh_instances: Array = index["meshInstances"] as Array
	_apply_material_passes(mesh_instances)
	_apply_collision_declarations(index["byName"] as Dictionary)
	_apply_rendered_walk_surfaces(mesh_instances)
	_apply_navigation_collision()
	# Must run last: it skips anything that carries collision, so the collision
	# passes above decide what stays an individually culled MeshInstance3D.
	_batch_static_instances(mesh_instances)
	_collision_shapes.clear()
	load_completed.emit(manifest)

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
	if is_instance_valid(world_root):
		world_root.queue_free()
	world_root = null
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
	var rendering_value: Variant = manifest.data.get("rendering", {})
	var rendering: Dictionary = rendering_value as Dictionary if rendering_value is Dictionary else {}
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
	for member_index: int in members.size():
		var member: MeshInstance3D = members[member_index] as MeshInstance3D
		multimesh.set_instance_transform(member_index, member.global_transform)
		# The source node stays in the tree so name lookups, manifest
		# declarations and tooling keep resolving; it simply stops drawing.
		member.visible = false
		member.set_meta(BATCH_META, batch)
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
