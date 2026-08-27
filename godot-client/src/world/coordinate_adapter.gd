class_name CoordinateAdapter
extends RefCounted

# The legacy protocol reports integer tile coordinates. Godot uses metres, Y-up,
# with north toward -Z. Manifest origin is the Godot-space location of server (0, 0).
var metres_per_tile: float
var origin: Vector3
var server_origin: Vector2
var walking_height: float
var invert_server_y: bool

func _init(config := {}) -> void:
	metres_per_tile = float(config.get("metresPerTile", 1.0))
	var raw_origin: Array = config.get("origin", [0.0, 0.0, 0.0])
	origin = Vector3(float(raw_origin[0]), float(raw_origin[1]), float(raw_origin[2]))
	var raw_server_origin: Array = config.get("serverOrigin", [0.0, 0.0])
	server_origin = Vector2(float(raw_server_origin[0]), float(raw_server_origin[1]))
	walking_height = float(config.get("walkingHeight", origin.y))
	invert_server_y = bool(config.get("invertServerY", true))

func server_to_godot(server_x: float, server_y: float, elevation := NAN) -> Vector3:
	var local_x := server_x - server_origin.x
	var local_y := server_y - server_origin.y
	var z := -local_y if invert_server_y else local_y
	# walkingHeight/elevation are absolute Godot Y values. Adding origin.y here
	# placed Four Gates actors and the follow camera 30 metres too high.
	var y: float = walking_height if is_nan(elevation) else elevation
	return Vector3(origin.x + local_x * metres_per_tile, y,
		origin.z + z * metres_per_tile)

func godot_to_server(position: Vector3) -> Vector2i:
	var local := position - origin
	var server_y := -local.z if invert_server_y else local.z
	return Vector2i(roundi(local.x / metres_per_tile + server_origin.x),
		roundi(server_y / metres_per_tile + server_origin.y))

func rotation_to_godot(server_rotation: int) -> float:
	# Legacy actor rotations span signed 16-bit storage; direction frames are audited separately.
	return -float(server_rotation) * TAU / 65536.0

func direction_to_godot(direction: Vector2i) -> float:
	var godot_direction: Vector3 = Vector3(
		float(direction.x), 0.0,
		-float(direction.y) if invert_server_y else float(direction.y)).normalized()
	return atan2(-godot_direction.x, -godot_direction.z)

func tile_center(server_x: int, server_y: int) -> Vector3:
	return server_to_godot(float(server_x) + 0.5, float(server_y) + 0.5)
