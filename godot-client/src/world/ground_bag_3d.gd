class_name GroundBag3D
extends StaticBody3D

const PICK_LAYER := 16
## The disc a dropped bag shows on both maps, in the amber the loot windows
## use for a bag. Sized like the harvest nodes and interactives it is dropped
## among: a bag is the same kind of thing to read off a map as they are, and a
## smaller disc than theirs is one the outline closes over rather than frames.
const MAP_MARKER_RADIUS := 7.0
const MAP_MARKER_COLOUR := Color(1.0, 0.78, 0.18, 1.0)

var bag_id: int = -1
var server_tile: Vector2i = Vector2i.ZERO

func configure(dto: Dictionary, adapter: CoordinateAdapter) -> void:
	bag_id = int(dto.get("bag_id", -1))
	server_tile = Vector2i(int(dto.get("x", 0)), int(dto.get("y", 0)))
	name = "GroundBag_%d" % bag_id
	collision_layer = PICK_LAYER
	collision_mask = 0
	# Configure before the node enters the scene tree; its parent WorldRoot uses
	# the same authored coordinate space, so a local transform is correct here.
	# Centered on the tile like the actor who dropped it, who stands at the
	# tile's center - a bag at the corner sat half a tile away from its owner.
	position = adapter.tile_center(server_tile.x, server_tile.y)
	_build_visual()

func set_surface_height(height: float) -> void:
	global_position.y = height + 0.22

## The reference sack: a round-bellied bag of warm tan cloth, gathered into a
## short neck, tied with a dark cord, a small puff of cloth above the knot.
## The belly is a barely squashed sphere - the shape that reads as "full bag"
## at a glance - and every part shares the one cloth material so the light
## models the folds rather than a palette.
func _build_visual() -> void:
	if get_child_count() > 0:
		return
	var cloth: StandardMaterial3D = StandardMaterial3D.new()
	cloth.albedo_color = Color(0.8, 0.55, 0.32, 1.0)
	cloth.roughness = 0.95
	var body_mesh: SphereMesh = SphereMesh.new()
	body_mesh.radius = 0.36
	body_mesh.height = 0.72
	body_mesh.radial_segments = 24
	body_mesh.rings = 12
	body_mesh.material = cloth
	var body: MeshInstance3D = MeshInstance3D.new()
	body.name = "LegacyBagFallback"
	body.mesh = body_mesh
	# Almost a full sphere: barely settled under its own weight, and sunk a
	# touch into the ground so it sits rather than floats.
	body.scale = Vector3(1.0, 0.9, 1.0)
	body.position.y = 0.08
	add_child(body)

	var neck_mesh: CylinderMesh = CylinderMesh.new()
	neck_mesh.bottom_radius = 0.16
	neck_mesh.top_radius = 0.1
	neck_mesh.height = 0.14
	neck_mesh.material = cloth
	var neck: MeshInstance3D = MeshInstance3D.new()
	neck.name = "BagNeck"
	neck.mesh = neck_mesh
	neck.position.y = 0.39
	add_child(neck)

	var cord_material: StandardMaterial3D = StandardMaterial3D.new()
	cord_material.albedo_color = Color(0.33, 0.19, 0.09, 1.0)
	cord_material.roughness = 0.9
	var cord_mesh: CylinderMesh = CylinderMesh.new()
	cord_mesh.bottom_radius = 0.115
	cord_mesh.top_radius = 0.115
	cord_mesh.height = 0.045
	cord_mesh.material = cord_material
	var cord: MeshInstance3D = MeshInstance3D.new()
	cord.name = "BagTie"
	cord.mesh = cord_mesh
	cord.position.y = 0.455
	add_child(cord)

	var puff_mesh: SphereMesh = SphereMesh.new()
	puff_mesh.radius = 0.125
	puff_mesh.height = 0.25
	puff_mesh.material = cloth
	var puff: MeshInstance3D = MeshInstance3D.new()
	puff.name = "BagPuff"
	puff.mesh = puff_mesh
	puff.scale = Vector3(1.0, 0.65, 1.0)
	puff.position.y = 0.495
	add_child(puff)

	var map_marker: MeshInstance3D = MapMarkerDisc.build(
		"BagMapMarker", MAP_MARKER_RADIUS, MAP_MARKER_COLOUR)
	map_marker.position.y = 4.0
	add_child(map_marker)

	var shape: CapsuleShape3D = CapsuleShape3D.new()
	shape.radius = 0.5
	shape.height = 0.9
	var collision: CollisionShape3D = CollisionShape3D.new()
	collision.name = "BagPickShape"
	collision.shape = shape
	add_child(collision)
