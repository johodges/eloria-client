@tool
class_name MapAuthoringTerrainControl
extends Node3D

const PATCH_SCRIPT := preload("res://src/dev/map_authoring_region/terrain_patch.gd")
const PATH_SCRIPT := preload("res://src/dev/map_authoring_region/path_control.gd")
const GROUND_SCRIPT := preload(
	"res://src/dev/map_authoring_region/ground_region_control.gd")
const GROUND_REGION_MATERIAL := preload(
	"res://src/dev/map_authoring_pilot/style/ground_region_material.gd")

@export var origin := Vector2(-194.0, -500.0)
@export_range(0.25, 16.0, 0.25) var cell_metres := 2.0
@export var grid_size := Vector2i(397, 397)
@export_file("*.f32le", "*.bin") var base_heights_path := ""
@export_file("*.rgba8", "*.bin") var base_colors_path := ""
@export var base_surface: MapAuthoringSurface
@export var preview_enabled := true
@export_range(0.01, 2.0, 0.01) var preview_uv_metres_inverse := 0.24

var _base_heights := PackedFloat32Array()
var _effective_heights := PackedFloat32Array()
var _base_colors := PackedColorArray()
var _loaded_path := ""
var _loaded_sha := ""
var _loaded_colors_path := ""
var _loaded_colors_sha := ""
var _preview_signature: Array = []
var _elapsed := 0.0
var _bound_surface: MapAuthoringSurface
var last_error := ""
var preview_revision := 0


func _ready() -> void:
	set_process(true)
	_sync_surface()
	refresh_preview()


func _process(delta: float) -> void:
	if base_surface != _bound_surface:
		_sync_surface()
	if not Engine.is_editor_hint():
		return
	_elapsed += delta
	if _elapsed < 0.18:
		return
	_elapsed = 0.0
	var signature := _current_signature()
	if signature != _preview_signature:
		refresh_preview()


func refresh_preview() -> bool:
	last_error = ""
	if not _load_base_heights():
		_clear_preview()
		update_configuration_warnings()
		return false
	if not _load_base_colors():
		_clear_preview()
		update_configuration_warnings()
		return false
	_apply_patches()
	_apply_path_effects()
	_preview_signature = _current_signature()
	if preview_enabled:
		_build_preview_mesh()
		_build_ground_region_previews()
	else:
		_clear_preview()
	preview_revision += 1
	update_configuration_warnings()
	return true


func base_heights() -> PackedFloat32Array:
	_load_base_heights()
	return _base_heights.duplicate()


func effective_heights() -> PackedFloat32Array:
	if _effective_heights.size() != grid_size.x * grid_size.y:
		refresh_preview()
	return _effective_heights.duplicate()


func base_sha256() -> String:
	_load_base_heights()
	return _loaded_sha


func patch_records() -> Array[Dictionary]:
	var records: Array[Dictionary] = []
	var patches := get_node_or_null("Patches")
	if patches == null:
		return records
	for child in patches.get_children():
		if _uses_script(child, PATCH_SCRIPT):
			var patch = child
			records.append(patch.snapshot_record(global_transform.affine_inverse() *
				patch.global_transform))
	records.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return String(a.id) < String(b.id))
	return records


func height_at_local(x: float, z: float) -> float:
	if _effective_heights.size() != grid_size.x * grid_size.y:
		refresh_preview()
	if _effective_heights.is_empty():
		return NAN
	var fx := clampf((x - origin.x) / cell_metres, 0.0, float(grid_size.x - 1))
	var fz := clampf((z - origin.y) / cell_metres, 0.0, float(grid_size.y - 1))
	var x0 := mini(floori(fx), grid_size.x - 2)
	var z0 := mini(floori(fz), grid_size.y - 2)
	var tx := fx - float(x0)
	var tz := fz - float(z0)
	var h00 := _height(x0, z0)
	var h10 := _height(x0 + 1, z0)
	var h01 := _height(x0, z0 + 1)
	var h11 := _height(x0 + 1, z0 + 1)
	if tx + tz <= 1.0:
		return h00 + (h10 - h00) * tx + (h01 - h00) * tz
	return h11 + (h01 - h11) * (1.0 - tx) + (h10 - h11) * (1.0 - tz)


## Returns the highest authored river surface covering this terrain-local point.
## River widths are full metres, matching snapshots and the production composer.
func river_water_height_at_local(x: float, z: float) -> Variant:
	var sample := Vector2(x, z)
	var highest := -INF
	var found := false
	for path in _region_paths():
		if path.kind != "river" or path.curve == null or path.curve.point_count < 2:
			continue
		var points: Array[Dictionary] = path.snapshot_points()
		var path_to_terrain: Transform3D = global_transform.affine_inverse() * \
			path.global_transform
		var width_scale := Vector2(path_to_terrain.basis.x.x,
			path_to_terrain.basis.x.z).length()
		for segment_index in points.size() - 1:
			var first := path_to_terrain * _record_point(points[segment_index])
			var second := path_to_terrain * _record_point(points[segment_index + 1])
			var start_xz := Vector2(first.x, first.z)
			var delta := Vector2(second.x - first.x, second.z - first.z)
			var length_squared := delta.length_squared()
			if length_squared <= 0.000001:
				continue
			var amount := clampf((sample - start_xz).dot(delta) / length_squared,
				0.0, 1.0)
			var nearest := start_xz + delta * amount
			var first_width := float(points[segment_index].width) * width_scale
			var second_width := float(points[segment_index + 1].width) * width_scale
			var half_width := lerpf(first_width, second_width, amount) * 0.5
			if sample.distance_to(nearest) > half_width:
				continue
			found = true
			highest = maxf(highest, lerpf(first.y, second.y, amount))
	return highest if found else null


func intersect_local_segment(segment_start: Vector3, segment_end: Vector3) -> Variant:
	if _effective_heights.size() != grid_size.x * grid_size.y:
		refresh_preview()
	if _effective_heights.is_empty():
		return null
	var minimum_height := INF
	var maximum_height := -INF
	for value in _effective_heights:
		minimum_height = minf(minimum_height, value)
		maximum_height = maxf(maximum_height, value)
	var bounds := AABB(Vector3(origin.x, minimum_height - 0.1, origin.y), Vector3(
		float(grid_size.x - 1) * cell_metres, maximum_height - minimum_height + 0.2,
		float(grid_size.y - 1) * cell_metres))
	if bounds.intersects_segment(segment_start, segment_end) == null:
		return null
	var min_x := clampi(floori((minf(segment_start.x, segment_end.x) - origin.x) /
		cell_metres) - 1, 0, grid_size.x - 2)
	var max_x := clampi(ceili((maxf(segment_start.x, segment_end.x) - origin.x) /
		cell_metres) + 1, 0, grid_size.x - 2)
	var min_z := clampi(floori((minf(segment_start.z, segment_end.z) - origin.y) /
		cell_metres) - 1, 0, grid_size.y - 2)
	var max_z := clampi(ceili((maxf(segment_start.z, segment_end.z) - origin.y) /
		cell_metres) + 1, 0, grid_size.y - 2)
	var nearest: Variant = null
	var nearest_distance := INF
	for z_index in range(min_z, max_z + 1):
		for x_index in range(min_x, max_x + 1):
			var p00 := _point(x_index, z_index)
			var p10 := _point(x_index + 1, z_index)
			var p01 := _point(x_index, z_index + 1)
			var p11 := _point(x_index + 1, z_index + 1)
			var triangles: Array = [[p00, p01, p10], [p10, p01, p11]]
			for triangle_value in triangles:
				var triangle: Array = triangle_value
				var hit: Variant = Geometry3D.segment_intersects_triangle(segment_start,
					segment_end, triangle[0], triangle[1], triangle[2])
				if hit is Vector3:
					var distance := segment_start.distance_squared_to(hit as Vector3)
					if distance < nearest_distance:
						nearest_distance = distance
						nearest = hit
	return nearest


func _load_base_heights() -> bool:
	if grid_size.x < 2 or grid_size.y < 2 or cell_metres <= 0.0:
		last_error = "Terrain grid needs at least 2×2 samples and a positive cell size."
		return false
	if base_heights_path.strip_edges().is_empty():
		last_error = "Terrain Base Heights Path is empty."
		return false
	var absolute := ProjectSettings.globalize_path(base_heights_path)
	if not FileAccess.file_exists(absolute):
		last_error = "Terrain base heights file is missing: %s" % base_heights_path
		return false
	var sha := FileAccess.get_sha256(absolute)
	if base_heights_path == _loaded_path and sha == _loaded_sha and \
			_base_heights.size() == grid_size.x * grid_size.y:
		return true
	var file := FileAccess.open(absolute, FileAccess.READ)
	if file == null:
		last_error = "Could not open terrain base heights: %s" % base_heights_path
		return false
	var expected_bytes := grid_size.x * grid_size.y * 4
	if file.get_length() != expected_bytes:
		last_error = "Terrain base heights has %d bytes; expected %d for %d×%d float32 samples." % [
			file.get_length(), expected_bytes, grid_size.x, grid_size.y]
		return false
	file.big_endian = false
	var loaded := PackedFloat32Array()
	loaded.resize(grid_size.x * grid_size.y)
	for index in loaded.size():
		loaded[index] = file.get_float()
		if not is_finite(loaded[index]):
			last_error = "Terrain base heights contains a non-finite sample at %d." % index
			return false
	_base_heights = loaded
	_loaded_path = base_heights_path
	_loaded_sha = sha
	return true


func _load_base_colors() -> bool:
	if base_colors_path.strip_edges().is_empty():
		_base_colors = PackedColorArray()
		_loaded_colors_path = ""
		_loaded_colors_sha = ""
		return true
	var absolute := ProjectSettings.globalize_path(base_colors_path)
	if not FileAccess.file_exists(absolute):
		last_error = "Terrain base colors file is missing: %s" % base_colors_path
		return false
	var sha := FileAccess.get_sha256(absolute)
	if base_colors_path == _loaded_colors_path and sha == _loaded_colors_sha and \
			_base_colors.size() == grid_size.x * grid_size.y:
		return true
	var bytes := FileAccess.get_file_as_bytes(absolute)
	var expected_bytes := grid_size.x * grid_size.y * 4
	if bytes.size() != expected_bytes:
		last_error = "Terrain base colors has %d bytes; expected %d for %d×%d RGBA8 samples." % [
			bytes.size(), expected_bytes, grid_size.x, grid_size.y]
		return false
	var loaded := PackedColorArray()
	loaded.resize(grid_size.x * grid_size.y)
	for index in loaded.size():
		var offset := index * 4
		loaded[index] = Color8(bytes[offset], bytes[offset + 1], bytes[offset + 2],
			bytes[offset + 3])
	_base_colors = loaded
	_loaded_colors_path = base_colors_path
	_loaded_colors_sha = sha
	return true


func _apply_patches() -> void:
	_effective_heights = _base_heights.duplicate()
	var patches := get_node_or_null("Patches")
	if patches == null:
		return
	var ordered: Array = []
	for child in patches.get_children():
		if _uses_script(child, PATCH_SCRIPT):
			ordered.append(child)
	ordered.sort_custom(func(a: Variant, b: Variant) -> bool:
		return String(a.patch_id) < String(b.patch_id))
	for patch in ordered:
		if not patch.enabled:
			continue
		var half: Vector2 = patch.size * 0.5
		var patch_to_terrain: Transform3D = global_transform.affine_inverse() * patch.global_transform
		var corners: Array[Vector3] = []
		for corner in [Vector3(-half.x, 0.0, -half.y), Vector3(half.x, 0.0, -half.y),
				Vector3(half.x, 0.0, half.y), Vector3(-half.x, 0.0, half.y)]:
			corners.append(patch_to_terrain * corner)
		var minimum := Vector2(INF, INF)
		var maximum := Vector2(-INF, -INF)
		for corner in corners:
			minimum = minimum.min(Vector2(corner.x, corner.z))
			maximum = maximum.max(Vector2(corner.x, corner.z))
		var x0 := clampi(floori((minimum.x - origin.x) / cell_metres),
			0, grid_size.x - 1)
		var x1 := clampi(ceili((maximum.x - origin.x) / cell_metres),
			0, grid_size.x - 1)
		var z0 := clampi(floori((minimum.y - origin.y) / cell_metres),
			0, grid_size.y - 1)
		var z1 := clampi(ceili((maximum.y - origin.y) / cell_metres),
			0, grid_size.y - 1)
		for z_index in range(z0, z1 + 1):
			for x_index in range(x0, x1 + 1):
				var sample := Vector2(origin.x + float(x_index) * cell_metres,
					origin.y + float(z_index) * cell_metres)
				var weight: float = patch.weight_at_transform(sample, patch_to_terrain)
				if weight <= 0.0:
					continue
				var index := z_index * grid_size.x + x_index
				if patch.operation == PATCH_SCRIPT.Operation.ADD:
					_effective_heights[index] += patch_to_terrain.origin.y * weight
				else:
					_effective_heights[index] = lerpf(_effective_heights[index],
						patch_to_terrain.origin.y, weight)


func _apply_path_effects() -> void:
	var paths := _region_paths()
	paths.sort_custom(func(a: Variant, b: Variant) -> bool:
		if (a.kind == "river") != (b.kind == "river"):
			return a.kind != "river"
		return String(a.path_id) < String(b.path_id))
	for path in paths:
		if path.curve == null or path.curve.point_count < 2 or \
				not bool(path.properties.get("terrainConform", true)):
			continue
		var points: Array[Dictionary] = path.snapshot_points()
		var path_to_terrain: Transform3D = global_transform.affine_inverse() * \
			path.global_transform
		var path_width_scale := Vector2(path_to_terrain.basis.x.x,
			path_to_terrain.basis.x.z).length()
		if path.kind == "river":
			_apply_river_effect(path, points, path_to_terrain, path_width_scale)
			continue
		for segment_index in points.size() - 1:
			var first := path_to_terrain * _record_point(points[segment_index])
			var second := path_to_terrain * _record_point(points[segment_index + 1])
			var first_width := float(points[segment_index].width) * path_width_scale
			var second_width := float(points[segment_index + 1].width) * path_width_scale
			var feather := float(path.properties.get("terrainFeather",
				2.0 if path.kind == "road" else 5.5))
			var reach := maxf(first_width, second_width) * 0.5 + maxf(0.0, feather)
			var x0 := clampi(floori((minf(first.x, second.x) - reach - origin.x) /
				cell_metres), 0, grid_size.x - 1)
			var x1 := clampi(ceili((maxf(first.x, second.x) + reach - origin.x) /
				cell_metres), 0, grid_size.x - 1)
			var z0 := clampi(floori((minf(first.z, second.z) - reach - origin.y) /
				cell_metres), 0, grid_size.y - 1)
			var z1 := clampi(ceili((maxf(first.z, second.z) + reach - origin.y) /
				cell_metres), 0, grid_size.y - 1)
			var start_xz := Vector2(first.x, first.z)
			var delta := Vector2(second.x - first.x, second.z - first.z)
			var length_squared := delta.length_squared()
			if length_squared <= 0.000001:
				continue
			for z_index in range(z0, z1 + 1):
				for x_index in range(x0, x1 + 1):
					var sample := Vector2(origin.x + float(x_index) * cell_metres,
						origin.y + float(z_index) * cell_metres)
					var amount := clampf((sample - start_xz).dot(delta) /
						length_squared, 0.0, 1.0)
					var nearest := start_xz + delta * amount
					var distance := sample.distance_to(nearest)
					var half_width := lerpf(first_width, second_width, amount) * 0.5
					if distance > half_width + feather:
						continue
					var weight := 1.0 if distance <= half_width else \
						_smooth_weight(1.0 - (distance - half_width) / maxf(feather, 0.000001))
					var path_y := lerpf(first.y, second.y, amount)
					var index := z_index * grid_size.x + x_index
					_effective_heights[index] = lerpf(_effective_heights[index], path_y, weight)


func _apply_river_effect(path: Node, points: Array[Dictionary],
		path_to_terrain: Transform3D, path_width_scale: float) -> void:
	# Resolve the strongest segment influence first, then apply the river once.
	# This avoids deepening a bend merely because its densely sampled segments
	# overlap, and makes zero influence at the feather edge truly unchanged.
	var sample_count := grid_size.x * grid_size.y
	var best_weights := PackedFloat32Array()
	best_weights.resize(sample_count)
	best_weights.fill(0.0)
	var best_beds := PackedFloat32Array()
	best_beds.resize(sample_count)
	best_beds.fill(INF)
	var feather := maxf(0.0, float(path.properties.get("terrainFeather", 5.5)))
	var depth := maxf(0.0, float(path.properties.get("channelDepth", 1.45)))
	for segment_index in points.size() - 1:
		var first := path_to_terrain * _record_point(points[segment_index])
		var second := path_to_terrain * _record_point(points[segment_index + 1])
		var first_width := float(points[segment_index].width) * path_width_scale
		var second_width := float(points[segment_index + 1].width) * path_width_scale
		var reach := maxf(first_width, second_width) * 0.5 + feather
		var x0 := clampi(floori((minf(first.x, second.x) - reach - origin.x) /
			cell_metres), 0, grid_size.x - 1)
		var x1 := clampi(ceili((maxf(first.x, second.x) + reach - origin.x) /
			cell_metres), 0, grid_size.x - 1)
		var z0 := clampi(floori((minf(first.z, second.z) - reach - origin.y) /
			cell_metres), 0, grid_size.y - 1)
		var z1 := clampi(ceili((maxf(first.z, second.z) + reach - origin.y) /
			cell_metres), 0, grid_size.y - 1)
		var start_xz := Vector2(first.x, first.z)
		var delta := Vector2(second.x - first.x, second.z - first.z)
		var length_squared := delta.length_squared()
		if length_squared <= 0.000001:
			continue
		for z_index in range(z0, z1 + 1):
			for x_index in range(x0, x1 + 1):
				var sample := Vector2(origin.x + float(x_index) * cell_metres,
					origin.y + float(z_index) * cell_metres)
				var amount := clampf((sample - start_xz).dot(delta) /
					length_squared, 0.0, 1.0)
				var nearest := start_xz + delta * amount
				var distance := sample.distance_to(nearest)
				var half_width := lerpf(first_width, second_width, amount) * 0.5
				if distance > half_width + feather:
					continue
				var weight := 1.0 if distance <= half_width else \
					_smooth_weight(1.0 - (distance - half_width) / \
					maxf(feather, 0.000001))
				if weight <= 0.0:
					continue
				var bed := lerpf(first.y, second.y, amount) - depth
				var index := z_index * grid_size.x + x_index
				if weight > best_weights[index] + 0.000001 or \
						(absf(weight - best_weights[index]) <= 0.000001 and
						bed < best_beds[index]):
					best_weights[index] = weight
					best_beds[index] = bed
	for index in sample_count:
		var weight := best_weights[index]
		if weight <= 0.0:
			continue
		var original := _effective_heights[index]
		var lowered := minf(original, best_beds[index])
		_effective_heights[index] = lerpf(original, lowered, weight)


func _build_preview_mesh() -> void:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	var indices := PackedInt32Array()
	vertices.resize(grid_size.x * grid_size.y)
	normals.resize(vertices.size())
	uvs.resize(vertices.size())
	for z_index in grid_size.y:
		for x_index in grid_size.x:
			var index := z_index * grid_size.x + x_index
			vertices[index] = _point(x_index, z_index)
			var left := _height(maxi(0, x_index - 1), z_index)
			var right := _height(mini(grid_size.x - 1, x_index + 1), z_index)
			var back := _height(x_index, maxi(0, z_index - 1))
			var front := _height(x_index, mini(grid_size.y - 1, z_index + 1))
			normals[index] = Vector3(left - right, 2.0 * cell_metres,
				back - front).normalized()
			uvs[index] = Vector2(vertices[index].x, vertices[index].z) * \
				preview_uv_metres_inverse
	for z_index in grid_size.y - 1:
		for x_index in grid_size.x - 1:
			var index := z_index * grid_size.x + x_index
			indices.append_array(PackedInt32Array([index, index + grid_size.x,
				index + 1, index + 1, index + grid_size.x, index + grid_size.x + 1]))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TANGENT] = _generated_tangents(vertices, normals, uvs,
		indices)
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	if not _base_colors.is_empty():
		arrays[Mesh.ARRAY_COLOR] = _base_colors
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var preview := get_node_or_null("__TerrainPreview") as MeshInstance3D
	if preview == null:
		preview = MeshInstance3D.new()
		preview.name = "__TerrainPreview"
		add_child(preview)
	preview.mesh = mesh
	preview.material_override = base_surface.get_material() if base_surface != null else null


func _build_ground_region_previews() -> void:
	var old := get_node_or_null("__GroundRegionPreviews")
	if old != null:
		remove_child(old)
		old.queue_free()
	var container := Node3D.new()
	container.name = "__GroundRegionPreviews"
	add_child(container)
	var regions := _ground_regions()
	regions.sort_custom(func(a: Variant, b: Variant) -> bool:
		if a.priority == b.priority:
			return String(a.get_path()) < String(b.get_path())
		return a.priority < b.priority)
	for region_index in mini(regions.size(), 127):
		var region: Node3D = regions[region_index]
		if not region.enabled or not region.is_visible_in_tree() or region.surface == null:
			continue
		region.surface.enable_region_uv_projection()
		var bounds: Rect2 = region.world_bounds()
		if bounds.size.x <= 0.0 or bounds.size.y <= 0.0:
			continue
		var x0 := clampi(floori((bounds.position.x - global_position.x - origin.x) /
			cell_metres) - 1, 0, grid_size.x - 2)
		var x1 := clampi(ceili((bounds.end.x - global_position.x - origin.x) /
			cell_metres) + 1, 0, grid_size.x - 2)
		var z0 := clampi(floori((bounds.position.y - global_position.z - origin.y) /
			cell_metres) - 1, 0, grid_size.y - 2)
		var z1 := clampi(ceili((bounds.end.y - global_position.z - origin.y) /
			cell_metres) + 1, 0, grid_size.y - 2)
		var vertices := PackedVector3Array()
		var normals := PackedVector3Array()
		var uvs := PackedVector2Array()
		var indices := PackedInt32Array()
		for z_index in range(z0, z1 + 1):
			for x_index in range(x0, x1 + 1):
				var p00 := _point(x_index, z_index) + Vector3.UP * 0.008
				var p10 := _point(x_index + 1, z_index) + Vector3.UP * 0.008
				var p01 := _point(x_index, z_index + 1) + Vector3.UP * 0.008
				var p11 := _point(x_index + 1, z_index + 1) + Vector3.UP * 0.008
				var quad := PackedVector3Array([p00, p01, p10, p10, p01, p11])
				var normal0 := (p01 - p00).cross(p10 - p00).normalized()
				var normal1 := (p01 - p10).cross(p11 - p10).normalized()
				for vertex in quad:
					indices.append(vertices.size())
					vertices.append(vertex)
					uvs.append(Vector2(vertex.x, vertex.z) *
						preview_uv_metres_inverse)
				for unused in 3:
					normals.append(normal0)
				for unused in 3:
					normals.append(normal1)
		if vertices.is_empty():
			continue
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = vertices
		arrays[Mesh.ARRAY_NORMAL] = normals
		arrays[Mesh.ARRAY_TANGENT] = _generated_tangents(vertices, normals, uvs,
			indices)
		arrays[Mesh.ARRAY_TEX_UV] = uvs
		arrays[Mesh.ARRAY_INDEX] = indices
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		var instance := MeshInstance3D.new()
		instance.name = "GroundRegion_%s" % region.region_id
		instance.mesh = mesh
		instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var projected: Variant = region.projected_world_to_local()
		if projected == null:
			continue
		instance.material_override = GROUND_REGION_MATERIAL.create(region.surface,
			projected as Transform2D, region.size * 0.5, region.shape,
			region.blend_width, region.opacity, -128 + region_index)
		if instance.material_override != null:
			container.add_child(instance)


func _clear_preview() -> void:
	var preview := get_node_or_null("__TerrainPreview") as MeshInstance3D
	if preview != null:
		preview.mesh = null
	var ground := get_node_or_null("__GroundRegionPreviews")
	if ground != null:
		ground.queue_free()


func _height(x_index: int, z_index: int) -> float:
	return _effective_heights[z_index * grid_size.x + x_index]


func _point(x_index: int, z_index: int) -> Vector3:
	return Vector3(origin.x + float(x_index) * cell_metres,
		_height(x_index, z_index), origin.y + float(z_index) * cell_metres)


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
		var tangent := tangent_accum[index] - normal * normal.dot(
			tangent_accum[index])
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


func _current_signature() -> Array:
	var patches: Array = []
	var container := get_node_or_null("Patches")
	if container != null:
		for child in container.get_children():
			if _uses_script(child, PATCH_SCRIPT):
				patches.append([child.patch_id, child.transform, child.shape,
					child.operation, child.size, child.feather, child.height_value,
					child.enabled])
	var paths: Array = []
	for path in _region_paths():
		paths.append([path.path_id, path.kind, path.transform, path.properties,
			path.snapshot_points(), path.width_signature()])
	var grounds: Array = []
	for region in _ground_regions():
		grounds.append([region.region_id, region.region_signature()])
	return [origin, cell_metres, grid_size, base_heights_path,
		FileAccess.get_sha256(ProjectSettings.globalize_path(base_heights_path))
			if not base_heights_path.is_empty() and FileAccess.file_exists(
				ProjectSettings.globalize_path(base_heights_path)) else "",
		base_colors_path,
		FileAccess.get_sha256(ProjectSettings.globalize_path(base_colors_path))
			if not base_colors_path.is_empty() and FileAccess.file_exists(
				ProjectSettings.globalize_path(base_colors_path)) else "",
		base_surface.signature() if base_surface != null else [], preview_enabled,
		preview_uv_metres_inverse, patches, paths, grounds]


func _region_paths() -> Array:
	var result: Array = []
	var region_root := get_parent()
	if region_root == null:
		return result
	for container_name in ["Roads", "Rivers"]:
		var container := region_root.get_node_or_null(NodePath(container_name))
		if container == null:
			continue
		for child in container.get_children():
			if _uses_script(child, PATH_SCRIPT):
				result.append(child)
	return result


func _ground_regions() -> Array:
	var result: Array = []
	var region_root := get_parent()
	var container := region_root.get_node_or_null("Ground/Regions") if region_root != null else null
	if container == null:
		return result
	for child in container.get_children():
		if _uses_script(child, GROUND_SCRIPT):
			result.append(child)
	return result


func _uses_script(value: Variant, script: Script) -> bool:
	return value is Object and (value as Object).get_script() == script


func _record_point(record: Dictionary) -> Vector3:
	var raw: Array = record.position
	return Vector3(float(raw[0]), float(raw[1]), float(raw[2]))


func _smooth_weight(value: float) -> float:
	var amount := clampf(value, 0.0, 1.0)
	return amount * amount * (3.0 - 2.0 * amount)


func _sync_surface() -> void:
	if base_surface != null:
		base_surface = base_surface.duplicate(true) as MapAuthoringSurface
		base_surface.resource_local_to_scene = true
		base_surface.enable_region_uv_projection()
	_bound_surface = base_surface


func _get_configuration_warnings() -> PackedStringArray:
	var warnings := PackedStringArray()
	if not last_error.is_empty():
		warnings.append(last_error)
	if base_surface == null:
		warnings.append("Terrain needs a local Base Surface before export.")
	return warnings
