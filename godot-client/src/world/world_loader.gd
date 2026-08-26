class_name WorldLoader
extends Node3D

signal load_started(manifest_path: String)
signal load_completed(manifest: WorldManifest)
signal load_failed(errors: Array[String])

var manifest: WorldManifest
var coordinate_adapter: CoordinateAdapter
var world_root: Node3D

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
	_apply_collision_declarations()
	load_completed.emit(manifest)

func unload_world() -> void:
	if is_instance_valid(world_root):
		world_root.queue_free()
	world_root = null
	manifest = null
	coordinate_adapter = null

func _apply_collision_declarations() -> void:
	var collision: Dictionary = manifest.data.get("collision", {})
	var declared: Array = collision.get("nodeNames", [])
	for node_name in declared:
		var node := world_root.find_child(str(node_name), true, false)
		if node is MeshInstance3D:
			_create_static_collision(node)
		elif node == null:
			manifest.warnings.append("collision node not found: " + str(node_name))

func _create_static_collision(mesh_instance: MeshInstance3D) -> void:
	if mesh_instance.mesh == null:
		return
	var body := StaticBody3D.new()
	body.name = mesh_instance.name + "_Collision"
	var shape := CollisionShape3D.new()
	shape.shape = mesh_instance.mesh.create_trimesh_shape()
	body.add_child(shape)
	mesh_instance.add_child(body)
