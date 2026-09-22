@tool
class_name MapAuthoringBridgeControl
extends Node3D

## One saved bridge span. Move this node to move the whole bridge, or move its
## Start and End markers to place each bank landing independently.

@export_range(1.5, 6.0, 0.1) var width := 3.0
@export_range(0.0, 2.0, 0.05) var arch := 0.6
@export_range(0.85, 2.0, 0.05) var water_clearance := 0.9
@export_range(-360.0, 360.0, 1.0, "or_less", "or_greater") var deck_texture_rotation_degrees := 0.0


func start_marker() -> Marker3D:
	return get_node_or_null("Start") as Marker3D


func end_marker() -> Marker3D:
	return get_node_or_null("End") as Marker3D


func authored_signature() -> Array:
	var start := start_marker()
	var end := end_marker()
	return [global_transform, width, arch, water_clearance,
		deck_texture_rotation_degrees,
		start.transform if start else Transform3D.IDENTITY,
		end.transform if end else Transform3D.IDENTITY]
