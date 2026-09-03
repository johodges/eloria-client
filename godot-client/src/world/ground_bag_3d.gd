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
	# Half the visual's own height, so the sack rests on the ground rather
	# than hovering over it or sinking into it.
	global_position.y = height + 0.14

func _build_visual() -> void:
	if get_child_count() > 0:
		return
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = Color(0.34, 0.19, 0.07, 1.0)
	material.roughness = 0.9
	# A dropped sack, not a boulder.  At the old 0.32 the bag stood three
	# quarters of a metre across -- two hip widths, and 40 per cent of a
	# character's height -- which read as scenery beside the person who
	# dropped it.  This is knee high on a 1.87 m body and still drawn
	# chunkier than life, the way the bags it descends from were, so it
	# stays easy to see and to click at the gameplay camera's distance.
	var bag_mesh: CapsuleMesh = CapsuleMesh.new()
	bag_mesh.radius = 0.18
	bag_mesh.height = 0.32
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
	tie_mesh.top_radius = 0.062
	tie_mesh.bottom_radius = 0.079
	tie_mesh.height = 0.057
	tie_mesh.material = tie_material
	var tie: MeshInstance3D = MeshInstance3D.new()
	tie.name = "BagTie"
	tie.mesh = tie_mesh
	tie.position.y = 0.17
	add_child(tie)

	var map_marker: MeshInstance3D = MapMarkerDisc.build(
		"BagMapMarker", MAP_MARKER_RADIUS, MAP_MARKER_COLOUR)
	map_marker.position.y = 4.0
	add_child(map_marker)

	# Deliberately roomier than the sack it picks: the shape is what a
	# player clicks, and a smaller bag should not become a harder target.
	var shape: CapsuleShape3D = CapsuleShape3D.new()
	shape.radius = 0.32
	shape.height = 0.62
	var collision: CollisionShape3D = CollisionShape3D.new()
	collision.name = "BagPickShape"
	collision.shape = shape
	add_child(collision)
