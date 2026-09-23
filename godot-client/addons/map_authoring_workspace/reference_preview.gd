@tool
class_name MapAuthoringReferencePreview
extends Node3D

signal status_changed(message: String)

const HOST_NAME := "__TerritoryReferenceHost"
const ACTIVE_CLIP_NAME := "ActiveOwnedTerrain"

var active_root: Node3D
var active_entry: Dictionary = {}
var _references: Dictionary = {}
var _source_visibility: Dictionary = {}
var _source_mesh_ids: Dictionary = {}
var _cache: Dictionary = {}
var _cache_order := PackedStringArray()
var _generation := 0


func configure(root: Node3D, entry: Dictionary) -> void:
	clear()
	active_root = root
	active_entry = entry.duplicate(true)
	name = HOST_NAME
	set_meta(&"map_authoring_reference_host", true)


func clear() -> void:
	_generation += 1
	_restore_sources()
	for child in get_children():
		remove_child(child)
		child.queue_free()
	_references.clear()
	_source_mesh_ids.clear()
	active_root = null
	active_entry.clear()


func set_references(entries: Array[Dictionary]) -> void:
	_generation += 1
	var generation := _generation
	_restore_sources()
	for child in get_children():
		remove_child(child)
		child.queue_free()
	_references.clear()
	if entries.is_empty() or active_root == null:
		status_changed.emit("Neighbour references hidden.")
		return
	var active_error := _validate_authored(active_root, active_entry)
	if not active_error.is_empty():
		status_changed.emit(active_error)
		return
	await get_tree().process_frame
	if generation != _generation:
		return
	if not _add_owned_terrain(active_root, active_entry, ACTIVE_CLIP_NAME, false):
		status_changed.emit("Active territory terrain preview is not ready; refresh it and try again.")
		return
	_add_boundary(active_root, active_entry)
	var failures := PackedStringArray()
	for entry in entries:
		if String(entry.id) == String(active_entry.id):
			continue
		var failure := await _add_reference(entry, generation)
		if generation != _generation:
			return
		if not failure.is_empty():
			failures.append(failure)
	status_changed.emit("Showing %d read-only reference%s.%s" % [
		_references.size(), "" if _references.size() == 1 else "s",
		" " + " ".join(failures) if not failures.is_empty() else ""])


func source_state() -> Dictionary:
	return {
		"reference_ids": _references.keys(),
		"hidden_source_count": _source_visibility.size(),
		"active_id": String(active_entry.get("id", "")),
	}


func refresh_if_changed() -> bool:
	if active_root == null or _references.is_empty():
		return false
	var source := active_root.get_node_or_null("Terrain/__TerrainPreview") as MeshInstance3D
	var mesh_id := source.mesh.get_instance_id() if source != null and source.mesh != null else 0
	if int(_source_mesh_ids.get(String(active_entry.id), 0)) == mesh_id:
		return false
	var selected: Array[Dictionary] = []
	for value: Variant in _references.values():
		if value is Dictionary:
			selected.append((value as Dictionary).entry)
	set_references(selected)
	return true


func _add_reference(entry: Dictionary, generation: int) -> String:
	var source_path := String(entry.get("source_path", ""))
	if source_path.is_empty() or not ResourceLoader.exists(source_path):
		return "%s source is unavailable." % String(entry.label)
	var packed := _cache.get(String(entry.get("cache_key", source_path))) as PackedScene
	if packed == null:
		packed = ResourceLoader.load(source_path, "PackedScene",
			ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
		if packed == null:
			return "%s could not load %s." % [String(entry.label), source_path]
		_store_cache(String(entry.get("cache_key", source_path)), packed)
	var instance := packed.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE) as Node3D
	if instance == null:
		return "%s source is not a Node3D scene." % String(entry.label)
	instance.name = "Reference_%s" % String(entry.id)
	instance.position = _relative_translation(entry)
	instance.set_meta(&"map_authoring_reference", true)
	add_child(instance, false, Node.INTERNAL_MODE_FRONT)
	await get_tree().process_frame
	if generation != _generation:
		remove_child(instance)
		instance.queue_free()
		return ""
	if String(entry.source_kind) == "saved_authored":
		var validation := _validate_authored(instance, entry)
		if not validation.is_empty():
			remove_child(instance)
			instance.queue_free()
			return validation
		_hide_authoring_controls(instance)
		if not _add_owned_terrain(instance, entry, "OwnedTerrain_%s" % String(entry.id), true):
			remove_child(instance)
			instance.queue_free()
			return "%s authored terrain preview is unavailable." % String(entry.label)
	else:
		_style_reference_geometry(instance)
		if not _add_published_owned_surfaces(instance, entry):
			remove_child(instance)
			instance.queue_free()
			return "%s published terrain could not be ownership-clipped." % String(entry.label)
	_add_boundary(instance, entry)
	if String(entry.source_kind) == "saved_authored":
		_strip_reference_scripts(instance)
	instance.process_mode = Node.PROCESS_MODE_DISABLED
	_references[String(entry.id)] = {"entry": entry.duplicate(true), "node": instance}
	return ""


func clear_source_cache() -> void:
	_cache.clear()
	_cache_order.clear()


func _store_cache(key: String, packed: PackedScene) -> void:
	_cache[key] = packed
	_cache_order.erase(key)
	_cache_order.append(key)
	while _cache_order.size() > 24:
		_cache.erase(_cache_order[0])
		_cache_order.remove_at(0)


func _validate_authored(root: Node3D, entry: Dictionary) -> String:
	if root == null or String(root.get("region_id")) != String(entry.id):
		return "%s authored scene has the wrong region ID." % String(entry.label)
	var expected := String(root.get("ownership_polygon_sha256"))
	var actual := String(entry.get("ownership_sha256", ""))
	if expected.is_empty() or expected != actual:
		return "%s ownership polygon does not match its saved authored scene; reference hidden." % \
			String(entry.label)
	return ""


func _relative_translation(entry: Dictionary) -> Vector3:
	var reference_translation: Vector3 = entry.translation
	var active_translation_value: Vector3 = active_entry.translation
	return relative_translation(reference_translation, active_translation_value)


static func relative_translation(reference: Vector3, active: Vector3) -> Vector3:
	return reference - active


func _add_owned_terrain(region: Node3D, entry: Dictionary, display_name: String,
		reference_style: bool) -> bool:
	var source := region.get_node_or_null("Terrain/__TerrainPreview") as MeshInstance3D
	if source == null or source.mesh == null:
		return false
	var mesh := clipped_mesh(source, active_root, entry.ownership_polygon,
		active_entry.translation)
	if mesh == null or mesh.get_surface_count() == 0:
		return false
	_hide_source(source)
	var display := MeshInstance3D.new()
	display.name = display_name
	display.mesh = mesh
	display.transform = global_transform.affine_inverse() * source.global_transform
	display.material_override = source.material_override
	display.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF \
		if reference_style else source.cast_shadow
	display.transparency = 0.28 if reference_style else source.transparency
	add_child(display, false, Node.INTERNAL_MODE_FRONT)
	_source_mesh_ids[String(entry.id)] = source.mesh.get_instance_id()
	return true


func _add_published_owned_surfaces(region: Node3D, entry: Dictionary) -> bool:
	var clipped_count := 0
	for child in region.find_children("*", "MeshInstance3D", true, false):
		var source := child as MeshInstance3D
		var source_name := String(source.name)
		if not source_name.begins_with("Terrain_") and \
				not source_name.begins_with("Water_"):
			continue
		var mesh := clipped_mesh(source, active_root, entry.ownership_polygon,
			active_entry.translation)
		_hide_source(source)
		if mesh == null or mesh.get_surface_count() == 0:
			continue
		var display := MeshInstance3D.new()
		display.name = "Owned_%s" % source_name
		display.mesh = mesh
		display.transform = global_transform.affine_inverse() * source.global_transform
		display.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		display.transparency = maxf(source.transparency, 0.28)
		add_child(display, false, Node.INTERNAL_MODE_FRONT)
		clipped_count += 1
	return clipped_count > 0


func _hide_source(source: GeometryInstance3D) -> void:
	var key := source.get_instance_id()
	if not _source_visibility.has(key):
		_source_visibility[key] = {"node": source, "visible": source.visible}
	source.visible = false


func _restore_sources() -> void:
	for value: Variant in _source_visibility.values():
		if value is Dictionary and is_instance_valid(value.node):
			(value.node as GeometryInstance3D).visible = bool(value.visible)
	_source_visibility.clear()


func _hide_authoring_controls(root: Node3D) -> void:
	var gameplay := root.get_node_or_null("Gameplay") as Node3D
	if gameplay != null:
		gameplay.visible = false
	for marker in root.find_children("*", "Marker3D", true, false):
		(marker as Marker3D).visible = false
	root.remove_from_group(&"map_authoring_region")
	_style_reference_geometry(root)


func _style_reference_geometry(root: Node3D) -> void:
	for child in root.find_children("*", "GeometryInstance3D", true, false):
		var geometry := child as GeometryInstance3D
		if not bool(geometry.get_meta(&"map_authoring_owned_terrain", false)):
			geometry.transparency = maxf(geometry.transparency, 0.28)
		geometry.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _strip_reference_scripts(root: Node) -> void:
	for child in root.find_children("*", "", true, false):
		if child.get_script() != null:
			child.set_script(null)
	if root.get_script() != null:
		root.set_script(null)


func _add_boundary(region: Node3D, entry: Dictionary) -> void:
	var polygon: PackedVector2Array = entry.ownership_polygon
	var entry_translation: Vector3 = entry.translation
	var active_translation_value: Vector3 = active_entry.translation
	var vertices := PackedVector3Array()
	var terrain := region.get_node_or_null("Terrain")
	for index in polygon.size():
		var first: Vector2 = polygon[index]
		var second: Vector2 = polygon[(index + 1) % polygon.size()]
		for point_value in [first, second]:
			var point: Vector2 = point_value
			var local: Vector2 = point - Vector2(entry_translation.x,
				entry_translation.z)
			var height := 0.15
			if terrain != null and terrain.has_method("height_at_local"):
				var sampled: float = terrain.call("height_at_local", local.x, local.y)
				if not is_nan(sampled):
					height = sampled + 0.15
			vertices.append(Vector3(point.x - active_translation_value.x, height,
				point.y - active_translation_value.z))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_LINES, arrays)
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = Color(0.18, 0.9, 1.0, 0.9)
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.no_depth_test = true
	mesh.surface_set_material(0, material)
	var boundary := MeshInstance3D.new()
	boundary.name = "OwnershipBoundary_%s" % String(entry.id)
	boundary.mesh = mesh
	boundary.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(boundary, false, Node.INTERNAL_MODE_FRONT)


static func clipped_mesh(source: MeshInstance3D, active: Node3D,
		polygon_global: PackedVector2Array, active_translation: Vector3) -> ArrayMesh:
	if source == null or source.mesh == null or active == null or polygon_global.size() < 3:
		return null
	var result := ArrayMesh.new()
	var source_to_active := active.global_transform.affine_inverse() * source.global_transform
	var edge_bins := _polygon_edge_bins(polygon_global)
	for surface_index in source.mesh.get_surface_count():
		var arrays: Array = source.mesh.surface_get_arrays(surface_index)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var original: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		if vertices.is_empty():
			continue
		if original.is_empty():
			original.resize(vertices.size())
			for index in original.size():
				original[index] = index
		var projected := PackedVector2Array()
		var inside := PackedByteArray()
		projected.resize(vertices.size())
		inside.resize(vertices.size())
		for index in vertices.size():
			var active_point := source_to_active * vertices[index]
			projected[index] = Vector2(active_point.x + active_translation.x,
				active_point.z + active_translation.z)
			inside[index] = 1 if Geometry2D.is_point_in_polygon(
				projected[index], polygon_global) else 0
		var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL] \
			if arrays[Mesh.ARRAY_NORMAL] is PackedVector3Array else PackedVector3Array()
		var tangents: PackedFloat32Array = arrays[Mesh.ARRAY_TANGENT] \
			if arrays[Mesh.ARRAY_TANGENT] is PackedFloat32Array else PackedFloat32Array()
		var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV] \
			if arrays[Mesh.ARRAY_TEX_UV] is PackedVector2Array else PackedVector2Array()
		var uv2s: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV2] \
			if arrays[Mesh.ARRAY_TEX_UV2] is PackedVector2Array else PackedVector2Array()
		var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR] \
			if arrays[Mesh.ARRAY_COLOR] is PackedColorArray else PackedColorArray()
		var output_vertices := vertices.duplicate()
		var output_normals := normals.duplicate()
		var output_tangents := tangents.duplicate()
		var output_uvs := uvs.duplicate()
		var output_uv2s := uv2s.duplicate()
		var output_colors := colors.duplicate()
		var kept := PackedInt32Array()
		for offset in range(0, original.size() - 2, 3):
			var triangle_indices := PackedInt32Array([original[offset], original[offset + 1],
				original[offset + 2]])
			var inside_count := int(inside[triangle_indices[0]]) + \
				int(inside[triangle_indices[1]]) + int(inside[triangle_indices[2]])
			if inside_count == 3:
				kept.append_array(triangle_indices)
				continue
			var triangle := PackedVector2Array([projected[triangle_indices[0]],
				projected[triangle_indices[1]], projected[triangle_indices[2]]])
			if inside_count == 0 and not _triangle_near_boundary(triangle, edge_bins):
				continue
			for piece: PackedVector2Array in Geometry2D.intersect_polygons(
					triangle, polygon_global):
				if piece.size() < 3:
					continue
				var triangulated := Geometry2D.triangulate_polygon(piece)
				if triangulated.is_empty():
					piece = _reversed_polygon(piece)
					triangulated = Geometry2D.triangulate_polygon(piece)
				for clipped_index in triangulated:
					var weights := _barycentric(piece[clipped_index], triangle)
					if weights == null:
						continue
					var new_index := output_vertices.size()
					output_vertices.append(_interpolate_vec3(vertices, triangle_indices, weights))
					if normals.size() == vertices.size():
						output_normals.append(_interpolate_vec3(normals, triangle_indices,
							weights).normalized())
					if tangents.size() == vertices.size() * 4:
						var tangent := _interpolate_tangent(tangents, triangle_indices, weights)
						output_tangents.append_array(PackedFloat32Array([
							tangent.x, tangent.y, tangent.z, tangent.w]))
					if uvs.size() == vertices.size():
						output_uvs.append(_interpolate_vec2(uvs, triangle_indices, weights))
					if uv2s.size() == vertices.size():
						output_uv2s.append(_interpolate_vec2(uv2s, triangle_indices, weights))
					if colors.size() == vertices.size():
						output_colors.append(_interpolate_color(colors, triangle_indices, weights))
					kept.append(new_index)
		if kept.is_empty():
			continue
		var filtered := arrays.duplicate(true)
		filtered[Mesh.ARRAY_VERTEX] = output_vertices
		if normals.size() == vertices.size():
			filtered[Mesh.ARRAY_NORMAL] = output_normals
		if tangents.size() == vertices.size() * 4:
			filtered[Mesh.ARRAY_TANGENT] = output_tangents
		if uvs.size() == vertices.size():
			filtered[Mesh.ARRAY_TEX_UV] = output_uvs
		if uv2s.size() == vertices.size():
			filtered[Mesh.ARRAY_TEX_UV2] = output_uv2s
		if colors.size() == vertices.size():
			filtered[Mesh.ARRAY_COLOR] = output_colors
		filtered[Mesh.ARRAY_INDEX] = kept
		result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, filtered)
		var material := source.mesh.surface_get_material(surface_index)
		if material != null:
			result.surface_set_material(result.get_surface_count() - 1, material)
	return result


static func _polygon_edge_bins(polygon: PackedVector2Array) -> Dictionary:
	var result := {}
	for index in polygon.size():
		var first := polygon[index]
		var second := polygon[(index + 1) % polygon.size()]
		var minimum := Vector2(floorf(minf(first.x, second.x) / 8.0),
			floorf(minf(first.y, second.y) / 8.0))
		var maximum := Vector2(floorf(maxf(first.x, second.x) / 8.0),
			floorf(maxf(first.y, second.y) / 8.0))
		for y in range(int(minimum.y), int(maximum.y) + 1):
			for x in range(int(minimum.x), int(maximum.x) + 1):
				result[Vector2i(x, y)] = true
	return result


static func _triangle_near_boundary(triangle: PackedVector2Array,
		edge_bins: Dictionary) -> bool:
	var minimum := triangle[0]
	var maximum := triangle[0]
	for point in triangle:
		minimum = minimum.min(point)
		maximum = maximum.max(point)
	for y in range(floori(minimum.y / 8.0), floori(maximum.y / 8.0) + 1):
		for x in range(floori(minimum.x / 8.0), floori(maximum.x / 8.0) + 1):
			if edge_bins.has(Vector2i(x, y)):
				return true
	return false


static func _barycentric(point: Vector2, triangle: PackedVector2Array) -> Variant:
	var a := triangle[0]
	var b := triangle[1]
	var c := triangle[2]
	var denominator := (b.y - c.y) * (a.x - c.x) + \
		(c.x - b.x) * (a.y - c.y)
	if absf(denominator) <= 0.0000001:
		return null
	var first := ((b.y - c.y) * (point.x - c.x) + \
		(c.x - b.x) * (point.y - c.y)) / denominator
	var second := ((c.y - a.y) * (point.x - c.x) + \
		(a.x - c.x) * (point.y - c.y)) / denominator
	return Vector3(first, second, 1.0 - first - second)


static func _interpolate_vec3(values: PackedVector3Array, indices: PackedInt32Array,
		weights: Vector3) -> Vector3:
	return values[indices[0]] * weights.x + values[indices[1]] * weights.y + \
		values[indices[2]] * weights.z


static func _interpolate_vec2(values: PackedVector2Array, indices: PackedInt32Array,
		weights: Vector3) -> Vector2:
	return values[indices[0]] * weights.x + values[indices[1]] * weights.y + \
		values[indices[2]] * weights.z


static func _interpolate_color(values: PackedColorArray, indices: PackedInt32Array,
		weights: Vector3) -> Color:
	return values[indices[0]] * weights.x + values[indices[1]] * weights.y + \
		values[indices[2]] * weights.z


static func _interpolate_tangent(values: PackedFloat32Array,
		indices: PackedInt32Array, weights: Vector3) -> Vector4:
	var tangent := Vector3.ZERO
	var handedness := 0.0
	for corner in 3:
		var offset := indices[corner] * 4
		var weight := weights[corner]
		tangent += Vector3(values[offset], values[offset + 1], values[offset + 2]) * weight
		handedness += values[offset + 3] * weight
	tangent = tangent.normalized()
	return Vector4(tangent.x, tangent.y, tangent.z, 1.0 if handedness >= 0.0 else -1.0)


static func _reversed_polygon(polygon: PackedVector2Array) -> PackedVector2Array:
	var result := PackedVector2Array()
	for index in range(polygon.size() - 1, -1, -1):
		result.append(polygon[index])
	return result
