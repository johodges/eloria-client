class_name GroundBag3D
extends StaticBody3D

const PICK_LAYER := 16

var bag_id: int = -1
var server_tile: Vector2i = Vector2i.ZERO

func configure(dto: Dictionary, adapter: CoordinateAdapter) -> void:
	bag_id = int(dto.get("bag_id", -1))
	server_tile = Vector2i(int(dto.get("x", 0)), int(dto.get("y", 0)))
	name = "GroundBag_%d" % bag_id
	collision_layer = PICK_LAYER
	collision_mask = 0
	global_position = adapter.server_to_godot(server_tile.x, server_tile.y)
	_build_visual()

func set_surface_height(height: float) -> void:
	global_position.y = height + 0.22

func _build_visual() -> void:
	if get_child_count() > 0:
		return
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = Color(0.34, 0.19, 0.07, 1.0)
	material.roughness = 0.9
	var bag_mesh: CapsuleMesh = CapsuleMesh.new()
	bag_mesh.radius = 0.32
	bag_mesh.height = 0.52
	bag_mesh.radial_segments = 16
	bag_mesh.rings = 8
	bag_mesh.material = material
	var visual: MeshInstance3D = MeshInstance3D.new()
	visual.name = "LegacyBagFallback"
	visual.mesh = bag_mesh
	visual.scale = Vector3(1.15, 0.85, 0.85)
	add_child(visual)

	var tie_material: StandardMaterial3D = StandardMaterial3D.new()
	tie_material.albedo_color = Color(0.82, 0.58, 0.18, 1.0)
	tie_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	var tie_mesh: CylinderMesh = CylinderMesh.new()
	tie_mesh.top_radius = 0.11
	tie_mesh.bottom_radius = 0.14
	tie_mesh.height = 0.1
	tie_mesh.material = tie_material
	var tie: MeshInstance3D = MeshInstance3D.new()
	tie.name = "BagTie"
	tie.mesh = tie_mesh
	tie.position.y = 0.3
	add_child(tie)

	var marker_material: StandardMaterial3D = StandardMaterial3D.new()
	marker_material.albedo_color = Color(1.0, 0.78, 0.18, 1.0)
	marker_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	marker_material.no_depth_test = true
	var marker_mesh: CylinderMesh = CylinderMesh.new()
	marker_mesh.top_radius = 0.7
	marker_mesh.bottom_radius = 0.7
	marker_mesh.height = 0.08
	marker_mesh.material = marker_material
	var map_marker: MeshInstance3D = MeshInstance3D.new()
	map_marker.name = "BagMapMarker"
	map_marker.mesh = marker_mesh
	map_marker.layers = 4
	map_marker.position.y = 4.0
	add_child(map_marker)

	var shape: CapsuleShape3D = CapsuleShape3D.new()
	shape.radius = 0.5
	shape.height = 0.9
	var collision: CollisionShape3D = CollisionShape3D.new()
	collision.name = "BagPickShape"
	collision.shape = shape
	add_child(collision)
