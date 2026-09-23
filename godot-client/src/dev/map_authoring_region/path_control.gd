@tool
class_name MapAuthoringRegionPath
extends "res://src/dev/map_authoring_pilot/width_path.gd"

@export var path_id := ""
@export_enum("road", "river") var kind := "road"
@export_enum("required", "decorative") var routing_role := "required"
@export var replaces_route_id := ""
@export var replaces_plan_feature_id := ""
@export var properties: Dictionary = {}
@export_range(0.1, 8.0, 0.1) var snapshot_spacing := 1.0
@export var preview_enabled := true

const LATERAL_STEPS := 6

var _preview_signature: Array = []
var _preview_elapsed := 0.0


func _ready() -> void:
	super._ready()
	set_process(true)
	_refresh_preview()


func sync_surface_binding() -> void:
	super.sync_surface_binding()
	if surface != null:
		surface.enable_region_uv_projection()


func _process(delta: float) -> void:
	super._process(delta)
	if not Engine.is_editor_hint():
		return
	_preview_elapsed += delta
	if _preview_elapsed < 0.18:
		return
	_preview_elapsed = 0.0
	var current := _current_preview_signature()
	if current != _preview_signature:
		_refresh_preview()


func snapshot_points() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	if curve == null or curve.point_count == 0:
		return result
	var total := curve.get_baked_length()
	if total <= 0.000001:
		var only := curve.get_point_position(0)
		result.append({"position": [only.x, only.y, only.z],
			"width": width_at_offset(0.0)})
		return result
	var count := maxi(1, ceili(total / maxf(snapshot_spacing, 0.1)))
	var anchor_offsets := width_sample_offsets()
	var offsets := PackedFloat32Array()
	for index in count + 1:
		offsets.append(total * float(index) / float(count))
	for offset in anchor_offsets:
		offsets.append(offset)
	offsets.sort()
	var previous := -INF
	for offset in offsets:
		if offset <= previous + 0.00001:
			continue
		previous = offset
		var point := curve.sample_baked(offset, true)
		for anchor_index in anchor_offsets.size():
			if absf(offset - anchor_offsets[anchor_index]) <= 0.00001:
				point = curve.get_point_position(anchor_index)
				break
		result.append({"position": [point.x, point.y, point.z],
			"width": width_at_offset(offset)})
	return result


func replacement_route_value() -> Variant:
	return null if replaces_route_id.strip_edges().is_empty() else replaces_route_id


func replacement_plan_feature_value() -> Variant:
	return null if replaces_plan_feature_id.strip_edges().is_empty() \
		else replaces_plan_feature_id


func _refresh_preview() -> void:
	_preview_signature = _current_preview_signature()
	var mesh_instance := get_node_or_null("__PathPreview") as MeshInstance3D
	if not preview_enabled or curve == null or curve.point_count < 2:
		if mesh_instance != null:
			mesh_instance.mesh = null
		return
	if mesh_instance == null:
		mesh_instance = MeshInstance3D.new()
		mesh_instance.name = "__PathPreview"
		mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mesh_instance)
	var points := snapshot_points()
	var source_vertices := PackedVector3Array()
	var source_uvs := PackedVector2Array()
	var source_uv2s := PackedVector2Array()
	var wet_scalars := PackedFloat32Array()
	var along := 0.0
	for index in points.size():
		var raw: Array = points[index].position
		var point := Vector3(float(raw[0]), float(raw[1]), float(raw[2]))
		var previous := point if index == 0 else _point_vector(points[index - 1])
		var following := point if index == points.size() - 1 else _point_vector(points[index + 1])
		var tangent := Vector2(following.x - previous.x, following.z - previous.z).normalized()
		if tangent.length_squared() <= 0.000001:
			tangent = Vector2.RIGHT
		var side := Vector2(-tangent.y, tangent.x)
		var half := float(points[index].width) * 0.5
		if index > 0:
			along += point.distance_to(_point_vector(points[index - 1]))
		for lateral_index in LATERAL_STEPS + 1:
			var lateral_amount := float(lateral_index) / float(LATERAL_STEPS)
			var offset := lerpf(half, -half, lateral_amount)
			var authored_vertex := point + Vector3(side.x * offset, 0.0,
				side.y * offset)
			source_vertices.append(_preview_vertex(authored_vertex))
			source_uvs.append(Vector2(lateral_amount * half * 2.0, along))
			source_uv2s.append(Vector2(lateral_amount, half))
			wet_scalars.append(minf(half - absf(offset),
				_hydraulic_clearance(authored_vertex)))
	var vertices := PackedVector3Array()
	var uvs := PackedVector2Array()
	var uv2s := PackedVector2Array()
	var indices := PackedInt32Array()
	if kind == "river":
		for station in points.size() - 1:
			for lateral_index in LATERAL_STEPS:
				var first := station * (LATERAL_STEPS + 1) + lateral_index
				var next := first + LATERAL_STEPS + 1
				_append_clipped_water_triangle([first, next, first + 1],
					source_vertices, source_uvs, source_uv2s, wet_scalars,
					vertices, uvs, uv2s, indices)
				_append_clipped_water_triangle([first + 1, next, next + 1],
					source_vertices, source_uvs, source_uv2s, wet_scalars,
					vertices, uvs, uv2s, indices)
	else:
		vertices = source_vertices
		uvs = source_uvs
		uv2s = source_uv2s
		for station in points.size() - 1:
			for lateral_index in LATERAL_STEPS:
				var first := station * (LATERAL_STEPS + 1) + lateral_index
				var next := first + LATERAL_STEPS + 1
				indices.append_array(PackedInt32Array([first, next, first + 1,
					first + 1, next, next + 1]))
	if indices.is_empty():
		mesh_instance.mesh = null
		return
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	var normals := _generated_normals(vertices, indices)
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TANGENT] = _generated_tangents(vertices, normals, uvs, indices)
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_TEX_UV2] = uv2s
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	mesh_instance.mesh = mesh
	mesh_instance.material_override = surface.get_material() if surface != null \
		else _default_preview_material()


func _point_vector(record: Dictionary) -> Vector3:
	var raw: Array = record.position
	return Vector3(float(raw[0]), float(raw[1]), float(raw[2]))


func _preview_vertex(authored_point: Vector3) -> Vector3:
	# River points are the hydraulic surface authority. The resolved terrain
	# cuts the channel beneath this level; lifting water to dry ground would
	# hide a missing/invalid cut and disagree with the production water mesh.
	if kind == "river":
		return authored_point
	var terrain := _terrain_control()
	if terrain == null or not terrain.has_method("height_at_local"):
		return authored_point + Vector3.UP * 0.055
	var path_to_terrain: Transform3D = terrain.global_transform.affine_inverse() * \
		global_transform
	var terrain_point := path_to_terrain * authored_point
	var resolved_height: float = terrain.height_at_local(terrain_point.x,
		terrain_point.z)
	if is_nan(resolved_height):
		return authored_point + Vector3.UP * 0.055
	terrain_point.y = resolved_height + 0.055
	return path_to_terrain.affine_inverse() * terrain_point


func _hydraulic_clearance(authored_point: Vector3) -> float:
	var terrain := _terrain_control()
	if terrain == null or not terrain.has_method("height_at_local"):
		return INF
	var path_to_terrain: Transform3D = terrain.global_transform.affine_inverse() * \
		global_transform
	var terrain_point := path_to_terrain * authored_point
	var resolved_height: float = terrain.height_at_local(terrain_point.x,
		terrain_point.z)
	if is_nan(resolved_height):
		return -INF
	return terrain_point.y - resolved_height - 0.015


func _append_clipped_water_triangle(source_indices: Array,
		source_vertices: PackedVector3Array, source_uvs: PackedVector2Array,
		source_uv2s: PackedVector2Array, wet_scalars: PackedFloat32Array,
		vertices: PackedVector3Array, uvs: PackedVector2Array,
		uv2s: PackedVector2Array, indices: PackedInt32Array) -> void:
	var polygon: Array[Dictionary] = []
	var records: Array[Dictionary] = []
	for source_index_value in source_indices:
		var source_index := int(source_index_value)
		records.append({"position": source_vertices[source_index],
			"uv": source_uvs[source_index], "uv2": source_uv2s[source_index],
			"scalar": float(wet_scalars[source_index])})
	for index in records.size():
		var current: Dictionary = records[index]
		var following: Dictionary = records[(index + 1) % records.size()]
		var current_inside := float(current.scalar) > 0.0000001
		var following_inside := float(following.scalar) > 0.0000001
		if current_inside:
			polygon.append(current)
		if current_inside != following_inside:
			var amount := float(current.scalar) / \
				(float(current.scalar) - float(following.scalar))
			polygon.append({"position": (current.position as Vector3).lerp(
				following.position as Vector3, amount),
				"uv": (current.uv as Vector2).lerp(following.uv as Vector2, amount),
				"uv2": (current.uv2 as Vector2).lerp(following.uv2 as Vector2, amount),
				"scalar": 0.0})
	if polygon.size() < 3:
		return
	for index in range(1, polygon.size() - 1):
		for record in [polygon[0], polygon[index], polygon[index + 1]]:
			indices.append(vertices.size())
			vertices.append(record.position)
			uvs.append(record.uv)
			uv2s.append(record.uv2)


func _generated_normals(vertices: PackedVector3Array,
		indices: PackedInt32Array) -> PackedVector3Array:
	var normals := PackedVector3Array()
	normals.resize(vertices.size())
	for triangle_index in range(0, indices.size(), 3):
		var a := indices[triangle_index]
		var b := indices[triangle_index + 1]
		var c := indices[triangle_index + 2]
		var normal := (vertices[b] - vertices[a]).cross(vertices[c] - vertices[a])
		if normal.length_squared() <= 0.0000000001:
			continue
		normal = normal.normalized()
		normals[a] += normal
		normals[b] += normal
		normals[c] += normal
	for index in normals.size():
		normals[index] = normals[index].normalized() if \
			normals[index].length_squared() > 0.0000000001 else Vector3.UP
	return normals


func _generated_tangents(vertices: PackedVector3Array,
		normals: PackedVector3Array, uvs: PackedVector2Array,
		indices: PackedInt32Array) -> PackedFloat32Array:
	var tangent_accum := PackedVector3Array()
	var bitangent_accum := PackedVector3Array()
	tangent_accum.resize(vertices.size())
	bitangent_accum.resize(vertices.size())
	for triangle_index in range(0, indices.size(), 3):
		var a := indices[triangle_index]
		var b := indices[triangle_index + 1]
		var c := indices[triangle_index + 2]
		var edge1 := vertices[b] - vertices[a]
		var edge2 := vertices[c] - vertices[a]
		var uv1 := uvs[b] - uvs[a]
		var uv2 := uvs[c] - uvs[a]
		var determinant := uv1.x * uv2.y - uv1.y * uv2.x
		if absf(determinant) <= 0.000000001:
			continue
		var reciprocal := 1.0 / determinant
		var tangent := (edge1 * uv2.y - edge2 * uv1.y) * reciprocal
		var bitangent := (edge2 * uv1.x - edge1 * uv2.x) * reciprocal
		for index in [a, b, c]:
			tangent_accum[index] += tangent
			bitangent_accum[index] += bitangent
	var tangents := PackedFloat32Array()
	for index in vertices.size():
		var normal := normals[index]
		var tangent := tangent_accum[index] - normal * \
			normal.dot(tangent_accum[index])
		if tangent.length_squared() <= 0.0000000001:
			tangent = Vector3.RIGHT - normal * normal.x
			if tangent.length_squared() <= 0.0000000001:
				tangent = Vector3.FORWARD - normal * normal.z
		tangent = tangent.normalized()
		var handedness := -1.0 if normal.cross(tangent).dot(
			bitangent_accum[index]) < 0.0 else 1.0
		tangents.append_array(PackedFloat32Array([
			tangent.x, tangent.y, tangent.z, handedness]))
	return tangents


func _terrain_control() -> Node3D:
	var container := get_parent()
	var region_root := container.get_parent() if container != null else null
	return region_root.get_node_or_null("Terrain") as Node3D if region_root != null \
		else null


func _default_preview_material() -> Material:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.12, 0.38, 0.58, 0.78) if kind == "river" \
		else Color(0.46, 0.33, 0.20, 1.0)
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA if kind == "river" \
		else BaseMaterial3D.TRANSPARENCY_DISABLED
	material.roughness = 0.45 if kind == "river" else 1.0
	return material


func _current_preview_signature() -> Array:
	var curve_state: Array = []
	if curve != null:
		curve_state.append(curve.closed)
		curve_state.append(curve.bake_interval)
		for index in curve.point_count:
			curve_state.append([curve.get_point_position(index),
				curve.get_point_in(index), curve.get_point_out(index),
				curve.get_point_tilt(index)])
	var terrain := _terrain_control()
	var terrain_revision: int = int(terrain.get("preview_revision")) \
		if terrain != null else -1
	return [curve_state, width_signature(), kind, preview_enabled, snapshot_spacing,
		surface.signature() if surface != null else [], terrain_revision]


func _get_configuration_warnings() -> PackedStringArray:
	var warnings := PackedStringArray()
	if path_id.strip_edges().is_empty():
		warnings.append("Region paths need a stable Path Id before export.")
	if curve == null or curve.point_count < 2:
		warnings.append("Region paths need at least two curve points.")
	if kind == "river" and not replaces_route_id.is_empty():
		warnings.append("River paths cannot replace composer road routes.")
	if kind == "road" and not replaces_plan_feature_id.is_empty():
		warnings.append("Road paths cannot replace planned water features.")
	return warnings
