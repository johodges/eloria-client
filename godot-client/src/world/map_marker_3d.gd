class_name MapMarker3D
extends Node3D
## One server-placed map marker: a waypoint, a quest target or a tutorial
## pointer.
##
## The server owns markers entirely - it states each one with `SEND_MAP_MARKER`
## and takes it away with `REMOVE_MAP_MARKER` - so this node carries no state of
## its own and never decides that a marker has been reached. It draws on the
## map-marker layer both top-down cameras render and nothing else, because a
## marker is a navigation aid, not scenery: showing it in the gameplay view
## would put a floating pin over map artwork that already stands on its own.
##
## The label is not drawn here. A full map covers a whole map at once, so no
## text at that scale is readable; `main.gd` lists the labels in the map
## sidebar instead, where they can be read.

## The visual layer both map cameras render, shared with world objects.
const MAP_MARKER_LAYER := 4
const MARKER_COLOUR := Color(0.98, 0.78, 0.22)

var marker_id: int = -1
var server_tile: Vector2i = Vector2i.ZERO
var label: String = ""

func configure(dto: Dictionary, adapter: CoordinateAdapter) -> void:
	marker_id = int(dto.get("marker_id", -1))
	server_tile = Vector2i(int(dto.get("x", 0)), int(dto.get("y", 0)))
	label = str(dto.get("label", ""))
	name = "MapMarker_%d" % marker_id
	position = adapter.server_to_godot(server_tile.x, server_tile.y)
	_build_visual()

func set_surface_height(height: float) -> void:
	global_position.y = height

func _build_visual() -> void:
	if get_child_count() > 0:
		return
	var material := StandardMaterial3D.new()
	material.albedo_color = MARKER_COLOUR
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.no_depth_test = true
	# Sized to read on the full map, which covers a whole map at once: a pin
	# scaled for the gameplay view is a single pixel there.
	# A full map frames 1600 metres in under a thousand pixels, so 2.6 metres
	# of pin was a pixel and a half and read as nothing at all.
	var pin_mesh := CylinderMesh.new()
	pin_mesh.top_radius = 0.0
	pin_mesh.bottom_radius = 9.0
	pin_mesh.height = 6.0
	pin_mesh.radial_segments = 4
	pin_mesh.material = material
	var pin := MeshInstance3D.new()
	pin.name = "Pin"
	pin.mesh = pin_mesh
	pin.layers = MAP_MARKER_LAYER
	pin.position.y = 5.0
	add_child(pin)

