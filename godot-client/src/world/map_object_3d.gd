class_name MapObject3D
extends StaticBody3D
## A clickable world object: a harvest node or an interactive.
##
## The world package renders the prop itself as ordinary map geometry, and the
## client has no way to tell which mesh is a resource - the legacy client tried
## to match object basenames against a lowercase harvestable list and matched
## nothing, because the packs wrote relative paths. So the server states which
## object ids exist and where they are, and this places a pick target at each
## one rather than guessing from the scene.
##
## The marker is a deliberately plain, unshaded ring: it says "this is
## clickable" without pretending to be artwork for the thing underneath it,
## which the map already draws.

const PICK_LAYER := 32
## The map-marker visual layer both map cameras render, shared with ground bags.
const MAP_MARKER_LAYER := 4

var object_id: int = -1
var kind: int = 0
var server_tile: Vector2i = Vector2i.ZERO
var label: String = ""
var detail: String = ""

func configure(dto: Dictionary, adapter: CoordinateAdapter) -> void:
	object_id = int(dto.get("object_id", -1))
	kind = int(dto.get("kind", 0))
	server_tile = Vector2i(int(dto.get("x", 0)), int(dto.get("y", 0)))
	label = str(dto.get("label", ""))
	detail = str(dto.get("detail", ""))
	name = "MapObject_%d" % object_id
	collision_layer = PICK_LAYER
	collision_mask = 0
	position = adapter.server_to_godot(server_tile.x, server_tile.y)
	_build_visual()

func is_harvestable() -> bool:
	return kind == EloriaProtocol.MAP_OBJECT_HARVEST

func set_surface_height(height: float) -> void:
	global_position.y = height + 0.05

## Marks the node the player is currently harvesting.
func set_active(active: bool) -> void:
	var ring: MeshInstance3D = get_node_or_null("Ring") as MeshInstance3D
	if not is_instance_valid(ring):
		return
	var material: StandardMaterial3D = ring.material_override as StandardMaterial3D
	if material == null:
		return
	material.albedo_color = Color(1.0, 0.86, 0.36) if active else _ring_colour()

func _ring_colour() -> Color:
	# Harvest nodes and interactives are told apart by colour rather than by a
	# label the player has to read before every click.
	return (Color(0.42, 0.86, 0.44) if is_harvestable()
		else Color(0.45, 0.68, 0.95))

func _build_visual() -> void:
	if get_child_count() > 0:
		return
	var material := StandardMaterial3D.new()
	material.albedo_color = _ring_colour()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color.a = 0.75
	var ring_mesh := TorusMesh.new()
	ring_mesh.inner_radius = 0.62
	ring_mesh.outer_radius = 0.78
	ring_mesh.rings = 24
	ring_mesh.ring_segments = 8
	var ring := MeshInstance3D.new()
	ring.name = "Ring"
	ring.mesh = ring_mesh
	ring.material_override = material
	add_child(ring)

	var marker_material := StandardMaterial3D.new()
	marker_material.albedo_color = _ring_colour()
	marker_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	marker_material.no_depth_test = true
	# Sized for the map cameras, not the world: 0.6 metres was a third of a
	# pixel on the full map.
	var marker_mesh := CylinderMesh.new()
	marker_mesh.top_radius = 4.0
	marker_mesh.bottom_radius = 4.0
	marker_mesh.height = 0.08
	marker_mesh.material = marker_material
	var map_marker := MeshInstance3D.new()
	map_marker.name = "MapMarker"
	map_marker.mesh = marker_mesh
	map_marker.layers = MAP_MARKER_LAYER
	map_marker.position.y = 4.0
	add_child(map_marker)

	var shape := CylinderShape3D.new()
	shape.radius = 0.9
	shape.height = 2.2
	var collision := CollisionShape3D.new()
	collision.name = "PickShape"
	collision.shape = shape
	collision.position.y = 1.0
	add_child(collision)
