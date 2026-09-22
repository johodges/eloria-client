@tool
class_name MapAuthoringPilot
extends Node3D

## A deliberately small, code-first map authoring example. Authored controls live
## under AuthoredControls and are saved in the scene. Everything below
## GeneratedPreview is disposable and is rebuilt from those controls.

const MAP_METRES := 48.0
const HALF_CELL := 0.5
const HALF_CELLS := 96
const SERVER_CELLS := 48
const HEIGHT_STEP := 0.2
const WALKER_SPEED := 5.0
const WATER_HALF_WIDTH := 3.0

@export_category("Terrain")
@export_range(0.0, 2.0, 0.05) var terrain_relief := 0.8
@export_range(-1.0, 3.0, 0.05) var terrain_base_height := 1.4
@export_range(-1.0, 3.0, 0.05) var water_level := 0.35

@export_category("Road and bridge")
@export_range(1.0, 6.0, 0.1) var road_width := 2.5
@export_range(1.5, 6.0, 0.1) var bridge_width := 3.0
@export_range(0.0, 2.0, 0.05) var bridge_arch := 0.6
@export_range(0.85, 2.0, 0.05) var bridge_water_clearance := 0.9

@export_category("Preview")
@export var show_walkability := false
@export_enum("All", "Terrain", "Road", "Bridge", "Building", "Walkability") var refresh_scope := "All"
@export_dir var export_directory := "user://map_authoring_pilot/export"
@export_tool_button("Refresh selected feature", "Callable") var refresh_selected_action := refresh_selected
@export_tool_button("Export EWCG + JSON", "Callable") var export_action := export_contract

@onready var authored: Node3D = get_node_or_null("AuthoredControls")
@onready var road: Path3D = get_node_or_null("AuthoredControls/Road")
@onready var bridge_start: Marker3D = get_node_or_null("AuthoredControls/BridgeStart")
@onready var bridge_end: Marker3D = get_node_or_null("AuthoredControls/BridgeEnd")
@onready var building_control: Node3D = get_node_or_null("AuthoredControls/Building")
@onready var entrance: Marker3D = get_node_or_null("AuthoredControls/Building/Entrance")
@onready var spawn_marker: Marker3D = get_node_or_null("AuthoredControls/Spawn")
@onready var generated: Node3D = get_node_or_null("GeneratedPreview")

var _half_grid := PackedByteArray()
var _server_grid := PackedByteArray()
var _last_signatures: Dictionary = {}
var _editor_debounce := 0.0
var _walker: MeshInstance3D
var _walker_tile := Vector2i.ZERO
var _walk_route: Array[Vector2i] = []
var _walk_route_index := 0
var _walking := false
var _status: Label


func _ready() -> void:
	set_process(true)
	set_process_input(not Engine.is_editor_hint())
	refresh_all()
	if Engine.is_editor_hint():
		print("map authoring pilot editor preview: generated")
	if not Engine.is_editor_hint():
		_setup_runtime()


func _process(delta: float) -> void:
	if Engine.is_editor_hint():
		_editor_debounce += delta
		if _editor_debounce >= 0.18:
			_editor_debounce = 0.0
			_detect_authored_changes()
		return
	if _walking:
		_advance_walker(delta)


func refresh_selected() -> void:
	_regenerate(refresh_scope)


func refresh_all() -> void:
	_regenerate("All")


func export_contract() -> void:
	_build_walk_grids()
	var absolute := ProjectSettings.globalize_path(export_directory)
	var error := DirAccess.make_dir_recursive_absolute(absolute)
	if error != OK:
		push_error("Map authoring pilot: cannot create export directory %s" % absolute)
		return
	var binary_path := absolute.path_join("collision.bin")
	var binary := FileAccess.open(binary_path, FileAccess.WRITE)
	if binary == null:
		push_error("Map authoring pilot: cannot write %s" % binary_path)
		return
	binary.store_buffer("EWCG".to_ascii_buffer())
	binary.store_16(2)
	binary.store_16(0)
	binary.store_32(HALF_CELLS)
	binary.store_32(HALF_CELLS)
	binary.store_buffer(_half_grid)
	binary.close()
	var document := {
		"schemaVersion": "1.0.0",
		"asset": {"id": "map-authoring-pilot", "name": "Map Authoring Pilot"},
		"coordinateTransform": {
			"metresPerTile": 1.0,
			"serverOrigin": [0, 0],
			"serverCells": [SERVER_CELLS, SERVER_CELLS],
			"origin": [-24.0, 0.0, 24.0],
			"invertServerY": true,
		},
		"collision": {
			"binary": "collision.bin",
			"format": "EWCG-v2",
			"formatVersion": 2,
			"cellSize": HALF_CELL,
			"gridAlignment": "tile-centres-v1",
			"heightEncoding": {"origin": 0.0, "step": HEIGHT_STEP},
		},
		"validation": _validation_probes(),
	}
	var json_path := absolute.path_join("world.json")
	var json_file := FileAccess.open(json_path, FileAccess.WRITE)
	if json_file == null:
		push_error("Map authoring pilot: cannot write %s" % json_path)
		return
	json_file.store_string(JSON.stringify(document, "  ") + "\n")
	json_file.close()
	_set_status("Exported collision.bin + world.json\n%s" % absolute)
	print("map authoring pilot export: ", absolute)


func server_grid() -> PackedByteArray:
	_build_walk_grids()
	return _server_grid.duplicate()


func authored_snapshot() -> Dictionary:
	return {
		"road": _curve_signature(),
		"bridge_start": bridge_start.transform if bridge_start else Transform3D.IDENTITY,
		"bridge_end": bridge_end.transform if bridge_end else Transform3D.IDENTITY,
		"building": building_control.transform if building_control else Transform3D.IDENTITY,
		"entrance": entrance.transform if entrance else Transform3D.IDENTITY,
	}


func validation_route() -> Array[Vector2i]:
	_build_walk_grids()
	if spawn_marker == null or entrance == null:
		return []
	return _find_route(_world_to_server(spawn_marker.global_position),
		_world_to_server(entrance.global_position))


func _regenerate(scope: String) -> void:
	if not is_inside_tree():
		return
	_cache_nodes()
	if generated == null or road == null or road.curve == null:
		return
	_build_walk_grids()
	if scope in ["All", "Terrain"]:
		_replace_feature("Terrain", _build_terrain)
		_replace_feature("Water", _build_water)
	if scope in ["All", "Road", "Bridge"]:
		_replace_feature("Road", _build_road)
	if scope in ["All", "Bridge"]:
		_replace_feature("Bridge", _build_bridge)
	if scope in ["All", "Building"]:
		_replace_feature("Building", _build_building)
	_replace_feature("Walkability", _build_walkability)
	_last_signatures = _signatures()
	_set_status("Preview refreshed: %s" % scope)


func _cache_nodes() -> void:
	authored = get_node_or_null("AuthoredControls")
	road = get_node_or_null("AuthoredControls/Road")
	bridge_start = get_node_or_null("AuthoredControls/BridgeStart")
	bridge_end = get_node_or_null("AuthoredControls/BridgeEnd")
	building_control = get_node_or_null("AuthoredControls/Building")
	entrance = get_node_or_null("AuthoredControls/Building/Entrance")
	spawn_marker = get_node_or_null("AuthoredControls/Spawn")
	generated = get_node_or_null("GeneratedPreview")


func _replace_feature(feature_name: String, builder: Callable) -> void:
	var old := generated.get_node_or_null(feature_name)
	if old != null:
		old.free()
	var feature := Node3D.new()
	feature.name = feature_name
	generated.add_child(feature)
	# Deliberately omit owner: generated preview children never become scene data.
	builder.call(feature)


func _detect_authored_changes() -> void:
	_cache_nodes()
	if road == null or generated == null:
		return
	var current := _signatures()
	if _last_signatures.is_empty():
		_regenerate("All")
		return
	var changed: Array[String] = []
	if current.params != _last_signatures.params:
		changed.append("All")
	if current.road != _last_signatures.road:
		changed.append("Road")
	if current.bridge != _last_signatures.bridge:
		changed.append("Bridge")
	if current.building != _last_signatures.building or current.markers != _last_signatures.markers:
		changed.append("Building")
	if changed.is_empty():
		return
	if changed.size() > 1 or changed[0] == "All":
		_regenerate("All")
	else:
		_regenerate(changed[0])


func _signatures() -> Dictionary:
	return {
		"params": [terrain_relief, terrain_base_height, water_level, road_width,
			bridge_width, bridge_arch, bridge_water_clearance, show_walkability].hash(),
		"road": _curve_signature(),
		"bridge": [bridge_start.transform if bridge_start else Transform3D.IDENTITY,
			bridge_end.transform if bridge_end else Transform3D.IDENTITY].hash(),
		"building": str(building_control.transform).hash() if building_control else 0,
		"markers": [entrance.transform if entrance else Transform3D.IDENTITY,
			spawn_marker.transform if spawn_marker else Transform3D.IDENTITY].hash(),
	}


func _curve_signature() -> Array:
	var result: Array = []
	if road == null or road.curve == null:
		return result
	result.append(road.transform)
	for index in road.curve.point_count:
		result.append(road.curve.get_point_position(index))
		result.append(road.curve.get_point_in(index))
		result.append(road.curve.get_point_out(index))
	return result


func _build_walk_grids() -> void:
	_half_grid.resize(HALF_CELLS * HALF_CELLS)
	for cell_y in HALF_CELLS:
		for cell_x in HALF_CELLS:
			var world := _half_cell_world(cell_x, cell_y)
			_half_grid[cell_y * HALF_CELLS + cell_x] = _encoded_floor(world.x, world.z)
	_server_grid.resize(SERVER_CELLS * SERVER_CELLS)
	for tile_y in SERVER_CELLS:
		for tile_x in SERVER_CELLS:
			var folded := 0
			for oy in 2:
				for ox in 2:
					var value := int(_half_grid[(tile_y * 2 + oy) * HALF_CELLS + tile_x * 2 + ox])
					if value == 0:
						folded = 0
						break
					folded = maxi(folded, value)
				if folded == 0:
					break
			_server_grid[tile_y * SERVER_CELLS + tile_x] = folded


func _encoded_floor(x: float, z: float) -> int:
	if _inside_bridge(x, z):
		return _encode_height(_bridge_height(x, z))
	if absf(x) <= WATER_HALF_WIDTH:
		return 0
	if _inside_building(x, z):
		return 0
	return _encode_height(_terrain_height(x, z))


func _encode_height(height: float) -> int:
	return clampi(roundi(height / HEIGHT_STEP), 1, 63)


func _decoded_height(value: int) -> float:
	return float(value) * HEIGHT_STEP


func _terrain_height(x: float, z: float) -> float:
	var broad := 0.55 * sin(x * 0.12) * cos(z * 0.10)
	var detail := 0.25 * sin((x + z) * 0.24)
	var river_bank := 0.45 * smoothstep(0.0, 7.0, absf(x))
	# The bounded cut makes the water visible and leaves the bridge anchors on
	# dry banks. It is visual terrain and the source of the exported heights.
	var river_cut := 1.45 * (1.0 - smoothstep(2.6, 5.5, absf(x)))
	return maxf(0.2, terrain_base_height + terrain_relief * (broad + detail) + river_bank - river_cut)


func _bridge_basis() -> Dictionary:
	if bridge_start == null or bridge_end == null:
		return {"a": Vector2(-4.0, 0.0), "b": Vector2(4.0, 0.0), "delta": Vector2(8.0, 0.0), "length": 8.0}
	var a := Vector2(bridge_start.global_position.x, bridge_start.global_position.z)
	var b := Vector2(bridge_end.global_position.x, bridge_end.global_position.z)
	return {"a": a, "b": b, "delta": b - a, "length": maxf(a.distance_to(b), 0.01)}


func _bridge_projection(x: float, z: float) -> Dictionary:
	var basis := _bridge_basis()
	var point := Vector2(x, z)
	var t: float = clampf((point - basis.a).dot(basis.delta) /
		maxf(basis.delta.length_squared(), 0.0001), 0.0, 1.0)
	var nearest: Vector2 = basis.a + basis.delta * t
	return {"t": t, "distance": point.distance_to(nearest)}


func _inside_bridge(x: float, z: float) -> bool:
	var projected := _bridge_projection(x, z)
	return projected.distance <= bridge_width * 0.5 and projected.t > 0.0 and projected.t < 1.0


func _bridge_height(x: float, z: float) -> float:
	var projected := _bridge_projection(x, z)
	var t: float = projected.t
	var basis := _bridge_basis()
	# Marker Y is an authored height offset above its bank, not discarded data.
	var a_height := _terrain_height(basis.a.x, basis.a.y) + (bridge_start.global_position.y if bridge_start else 0.0)
	var b_height := _terrain_height(basis.b.x, basis.b.y) + (bridge_end.global_position.y if bridge_end else 0.0)
	var plateau := 1.0
	if t < 0.3:
		plateau = smoothstep(0.0, 0.3, t)
	elif t > 0.7:
		plateau = smoothstep(1.0, 0.7, t)
	var base := lerpf(a_height, b_height, t)
	return maxf(base + bridge_arch * plateau, water_level + bridge_water_clearance)


func _inside_building(x: float, z: float) -> bool:
	if building_control == null:
		return false
	var local := building_control.global_transform.affine_inverse() * Vector3(x, 0.0, z)
	if absf(local.x) > 3.5 or absf(local.z) > 2.5:
		return false
	# A thin open-front cabin: the interior and centred doorway remain walkable.
	var back_wall := local.x >= 3.0
	var side_walls := absf(local.z) >= 2.0
	var front_wall := local.x <= -3.0 and absf(local.z) >= 1.0
	return back_wall or side_walls or front_wall


func _build_terrain(parent: Node3D) -> void:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var step := 1.0
	for row in int(MAP_METRES):
		for column in int(MAP_METRES):
			var x0 := -MAP_METRES * 0.5 + float(column) * step
			var z0 := -MAP_METRES * 0.5 + float(row) * step
			var x1 := x0 + step
			var z1 := z0 + step
			var a := Vector3(x0, _decoded_height(_encode_height(_terrain_height(x0, z0))), z0)
			var b := Vector3(x1, _decoded_height(_encode_height(_terrain_height(x1, z0))), z0)
			var c := Vector3(x1, _decoded_height(_encode_height(_terrain_height(x1, z1))), z1)
			var d := Vector3(x0, _decoded_height(_encode_height(_terrain_height(x0, z1))), z1)
			for vertex in [a, c, b, a, d, c]:
				surface.set_uv(Vector2((vertex.x + 24.0) / 48.0, (vertex.z + 24.0) / 48.0))
				surface.add_vertex(vertex)
	surface.generate_normals()
	var mesh := surface.commit()
	_add_mesh(parent, "TerrainMesh", mesh, _material(Color("#648052"), 0.92))
	var body := StaticBody3D.new()
	body.name = "TerrainCollision"
	var collision := CollisionShape3D.new()
	var shape := ConcavePolygonShape3D.new()
	shape.set_faces(mesh.get_faces())
	collision.shape = shape
	body.add_child(collision)
	parent.add_child(body)


func _build_water(parent: Node3D) -> void:
	var mesh := BoxMesh.new()
	mesh.size = Vector3(WATER_HALF_WIDTH * 2.0, 0.08, MAP_METRES)
	var node := _add_mesh(parent, "River", mesh, _material(Color(0.12, 0.48, 0.68, 0.78), 0.2))
	node.position.y = water_level - 0.04


func _build_road(parent: Node3D) -> void:
	var points := _road_samples()
	if points.size() < 2:
		return
	var cross_sections: Array[Array] = []
	var lateral_steps := 6
	for index in points.size():
		var previous: Vector3 = points[maxi(0, index - 1)]
		var following: Vector3 = points[mini(points.size() - 1, index + 1)]
		var direction := Vector2(following.x - previous.x, following.z - previous.z).normalized()
		var normal := Vector2(-direction.y, direction.x)
		var point: Vector3 = points[index]
		var section: Array[Vector3] = []
		for lateral_index in lateral_steps + 1:
			var lateral := road_width * (0.5 - float(lateral_index) / float(lateral_steps))
			var x := point.x + normal.x * lateral
			var z := point.z + normal.y * lateral
			section.append(Vector3(x, _road_height(x, z), z))
		cross_sections.append(section)
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for index in points.size() - 1:
		for lateral_index in lateral_steps:
			var vertices := [cross_sections[index][lateral_index],
				cross_sections[index][lateral_index + 1],
				cross_sections[index + 1][lateral_index + 1],
				cross_sections[index + 1][lateral_index]]
			for vertex in [vertices[0], vertices[2], vertices[1], vertices[0], vertices[3], vertices[2]]:
				surface.add_vertex(vertex)
	surface.generate_normals()
	_add_mesh(parent, "RoadSurface", surface.commit(), _material(Color("#8d7958"), 0.95))


func _road_height(x: float, z: float) -> float:
	if _inside_bridge(x, z):
		return _bridge_height(x, z) + 0.035
	return _rendered_terrain_height(x, z) + 0.055


func _rendered_terrain_height(x: float, z: float) -> float:
	# Match the two triangles emitted by `_build_terrain`. Sampling the scalar
	# height function here can cut a road corner through their planar surface.
	var x0 := clampf(floorf(x), -MAP_METRES * 0.5, MAP_METRES * 0.5 - 1.0)
	var z0 := clampf(floorf(z), -MAP_METRES * 0.5, MAP_METRES * 0.5 - 1.0)
	var u := clampf(x - x0, 0.0, 1.0)
	var v := clampf(z - z0, 0.0, 1.0)
	var a := _decoded_height(_encode_height(_terrain_height(x0, z0)))
	var b := _decoded_height(_encode_height(_terrain_height(x0 + 1.0, z0)))
	var c := _decoded_height(_encode_height(_terrain_height(x0 + 1.0, z0 + 1.0)))
	var d := _decoded_height(_encode_height(_terrain_height(x0, z0 + 1.0)))
	if u >= v:
		return a + (b - a) * u + (c - b) * v
	return a + (d - a) * v + (c - d) * u


func _road_samples() -> Array[Vector3]:
	var points: Array[Vector3] = []
	var length := road.curve.get_baked_length()
	var count := maxi(2, ceili(length / 0.35) + 1)
	for index in count:
		var local := road.curve.sample_baked(length * float(index) / float(count - 1), true)
		points.append(road.global_transform * local)
	return points


func _build_bridge(parent: Node3D) -> void:
	var basis := _bridge_basis()
	var direction: Vector2 = basis.delta.normalized()
	var normal := Vector2(-direction.y, direction.x) * bridge_width * 0.5
	var segments := 20
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for index in segments:
		var t0 := float(index) / float(segments)
		var t1 := float(index + 1) / float(segments)
		var p0: Vector2 = basis.a.lerp(basis.b, t0)
		var p1: Vector2 = basis.a.lerp(basis.b, t1)
		var y0 := _bridge_height(p0.x, p0.y) + 0.06
		var y1 := _bridge_height(p1.x, p1.y) + 0.06
		var vertices := [Vector3(p0.x + normal.x, y0, p0.y + normal.y),
			Vector3(p0.x - normal.x, y0, p0.y - normal.y),
			Vector3(p1.x - normal.x, y1, p1.y - normal.y),
			Vector3(p1.x + normal.x, y1, p1.y + normal.y)]
		for vertex in [vertices[0], vertices[2], vertices[1], vertices[0], vertices[3], vertices[2]]:
			surface.add_vertex(vertex)
	surface.generate_normals()
	_add_mesh(parent, "BridgeDeck", surface.commit(), _material(Color("#b08a58"), 0.86))
	for point: Vector2 in [basis.a, basis.b]:
		var pier := BoxMesh.new()
		var top := _bridge_height(point.x, point.y)
		pier.size = Vector3(0.45, maxf(0.2, top - water_level), bridge_width + 0.6)
		var node := _add_mesh(parent, "BridgeSupport", pier, _material(Color("#625243"), 1.0))
		node.position = Vector3(point.x, water_level + pier.size.y * 0.5, point.y)
		node.rotation.y = -direction.angle()


func _build_building(parent: Node3D) -> void:
	if building_control == null or entrance == null:
		return
	var centre := building_control.global_position
	var floor := _decoded_height(_encode_height(_terrain_height(centre.x, centre.z)))
	var wall_material := _material(Color("#9d876d"), 0.9)
	# Four wall groups form a readable open-front cabin. The gap in the front
	# wall is the same gap `_inside_building` leaves open in the walk grid.
	_add_building_box(parent, "BackWall", Vector3(0.5, 4.0, 5.0),
		Vector3(3.25, 2.0, 0.0), floor, wall_material)
	_add_building_box(parent, "LeftWall", Vector3(6.0, 4.0, 0.5),
		Vector3(0.0, 2.0, -2.25), floor, wall_material)
	_add_building_box(parent, "RightWall", Vector3(6.0, 4.0, 0.5),
		Vector3(0.0, 2.0, 2.25), floor, wall_material)
	_add_building_box(parent, "FrontWallLeft", Vector3(0.5, 4.0, 1.5),
		Vector3(-3.25, 2.0, -1.75), floor, wall_material)
	_add_building_box(parent, "FrontWallRight", Vector3(0.5, 4.0, 1.5),
		Vector3(-3.25, 2.0, 1.75), floor, wall_material)
	var roof := PrismMesh.new()
	roof.size = Vector3(7.8, 2.0, 5.8)
	var roof_node := _add_mesh(parent, "Roof", roof, _material(Color("#5c3f35"), 1.0))
	roof_node.transform = building_control.global_transform
	roof_node.position += Vector3(0.0, floor + 4.8, 0.0)
	var door_mat := _material(Color("#3b251c"), 1.0)
	for offset in [-1.0, 1.0]:
		var post := BoxMesh.new()
		post.size = Vector3(0.35, 2.6, 0.4)
		var post_node := _add_mesh(parent, "EntrancePost", post, door_mat)
		post_node.global_transform = entrance.global_transform.translated_local(Vector3(0.0, floor + 1.3, offset * 0.8))
	var lintel := BoxMesh.new()
	lintel.size = Vector3(0.4, 0.35, 1.95)
	var lintel_node := _add_mesh(parent, "EntranceLintel", lintel, door_mat)
	lintel_node.global_transform = entrance.global_transform.translated_local(Vector3(0.0, floor + 2.55, 0.0))


func _add_building_box(parent: Node3D, box_name: String, size: Vector3,
		local_position: Vector3, floor: float, material: Material) -> void:
	var mesh := BoxMesh.new()
	mesh.size = size
	var node := _add_mesh(parent, box_name, mesh, material)
	node.global_transform = building_control.global_transform.translated_local(
		local_position + Vector3(0.0, floor, 0.0))


func _build_walkability(parent: Node3D) -> void:
	parent.visible = show_walkability
	var reachable := _server_reachable()
	var open_surface := SurfaceTool.new()
	var blocked_surface := SurfaceTool.new()
	open_surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	blocked_surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for y in SERVER_CELLS:
		for x in SERVER_CELLS:
			var value := int(_server_grid[y * SERVER_CELLS + x])
			var connected := reachable.has(Vector2i(x, y))
			var surface := open_surface if value and connected else blocked_surface
			var world := _server_tile_world(x, y)
			var height := _decoded_height(value) + 0.09 if value else maxf(
				water_level + 0.11, _terrain_height(world.x, world.z) + 0.09)
			var extent := 0.43
			var a := Vector3(world.x - extent, height, world.z - extent)
			var b := Vector3(world.x + extent, height, world.z - extent)
			var c := Vector3(world.x + extent, height, world.z + extent)
			var d := Vector3(world.x - extent, height, world.z + extent)
			for vertex in [a, c, b, a, d, c]:
				surface.add_vertex(vertex)
	_add_mesh(parent, "WalkableServerTiles", open_surface.commit(),
		_material(Color(0.15, 0.95, 0.35, 0.34), 0.15, true))
	_add_mesh(parent, "BlockedServerTiles", blocked_surface.commit(),
		_material(Color(0.95, 0.12, 0.12, 0.43), 0.15, true))


func _add_mesh(parent: Node3D, node_name: String, mesh: Mesh,
		material: Material) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = node_name
	node.mesh = mesh
	node.material_override = material
	parent.add_child(node)
	return node


func _material(color: Color, roughness: float, overlay := false) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = roughness
	# Generated surfaces are authoring previews and remain readable from either
	# side while their control points are being moved through the viewport.
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	if color.a < 0.99:
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if overlay:
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.no_depth_test = true
	return material


func _setup_runtime() -> void:
	_status = get_node_or_null("UI/Margin/Panel/VBox/Status")
	var start: Button = get_node_or_null("UI/Margin/Panel/VBox/Buttons/Start")
	var reset: Button = get_node_or_null("UI/Margin/Panel/VBox/Buttons/Reset")
	var overlay: Button = get_node_or_null("UI/Margin/Panel/VBox/Buttons/Overlay")
	if start:
		start.pressed.connect(start_walk)
	if reset:
		reset.pressed.connect(reset_walk)
	if overlay:
		overlay.pressed.connect(toggle_overlay)
	_walker = MeshInstance3D.new()
	_walker.name = "LocalWalker"
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.35
	capsule.height = 1.7
	_walker.mesh = capsule
	_walker.material_override = _material(Color("#f4c95d"), 0.8)
	add_child(_walker)
	reset_walk()


func start_walk() -> void:
	_walking = false
	_walker_tile = _world_to_server(spawn_marker.global_position)
	_place_walker(_walker_tile)
	_walk_route = validation_route()
	_walk_route_index = 0
	_walking = _walk_route.size() > 1
	_set_status("Walking shared 1 m server grid (%d tiles)" % _walk_route.size()
		if _walking else "No legal route to entrance")


func reset_walk() -> void:
	_build_walk_grids()
	_walking = false
	_walk_route.clear()
	_walk_route_index = 0
	_walker_tile = _world_to_server(spawn_marker.global_position)
	_place_walker(_walker_tile)
	_set_status("Ready. Start: Enter/button  Reset: R  Overlay: V")


func toggle_overlay() -> void:
	show_walkability = not show_walkability
	var overlay := generated.get_node_or_null("Walkability")
	if overlay:
		overlay.visible = show_walkability
	_set_status("Walkability overlay %s" % ("shown" if show_walkability else "hidden"))


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_ENTER:
				start_walk()
			KEY_R:
				reset_walk()
			KEY_V:
				toggle_overlay()


func _advance_walker(delta: float) -> void:
	if _walk_route_index >= _walk_route.size() - 1:
		_walking = false
		_set_status("ARRIVED at entrance on exported server grid")
		return
	var next_tile := _walk_route[_walk_route_index + 1]
	var target := _server_tile_world(next_tile.x, next_tile.y)
	var value := int(_server_grid[next_tile.y * SERVER_CELLS + next_tile.x])
	target.y = _decoded_height(value) + 0.85
	_walker.position = _walker.position.move_toward(target, WALKER_SPEED * delta)
	if _walker.position.distance_to(target) < 0.03:
		_walker_tile = next_tile
		_walk_route_index += 1


func _place_walker(tile: Vector2i) -> void:
	if _walker == null:
		return
	var value := int(_server_grid[tile.y * SERVER_CELLS + tile.x])
	var point := _server_tile_world(tile.x, tile.y)
	point.y = _decoded_height(value) + 0.85
	_walker.position = point


func _find_route(start: Vector2i, goal: Vector2i) -> Array[Vector2i]:
	if not _server_open(start) or not _server_open(goal):
		return []
	var frontier: Array[Vector2i] = [start]
	var parent := {start: Vector2i(-999, -999)}
	var directions := [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
	while not frontier.is_empty():
		var here: Vector2i = frontier.pop_front() as Vector2i
		if here == goal:
			break
		for direction: Vector2i in directions:
			var there: Vector2i = here + direction
			if parent.has(there) or not _server_step_allowed(here, there):
				continue
			parent[there] = here
			frontier.append(there)
	if not parent.has(goal):
		return []
	var route: Array[Vector2i] = []
	var cursor := goal
	while cursor != Vector2i(-999, -999):
		route.push_front(cursor)
		cursor = parent[cursor]
	return route


func _server_reachable() -> Dictionary:
	var result := {}
	if spawn_marker == null:
		return result
	var start := _world_to_server(spawn_marker.global_position)
	if not _server_open(start):
		return result
	var frontier: Array[Vector2i] = [start]
	result[start] = true
	var directions: Array[Vector2i] = [Vector2i(1, 0), Vector2i(-1, 0),
		Vector2i(0, 1), Vector2i(0, -1)]
	while not frontier.is_empty():
		var here: Vector2i = frontier.pop_front() as Vector2i
		for direction: Vector2i in directions:
			var there := here + direction
			if result.has(there) or not _server_step_allowed(here, there):
				continue
			result[there] = true
			frontier.append(there)
	return result


func _server_open(tile: Vector2i) -> bool:
	return tile.x >= 0 and tile.y >= 0 and tile.x < SERVER_CELLS and tile.y < SERVER_CELLS \
		and int(_server_grid[tile.y * SERVER_CELLS + tile.x]) > 0


func _server_step_allowed(a: Vector2i, b: Vector2i) -> bool:
	if not _server_open(a) or not _server_open(b):
		return false
	return absi(int(_server_grid[a.y * SERVER_CELLS + a.x]) -
		int(_server_grid[b.y * SERVER_CELLS + b.x])) <= 2


func _half_cell_world(x: int, y: int) -> Vector3:
	return Vector3(-24.0 + (float(x) + 0.5) * HALF_CELL, 0.0,
		24.0 - (float(y) + 0.5) * HALF_CELL)


func _server_tile_world(x: int, y: int) -> Vector3:
	return Vector3(-24.0 + float(x) + 0.5, 0.0, 24.0 - float(y) - 0.5)


func _world_to_server(point: Vector3) -> Vector2i:
	return Vector2i(clampi(floori(point.x + 24.0), 0, SERVER_CELLS - 1),
		clampi(floori(24.0 - point.z), 0, SERVER_CELLS - 1))


func _validation_probes() -> Dictionary:
	var basis := _bridge_basis()
	var bridge_mid: Vector2 = basis.a.lerp(basis.b, 0.5)
	var bridge_side := bridge_mid + Vector2(0.0, bridge_width * 0.5 + 1.0)
	var solid_wall := building_control.global_transform * Vector3(3.25, 0.0, 0.0)
	return {
		"spawn": _tile_array(_world_to_server(spawn_marker.global_position)),
		"roadWaypoint": _tile_array(_world_to_server(road.global_transform * road.curve.sample_baked(road.curve.get_baked_length() * 0.25))),
		"bridgeEntry": _tile_array(_world_to_server(Vector3(basis.a.x, 0.0, basis.a.y))),
		"bridgeDeck": _tile_array(_world_to_server(Vector3(bridge_mid.x, 0.0, bridge_mid.y))),
		"bridgeExit": _tile_array(_world_to_server(Vector3(basis.b.x, 0.0, basis.b.y))),
		"entrance": _tile_array(_world_to_server(entrance.global_position)),
		"waterProbe": _tile_array(_world_to_server(Vector3(0.0, 0.0, 16.0))),
		"solidProbe": _tile_array(_world_to_server(solid_wall)),
		"besideBridgeProbe": _tile_array(_world_to_server(Vector3(bridge_side.x, 0.0, bridge_side.y))),
	}


func _tile_array(tile: Vector2i) -> Array[int]:
	return [tile.x, tile.y]


func _set_status(message: String) -> void:
	if _status == null:
		_status = get_node_or_null("UI/Margin/Panel/VBox/Status")
	if _status:
		_status.text = message
