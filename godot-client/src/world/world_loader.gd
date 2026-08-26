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
	load_started.emit(manifest_path)
	manifest = WorldManifest.load_file(manifest_path)
	if not manifest.is_valid():
		load_failed.emit(manifest.errors)
		return
	coordinate_adapter = manifest.coordinate_adapter()
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	var error := document.append_from_file(manifest.glb_path(), state)
	if error != OK:
		load_failed.emit(["glb_import_failed: " + error_string(error), manifest.glb_path()])
		return
	var generated := document.generate_scene(state)
	if generated == null:
		load_failed.emit(["glb_scene_generation_failed"])
		return
	world_root = generated
	world_root.name = "ImportedWorld_" + manifest.asset_id()
	add_child(world_root)
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
