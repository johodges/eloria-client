class_name CoordinateAdapter
extends RefCounted

# The legacy protocol reports integer tile coordinates. Godot uses metres, Y-up,
# with north toward -Z. Manifest origin is the Godot-space location of server (0, 0).
var metres_per_tile: float
var origin: Vector3
var walking_height: float
var invert_server_y: bool

func _init(config := {}) -> void:
	metres_per_tile = float(config.get("metresPerTile", 1.0))
	var raw_origin: Array = config.get("origin", [0.0, 0.0, 0.0])
	origin = Vector3(float(raw_origin[0]), float(raw_origin[1]), float(raw_origin[2]))
	walking_height = float(config.get("walkingHeight", origin.y))
	invert_server_y = bool(config.get("invertServerY", true))

func server_to_godot(server_x: float, server_y: float, elevation := NAN) -> Vector3:
	var z := -server_y if invert_server_y else server_y
	var y := walking_height if is_nan(elevation) else elevation
	return origin + Vector3(server_x * metres_per_tile, y, z * metres_per_tile)

func godot_to_server(position: Vector3) -> Vector2i:
	var local := position - origin
	var server_y := -local.z if invert_server_y else local.z
	return Vector2i(roundi(local.x / metres_per_tile), roundi(server_y / metres_per_tile))

func rotation_to_godot(server_rotation: int) -> float:
	# Legacy actor rotations span signed 16-bit storage; direction frames are audited separately.
	return -float(server_rotation) * TAU / 65536.0

func tile_center(server_x: int, server_y: int) -> Vector3:
	return server_to_godot(float(server_x) + 0.5, float(server_y) + 0.5)
